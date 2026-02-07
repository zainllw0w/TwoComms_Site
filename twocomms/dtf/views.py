from decimal import Decimal, InvalidOperation
from itertools import groupby
import xml.etree.ElementTree as ET
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, NoReverseMatch
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.translation import gettext_lazy as _

from .forms import (
    DtfBuilderSessionForm,
    DtfFabLeadForm,
    DtfHelpForm,
    DtfOrderForm,
    DtfSampleLeadForm,
)
from .models import (
    BuilderStatus,
    DtfOrder,
    DtfBuilderSession,
    DtfLead,
    DtfLeadAttachment,
    DtfSampleLead,
    DtfWork,
    WorkCategory,
    OrderStatus,
    LeadType,
    LengthSource,
    KnowledgePost,
)
from .telegram import (
    notify_new_lead,
    notify_new_order,
    notify_need_fix,
    notify_awaiting_payment,
    notify_paid,
    notify_shipped,
)
from .utils import (
    activate_language_from_request,
    build_lang_links,
    calculate_pricing,
    get_file_extension,
    get_feature_flags,
    get_limits,
    get_pricing_config,
    normalize_phone,
)
from .utils import ALLOWED_READY_EXTS


STATUS_STEPS = [
    (OrderStatus.NEW_ORDER, _("Прийнято")),
    (OrderStatus.CHECK_MOCKUP, _("Перевірка макета")),
    (OrderStatus.AWAITING_PAYMENT, _("Очікує оплати")),
    (OrderStatus.PRINTING, _("У друці")),
    (OrderStatus.READY, _("Готово")),
    (OrderStatus.SHIPPED, _("Відправлено")),
    (OrderStatus.CLOSED, _("Закрито")),
]


def _get_published_posts():
    return list(
        KnowledgePost.objects.published()
        .order_by("-pub_date", "-id")
    )


def _group_posts_by_month(posts):
    def month_key(post):
        return post.pub_date.strftime("%Y-%m")

    ordered = sorted(posts, key=lambda post: post.pub_date, reverse=True)
    groups = []
    for key, items in groupby(ordered, key=month_key):
        chunk = list(items)
        if not chunk:
            continue
        anchor = chunk[0].pub_date
        groups.append({
            "key": key,
            "month": anchor,
            "posts": chunk,
        })
    return groups


def _build_initials(value: str | None, fallback: str = "U") -> str:
    source = (value or "").strip() or (fallback or "").strip()
    if not source:
        return "U"
    parts = [chunk for chunk in source.replace("_", " ").split() if chunk]
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    return parts[0][:2].upper() if parts else source[:2].upper()


def _extract_profile_meta(user):
    if not user.is_authenticated:
        return {
            "display_name": _("Гість"),
            "initials": "TC",
            "avatar_url": "",
            "can_management": False,
            "can_store_admin": False,
            "can_django_admin": False,
        }

    profile = None
    try:
        profile = user.userprofile
    except Exception:
        profile = None

    profile_name = (getattr(profile, "full_name", "") or "").strip() if profile else ""
    display_name = profile_name or (user.get_full_name() or "").strip() or user.username
    avatar_url = ""
    if profile:
        avatar_field = getattr(profile, "avatar", None)
        if avatar_field:
            try:
                if getattr(avatar_field, "name", ""):
                    avatar_url = avatar_field.url
            except Exception:
                avatar_url = ""

    can_management = bool(
        user.is_staff
        or user.is_superuser
        or (profile and bool(getattr(profile, "is_manager", False)))
    )
    can_store_admin = bool(user.is_staff)
    can_django_admin = bool(user.is_staff or user.is_superuser)
    return {
        "display_name": display_name,
        "initials": _build_initials(display_name, fallback=user.username),
        "avatar_url": avatar_url,
        "can_management": can_management,
        "can_store_admin": can_store_admin,
        "can_django_admin": can_django_admin,
    }


def _resolve_platform_hosts(request):
    scheme = "https" if request.is_secure() else "http"
    current_host = request.get_host().split(":")[0].lower()
    if current_host.endswith(".twocomms.shop"):
        main_host = "twocomms.shop"
    elif current_host in {"twocomms.shop", "www.twocomms.shop"}:
        main_host = "twocomms.shop"
    else:
        main_host = current_host

    management_host = f"management.{main_host}" if main_host not in {"localhost", "127.0.0.1"} else main_host
    return scheme, current_host, main_host, management_host


def _base_context(request):
    lang = activate_language_from_request(request)
    pricing = get_pricing_config()
    rates = [pricing["base_rate"], *[tier["rate"] for tier in pricing["tiers"]]]
    pricing_rate_high = max(rates) if rates else pricing["base_rate"]
    pricing_rate_low = min(rates) if rates else pricing["base_rate"]
    profile_meta = _extract_profile_meta(request.user)
    scheme, current_host, main_host, management_host = _resolve_platform_hosts(request)
    current_url = request.build_absolute_uri()
    next_param = quote(current_url, safe="")
    next_path_param = quote(request.get_full_path() or "/", safe="")
    try:
        google_login_path = reverse("social:begin", args=("google-oauth2",))
    except NoReverseMatch:
        google_login_path = "/oauth/login/google-oauth2/"
    profile_links = {
        "login": f"{scheme}://{main_host}/login/?next={next_param}",
        "register": f"{scheme}://{main_host}/register/?next={next_param}",
        "google_login": (
            f"{scheme}://{current_host}"
            f"{google_login_path}"
            f"?next={next_path_param}"
        ),
        "profile": f"{scheme}://{main_host}/profile/setup/",
        "orders": f"{scheme}://{main_host}/my/orders/",
        "store_admin": f"{scheme}://{main_host}/admin-panel/",
        "management_home": f"{scheme}://{management_host}/",
        "management_login": f"{scheme}://{management_host}/login/",
        "django_admin": f"{scheme}://{current_host}/admin/",
    }
    return {
        "current_lang": lang,
        "lang_links": build_lang_links(request),
        "pricing": pricing,
        "pricing_rate_high": pricing_rate_high,
        "pricing_rate_low": pricing_rate_low,
        "pricing_range_label": f"{pricing_rate_high}-{pricing_rate_low}",
        "limits": get_limits(),
        "feature_flags": get_feature_flags(),
        "profile_display_name": profile_meta["display_name"],
        "profile_initials": profile_meta["initials"],
        "profile_avatar_url": profile_meta["avatar_url"],
        "profile_can_management": profile_meta["can_management"],
        "profile_can_store_admin": profile_meta["can_store_admin"],
        "profile_can_django_admin": profile_meta["can_django_admin"],
        "profile_links": profile_links,
    }


def _is_rate_limited(request, key_prefix: str, *, limit: int = 5, window_seconds: int = 3600) -> bool:
    ip = (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "unknown").split(",")[0].strip()
    key = f"dtf:{key_prefix}:{ip}"
    current = cache.get(key, 0)
    if current >= limit:
        return True
    cache.set(key, current + 1, timeout=window_seconds)
    return False


def _get_user_phone_digits(user):
    if not user or not user.is_authenticated:
        return ""
    try:
        profile = user.userprofile
    except Exception:
        profile = None
    profile_phone = ""
    if profile:
        profile_phone = (
            getattr(profile, "phone", "")
            or getattr(profile, "phone_number", "")
            or getattr(profile, "mobile", "")
            or ""
        )
    return normalize_phone(profile_phone)


def _calc_loyalty_meta(order_count: int):
    points_per_order = int(getattr(settings, "DTF_LOYALTY_POINTS_PER_ORDER", 10))
    manager_badge_after = int(getattr(settings, "DTF_LOYALTY_MANAGER_BADGE_AFTER_ORDERS", 5))
    points = max(0, order_count) * max(1, points_per_order)
    return {
        "order_count": max(0, order_count),
        "points": points,
        "points_per_order": points_per_order,
        "manager_badge_after": manager_badge_after,
        "has_manager_badge": order_count >= manager_badge_after,
    }


def _build_constructor_task_description(builder_session: DtfBuilderSession) -> str:
    payload = [
        f"Builder session: {builder_session.session_id}",
        f"Product: {builder_session.product_type}",
        f"Placement: {builder_session.placement}",
        f"Color: {builder_session.product_color}",
        f"Qty: {builder_session.quantity}",
    ]
    if builder_session.size_breakdown_json:
        payload.append(f"Sizes: {builder_session.size_breakdown_json}")
    if builder_session.delivery_city or builder_session.delivery_np_branch:
        payload.append(f"Delivery: {builder_session.delivery_city} / {builder_session.delivery_np_branch}")
    if builder_session.preflight_json:
        payload.append(f"Preflight: {builder_session.preflight_json}")
    if builder_session.comment:
        payload.append(f"Comment: {builder_session.comment}")
    return "\n".join(payload)


def _render(request, template, context, status: int | None = None):
    response = render(request, template, context, status=status)
    lang = request.GET.get("lang")
    if lang in ("uk", "ru", "en"):
        response.set_cookie("dtf_lang", lang, max_age=365 * 24 * 3600)
    return response


def landing(request):
    ctx = _base_context(request)
    works = DtfWork.objects.filter(is_active=True).order_by("sort_order", "-created_at")
    knowledge_posts = _get_published_posts()[:3]
    ctx.update({
        "works": works,
        "work_macro": [w for w in works if w.category == WorkCategory.MACRO][:3],
        "work_process": [w for w in works if w.category == WorkCategory.PROCESS][:3],
        "work_final": [w for w in works if w.category == WorkCategory.FINAL][:3],
        "status_steps": STATUS_STEPS,
        "knowledge_posts_preview": knowledge_posts,
    })
    return _render(request, "dtf/index.html", ctx)


@require_http_methods(["GET"])
def estimate(request):
    length_raw = (request.GET.get("length_m") or "").replace(",", ".")
    copies_raw = request.GET.get("copies") or "1"
    context_kind = request.GET.get("context") or "estimate"
    length_m = None
    copies = 1
    try:
        if length_raw:
            length_m = Decimal(length_raw)
    except (InvalidOperation, ValueError):
        length_m = None
    try:
        copies = int(copies_raw)
    except (TypeError, ValueError):
        copies = 1

    pricing = None
    if length_m and copies:
        pricing = calculate_pricing(length_m, copies)

    ctx = _base_context(request)
    ctx.update({
        "pricing_result": pricing,
    })
    if context_kind == "order":
        return render(request, "dtf/partials/order_calc.html", ctx)
    return render(request, "dtf/partials/estimate_result.html", ctx)


@require_http_methods(["GET", "POST", "HEAD"])
def order(request):
    ctx = _base_context(request)
    tab = request.GET.get("tab") or "ready"
    if request.method == "POST":
        tab = request.POST.get("tab") or tab
        if tab == "help":
            help_form = DtfHelpForm(request.POST, request.FILES)
            order_form = DtfOrderForm()
            if help_form.is_valid():
                lead = help_form.save(commit=False)
                lead.lead_type = LeadType.HELP
                lead.source = "order_help"
                lead.save()
                for file in getattr(help_form, "_validated_files", []):
                    DtfLeadAttachment.objects.create(lead=lead, file=file)
                notify_new_lead(lead)
                return redirect("dtf:thanks", kind="lead", number=lead.lead_number)
        else:
            order_form = DtfOrderForm(request.POST, request.FILES)
            help_form = DtfHelpForm()
            if order_form.is_valid():
                order = order_form.save(commit=False)
                if hasattr(order_form, "_auto_length_m"):
                    order.length_source = LengthSource.AUTO
                pricing = calculate_pricing(order.length_m, order.copies)
                if pricing:
                    order.meters_total = pricing["meters_total"]
                    order.price_per_meter = pricing["rate"]
                    order.price_total = pricing["price_total"]
                    order.pricing_tier = pricing["pricing_tier"]
                    order.requires_review = pricing["requires_review"] or getattr(order_form, "_copies_requires_review", False)
                order.status = OrderStatus.CHECK_MOCKUP
                order.save()
                notify_new_order(order)
                return redirect("dtf:thanks", kind="order", number=order.order_number)
    else:
        help_form = DtfHelpForm()
        order_form = DtfOrderForm()

    ctx.update({
        "tab": tab,
        "help_form": help_form,
        "order_form": order_form,
    })
    return _render(request, "dtf/order.html", ctx)


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, _("Ви вийшли з акаунту"))
    return redirect("dtf:landing")


def thanks(request, kind: str, number: str):
    ctx = _base_context(request)
    if kind == "order":
        obj = get_object_or_404(DtfOrder, order_number=number)
        ctx.update({"kind": "order", "item": obj})
    else:
        obj = get_object_or_404(DtfLead, lead_number=number)
        ctx.update({"kind": "lead", "item": obj})
    return _render(request, "dtf/thanks.html", ctx)


@require_http_methods(["GET", "POST", "HEAD"])
def status(request, order_number: str | None = None):
    ctx = _base_context(request)
    order = None
    error = None
    share_mode = request.GET.get("share") == "1"
    share_number = request.GET.get("order")
    if order_number:
        share_mode = True
        share_number = order_number
    if request.method == "POST":
        number = request.POST.get("order_number", "").strip()
        phone = request.POST.get("phone", "").strip()
        phone_digits = normalize_phone(phone)
        if not number or not phone_digits:
            error = _("Вкажіть номер і телефон")
        else:
            order = DtfOrder.objects.filter(order_number__iexact=number).first()
            if not order:
                error = _("Замовлення не знайдено")
            else:
                if normalize_phone(order.phone) != phone_digits:
                    error = _("Телефон не збігається із замовленням")
                    order = None
    elif share_mode and share_number:
        order = DtfOrder.objects.filter(order_number__iexact=str(share_number).strip()).first()
        if not order:
            error = _("Замовлення не знайдено")

    pipeline_steps = [
        {"key": "intake", "label": _("Intake")},
        {"key": "preflight", "label": _("Preflight")},
        {"key": "print", "label": _("Print")},
        {"key": "powder", "label": _("Powder")},
        {"key": "cure", "label": _("Cure")},
        {"key": "pack", "label": _("Pack")},
        {"key": "ship", "label": _("Ship")},
    ]
    status_map = {
        OrderStatus.NEW_ORDER: 0,
        OrderStatus.CHECK_MOCKUP: 1,
        OrderStatus.AWAITING_PAYMENT: 1,
        OrderStatus.PRINTING: 2,
        OrderStatus.READY: 5,
        OrderStatus.SHIPPED: 6,
        OrderStatus.CLOSED: 6,
    }
    status_index = None
    if order:
        try:
            status_index = status_map.get(order.status)
        except Exception:
            status_index = None
    qc_checks = []
    if order:
        limits = get_limits()
        ext = get_file_extension(order.gang_file.name) if order.gang_file else ""
        ext_ok = ext.lower() in ALLOWED_READY_EXTS if ext else False
        qc_checks = [
            {
                "label": _("Файл"),
                "status": "ok" if order.gang_file else "warn",
                "value": ext.upper() if ext else _("Відсутній"),
            },
            {
                "label": _("Метраж"),
                "status": "ok" if order.meters_total else "warn",
                "value": f"{order.meters_total} м" if order.meters_total else _("Невідомо"),
            },
            {
                "label": _("Копії"),
                "status": "warn" if order.copies > limits["max_copies"] else "ok",
                "value": str(order.copies),
            },
            {
                "label": _("Оптовий метраж"),
                "status": "warn" if order.requires_review else "ok",
                "value": _("Потрібна перевірка") if order.requires_review else _("OK"),
            },
            {
                "label": _("Формат"),
                "status": "ok" if ext_ok else "warn",
                "value": ext.upper() if ext else _("Невідомо"),
            },
        ]
    share_url = None
    if order and request.build_absolute_uri:
        share_url = request.build_absolute_uri(f"{request.path}?share=1&order={order.order_number}")
    ctx.update({
        "order": order,
        "error": error,
        "status_steps": pipeline_steps,
        "status_index": status_index,
        "qc_checks": qc_checks,
        "share_mode": share_mode,
        "share_url": share_url,
    })
    return _render(request, "dtf/status.html", ctx)


def gallery(request):
    ctx = _base_context(request)
    category = request.GET.get("category", "all")
    works = DtfWork.objects.filter(is_active=True).order_by("sort_order", "-created_at")
    if category in {WorkCategory.MACRO, WorkCategory.PROCESS, WorkCategory.FINAL}:
        works = works.filter(category=category)
    works_list = list(works)
    ctx.update({
        "works": works_list,
        "works_with_images": [work for work in works_list if getattr(work, "image", None)],
        "category": category,
    })
    return _render(request, "dtf/gallery.html", ctx)


def requirements(request):
    ctx = _base_context(request)
    return _render(request, "dtf/requirements.html", ctx)


def price(request):
    ctx = _base_context(request)
    return _render(request, "dtf/price.html", ctx)


def quality(request):
    ctx = _base_context(request)
    return _render(request, "dtf/quality.html", ctx)


@require_http_methods(["GET", "POST", "HEAD"])
def sample(request):
    ctx = _base_context(request)
    saved = False
    if request.method == "POST":
        if _is_rate_limited(request, "sample_form", limit=6, window_seconds=3600):
            messages.error(request, _("Забагато спроб. Спробуйте трохи пізніше."))
            form = DtfSampleLeadForm(request.POST)
        else:
            form = DtfSampleLeadForm(request.POST)
            if form.is_valid():
                sample_lead = form.save(commit=False)
                sample_lead.source = "sample_page"
                sample_lead.save()
                saved = True
                form = DtfSampleLeadForm(initial={"sample_size": sample_lead.sample_size})
    else:
        form = DtfSampleLeadForm(initial={"sample_size": "a4"})
    ctx.update({
        "sample_form": form,
        "sample_saved": saved,
    })
    return _render(request, "dtf/sample.html", ctx)


def about(request):
    ctx = _base_context(request)
    return _render(request, "dtf/about.html", ctx)


def products(request):
    ctx = _base_context(request)
    product_cards = [
        {
            "key": "hoodie",
            "title": _("Худі"),
            "description": _("Щільні худі під DTF: підбір blank + друк + контроль якості."),
            "spec": _("Щільність 280–420 gsm, front/back/left chest"),
        },
        {
            "key": "tshirt",
            "title": _("Футболки"),
            "description": _("Базові та преміум футболки, підібрані під ваш бренд."),
            "spec": _("S–XXL, білий/чорний/кольори, опт і дрібні партії"),
        },
        {
            "key": "tote",
            "title": _("Шопери"),
            "description": _("Готові шопери з нанесенням під запуск мерчу чи промо."),
            "spec": _("Бавовна/саржа, front print, серійні тиражі"),
        },
    ]
    ctx.update({"product_cards": product_cards})
    return _render(request, "dtf/products.html", ctx)


def constructor_landing(request):
    ctx = _base_context(request)
    return _render(request, "dtf/constructor_landing.html", ctx)


@require_http_methods(["GET", "POST", "HEAD"])
def constructor_app(request):
    ctx = _base_context(request)
    session_obj = None
    sid = (request.GET.get("sid") or request.POST.get("session_id") or "").strip()
    if sid:
        session_obj = DtfBuilderSession.objects.filter(session_id=sid).first()
    if not session_obj:
        session_obj = DtfBuilderSession.objects.create(
            user=request.user if request.user.is_authenticated else None,
        )
    if request.method == "POST":
        form = DtfBuilderSessionForm(request.POST, request.FILES, instance=session_obj)
        if form.is_valid():
            builder = form.save(commit=False)
            builder.size_breakdown_json = form.cleaned_data.get("size_breakdown_json", {})
            builder.placements_json = form.cleaned_data.get("placements_json", [])
            builder.preflight_json = form.cleaned_data.get("preflight_json", {})
            preview_file = form.cleaned_data.get("preview_image_file")
            if preview_file:
                builder.preview_image = preview_file
            if request.user.is_authenticated and not builder.user_id:
                builder.user = request.user
            builder.status = BuilderStatus.DRAFT
            builder.save()
            messages.success(request, _("Чернетку конструктора збережено"))
            return redirect(f"{reverse('dtf:constructor_app')}?sid={builder.session_id}")
    else:
        initial = {}
        if session_obj.size_breakdown_json:
            initial["size_breakdown"] = ",".join(f"{k}:{v}" for k, v in session_obj.size_breakdown_json.items())
        form = DtfBuilderSessionForm(instance=session_obj, initial=initial)
    preflight = session_obj.preflight_json if session_obj.preflight_json else {}
    ctx.update({
        "builder_session": session_obj,
        "builder_form": form,
        "builder_preflight": preflight,
    })
    return _render(request, "dtf/constructor_app.html", ctx)


@require_POST
def constructor_submit(request):
    sid = (request.POST.get("session_id") or "").strip()
    if not sid:
        return JsonResponse({"ok": False, "error": _("Session ID required")}, status=400)
    builder = get_object_or_404(DtfBuilderSession, session_id=sid)
    if builder.status == BuilderStatus.SUBMITTED and builder.submitted_lead_id:
        return JsonResponse({"ok": True, "lead_number": builder.submitted_lead.lead_number})
    if _is_rate_limited(request, "constructor_submit", limit=8, window_seconds=3600):
        return JsonResponse({"ok": False, "error": _("Too many submissions. Try later.")}, status=429)

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    city = (request.POST.get("city") or builder.delivery_city or "").strip()
    np_branch = (request.POST.get("np_branch") or builder.delivery_np_branch or "").strip()
    contact_channel = (request.POST.get("contact_channel") or "telegram").strip()
    risk_ack = (request.POST.get("risk_ack") or "").strip() in {"1", "true", "on", "yes"}

    if not name or len(normalize_phone(phone)) < 10:
        return JsonResponse({"ok": False, "error": _("Provide valid name and phone")}, status=400)

    preflight = builder.preflight_json or {}
    has_fail = bool(preflight.get("has_fail"))
    has_warn = bool(preflight.get("has_warn"))
    if has_fail:
        return JsonResponse({"ok": False, "error": _("Fix critical preflight issues before submit")}, status=400)
    if has_warn and not risk_ack:
        return JsonResponse({"ok": False, "error": _("Please accept preflight risks to continue")}, status=400)

    lead = DtfLead.objects.create(
        lead_type=LeadType.CONSULTATION,
        name=name,
        phone=phone,
        city=city,
        np_branch=np_branch,
        contact_channel=contact_channel if contact_channel in {"telegram", "whatsapp", "instagram", "call"} else "telegram",
        task_description=_build_constructor_task_description(builder),
        source="constructor_submit",
    )
    notify_new_lead(lead)
    builder.status = BuilderStatus.SUBMITTED
    builder.submitted_lead = lead
    builder.risk_ack = risk_ack
    builder.delivery_city = city
    builder.delivery_np_branch = np_branch
    builder.save(update_fields=[
        "status",
        "submitted_lead",
        "risk_ack",
        "delivery_city",
        "delivery_np_branch",
        "updated_at",
    ])
    return JsonResponse({"ok": True, "lead_number": lead.lead_number, "redirect": reverse("dtf:thanks", kwargs={"kind": "lead", "number": lead.lead_number})})


def constructor_session_detail(request, session_id: str):
    session_obj = get_object_or_404(DtfBuilderSession, session_id=session_id)
    return redirect(f"{reverse('dtf:constructor_app')}?sid={session_obj.session_id}")


def robots_txt(request):
    host = request.get_host().split(":")[0]
    scheme = request.scheme or "https"
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        f"Sitemap: {scheme}://{host}/sitemap.xml",
        "",
        "Disallow: /admin/",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    host = request.get_host().split(":")[0]
    scheme = request.scheme or "https"
    base_url = f"{scheme}://{host}"

    route_names = [
        "dtf:landing",
        "dtf:order",
        "dtf:status",
        "dtf:gallery",
        "dtf:sample",
        "dtf:about",
        "dtf:products",
        "dtf:constructor",
        "dtf:requirements",
        "dtf:price",
        "dtf:delivery_payment",
        "dtf:contacts",
        "dtf:privacy",
        "dtf:terms",
        "dtf:returns",
        "dtf:requisites",
        "dtf:quality",
        "dtf:templates",
        "dtf:how_to_press",
        "dtf:preflight",
        "dtf:blog",
    ]

    unique_paths = []
    seen = set()
    for route_name in route_names:
        path = reverse(route_name)
        if path not in seen:
            unique_paths.append(path)
            seen.add(path)

    for post in KnowledgePost.objects.published().only("slug"):
        path = reverse("dtf:blog_post", kwargs={"slug": post.slug})
        if path not in seen:
            unique_paths.append(path)
            seen.add(path)

    urlset = ET.Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
    for path in unique_paths:
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = f"{base_url}{path}"

    xml_payload = ET.tostring(urlset, encoding="utf-8", xml_declaration=True)
    return HttpResponse(xml_payload, content_type="application/xml; charset=utf-8")


def templates(request):
    ctx = _base_context(request)
    return _render(request, "dtf/templates.html", ctx)


def how_to_press(request):
    ctx = _base_context(request)
    return _render(request, "dtf/how_to_press.html", ctx)


@require_http_methods(["GET", "POST", "HEAD"])
def preflight(request):
    ctx = _base_context(request)
    if request.method == "POST":
        form = DtfHelpForm(request.POST, request.FILES)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.lead_type = LeadType.HELP
            lead.source = "preflight"
            lead.save()
            for file in getattr(form, "_validated_files", []):
                DtfLeadAttachment.objects.create(lead=lead, file=file)
            notify_new_lead(lead)
            return redirect("dtf:thanks", kind="lead", number=lead.lead_number)
    else:
        form = DtfHelpForm(initial={"task_description": _("Preflight перевірка файлу")})
    ctx.update({"preflight_form": form})
    return _render(request, "dtf/preflight.html", ctx)


def delivery_payment(request):
    ctx = _base_context(request)
    return _render(request, "dtf/delivery_payment.html", ctx)


def contacts(request):
    ctx = _base_context(request)
    return _render(request, "dtf/contacts.html", ctx)


def blog(request):
    ctx = _base_context(request)
    posts = _get_published_posts()
    ctx.update({
        "posts": posts,
        "post_month_groups": _group_posts_by_month(posts),
    })
    return _render(request, "dtf/blog.html", ctx)


def blog_post(request, slug: str):
    post = get_object_or_404(KnowledgePost.objects.published(), slug=slug)
    ctx = _base_context(request)
    related = list(
        KnowledgePost.objects.published()
        .exclude(pk=post.pk)
        .order_by("-pub_date", "-id")[:3]
    )
    ctx.update({
        "post": post,
        "related_posts": related,
    })
    overlay = request.GET.get("overlay") == "1"
    if overlay:
        return render(request, "dtf/partials/blog_overlay_content.html", ctx)
    return _render(request, "dtf/blog_post.html", ctx)


@login_required
def cabinet_home(request):
    ctx = _base_context(request)
    user_phone = _get_user_phone_digits(request.user)
    orders = []
    if user_phone:
        for order in DtfOrder.objects.order_by("-created_at")[:300]:
            if normalize_phone(order.phone) == user_phone:
                orders.append(order)
    elif request.user.is_staff:
        orders = list(DtfOrder.objects.order_by("-created_at")[:10])
    sessions_qs = DtfBuilderSession.objects.filter(user=request.user).order_by("-updated_at")
    loyalty_meta = _calc_loyalty_meta(len(orders))
    ctx.update({
        "cabinet_tab": "home",
        "cabinet_orders": orders[:5],
        "cabinet_sessions": sessions_qs[:5],
        "loyalty": loyalty_meta,
    })
    return _render(request, "dtf/cabinet_home.html", ctx)


@login_required
def cabinet_orders(request):
    ctx = _base_context(request)
    user_phone = _get_user_phone_digits(request.user)
    orders = []
    if user_phone:
        for order in DtfOrder.objects.order_by("-created_at")[:300]:
            if normalize_phone(order.phone) == user_phone:
                orders.append(order)
    elif request.user.is_staff:
        orders = list(DtfOrder.objects.order_by("-created_at")[:30])
    loyalty_meta = _calc_loyalty_meta(len(orders))
    ctx.update({
        "cabinet_tab": "orders",
        "cabinet_orders": orders,
        "loyalty": loyalty_meta,
    })
    return _render(request, "dtf/cabinet_orders.html", ctx)


@login_required
def cabinet_sessions(request):
    ctx = _base_context(request)
    sessions = DtfBuilderSession.objects.filter(user=request.user).order_by("-updated_at")
    user_phone = _get_user_phone_digits(request.user)
    orders = []
    if user_phone:
        for order in DtfOrder.objects.order_by("-created_at")[:300]:
            if normalize_phone(order.phone) == user_phone:
                orders.append(order)
    loyalty_meta = _calc_loyalty_meta(len(orders))
    ctx.update({
        "cabinet_tab": "sessions",
        "cabinet_sessions": sessions,
        "loyalty": loyalty_meta,
    })
    return _render(request, "dtf/cabinet_sessions.html", ctx)


def privacy(request):
    ctx = _base_context(request)
    return _render(request, "dtf/legal/privacy.html", ctx)


def terms(request):
    ctx = _base_context(request)
    return _render(request, "dtf/legal/terms.html", ctx)


def returns(request):
    ctx = _base_context(request)
    return _render(request, "dtf/legal/returns.html", ctx)


def requisites(request):
    ctx = _base_context(request)
    return _render(request, "dtf/legal/requisites.html", ctx)


def handler404(request, exception):
    ctx = _base_context(request)
    return _render(request, "dtf/404.html", ctx, status=404)


def handler500(request):
    ctx = _base_context(request)
    return _render(request, "dtf/500.html", ctx, status=500)


@require_POST
def fab_lead(request):
    form = DtfFabLeadForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    lead = form.save(commit=False)
    lead.lead_type = LeadType.FAB
    lead.source = "fab"
    lead.save()
    notify_new_lead(lead)
    return JsonResponse({"ok": True, "lead_number": lead.lead_number})
