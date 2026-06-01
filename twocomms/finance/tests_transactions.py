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


class PaymentsViewTests(TestCase):
    """Журнал і API-ендпоінти рендеряться/відповідають для адміна."""

    FIN_HOST = 'fin.twocomms.shop'

    def setUp(self):
        self.user = User.objects.create_superuser('fin_root2', 'r2@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='Каса', currency='UAH',
                                           initial_balance=Decimal('1000'), current_balance=Decimal('1000'))
        self.client.force_login(self.user)

    def _get(self, path):
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            return self.client.get(path, HTTP_HOST=self.FIN_HOST)

    def test_journal_renders(self):
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('250'), account=self.acc)
        resp = self._get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Платежі')
        self.assertContains(resp, 'fin-table')
        # Регресія: коментарі шаблону не повинні протікати у вивід як текст
        # (багаторядкові {# #} рендеряться буквально — використовувати {% comment %}).
        body = resp.content.decode('utf-8')
        self.assertNotIn('{#', body)
        self.assertNotIn('{% comment', body)
        self.assertNotIn('Проект» приховано', body)

    def test_journal_pagination(self):
        # 15 фактичних операцій → за замовчуванням сторінка показує 10.
        for i in range(15):
            txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                           amount=Decimal('10'), account=self.acc)
        resp = self._get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['rows']), 10)
        self.assertEqual(resp.context['total_count'], 15)
        self.assertEqual(resp.context['per_page'], 10)
        self.assertEqual(resp.context['page_obj'].paginator.num_pages, 2)
        # Друга сторінка — решта 5.
        resp2 = self._get('/?page=2')
        self.assertEqual(len(resp2.context['rows']), 5)
        # per_page=all → без розбивки.
        resp3 = self._get('/?per_page=all')
        self.assertEqual(len(resp3.context['rows']), 15)
        self.assertEqual(resp3.context['per_page'], 'all')
        self.assertIsNone(resp3.context['page_obj'])
        # per_page=25 → усі 15 на одній сторінці.
        resp4 = self._get('/?per_page=25')
        self.assertEqual(len(resp4.context['rows']), 15)

    def test_dropdowns_api(self):
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            resp = self.client.get('/api/dropdowns/', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

    def test_create_via_api(self):
        from django.test import override_settings
        import json as _json
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            resp = self.client.post('/api/transactions/create/',
                                    data=_json.dumps({'type': 'income', 'amount': '500',
                                                      'account': self.acc.id}),
                                    content_type='application/json', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.current_balance, Decimal('1500'))

    def test_future_date_auto_plan(self):
        """Майбутня дата → операція стає плановою і не змінює фактичний баланс."""
        from django.test import override_settings
        from django.utils import timezone
        import datetime as dt
        future = (timezone.now() + dt.timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            resp = self.client.post('/api/transactions/create/', data={
                'type': 'expense', 'amount': '300', 'account': self.acc.id,
                'currency': 'UAH', 'date_actual': future, 'status': 'actual',
            }, HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        txn = Transaction.objects.get(id=resp.json()['transaction']['id'])
        self.assertEqual(txn.status, Transaction.STATUS_PLANNED)
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.current_balance, Decimal('1000'))  # план не чіпає баланс

    def test_create_with_file_attachment(self):
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('receipt.txt', b'hello', content_type='text/plain')
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            resp = self.client.post('/api/transactions/create/', data={
                'type': 'income', 'amount': '100', 'account': self.acc.id,
                'currency': 'UAH', 'attachments': f,
            }, HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        txn = Transaction.objects.get(id=resp.json()['transaction']['id'])
        self.assertEqual(txn.attachments.count(), 1)

    def test_journal_filters_by_accounts_param(self):
        acc2 = Account.objects.create(company=self.company, name='ФОП', currency='UAH',
                                      initial_balance=Decimal('0'), current_balance=Decimal('0'))
        t1 = txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                            amount=Decimal('111'), account=self.acc)
        t2 = txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                            amount=Decimal('222'), account=acc2)
        resp = self._get('/?accounts=%s' % acc2.id)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '222')
        self.assertNotContains(resp, '+111')
