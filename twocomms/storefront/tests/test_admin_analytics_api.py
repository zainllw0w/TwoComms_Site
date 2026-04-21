from django.contrib.auth.models import User
from django.test import Client, TestCase

from storefront.models import SiteSession, UserAction


class AdminAnalyticsApiTests(TestCase):
    def setUp(self):
        self.client = Client(
            HTTP_HOST="twocomms.shop",
            SERVER_PORT="443",
            **{"wsgi.url_scheme": "https"},
        )
        self.staff = User.objects.create_user(username="staff", password="pass1234", is_staff=True)
        self.user = User.objects.create_user(username="user", password="pass1234")

    def test_requires_staff_permissions(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/admin/analytics/", secure=True)
        self.assertEqual(response.status_code, 403)

    def test_returns_dashboard_bundle_for_staff(self):
        session = SiteSession.objects.create(session_key="analytics-session", pageviews=2, last_path="/product/test")
        UserAction.objects.create(
            site_session=session,
            action_type="product_view",
            product_id=1,
            product_name="Test",
            metadata={"visitor_id": "vid-1"},
        )

        self.client.force_login(self.staff)
        response = self.client.get("/api/admin/analytics/?period=month", secure=True)
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn("overview", payload)
        self.assertIn("timeseries", payload)
        self.assertIn("integration_status", payload)
        self.assertIn("data", payload["overview"])

    def test_products_widget_endpoint_is_available_for_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get("/api/admin/analytics/products/?period=month", secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("data", payload)
        self.assertEqual(payload.get("source"), "internal")

    def test_admin_panel_stats_section_renders_new_dashboard_shell(self):
        self.client.force_login(self.staff)
        response = self.client.get("/admin-panel/?section=stats", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "adminAnalyticsConfig")
        self.assertContains(response, "analyticsOverviewChart")
