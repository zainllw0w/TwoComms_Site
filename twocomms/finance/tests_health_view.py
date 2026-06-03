"""Тест рендеру сторінки «Фінансове здоров'я» з новим рушієм."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import Account, Transaction, get_default_company

User = get_user_model()
FIN_HOST = 'fin.twocomms.shop'


@override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'])
class HealthViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = get_default_company()
        cls.admin = User.objects.create_superuser('hs_admin', 'a@a.com', 'pass12345')
        cls.biz = Account.objects.create(
            company=cls.company, name='ФОП', currency='UAH', is_business=True)
        Transaction.objects.create(
            company=cls.company, type=Transaction.TYPE_INCOME,
            status=Transaction.STATUS_ACTUAL, amount=Decimal('8000'),
            amount_base=Decimal('8000'), currency='UAH', account=cls.biz,
            date_actual=timezone.now(), is_business=True)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)

    def test_health_page_renders(self):
        r = self.client.get('/health/', HTTP_HOST=FIN_HOST, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Фінансове здоров\'я')
        self.assertContains(r, 'Довіра до оцінки')
        self.assertContains(r, 'fin-hs-hero')
        # Sub-scores присутні.
        self.assertContains(r, 'Бізнес')
        self.assertContains(r, 'Межа')
