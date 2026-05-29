"""Зв'язка з warehouse (storage субдомен): скільки коштів «заморожено» у складі.

Рахуємо собівартість залишків = Σ(quantity × cost_price) по StockItem та
PrintColorVariant. warehouse живе в тій самій (default) БД, тож читаємо напряму.
Значення у гривні (база компанії). Безпечно деградує, якщо warehouse недоступний.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import F, Sum


def frozen_in_warehouse() -> Decimal:
    """Загальна собівартість залишків складу (товари + принти)."""
    total = Decimal('0')
    try:
        from warehouse.models import StockItem, PrintColorVariant
    except Exception:
        return total
    try:
        stock = StockItem.objects.aggregate(
            v=Sum(F('quantity') * F('cost_price')))['v'] or Decimal('0')
        prints = PrintColorVariant.objects.aggregate(
            v=Sum(F('quantity') * F('cost_price')))['v'] or Decimal('0')
        total = Decimal(stock) + Decimal(prints)
    except Exception:
        return Decimal('0')
    return total.quantize(Decimal('0.01'))


def warehouse_breakdown() -> dict:
    """Деталізація: окремо товари і принти, кількість позицій."""
    out = {'stock_value': Decimal('0'), 'print_value': Decimal('0'),
           'stock_qty': 0, 'print_qty': 0, 'total': Decimal('0')}
    try:
        from warehouse.models import StockItem, PrintColorVariant
    except Exception:
        return out
    try:
        s = StockItem.objects.aggregate(
            v=Sum(F('quantity') * F('cost_price')), q=Sum('quantity'))
        p = PrintColorVariant.objects.aggregate(
            v=Sum(F('quantity') * F('cost_price')), q=Sum('quantity'))
        out['stock_value'] = Decimal(s['v'] or 0)
        out['print_value'] = Decimal(p['v'] or 0)
        out['stock_qty'] = int(s['q'] or 0)
        out['print_qty'] = int(p['q'] or 0)
        out['total'] = (out['stock_value'] + out['print_value']).quantize(Decimal('0.01'))
    except Exception:
        pass
    return out
