"""Тести для Recurring Payments та Forecast — БЛОК 3."""
from decimal import Decimal
import datetime as dt

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from finance.models import Company, Account, Category, RecurrenceRule, Transaction
from finance.services import recurring, reports


class RecurringPaymentsTestCase(TestCase):
    """Тести для функціональності recurring платежів."""

    def setUp(self):
        """Створення тестових даних."""
        self.company = Company.objects.create(name='Test Company', base_currency='UAH')
        self.user = get_user_model().objects.create(username='test')

        self.account = Account.objects.create(
            company=self.company,
            name='Бізнес рахунок',
            type='bank',
            currency='UAH',
            is_business=True,
            initial_balance=Decimal('100000'),
        )

        self.category = Category.objects.create(
            company=self.company,
            name='Оренда офісу',
            type='expense',
        )

    def test_calculate_next_occurrence_monthly(self):
        """Тест розрахунку наступної дати для щомісячного правила."""
        rule = RecurrenceRule.objects.create(
            company=self.company,
            frequency='monthly',
            interval=1,
            by_month_day=15,
            start_date=dt.date(2026, 5, 15),
            template_type='expense',
            template_amount=Decimal('36000'),
            template_account=self.account,
            template_category=self.category,
        )

        # Наступна дата після 15 травня має бути 15 червня
        next_date = recurring.calculate_next_occurrence(rule, dt.date(2026, 5, 15))
        self.assertEqual(next_date, dt.date(2026, 6, 15))

        # Наступна після 15 червня має бути 15 липня
        next_date = recurring.calculate_next_occurrence(rule, dt.date(2026, 6, 15))
        self.assertEqual(next_date, dt.date(2026, 7, 15))

    def test_generate_planned_transaction(self):
        """Тест створення планової транзакції з правила."""
        rule = RecurrenceRule.objects.create(
            company=self.company,
            frequency='monthly',
            interval=1,
            start_date=dt.date(2026, 6, 1),
            template_type='expense',
            template_amount=Decimal('36000'),
            template_account=self.account,
            template_category=self.category,
            template_comment='Оренда офісу',
        )

        # Генеруємо транзакцію на 1 червня
        txn = recurring.generate_planned_transaction(
            rule, dt.date(2026, 6, 1), user=self.user
        )

        self.assertIsNotNone(txn)
        self.assertEqual(txn.type, Transaction.TYPE_EXPENSE)
        self.assertEqual(txn.amount, Decimal('36000'))
        self.assertEqual(txn.status, Transaction.STATUS_PLANNED)
        self.assertEqual(txn.recurrence_rule, rule)
        self.assertEqual(txn.account, self.account)
        self.assertEqual(txn.category, self.category)

    def test_generate_upcoming_transactions(self):
        """Тест генерації транзакцій на N днів вперед."""
        rule = RecurrenceRule.objects.create(
            company=self.company,
            frequency='monthly',
            interval=1,
            by_month_day=1,
            start_date=timezone.localdate(),
            template_type='expense',
            template_amount=Decimal('36000'),
            template_account=self.account,
            template_category=self.category,
            auto_create=True,
            is_active=True,
        )

        # Генеруємо на 90 днів вперед (має створити ~3 транзакції)
        created = recurring.generate_upcoming_transactions(
            rule, user=self.user, days_ahead=90
        )

        self.assertGreaterEqual(len(created), 2)
        self.assertLessEqual(len(created), 4)

        # Всі мають бути планові
        for txn in created:
            self.assertEqual(txn.status, Transaction.STATUS_PLANNED)
            self.assertEqual(txn.amount, Decimal('36000'))

    def test_recurring_rule_with_end_date(self):
        """Тест що правило зупиняється після end_date."""
        rule = RecurrenceRule.objects.create(
            company=self.company,
            frequency='monthly',
            interval=1,
            start_date=dt.date(2026, 5, 1),
            end_date=dt.date(2026, 7, 31),  # Тільки 3 місяці
            template_type='expense',
            template_amount=Decimal('10000'),
            template_account=self.account,
            template_category=self.category,
            auto_create=True,
            is_active=True,
        )

        # Генеруємо на 180 днів вперед
        created = recurring.generate_upcoming_transactions(
            rule, user=self.user, days_ahead=180
        )

        # Має створити максимум 3 транзакції (травень, червень, липень)
        self.assertLessEqual(len(created), 3)


class ForecastTestCase(TestCase):
    """Тести для прогнозу балансу."""

    def setUp(self):
        """Створення тестових даних."""
        self.company = Company.objects.create(name='Test Company', base_currency='UAH')

        self.account = Account.objects.create(
            company=self.company,
            name='Основний рахунок',
            type='bank',
            currency='UAH',
            initial_balance=Decimal('50000'),
        )

    def test_balance_forecast_report(self):
        """Тест звіту прогнозу балансу."""
        # Створюємо планові операції на майбутнє
        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_INCOME,
            status=Transaction.STATUS_PLANNED,
            amount=Decimal('100000'),
            currency='UAH',
            account=self.account,
            date_actual=timezone.now() + dt.timedelta(days=15),
        )

        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_PLANNED,
            amount=Decimal('30000'),
            currency='UAH',
            account=self.account,
            date_actual=timezone.now() + dt.timedelta(days=20),
        )

        # Генеруємо прогноз на 3 місяці
        data = reports.balance_forecast_report(self.company, months=3)

        # Перевіряємо структуру
        self.assertEqual(data['current_balance'], Decimal('50000'))
        self.assertEqual(len(data['forecast']), 3)

        # Перший місяць має включати планові операції
        first_month = data['forecast'][0]
        self.assertGreaterEqual(first_month['planned_income'], Decimal('100000'))
        self.assertGreaterEqual(first_month['planned_expense'], Decimal('30000'))

    def test_forecast_with_negative_balance(self):
        """Тест прогнозу з негативним балансом."""
        # Створюємо велику планову витрату
        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_PLANNED,
            amount=Decimal('80000'),  # Більше ніж баланс
            currency='UAH',
            account=self.account,
            date_actual=timezone.now() + dt.timedelta(days=10),
        )

        data = reports.balance_forecast_report(self.company, months=3)

        # Перевіряємо що є попередження про негативний баланс
        first_month = data['forecast'][0]
        self.assertTrue(first_month['is_negative'] or first_month['is_warning'])
