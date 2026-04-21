from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import UserPoints
from orders.models import Order


POINTS_AWARDING_STATUSES = frozenset({"prep", "ship", "done"})
POINTS_CANCELLING_STATUSES = frozenset({"cancelled"})

TELEGRAM_STATUS_ACTIONS: dict[str, dict[str, Any]] = {
    "ship": {
        "label": "Відправлено",
        "button_text": "🚚 Відправлено + ТТН",
        "requires_tracking_number": True,
        "allowed_current_statuses": frozenset({"new", "prep", "ship"}),
    },
}


def first_validation_error(exc: ValidationError) -> str:
    if getattr(exc, "message_dict", None):
        for messages in exc.message_dict.values():
            if messages:
                return str(messages[0])
    if getattr(exc, "messages", None):
        return str(exc.messages[0])
    return str(exc)


def get_telegram_status_action(status: str) -> dict[str, Any] | None:
    return TELEGRAM_STATUS_ACTIONS.get((status or "").strip())


def can_apply_telegram_status_action(order: Order, status: str) -> bool:
    action = get_telegram_status_action(status)
    if not action:
        return False
    return (order.status or "") in action["allowed_current_statuses"]


def _validate_cancellation(status: str, cancellation_reason: str, cancellation_comment: str) -> tuple[str | None, str | None]:
    if status != "cancelled":
        return None, None

    valid_reasons = {code for code, _ in Order._meta.get_field("cancellation_reason").choices}
    normalized_reason = (cancellation_reason or "").strip()
    normalized_comment = (cancellation_comment or "").strip()

    if not normalized_reason:
        raise ValidationError({"cancellation_reason": "Вкажіть причину скасування"})
    if normalized_reason not in valid_reasons:
        raise ValidationError({"cancellation_reason": "Невірна причина скасування"})

    return normalized_reason, normalized_comment or None


def _sync_loyalty_points(order: Order, *, old_status: str) -> None:
    if not order.user:
        return

    user_points = UserPoints.get_or_create_points(order.user)
    total_points = 0
    for item in order.items.all():
        if item.product.points_reward > 0:
            total_points += item.product.points_reward * item.qty

    if total_points <= 0:
        return

    if (
        order.status in POINTS_AWARDING_STATUSES
        and old_status not in POINTS_AWARDING_STATUSES
        and not order.points_awarded
    ):
        user_points.add_points(total_points, f"Замовлення #{order.order_number} {order.get_status_display()}")
        order.points_awarded = True
        order.save(update_fields=["points_awarded"])
        return

    if (
        order.status in POINTS_CANCELLING_STATUSES
        and old_status not in POINTS_CANCELLING_STATUSES
        and order.points_awarded
    ):
        user_points.spend_points(total_points, f"Скасування замовлення #{order.order_number}")
        order.points_awarded = False
        order.save(update_fields=["points_awarded"])


def _apply_order_status_update_to_order(
    order: Order,
    *,
    status: str,
    tracking_number: str = "",
    cancellation_reason: str = "",
    cancellation_comment: str = "",
    require_tracking_number: bool = False,
) -> dict[str, Any]:
    normalized_status = (status or "").strip()
    normalized_tracking = (tracking_number or "").strip()

    old_status = order.status
    old_tracking_number = order.tracking_number or ""

    cancellation_reason_value, cancellation_comment_value = _validate_cancellation(
        normalized_status,
        cancellation_reason,
        cancellation_comment,
    )

    if require_tracking_number and not (normalized_tracking or order.tracking_number):
        raise ValidationError({"tracking_number": "Вкажіть ТТН"})

    order.status = normalized_status
    order.cancellation_reason = cancellation_reason_value
    order.cancellation_comment = cancellation_comment_value

    if normalized_tracking:
        order.tracking_number = normalized_tracking

    order.save()
    _sync_loyalty_points(order, old_status=old_status)

    return {
        "order": order,
        "old_status": old_status,
        "status_changed": old_status != order.status,
        "tracking_changed": (order.tracking_number or "") != old_tracking_number,
        "tracking_number": order.tracking_number or "",
    }


def apply_order_status_update(
    order_or_id: Order | int | str,
    *,
    status: str,
    tracking_number: str = "",
    cancellation_reason: str = "",
    cancellation_comment: str = "",
    require_tracking_number: bool = False,
) -> dict[str, Any]:
    normalized_status = (status or "").strip()
    valid_statuses = dict(Order.STATUS_CHOICES)
    if normalized_status not in valid_statuses:
        raise ValidationError({"status": "Невірний статус"})

    order_id = getattr(order_or_id, "pk", order_or_id)

    with transaction.atomic():
        order = (
            Order.objects.select_for_update()
            .select_related("user")
            .prefetch_related("items__product")
            .get(pk=order_id)
        )
        return _apply_order_status_update_to_order(
            order,
            status=normalized_status,
            tracking_number=tracking_number,
            cancellation_reason=cancellation_reason,
            cancellation_comment=cancellation_comment,
            require_tracking_number=require_tracking_number,
        )
