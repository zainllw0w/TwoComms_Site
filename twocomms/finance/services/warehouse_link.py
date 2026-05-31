"""Інтеграція з warehouse: заморожені кошти у складі."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import F, Sum


def frozen_in_warehouse() -> Decimal:
    """Загальна собівартість залишків складу (товари + принти + розхідники).

    Безпечно деградує якщо warehouse недоступний.
    """
    try:
        from warehouse.models import StockItem, PrintColorVariant, ConsumableItem
    except Exception:
        return Decimal('0')

    try:
        # Товари
        stock_agg = StockItem.objects.aggregate(v=Sum(F('quantity') * F('cost_price')))
        stock_value = Decimal(stock_agg['v'] or 0)

        # Принти
        print_agg = PrintColorVariant.objects.aggregate(v=Sum(F('quantity') * F('cost_price')))
        print_value = Decimal(print_agg['v'] or 0)

        # Розхідники
        consumable_agg = ConsumableItem.objects.aggregate(v=Sum(F('quantity') * F('cost_per_unit')))
        consumable_value = Decimal(consumable_agg['v'] or 0)

        return stock_value + print_value + consumable_value
    except Exception:
        return Decimal('0')


def warehouse_breakdown() -> dict:
    """Деталізація замороженого по типах.

    Returns:
        {
            'stock_value': Decimal,
            'print_value': Decimal,
            'consumable_value': Decimal,
            'stock_qty': int,
            'print_qty': int,
            'consumable_qty': int,
            'total': Decimal,
        }
    """
    try:
        from warehouse.models import StockItem, PrintColorVariant, ConsumableItem
    except Exception:
        return {
            'stock_value': Decimal('0'),
            'print_value': Decimal('0'),
            'consumable_value': Decimal('0'),
            'stock_qty': 0,
            'print_qty': 0,
            'consumable_qty': 0,
            'total': Decimal('0'),
        }

    try:
        # Товари
        stock_agg = StockItem.objects.aggregate(
            v=Sum(F('quantity') * F('cost_price')),
            q=Sum('quantity')
        )
        stock_value = Decimal(stock_agg['v'] or 0)
        stock_qty = stock_agg['q'] or 0

        # Принти
        print_agg = PrintColorVariant.objects.aggregate(
            v=Sum(F('quantity') * F('cost_price')),
            q=Sum('quantity')
        )
        print_value = Decimal(print_agg['v'] or 0)
        print_qty = print_agg['q'] or 0

        # Розхідники
        consumable_agg = ConsumableItem.objects.aggregate(
            v=Sum(F('quantity') * F('cost_per_unit')),
            q=Sum('quantity')
        )
        consumable_value = Decimal(consumable_agg['v'] or 0)
        consumable_qty = int(consumable_agg['q'] or 0)

        return {
            'stock_value': stock_value,
            'print_value': print_value,
            'consumable_value': consumable_value,
            'stock_qty': stock_qty,
            'print_qty': print_qty,
            'consumable_qty': consumable_qty,
            'total': stock_value + print_value + consumable_value,
        }
    except Exception:
        return {
            'stock_value': Decimal('0'),
            'print_value': Decimal('0'),
            'consumable_value': Decimal('0'),
            'stock_qty': 0,
            'print_qty': 0,
            'consumable_qty': 0,
            'total': Decimal('0'),
        }
