"""Тести керування плановими платежами: повторення, згортання (без дублів),
погашення з вибором рахунку/контрагента, редагування плану, історія контрагента."""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from finance.models import (
    Account, Category, Counterparty, RecurrenceRule, Transaction, get_default_company,
)
from finance.services import obligations as obligations_service
from finance.services import recurring as recurring_service
from finance.services import counterparty as cp_service
from finance.services import transactions as txn_service

User = get_user_model()


class RecurrenceLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_rec', 'r@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='ФОП', currency='UAH',
                                          initial_balance=Decimal('0'), is_business=True)
        self.cat = Category.objects.create(company=self.company, name='Комуналка', type='expense')
        self.cp = Counterparty.objects.create(company=self.company, name='Водоканал', type='supplier')

    def _seed_expense(self, *, status=Transaction.STATUS_PLANNED, date=None):
        return txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('3000'),
            account=self.acc, currency='UAH', category=self.cat, counterparty=self.cp,
            status=status, date_actual=date or timezone.now(), comment='Комуналка',
        )

    def test_rule_created_and_materialized_indefinite(self):
        """Безстрокове щомісячне правило матеріалізує кілька планових наперед."""
        txn = self._seed_expense()
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        self.assertTrue(rule.is_active)
        # Початкова транзакція стала першим екземпляром.
        txn.refresh_from_db()
        self.assertEqual(txn.recurrence_rule_id, rule.id)
        self.assertTrue(txn.is_recurring)
        # Матеріалізовано наступні (горизонт 120 дн → щонайменше ще 1).
        total = rule.transactions.count()
        self.assertGreaterEqual(total, 2)

    def test_remaining_count_mode(self):
        """Режим «N разів» рахує, скільки лишилось."""
        txn = self._seed_expense()
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly',
            end_mode=RecurrenceRule.END_COUNT, count=3)
        # Усього рівно 3 екземпляри (не більше).
        self.assertEqual(rule.transactions.exclude(status=Transaction.STATUS_CANCELLED).count(), 3)
        rem = recurring_service.remaining(rule)
        self.assertEqual(rem['mode'], 'count')
        self.assertEqual(rem['done'], 0)
        self.assertEqual(rem['left'], 3)
        self.assertEqual(rem['left_amount'], Decimal('9000'))

    def test_obligations_collapse_no_duplication(self):
        """Повторюване зобов'язання — ОДИН рядок, а не копія за кожен місяць."""
        txn = self._seed_expense()
        recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        # У БД кілька планових, але зобов'язання має бути одне.
        planned_count = Transaction.objects.filter(
            company=self.company, status=Transaction.STATUS_PLANNED,
            type=Transaction.TYPE_EXPENSE).count()
        self.assertGreaterEqual(planned_count, 1)
        data = obligations_service.planned_obligations(self.company)
        self.assertEqual(len(data['expense']), 1)
        oblig = data['expense'][0]
        self.assertEqual(oblig['kind'], 'recurring')
        self.assertEqual(oblig['title'], 'Комуналка')
        self.assertIn('щомісяця', oblig['frequency_label'])
        self.assertEqual(oblig['per_amount'], Decimal('3000'))

    def test_settle_with_account_and_counterparty_advances(self):
        """Погашення проводить платіж на рахунок, фіксує контрагента й підтягує наступний."""
        txn = self._seed_expense()
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        # Найближчий планований (= перший екземпляр).
        first = rule.transactions.filter(status=Transaction.STATUS_PLANNED).order_by('date_actual').first()
        pay_acc = Account.objects.create(company=self.company, name='Картка', currency='UAH')
        recurring_service.settle_occurrence(
            first, user=self.user, account=pay_acc, counterparty=self.cp, link_account_cp=True)
        first.refresh_from_db()
        self.assertEqual(first.status, Transaction.STATUS_ACTUAL)
        self.assertEqual(first.account_id, pay_acc.id)
        self.assertEqual(first.counterparty_id, self.cp.id)
        # Рахунок прив'язано до контрагента (для історії).
        pay_acc.refresh_from_db()
        self.assertEqual(pay_acc.counterparty_id, self.cp.id)
        # Проведення зменшило фактичний баланс картки.
        self.assertEqual(pay_acc.current_balance, Decimal('-3000'))

    def test_update_plan_changes_future_not_past(self):
        """Зміна суми плану переносить її на майбутні, не чіпаючи проведені."""
        txn = self._seed_expense(status=Transaction.STATUS_ACTUAL,
                                 date=timezone.now() - dt.timedelta(days=2))
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        recurring_service.update_plan(rule, user=self.user, amount=Decimal('4200'))
        txn.refresh_from_db()
        # Проведена (фактична) лишилась 3000.
        self.assertEqual(txn.amount, Decimal('3000'))
        # Майбутні планові стали 4200.
        future = rule.transactions.filter(status=Transaction.STATUS_PLANNED)
        self.assertTrue(future.exists())
        for f in future:
            self.assertEqual(f.amount, Decimal('4200'))
        rule.refresh_from_db()
        self.assertEqual(rule.template_amount, Decimal('4200'))


class CounterpartyHistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_cp', 'c@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='Банк', currency='UAH')
        self.cp = Counterparty.objects.create(company=self.company, name='ТОВ Ромашка')

    def test_history_aggregates_received_paid_planned(self):
        txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_INCOME, amount=Decimal('5000'),
            account=self.acc, counterparty=self.cp, date_actual=timezone.now())
        txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('1200'),
            account=self.acc, counterparty=self.cp, date_actual=timezone.now())
        txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_INCOME, amount=Decimal('8000'),
            account=self.acc, counterparty=self.cp, status=Transaction.STATUS_PLANNED,
            date_actual=timezone.now() + dt.timedelta(days=10))
        data = cp_service.counterparty_history(self.company, self.cp)
        self.assertEqual(data['counterparty']['name'], 'ТОВ Ромашка')
        self.assertEqual(len(data['transactions']), 3)
        self.assertEqual(len(data['accounts']), 1)
        self.assertIn('5 000', data['totals']['received'])
        self.assertIn('1 200', data['totals']['paid'])
        self.assertIn('8 000', data['totals']['planned_in'])


class RecurrenceApiWiringTests(TestCase):
    FIN_HOST = 'fin.twocomms.shop'

    def setUp(self):
        self.user = User.objects.create_superuser('fin_api', 'a@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='ФОП', currency='UAH',
                                          is_business=True)
        self.cat = Category.objects.create(company=self.company, name='Оренда', type='expense')
        self.client.force_login(self.user)

    def _post(self, path, payload):
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=[self.FIN_HOST, 'testserver']):
            return self.client.post(path, data=json.dumps(payload),
                                    content_type='application/json', HTTP_HOST=self.FIN_HOST)

    def _get(self, path):
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=[self.FIN_HOST, 'testserver']):
            return self.client.get(path, HTTP_HOST=self.FIN_HOST)

    def test_create_api_creates_recurrence_rule(self):
        """POST у журнал з recurrence створює правило (раніше поле ігнорувалося)."""
        future = (timezone.now() + dt.timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        resp = self._post('/api/transactions/create/', {
            'type': 'expense', 'amount': '15000', 'account': self.acc.id,
            'category': self.cat.id, 'date_actual': future,
            'recurrence': 'monthly', 'recurrence_end_mode': 'never',
            'recurrence_title': 'Оренда офісу',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        rule = RecurrenceRule.objects.filter(company=self.company, title='Оренда офісу').first()
        self.assertIsNotNone(rule)
        self.assertEqual(rule.frequency, 'monthly')
        self.assertTrue(rule.transactions.exists())

    def test_settle_api_marks_actual_with_account(self):
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('500'),
            account=None, currency='UAH', status=Transaction.STATUS_PLANNED,
            date_actual=timezone.now() + dt.timedelta(days=1))
        resp = self._post(f'/api/transactions/{txn.id}/settle/', {'account_id': self.acc.id})
        self.assertEqual(resp.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, Transaction.STATUS_ACTUAL)
        self.assertEqual(txn.account_id, self.acc.id)

    def test_planned_page_renders(self):
        resp = self._get('/planned/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Планові платежі')
