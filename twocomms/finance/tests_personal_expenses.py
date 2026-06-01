"""Тести для Personal Expenses (особисті витрати) — БЛОК 2."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from finance.models import Category, Company, Account, Transaction
from finance.services import reports


class PersonalExpensesTestCase(TestCase):
    """Тести для функціональності особистих витрат."""

    def _mk(self, *, amount, ttype=Transaction.TYPE_EXPENSE, account=None,
            category=None, is_business=False, date_actual=None):
        """Створює фактичну транзакцію з коректним amount_base (= amount для UAH)."""
        amt = Decimal(str(amount))
        return Transaction.objects.create(
            company=self.company, type=ttype, status=Transaction.STATUS_ACTUAL,
            amount=amt, amount_base=amt, currency='UAH',
            account=account or self.personal_account, category=category,
            date_actual=date_actual or timezone.now(), is_business=is_business,
        )

    def setUp(self):
        """Створення тестових даних."""
        self.company = Company.objects.create(name='Test Company', base_currency='UAH')
        self.food_cat = Category.objects.create(
            company=self.company, name='Їжа та продукти', type='expense',
            icon='🍕', color='#f59e0b')
        self.transport_cat = Category.objects.create(
            company=self.company, name='Транспорт', type='expense',
            icon='🚗', color='#3b82f6')
        self.business_cat = Category.objects.create(
            company=self.company, name='Офісні витрати', type='expense')
        self.personal_account = Account.objects.create(
            company=self.company, name='Особиста картка', type='card',
            currency='UAH', is_business=False, initial_balance=Decimal('50000'))
        self.business_account = Account.objects.create(
            company=self.company, name='ФОП рахунок', type='bank',
            currency='UAH', is_business=True, initial_balance=Decimal('100000'))

    def test_personal_expenses_report(self):
        """Тест звіту по особистих витратах."""
        self._mk(amount='5000', category=self.food_cat, is_business=False)
        self._mk(amount='2000', category=self.transport_cat, is_business=False)
        # Бізнес-витрата (не має враховуватись у особистих).
        self._mk(amount='10000', account=self.business_account,
                 category=self.business_cat, is_business=True)
        # Дохід.
        self._mk(amount='50000', ttype=Transaction.TYPE_INCOME,
                 account=self.business_account, is_business=True)

        data = reports.personal_expenses_report(self.company, {'period': 'all'})

        self.assertEqual(data['total_personal'], Decimal('7000'))  # 5000 + 2000
        self.assertEqual(data['business_expenses'], Decimal('10000'))
        self.assertEqual(data['total_income'], Decimal('50000'))
        self.assertEqual(data['personal_percent'], 14.0)  # 7000 / 50000 * 100
        self.assertEqual(len(data['categories']), 2)

        food_cat_data = next((c for c in data['categories'] if c['name'] == 'Їжа та продукти'), None)
        self.assertIsNotNone(food_cat_data)
        self.assertEqual(food_cat_data['amount'], Decimal('5000'))
        self.assertAlmostEqual(food_cat_data['pct'], 71.4, places=1)  # 5000 / 7000 * 100

    def test_personal_expenses_by_month(self):
        """Тест групування особистих витрат по місяцях."""
        import datetime as dt
        self._mk(amount='3000', category=self.food_cat, is_business=False,
                 date_actual=timezone.make_aware(dt.datetime(2026, 5, 15)))
        self._mk(amount='4000', category=self.food_cat, is_business=False,
                 date_actual=timezone.make_aware(dt.datetime(2026, 4, 20)))

        data = reports.personal_expenses_report(self.company, {'period': 'all'})

        self.assertEqual(len(data['by_month']), 2)
        months_dict = dict(data['by_month'])
        self.assertEqual(months_dict['2026-05'], Decimal('3000'))
        self.assertEqual(months_dict['2026-04'], Decimal('4000'))

    def test_personal_expenses_excluded_from_business(self):
        """Тест що особисті витрати не впливають на бізнес-звіти."""
        self._mk(amount='5000', category=self.food_cat, is_business=False)
        self._mk(amount='50000', ttype=Transaction.TYPE_INCOME,
                 account=self.business_account, is_business=True)
        self._mk(amount='30000', account=self.business_account,
                 category=self.business_cat, is_business=True)

        pnl_data = reports.pnl(self.company, {'scope': 'business', 'period': 'all'})

        self.assertEqual(pnl_data['profit'], Decimal('20000'))  # 50000 - 30000
        self.assertEqual(pnl_data['expenses'], Decimal('30000'))  # Без особистих 5000
