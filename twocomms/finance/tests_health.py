"""Тести рушія «Фінансового здоров'я» (acceptance-критерії ТЗ §19)."""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Account, Counterparty, Transaction, get_default_company
from .services import health


def _txn(company, account, **kw):
    defaults = dict(
        company=company, type=Transaction.TYPE_INCOME,
        status=Transaction.STATUS_ACTUAL, amount=Decimal('100'),
        amount_base=Decimal('100'), currency='UAH', account=account,
        date_actual=timezone.now(), is_business=True,
    )
    defaults.update(kw)
    return Transaction.objects.create(**defaults)


@override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'])
class HealthEngineTests(TestCase):
    def setUp(self):
        self.company = get_default_company()
        self.biz = Account.objects.create(
            company=self.company, name='ФОП', currency='UAH', is_business=True,
            initial_balance=Decimal('0'))
        self.pers = Account.objects.create(
            company=self.company, name='Особиста', currency='UAH', is_business=False,
            initial_balance=Decimal('0'))

    def test_normalizers(self):
        self.assertEqual(health.score_higher_better(5, 0, 10), 50.0)
        self.assertEqual(health.score_higher_better(-1, 0, 10), 0.0)
        self.assertEqual(health.score_higher_better(11, 0, 10), 100.0)
        self.assertEqual(health.score_lower_better(0, 0, 10), 100.0)
        self.assertEqual(health.score_lower_better(10, 0, 10), 0.0)
        self.assertEqual(health.score_target_range(5, 0, 3, 7, 10), 100.0)

    def test_zero_profit_cannot_be_100(self):
        """§19.1: нульова прибутковість → portfolio < 90, є lost point."""
        # Активний бізнес: є виручка, але прибуток ~0 (витрати = доходам).
        now = timezone.now()
        _txn(self.company, self.biz, type=Transaction.TYPE_INCOME,
             amount=Decimal('5000'), amount_base=Decimal('5000'),
             category=self._cat('Продажі', 'income'))
        _txn(self.company, self.biz, type=Transaction.TYPE_EXPENSE,
             amount=Decimal('5000'), amount_base=Decimal('5000'),
             category=self._cat('Закупівля', 'expense'))
        res = health.calculate_health(self.company)
        self.assertLess(res['scores']['portfolio_final'], 90)

    def test_incomplete_data_caps_score(self):
        """§19.2: низька категоризація → confidence та cap."""
        now = timezone.now()
        # Багато некатегоризованих операцій.
        for i in range(10):
            _txn(self.company, self.biz, type=Transaction.TYPE_EXPENSE,
                 amount=Decimal('300'), amount_base=Decimal('300'), category=None)
        res = health.calculate_health(self.company)
        self.assertLessEqual(res['scores']['portfolio_final'], 84)

    def test_forecast_cash_gap_caps_to_59(self):
        """§19.3: прогнозний касовий розрив → cap ≤ 59 + critical alert."""
        now = timezone.now()
        # Невеликий баланс.
        _txn(self.company, self.biz, type=Transaction.TYPE_INCOME,
             amount=Decimal('1000'), amount_base=Decimal('1000'))
        # Великий плановий платіж у майбутньому → розрив.
        Transaction.objects.create(
            company=self.company, type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_PLANNED, amount=Decimal('50000'),
            amount_base=Decimal('50000'), currency='UAH', account=self.biz,
            date_actual=now + timezone.timedelta(days=10), is_business=True)
        res = health.calculate_health(self.company)
        self.assertLessEqual(res['scores']['portfolio_final'], 59)
        self.assertTrue(any(a['title'] == 'Можливий касовий розрив'
                            for a in res['critical_alerts']))

    def test_personal_empty_is_incomplete_not_excellent(self):
        """§19.8: особисті витрати = 0 при контурі → incomplete, не excellent."""
        now = timezone.now()
        _txn(self.company, self.biz, type=Transaction.TYPE_INCOME,
             amount=Decimal('10000'), amount_base=Decimal('10000'),
             category=self._cat('Продажі', 'income'))
        res = health.calculate_health(self.company)
        self.assertTrue(res['personal_incomplete'])

    def test_lost_points_present_when_not_100(self):
        now = timezone.now()
        _txn(self.company, self.biz, type=Transaction.TYPE_EXPENSE,
             amount=Decimal('2000'), amount_base=Decimal('2000'), category=None)
        res = health.calculate_health(self.company)
        if res['scores']['portfolio_final'] < 100:
            self.assertTrue(len(res['lost_points']) > 0)

    def test_recommendations_have_structure(self):
        now = timezone.now()
        for i in range(5):
            _txn(self.company, self.biz, type=Transaction.TYPE_EXPENSE,
                 amount=Decimal('400'), amount_base=Decimal('400'), category=None)
        res = health.calculate_health(self.company)
        for r in res['recommendations']:
            self.assertIn('title', r)
            self.assertIn('problem', r)
            self.assertIn('why', r)
            self.assertIn('action', r)
            self.assertIn('severity', r)

    def test_result_shape(self):
        res = health.calculate_health(self.company)
        for key in ('scores', 'caps', 'lost_points', 'critical_alerts', 'recommendations'):
            self.assertIn(key, res)
        for key in ('business', 'personal', 'boundary', 'portfolio_final', 'data_confidence'):
            self.assertIn(key, res['scores'])
        self.assertGreaterEqual(res['scores']['portfolio_final'], 0)
        self.assertLessEqual(res['scores']['portfolio_final'], 100)

    def _cat(self, name, ctype):
        from .models import Category
        return Category.objects.create(company=self.company, name=name, type=ctype)
