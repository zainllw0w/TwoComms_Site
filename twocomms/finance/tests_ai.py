"""Тести Блоку 9: AI радник (rule-based відповіді та інструменти перевірки)."""
from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from finance.models import Account, Transaction, get_default_company
from finance.services import ai_advisor
from finance.services import transactions as txn_service

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'])
class AiAdvisorTests(TestCase):
    FIN_HOST = 'fin.twocomms.shop'

    def setUp(self):
        self.user = User.objects.create_superuser('fin_ai', 'ai@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='Банк', currency='UAH',
                                           initial_balance=Decimal('1000'), current_balance=Decimal('1000'))
        txn_service.create_transaction(user=self.user, type=Transaction.TYPE_INCOME,
                                       amount=Decimal('500'), account=self.acc, date_actual=timezone.now())

    def test_overview_intent(self):
        res = ai_advisor.answer(self.company, 'покажи загальну картину місяця')
        self.assertIn('доходи', res['answer'].lower())

    def test_expenses_intent(self):
        res = ai_advisor.answer(self.company, 'куди пішли гроші')
        self.assertTrue(res['answer'])

    def test_check_payments_returns_issues(self):
        issues = ai_advisor.check_payments(self.company)
        self.assertTrue(isinstance(issues, list) and len(issues) >= 1)

    def test_chat_api(self):
        self.client.force_login(self.user)
        resp = self.client.post('/api/ai/chat/', data=json.dumps({'question': 'прогноз залишку'}),
                                content_type='application/json', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

    def test_ai_page_renders(self):
        self.client.force_login(self.user)
        resp = self.client.get('/ai/', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Фінансовий чат')
