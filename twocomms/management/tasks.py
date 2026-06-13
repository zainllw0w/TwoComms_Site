"""
Celery задачі для системи рівнів менеджерів
"""
from datetime import timedelta

try:
    from celery import shared_task
except ImportError:  # Celery удалён с хостинга — задачи запускаются из cron
    def shared_task(*args, **kwargs):
        def decorator(func):
            func.delay = func
            return func
        if args and callable(args[0]):
            return decorator(args[0])
        return decorator
from django.contrib.auth import get_user_model
from django.utils import timezone

from management.models import ManagerLevel
from management.services.weekly_kpi import accrue_weekly_salary, get_week_boundaries
from management.services.level_progression import check_auto_promotion_conditions

User = get_user_model()


@shared_task
def accrue_weekly_salaries():
    """
    Нараховує тижневі ставки всім менеджерам Level 1+
    Запускається щопонеділка о 00:01
    Нараховує за попередній тиждень (понеділок-неділя)
    """
    # Попередній тиждень
    today = timezone.now().date()
    last_week_date = today - timedelta(days=7)
    week_start, week_end = get_week_boundaries(last_week_date)

    # Знайти всіх активних менеджерів Level 1+
    managers = User.objects.filter(
        manager_level__is_active=True,
        manager_level__level__in=[
            ManagerLevel.Level.LEVEL_1,
            ManagerLevel.Level.LEVEL_2,
            ManagerLevel.Level.TOP_MANAGER,
            ManagerLevel.Level.PROJECT_MANAGER,
            ManagerLevel.Level.ADMIN,
        ]
    ).select_related('manager_level')

    accrued_count = 0
    for user in managers:
        try:
            # Перевірити, чи salary_start_date <= week_end
            level = user.manager_level
            if level.salary_start_date and level.salary_start_date > week_end:
                continue  # Ще не почав працювати в цьому тижні

            # Нарахувати ставку
            accrue_weekly_salary(user, week_start, week_end)
            accrued_count += 1
        except Exception as e:
            print(f"Error accruing salary for {user.username}: {e}")

    return f"Accrued weekly salaries for {accrued_count} managers"


@shared_task
def check_auto_promotions():
    """
    Перевіряє умови автоматичного підвищення для Candidate та Level 1
    Запускається щодня о 01:00
    """
    # Знайти всіх кандидатів та менеджерів 1-го рівня
    managers = User.objects.filter(
        manager_level__is_active=True,
        manager_level__level__in=[
            ManagerLevel.Level.CANDIDATE,
            ManagerLevel.Level.LEVEL_1,
        ]
    ).select_related('manager_level')

    eligible_count = 0
    for user in managers:
        try:
            can_promote, reason = check_auto_promotion_conditions(user)
            if can_promote:
                eligible_count += 1
                # TODO: Відправити уведомлення адміністратору
                print(f"User {user.username} is eligible for promotion: {reason}")
        except Exception as e:
            print(f"Error checking promotion for {user.username}: {e}")

    return f"Found {eligible_count} managers eligible for promotion"
