#!/usr/bin/env python
"""
Скрипт для тестування системи рівнів менеджерів

Використання:
    python test_manager_levels.py
"""

import os
import sys
import django

# Налаштування Django
sys.path.insert(0, '/Users/zainllw0w/TwoComms/site/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone

from management.models import ManagerLevel, Client
from management.services.manager_levels import (
    get_current_level,
    promote_manager,
    get_level_permissions,
    has_permission,
)
from management.services.weekly_kpi import (
    get_current_week_kpi_status,
    calculate_weekly_salary,
    get_week_boundaries,
)
from management.services.level_progression import (
    get_progression_status,
    check_auto_promotion_conditions,
)

User = get_user_model()


def print_header(text):
    """Красиво вивести заголовок"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_success(text):
    """Вивести успішне повідомлення"""
    print(f"✅ {text}")


def print_error(text):
    """Вивести помилку"""
    print(f"❌ {text}")


def print_info(text):
    """Вивести інформацію"""
    print(f"ℹ️  {text}")


def test_models():
    """Тест 1: Перевірка моделей"""
    print_header("Тест 1: Перевірка моделей")

    try:
        # Перевірити, чи існують таблиці
        count = ManagerLevel.objects.count()
        print_success(f"Таблиця ManagerLevel існує ({count} записів)")

        from management.models import ManagerLevelHistory, WeeklySalaryAccrual
        count_history = ManagerLevelHistory.objects.count()
        count_salary = WeeklySalaryAccrual.objects.count()

        print_success(f"Таблиця ManagerLevelHistory існує ({count_history} записів)")
        print_success(f"Таблиця WeeklySalaryAccrual існує ({count_salary} записів)")

        return True
    except Exception as e:
        print_error(f"Помилка перевірки моделей: {e}")
        return False


def test_create_test_manager():
    """Тест 2: Створення тестового менеджера"""
    print_header("Тест 2: Створення тестового менеджера")

    try:
        # Знайти або створити тестового користувача
        user, created = User.objects.get_or_create(
            username='test_manager',
            defaults={
                'email': 'test@example.com',
                'first_name': 'Тест',
                'last_name': 'Менеджер',
            }
        )

        if created:
            user.set_password('test123')
            user.save()
            print_success(f"Створено тестового користувача: {user.username}")
        else:
            print_info(f"Тестовий користувач вже існує: {user.username}")

        # Створити UserProfile якщо немає
        try:
            from accounts.models import UserProfile
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={'is_manager': True}
            )
            if created:
                print_success("Створено UserProfile")
            else:
                profile.is_manager = True
                profile.save()
                print_info("Оновлено UserProfile")
        except Exception as e:
            print_info(f"UserProfile: {e}")

        return user
    except Exception as e:
        print_error(f"Помилка створення менеджера: {e}")
        return None


def test_assign_level(user):
    """Тест 3: Призначення рівня"""
    print_header("Тест 3: Призначення рівня")

    try:
        # Знайти адміна
        admin = User.objects.filter(is_staff=True).first()
        if not admin:
            admin = User.objects.filter(is_superuser=True).first()

        if not admin:
            print_error("Не знайдено адміна для призначення")
            return False

        # Призначити рівень Candidate
        level = promote_manager(
            user=user,
            new_level=ManagerLevel.Level.CANDIDATE,
            promoted_by=admin,
            weekly_salary=0,
            commission_percent=Decimal('3.0'),
            start_date=date.today(),
            comment='Тестове призначення через скрипт'
        )

        print_success(f"Призначено рівень: {level.get_level_display()}")
        print_info(f"  Ставка: {level.weekly_salary_uah} грн/тиждень")
        print_info(f"  Відсоток: {level.commission_percent}%")
        print_info(f"  Дата початку: {level.salary_start_date}")

        return True
    except Exception as e:
        print_error(f"Помилка призначення рівня: {e}")
        return False


def test_permissions(user):
    """Тест 4: Перевірка прав доступу"""
    print_header("Тест 4: Перевірка прав доступу")

    try:
        level = get_current_level(user)
        if not level:
            print_error("Рівень не знайдено")
            return False

        permissions = get_level_permissions(level.level)

        print_success(f"Рівень: {level.get_level_display()}")
        print_info("Права доступу:")
        for perm, value in permissions.items():
            status = "✅" if value else "❌"
            print(f"    {status} {perm}: {value}")

        # Перевірити конкретні права
        can_view_payouts = has_permission(user, 'can_view_payouts')
        can_run_parsing = has_permission(user, 'can_run_parsing')

        print_info(f"\nПеревірка прав:")
        print(f"    can_view_payouts: {can_view_payouts}")
        print(f"    can_run_parsing: {can_run_parsing}")

        return True
    except Exception as e:
        print_error(f"Помилка перевірки прав: {e}")
        return False


def test_kpi_calculation(user):
    """Тест 5: Розрахунок KPI"""
    print_header("Тест 5: Розрахунок KPI")

    try:
        # Отримати поточний тижневий KPI
        kpi_status = get_current_week_kpi_status(user)

        print_success("Поточний тижневий KPI:")
        print_info(f"  Тиждень: {kpi_status['week_start']} - {kpi_status['week_end']}")
        print_info(f"  Конверсії: {kpi_status['conversions']} / {kpi_status['conversions_target']}")
        print_info(f"  Оброблено клієнтів: {kpi_status['processed_clients']}")
        print_info(f"  KPI множник: {kpi_status['kpi_multiplier']}")
        print_info(f"  Прогнозована ставка: {kpi_status['projected_salary']} грн")
        print_info(f"  Статус: {kpi_status['kpi_status']}")
        print_info(f"  Днів до кінця тижня: {kpi_status['days_remaining']}")

        return True
    except Exception as e:
        print_error(f"Помилка розрахунку KPI: {e}")
        return False


def test_progression(user):
    """Тест 6: Прогрес до наступного рівня"""
    print_header("Тест 6: Прогрес до наступного рівня")

    try:
        progression = get_progression_status(user)

        print_success("Прогрес до наступного рівня:")
        print_info(f"  Поточний рівень: {progression['current_level']}")
        print_info(f"  Наступний рівень: {progression['next_level']}")
        print_info(f"  Прогрес: {progression['progress_pct']}%")
        print_info(f"  Умови виконано: {progression['requirements_met']}")
        print_info(f"  Опис: {progression['description']}")

        if progression['conditions']:
            print_info("\n  Умови:")
            for cond in progression['conditions']:
                status = "✅" if cond['is_met'] else "❌"
                print(f"    {status} {cond['description']}: {cond['current']}/{cond['target']} ({cond['progress_pct']}%)")

        # Перевірити автопідвищення
        can_promote, reason = check_auto_promotion_conditions(user)
        print_info(f"\n  Автопідвищення: {can_promote}")
        print_info(f"  Причина: {reason}")

        return True
    except Exception as e:
        print_error(f"Помилка перевірки прогресу: {e}")
        return False


def test_create_test_clients(user):
    """Тест 7: Створення тестових клієнтів"""
    print_header("Тест 7: Створення тестових клієнтів")

    try:
        # Створити 3 тестових клієнти
        for i in range(3):
            client, created = Client.objects.get_or_create(
                phone=f'+380501234{i:03d}',
                defaults={
                    'owner': user,
                    'shop_name': f'Тестовий магазин {i+1}',
                    'call_result': Client.CallResult.ORDER if i < 2 else Client.CallResult.NO_ANSWER,
                }
            )
            if created:
                print_success(f"Створено клієнта: {client.shop_name}")
            else:
                print_info(f"Клієнт вже існує: {client.shop_name}")

        # Підрахувати клієнтів
        total_clients = Client.objects.filter(owner=user).count()
        conversions = Client.objects.filter(
            owner=user,
            call_result__in=[Client.CallResult.ORDER, Client.CallResult.TEST_BATCH]
        ).count()

        print_success(f"\nВсього клієнтів: {total_clients}")
        print_success(f"Конверсій: {conversions}")

        return True
    except Exception as e:
        print_error(f"Помилка створення клієнтів: {e}")
        return False


def main():
    """Головна функція"""
    print_header("🚀 Тестування системи рівнів менеджерів")

    results = []

    # Тест 1: Моделі
    results.append(("Моделі", test_models()))

    # Тест 2: Створення менеджера
    user = test_create_test_manager()
    results.append(("Створення менеджера", user is not None))

    if user:
        # Тест 3: Призначення рівня
        results.append(("Призначення рівня", test_assign_level(user)))

        # Тест 4: Права доступу
        results.append(("Права доступу", test_permissions(user)))

        # Тест 5: KPI
        results.append(("Розрахунок KPI", test_kpi_calculation(user)))

        # Тест 6: Прогрес
        results.append(("Прогрес до рівня", test_progression(user)))

        # Тест 7: Тестові клієнти
        results.append(("Тестові клієнти", test_create_test_clients(user)))

    # Підсумок
    print_header("📊 Підсумок тестування")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\nРезультат: {passed}/{total} тестів пройдено")

    if passed == total:
        print_success("\n🎉 Всі тести пройдено успішно!")
        print_info("\nНаступні кроки:")
        print_info("1. Відкрити профіль: http://management.localhost:8000/profile/")
        print_info("2. Перевірити API: http://management.localhost:8000/api/levels/progression/")
        print_info("3. Налаштувати Celery Beat для автоматичних нарахувань")
    else:
        print_error("\n⚠️  Деякі тести не пройдено. Перевірте помилки вище.")

    return passed == total


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Тестування перервано користувачем")
        sys.exit(1)
    except Exception as e:
        print_error(f"\n\n💥 Критична помилка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
