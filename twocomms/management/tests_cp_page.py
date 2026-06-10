from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient, override_settings
from django.urls import reverse

HOST = "management.twocomms.shop"
MGMT = override_settings(ROOT_URLCONF="twocomms.urls_management")


@MGMT
class CommercialOfferPageRenderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cp_page_mgr", password="x", is_staff=True
        )
        self.http = TestClient()
        self.http.force_login(self.user)

    def test_cp_page_renders_200(self):
        url = reverse("management_commercial_offer_email")
        resp = self.http.get(url, HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        # Key revamp elements present.
        self.assertIn("offer-kpi-strip", body)
        self.assertIn("offer-cp-link-modal", body)
        self.assertIn("offer-cp-process-modal", body)
        self.assertIn("offer-preview-visual", body)
        self.assertIn("offer-send-test", body)
