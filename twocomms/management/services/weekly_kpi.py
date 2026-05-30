"""
Сервіс для розрахунку тижневого KPI та ставки менеджерів
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q, Count
from django.utils import timezone

from management.models import Client, WeeklySalaryAccrual, ManagerLevel
from management.services.visible_points import CONVERSION_RESULTS


TWO_PLACES = Decimal('0.01')


def get_week_boundaries(target_date=None) -> tuple[date, date]:
    """
    Отримати межі тижня (понеділок-неділя) для заданої дати

    Args:
        target_date: Дата для якої шукати тиждень (якщо None, то сьогодні)

    Returns:
        (week_start, week_end) - понеділок та неділя
    """
    if target_date is None:
        target_date = timezone.now().date()

    # ISO календар: понеділок = 1, неділя = 7
    weekday = target_date.isoweekday()

    # Початок тижня (понеділок)
    week_start = target_date - timedelta(days=weekday - 1)

    # Кінець тижня (неділя)
    week_end = week_start + timedelta(days=6)

    return week_start, week_end


def get_user_week_start(user, target_date=None) -> date:
    """
    Отримати початок тижня для користувача з урахуванням salary_start_date

    Якщо менеджер почав роботу не з понеділка, його перший тиждень
    буде неповним і почнеться з salary_start_date

    Args:
        user: Користувач
        target_date: Дата для якої шукати тиждень

    Returns:
        Початок тижня для цього користувача
    """
    if target_date is None:
        target_date = timezone.now().date()

    try:
        level = user.manager_level
        salary_start = level.salary_start_date
    except (ManagerLevel.DoesNotExist, AttributeError):
        salary_start = None

    week_start, week_end = get_week_boundaries(target_date)

    # Якщо salary_start_date в межах цього тижня і пізніше за понеділок,
    # то тиждень починається з salary_start_date
    if salary_start and week_start <= salary_start <= week_end:
        return salary_start

    return week_start


def calculate_weekly_conversions(user, week_start: date, week_end: date) -> int:
    """
    Підрахувати кількість конверсій за тиждень

    Конверсія = call_result in {ORDER, TEST_BATCH}

    Args:
        user: Користувач
        week_start: Початок тижня
        week_end: Кінець тижня

    Returns:
        Кількість конверсій
    """
    # Конвертувати дати в datetime для порівняння з created_at
    week_start_dt = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
    week_end_dt = timezone.make_aware(datetime.combine(week_end, datetime.max.time()))

    conversions = Client.objects.filter(
        owner=user,
        created_at__gte=week_start_dt,
        created_at__lte=week_end_dt,
        call_result__in=CONVERSION_RESULTS,
    ).count()

    return conversions


def calculate_weekly_processed_clients(user, week_start: date, week_end: date) -> int:
    """
    Підрахувати кількість оброблених клієнтів за тиждень

    Args:
        user: Користувач
        week_start: Початок тижня
        week_end: Кінець тижня

    Returns:
        Кількість оброблених клієнтів
    """
    week_start_dt = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
    week_end_dt = timezone.make_aware(datetime.combine(week_end, datetime.max.time()))

    processed = Client.objects.filter(
        owner=user,
        created_at__gte=week_start_dt,
        created_at__lte=week_end_dt,
    ).count()

    return processed


def calculate_kpi_multiplier(conversions: int) -> Decimal:
    """
    Розрахувати KPI множник на основі кількості конверсій

    Логіка:
    - 2+ конверсії = 1.0 (100% ставки)
    - 1 конверсія = 0.5 (50% ставки)
    - 0 конверсій = 0.0 (0% ставки)

    Args:
        conversions: Кількість конверсій

    Returns:
        Множник (0.0, 0.5 або 1.0)
    """
    if conversions >= 2:
        return Decimal('1.0')
    elif conversions == 1:
        return Decimal('0.5')
    else:
        return Decimal('0.0')


def calculate_weekly_salary(user, week_start: date, week_end: date) -> dict:
    """
    Розрахувати тижневу ставку для користувача

    Args:
        user: Користувач
        week_start: Початок тижня
        week_end: Кінець тижня

    Returns:
        dict з полями:
        - base_salary: Базова ставка
        - conversions: Кількість конверсій
        - processed_clients: Кількість оброблених клієнтів
        - kpi_multiplier: KPI множник
        - accrued_amount: Нарахована сума
        - kpi_status: Статус KPI ('excellent', 'good', 'poor', 'failed')
    """
    try:
        level = user.manager_level
        base_salary = Decimal(str(level.weekly_salary_uah))
    except (ManagerLevel.DoesNotExist, AttributeError):
        return {
            'base_salary': Decimal('0'),
            'conversions': 0,
            'processed_clients': 0,
            'kpi_multiplier': Decimal('0'),
            'accrued_amount': Decimal('0'),
            'kpi_status': 'no_level',
        }

    # Якщо рівень Candidate, ставка не нараховується
    if level.level == ManagerLevel.Level.CANDIDATE:
        conversions = calculate_weekly_conversions(user, week_start, week_end)
        processed_clients = calculate_weekly_processed_clients(user, week_start, week_end)

        return {
            'base_salary': Decimal('0'),
            'conversions': conversions,
            'processed_clients': processed_clients,
            'kpi_multiplier': Decimal('0'),
            'accrued_amount': Decimal('0'),
            'kpi_status': 'candidate',
        }

    # Підрахувати метрики
    conversions = calculate_weekly_conversions(user, week_start, week_end)
    processed_clients = calculate_weekly_processed_clients(user, week_start, week_end)

    # Розрахувати множник
    kpi_multiplier = calculate_kpi_multiplier(conversions)

    # Розрахувати нараховану суму
    accrued_amount = (base_salary * kpi_multiplier).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Визначити статус KPI
    if conversions >= 5:
        kpi_status = 'excellent'  # Перевиконання
    elif conversions >= 2:
        kpi_status = 'good'  # Виконано
    elif conversions == 1:
        kpi_status = 'poor'  # Частково виконано
    else:
        kpi_status = 'failed'  # Не виконано

    return {
        'base_salary': base_salary,
        'conversions': conversions,
        'processed_clients': processed_clients,
        'kpi_multiplier': kpi_multiplier,
        'accrued_amount': accrued_amount,
        'kpi_status': kpi_status,
    }


def accrue_weekly_salary(user, week_start: date, week_end: date) -> WeeklySalaryAccrual:
    """
    Нарахувати тижневу ставку (створити запис WeeklySalaryAccrual)

    Args:
        user: Користувач
        week_start: Початок тижня
        week_end: Кінець тижня

    Returns:
        WeeklySalaryAccrual instance
    """
    # Перевірити, чи вже є нарахування за цей тиждень
    existing = WeeklySalaryAccrual.objects.filter(
        user=user,
        week_start=week_start,
    ).first()

    if existing:
        return existing

    # Розрахувати ставку
    salary_data = calculate_weekly_salary(user, week_start, week_end)

    # Заморозити на 7 днів після кінця тижня
    frozen_until = timezone.make_aware(
        datetime.combine(week_end + timedelta(days=7), datetime.max.time())
    )

    # Створити нарахування
    accrual = WeeklySalaryAccrual.objects.create(
        user=user,
        week_start=week_start,
        week_end=week_end,
        conversions_count=salary_data['conversions'],
        processed_clients_count=salary_data['processed_clients'],
        base_weekly_salary=salary_data['base_salary'],
        kpi_multiplier=salary_data['kpi_multiplier'],
        accrued_amount=salary_data['accrued_amount'],
        status=WeeklySalaryAccrual.Status.ACCRUED,
        frozen_until=frozen_until,
    )

    return accrual


def get_current_week_kpi_status(user) -> dict:
    """
    Отримати статус KPI для поточного тижня

    Returns:
        dict з полями:
        - week_start: Початок тижня
        - week_end: Кінець тижня
        - conversions: Кількість конверсій
        - conversions_target: Ціль (2)
        - conversions_progress_pct: Прогрес у відсотках
        - processed_clients: Кількість оброблених клієнтів
        - kpi_multiplier: Поточний множник
        - projected_salary: Прогнозована ставка
        - kpi_status: Статус
        - days_remaining: Днів до кінця тижня
    """
    today = timezone.now().date()
    week_start, week_end = get_week_boundaries(today)

    salary_data = calculate_weekly_salary(user, week_start, week_end)

    # Прогрес до цілі (2 конверсії)
    conversions_target = 2
    conversions_progress_pct = min(100, int(salary_data['conversions'] / conversions_target * 100))

    # Днів до кінця тижня
    days_remaining = (week_end - today).days

    return {
        'week_start': week_start,
        'week_end': week_end,
        'conversions': salary_data['conversions'],
        'conversions_target': conversions_target,
        'conversions_progress_pct': conversions_progress_pct,
        'processed_clients': salary_data['processed_clients'],
        'kpi_multiplier': salary_data['kpi_multiplier'],
        'projected_salary': salary_data['accrued_amount'],
        'base_salary': salary_data['base_salary'],
        'kpi_status': salary_data['kpi_status'],
        'days_remaining': days_remaining,
    }


def get_weekly_kpi_history(user, weeks: int = 4) -> list[dict]:
    """
    Отримати історію KPI за останні N тижнів

    Args:
        user: Користувач
        weeks: Кількість тижнів

    Returns:
        Список dict з даними по тижнях
    """
    history = []
    today = timezone.now().date()

    for i in range(weeks):
        # Тиждень назад
        target_date = today - timedelta(weeks=i)
        week_start, week_end = get_week_boundaries(target_date)

        # Спробувати знайти існуюче нарахування
        accrual = WeeklySalaryAccrual.objects.filter(
            user=user,
            week_start=week_start,
        ).first()

        if accrual:
            history.append({
                'week_start': accrual.week_start,
                'week_end': accrual.week_end,
                'conversions': accrual.conversions_count,
                'processed_clients': accrual.processed_clients_count,
                'kpi_multiplier': accrual.kpi_multiplier,
                'accrued_amount': accrual.accrued_amount,
                'status': accrual.status,
            })
        else:
            # Розрахувати на льоту
            salary_data = calculate_weekly_salary(user, week_start, week_end)
            history.append({
                'week_start': week_start,
                'week_end': week_end,
                'conversions': salary_data['conversions'],
                'processed_clients': salary_data['processed_clients'],
                'kpi_multiplier': salary_data['kpi_multiplier'],
                'accrued_amount': salary_data['accrued_amount'],
                'status': 'not_accrued',
            })

    return history
