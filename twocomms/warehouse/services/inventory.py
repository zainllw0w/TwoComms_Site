"""Бізнес-операції зі складом: запис рухів, коригування, списання."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
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


def weighted_average_cost(
    *,
    old_qty: int,
    old_cost: Decimal,
    add_qty: int,
    add_cost: Decimal,
) -> Decimal:
    """Розрахунок середньозваженої собівартості при прибутті нової партії.

    Формула: (old_qty × old_cost + add_qty × add_cost) / (old_qty + add_qty)

    Якщо ``old_qty == 0`` — повертає ``add_cost`` (стартова собівартість).
    Якщо ``add_qty == 0`` — повертає ``old_cost`` (нічого не змінюється).
    Округлення до 2 знаків після коми (стандартна точність грн).
    """
    if old_qty == 0 and add_qty == 0:
        return old_cost
    if old_qty == 0:
        return Decimal(add_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if add_qty == 0:
        return Decimal(old_cost)
    total_value = (Decimal(old_qty) * Decimal(old_cost)) + (Decimal(add_qty) * Decimal(add_cost))
    new_qty = Decimal(old_qty + add_qty)
    return (total_value / new_qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
    """Змінити кількість StockItem на delta та зафіксувати StockMovement.

    Поведінка cost_price:
    - delta > 0 (прихід) і ``cost_price_override`` задано →
      нова cost_price = weighted average (old × old_qty + override × delta) / total.
      Це зберігає історію витрат: якщо було 5 шт по 500, додаємо 7 по 550 —
      середня стане ~529 грн, а не 550. Старі гроші не «забуваються».
    - delta > 0 без override → cost_price лишається без змін.
    - delta < 0 (списання/продаж) → cost_price НЕ змінюється
      (override ігнорується, бо ми не «купуємо» позицію).
    """
    if delta == 0:
        raise ValueError("Delta cannot be zero")

    old_qty = stock_item.quantity
    new_qty = old_qty + delta
    if new_qty < 0:
        raise ValueError(
            f"Недостатньо залишку: маємо {old_qty}, спроба списати {-delta}"
        )

    stock_item.quantity = new_qty
    if cost_price_override is not None and delta > 0:
        stock_item.cost_price = weighted_average_cost(
            old_qty=old_qty,
            old_cost=stock_item.cost_price,
            add_qty=delta,
            add_cost=Decimal(cost_price_override),
        )
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

    old_qty = variant.quantity
    new_qty = old_qty + delta
    if new_qty < 0:
        raise ValueError(
            f"Недостатньо принтів: маємо {old_qty}, спроба списати {-delta}"
        )
    variant.quantity = new_qty
    if cost_price_override is not None and delta > 0:
        variant.cost_price = weighted_average_cost(
            old_qty=old_qty,
            old_cost=variant.cost_price,
            add_qty=delta,
            add_cost=Decimal(cost_price_override),
        )
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
