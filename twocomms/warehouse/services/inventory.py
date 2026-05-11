"""Бізнес-операції зі складом: запис рухів, коригування, списання."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from warehouse.models import (
    MovementReason,
    PrintColorVariant,
    StockItem,
    StockMovement,
    WriteOffRequest,
)


@transaction.atomic
def adjust_stock_item(
    *,
    stock_item: StockItem,
    delta: int,
    user=None,
    reason: str = MovementReason.MANUAL_ADD,
    comment: str = "",
    order=None,
    write_off_request: Optional[WriteOffRequest] = None,
    cost_price_override: Optional[Decimal] = None,
) -> StockMovement:
    """Змінити кількість StockItem на delta та зафіксувати StockMovement."""
    if delta == 0:
        raise ValueError("Delta cannot be zero")

    new_qty = stock_item.quantity + delta
    if new_qty < 0:
        raise ValueError(
            f"Недостатньо залишку: маємо {stock_item.quantity}, спроба списати {-delta}"
        )

    stock_item.quantity = new_qty
    if cost_price_override is not None:
        stock_item.cost_price = cost_price_override
    stock_item.save(update_fields=["quantity", "cost_price", "updated_at"])

    return StockMovement.objects.create(
        content_type=ContentType.objects.get_for_model(StockItem),
        object_id=stock_item.pk,
        delta=delta,
        quantity_after=new_qty,
        reason=reason,
        comment=comment,
        order=order,
        write_off_request=write_off_request,
        created_by=user,
    )


@transaction.atomic
def adjust_print_variant(
    *,
    variant: PrintColorVariant,
    delta: int,
    user=None,
    reason: str = MovementReason.PRINT_ADD,
    comment: str = "",
    cost_price_override: Optional[Decimal] = None,
) -> StockMovement:
    """Змінити кількість PrintColorVariant та зафіксувати StockMovement."""
    if delta == 0:
        raise ValueError("Delta cannot be zero")

    new_qty = variant.quantity + delta
    if new_qty < 0:
        raise ValueError(
            f"Недостатньо принтів: маємо {variant.quantity}, спроба списати {-delta}"
        )
    variant.quantity = new_qty
    if cost_price_override is not None:
        variant.cost_price = cost_price_override
    variant.save(update_fields=["quantity", "cost_price", "updated_at"])

    return StockMovement.objects.create(
        content_type=ContentType.objects.get_for_model(PrintColorVariant),
        object_id=variant.pk,
        delta=delta,
        quantity_after=new_qty,
        reason=reason,
        comment=comment,
        created_by=user,
    )


def set_stock_quantity(
    *,
    stock_item: StockItem,
    new_quantity: int,
    user=None,
    reason: str = MovementReason.RECOUNT,
    comment: str = "",
    cost_price_override: Optional[Decimal] = None,
) -> Optional[StockMovement]:
    """Встановити абсолютну кількість (для інвентаризації)."""
    if new_quantity < 0:
        raise ValueError("Quantity cannot be negative")
    delta = new_quantity - stock_item.quantity
    if delta == 0 and cost_price_override is None:
        return None
    if delta == 0 and cost_price_override is not None:
        # тільки оновлення собівартості, не створюємо movement
        stock_item.cost_price = cost_price_override
        stock_item.save(update_fields=["cost_price", "updated_at"])
        return None
    return adjust_stock_item(
        stock_item=stock_item,
        delta=delta,
        user=user,
        reason=reason,
        comment=comment,
        cost_price_override=cost_price_override,
    )


def set_print_variant_quantity(
    *,
    variant: PrintColorVariant,
    new_quantity: int,
    user=None,
    reason: str = MovementReason.RECOUNT,
    comment: str = "",
    cost_price_override: Optional[Decimal] = None,
) -> Optional[StockMovement]:
    if new_quantity < 0:
        raise ValueError("Quantity cannot be negative")
    delta = new_quantity - variant.quantity
    if delta == 0 and cost_price_override is None:
        return None
    if delta == 0 and cost_price_override is not None:
        variant.cost_price = cost_price_override
        variant.save(update_fields=["cost_price", "updated_at"])
        return None
    return adjust_print_variant(
        variant=variant,
        delta=delta,
        user=user,
        reason=reason,
        comment=comment,
        cost_price_override=cost_price_override,
    )
