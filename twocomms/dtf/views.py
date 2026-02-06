from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.translation import gettext_lazy as _

from .forms import DtfOrderForm, DtfHelpForm, DtfFabLeadForm
from .models import DtfOrder, DtfLead, DtfLeadAttachment, DtfWork, WorkCategory, OrderStatus, LeadType, LengthSource
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


def _base_context(request):
    lang = activate_language_from_request(request)
    return {
        "current_lang": lang,
        "lang_links": build_lang_links(request),
        "pricing": get_pricing_config(),
        "limits": get_limits(),
        "feature_flags": get_feature_flags(),
    }


def _render(request, template, context, status: int | None = None):
    response = render(request, template, context, status=status)
    lang = request.GET.get("lang")
    if lang in ("uk", "ru"):
        response.set_cookie("dtf_lang", lang, max_age=365 * 24 * 3600)
    return response


def landing(request):
    ctx = _base_context(request)
    works = DtfWork.objects.filter(is_active=True).order_by("sort_order", "-created_at")
    ctx.update({
        "works": works,
        "work_macro": [w for w in works if w.category == WorkCategory.MACRO][:3],
        "work_process": [w for w in works if w.category == WorkCategory.PROCESS][:3],
        "work_final": [w for w in works if w.category == WorkCategory.FINAL][:3],
        "status_steps": STATUS_STEPS,
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


@require_http_methods(["GET", "POST"])
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
                for file in request.FILES.getlist("files"):
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


def thanks(request, kind: str, number: str):
    ctx = _base_context(request)
    if kind == "order":
        obj = get_object_or_404(DtfOrder, order_number=number)
        ctx.update({"kind": "order", "item": obj})
    else:
        obj = get_object_or_404(DtfLead, lead_number=number)
        ctx.update({"kind": "lead", "item": obj})
    return _render(request, "dtf/thanks.html", ctx)


@require_http_methods(["GET", "POST"])
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


def templates(request):
    ctx = _base_context(request)
    return _render(request, "dtf/templates.html", ctx)


def how_to_press(request):
    ctx = _base_context(request)
    return _render(request, "dtf/how_to_press.html", ctx)


@require_http_methods(["GET", "POST"])
def preflight(request):
    ctx = _base_context(request)
    if request.method == "POST":
        form = DtfHelpForm(request.POST, request.FILES)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.lead_type = LeadType.HELP
            lead.source = "preflight"
            lead.save()
            for file in request.FILES.getlist("files"):
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
