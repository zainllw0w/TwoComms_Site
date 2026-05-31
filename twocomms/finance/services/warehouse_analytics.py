"""Аналітика складу — БЛОК 5."""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db.models import F, Sum, Count, Q
from django.utils import timezone


def warehouse_dynamics(days: int = 90) -> dict:
    """Графік динаміки вартості складу по днях.

    Args:
        days: Кількість днів для аналізу

    Returns:
        {
            'dates': list[str],  # Дати у форматі YYYY-MM-DD
            'total_value': list[float],  # Загальна вартість по днях
            'added_value': list[float],  # Додано за день
            'sold_value': list[float],  # Продано за день
            'written_off_value': list[float],  # Списано за день
            'current_value': Decimal,  # Поточна вартість
        }
    """
    from warehouse.models import StockMovement, MovementReason, StockItem, PrintColorVariant, ConsumableItem

    today = timezone.localdate()
    start_date = today - dt.timedelta(days=days)

    # Отримуємо всі рухи за період
    movements = StockMovement.objects.filter(
        created_at__date__gte=start_date
    ).select_related('content_type').order_by('created_at')

    # Групуємо по датах
    by_date = defaultdict(lambda: {'added': Decimal('0'), 'sold': Decimal('0'), 'written_off': Decimal('0')})

    for m in movements:
        date_key = m.created_at.date().isoformat()

        # Визначаємо тип руху та вартість
        if m.content_type.model == 'stockitem':
            try:
                item = StockItem.objects.get(pk=m.object_id)
                value = abs(m.delta) * item.cost_price
            except StockItem.DoesNotExist:
                continue
        elif m.content_type.model == 'printcolorvariant':
            try:
                item = PrintColorVariant.objects.get(pk=m.object_id)
                value = abs(m.delta) * item.cost_price
            except PrintColorVariant.DoesNotExist:
                continue
        elif m.content_type.model == 'consumableitem':
            try:
                item = ConsumableItem.objects.get(pk=m.object_id)
                value = abs(m.delta) * item.cost_per_unit
            except ConsumableItem.DoesNotExist:
                continue
        else:
            continue

        # Класифікуємо рух
        if m.reason in [MovementReason.BULK_ADD, MovementReason.PRINT_COMPLETE]:
            by_date[date_key]['added'] += value
        elif m.reason == MovementReason.ORDER_WRITE_OFF:
            by_date[date_key]['sold'] += value
        elif m.reason in [MovementReason.MANUAL_REMOVE, MovementReason.DAMAGE]:
            by_date[date_key]['written_off'] += value

    # Формуємо серії для графіка
    dates = []
    added_series = []
    sold_series = []
    written_off_series = []

    current_date = start_date
    while current_date <= today:
        date_key = current_date.isoformat()
        dates.append(date_key)
        data = by_date[date_key]
        added_series.append(float(data['added']))
        sold_series.append(float(data['sold']))
        written_off_series.append(float(data['written_off']))
        current_date += dt.timedelta(days=1)

    # Поточна вартість
    from finance.services.warehouse_link import frozen_in_warehouse
    current_value = frozen_in_warehouse()

    return {
        'dates': dates,
        'added_value': added_series,
        'sold_value': sold_series,
        'written_off_value': written_off_series,
        'current_value': current_value,
    }


def warehouse_structure() -> dict:
    """Структура складу за категоріями та товарами.

    Returns:
        {
            'by_category': list[dict],  # Топ категорій за вартістю
            'by_item': list[dict],  # Топ товарів за вартістю
            'by_consumable_category': list[dict],  # Розхідники за категоріями
            'total_value': Decimal,
        }
    """
    from warehouse.models import StockItem, PrintColorVariant, ConsumableItem, StorageCategory

    # Топ-10 категорій товарів
    categories = []
    for cat in StorageCategory.objects.all():
        value = cat.total_frozen_value
        if value > 0:
            categories.append({
                'name': cat.name,
                'value': value,
                'quantity': cat.total_quantity,
            })
    categories.sort(key=lambda x: x['value'], reverse=True)
    top_categories = categories[:10]

    # Топ-10 товарів за вартістю
    stock_items = StockItem.objects.annotate(
        total_value=F('quantity') * F('cost_price')
    ).filter(quantity__gt=0).order_by('-total_value')[:10]

    top_items = [{
        'name': f"{item.subcategory.category.name} / {item.subcategory.name} / {item.color.name} / {item.size}",
        'value': item.quantity * item.cost_price,
        'quantity': item.quantity,
    } for item in stock_items]

    # Розхідники за категоріями
    consumable_by_cat = ConsumableItem.objects.values('category').annotate(
        total_value=Sum(F('quantity') * F('cost_per_unit')),
        total_qty=Sum('quantity')
    ).order_by('-total_value')

    consumables = [{
        'name': dict(ConsumableItem.CATEGORY_CHOICES).get(c['category'], c['category']),
        'value': Decimal(c['total_value'] or 0),
        'quantity': int(c['total_qty'] or 0),
    } for c in consumable_by_cat]

    # Загальна вартість
    from finance.services.warehouse_link import frozen_in_warehouse
    total_value = frozen_in_warehouse()

    return {
        'by_category': top_categories,
        'by_item': top_items,
        'by_consumable_category': consumables,
        'total_value': total_value,
    }


def warehouse_turnover() -> dict:
    """Аналіз оборотності складу.

    Returns:
        {
            'dead_stock': list[dict],  # Товари без руху > 90 днів
            'slow_movers': list[dict],  # Повільні товари (60-90 днів)
            'fast_movers': list[dict],  # Швидкі товари (< 30 днів)
            'avg_days_in_stock': float,  # Середній час на складі
        }
    """
    from warehouse.models import StockItem, StockMovement, MovementReason
    from django.contrib.contenttypes.models import ContentType

    today = timezone.now()
    dead_threshold = today - dt.timedelta(days=90)
    slow_threshold = today - dt.timedelta(days=60)
    fast_threshold = today - dt.timedelta(days=30)

    stock_ct = ContentType.objects.get_for_model(StockItem)

    dead_stock = []
    slow_movers = []
    fast_movers = []
    total_days = 0
    total_items = 0

    for item in StockItem.objects.filter(quantity__gt=0).select_related('subcategory__category', 'color'):
        # Знаходимо останній рух цього товару
        last_movement = StockMovement.objects.filter(
            content_type=stock_ct,
            object_id=item.pk,
            reason=MovementReason.ORDER_WRITE_OFF
        ).order_by('-created_at').first()

        if last_movement:
            days_since_sale = (today - last_movement.created_at).days
        else:
            # Якщо не було продажів, беремо дату створення
            days_since_sale = (today - item.created_at).days if hasattr(item, 'created_at') else 999

        item_data = {
            'name': f"{item.subcategory.category.name} / {item.color.name} / {item.size}",
            'quantity': item.quantity,
            'value': item.quantity * item.cost_price,
            'days_since_sale': days_since_sale,
        }

        if days_since_sale > 90:
            dead_stock.append(item_data)
        elif days_since_sale > 60:
            slow_movers.append(item_data)
        elif days_since_sale < 30:
            fast_movers.append(item_data)

        total_days += days_since_sale
        total_items += 1

    avg_days = total_days / total_items if total_items > 0 else 0

    # Сортуємо
    dead_stock.sort(key=lambda x: x['days_since_sale'], reverse=True)
    slow_movers.sort(key=lambda x: x['days_since_sale'], reverse=True)
    fast_movers.sort(key=lambda x: x['days_since_sale'])

    return {
        'dead_stock': dead_stock[:20],
        'slow_movers': slow_movers[:20],
        'fast_movers': fast_movers[:20],
        'avg_days_in_stock': round(avg_days, 1),
    }
