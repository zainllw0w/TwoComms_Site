"""
Сервіс для відстеження прогресу менеджера до наступного рівня
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from management.models import Client, ManagerLevel
from management.services.visible_points import CONVERSION_RESULTS
from management.services.manager_levels import get_current_level, LEVEL_HIERARCHY


# Умови переходу між рівнями
PROMOTION_CONDITIONS = {
    ManagerLevel.Level.CANDIDATE: {
        'next_level': ManagerLevel.Level.LEVEL_1,
        'auto_check': True,
        'conditions': {
            'type': 'or',
            'options': [
                {'type': 'conversions', 'min': 2, 'period': 'all_time'},
                {'type': 'processed_clients', 'min': 100, 'period': 'all_time'},
            ],
        },
        'description': '2 конверсії АБО 100 оброблених клієнтів',
    },
    ManagerLevel.Level.LEVEL_1: {
        'next_level': ManagerLevel.Level.LEVEL_2,
        'auto_check': True,
        'conditions': {
            'type': 'and',
            'options': [
                {'type': 'work_duration_days', 'min': 30},
                {
                    'type': 'or',
                    'options': [
                        {'type': 'conversions', 'min': 4, 'period': 'all_time'},
                        {'type': 'processed_clients', 'min': 500, 'period': 'all_time'},
                    ],
                },
            ],
        },
        'description': '1 місяць роботи І (4 конверсії АБО 500 оброблених)',
    },
    ManagerLevel.Level.LEVEL_2: {
        'next_level': ManagerLevel.Level.TOP_MANAGER,
        'auto_check': False,
        'description': 'Призначається адміністратором вручну',
    },
    ManagerLevel.Level.TOP_MANAGER: {
        'next_level': ManagerLevel.Level.PROJECT_MANAGER,
        'auto_check': False,
        'description': 'Призначається адміністратором вручну',
    },
    ManagerLevel.Level.PROJECT_MANAGER: {
        'next_level': ManagerLevel.Level.ADMIN,
        'auto_check': False,
        'description': 'Призначається адміністратором вручну',
    },
}


def get_next_level_requirements(current_level: str) -> dict:
    """Отримати вимоги для переходу на наступний рівень"""
    return PROMOTION_CONDITIONS.get(current_level, {})


def calculate_user_metrics(user) -> dict:
    """
    Розрахувати метрики користувача

    Returns:
        dict з полями:
        - total_conversions: Загальна кількість конверсій
        - total_processed_clients: Загальна кількість оброблених клієнтів
        - work_duration_days: Кількість днів роботи
    """
    level = get_current_level(user)

    # Конверсії
    total_conversions = Client.objects.filter(
        owner=user,
        call_result__in=CONVERSION_RESULTS,
    ).count()

    # Оброблені клієнти
    total_processed_clients = Client.objects.filter(owner=user).count()

    # Тривалість роботи
    work_duration_days = 0
    if level and level.salary_start_date:
        work_duration_days = (timezone.now().date() - level.salary_start_date).days

    return {
        'total_conversions': total_conversions,
        'total_processed_clients': total_processed_clients,
        'work_duration_days': work_duration_days,
    }


def check_condition(condition: dict, metrics: dict) -> tuple[bool, int, int]:
    """
    Перевірити одну умову

    Returns:
        (is_met, current_value, target_value)
    """
    cond_type = condition.get('type')

    if cond_type == 'conversions':
        current = metrics['total_conversions']
        target = condition['min']
        return current >= target, current, target

    elif cond_type == 'processed_clients':
        current = metrics['total_processed_clients']
        target = condition['min']
        return current >= target, current, target

    elif cond_type == 'work_duration_days':
        current = metrics['work_duration_days']
        target = condition['min']
        return current >= target, current, target

    elif cond_type == 'or':
        # Хоча б одна з умов виконана
        for opt in condition.get('options', []):
            is_met, _, _ = check_condition(opt, metrics)
            if is_met:
                return True, 1, 1
        return False, 0, 1

    elif cond_type == 'and':
        # Всі умови виконані
        for opt in condition.get('options', []):
            is_met, _, _ = check_condition(opt, metrics)
            if not is_met:
                return False, 0, 1
        return True, 1, 1

    return False, 0, 1


def check_auto_promotion_conditions(user) -> tuple[bool, str]:
    """
    Перевірити умови автоматичного підвищення

    Returns:
        (can_promote, reason)
    """
    level = get_current_level(user)
    if not level:
        return False, "Немає рівня"

    requirements = get_next_level_requirements(level.level)
    if not requirements:
        return False, "Немає наступного рівня"

    if not requirements.get('auto_check'):
        return False, "Підвищення тільки вручну"

    metrics = calculate_user_metrics(user)
    conditions = requirements.get('conditions', {})

    is_met, _, _ = check_condition(conditions, metrics)

    if is_met:
        return True, f"Умови виконано: {requirements['description']}"
    else:
        return False, f"Умови не виконано: {requirements['description']}"


def get_progression_status(user) -> dict:
    """
    Отримати статус прогресу до наступного рівня

    Returns:
        dict з полями:
        - current_level: Поточний рівень
        - next_level: Наступний рівень
        - can_auto_promote: Чи можна автоматично підвищити
        - requirements_met: Чи виконані вимоги
        - progress_pct: Прогрес у відсотках
        - conditions: Список умов з статусами
        - description: Опис вимог
    """
    level = get_current_level(user)

    if not level:
        return {
            'current_level': None,
            'next_level': None,
            'can_auto_promote': False,
            'requirements_met': False,
            'progress_pct': 0,
            'conditions': [],
            'description': 'Немає рівня',
        }

    requirements = get_next_level_requirements(level.level)

    if not requirements:
        return {
            'current_level': level.level,
            'next_level': None,
            'can_auto_promote': False,
            'requirements_met': True,
            'progress_pct': 100,
            'conditions': [],
            'description': 'Максимальний рівень',
        }

    metrics = calculate_user_metrics(user)
    conditions_data = requirements.get('conditions', {})

    # Розібрати умови
    conditions_list = parse_conditions_for_display(conditions_data, metrics)

    # Перевірити загальний статус
    can_promote, reason = check_auto_promotion_conditions(user)

    # Розрахувати прогрес
    progress_pct = calculate_progress_percentage(conditions_list)

    return {
        'current_level': level.level,
        'next_level': requirements.get('next_level'),
        'can_auto_promote': requirements.get('auto_check', False),
        'requirements_met': can_promote,
        'progress_pct': progress_pct,
        'conditions': conditions_list,
        'description': requirements.get('description', ''),
    }


def parse_conditions_for_display(conditions: dict, metrics: dict) -> list[dict]:
    """
    Розібрати умови для відображення в UI

    Returns:
        Список dict з полями:
        - type: Тип умови
        - description: Опис
        - is_met: Чи виконана
        - current: Поточне значення
        - target: Цільове значення
        - progress_pct: Прогрес у відсотках
    """
    result = []

    cond_type = conditions.get('type')

    if cond_type == 'conversions':
        current = metrics['total_conversions']
        target = conditions['min']
        is_met = current >= target
        progress_pct = min(100, int(current / target * 100)) if target > 0 else 0

        result.append({
            'type': 'conversions',
            'description': f'{target} конверсій',
            'is_met': is_met,
            'current': current,
            'target': target,
            'progress_pct': progress_pct,
        })

    elif cond_type == 'processed_clients':
        current = metrics['total_processed_clients']
        target = conditions['min']
        is_met = current >= target
        progress_pct = min(100, int(current / target * 100)) if target > 0 else 0

        result.append({
            'type': 'processed_clients',
            'description': f'{target} оброблених клієнтів',
            'is_met': is_met,
            'current': current,
            'target': target,
            'progress_pct': progress_pct,
        })

    elif cond_type == 'work_duration_days':
        current = metrics['work_duration_days']
        target = conditions['min']
        is_met = current >= target
        progress_pct = min(100, int(current / target * 100)) if target > 0 else 0

        result.append({
            'type': 'work_duration_days',
            'description': f'{target} днів роботи',
            'is_met': is_met,
            'current': current,
            'target': target,
            'progress_pct': progress_pct,
        })

    elif cond_type in ['or', 'and']:
        for opt in conditions.get('options', []):
            result.extend(parse_conditions_for_display(opt, metrics))

    return result


def calculate_progress_percentage(conditions_list: list[dict]) -> int:
    """Розрахувати загальний прогрес у відсотках"""
    if not conditions_list:
        return 0

    total_progress = sum(c['progress_pct'] for c in conditions_list)
    return min(100, int(total_progress / len(conditions_list)))


def get_unlocked_features(level: str) -> list[dict]:
    """Отримати список розблокованих функцій для рівня"""
    from management.services.manager_levels import get_level_description

    desc = get_level_description(level)
    features = desc.get('unlocked_features', [])

    return [{'name': f, 'icon': '✓'} for f in features]


def get_locked_features(level: str) -> list[dict]:
    """Отримати список заблокованих функцій для рівня"""
    from management.services.manager_levels import get_level_description

    desc = get_level_description(level)
    features = desc.get('locked_features', [])

    return [{'name': f, 'icon': '🔒'} for f in features]
