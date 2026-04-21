from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from orders.forms import TelegramNovaPoshtaWaybillForm
from orders.models import Order
from orders.nova_poshta_data import apply_nova_poshta_refs
from orders.nova_poshta_documents import (
    TELEGRAM_CREATE_NP_WAYBILL_ACTION,
    NovaPoshtaDocumentError,
    NovaPoshtaDocumentService,
    build_waybill_description,
)
from orders.status_management import (
    _apply_order_status_update_to_order,
    apply_order_status_update,
    can_apply_telegram_status_action,
    first_validation_error,
    get_telegram_status_action,
)
from orders.telegram_notifications import telegram_notifier
from orders.telegram_status_links import (
    verify_order_action_token,
    verify_order_status_token,
)

logger = logging.getLogger(__name__)

STATUS_ACTION_TEMPLATE = "pages/telegram_order_status_action.html"
WAYBILL_ACTION_TEMPLATE = "pages/telegram_order_nova_poshta_action.html"


def _get_token(request) -> str:
    return (request.POST.get("token") or request.GET.get("token") or "").strip()


def _render_template(request, template_name: str, context: dict, *, status_code: int = 200):
    return render(request, template_name, context, status=status_code)


def _manual_ship_action_block_reason(order: Order, status: str) -> str | None:
    if not can_apply_telegram_status_action(order, status):
        return (
            f"Для цього замовлення дія більше недоступна. "
            f"Поточний статус: {order.get_status_display()}."
        )
    if status == "ship" and (order.tracking_number or order.nova_poshta_document_ref):
        return "Для цього замовлення ТТН уже збережена. Повторне оновлення через старе посилання заблоковано."
    return None


def _waybill_action_block_reason(order: Order) -> str | None:
    if order.status in {"done", "cancelled"}:
        return (
            f"Створення ТТН більше недоступне. "
            f"Поточний статус: {order.get_status_display()}."
        )
    if order.nova_poshta_document_ref:
        return "Для цього замовлення накладну Нова пошта вже створено."
    if order.tracking_number:
        return "Для цього замовлення ТТН уже збережена вручну або через інший сценарій."
    return None


def _fallback_waybill_initial(service: NovaPoshtaDocumentService, order: Order) -> dict[str, str]:
    cod_amount = service._get_cod_amount(order)
    declared_cost = service._as_money(getattr(order, "total_sum", 0))
    return {
        "recipient_full_name": order.full_name or "",
        "recipient_phone": order.phone or "",
        "recipient_city": order.city or "",
        "recipient_settlement_ref": getattr(order, "np_settlement_ref", "") or "",
        "recipient_city_ref": getattr(order, "np_city_ref", "") or "",
        "recipient_warehouse": order.np_office or "",
        "recipient_warehouse_ref": getattr(order, "np_warehouse_ref", "") or "",
        "sender_city": service.SENDER_CITY_QUERY,
        "sender_settlement_ref": "",
        "sender_city_ref": "",
        "sender_warehouse": service.SENDER_WAREHOUSE_QUERY,
        "sender_warehouse_ref": "",
        "description": build_waybill_description(order),
        "declared_cost": f"{declared_cost:.2f}",
        "weight": "1.0",
        "seats_amount": "1",
        "length_cm": f"{service.DEFAULT_LENGTH_CM}",
        "width_cm": f"{service.DEFAULT_WIDTH_CM}",
        "height_cm": f"{service.DEFAULT_HEIGHT_CM}",
        "cod_amount": f"{cod_amount:.2f}" if cod_amount > 0 else "",
        "payer_type": "Recipient",
        "payment_method": "Cash",
    }


def _build_waybill_initial(service: NovaPoshtaDocumentService, order: Order) -> tuple[dict[str, str], str]:
    try:
        return service.build_initial_payload(order), ""
    except NovaPoshtaDocumentError as exc:
        logger.warning("Failed to prefill Nova Poshta action for order %s: %s", order.pk, exc)
        fallback = _fallback_waybill_initial(service, order)
        return fallback, (
            "Не вдалося повністю підтягнути довідкові дані Нової пошти. "
            "Можна перевірити поля вручну і спробувати створити ТТН повторно."
        )


def _update_telegram_message_after_order_change(order: Order) -> None:
    try:
        telegram_notifier.update_order_notification_message(order, clear_actions=True)
    except Exception:
        logger.exception("Failed to update Telegram order notification message for order %s", order.pk)


def _render_status_action_page(
    request,
    *,
    order: Order | None,
    action: dict | None,
    token: str,
    status_code: int = 200,
    success_message: str = "",
    error_message: str = "",
    is_success: bool = False,
    is_blocked: bool = False,
    tracking_number: str = "",
    can_submit: bool = True,
):
    return _render_template(
        request,
        STATUS_ACTION_TEMPLATE,
        {
            "order": order,
            "action": action,
            "token": token,
            "success_message": success_message,
            "error_message": error_message,
            "is_success": is_success,
            "is_blocked": is_blocked,
            "tracking_number": tracking_number,
            "can_submit": can_submit,
        },
        status_code=status_code,
    )


def _render_waybill_action_page(
    request,
    *,
    order: Order | None,
    token: str,
    form: TelegramNovaPoshtaWaybillForm | None,
    status_code: int = 200,
    success_message: str = "",
    error_message: str = "",
    helper_message: str = "",
    is_success: bool = False,
    is_blocked: bool = False,
    warnings: list[str] | None = None,
    can_submit: bool = True,
):
    return _render_template(
        request,
        WAYBILL_ACTION_TEMPLATE,
        {
            "order": order,
            "token": token,
            "form": form,
            "success_message": success_message,
            "error_message": error_message,
            "helper_message": helper_message,
            "is_success": is_success,
            "is_blocked": is_blocked,
            "warnings": warnings or [],
            "can_submit": can_submit,
        },
        status_code=status_code,
    )


@require_http_methods(["GET", "POST"])
def telegram_order_status_action(request, order_id: int, status: str):
    action = get_telegram_status_action(status)
    if not action:
        raise Http404("Unknown Telegram order action")

    token = _get_token(request)
    if not verify_order_status_token(token, order_id=order_id, status=status):
        return _render_status_action_page(
            request,
            order=None,
            action=action,
            token=token,
            status_code=403,
            error_message="Посилання недійсне або вже застаріло. Відкрийте актуальне повідомлення в Telegram.",
            can_submit=False,
        )

    order = get_object_or_404(Order, pk=order_id)
    block_reason = _manual_ship_action_block_reason(order, status)
    if block_reason:
        return _render_status_action_page(
            request,
            order=order,
            action=action,
            token=token,
            status_code=409,
            is_blocked=True,
            tracking_number=order.tracking_number or "",
            error_message=block_reason,
            can_submit=False,
        )

    tracking_number = (request.POST.get("tracking_number") or order.tracking_number or "").strip()
    if request.method == "POST":
        try:
            result = apply_order_status_update(
                order.pk,
                status=status,
                tracking_number=tracking_number,
                require_tracking_number=bool(action.get("requires_tracking_number")),
            )
            updated_order = result["order"]
            _update_telegram_message_after_order_change(updated_order)
            return _render_status_action_page(
                request,
                order=updated_order,
                action=action,
                token=token,
                is_success=True,
                tracking_number=updated_order.tracking_number or "",
                success_message=(
                    f"Замовлення #{updated_order.order_number} переведено у статус "
                    f"«{updated_order.get_status_display()}»."
                ),
            )
        except ValidationError as exc:
            return _render_status_action_page(
                request,
                order=order,
                action=action,
                token=token,
                tracking_number=tracking_number,
                error_message=first_validation_error(exc),
            )

    return _render_status_action_page(
        request,
        order=order,
        action=action,
        token=token,
        tracking_number=tracking_number,
    )


@require_http_methods(["GET", "POST"])
def telegram_order_np_waybill_action(request, order_id: int, action: str):
    if action != TELEGRAM_CREATE_NP_WAYBILL_ACTION:
        raise Http404("Unknown Telegram order action")

    token = _get_token(request)
    if not verify_order_action_token(token, order_id=order_id, action=action):
        return _render_waybill_action_page(
            request,
            order=None,
            token=token,
            form=None,
            status_code=403,
            error_message="Посилання недійсне або вже застаріло. Відкрийте актуальне повідомлення в Telegram.",
            can_submit=False,
        )

    order = get_object_or_404(Order, pk=order_id)
    block_reason = _waybill_action_block_reason(order)
    if block_reason:
        return _render_waybill_action_page(
            request,
            order=order,
            token=token,
            form=None,
            status_code=409,
            error_message=block_reason,
            is_blocked=True,
            can_submit=False,
        )

    service = NovaPoshtaDocumentService()
    if not service.is_configured():
        return _render_waybill_action_page(
            request,
            order=order,
            token=token,
            form=None,
            status_code=503,
            error_message="Інтеграція з Nova Poshta API не налаштована в цьому середовищі.",
            can_submit=False,
        )

    initial, helper_message = _build_waybill_initial(service, order)
    form = TelegramNovaPoshtaWaybillForm(request.POST or None, initial=initial if request.method == "GET" else None)

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                locked_order = (
                    Order.objects.select_for_update()
                    .select_related("user")
                    .prefetch_related("items__product")
                    .get(pk=order.pk)
                )
                block_reason = _waybill_action_block_reason(locked_order)
                if block_reason:
                    return _render_waybill_action_page(
                        request,
                        order=locked_order,
                        token=token,
                        form=form,
                        status_code=409,
                        error_message=block_reason,
                        is_blocked=True,
                        can_submit=False,
                )

                created = service.create_waybill(locked_order, form.cleaned_data)
                recipient_point = created["recipient_point"]
                locked_order.full_name = form.cleaned_data["recipient_full_name"]
                locked_order.phone = form.cleaned_data["recipient_phone"]
                locked_order.city = recipient_point.city_label or form.cleaned_data["recipient_city"]
                locked_order.np_office = recipient_point.warehouse_label or form.cleaned_data["recipient_warehouse"]
                apply_nova_poshta_refs(
                    locked_order,
                    {
                        "np_settlement_ref": recipient_point.settlement_ref,
                        "np_city_ref": recipient_point.city_ref,
                        "np_warehouse_ref": recipient_point.warehouse_ref,
                    },
                )
                locked_order.nova_poshta_recipient_ref = created["recipient_ref"]
                locked_order.nova_poshta_recipient_contact_ref = created["recipient_contact_ref"]
                locked_order.nova_poshta_document_ref = created["document_ref"] or None

                update_result = _apply_order_status_update_to_order(
                    locked_order,
                    status="ship",
                    tracking_number=created["tracking_number"],
                    require_tracking_number=True,
                )
                updated_order = update_result["order"]

            _update_telegram_message_after_order_change(updated_order)
            return _render_waybill_action_page(
                request,
                order=updated_order,
                token=token,
                form=TelegramNovaPoshtaWaybillForm(initial=form.cleaned_data),
                is_success=True,
                success_message=(
                    f"ТТН {updated_order.tracking_number} створено і прив’язано до замовлення "
                    f"#{updated_order.order_number}."
                ),
                warnings=created.get("warnings") or [],
                helper_message=helper_message,
                can_submit=False,
            )
        except NovaPoshtaDocumentError as exc:
            error_message = str(exc)
        except ValidationError as exc:
            error_message = first_validation_error(exc)
        except Exception:
            logger.exception("Unexpected error while creating Nova Poshta waybill for order %s", order.pk)
            error_message = "Не вдалося створити ТТН через внутрішню помилку. Спробуйте ще раз."

        return _render_waybill_action_page(
            request,
            order=order,
            token=token,
            form=form,
            error_message=error_message,
            helper_message=helper_message,
        )

    return _render_waybill_action_page(
        request,
        order=order,
        token=token,
        form=form,
        helper_message=helper_message,
    )
