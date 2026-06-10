from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, Client as TestClient, override_settings
from django.urls import reverse

from management.models import CommercialOfferEmailLog

HOST = "management.twocomms.shop"


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class SendTestTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cp_send", password="x", is_staff=True, email="mgr@example.com"
        )
        self.http = TestClient()
        self.http.force_login(self.user)

    def test_send_test_uses_manager_email_no_log(self):
        url = reverse("management_commercial_offer_email_send_test_api")
        before = CommercialOfferEmailLog.objects.count()
        resp = self.http.post(url, data={"recipient_name": "X", "mode": "VISUAL"}, HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("mgr@example.com", mail.outbox[0].to)
        # Test send must not create a log entry.
        self.assertEqual(CommercialOfferEmailLog.objects.count(), before)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class ProductsApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cp_prod", password="x", is_staff=True
        )
        self.http = TestClient()
        self.http.force_login(self.user)

    def test_products_api_ok(self):
        url = reverse("management_commercial_offer_email_products_api")
        resp = self.http.get(url, HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("ok"))

    def test_products_api_forbidden_for_anon(self):
        url = reverse("management_commercial_offer_email_products_api")
        resp = TestClient().get(url, HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 403)
