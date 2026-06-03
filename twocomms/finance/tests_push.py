"""Тести push-сервісу фінансів (звіти + відправка з моком pywebpush)."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Account, Transaction, get_default_company
from .models_settings import PushSubscription, NotificationLog
from .services import push as push_service

User = get_user_model()


@override_settings(
    WEB_PUSH_ENABLED=True,
    WEB_PUSH_VAPID_PUBLIC_KEY='test-pub',
    WEB_PUSH_VAPID_PRIVATE_KEY='test-priv',
    WEB_PUSH_VAPID_SUBJECT='mailto:test@twocomms.shop',
    SITE_BASE_URL='https://fin.twocomms.shop',
    ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'],
)
class PushServiceTests(TestCase):
    def setUp(self):
        self.company = get_default_company()
        self.user = User.objects.create_superuser('push_admin', 'a@a.com', 'pass12345')
        self.acc = Account.objects.create(
            company=self.company, name='ФОП', currency='UAH', is_business=True)
        Transaction.objects.create(
            company=self.company, type=Transaction.TYPE_INCOME,
            status=Transaction.STATUS_ACTUAL, amount=Decimal('1500'),
            amount_base=Decimal('1500'), currency='UAH', account=self.acc,
            date_actual=timezone.now(), is_business=True)
        self.sub = PushSubscription.objects.create(
            user=self.user, endpoint='https://push.example/abc',
            p256dh='p256dh-key', auth='auth-key', is_active=True)

    def test_daily_report_content(self):
        r = push_service.build_daily_report(self.company)
        self.assertIn('title', r)
        self.assertIn('body', r)
        self.assertIn('Баланс', r['body'])

    def test_weekly_report_content(self):
        r = push_service.build_weekly_report(self.company)
        self.assertIn('здоров', r['body'].lower())
        self.assertIn('health_score', r['data'])

    @patch('finance.services.push.webpush')
    def test_send_to_user_success(self, mocked):
        mocked.return_value = SimpleNamespace(status_code=201)
        res = push_service.send_to_user(self.user, 'Тест', 'Тіло', url='/health/')
        self.assertTrue(res['ok'])
        self.assertEqual(res['sent'], 1)
        self.assertTrue(NotificationLog.objects.filter(user=self.user).exists())

    @patch('finance.services.push.webpush')
    def test_send_deactivates_gone_subscription(self, mocked):
        from finance.services.push import WebPushException
        resp = SimpleNamespace(status_code=410)
        mocked.side_effect = WebPushException('gone', response=resp)
        res = push_service.send_to_user(self.user, 'Тест', 'Тіло')
        self.assertEqual(res['failed'], 1)
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.is_active)

    def test_test_push_api(self):
        from django.test import Client
        c = Client()
        c.force_login(self.user)
        with patch('finance.services.push.webpush') as mocked:
            mocked.return_value = SimpleNamespace(status_code=201)
            r = c.post('/api/push/test/', HTTP_HOST='fin.twocomms.shop', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])

    @override_settings(WEB_PUSH_ENABLED=False)
    def test_not_configured(self):
        self.assertFalse(push_service.is_configured())
        res = push_service.send_to_user(self.user, 'x', 'y')
        self.assertFalse(res['ok'])
