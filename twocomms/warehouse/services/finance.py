"""Фінансові агрегати для дашборду."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import F, Sum

from warehouse.models import (
    Print,
    PrintColorVariant,
    StockItem,
    StockMovement,
    StorageCategory,
)


def total_frozen_value() -> Decimal:
    """Сума всіх позицій складу + всіх принтів."""
    stock_agg = StockItem.objects.aggregate(v=Sum(F("quantity") * F("cost_price")))
    print_agg = PrintColorVariant.objects.aggregate(v=Sum(F("quantity") * F("cost_price")))
    return Decimal(stock_agg["v"] or 0) + Decimal(print_agg["v"] or 0)


def frozen_value_by_category() -> list[dict]:
    """Розбивка замороженого по складських категоріях."""
    results = []
    for cat in StorageCategory.objects.filter(is_active=True).order_by("order", "name"):
        value = cat.total_frozen_value
        qty = cat.total_quantity
        results.append(
            {
                "category": cat,
                "qty": qty,
                "value": value,
            }
        )
    return results


def frozen_value_by_print() -> list[dict]:
    results = []
    for pr in Print.objects.filter(is_active=True).order_by("name"):
        results.append(
            {
                "print": pr,
                "qty": pr.total_quantity,
                "value": pr.total_frozen_value,
            }
        )
    return results


def movements_chart_data(days: int = 30) -> dict:
    """Дані для графіку рухів за останні N днів."""
    today = date.today()
    start = today - timedelta(days=days - 1)
    movements = (
        StockMovement.objects.filter(created_at__date__gte=start)
        .values("created_at__date", "reason")
        .annotate(total=Sum("delta"))
    )
    by_day: dict[str, dict] = {}
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        by_day[d] = {"in": 0, "out": 0}
    for row in movements:
        d = row["created_at__date"].isoformat()
        if d not in by_day:
            continue
        total = row["total"] or 0
        if total > 0:
            by_day[d]["in"] += total
        else:
            by_day[d]["out"] += abs(total)
    labels = sorted(by_day.keys())
    return {
        "labels": labels,
        "in_series": [by_day[d]["in"] for d in labels],
        "out_series": [by_day[d]["out"] for d in labels],
    }
