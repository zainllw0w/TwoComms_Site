"""Тести виправлення дрейфу балансів рахунків (repair + back-calc)."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.core.management import call_command

from finance.models import Account, Company, Transaction, IntegrationConnection


class BalanceRepairTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Test Co', base_currency='UAH')

    def _txn(self, acc, ttype, amount, balance_after=None, to_acc=None, to_amount=None):
        ed = {}
        if balance_after is not None:
            ed['balance_after'] = int(Decimal(balance_after) * 100)
        return Transaction.objects.create(
            company=self.company, type=ttype, status='actual',
            amount=Decimal(amount), currency='UAH', account=acc, to_account=to_acc,
            to_amount=Decimal(to_amount) if to_amount is not None else None,
            date_actual=timezone.now(), source='integration', external_data=ed,
        )

    def test_repair_fixes_drifted_integration_account(self):
        """Repair доводить initial так, щоб current == останній bank balance_after."""
        acc = Account.objects.create(
            company=self.company, name='mono black', type='card', currency='UAH',
            external_account_id='acc-1', external_kind='card',
            initial_balance=Decimal('-1600.53'),
        )
        # Транзакції з достовірним balance_after (остання = 1438.78).
        self._txn(acc, 'expense', '215.00', balance_after='261.12')
        self._txn(acc, 'income', '300.00', balance_after='1438.78')
        acc.recalc_balance(save=True)
        acc.refresh_from_db()
        # Через занижений initial баланс «зламаний».
        self.assertNotEqual(acc.current_balance, Decimal('1438.78'))

        call_command('finance_repair_balances')
        acc.refresh_from_db()
        self.assertEqual(acc.current_balance, Decimal('1438.78'))

    def test_repair_ignores_transfer_in_balance_after(self):
        """balance_after переказу, отриманого з чужого рахунку, не береться як свій."""
        src = Account.objects.create(company=self.company, name='ФОП', type='bank',
                                     currency='UAH', external_account_id='fop',
                                     initial_balance=Decimal('0'))
        acc = Account.objects.create(company=self.company, name='card', type='card',
                                     currency='UAH', external_account_id='card',
                                     initial_balance=Decimal('0'))
        # Перевод ФОП -> card: account=src, to_account=acc, balance_after = ФОП-баланс (чужий).
        self._txn(src, 'transfer', '1000', balance_after='9999.99', to_acc=acc, to_amount='1000')
        # Власна income картки з достовірним balance_after.
        self._txn(acc, 'income', '300', balance_after='1300.00')
        acc.recalc_balance(save=True)
        call_command('finance_repair_balances')
        acc.refresh_from_db()
        # Має взяти 1300 (свій), а не 9999.99 (чужий від переказу).
        self.assertEqual(acc.current_balance, Decimal('1300.00'))

    def test_repair_manual_account_aligns_initial(self):
        """Manual-рахунок без руху: init вирівнюється до current (стабільність recalc)."""
        acc = Account.objects.create(company=self.company, name='Готівка', type='cash',
                                     currency='UAH', initial_balance=Decimal('15000'),
                                     current_balance=Decimal('27000'))
        call_command('finance_repair_balances')
        acc.refresh_from_db()
        self.assertEqual(acc.initial_balance, Decimal('27000'))
        self.assertEqual(acc.current_balance, Decimal('27000'))

    def test_reconcile_balances_from_client(self):
        """Фінальний back-calc проти client-info доводить current до банк-балансу."""
        from finance.services import mono

        conn = IntegrationConnection.objects.create(
            company=self.company, provider='monobank', status='success')
        acc = Account.objects.create(
            company=self.company, name='mono', type='card', currency='UAH',
            external_account_id='X1', integration=conn, initial_balance=Decimal('-500'))
        self._txn(acc, 'income', '300')
        acc.recalc_balance(save=True)

        # Stub-клієнт повертає реальний баланс 1438.78 (143878 копійок).
        class _A:
            id = 'X1'; balance = 143878
        class _Client:
            def accounts(self_inner):
                return [_A()]
        n = mono.reconcile_balances_from_client(conn, client=_Client())
        acc.refresh_from_db()
        self.assertEqual(n, 1)
        self.assertEqual(acc.current_balance, Decimal('1438.78'))
