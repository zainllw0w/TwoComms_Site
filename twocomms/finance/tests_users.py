"""Тести Блоку 10: користувачі (доступи) та панель ефективності."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from finance.models import Account, get_default_company
from finance.views.users import effectiveness

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['fin.twocomms.shop', 'testserver'])
class UsersTests(TestCase):
    FIN_HOST = 'fin.twocomms.shop'

    def setUp(self):
        self.owner = User.objects.create_superuser('owner', 'o@x.com', 'x')
        self.admin = User.objects.create_user('mgr', password='x', is_staff=True)
        self.plain = User.objects.create_user('plain', password='x')
        self.company = get_default_company()

    def test_users_page_lists_only_admins(self):
        self.client.force_login(self.owner)
        resp = self.client.get('/users/', HTTP_HOST=self.FIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'owner')
        self.assertContains(resp, 'mgr')
        self.assertNotContains(resp, '>plain<')

    def test_effectiveness_grows_with_setup(self):
        eff0 = effectiveness(self.company)
        Account.objects.create(company=self.company, name='Банк', currency='UAH',
                               initial_balance=Decimal('0'), current_balance=Decimal('0'))
        eff1 = effectiveness(self.company)
        self.assertGreaterEqual(eff1['done'], eff0['done'] + 1)
        self.assertLessEqual(eff1['percent'], 100)
