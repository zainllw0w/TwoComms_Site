"""
Сервіс для роботи з рівнями менеджерів
"""
from decimal import Decimal
from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from management.models import ManagerLevel, ManagerLevelHistory

User = get_user_model()


# Права доступу по рівнях
LEVEL_PERMISSIONS = {
    ManagerLevel.Level.CANDIDATE: {
        'can_view_payouts': False,
        'can_process_bases': False,
        'can_run_parsing': False,
        'can_approve_bases': False,
        'can_view_sensitive_data': False,
        'can_manage_managers': False,
        'can_view_system_settings': False,
    },
    ManagerLevel.Level.LEVEL_1: {
        'can_view_payouts': True,
        'can_process_bases': False,
        'can_run_parsing': False,
        'can_approve_bases': False,
        'can_view_sensitive_data': False,
        'can_manage_managers': False,
        'can_view_system_settings': False,
    },
    ManagerLevel.Level.LEVEL_2: {
        'can_view_payouts': True,
        'can_process_bases': True,
        'can_run_parsing': False,
        'can_approve_bases': False,
        'can_view_sensitive_data': True,
        'can_manage_managers': False,
        'can_view_system_settings': False,
    },
    ManagerLevel.Level.TOP_MANAGER: {
        'can_view_payouts': True,
        'can_process_bases': True,
        'can_run_parsing': True,
        'can_approve_bases': True,
        'can_view_sensitive_data': True,
        'can_manage_managers': True,
        'can_view_system_settings': False,
    },
    ManagerLevel.Level.PROJECT_MANAGER: {
        'can_view_payouts': True,
        'can_process_bases': True,
        'can_run_parsing': True,
        'can_approve_bases': True,
        'can_view_sensitive_data': True,
        'can_manage_managers': True,
        'can_view_system_settings': True,
    },
    ManagerLevel.Level.ADMIN: {
        'can_view_payouts': True,
        'can_process_bases': True,
        'can_run_parsing': True,
        'can_approve_bases': True,
        'can_view_sensitive_data': True,
        'can_manage_managers': True,
        'can_view_system_settings': True,
        'is_admin': True,
    },
}


# Ієрархія рівнів (для порівняння)
LEVEL_HIERARCHY = {
    ManagerLevel.Level.CANDIDATE: 0,
    ManagerLevel.Level.LEVEL_1: 1,
    ManagerLevel.Level.LEVEL_2: 2,
    ManagerLevel.Level.TOP_MANAGER: 3,
    ManagerLevel.Level.PROJECT_MANAGER: 4,
    ManagerLevel.Level.ADMIN: 5,
}


def get_current_level(user) -> Optional[ManagerLevel]:
    """Отримати поточний рівень менеджера.

    Якщо у staff/superuser немає явного запису ManagerLevel — повертаємо
    віртуальний (незбережений) рівень «Адміністратор», щоб адміністрація
    бачила свій профіль як найвищий ранг без потреби створювати запис вручну.
    """
    try:
        return user.manager_level
    except ManagerLevel.DoesNotExist:
        if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
            return _build_virtual_admin_level(user)
        return None


def _build_virtual_admin_level(user) -> ManagerLevel:
    """Віртуальний рівень ADMIN для staff/superuser без запису в БД (не зберігається)."""
    return ManagerLevel(
        user=user,
        level=ManagerLevel.Level.ADMIN,
        weekly_salary_uah=0,
        commission_percent=Decimal('0'),
        salary_start_date=None,
        assignment_comment='Системний рівень адміністратора',
        is_active=True,
    )


def get_level_display_name(level: str) -> str:
    """Отримати відображувану назву рівня"""
    return dict(ManagerLevel.Level.choices).get(level, level)


def get_level_permissions(level: str) -> dict:
    """Отримати права доступу для рівня"""
    return LEVEL_PERMISSIONS.get(level, {})


def has_permission(user, permission: str) -> bool:
    """Перевірити, чи має користувач певне право"""
    # Суперюзери та staff мають всі права
    if user.is_superuser or user.is_staff:
        return True

    level = get_current_level(user)
    if not level or not level.is_active:
        return False

    permissions = get_level_permissions(level.level)
    return permissions.get(permission, False)


def has_required_level(current_level: str, required_level: str) -> bool:
    """Перевірити, чи достатній поточний рівень"""
    current_rank = LEVEL_HIERARCHY.get(current_level, -1)
    required_rank = LEVEL_HIERARCHY.get(required_level, 999)
    return current_rank >= required_rank


def can_promote_to_level(user, target_level: str) -> tuple[bool, str]:
    """
    Перевірити, чи можна підвищити користувача до цільового рівня

    Returns:
        (can_promote, reason)
    """
    current_level = get_current_level(user)

    if not current_level:
        # Якщо немає рівня, можна призначити будь-який
        return True, ""

    current_rank = LEVEL_HIERARCHY.get(current_level.level, -1)
    target_rank = LEVEL_HIERARCHY.get(target_level, -1)

    if target_rank < current_rank:
        return True, "Пониження рівня"

    if target_rank == current_rank:
        return True, "Оновлення умов на поточному рівні"

    # Підвищення - завжди можливе, але може потребувати виконання умов
    return True, "Підвищення рівня"


@transaction.atomic
def promote_manager(
    user,
    new_level: str,
    promoted_by,
    weekly_salary: int = 0,
    commission_percent: Decimal = Decimal('0'),
    start_date=None,
    comment: str = "",
) -> ManagerLevel:
    """
    Призначити або змінити рівень менеджера

    Args:
        user: Користувач
        new_level: Новий рівень (з ManagerLevel.Level)
        promoted_by: Хто призначив
        weekly_salary: Тижнева ставка в грн
        commission_percent: Відсоток від замовлення
        start_date: Дата початку нарахувань (якщо None, то сьогодні)
        comment: Коментар

    Returns:
        ManagerLevel instance
    """
    if start_date is None:
        start_date = timezone.now().date()

    # Отримати старий рівень
    try:
        old_level_obj = user.manager_level
        old_level = old_level_obj.level
        old_weekly_salary = old_level_obj.weekly_salary_uah
        old_commission_percent = old_level_obj.commission_percent

        # Оновити існуючий рівень
        old_level_obj.level = new_level
        old_level_obj.weekly_salary_uah = weekly_salary
        old_level_obj.commission_percent = commission_percent
        old_level_obj.salary_start_date = start_date
        old_level_obj.assignment_comment = comment
        old_level_obj.assigned_by = promoted_by
        old_level_obj.assigned_at = timezone.now()
        old_level_obj.is_active = True
        old_level_obj.save()

        level_obj = old_level_obj

    except ManagerLevel.DoesNotExist:
        # Створити новий рівень
        old_level = None
        old_weekly_salary = 0
        old_commission_percent = Decimal('0')

        level_obj = ManagerLevel.objects.create(
            user=user,
            level=new_level,
            assigned_by=promoted_by,
            weekly_salary_uah=weekly_salary,
            commission_percent=commission_percent,
            salary_start_date=start_date,
            assignment_comment=comment,
            is_active=True,
        )

    # Записати в історію
    ManagerLevelHistory.objects.create(
        user=user,
        old_level=old_level,
        new_level=new_level,
        changed_by=promoted_by,
        old_weekly_salary=old_weekly_salary,
        new_weekly_salary=weekly_salary,
        old_commission_percent=old_commission_percent,
        new_commission_percent=commission_percent,
        reason=comment,
    )

    # Оновити старі поля в UserProfile для зворотної сумісності
    try:
        profile = user.userprofile
        profile.manager_position = get_level_display_name(new_level)
        profile.manager_base_salary_uah = weekly_salary
        profile.manager_commission_percent = commission_percent
        profile.manager_started_at = start_date
        profile.save(update_fields=[
            'manager_position',
            'manager_base_salary_uah',
            'manager_commission_percent',
            'manager_started_at',
        ])
    except Exception:
        pass  # UserProfile може не існувати

    return level_obj


@transaction.atomic
def demote_manager(user, reason: str, demoted_by) -> None:
    """
    Деактивувати менеджера (звільнення)

    Args:
        user: Користувач
        reason: Причина звільнення
        demoted_by: Хто звільнив
    """
    try:
        level_obj = user.manager_level
        old_level = level_obj.level
        old_weekly_salary = level_obj.weekly_salary_uah
        old_commission_percent = level_obj.commission_percent

        # Деактивувати рівень
        level_obj.is_active = False
        level_obj.save()

        # Записати в історію
        ManagerLevelHistory.objects.create(
            user=user,
            old_level=old_level,
            new_level=None,
            changed_by=demoted_by,
            old_weekly_salary=old_weekly_salary,
            new_weekly_salary=0,
            old_commission_percent=old_commission_percent,
            new_commission_percent=Decimal('0'),
            reason=f"Звільнення: {reason}",
        )

        # Оновити UserProfile
        try:
            profile = user.userprofile
            profile.is_manager = False
            profile.save(update_fields=['is_manager'])
        except Exception:
            pass

    except ManagerLevel.DoesNotExist:
        pass  # Немає рівня - нічого робити


def get_level_description(level: str) -> dict:
    """Отримати опис рівня з доступними функціями"""
    descriptions = {
        ManagerLevel.Level.CANDIDATE: {
            'name': 'Менеджер-кандидат',
            'description': 'Стартовий рівень для перевірки перед повноцінною роботою',
            'unlocked_features': [
                'Додавання клієнтів',
                'Обробка клієнтів',
                'Статистика',
                'Уведомлення',
                'Підключення Telegram',
            ],
            'locked_features': [
                'Виплати (доступні з рівня «Менеджер 1-го рівня»)',
                'Обробка баз (доступна з рівня «Менеджер 2-го рівня»)',
                'Парсинг (доступний з рівня «Топ-менеджер»)',
            ],
        },
        ManagerLevel.Level.LEVEL_1: {
            'name': 'Менеджер 1-го рівня',
            'description': 'Повноцінний менеджер з доступом до виплат',
            'unlocked_features': [
                'Всі функції Менеджера-кандидата',
                'Виплати та нарахування',
                'Тижнева ставка',
                'Відсоток від замовлення',
                'Тижневий KPI',
            ],
            'locked_features': [
                'Обробка баз (доступна з рівня «Менеджер 2-го рівня»)',
                'Парсинг (доступний з рівня «Топ-менеджер»)',
            ],
        },
        ManagerLevel.Level.LEVEL_2: {
            'name': 'Менеджер 2-го рівня',
            'description': 'Менеджер з доступом до обробки готових баз',
            'unlocked_features': [
                'Всі функції Менеджера 1-го рівня',
                'Обробка одобрених баз',
                'Доступ до контактів у базах',
                'Перегляд чутливих даних',
            ],
            'locked_features': [
                'Парсинг (доступний з рівня «Топ-менеджер»)',
                'Одобрення баз (доступне з рівня «Топ-менеджер»)',
            ],
        },
        ManagerLevel.Level.TOP_MANAGER: {
            'name': 'Топ-менеджер',
            'description': 'Контроль менеджерів та робота з парсингом',
            'unlocked_features': [
                'Всі функції Менеджера 2-го рівня',
                'Парсинг',
                'Одобрення/відхилення баз',
                'Контроль менеджерів 1-го та 2-го рівня',
                'Розширена статистика',
                'Перевірка якості роботи',
            ],
            'locked_features': [],
        },
        ManagerLevel.Level.PROJECT_MANAGER: {
            'name': 'Project-менеджер',
            'description': 'Помощник владельца, контроль всієї системи',
            'unlocked_features': [
                'Всі функції Топ-менеджера',
                'Контроль топ-менеджерів',
                'Системні налаштування',
                'Email-розсилки',
                'Операційні процеси',
                'Загальна аналітика',
            ],
            'locked_features': [],
        },
        ManagerLevel.Level.ADMIN: {
            'name': 'Адміністратор',
            'description': 'Повний доступ до всього функціоналу',
            'unlocked_features': [
                'Повний доступ до всіх функцій',
                'Управління рівнями',
                'Управління виплатами',
                'Ручні корректировки',
                'Налаштування системи',
            ],
            'locked_features': [],
        },
    }

    return descriptions.get(level, {
        'name': level,
        'description': '',
        'unlocked_features': [],
        'locked_features': [],
    })
