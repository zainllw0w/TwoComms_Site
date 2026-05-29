"""Тести лівої панелі: прогноз майбутніх платежів і собівартість складу."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from finance.models import Account, Transaction, get_default_company
from finance.services import balances as b
from finance.services import transactions as txn_service

User = get_user_model()


class PlannedForecastTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_fc', 'fc@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='Банк', currency='UAH',
                                           initial_balance=Decimal('100000'),
                                           current_balance=Decimal('100000'))

    def test_planned_counts_next_month_not_just_calendar_month(self):
        """Регрес: плани в наступному календарному місяці мали давати 0 і forecast == total."""
        # Сьогодні + 5 днів — може перетнути межу місяця.
        future = timezone.now() + dt.timedelta(days=5)
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('25000'), account=self.acc,
                                       status=Transaction.STATUS_PLANNED, date_actual=future)
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_EXPENSE,
                                       amount=Decimal('18000'), account=self.acc,
                                       status=Transaction.STATUS_PLANNED, date_actual=future)
        today = timezone.localdate()
        horizon = today + dt.timedelta(days=30)
        planned = b.planned_totals(self.company, None, horizon)
        self.assertEqual(planned['income'], Decimal('25000.00'))
        self.assertEqual(planned['expense'], Decimal('-18000.00'))
        total = b.total_actual_balance(self.company)
        forecast = total + planned['income'] + planned['expense']
        # forecast має відрізнятися від total на чистий план (+7000).
        self.assertEqual(forecast - total, Decimal('7000.00'))

    def test_overdue_pending_plan_included_with_open_lower_bound(self):
        past = timezone.now() - dt.timedelta(days=10)
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_EXPENSE,
                                       amount=Decimal('500'), account=self.acc,
                                       status=Transaction.STATUS_PLANNED, date_actual=past)
        horizon = timezone.localdate() + dt.timedelta(days=30)
        planned = b.planned_totals(self.company, None, horizon)
        self.assertEqual(planned['expense'], Decimal('-500.00'))

    def test_actual_not_counted_as_planned(self):
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('999'), account=self.acc,
                                       date_actual=timezone.now())
        horizon = timezone.localdate() + dt.timedelta(days=30)
        planned = b.planned_totals(self.company, None, horizon)
        self.assertEqual(planned['income'], Decimal('0.00'))
