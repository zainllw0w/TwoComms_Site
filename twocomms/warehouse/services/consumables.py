"""Сервіс для роботи з розхідними матеріалами — БЛОК 4."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from warehouse.models import ConsumableItem, StockMovement, MovementReason


@transaction.atomic
def adjust_consumable(
    *,
    consumable: ConsumableItem,
    delta: Decimal,
    user=None,
    reason: str = MovementReason.MANUAL_REMOVE,
    comment: str = "",
    order=None,
    write_off_request=None,
) -> StockMovement:
    """Коригування кількості розхідного матеріалу.

    Args:
        consumable: Розхідний матеріал
        delta: Зміна кількості (може бути дробовою, напр. 0.5 л)
        user: Користувач який виконує операцію
        reason: Причина руху
        comment: Коментар
        order: Зв'язане замовлення (якщо списання при продажу)
        write_off_request: Зв'язаний запит на списання

    Returns:
        Створений StockMovement

    Raises:
        ValueError: Якщо після операції кількість стане негативною
    """
    new_qty = consumable.quantity + delta

    if new_qty < 0:
        raise ValueError(
            f"Недостатньо {consumable.name}: є {consumable.quantity} {consumable.unit}, "
            f"потрібно {abs(delta)} {consumable.unit}"
        )

    # Оновлюємо кількість
    consumable.quantity = new_qty
    consumable.save()

    # Створюємо запис руху
    movement = StockMovement.objects.create(
        content_type=ContentType.objects.get_for_model(ConsumableItem),
        object_id=consumable.pk,
        delta=delta,
        quantity_after=new_qty,
        reason=reason,
        comment=comment or "",
        order=order,
        write_off_request=write_off_request,
        created_by=user,
    )

    return movement


def add_consumable_stock(
    *,
    consumable: ConsumableItem,
    quantity: Decimal,
    cost_per_unit: Decimal,
    user=None,
    comment: str = "",
) -> StockMovement:
    """Додавання нової партії розхідного матеріалу.

    Автоматично розраховує середньозважену собівартість.

    Args:
        consumable: Розхідний матеріал
        quantity: Кількість що додається
        cost_per_unit: Собівартість за одиницю нової партії
        user: Користувач
        comment: Коментар

    Returns:
        Створений StockMovement
    """
    # Розраховуємо нову середньозважену собівартість
    if consumable.quantity > 0:
        old_value = consumable.quantity * consumable.cost_per_unit
        new_value = quantity * cost_per_unit
        total_value = old_value + new_value
        total_qty = consumable.quantity + quantity
        consumable.cost_per_unit = (total_value / total_qty).quantize(Decimal("0.01"))
    else:
        consumable.cost_per_unit = cost_per_unit

    # Додаємо кількість
    return adjust_consumable(
        consumable=consumable,
        delta=quantity,
        user=user,
        reason=MovementReason.BULK_ADD,
        comment=comment or f"Прихід партії: {quantity} {consumable.unit} по {cost_per_unit} грн",
    )


def use_consumable(
    *,
    consumable: ConsumableItem,
    quantity: Decimal,
    user=None,
    comment: str = "",
    order=None,
    write_off_request=None,
) -> StockMovement:
    """Списання розхідного матеріалу при використанні.

    Args:
        consumable: Розхідний матеріал
        quantity: Кількість що використовується
        user: Користувач
        comment: Коментар
        order: Зв'язане замовлення
        write_off_request: Зв'язаний запит на списання

    Returns:
        Створений StockMovement
    """
    return adjust_consumable(
        consumable=consumable,
        delta=-quantity,
        user=user,
        reason=MovementReason.ORDER_WRITE_OFF if order else MovementReason.MANUAL_REMOVE,
        comment=comment or f"Використано: {quantity} {consumable.unit}",
        order=order,
        write_off_request=write_off_request,
    )


def get_low_stock_consumables() -> list[ConsumableItem]:
    """Повертає список розхідників з низьким залишком.

    Returns:
        Список ConsumableItem де quantity <= min_stock_alert
    """
    return list(
        ConsumableItem.objects.filter(
            quantity__lte=models.F("min_stock_alert")
        ).order_by("quantity")
    )


def consumables_total_value() -> Decimal:
    """Загальна вартість всіх розхідних матеріалів на складі.

    Returns:
        Сума (quantity × cost_per_unit) по всіх ConsumableItem
    """
    from django.db.models import Sum, F

    result = ConsumableItem.objects.aggregate(
        total=Sum(F("quantity") * F("cost_per_unit"))
    )
    return Decimal(result["total"] or 0)
