"""Тести Блоку 14: експорт відфільтрованих платежів (XLSX + XML)."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from finance.models import Account, Transaction, get_default_company
from finance.services import transactions as txn_service

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'])
class ExportTests(TestCase):
    FIN_HOST = 'fin.twocomms.shop'

    def setUp(self):
        self.user = User.objects.create_superuser('fin_exp', 'e@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='Каса', currency='UAH',
                                           initial_balance=Decimal('0'), current_balance=Decimal('0'))
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('333'), account=self.acc, comment='Експорт-тест')
        self.client.force_login(self.user)

    def test_xlsx_export(self):
        resp = self.client.get('/export/?format=xlsx', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])

    def test_xml_export_contains_data(self):
        resp = self.client.get('/export/?format=xml', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('xml', resp['Content-Type'])
        body = resp.content.decode('utf-8')
        self.assertIn('<payments', body)
        self.assertIn('Експорт-тест', body)
        self.assertIn('333', body)

    def test_export_respects_account_filter(self):
        acc2 = Account.objects.create(company=self.company, name='ФОП', currency='UAH')
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('777'), account=acc2, comment='інший рахунок')
        resp = self.client.get('/export/?format=xml&accounts=%s' % self.acc.id, HTTP_HOST=self.FIN_HOST)
        body = resp.content.decode('utf-8')
        self.assertIn('333', body)
        self.assertNotIn('777', body)
