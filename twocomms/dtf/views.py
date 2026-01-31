from decimal import Decimal

from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
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
    get_limits,
    get_pricing_config,
    normalize_phone,
)


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
    }


def _render(request, template, context):
    response = render(request, template, context)
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
def status(request):
    ctx = _base_context(request)
    order = None
    error = None
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
    status_index = None
    if order:
        try:
            status_index = [code for code, _ in STATUS_STEPS].index(order.status)
        except ValueError:
            status_index = None
    ctx.update({
        "order": order,
        "error": error,
        "status_steps": STATUS_STEPS,
        "status_index": status_index,
    })
    return _render(request, "dtf/status.html", ctx)


def requirements(request):
    ctx = _base_context(request)
    return _render(request, "dtf/requirements.html", ctx)


def price(request):
    ctx = _base_context(request)
    return _render(request, "dtf/price.html", ctx)


def delivery_payment(request):
    ctx = _base_context(request)
    return _render(request, "dtf/delivery_payment.html", ctx)


def contacts(request):
    ctx = _base_context(request)
    return _render(request, "dtf/contacts.html", ctx)


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
