from decimal import Decimal, InvalidOperation
from itertools import groupby
from datetime import date
import xml.etree.ElementTree as ET
from urllib.parse import quote
import hashlib

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.translation import gettext_lazy as _

from .forms import (
    DtfBuilderSessionForm,
    DtfFabLeadForm,
    DtfHelpForm,
    DtfOrderForm,
    DtfSampleLeadForm,
)
from .admin_panel_forms import (
    DtfAdminOrderUpdateForm,
    DtfKnowledgePostAdminForm,
)
from .models import (
    BuilderStatus,
    DtfOrder,
    DtfBuilderSession,
    DtfEventLog,
    DtfLead,
    DtfLeadAttachment,
    DtfLifecycleStatus,
    DtfPaymentStatus,
    DtfFulfillmentKind,
    DtfStatusEvent,
    DtfUpload,
    DtfPreflightReport,
    DtfPreflightResult,
    DtfQuote,
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
)
from .notify import (
    notify_manager_new_order,
)
from .pricing import calculate_quote
from .preflight.engine import (
    analyze_upload,
    build_preview_assets,
    normalize_preflight_report,
)
from .utils import (
    activate_language_from_request,
    build_lang_links,
    get_file_extension,
    get_feature_flags,
    get_limits,
    get_pricing_config,
    normalize_phone,
    unique_slug_for_queryset,
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


CUSTOMER_PROGRESS_STEPS = [
    {"key": "moderation", "label": _("На модерації")},
    {"key": "awaiting_payment", "label": _("Очікує оплату")},
    {"key": "printing", "label": _("Прийнято в роботу / друк")},
    {"key": "shipped", "label": _("Відправлено")},
    {"key": "delivered", "label": _("Доставлено у відділення / поштомат")},
    {"key": "received", "label": _("Отримано")},
]

PAYMENT_STATUS_TONE = {
    DtfPaymentStatus.PENDING_REVIEW: "pending",
    DtfPaymentStatus.AWAITING_PAYMENT: "due",
    DtfPaymentStatus.PAID: "paid",
    DtfPaymentStatus.PARTIAL: "partial",
    DtfPaymentStatus.FAILED: "error",
    DtfPaymentStatus.REFUNDED: "muted",
}


DTF_EFFECTS_TEMPLATES = {
    "dtf/index.html",
    "dtf/order.html",
    "dtf/status.html",
    "dtf/gallery.html",
    "dtf/requirements.html",
    "dtf/sample.html",
    "dtf/constructor_landing.html",
    "dtf/constructor_app.html",
    "dtf/templates.html",
    "dtf/effects_lab.html",
    "dtf/blog.html",
}

DTF_HTMX_TEMPLATES = {
    "dtf/index.html",
    "dtf/order.html",
}


def _is_dtf_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    try:
        return bool(user.userprofile and getattr(user.userprofile, "is_manager", False))
    except Exception:
        return False


def _order_stage_index(order: DtfOrder) -> int:
    stage_key = order.customer_stage()
    order_map = {item["key"]: idx for idx, item in enumerate(CUSTOMER_PROGRESS_STEPS)}
    return order_map.get(stage_key, 0)


def _order_payment_tone(order: DtfOrder) -> str:
    return PAYMENT_STATUS_TONE.get(order.payment_status, "pending")


def _order_item_summary(order: DtfOrder) -> str:
    if order.fulfillment_kind == DtfFulfillmentKind.CUSTOM_PRODUCT:
        product = (order.product_type or _("Готовий виріб")).strip()
        placement = (order.print_placement or "").strip()
        qty = order.product_quantity or order.copies
        if placement:
            return _("%(product)s · %(placement)s · %(qty)s шт") % {
                "product": product,
                "placement": placement,
                "qty": qty,
            }
        return _("%(product)s · %(qty)s шт") % {"product": product, "qty": qty}
    if order.meters_total:
        return _("%(meters)s пог.м · %(copies)s коп.") % {
            "meters": order.meters_total,
            "copies": order.copies,
        }
    if order.length_m:
        return _("%(meters)s пог.м · %(copies)s коп.") % {
            "meters": order.length_m,
            "copies": order.copies,
        }
    return _("Фільм DTF")


def _build_order_card_payload(order: DtfOrder) -> dict:
    stage_key = order.customer_stage()
    payment_amount = order.payment_amount if order.payment_amount is not None else order.price_total
    return {
        "id": order.id,
        "number": order.order_number,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "status": order.status,
        "lifecycle_status": order.lifecycle_status,
        "fulfillment_kind": order.fulfillment_kind,
        "product_type": order.product_type or "",
        "print_placement": order.print_placement or "",
        "product_quantity": order.product_quantity or order.copies,
        "stage_key": stage_key,
        "stage_index": _order_stage_index(order),
        "stage_label": dict((item["key"], item["label"]) for item in CUSTOMER_PROGRESS_STEPS).get(stage_key, _("На модерації")),
        "payment_status_key": order.payment_status,
        "payment_status": order.get_payment_status_display(),
        "payment_tone": _order_payment_tone(order),
        "payment_due": order.is_payment_due(),
        "payment_amount": payment_amount,
        "payment_reference": order.payment_reference or "",
        "payment_link": order.payment_link or "",
        "ttn": order.tracking_number or "",
        "delivery_point_type": order.delivery_point_type or "",
        "delivery_point_code": order.delivery_point_code or "",
        "delivery_point_label": order.delivery_point_label or order.np_branch,
        "item_summary": _order_item_summary(order),
        "manager_note": order.manager_note or "",
        "need_fix_reason": order.need_fix_reason or "",
        "can_pay_now": order.payment_status in {DtfPaymentStatus.AWAITING_PAYMENT, DtfPaymentStatus.FAILED},
        "reorder_url": f"{reverse('dtf:order')}?reorder={order.order_number}",
        "contact_url": f"{reverse('dtf:order')}?tab=help&order={order.order_number}",
    }


def _build_custom_session_card(session: DtfBuilderSession) -> dict:
    size_parts = []
    for size, qty in (session.size_breakdown_json or {}).items():
        size_parts.append(f"{size}:{qty}")
    size_text = ", ".join(size_parts)
    subtitle = _("Конструктор: %(product)s · %(placement)s · %(qty)s шт") % {
        "product": session.get_product_type_display(),
        "placement": session.get_placement_display(),
        "qty": session.quantity,
    }
    if size_text:
        subtitle = f"{subtitle} · {size_text}"
    return {
        "id": str(session.session_id),
        "number": f"CNSTR-{str(session.session_id)[:8].upper()}",
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "stage_key": "moderation",
        "stage_index": 0,
        "stage_label": _("На модерації"),
        "payment_status": _("Сума після узгодження"),
        "payment_tone": "pending",
        "payment_due": False,
        "payment_amount": None,
        "payment_link": "",
        "ttn": "",
        "delivery_point_type": "",
        "delivery_point_code": "",
        "delivery_point_label": session.delivery_np_branch or "",
        "item_summary": subtitle,
        "manager_note": "",
        "need_fix_reason": "",
        "can_pay_now": False,
        "reorder_url": f"{reverse('dtf:constructor_app')}?sid={session.session_id}",
        "contact_url": f"{reverse('dtf:order')}?tab=help&session={session.session_id}",
    }


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
    can_store_admin = bool(
        user.is_staff
        or user.is_superuser
        or (profile and bool(getattr(profile, "is_manager", False)))
    )
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
    store_admin_host = current_host if current_host.startswith("dtf.") else main_host
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
        "store_admin": f"{scheme}://{store_admin_host}/admin-panel/",
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


def _get_user_orders_for_cabinet(user, *, max_scan: int = 300, staff_fallback: int = 30):
    user_phone = _get_user_phone_digits(user)
    if user_phone:
        items = []
        for item in DtfOrder.objects.order_by("-created_at")[:max_scan]:
            if normalize_phone(item.phone) == user_phone:
                items.append(item)
        return items
    if user.is_staff:
        return list(DtfOrder.objects.order_by("-created_at")[:staff_fallback])
    return []


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


def _hash_ip(request):
    raw_ip = (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip()
    if not raw_ip:
        return ""
    return hashlib.sha256(raw_ip.encode("utf-8")).hexdigest()


def _log_event(name: str, *, request, payload: dict | None = None, order=None, quote=None, preflight=None):
    DtfEventLog.objects.create(
        event_name=name,
        payload=payload or {},
        order=order,
        quote=quote,
        preflight_report=preflight,
        ip_hash=_hash_ip(request),
    )


def _persist_quote(quote_data: dict, *, source: str, raw_inputs: dict, order=None, upload=None):
    breakdown = quote_data.get("breakdown", {})
    valid_until = quote_data.get("valid_until")
    if isinstance(valid_until, str):
        try:
            valid_until = date.fromisoformat(valid_until)
        except ValueError:
            valid_until = None
    return DtfQuote.objects.create(
        source=source,
        width_cm=quote_data.get("width_cm") or Decimal("60.00"),
        length_m=quote_data.get("length_m") or Decimal("0.00"),
        urgency=quote_data.get("urgency") or "standard",
        services_json=quote_data.get("services") or {},
        shipping_method="estimate" if (quote_data.get("services") or {}).get("with_shipping") else "none",
        unit_price=quote_data.get("unit_price", Decimal("0")),
        base_total=breakdown.get("base_total", Decimal("0")),
        discount_total=breakdown.get("discount_total", Decimal("0")),
        services_total=breakdown.get("services_total", Decimal("0")),
        shipping_total=breakdown.get("shipping_total", Decimal("0")),
        total=breakdown.get("total", Decimal("0")),
        pricing_version=quote_data.get("config_version", "default"),
        valid_until=valid_until,
        disclaimer=quote_data.get("disclaimer", ""),
        order=order,
        upload=upload,
        raw_inputs=raw_inputs or {},
    )


def _quote_to_legacy_calc(quote_data: dict):
    breakdown = quote_data.get("breakdown", {})
    return {
        "meters_total": quote_data.get("effective_length_m", quote_data.get("length_m", Decimal("0.00"))),
        "rate": quote_data.get("unit_price", Decimal("0.00")),
        "price_total": breakdown.get("total", Decimal("0.00")),
        "pricing_tier": quote_data.get("pricing_tier", "base"),
        "requires_review": quote_data.get("min_order_applied", False),
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
    context.setdefault("dtf_load_effects", template in DTF_EFFECTS_TEMPLATES)
    context.setdefault("dtf_load_htmx", template in DTF_HTMX_TEMPLATES)
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
        try:
            quote_data = calculate_quote({
                "length_m": length_m * Decimal(copies),
                "width_cm": Decimal("60"),
                "urgency": "standard",
                "help_layout": False,
                "with_shipping": False,
            })
            pricing = _quote_to_legacy_calc(quote_data)
        except ValueError:
            pricing = None

    ctx = _base_context(request)
    ctx.update({
        "pricing_result": pricing,
    })
    if context_kind == "order":
        return render(request, "dtf/partials/order_calc.html", ctx)
    return render(request, "dtf/partials/estimate_result.html", ctx)


@require_http_methods(["GET", "POST"])
def api_quote(request):
    payload = request.POST if request.method == "POST" else request.GET
    length_raw = (payload.get("length_m") or "").replace(",", ".")
    width_raw = (payload.get("width_cm") or "60").replace(",", ".")
    context_kind = payload.get("context") or "estimate"
    urgency = payload.get("urgency") or "standard"
    help_layout = payload.get("help_layout") or payload.get("service_layout") or ""
    with_shipping = payload.get("with_shipping") or payload.get("shipping") or ""

    try:
        length_m = Decimal(length_raw)
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid_length"}, status=400)

    try:
        width_cm = Decimal(width_raw)
    except (InvalidOperation, TypeError, ValueError):
        width_cm = Decimal("60")

    try:
        quote_data = calculate_quote({
            "length_m": length_m,
            "width_cm": width_cm,
            "urgency": urgency,
            "help_layout": help_layout,
            "with_shipping": with_shipping,
        })
    except ValueError:
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

    quote_obj = _persist_quote(
        quote_data,
        source=context_kind,
        raw_inputs={
            "length_m": str(length_m),
            "width_cm": str(width_cm),
            "urgency": urgency,
            "help_layout": str(help_layout),
            "with_shipping": str(with_shipping),
        },
    )
    _log_event(
        "quote_requested",
        request=request,
        payload={
            "context": context_kind,
            "pricing_tier": quote_data.get("pricing_tier"),
            "total": str(quote_data.get("breakdown", {}).get("total", "")),
        },
        quote=quote_obj,
    )

    if request.headers.get("HX-Request") == "true":
        ctx = _base_context(request)
        ctx.update({
            "pricing_result": _quote_to_legacy_calc(quote_data),
        })
        if context_kind == "order":
            return render(request, "dtf/partials/order_calc.html", ctx)
        return render(request, "dtf/partials/estimate_result.html", ctx)

    return JsonResponse({
        "ok": True,
        "quote_id": quote_obj.id,
        "quote": quote_data,
    })


@require_POST
def api_preflight(request):
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"ok": False, "error": "file_required"}, status=400)

    report = analyze_upload(uploaded_file, allowed_exts=ALLOWED_READY_EXTS)
    normalized = normalize_preflight_report(report)
    return JsonResponse({
        "ok": True,
        "report": normalized,
    })


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
                quote_data = calculate_quote({
                    "length_m": (order.length_m or Decimal("0")) * Decimal(order.copies or 1),
                    "width_cm": Decimal("60"),
                    "urgency": "standard",
                    "help_layout": False,
                    "with_shipping": False,
                })
                pricing = _quote_to_legacy_calc(quote_data)
                order.meters_total = pricing["meters_total"]
                order.price_per_meter = pricing["rate"]
                order.price_total = pricing["price_total"]
                order.pricing_tier = pricing["pricing_tier"]
                order.requires_review = bool(pricing["requires_review"] or getattr(order_form, "_copies_requires_review", False))
                order.status = OrderStatus.CHECK_MOCKUP
                order.lifecycle_status = DtfLifecycleStatus.NEW
                order.fulfillment_kind = DtfFulfillmentKind.FILM
                order.product_quantity = order.copies
                order.payment_status = DtfPaymentStatus.PENDING_REVIEW
                order.payment_amount = pricing["price_total"]
                order.save()
                DtfStatusEvent.objects.create(
                    order=order,
                    status_from=DtfLifecycleStatus.NEW,
                    status_to=DtfLifecycleStatus.NEW,
                    actor="system",
                    public_message=_("Замовлення створено"),
                )
                if order.requires_review:
                    order.transition_lifecycle(
                        DtfLifecycleStatus.NEEDS_REVIEW,
                        actor="system",
                        public_message=_("Потрібна перевірка менеджером"),
                    )
                quote_obj = _persist_quote(
                    quote_data,
                    source="order_form",
                    raw_inputs={
                        "length_m": str(order.length_m),
                        "copies": order.copies,
                    },
                    order=order,
                )
                _log_event(
                    "order_submitted",
                    request=request,
                    payload={
                        "order_number": order.order_number,
                        "requires_review": order.requires_review,
                    },
                    order=order,
                    quote=quote_obj,
                )
                notify_new_order(order)
                notify_manager_new_order(order, quote_obj)
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
    status_timeline = []
    generic_error = _("Не вдалося знайти замовлення за цими даними")
    share_mode = request.GET.get("share") == "1"
    share_number = request.GET.get("order")
    if order_number:
        share_mode = True
        share_number = order_number
    if request.method == "POST":
        if _is_rate_limited(request, "status_lookup", limit=18, window_seconds=900):
            error = _("Тимчасово обмежено. Спробуйте трохи пізніше")
            share_mode = False
            share_number = None
        else:
            number = request.POST.get("order_number", "").strip()
            phone = request.POST.get("phone", "").strip()
            phone_digits = normalize_phone(phone)
            if not number or not phone_digits:
                error = generic_error
            else:
                candidate = DtfOrder.objects.filter(order_number__iexact=number).first()
                if not candidate or normalize_phone(candidate.phone) != phone_digits:
                    error = generic_error
                else:
                    order = candidate
                    _log_event(
                        "status_check_success",
                        request=request,
                        payload={"order_number": order.order_number},
                        order=order,
                    )
    elif share_mode and share_number:
        number = str(share_number).strip()
        phone_digits = normalize_phone(request.GET.get("phone", ""))
        if not number or not phone_digits:
            error = generic_error
        else:
            candidate = DtfOrder.objects.filter(order_number__iexact=number).first()
            if not candidate or normalize_phone(candidate.phone) != phone_digits:
                error = generic_error
            else:
                order = candidate
                _log_event(
                    "status_check_success",
                    request=request,
                    payload={"order_number": order.order_number, "via": "share"},
                    order=order,
                )
    elif request.method == "GET" and request.GET.get("order_number"):
        _log_event(
            "status_check_fail",
            request=request,
            payload={"reason": "missing_phone_or_submit"},
        )

    pipeline_steps = [
        {"key": "intake", "label": _("Intake")},
        {"key": "preflight", "label": _("Preflight")},
        {"key": "print", "label": _("Print")},
        {"key": "powder", "label": _("Powder")},
        {"key": "cure", "label": _("Cure")},
        {"key": "pack", "label": _("Pack")},
        {"key": "ship", "label": _("Ship")},
    ]
    lifecycle_status_map = {
        DtfLifecycleStatus.NEW: 0,
        DtfLifecycleStatus.NEEDS_REVIEW: 1,
        DtfLifecycleStatus.CONFIRMED: 1,
        DtfLifecycleStatus.IN_PRODUCTION: 2,
        DtfLifecycleStatus.QA_CHECK: 4,
        DtfLifecycleStatus.PACKED: 5,
        DtfLifecycleStatus.SHIPPED: 6,
        DtfLifecycleStatus.DELIVERED: 6,
        DtfLifecycleStatus.RECEIVED: 6,
        DtfLifecycleStatus.CANCELLED: 0,
    }
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
        status_index = lifecycle_status_map.get(order.lifecycle_status)
        if status_index is None:
            status_index = status_map.get(order.status)
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
        for event in order.status_events.order_by("created_at", "id"):
            status_timeline.append({
                "from_label": event.get_status_from_display(),
                "to_label": event.get_status_to_display(),
                "message": event.public_message,
                "created_at": event.created_at,
            })

    share_url = None
    if error and request.method == "POST":
        _log_event(
            "status_check_fail",
            request=request,
            payload={"reason": "not_found_or_mismatch"},
        )
    ctx.update({
        "order": order,
        "error": error,
        "status_steps": pipeline_steps,
        "status_index": status_index,
        "qc_checks": qc_checks,
        "status_timeline": status_timeline,
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
            design_file = form.cleaned_data.get("design_file")
            if design_file:
                try:
                    design_file.seek(0)
                except Exception:
                    pass
                raw = design_file.read()
                try:
                    design_file.seek(0)
                except Exception:
                    pass
                upload = DtfUpload.objects.create(
                    file=design_file,
                    size_bytes=int(getattr(design_file, "size", len(raw) if raw else 0) or 0),
                    mime_type=(getattr(design_file, "content_type", "") or "").split(";")[0].strip().lower(),
                    sha256=hashlib.sha256(raw).hexdigest() if raw else hashlib.sha256(str(builder.session_id).encode("utf-8")).hexdigest(),
                    owner=request.user if request.user.is_authenticated else None,
                    source="constructor_draft",
                )
                report_payload = builder.preflight_json or {}
                result_map = {
                    "PASS": DtfPreflightResult.PASS,
                    "WARN": DtfPreflightResult.WARN,
                    "FAIL": DtfPreflightResult.FAIL,
                }
                preflight = DtfPreflightReport.objects.create(
                    upload=upload,
                    result=result_map.get(str(report_payload.get("result", "PASS")).upper(), DtfPreflightResult.PASS),
                    checks_json=report_payload.get("checks", []),
                    metrics_json=report_payload.get("metrics", {}),
                    warnings_json=report_payload.get("warnings", []),
                    errors_json=report_payload.get("errors", []),
                    preflight_version=report_payload.get("preflight_version", "2.0"),
                    engine_version=report_payload.get("engine_version", "2.0.0"),
                )
                thumb_bytes, overlay_bytes = build_preview_assets(design_file)
                if thumb_bytes:
                    preflight.thumbnail.save(
                        f"preflight-thumb-{upload.sha256[:12]}.jpg",
                        ContentFile(thumb_bytes),
                        save=False,
                    )
                if overlay_bytes:
                    preflight.overlay_image.save(
                        f"preflight-overlay-{upload.sha256[:12]}.jpg",
                        ContentFile(overlay_bytes),
                        save=False,
                    )
                preflight.save()
                _log_event(
                    "preflight_completed",
                    request=request,
                    payload={
                        "result": preflight.result,
                        "warnings": len(preflight.warnings_json or []),
                        "errors": len(preflight.errors_json or []),
                    },
                    preflight=preflight,
                )
            messages.success(request, _("Чернетку конструктора збережено"))
            return redirect(f"{reverse('dtf:constructor_app')}?sid={builder.session_id}")
    else:
        initial = {}
        if session_obj.size_breakdown_json:
            initial["size_breakdown"] = ",".join(f"{k}:{v}" for k, v in session_obj.size_breakdown_json.items())
        form = DtfBuilderSessionForm(instance=session_obj, initial=initial)
    raw_preflight = session_obj.preflight_json if session_obj.preflight_json else {}
    preflight = normalize_preflight_report(raw_preflight)
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


def effects_lab(request):
    enabled = bool(getattr(settings, "DTF_EFFECTS_LAB_ENABLED", settings.DEBUG))
    is_staff = bool(getattr(request.user, "is_staff", False))
    if not enabled and not is_staff:
        ctx = _base_context(request)
        return _render(request, "dtf/404.html", ctx, status=404)
    ctx = _base_context(request)
    ctx.update({
        "robots_noindex": True,
    })
    return _render(request, "dtf/effects_lab.html", ctx)


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
    orders = _get_user_orders_for_cabinet(request.user, staff_fallback=10)
    sessions_qs = DtfBuilderSession.objects.filter(user=request.user).order_by("-updated_at")
    loyalty_meta = _calc_loyalty_meta(len(orders))
    ctx.update({
        "cabinet_tab": "home",
        "cabinet_orders": orders[:5],
        "cabinet_order_cards": [_build_order_card_payload(item) for item in orders[:5]],
        "cabinet_sessions": sessions_qs[:5],
        "loyalty": loyalty_meta,
    })
    return _render(request, "dtf/cabinet_home.html", ctx)


@login_required
def cabinet_orders(request):
    ctx = _base_context(request)
    orders = _get_user_orders_for_cabinet(request.user, staff_fallback=30)
    session_items = list(
        DtfBuilderSession.objects.filter(user=request.user, status=BuilderStatus.SUBMITTED)
        .order_by("-updated_at")[:30]
    )
    loyalty_meta = _calc_loyalty_meta(len(orders))
    order_cards = [_build_order_card_payload(item) for item in orders]
    session_cards = [_build_custom_session_card(item) for item in session_items]
    combined_cards = sorted(
        [*order_cards, *session_cards],
        key=lambda payload: payload.get("updated_at") or payload.get("created_at"),
        reverse=True,
    )
    ctx.update({
        "cabinet_tab": "orders",
        "cabinet_orders": orders,
        "cabinet_order_cards": combined_cards,
        "cabinet_progress_steps": CUSTOMER_PROGRESS_STEPS,
        "loyalty": loyalty_meta,
    })
    return _render(request, "dtf/cabinet_orders.html", ctx)


@login_required
def cabinet_sessions(request):
    ctx = _base_context(request)
    sessions = DtfBuilderSession.objects.filter(user=request.user).order_by("-updated_at")
    orders = _get_user_orders_for_cabinet(request.user)
    loyalty_meta = _calc_loyalty_meta(len(orders))
    ctx.update({
        "cabinet_tab": "sessions",
        "cabinet_sessions": sessions,
        "loyalty": loyalty_meta,
    })
    return _render(request, "dtf/cabinet_sessions.html", ctx)


def _dtf_admin_shell_tabs():
    return [
        {"key": "dashboard", "label": _("Статистика / Dashboard"), "icon": "gauge"},
        {"key": "orders", "label": _("Замовлення"), "icon": "package"},
        {"key": "blog", "label": _("Блог"), "icon": "book"},
        {"key": "users", "label": _("Користувачі"), "icon": "users"},
        {"key": "promocodes", "label": _("Промокоди"), "icon": "ticket"},
    ]


def _dtf_admin_stats_snapshot():
    total_orders = DtfOrder.objects.count()
    active_orders = DtfOrder.objects.exclude(
        lifecycle_status__in=[DtfLifecycleStatus.CANCELLED, DtfLifecycleStatus.RECEIVED]
    ).count()
    awaiting_payment = DtfOrder.objects.filter(payment_status=DtfPaymentStatus.AWAITING_PAYMENT).count()
    shipped_today = DtfOrder.objects.filter(lifecycle_status=DtfLifecycleStatus.SHIPPED, updated_at__date=timezone.localdate()).count()
    return {
        "total_orders": total_orders,
        "active_orders": active_orders,
        "awaiting_payment": awaiting_payment,
        "shipped_today": shipped_today,
    }


def _dtf_admin_tab_context(tab_key: str):
    context = {
        "admin_tab_key": tab_key,
        "admin_stats": _dtf_admin_stats_snapshot(),
        "admin_progress_steps": CUSTOMER_PROGRESS_STEPS,
    }
    if tab_key == "orders":
        orders = list(DtfOrder.objects.order_by("-created_at")[:80])
        order_cards = [_build_order_card_payload(item) for item in orders]
        context.update({
            "admin_orders": orders,
            "admin_order_cards": order_cards,
            "admin_order_cards_map": {card["id"]: card for card in order_cards},
            "admin_order_form": DtfAdminOrderUpdateForm(),
            "order_status_choices": DtfOrder._meta.get_field("status").choices,
            "lifecycle_choices": DtfOrder._meta.get_field("lifecycle_status").choices,
            "payment_choices": DtfOrder._meta.get_field("payment_status").choices,
            "fulfillment_choices": DtfOrder._meta.get_field("fulfillment_kind").choices,
        })
    elif tab_key == "blog":
        context.update({
            "blog_posts": KnowledgePost.objects.order_by("-pub_date", "-id")[:120],
            "blog_form": DtfKnowledgePostAdminForm(),
        })
    elif tab_key == "users":
        user_model = get_user_model()
        context.update({
            "admin_users": user_model.objects.order_by("-date_joined")[:60],
        })
    elif tab_key == "promocodes":
        context.update({
            "promocodes_placeholder": [
                {"code": "DTF-SOON", "discount": "10%", "status": _("В розробці")},
                {"code": "PRINT-LAB", "discount": "15%", "status": _("В розробці")},
            ]
        })
    return context


@login_required
@user_passes_test(_is_dtf_admin)
def admin_panel(request):
    ctx = _base_context(request)
    tabs = _dtf_admin_shell_tabs()
    allowed = {item["key"] for item in tabs}
    default_tab = "dashboard"
    requested_tab = (request.GET.get("tab") or "").strip()
    active_tab = requested_tab if requested_tab in allowed else default_tab
    ctx.update({
        "admin_tabs": tabs,
        "admin_default_tab": default_tab,
    })
    ctx.update(_dtf_admin_tab_context(active_tab))
    return _render(request, "dtf/admin/panel.html", ctx)


@login_required
@user_passes_test(_is_dtf_admin)
@require_http_methods(["GET"])
def admin_panel_tab(request, tab_key: str):
    allowed = {item["key"] for item in _dtf_admin_shell_tabs()}
    if tab_key not in allowed:
        return JsonResponse({"ok": False, "error": "unknown_tab"}, status=404)
    ctx = _base_context(request)
    ctx.update(_dtf_admin_tab_context(tab_key))
    return render(request, f"dtf/admin/tabs/{tab_key}.html", ctx)


@login_required
@user_passes_test(_is_dtf_admin)
@require_POST
def admin_order_update(request, order_id: int):
    order = get_object_or_404(DtfOrder, pk=order_id)
    form = DtfAdminOrderUpdateForm(request.POST, instance=order)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    current_lifecycle = order.lifecycle_status
    target_lifecycle = form.cleaned_data.get("lifecycle_status")
    updated_order = form.save(commit=False)

    if target_lifecycle and target_lifecycle != current_lifecycle:
        DtfStatusEvent.objects.create(
            order=order,
            status_from=current_lifecycle,
            status_to=target_lifecycle,
            actor="manager",
            public_message=_("Статус оновлено менеджером в DTF Admin"),
        )
        updated_order.lifecycle_status = target_lifecycle
        if target_lifecycle == DtfLifecycleStatus.DELIVERED and not updated_order.delivered_at:
            updated_order.delivered_at = timezone.now()
        if target_lifecycle == DtfLifecycleStatus.RECEIVED and not updated_order.received_at:
            updated_order.received_at = timezone.now()

    if updated_order.payment_status in {DtfPaymentStatus.PAID, DtfPaymentStatus.PARTIAL} and not updated_order.payment_updated_at:
        updated_order.payment_updated_at = timezone.now()

    updated_order.save()
    return JsonResponse({
        "ok": True,
        "message": _("Замовлення оновлено"),
        "order": _build_order_card_payload(updated_order),
    })


@login_required
@user_passes_test(_is_dtf_admin)
@require_POST
def admin_blog_create(request):
    form = DtfKnowledgePostAdminForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    post = form.save()
    return JsonResponse({
        "ok": True,
        "message": _("Публікацію створено"),
        "post": {
            "id": post.id,
            "title": post.title,
            "slug": post.slug,
            "published": post.is_published,
            "pub_date": post.pub_date.strftime("%Y-%m-%d"),
        },
    })


@login_required
@user_passes_test(_is_dtf_admin)
@require_POST
def admin_blog_update(request, post_id: int):
    post = get_object_or_404(KnowledgePost, pk=post_id)
    form = DtfKnowledgePostAdminForm(request.POST, instance=post)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    post = form.save()
    return JsonResponse({
        "ok": True,
        "message": _("Публікацію оновлено"),
        "post": {
            "id": post.id,
            "title": post.title,
            "slug": post.slug,
            "published": post.is_published,
            "pub_date": post.pub_date.strftime("%Y-%m-%d"),
        },
    })


@login_required
@user_passes_test(_is_dtf_admin)
@require_POST
def admin_blog_delete(request, post_id: int):
    post = get_object_or_404(KnowledgePost, pk=post_id)
    post.delete()
    return JsonResponse({"ok": True, "message": _("Публікацію видалено")})


@login_required
@user_passes_test(_is_dtf_admin)
@require_http_methods(["GET"])
def admin_blog_slug_preview(request):
    raw = (request.GET.get("value") or request.GET.get("title") or "").strip()
    slug = unique_slug_for_queryset(KnowledgePost.objects.all(), raw, fallback="knowledge-post", max_length=240)
    return JsonResponse({"ok": True, "slug": slug})


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
