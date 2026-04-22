from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from orders.models import Order
from storefront.models import PageView, SiteSession, UserAction
from storefront.analytics_audience import ANALYTICS_SCOPE_ADMIN, ANALYTICS_SCOPE_KEY, ANALYTICS_SCOPE_REASON_KEY
from storefront.services.admin_analytics import build_integration_status_widget, parse_analytics_filters


class AdminAnalyticsApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(
            HTTP_HOST="twocomms.shop",
            SERVER_PORT="443",
            **{"wsgi.url_scheme": "https"},
        )
        self.staff = User.objects.create_user(username="staff", password="pass1234", is_staff=True)
        self.user = User.objects.create_user(username="user", password="pass1234")

    def _create_paid_order(self, *, user=None, session_key=None, total="1200.00"):
        return Order.objects.create(
            user=user,
            session_key=session_key,
            full_name="Buyer",
            phone="+380991112233",
            city="Kyiv",
            np_office="1",
            pay_type="online_full",
            total_sum=Decimal(total),
            status="new",
            payment_status="paid",
        )

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

    def test_bundle_supports_compare_mode_for_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            "/api/admin/analytics/?period=month&compare_to=previous_period",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("comparison", payload["overview"]["data"])
        self.assertIn("orders", payload["overview"]["data"]["comparison"])

    def test_products_widget_endpoint_is_available_for_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get("/api/admin/analytics/products/?period=month", secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("data", payload)
        self.assertEqual(payload.get("source"), "internal")

    def test_sales_widget_endpoint_is_available_for_staff(self):
        Order.objects.create(
            full_name="Buyer",
            phone="+380991112233",
            city="Kyiv",
            np_office="1",
            pay_type="online_full",
            total_sum=Decimal("1200.00"),
            status="new",
            payment_status="paid",
        )

        self.client.force_login(self.staff)
        response = self.client.get("/api/admin/analytics/sales/?period=month", secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("daily_series", payload["data"])
        self.assertEqual(payload.get("source"), "internal")

    def test_admin_panel_stats_section_renders_new_dashboard_shell(self):
        self.client.force_login(self.staff)
        response = self.client.get("/admin-panel/?section=stats", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "adminAnalyticsConfig")
        self.assertContains(response, "analyticsOverviewChart")

    @patch("storefront.services.admin_analytics.get_clarity_status")
    @patch("storefront.services.admin_analytics.get_ga4_status")
    def test_integration_status_uses_live_checks_and_does_not_raise_false_ip_warning(self, ga4_mock, clarity_mock):
        cache.clear()
        ga4_mock.return_value = {
            "key": "ga4",
            "label": "GA4 Data API",
            "status": "healthy",
            "message": "GA4 ok",
            "details": {"configured": True},
        }
        clarity_mock.return_value = {
            "key": "clarity",
            "label": "Microsoft Clarity",
            "status": "healthy",
            "message": "Clarity ok",
            "details": {"configured": True},
        }
        SiteSession.objects.create(
            session_key="ip-session",
            ip_address="188.163.49.54",
            visitor_id="vid-1",
            pageviews=1,
            last_path="/",
        )

        widget = build_integration_status_widget(parse_analytics_filters({}))
        cached_widget = build_integration_status_widget(parse_analytics_filters({}))

        ga4_mock.assert_called_once_with(test_connection=True)
        clarity_mock.assert_called_once_with(test_connection=False)
        self.assertEqual(widget["data"]["integrations"][1]["status"], "healthy")
        self.assertEqual(cached_widget["data"]["integrations"][2]["details"]["live_check_deferred"], True)
        self.assertNotIn(
            "IP capture нижче 75%: перед використанням unique-IP KPI перевірити production reverse proxy.",
            widget["data"]["warnings"],
        )

    def test_dashboard_metrics_ignore_technical_only_session_noise(self):
        human_session = SiteSession.objects.create(
            session_key="human-session",
            ip_address="188.163.49.54",
            visitor_id="vid-human",
            pageviews=2,
            last_path="/favorites/count/",
        )
        PageView.objects.create(session=human_session, path="/catalog/", referrer="", is_bot=False)
        PageView.objects.create(session=human_session, path="/favorites/count/", referrer="", is_bot=False)

        noise_session = SiteSession.objects.create(
            session_key="noise-session",
            ip_address="188.163.49.55",
            visitor_id="vid-noise",
            pageviews=1,
            last_path="/sw.js",
        )
        PageView.objects.create(session=noise_session, path="/sw.js", referrer="", is_bot=False)

        self.client.force_login(self.staff)
        response = self.client.get("/api/admin/analytics/?period=month", secure=True)
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["overview"]["data"]["headline"]["sessions"], 1)
        self.assertEqual(payload["overview"]["data"]["headline"]["page_views"], 1)

    def test_dashboard_excludes_staff_activity_from_public_kpis_and_reports_it_separately(self):
        public_session = SiteSession.objects.create(
            session_key="public-session",
            user=self.user,
            ip_address="188.163.49.58",
            visitor_id="vid-public",
            pageviews=1,
            last_path="/catalog/",
            first_touch_data={ANALYTICS_SCOPE_KEY: "public", ANALYTICS_SCOPE_REASON_KEY: "public_traffic"},
        )
        PageView.objects.create(session=public_session, user=self.user, path="/catalog/", referrer="", is_bot=False)
        UserAction.objects.create(
            site_session=public_session,
            user=self.user,
            action_type="add_to_cart",
            product_id=1,
            product_name="Public product",
            metadata={"visitor_id": "vid-public", ANALYTICS_SCOPE_KEY: "public"},
        )
        self._create_paid_order(user=self.user, session_key="public-session", total="1200.00")

        staff_session = SiteSession.objects.create(
            session_key="staff-session",
            user=self.staff,
            ip_address="188.163.49.59",
            visitor_id="vid-staff",
            pageviews=1,
            last_path="/catalog/",
            first_touch_data={
                ANALYTICS_SCOPE_KEY: ANALYTICS_SCOPE_ADMIN,
                ANALYTICS_SCOPE_REASON_KEY: "staff_user",
            },
        )
        PageView.objects.create(session=staff_session, user=self.staff, path="/catalog/", referrer="", is_bot=False)
        UserAction.objects.create(
            site_session=staff_session,
            user=self.staff,
            action_type="add_to_cart",
            product_id=2,
            product_name="Staff product",
            metadata={"visitor_id": "vid-staff", ANALYTICS_SCOPE_KEY: ANALYTICS_SCOPE_ADMIN},
        )
        self._create_paid_order(user=self.staff, session_key="staff-session", total="500.00")

        self.client.force_login(self.staff)
        response = self.client.get("/api/admin/analytics/?period=month", secure=True)
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        headline = payload["overview"]["data"]["headline"]
        excluded = payload["overview"]["data"]["excluded_activity"]

        self.assertEqual(headline["sessions"], 1)
        self.assertEqual(headline["cart_adds"], 1)
        self.assertEqual(headline["orders"], 1)
        self.assertEqual(headline["revenue"], 1200.0)

        self.assertEqual(excluded["sessions"], 1)
        self.assertEqual(excluded["cart_adds"], 1)
        self.assertEqual(excluded["orders"], 1)
        self.assertEqual(excluded["revenue"], 500.0)

        cart_response = self.client.get("/api/admin/analytics/cart/?period=month", secure=True)
        self.assertEqual(cart_response.status_code, 200)
        cart_payload = cart_response.json()
        self.assertEqual(cart_payload["data"]["summary"]["adds"], 1)
        self.assertEqual(cart_payload["data"]["excluded_activity"]["adds"], 1)
        self.assertEqual(payload["overview"]["data"]["headline"]["bounce_rate"], 100.0)

    def test_dashboard_keeps_real_favorites_page_traffic(self):
        favorites_session = SiteSession.objects.create(
            session_key="favorites-session",
            ip_address="188.163.49.56",
            visitor_id="vid-favorites",
            pageviews=1,
            last_path="/favorites/",
        )
        PageView.objects.create(session=favorites_session, path="/favorites/", referrer="", is_bot=False)

        self.client.force_login(self.staff)
        response = self.client.get("/api/admin/analytics/?period=month", secure=True)
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["overview"]["data"]["headline"]["sessions"], 1)
        self.assertEqual(payload["overview"]["data"]["headline"]["page_views"], 1)
