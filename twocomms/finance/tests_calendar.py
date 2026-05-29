"""Тести Блоку 5: розрахунок календаря (залишок по днях, план vs факт)."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from finance.models import Account, Transaction, get_default_company
from finance.services import calendar as cal_service
from finance.services import transactions as txn_service

User = get_user_model()


class CalendarServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_c', 'c@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='Банк', currency='UAH',
                                           initial_balance=Decimal('1000'), current_balance=Decimal('1000'))

    def test_month_grid_runs_balance(self):
        today = timezone.localdate()
        # Дохід сьогодні +500.
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('500'), account=self.acc,
                                       date_actual=timezone.now())
        grid = cal_service.month_grid(self.company, today.year, today.month)
        day = next(d for d in grid['days'] if d['day'] == today.day)
        self.assertEqual(day['income'], Decimal('500'))
        # Кінцевий залишок дня >= 1500 (1000 початок + 500).
        self.assertGreaterEqual(day['end_balance'], Decimal('1500'))

    def test_planned_affects_forecast_not_actual(self):
        future = timezone.now() + dt.timedelta(days=3)
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_EXPENSE,
                                       amount=Decimal('300'), account=self.acc,
                                       status=Transaction.STATUS_PLANNED, date_actual=future)
        # Фактичний баланс не змінився.
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.current_balance, Decimal('1000'))
        # Але в календарі майбутній день показує витрату.
        grid = cal_service.month_grid(self.company, future.year, future.month)
        day = next(d for d in grid['days'] if d['day'] == future.day)
        self.assertEqual(day['expense'], Decimal('300'))

    def test_day_detail_lists_transactions(self):
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('200'), account=self.acc,
                                       date_actual=timezone.now())
        detail = cal_service.day_detail(self.company, timezone.localdate())
        self.assertEqual(len(detail['transactions']), 1)

    @override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'])
    def test_calendar_page_renders(self):
        self.client.force_login(self.user)
        resp = self.client.get('/calendar/', HTTP_HOST='fin.twocomms.shop')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'fin-calendar')
