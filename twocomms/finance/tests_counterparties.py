"""Тести розділу «Контрагенти»: рендер сторінок + CRUD API."""
from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import Account, Counterparty, Transaction, get_default_company

User = get_user_model()
FIN_HOST = 'fin.twocomms.shop'


@override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'])
class CounterpartiesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = get_default_company()
        cls.admin = User.objects.create_superuser('cp_admin', 'a@a.com', 'pass12345')
        cls.cp = Counterparty.objects.create(
            company=cls.company, name='ТОВ Тест', type='client', group='Опт')
        cls.acc = Account.objects.create(company=cls.company, name='ФОП', currency='UAH')
        now = timezone.now()
        Transaction.objects.create(
            company=cls.company, type=Transaction.TYPE_INCOME,
            status=Transaction.STATUS_ACTUAL, amount=Decimal('1000'),
            amount_base=Decimal('1000'), currency='UAH', account=cls.acc,
            counterparty=cls.cp, date_actual=now, is_business=True)
        Transaction.objects.create(
            company=cls.company, type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_ACTUAL, amount=Decimal('300'),
            amount_base=Decimal('300'), currency='UAH', account=cls.acc,
            counterparty=cls.cp, date_actual=now, is_business=True)
        Transaction.objects.create(
            company=cls.company, type=Transaction.TYPE_INCOME,
            status=Transaction.STATUS_PLANNED, amount=Decimal('500'),
            amount_base=Decimal('500'), currency='UAH', account=cls.acc,
            counterparty=cls.cp, date_actual=now + timezone.timedelta(days=5))

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)

    def test_list_page_renders(self):
        r = self.client.get('/counterparties/', HTTP_HOST=FIN_HOST, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ТОВ Тест')
        self.assertContains(r, 'Контрагенти')

    def test_detail_page_renders(self):
        r = self.client.get(f'/counterparties/{self.cp.id}/', HTTP_HOST=FIN_HOST, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ТОВ Тест')
        # Отримано 1000, сплачено 300.
        self.assertContains(r, 'Баланс співпраці')

    def test_create_api(self):
        r = self.client.post(
            '/api/counterparties/create/',
            data=json.dumps({'name': 'Новий ЧП', 'type': 'supplier',
                             'contacts': {'phone': '+380001112233'}}),
            content_type='application/json', HTTP_HOST=FIN_HOST, secure=True)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['ok'])
        cp = Counterparty.objects.get(id=body['id'])
        self.assertEqual(cp.name, 'Новий ЧП')
        self.assertEqual(cp.type, 'supplier')
        self.assertEqual(cp.contacts.get('phone'), '+380001112233')

    def test_update_api(self):
        r = self.client.post(
            f'/api/counterparties/{self.cp.id}/update/',
            data=json.dumps({'name': 'ТОВ Тест Оновлено', 'group': 'Роздріб'}),
            content_type='application/json', HTTP_HOST=FIN_HOST, secure=True)
        self.assertEqual(r.status_code, 200)
        self.cp.refresh_from_db()
        self.assertEqual(self.cp.name, 'ТОВ Тест Оновлено')
        self.assertEqual(self.cp.group, 'Роздріб')

    def test_delete_api_requires_force_with_txns(self):
        # Має операції → потребує force.
        r = self.client.post(
            f'/api/counterparties/{self.cp.id}/delete/',
            data=json.dumps({'force': 0}),
            content_type='application/json', HTTP_HOST=FIN_HOST, secure=True)
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.json().get('needs_force'))
        self.assertTrue(Counterparty.objects.filter(id=self.cp.id).exists())

        # З force → видаляється, операції лишаються без контрагента.
        r2 = self.client.post(
            f'/api/counterparties/{self.cp.id}/delete/',
            data=json.dumps({'force': 1}),
            content_type='application/json', HTTP_HOST=FIN_HOST, secure=True)
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(Counterparty.objects.filter(id=self.cp.id).exists())
        self.assertTrue(Transaction.objects.filter(account=self.acc).exists())

    def test_get_api(self):
        r = self.client.get(f'/api/counterparties/{self.cp.id}/get/',
                            HTTP_HOST=FIN_HOST, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['counterparty']['name'], 'ТОВ Тест')
