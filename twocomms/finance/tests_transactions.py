"""Тести фінансової логіки Блоку 3: створення операцій і перерахунок балансів."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from finance.models import Account, Transaction, get_default_company
from finance.services import transactions as txn_service

User = get_user_model()


class TransactionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_root', 'r@x.com', 'x')
        self.company = get_default_company()
        self.acc1 = Account.objects.create(company=self.company, name='Каса', currency='UAH',
                                            initial_balance=Decimal('1000'), current_balance=Decimal('1000'))
        self.acc2 = Account.objects.create(company=self.company, name='Банк', currency='UAH',
                                            initial_balance=Decimal('5000'), current_balance=Decimal('5000'))

    def test_income_increases_balance(self):
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('250'), account=self.acc1)
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, Decimal('1250'))

    def test_expense_decreases_balance(self):
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_EXPENSE,
                                       amount=Decimal('300'), account=self.acc1)
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, Decimal('700'))

    def test_transfer_moves_between_accounts(self):
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_TRANSFER,
                                       amount=Decimal('400'), account=self.acc1,
                                       to_account=self.acc2, to_amount=Decimal('400'))
        self.acc1.refresh_from_db(); self.acc2.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, Decimal('600'))
        self.assertEqual(self.acc2.current_balance, Decimal('5400'))

    def test_planned_does_not_affect_balance(self):
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('999'), account=self.acc1,
                                       status=Transaction.STATUS_PLANNED)
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, Decimal('1000'))

    def test_delete_reverts_balance(self):
        txn = txn_service.create_transaction(user=self.user, type=Transaction.TYPE_EXPENSE,
                                             amount=Decimal('200'), account=self.acc1)
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, Decimal('800'))
        txn_service.delete_transaction(txn, user=self.user)
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, Decimal('1000'))

    def test_update_recomputes_balance(self):
        txn = txn_service.create_transaction(user=self.user, type=Transaction.TYPE_EXPENSE,
                                             amount=Decimal('200'), account=self.acc1)
        txn_service.update_transaction(txn, user=self.user, amount=Decimal('500'))
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, Decimal('500'))

    def test_convert_to_transfer_removes_pnl_effect(self):
        txn = txn_service.create_transaction(user=self.user, type=Transaction.TYPE_EXPENSE,
                                             amount=Decimal('100'), account=self.acc1)
        txn_service.convert_to_transfer(txn, user=self.user, to_account=self.acc2,
                                        to_amount=Decimal('100'))
        txn.refresh_from_db()
        self.assertEqual(txn.type, Transaction.TYPE_TRANSFER)
        self.acc2.refresh_from_db()
        self.assertEqual(self.acc2.current_balance, Decimal('5100'))
