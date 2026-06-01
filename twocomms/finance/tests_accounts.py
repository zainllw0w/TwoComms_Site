"""Тести Блоку 4: рахунки, корекція балансу, імпорт виписки з антидублями."""
from __future__ import annotations

import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from finance.models import Account, Transaction, get_default_company
from finance.services import accounts as account_service
from finance.services import imports as import_service

User = get_user_model()


class AccountServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_a', 'a@x.com', 'x')
        self.company = get_default_company()

    def test_create_account_sets_balance(self):
        acc = account_service.create_account(user=self.user, name='Каса',
                                             initial_balance=Decimal('500'))
        self.assertEqual(acc.current_balance, Decimal('500'))

    def test_delete_blocked_with_transactions(self):
        from finance.services import transactions as txn_service
        acc = account_service.create_account(user=self.user, name='Банк',
                                             initial_balance=Decimal('100'))
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('50'), account=acc)
        self.assertFalse(account_service.delete_account(acc, user=self.user))

    def test_correct_balance_creates_adjustment(self):
        acc = account_service.create_account(user=self.user, name='Каса',
                                             initial_balance=Decimal('100'))
        account_service.correct_balance(acc, user=self.user, target_balance=Decimal('250'))
        acc.refresh_from_db()
        self.assertEqual(acc.current_balance, Decimal('250'))


class ImportServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_i', 'i@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='Банк', currency='UAH',
                                           initial_balance=Decimal('0'), current_balance=Decimal('0'))

    def _csv(self):
        data = 'date,amount,comment,external_id\n2026-05-01,500.00,Продаж,EX1\n2026-05-02,-200.00,Закупівля,EX2\n'
        return io.BytesIO(data.encode('utf-8'))

    def test_parse_and_import(self):
        rows = import_service.parse_file(self._csv(), filename='statement.csv')
        self.assertEqual(len(rows), 2)
        result = import_service.import_rows(rows, user=self.user, account=self.acc, apply_rules=False)
        self.assertEqual(result['created'], 2)
        self.acc.refresh_from_db()
        # +500 -200 = 300
        self.assertEqual(self.acc.current_balance, Decimal('300'))

    def test_dedupe_by_external_id(self):
        rows = import_service.parse_file(self._csv(), filename='s.csv')
        import_service.import_rows(rows, user=self.user, account=self.acc, apply_rules=False)
        rows2 = import_service.parse_file(self._csv(), filename='s.csv')
        result = import_service.import_rows(rows2, user=self.user, account=self.acc, apply_rules=False)
        self.assertEqual(result['created'], 0)
        self.assertEqual(result['skipped'], 2)


class AccountsPageTests(TestCase):
    FIN_HOST = 'fin.twocomms.shop'

    def setUp(self):
        self.user = User.objects.create_superuser('fin_p', 'p@x.com', 'x')
        self.company = get_default_company()
        Account.objects.create(company=self.company, name='Каса', currency='UAH',
                               initial_balance=Decimal('100'), current_balance=Decimal('100'))
        self.client.force_login(self.user)

    def test_accounts_page_renders(self):
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            resp = self.client.get('/accounts/', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Рахунки')
        self.assertContains(resp, 'Оберіть спосіб додавання')

    def test_account_create_api(self):
        from django.test import override_settings
        import json as _json
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            resp = self.client.post('/api/accounts/create/',
                                    data=_json.dumps({'name': 'Нова картка', 'currency': 'USD',
                                                      'initial_balance': '300'}),
                                    content_type='application/json', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        self.assertTrue(Account.objects.filter(name='Нова картка', currency='USD').exists())


class AccountIconTests(TestCase):
    FIN_HOST = 'fin.twocomms.shop'

    def setUp(self):
        self.user = User.objects.create_superuser('fin_ic', 'ic@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='Картка', currency='UAH',
                                          initial_balance=Decimal('0'), current_balance=Decimal('0'))
        self.client.force_login(self.user)

    def _png_bytes(self, size=(400, 250), color=(200, 80, 40)):
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', size, color).save(buf, format='PNG')
        return buf.getvalue()

    def test_process_icon_returns_webp_datauri(self):
        from finance import account_icons
        result = account_icons.process_account_icon(io.BytesIO(self._png_bytes()))
        self.assertTrue(result.startswith('data:image/webp;base64,'))
        # Стиснута іконка має бути дуже легкою (кілька КБ).
        self.assertLess(len(result), 20000)

    def test_process_icon_rejects_garbage(self):
        from finance import account_icons
        with self.assertRaises(ValueError):
            account_icons.process_account_icon(io.BytesIO(b'not-an-image'))

    def test_update_sets_emoji_icon(self):
        from django.test import override_settings
        import json as _json
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            resp = self.client.post(f'/api/accounts/{self.acc.id}/update/',
                                    data=_json.dumps({'icon_type': 'emoji', 'icon_value': '💳'}),
                                    content_type='application/json', HTTP_HOST=self.FIN_HOST)
        self.assertTrue(resp.json()['ok'])
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.icon_type, 'emoji')
        self.assertEqual(self.acc.icon_value, '💳')

    def test_update_image_upload_and_clear_on_switch(self):
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile('card.png', self._png_bytes(), content_type='image/png')
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            resp = self.client.post(f'/api/accounts/{self.acc.id}/update/',
                                    data={'name': 'Картка', 'icon_type': 'image', 'icon_image': upload},
                                    HTTP_HOST=self.FIN_HOST)
        self.assertTrue(resp.json()['ok'])
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.icon_type, 'image')
        self.assertTrue(self.acc.icon_image.startswith('data:image/webp;base64,'))
        # Перемикання на емодзі прибирає збережене зображення.
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            self.client.post(f'/api/accounts/{self.acc.id}/update/',
                             data={'name': 'Картка', 'icon_type': 'emoji', 'icon_value': '🏦'},
                             HTTP_HOST=self.FIN_HOST)
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.icon_type, 'emoji')
        self.assertEqual(self.acc.icon_image, '')

    def test_accounts_page_renders_icon_picker(self):
        from django.test import override_settings
        self.acc.icon_type = 'bank'
        self.acc.icon_value = 'mono'
        self.acc.save()
        with override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver']):
            resp = self.client.get('/accounts/', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Іконка-картка')
        self.assertContains(resp, 'fin-acc-icon--bank')
