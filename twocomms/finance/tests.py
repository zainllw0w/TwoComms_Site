"""Тести каркаса фінансового кабінету (Блок 1): доступ і маршрутизація."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

User = get_user_model()

FIN_HOST = 'fin.twocomms.shop'


@override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'])
class FinanceAccessTests(TestCase):
    """Доступ до кабінету мають лише staff/superuser."""

    def setUp(self):
        self.admin = User.objects.create_user('fin_admin', password='x', is_staff=True)
        self.superuser = User.objects.create_superuser('fin_root', 'root@x.com', 'x')
        self.plain = User.objects.create_user('plain_user', password='x')

    def _get_home(self):
        # Емуляція піддомену fin.* через HTTP_HOST → urls_fin.
        return self.client.get('/', HTTP_HOST=FIN_HOST)

    def test_anonymous_redirected_to_login(self):
        resp = self._get_home()
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_plain_user_forbidden(self):
        self.client.force_login(self.plain)
        resp = self._get_home()
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_access(self):
        self.client.force_login(self.admin)
        resp = self._get_home()
        self.assertEqual(resp.status_code, 200)

    def test_superuser_can_access(self):
        self.client.force_login(self.superuser)
        resp = self._get_home()
        self.assertEqual(resp.status_code, 200)

    def test_all_sections_render_for_admin(self):
        self.client.force_login(self.admin)
        for path in ('/', '/analytic/', '/ai/', '/calendar/', '/invoices/', '/rules/', '/users/', '/accounts/'):
            resp = self.client.get(path, HTTP_HOST=FIN_HOST)
            self.assertEqual(resp.status_code, 200, f'{path} → {resp.status_code}')
