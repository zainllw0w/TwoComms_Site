import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from storefront.models import (
    PushNotificationCampaign,
    PushNotificationDelivery,
    WebPushDeviceSubscription,
)
from storefront.context_processors import web_push_settings
from storefront.services import web_push as web_push_service
from storefront.services.web_push import (
    WebPushConfigurationError,
    build_campaign_payload,
)


@override_settings(
    COMPRESS_ENABLED=False,
    COMPRESS_OFFLINE=False,
    WEB_PUSH_ENABLED=True,
    WEB_PUSH_VAPID_PUBLIC_KEY="test-public-key",
    WEB_PUSH_VAPID_PRIVATE_KEY="test-private-key",
    WEB_PUSH_VAPID_SUBJECT="mailto:test@example.com",
    SITE_BASE_URL="https://twocomms.shop",
)
class WebPushFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = Client(
            HTTP_HOST="twocomms.shop",
            SERVER_PORT="443",
            **{"wsgi.url_scheme": "https"},
        )
        self.request_factory = RequestFactory()
        self.user_model = get_user_model()
        self.staff_user = self.user_model.objects.create_user(
            username="push_admin",
            password="secret123",
            is_staff=True,
        )

    def _subscription_payload(self, **overrides):
        payload = {
            "subscription": {
                "endpoint": "https://push.example.test/subscription-1",
                "keys": {
                    "auth": "auth-token",
                    "p256dh": "p256dh-token",
                },
            },
            "installation_id": "install-1",
            "device_type": "desktop",
            "browser_family": "Chrome",
            "operating_system": "macOS",
            "language": "uk-UA",
            "timezone": "Europe/Kiev",
            "last_seen_path": "/catalog/",
        }
        payload.update(overrides)
        return payload

    def test_push_subscribe_creates_subscription(self):
        response = self.client.post(
            reverse("push_subscribe"),
            data=json.dumps(self._subscription_payload()),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        subscription = WebPushDeviceSubscription.objects.get()
        self.assertEqual(subscription.installation_id, "install-1")
        self.assertEqual(subscription.browser_family, "Chrome")
        self.assertTrue(subscription.is_active)

    def test_push_subscribe_stores_authenticated_user_preference_snapshot(self):
        user = self.user_model.objects.create_user(
            username="push_customer",
            password="secret123",
        )
        user.userprofile.push_marketing_enabled = False
        user.userprofile.push_order_updates_enabled = True
        user.userprofile.save(update_fields=["push_marketing_enabled", "push_order_updates_enabled"])
        self.client.force_login(user)

        response = self.client.post(
            reverse("push_subscribe"),
            data=json.dumps(self._subscription_payload()),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        subscription = WebPushDeviceSubscription.objects.get()
        self.assertEqual(subscription.user, user)
        self.assertEqual(
            subscription.metadata["user_preferences"],
            {
                "marketing_enabled": False,
                "order_updates_enabled": True,
            },
        )

    def test_push_subscribe_rejects_requests_without_pywebpush_dependency(self):
        with patch.object(web_push_service, "webpush", None):
            response = self.client.post(
                reverse("push_subscribe"),
                data=json.dumps(self._subscription_payload()),
                content_type="application/json",
                secure=True,
            )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {"ok": False, "error": "Web Push is not configured."},
        )

    def test_is_web_push_configured_reloads_dependency_if_it_appears_later(self):
        with patch.object(web_push_service, "webpush", None):
            with patch.object(web_push_service, "_webpush_dependency_resolved", False):
                with patch(
                    "storefront.services.web_push.import_module",
                    return_value=SimpleNamespace(
                        webpush=lambda **kwargs: None,
                        WebPushException=RuntimeError,
                    ),
                ):
                    self.assertTrue(web_push_service.is_web_push_configured())

    def test_send_campaign_raises_configuration_error_without_pywebpush_dependency(self):
        campaign = PushNotificationCampaign.objects.create(
            title="Нове повідомлення",
            body="Тест push-повідомлення",
            target_url="/catalog/",
            created_by=self.staff_user,
        )

        with patch.object(web_push_service, "webpush", None):
            with self.assertRaisesMessage(
                WebPushConfigurationError,
                "pywebpush dependency is not installed",
            ):
                web_push_service.send_campaign(campaign)

    @patch("storefront.services.web_push.webpush")
    def test_send_campaign_converts_pem_vapid_key_to_vapid_object(self, mocked_webpush):
        fake_vapid = object()
        mocked_webpush.return_value = SimpleNamespace(status_code=201)
        campaign = PushNotificationCampaign.objects.create(
            title="PEM key send",
            body="Тест PEM ключа",
            target_url="/catalog/",
            created_by=self.staff_user,
        )
        WebPushDeviceSubscription.objects.create(
            installation_id="install-pem",
            endpoint="https://push.example.test/subscription-pem",
            auth_key="auth-token",
            p256dh_key="p256dh-token",
            browser_family="Chrome",
            operating_system="macOS",
            device_type=WebPushDeviceSubscription.DeviceType.DESKTOP,
            is_active=True,
        )

        pem_key = "\n".join(
            [
                "-----BEGIN PRIVATE KEY-----",
                "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgDUMMYKEYDATA",
                "-----END PRIVATE KEY-----",
            ]
        )

        with override_settings(WEB_PUSH_VAPID_PRIVATE_KEY=pem_key):
            with patch(
                "storefront.services.web_push.import_module",
                return_value=SimpleNamespace(
                    Vapid01=SimpleNamespace(from_pem=lambda key: fake_vapid)
                ),
            ):
                web_push_service.send_campaign(campaign)

        self.assertIs(mocked_webpush.call_args.kwargs["vapid_private_key"], fake_vapid)

    @patch("storefront.services.web_push.webpush")
    def test_send_campaign_skips_users_with_marketing_push_disabled(self, mocked_webpush):
        mocked_webpush.return_value = SimpleNamespace(status_code=201)
        enabled_user = self.user_model.objects.create_user(
            username="push_enabled",
            password="secret123",
        )
        disabled_user = self.user_model.objects.create_user(
            username="push_disabled",
            password="secret123",
        )
        disabled_user.userprofile.push_marketing_enabled = False
        disabled_user.userprofile.save(update_fields=["push_marketing_enabled"])

        campaign = PushNotificationCampaign.objects.create(
            title="Маркетинговий push",
            body="Тестова маркетингова кампанія",
            target_url="/catalog/",
            created_by=self.staff_user,
        )
        WebPushDeviceSubscription.objects.create(
            user=enabled_user,
            installation_id="install-enabled",
            endpoint="https://push.example.test/subscription-enabled",
            auth_key="auth-token",
            p256dh_key="p256dh-token",
            browser_family="Chrome",
            operating_system="macOS",
            device_type=WebPushDeviceSubscription.DeviceType.DESKTOP,
            is_active=True,
        )
        WebPushDeviceSubscription.objects.create(
            user=disabled_user,
            installation_id="install-disabled",
            endpoint="https://push.example.test/subscription-disabled",
            auth_key="auth-token",
            p256dh_key="p256dh-token",
            browser_family="Chrome",
            operating_system="macOS",
            device_type=WebPushDeviceSubscription.DeviceType.DESKTOP,
            is_active=True,
        )
        WebPushDeviceSubscription.objects.create(
            installation_id="install-anon",
            endpoint="https://push.example.test/subscription-anon",
            auth_key="auth-token",
            p256dh_key="p256dh-token",
            browser_family="Chrome",
            operating_system="macOS",
            device_type=WebPushDeviceSubscription.DeviceType.DESKTOP,
            is_active=True,
        )

        result = web_push_service.send_campaign(campaign)
        endpoints = [
            call.kwargs["subscription_info"]["endpoint"]
            for call in mocked_webpush.call_args_list
        ]

        self.assertEqual(result["sent"], 2)
        self.assertIn("https://push.example.test/subscription-enabled", endpoints)
        self.assertIn("https://push.example.test/subscription-anon", endpoints)
        self.assertNotIn("https://push.example.test/subscription-disabled", endpoints)

    def test_home_page_embeds_web_push_config(self):
        response = self.client.get(reverse("home"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="web-push-config"')
        self.assertContains(response, reverse("push_subscribe"))
        self.assertContains(response, "test-public-key")
        self.assertContains(response, "/sw.js")
        self.assertContains(response, 'name="apple-mobile-web-app-capable" content="yes"')

    def test_static_service_worker_path_points_to_existing_asset(self):
        response = self.client.get(reverse("home"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/sw.js")
        self.assertTrue(finders.find("sw.js"))

    def test_home_page_contains_pwa_head_metadata(self):
        response = self.client.get(reverse("home"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "viewport-fit=cover")
        self.assertContains(response, "apple-mobile-web-app-capable")
        self.assertContains(response, "site.webmanifest")
        self.assertContains(response, "css/web-push.css")

    def test_service_worker_route_serves_root_worker_with_cache_headers(self):
        response = self.client.get(reverse("service_worker_js"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "networkFirstNavigation")
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("must-revalidate", response["Cache-Control"])

    def test_manifest_contains_install_metadata_and_existing_shortcuts(self):
        manifest_path = finders.find("site.webmanifest")

        self.assertTrue(manifest_path)
        with open(manifest_path, "r", encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)

        self.assertEqual(manifest["id"], "/")
        self.assertEqual(manifest["start_url"], "/?source=pwa")
        self.assertIn("standalone", manifest["display_override"])
        self.assertEqual(manifest["launch_handler"]["client_mode"], "focus-existing")

        for icon in manifest["icons"]:
            self.assertTrue(finders.find(icon["src"].replace("/static/", "", 1)))

        for shortcut in manifest["shortcuts"]:
            for icon in shortcut.get("icons", []):
                self.assertTrue(finders.find(icon["src"].replace("/static/", "", 1)))

    def test_new_subscription_deactivates_previous_same_installation(self):
        old_subscription = WebPushDeviceSubscription.objects.create(
            installation_id="install-1",
            endpoint="https://push.example.test/old-subscription",
            auth_key="old-auth",
            p256dh_key="old-p256dh",
            browser_family="Chrome",
            operating_system="macOS",
            device_type=WebPushDeviceSubscription.DeviceType.DESKTOP,
            is_active=True,
        )

        payload = self._subscription_payload()
        payload["subscription"]["endpoint"] = "https://push.example.test/new-subscription"
        response = self.client.post(
            reverse("push_subscribe"),
            data=json.dumps(payload),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        old_subscription.refresh_from_db()
        self.assertFalse(old_subscription.is_active)
        self.assertTrue(
            WebPushDeviceSubscription.objects.filter(
                endpoint="https://push.example.test/new-subscription",
                is_active=True,
            ).exists()
        )

    def test_push_delivery_events_update_campaign_metrics(self):
        campaign = PushNotificationCampaign.objects.create(
            title="Нове повідомлення",
            body="Тест push-повідомлення",
            target_url="/catalog/",
            created_by=self.staff_user,
        )
        subscription = WebPushDeviceSubscription.objects.create(
            installation_id="install-1",
            endpoint="https://push.example.test/subscription-1",
            auth_key="auth-token",
            p256dh_key="p256dh-token",
            browser_family="Chrome",
            operating_system="macOS",
            device_type=WebPushDeviceSubscription.DeviceType.DESKTOP,
            is_active=True,
        )
        delivery = PushNotificationDelivery.objects.create(
            campaign=campaign,
            subscription=subscription,
            status=PushNotificationDelivery.Status.SENT,
            sent_at=timezone.now(),
        )

        display_response = self.client.post(
            reverse("push_delivery_event"),
            data=json.dumps(
                {
                    "event_type": "displayed",
                    "delivery_token": str(delivery.event_token),
                }
            ),
            content_type="application/json",
            secure=True,
        )
        click_response = self.client.post(
            reverse("push_delivery_event"),
            data=json.dumps(
                {
                    "event_type": "clicked",
                    "delivery_token": str(delivery.event_token),
                }
            ),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(display_response.status_code, 204)
        self.assertEqual(click_response.status_code, 204)

        delivery.refresh_from_db()
        campaign.refresh_from_db()
        self.assertIsNotNone(delivery.displayed_at)
        self.assertIsNotNone(delivery.clicked_at)
        self.assertEqual(campaign.displayed_count, 1)
        self.assertEqual(campaign.clicked_count, 1)

    def test_campaign_payload_omits_image_when_campaign_has_no_upload(self):
        campaign = PushNotificationCampaign.objects.create(
            title="Fallback image",
            body="Тест без картинки",
            target_url="/catalog/",
            created_by=self.staff_user,
        )
        subscription = WebPushDeviceSubscription.objects.create(
            installation_id="install-fallback",
            endpoint="https://push.example.test/subscription-fallback",
            auth_key="auth-token",
            p256dh_key="p256dh-token",
            browser_family="Chrome",
            operating_system="macOS",
            device_type=WebPushDeviceSubscription.DeviceType.DESKTOP,
            is_active=True,
        )
        delivery = PushNotificationDelivery.objects.create(
            campaign=campaign,
            subscription=subscription,
        )

        payload = build_campaign_payload(campaign, delivery)

        self.assertNotIn("image", payload)
        self.assertEqual(
            payload["icon"],
            "https://twocomms.shop/static/img/favicon-192x192.png",
        )

    def test_staff_admin_panel_renders_push_notifications_section(self):
        PushNotificationCampaign.objects.create(
            title="Без картинки",
            body="Кампанія без медіа",
            target_url="/catalog/",
            created_by=self.staff_user,
        )
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("admin_panel"),
            {"section": "push_notifications"},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Push Control Center")
        self.assertContains(response, "Нова push-кампанія")
        self.assertNotContains(response, "Що ще потрібно для продакшна")
        self.assertContains(response, "Без зображення")
        self.assertContains(response, "push-history-scroll")
        self.assertContains(response, 'data-label="Статус"')

    @override_settings(ROOT_URLCONF="django.contrib.auth.urls")
    def test_web_push_context_processor_handles_missing_push_routes(self):
        request = self.request_factory.get("/")

        payload = web_push_settings(request)["web_push_config"]

        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["subscribeUrl"], "")
        self.assertEqual(payload["unsubscribeUrl"], "")

    def test_web_push_context_processor_exposes_viewer_preferences(self):
        user = self.user_model.objects.create_user(
            username="viewer-prefs",
            password="secret123",
        )
        user.userprofile.push_marketing_enabled = False
        user.userprofile.push_order_updates_enabled = True
        user.userprofile.save(update_fields=["push_marketing_enabled", "push_order_updates_enabled"])
        request = self.request_factory.get("/")
        request.user = user

        payload = web_push_settings(request)["web_push_config"]

        self.assertTrue(payload["viewer"]["isAuthenticated"])
        self.assertEqual(payload["viewer"]["profileUrl"], reverse("profile_setup"))
        self.assertEqual(
            payload["viewer"]["preferences"],
            {
                "marketingEnabled": False,
                "orderUpdatesEnabled": True,
            },
        )
        self.assertEqual(payload["strategy"]["cartPromptDelayMs"], 4000)

    @patch("storefront.services.web_push.webpush")
    def test_staff_can_send_push_campaign_from_admin(self, mocked_webpush):
        mocked_webpush.return_value = SimpleNamespace(status_code=201)
        WebPushDeviceSubscription.objects.create(
            installation_id="install-1",
            endpoint="https://push.example.test/subscription-1",
            auth_key="auth-token",
            p256dh_key="p256dh-token",
            browser_family="Chrome",
            operating_system="macOS",
            device_type=WebPushDeviceSubscription.DeviceType.DESKTOP,
            is_active=True,
        )
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("admin_push_notifications_create"),
            data={
                "title": "Новий дроп",
                "body": "Переходьте в каталог TwoComms.",
                "target_url": "/catalog/",
                "submit_action": "send_now",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        campaign = PushNotificationCampaign.objects.get(title="Новий дроп")
        self.assertEqual(campaign.status, PushNotificationCampaign.Status.SENT)
        self.assertEqual(campaign.sent_count, 1)
        self.assertEqual(campaign.targeted_count, 1)
        self.assertTrue(
            PushNotificationDelivery.objects.filter(
                campaign=campaign,
                status=PushNotificationDelivery.Status.SENT,
            ).exists()
        )
