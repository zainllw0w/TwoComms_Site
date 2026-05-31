"""Тести для Personal Expenses (особисті витрати) — БЛОК 2."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from finance.models import Category, Company, Account, Transaction
from finance.services import reports


class PersonalExpensesTestCase(TestCase):
    """Тести для функціональності особистих витрат."""

    def setUp(self):
        """Створення тестових даних."""
        self.company = Company.objects.create(name='Test Company', base_currency='UAH')

        # Категорії
        self.food_cat = Category.objects.create(
            company=self.company,
            name='Їжа та продукти',
            type='expense',
            icon='🍕',
            color='#f59e0b',
        )

        self.transport_cat = Category.objects.create(
            company=self.company,
            name='Транспорт',
            type='expense',
            icon='🚗',
            color='#3b82f6',
        )

        self.business_cat = Category.objects.create(
            company=self.company,
            name='Офісні витрати',
            type='expense',
        )

        # Рахунки
        self.personal_account = Account.objects.create(
            company=self.company,
            name='Особиста картка',
            type='card',
            currency='UAH',
            is_business=False,
            initial_balance=Decimal('50000'),
        )

        self.business_account = Account.objects.create(
            company=self.company,
            name='ФОП рахунок',
            type='bank',
            currency='UAH',
            is_business=True,
            initial_balance=Decimal('100000'),
        )

    def test_personal_expenses_report(self):
        """Тест звіту по особистих витратах."""
        # Створюємо особисті витрати
        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_ACTUAL,
            amount=Decimal('5000'),
            currency='UAH',
            account=self.personal_account,
            category=self.food_cat,
            date_actual=timezone.now(),
            is_business=False,
        )

        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_ACTUAL,
            amount=Decimal('2000'),
            currency='UAH',
            account=self.personal_account,
            category=self.transport_cat,
            date_actual=timezone.now(),
            is_business=False,
        )

        # Створюємо бізнес-витрату (не має враховуватись)
        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_ACTUAL,
            amount=Decimal('10000'),
            currency='UAH',
            account=self.business_account,
            category=self.business_cat,
            date_actual=timezone.now(),
            is_business=True,
        )

        # Створюємо дохід
        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_INCOME,
            status=Transaction.STATUS_ACTUAL,
            amount=Decimal('50000'),
            currency='UAH',
            account=self.business_account,
            date_actual=timezone.now(),
            is_business=True,
        )

        # Генеруємо звіт
        data = reports.personal_expenses_report(self.company, {})

        # Перевіряємо результати
        self.assertEqual(data['total_personal'], Decimal('7000'))  # 5000 + 2000
        self.assertEqual(data['business_expenses'], Decimal('10000'))
        self.assertEqual(data['total_income'], Decimal('50000'))
        self.assertEqual(data['personal_percent'], 14.0)  # 7000 / 50000 * 100
        self.assertEqual(len(data['categories']), 2)

        # Перевіряємо категорії
        food_cat_data = next((c for c in data['categories'] if c['name'] == 'Їжа та продукти'), None)
        self.assertIsNotNone(food_cat_data)
        self.assertEqual(food_cat_data['amount'], Decimal('5000'))
        self.assertAlmostEqual(food_cat_data['pct'], 71.4, places=1)  # 5000 / 7000 * 100

    def test_personal_expenses_by_month(self):
        """Тест групування особистих витрат по місяцях."""
        import datetime as dt

        # Витрати в різних місяцях
        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_ACTUAL,
            amount=Decimal('3000'),
            currency='UAH',
            account=self.personal_account,
            category=self.food_cat,
            date_actual=timezone.make_aware(dt.datetime(2026, 5, 15)),
            is_business=False,
        )

        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_ACTUAL,
            amount=Decimal('4000'),
            currency='UAH',
            account=self.personal_account,
            category=self.food_cat,
            date_actual=timezone.make_aware(dt.datetime(2026, 4, 20)),
            is_business=False,
        )

        data = reports.personal_expenses_report(self.company, {})

        # Перевіряємо групування по місяцях
        self.assertEqual(len(data['by_month']), 2)
        months_dict = dict(data['by_month'])
        self.assertEqual(months_dict['2026-05'], Decimal('3000'))
        self.assertEqual(months_dict['2026-04'], Decimal('4000'))

    def test_personal_expenses_excluded_from_business(self):
        """Тест що особисті витрати не впливають на бізнес-звіти."""
        # Особиста витрата
        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_ACTUAL,
            amount=Decimal('5000'),
            currency='UAH',
            account=self.personal_account,
            category=self.food_cat,
            date_actual=timezone.now(),
            is_business=False,
        )

        # Бізнес-операції
        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_INCOME,
            status=Transaction.STATUS_ACTUAL,
            amount=Decimal('50000'),
            currency='UAH',
            account=self.business_account,
            date_actual=timezone.now(),
            is_business=True,
        )

        Transaction.objects.create(
            company=self.company,
            type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_ACTUAL,
            amount=Decimal('30000'),
            currency='UAH',
            account=self.business_account,
            category=self.business_cat,
            date_actual=timezone.now(),
            is_business=True,
        )

        # P&L звіт (тільки бізнес)
        pnl_data = reports.pnl(self.company, {'scope': 'business'})

        # Особиста витрата не має впливати на бізнес-прибуток
        self.assertEqual(pnl_data['profit'], Decimal('20000'))  # 50000 - 30000
        self.assertEqual(pnl_data['expenses'], Decimal('30000'))  # Без особистих 5000
