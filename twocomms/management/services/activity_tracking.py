"""
Розширений сервіс для відстеження активності менеджера

Відстежує:
1. Активний час (користувач взаємодіє з вкладкою)
2. Відкритий час (вкладка просто відкрита, але неактивна)
3. Загальний час роботи
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from management.models import ManagementDailyActivity


TWO_PLACES = Decimal('0.01')


def get_activity_stats(user, days=7) -> dict:
    """
    Отримати статистику активності за N днів

    Returns:
        dict з полями:
        - active_hours: Decimal - активний час (годин)
        - idle_hours: Decimal - відкритий але неактивний час (годин)
        - total_hours: Decimal - загальний час (годин)
        - active_days: int - кількість днів з активністю
        - avg_active_per_day: Decimal - середній активний час на день
        - activity_rate: Decimal - відсоток активності (0-100)
        - daily_breakdown: list - розбивка по днях
    """
    start_date = timezone.now().date() - timedelta(days=days-1)

    records = ManagementDailyActivity.objects.filter(
        user=user,
        date__gte=start_date
    ).order_by('date')

    # Підрахунок
    total_active_seconds = 0
    total_idle_seconds = 0
    active_days = 0
    daily_breakdown = []

    for record in records:
        active_sec = record.active_seconds or 0
        idle_sec = record.idle_seconds or 0

        total_active_seconds += active_sec
        total_idle_seconds += idle_sec

        if active_sec > 0:
            active_days += 1

        daily_breakdown.append({
            'date': record.date,
            'active_hours': Decimal(active_sec) / Decimal(3600),
            'idle_hours': Decimal(idle_sec) / Decimal(3600),
            'total_hours': Decimal(active_sec + idle_sec) / Decimal(3600),
        })

    # Конвертація в години
    active_hours = (Decimal(total_active_seconds) / Decimal(3600)).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )
    idle_hours = (Decimal(total_idle_seconds) / Decimal(3600)).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )
    total_hours = active_hours + idle_hours

    # Середній активний час на день
    avg_active_per_day = (active_hours / Decimal(days)).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    ) if days > 0 else Decimal('0')

    # Відсоток активності
    activity_rate = ((active_hours / total_hours * 100).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    ) if total_hours > 0 else Decimal('0'))

    return {
        'active_hours': active_hours,
        'idle_hours': idle_hours,
        'total_hours': total_hours,
        'active_days': active_days,
        'avg_active_per_day': avg_active_per_day,
        'activity_rate': activity_rate,
        'daily_breakdown': daily_breakdown,
    }


def record_activity_pulse(user, active_seconds: int, idle_seconds: int = 0):
    """
    Записати pulse активності

    Args:
        user: Користувач
        active_seconds: Секунд активності
        idle_seconds: Секунд неактивності (вкладка відкрита але неактивна)
    """
    # Обмеження для запобігання зловживанням
    active_seconds = max(0, min(active_seconds, 60))
    idle_seconds = max(0, min(idle_seconds, 300))  # До 5 хвилин idle за раз

    now = timezone.now()
    day = timezone.localdate(now)

    obj, created = ManagementDailyActivity.objects.get_or_create(
        user=user,
        date=day,
        defaults={
            'active_seconds': 0,
            'idle_seconds': 0,
        }
    )

    # Оновити лічильники
    obj.active_seconds += active_seconds
    obj.idle_seconds += idle_seconds
    obj.last_seen_at = now
    obj.save(update_fields=['active_seconds', 'idle_seconds', 'last_seen_at'])

    return obj


def get_today_activity(user) -> dict:
    """
    Отримати активність за сьогодні

    Returns:
        dict з полями:
        - active_hours: Decimal
        - idle_hours: Decimal
        - total_hours: Decimal
        - activity_rate: Decimal
        - last_seen: datetime
    """
    today = timezone.now().date()

    try:
        record = ManagementDailyActivity.objects.get(user=user, date=today)

        active_hours = (Decimal(record.active_seconds) / Decimal(3600)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        idle_hours = (Decimal(record.idle_seconds) / Decimal(3600)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        total_hours = active_hours + idle_hours

        activity_rate = ((active_hours / total_hours * 100).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        ) if total_hours > 0 else Decimal('0'))

        return {
            'active_hours': active_hours,
            'idle_hours': idle_hours,
            'total_hours': total_hours,
            'activity_rate': activity_rate,
            'last_seen': record.last_seen_at,
        }
    except ManagementDailyActivity.DoesNotExist:
        return {
            'active_hours': Decimal('0'),
            'idle_hours': Decimal('0'),
            'total_hours': Decimal('0'),
            'activity_rate': Decimal('0'),
            'last_seen': None,
        }


def is_user_online(user, threshold_minutes=5) -> bool:
    """
    Перевірити чи користувач онлайн

    Args:
        user: Користувач
        threshold_minutes: Поріг в хвилинах

    Returns:
        bool - True якщо користувач був активний протягом threshold_minutes
    """
    today = timezone.now().date()

    try:
        record = ManagementDailyActivity.objects.get(user=user, date=today)
        if record.last_seen_at:
            time_since_last_seen = timezone.now() - record.last_seen_at
            return time_since_last_seen.total_seconds() < (threshold_minutes * 60)
    except ManagementDailyActivity.DoesNotExist:
        pass

    return False
