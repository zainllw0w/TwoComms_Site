"""Тести Блоку 7: рахунки-фактури — підсумки, оплата, статуси, рендер."""
from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from finance.models import Account, Invoice, get_default_company
from finance.services import invoices as inv_service

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'])
class InvoiceTests(TestCase):
    FIN_HOST = 'fin.twocomms.shop'

    def setUp(self):
        self.user = User.objects.create_superuser('fin_inv', 'inv@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='Банк', currency='UAH',
                                           initial_balance=Decimal('0'), current_balance=Decimal('0'))

    def _make(self, vat=False, discount='0', delivery='0'):
        return inv_service.save_invoice(user=self.user, data={
            'currency': 'UAH', 'vat_enabled': vat, 'vat_rate': '20',
            'discount_amount': discount, 'delivery_amount': delivery,
            'payer_name': 'ТОВ Клієнт',
            'items': [{'name': 'Товар', 'quantity': '2', 'unit_price': '500'},
                      {'name': 'Послуга', 'quantity': '1', 'unit_price': '300'}],
        })

    def test_totals_without_vat(self):
        inv = self._make()
        self.assertEqual(inv.subtotal, Decimal('1300.00'))
        self.assertEqual(inv.total_amount, Decimal('1300.00'))

    def test_totals_with_vat_discount_delivery(self):
        inv = self._make(vat=True, discount='100', delivery='50')
        # subtotal 1300, tax 20% = 260, total = 1300 - 100 + 50 + 260 = 1510
        self.assertEqual(inv.subtotal, Decimal('1300.00'))
        self.assertEqual(inv.tax_amount, Decimal('260.00'))
        self.assertEqual(inv.total_amount, Decimal('1510.00'))

    def test_payment_updates_status_and_balance(self):
        inv = self._make()
        inv.status = Invoice.STATUS_ISSUED
        inv.save()
        # Часткова оплата.
        inv_service.create_payment_for_invoice(inv, user=self.user, account=self.acc, amount=Decimal('500'))
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.STATUS_PARTIAL)
        self.assertEqual(inv.balance_due, Decimal('800.00'))
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.current_balance, Decimal('500'))
        # Повна оплата.
        inv_service.create_payment_for_invoice(inv, user=self.user, account=self.acc)
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.STATUS_PAID)

    def test_invoices_page_and_form_render(self):
        self.client.force_login(self.user)
        self._make()
        resp = self.client.get('/invoices/', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        resp2 = self.client.get('/invoices/new/', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, 'Дані постачальника')

    def test_save_api(self):
        self.client.force_login(self.user)
        resp = self.client.post('/api/invoices/save/', data=json.dumps({
            'currency': 'UAH', 'payer_name': 'Клієнт',
            'items': [{'name': 'X', 'quantity': '1', 'unit_price': '999'}],
        }), content_type='application/json', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
