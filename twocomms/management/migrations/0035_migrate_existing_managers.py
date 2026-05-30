# Data migration to migrate existing managers to new level system
from django.db import migrations
from decimal import Decimal


def migrate_existing_managers(apps, schema_editor):
    """
    Міграція існуючих менеджерів на нову систему рівнів

    Логіка:
    - Якщо is_manager=True → створити ManagerLevel з рівнем 'level_1'
    - Перенести manager_base_salary_uah → weekly_salary_uah
    - Перенести manager_commission_percent → commission_percent
    - Перенести manager_started_at → salary_start_date
    """
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('accounts', 'UserProfile')
    ManagerLevel = apps.get_model('management', 'ManagerLevel')

    # Знайти всіх користувачів з is_manager=True
    profiles = UserProfile.objects.filter(is_manager=True).select_related('user')

    migrated_count = 0
    for profile in profiles:
        user = profile.user

        # Перевірити, чи вже є рівень
        if hasattr(user, 'manager_level'):
            continue

        # Створити рівень
        try:
            ManagerLevel.objects.create(
                user=user,
                level='level_1',  # За замовчуванням Level 1 для існуючих менеджерів
                assigned_by=None,  # Немає інформації хто призначив
                weekly_salary_uah=profile.manager_base_salary_uah or 0,
                commission_percent=profile.manager_commission_percent or Decimal('0'),
                salary_start_date=profile.manager_started_at,
                assignment_comment='Автоматично мігровано з старої системи',
                is_active=True,
            )
            migrated_count += 1
        except Exception as e:
            print(f"Error migrating user {user.username}: {e}")

    print(f"Migrated {migrated_count} existing managers to new level system")


def reverse_migration(apps, schema_editor):
    """
    Зворотня міграція - видалити всі автоматично створені рівні
    """
    ManagerLevel = apps.get_model('management', 'ManagerLevel')

    # Видалити всі рівні з коментарем про автоматичну міграцію
    deleted_count = ManagerLevel.objects.filter(
        assignment_comment='Автоматично мігровано з старої системи'
    ).delete()[0]

    print(f"Deleted {deleted_count} auto-migrated manager levels")


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0034_add_manager_levels'),
        ('accounts', '0001_initial'),  # Залежність від accounts app
    ]

    operations = [
        migrations.RunPython(migrate_existing_managers, reverse_migration),
    ]
