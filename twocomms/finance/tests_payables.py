"""Тести точного погашення зобов'язань (services/payables.py).

Покриває всі варіації, які описав власник бізнесу:
  • pick_txn повне — без подвійного розходу (баланс не змінюється);
  • new_payment повне — створює один факт, баланс −amount;
  • орієнтовна сума частково — залишок лишається плановим, оцінка стабільна;
  • орієнтовна повне (сплачено менше) — період закрито, наступний = оцінка (НЕ факт);
  • переплата — не йде в мінус, період закрито;
  • дебіторка симетрично (кейс Віктора) — template_amount стабільний;
  • пріоритет кандидатів; обернена прив'язка; запам'ятовування картки;
  • повторна прив'язка того ж платежу не дублює settlement.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import (Account, Category, Company, Counterparty, CounterpartyCard,
                     ObligationSettlement, RecurrenceRule, Transaction,
                     get_default_company)
from .services import payables as payables_service
from .services import recurring as recurring_service
from .services import transactions as txn_service

User = get_user_model()


class PayablesSettlementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_pay', 'p@x.com', 'x')
        self.company = get_default_company()
        self.mono = Account.objects.create(company=self.company, name='Mono', currency='UAH',
                                           initial_balance=Decimal('10000'), is_business=True)
        self.cat = Category.objects.create(company=self.company, name='Комуналка', type='expense')
        self.vlada = Counterparty.objects.create(company=self.company, name='Влада Мама',
                                                  type='landlord_personal')
        self.mono.recalc_balance(save=True)

    # ---- helpers ----
    def _recurring_expense(self, amount='2500', estimated=False):
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal(amount),
            account=self.mono, currency='UAH', category=self.cat, counterparty=self.vlada,
            status=Transaction.STATUS_PLANNED,
            date_actual=timezone.now() + dt.timedelta(days=2), comment='Комуналка',
            amount_is_estimated=estimated)
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER,
            amount_is_estimated=estimated)
        txn.refresh_from_db()
        return rule, txn

    def _nearest_planned(self, rule):
        return (rule.transactions.filter(status=Transaction.STATUS_PLANNED)
                .order_by('date_actual').first())

    def _actual_expense(self, amount='1700', account=None, comment='Переказ на картку'):
        return txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal(amount),
            account=account or self.mono, currency='UAH', status=Transaction.STATUS_ACTUAL,
            date_actual=timezone.now(), comment=comment, is_business=True)

    # ---- 1: pick_txn повне — без подвійного розходу ----
    def test_pick_txn_full_no_double_expense(self):
        rule, planned = self._recurring_expense('2500', estimated=True)
        self.mono.refresh_from_db()
        balance_before = self.mono.current_balance  # 10000 − 2500(вже існуючий факт? ні, планові не впливають)
        pay = self._actual_expense('1724')
        self.mono.refresh_from_db()
        balance_after_payment = self.mono.current_balance
        res = payables_service.settle_obligation(
            user=self.user, planned_txn=planned, mode='pick_txn', payment_txn=pay,
            full_period=True)
        self.mono.refresh_from_db()
        # Прив'язка наявного платежу НЕ змінює баланс (нової транзакції не створено).
        self.assertEqual(self.mono.current_balance, balance_after_payment)
        # Плановий скасовано, оцінка стабільна, settlement створено.
        planned.refresh_from_db()
        self.assertEqual(planned.status, Transaction.STATUS_CANCELLED)
        rule.refresh_from_db()
        self.assertEqual(rule.template_amount, Decimal('2500'))
        self.assertEqual(ObligationSettlement.objects.filter(payment=pay).count(), 1)
        # Наступний плановий екземпляр існує і дорівнює оцінці 2500.
        nxt = self._nearest_planned(rule)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.amount, Decimal('2500'))

    # ---- 2: new_payment повне — один факт, баланс −amount ----
    def test_new_payment_full_creates_single_expense(self):
        rule, planned = self._recurring_expense('2500')
        self.mono.refresh_from_db()
        before = self.mono.current_balance
        res = payables_service.settle_obligation(
            user=self.user, planned_txn=planned, mode='new_payment', amount=Decimal('2500'),
            account=self.mono, full_period=True)
        self.mono.refresh_from_db()
        self.assertEqual(self.mono.current_balance, before - Decimal('2500'))
        # Рівно один фактичний витратний платіж за цим періодом.
        actuals = Transaction.objects.filter(company=self.company, type=Transaction.TYPE_EXPENSE,
                                              status=Transaction.STATUS_ACTUAL)
        self.assertEqual(actuals.count(), 1)
        rule.refresh_from_db()
        self.assertEqual(rule.template_amount, Decimal('2500'))

    # ---- 3: орієнтовна частково — залишок лишається плановим ----
    def test_estimated_partial_keeps_remainder(self):
        rule, planned = self._recurring_expense('2500', estimated=True)
        res = payables_service.settle_obligation(
            user=self.user, planned_txn=planned, mode='new_payment', amount=Decimal('1400'),
            account=self.mono, full_period=False)
        planned.refresh_from_db()
        # Плановий лишається, зменшений на сплачене (залишок 1100).
        self.assertEqual(planned.status, Transaction.STATUS_PLANNED)
        self.assertEqual(planned.amount, Decimal('1100'))
        rule.refresh_from_db()
        self.assertEqual(rule.template_amount, Decimal('2500'))
        self.assertFalse(res['full_period'])

    # ---- 4: орієнтовна повне (сплачено менше) — наступний = оцінка, не факт ----
    def test_estimated_full_paid_less_next_is_estimate(self):
        rule, planned = self._recurring_expense('2500', estimated=True)
        payables_service.settle_obligation(
            user=self.user, planned_txn=planned, mode='new_payment', amount=Decimal('1400'),
            account=self.mono, full_period=True)
        rule.refresh_from_db()
        self.assertEqual(rule.template_amount, Decimal('2500'))
        nxt = self._nearest_planned(rule)
        self.assertEqual(nxt.amount, Decimal('2500'))  # НЕ 1400

    # ---- 5: переплата — не йде в мінус, період закрито ----
    def test_overpay_closes_period(self):
        rule, planned = self._recurring_expense('2500', estimated=True)
        res = payables_service.settle_obligation(
            user=self.user, planned_txn=planned, mode='new_payment', amount=Decimal('3000'),
            account=self.mono, full_period=True)
        self.assertTrue(res['full_period'])
        self.assertEqual(res['settlement'].amount, Decimal('3000'))
        rule.refresh_from_db()
        self.assertEqual(rule.template_amount, Decimal('2500'))

    # ---- 6: пріоритет кандидатів ----
    def test_candidates_priority_counterparty_first(self):
        # Платіж з контрагентом Влада > платіж без контрагента.
        p_other = self._actual_expense('500', comment='інше')
        p_vlada = self._actual_expense('1700', comment='Влада')
        p_vlada.counterparty = self.vlada
        p_vlada.save(update_fields=['counterparty'])
        cands = payables_service.payable_candidates(
            self.company, ttype=Transaction.TYPE_EXPENSE, counterparty=self.vlada)
        self.assertEqual(cands[0]['id'], p_vlada.id)

    # ---- 7: дебіторка симетрично (Віктор) ----
    def test_receivable_full_keeps_template(self):
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_INCOME, amount=Decimal('13000'),
            account=self.mono, currency='UAH', status=Transaction.STATUS_PLANNED,
            date_actual=timezone.now() + dt.timedelta(days=2), comment='Віктор')
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        txn.refresh_from_db()
        planned = self._nearest_planned(rule)
        income_pay = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_INCOME, amount=Decimal('17000'),
            account=self.mono, currency='UAH', status=Transaction.STATUS_ACTUAL,
            date_actual=timezone.now(), comment='Повернення Віктор')
        payables_service.settle_obligation(
            user=self.user, planned_txn=planned, mode='pick_txn', payment_txn=income_pay,
            full_period=True)
        rule.refresh_from_db()
        self.assertEqual(rule.template_amount, Decimal('13000'))
        nxt = self._nearest_planned(rule)
        self.assertEqual(nxt.amount, Decimal('13000'))

    # ---- 8: обернена прив'язка ----
    def test_attach_payment_to_obligation(self):
        rule, planned = self._recurring_expense('2500', estimated=True)
        pay = self._actual_expense('1724')
        pay.counterparty = self.vlada
        pay.save(update_fields=['counterparty'])
        res = payables_service.attach_payment_to_obligation(
            user=self.user, payment_txn=pay, planned_txn=planned, full_period=True)
        self.assertTrue(res['full_period'])
        planned.refresh_from_db()
        self.assertEqual(planned.status, Transaction.STATUS_CANCELLED)
        self.assertEqual(ObligationSettlement.objects.filter(payment=pay).count(), 1)

    # ---- 9: запам'ятовування картки ----
    def test_remember_card_upserts(self):
        rule, planned = self._recurring_expense('2500', estimated=True)
        res = payables_service.settle_obligation(
            user=self.user, planned_txn=planned, mode='new_payment', amount=Decimal('2500'),
            account=self.mono, full_period=True, remember_card=True,
            card_hint={'pan_mask': '537541******1234', 'last4': '1234', 'bank': 'monobank'})
        self.assertEqual(CounterpartyCard.objects.filter(counterparty=self.vlada).count(), 1)
        card = CounterpartyCard.objects.get(counterparty=self.vlada)
        self.assertEqual(card.last4, '1234')

    # ---- 10: reverse_link_candidates знаходить зобов'язання за контрагентом ----
    def test_reverse_link_finds_obligation(self):
        rule, planned = self._recurring_expense('2500', estimated=True)
        pay = self._actual_expense('1724')
        pay.counterparty = self.vlada
        pay.save(update_fields=['counterparty'])
        res = payables_service.reverse_link_candidates(self.company, pay)
        ids = [g['counterparty_id'] for g in res['obligations']]
        self.assertIn(self.vlada.id, ids)

    # ---- 11: картка контрагента — згорнуті зобов'язання + позначка погашення ----
    def test_counterparty_detail_collapses_and_labels(self):
        from .services import counterparty as cp_service
        rule, planned = self._recurring_expense('2500', estimated=True)
        pay = self._actual_expense('1724')
        pay.counterparty = self.vlada
        pay.save(update_fields=['counterparty'])
        payables_service.attach_payment_to_obligation(
            user=self.user, payment_txn=pay, planned_txn=planned, full_period=True)
        detail = cp_service.counterparty_detail(self.company, self.vlada)
        # Є згорнуті зобов'язання (наступний період), а не стіна планових.
        self.assertTrue(any(g['counterparty_id'] == self.vlada.id for g in detail['obligations']))
        # Фактичний платіж має позначку «у рахунок».
        labeled = [t for t in detail['actual_transactions'] if t.get('settled_label')]
        self.assertTrue(labeled)
        self.assertIn('Комуналка', labeled[0]['settled_label'])
