"""Тест службового ендпоінта service worker (scope '/' для PWA)."""
from __future__ import annotations

from django.test import Client, TestCase, override_settings


@override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'], ROOT_URLCONF='twocomms.urls_fin')
class FinanceServiceWorkerTests(TestCase):
    def test_sw_served_from_root_with_allowed_header(self):
        c = Client()
        r = c.get('/finance-sw.js', HTTP_HOST='fin.twocomms.shop', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn('javascript', r['Content-Type'])
        self.assertEqual(r['Service-Worker-Allowed'], '/')
        # Має містити код SW (push-обробник).
        body = r.content.decode('utf-8')
        self.assertIn('addEventListener', body)
