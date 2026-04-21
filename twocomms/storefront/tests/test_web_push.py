import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from storefront.models import (
    PushNotificationCampaign,
    PushNotificationDelivery,
    WebPushDeviceSubscription,
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
        self.client = Client(
            HTTP_HOST="twocomms.shop",
            SERVER_PORT="443",
            **{"wsgi.url_scheme": "https"},
        )
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

    def test_staff_admin_panel_renders_push_notifications_section(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("admin_panel"),
            {"section": "push_notifications"},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Push Control Center")
        self.assertContains(response, "Нова push-кампанія")

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
