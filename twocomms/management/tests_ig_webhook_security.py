import hashlib
import hmac
import json
import os
from unittest.mock import patch

from django.test import Client, SimpleTestCase, TestCase
from django.utils import timezone

from management.ig_bot_models import IgBotNotification
from management.models import (
    IgClient,
    IgConversationAnalysisJob,
    InstagramBotLog,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import instagram_bot as bot


class WebhookSignatureTests(SimpleTestCase):
    def test_missing_secret_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(bot.verify_signature(b"{}", ""))
            self.assertEqual(bot.webhook_signature_status()["state"], "missing_secret")

    def test_explicit_unsigned_override_is_visible(self):
        with patch.dict(os.environ, {"IG_BOT_ALLOW_UNSIGNED_WEBHOOKS": "true"}, clear=True):
            self.assertTrue(bot.verify_signature(b"{}", ""))
            status = bot.webhook_signature_status()
        self.assertTrue(status["unsigned_override"])
        self.assertEqual(status["state"], "development_override")

    def test_valid_and_invalid_hmac(self):
        body = b'{"object":"instagram"}'
        secret = "test-secret"
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"IG_APP_SECRET": secret}, clear=True):
            self.assertTrue(bot.verify_signature(body, f"sha256={digest}"))
            self.assertFalse(bot.verify_signature(body, "sha256=wrong"))
            self.assertFalse(bot.verify_signature(body, ""))

    def test_facebook_app_secret_alias_is_accepted(self):
        body = b'{"object":"instagram"}'
        secret = "facebook-alias-secret"
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        with patch.dict(
            os.environ,
            {
                "IG_PROVIDER_TRANSPORT": "legacy_page",
                "FACEBOOK_APP_SECRET": secret,
            },
            clear=True,
        ):
            self.assertTrue(bot.verify_signature(body, f"sha256={digest}"))
            self.assertEqual(bot.webhook_signature_status()["state"], "configured")


class WebhookEndpointSecurityTests(TestCase):
    def setUp(self):
        settings_obj = InstagramBotSettings.load()
        settings_obj.is_enabled = True
        settings_obj.allowed_senders = ""
        settings_obj.save(update_fields=["is_enabled", "allowed_senders"])
        self.client = Client()

    def test_unsigned_post_is_rejected_without_secret(self):
        payload = json.dumps({"entry": []})
        with patch.dict(os.environ, {}, clear=True), patch("management.bot_webhook.bot.log"):
            response = self.client.post(
                "/bot/webhook/", data=payload, content_type="application/json",
                HTTP_HOST="management.twocomms.shop",
            )
        self.assertEqual(response.status_code, 403)

    def test_unsigned_post_requires_explicit_override(self):
        payload = json.dumps({"entry": []})
        with patch.dict(os.environ, {"IG_BOT_ALLOW_UNSIGNED_WEBHOOKS": "1"}, clear=True), \
             patch("management.bot_webhook.bot.record_raw_event"), \
             patch("management.bot_webhook.bot.handle_webhook_payload", return_value=0) as handle:
            response = self.client.post(
                "/bot/webhook/", data=payload, content_type="application/json",
                HTTP_HOST="management.twocomms.shop",
            )
        self.assertEqual(response.status_code, 200)
        handle.assert_called_once()

    def test_signed_inbound_ack_does_not_run_work_or_spawn_request_thread(self):
        payload = {
            "entry": [{
                "messaging": [{
                    "sender": {"id": "fast-path-user"},
                    "message": {"mid": "fast-path-mid", "text": "Скільки коштує?"},
                }],
            }],
        }
        raw = json.dumps(payload).encode("utf-8")
        digest = hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"IG_APP_SECRET": "test-secret"}, clear=True), \
             patch("management.bot_webhook.bot.record_raw_event"), \
             patch("management.bot_webhook.bot.process_pending", side_effect=AssertionError("reply work ran in HTTP path")), \
             patch("management.bot_webhook.bot.gemini_generate", side_effect=AssertionError("Gemini ran in HTTP path")), \
             patch("management.bot_webhook.bot._http", side_effect=AssertionError("provider HTTP ran in HTTP path")), \
             patch("management.bot_webhook.bot.download_image", side_effect=AssertionError("media download ran in HTTP path")), \
             patch("management.bot_webhook.bot._deliver_manager_notification", side_effect=AssertionError("notification delivery ran in HTTP path")), \
             patch("management.services.bot_sales_classifier.classify_message", side_effect=AssertionError("classifier ran in HTTP path")) as classify, \
             patch("management.bot_webhook.threading") as webhook_threading:
            response = self.client.post(
                "/bot/webhook/",
                data=raw,
                content_type="application/json",
                HTTP_HOST="management.twocomms.shop",
                HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}",
            )
        self.assertEqual(response.status_code, 200)
        classify.assert_not_called()
        webhook_threading.Thread.assert_not_called()
        message = InstagramBotMessage.objects.get(mid="fast-path-mid")
        self.assertEqual(message.status, InstagramBotMessage.Status.PENDING)
        job = IgConversationAnalysisJob.objects.get(client=message.client)
        self.assertEqual(job.watermark_message_id, message.pk)
        self.assertEqual(job.trigger, "webhook_inbound")

        with patch.dict(os.environ, {"IG_APP_SECRET": "test-secret"}, clear=True):
            duplicate = self.client.post(
                "/bot/webhook/",
                data=raw,
                content_type="application/json",
                HTTP_HOST="management.twocomms.shop",
                HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}",
            )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(InstagramBotMessage.objects.filter(mid="fast-path-mid").count(), 1)
        self.assertEqual(IgConversationAnalysisJob.objects.filter(client=message.client).count(), 1)

    def test_signed_unlisted_inbound_remains_visible_without_automation(self):
        settings_obj = InstagramBotSettings.load()
        settings_obj.allowed_senders = "permitted-sender"
        settings_obj.save(update_fields=["allowed_senders"])
        payload = {
            "entry": [{
                "messaging": [{
                    "sender": {"id": "unlisted-sender"},
                    "message": {
                        "mid": "unlisted-webhook-mid",
                        "text": "Could you share a phone number?",
                    },
                }],
            }],
        }
        raw = json.dumps(payload).encode("utf-8")
        digest = hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()

        with patch.dict(os.environ, {"IG_APP_SECRET": "test-secret"}, clear=True), \
             patch("management.bot_webhook.bot.record_raw_event"), \
             patch("management.services.instagram_bot._schedule_inbound_analysis") as schedule:
            response = self.client.post(
                "/bot/webhook/",
                data=raw,
                content_type="application/json",
                HTTP_HOST="management.twocomms.shop",
                HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}",
            )

        self.assertEqual(response.status_code, 200)
        message = InstagramBotMessage.objects.get(mid="unlisted-webhook-mid")
        client = IgClient.objects.get(igsid="unlisted-sender")
        self.assertEqual(message.client_id, client.pk)
        self.assertEqual(message.role, InstagramBotMessage.Role.USER)
        self.assertEqual(message.status, InstagramBotMessage.Status.DONE)
        self.assertIsNotNone(message.processed_at)
        self.assertFalse(client.hidden_at)
        self.assertIsNotNone(client.last_message_at)
        self.assertEqual(
            InstagramBotMessage.objects.filter(
                client=client,
                role=InstagramBotMessage.Role.USER,
                status=InstagramBotMessage.Status.DONE,
            ).count(),
            1,
        )
        self.assertFalse(
            InstagramBotMessage.objects.filter(
                client=client,
                status=InstagramBotMessage.Status.PENDING,
            ).exists()
        )
        self.assertFalse(IgConversationAnalysisJob.objects.filter(client=client).exists())
        self.assertTrue(InstagramBotSettings.load().last_inbound_at)
        schedule.assert_not_called()

    def test_signed_manager_echo_pauses_and_queues_without_inline_analysis_or_delivery(self):
        payload = {
            "entry": [{
                "messaging": [{
                    "sender": {"id": "page-id"},
                    "recipient": {"id": "manager-echo-user"},
                    "message": {
                        "mid": "manager-echo-mid",
                        "text": "Я підключився до діалогу",
                        "is_echo": True,
                    },
                }],
            }],
        }
        raw = json.dumps(payload).encode("utf-8")
        digest = hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"IG_APP_SECRET": "test-secret"}, clear=True), \
             patch("management.bot_webhook.bot.record_raw_event"), \
             patch("management.services.bot_sales_classifier.classify_message", side_effect=AssertionError("classifier ran in HTTP path")) as classify, \
             patch("management.bot_webhook.bot._deliver_manager_notification", side_effect=AssertionError("Telegram delivery ran in HTTP path")) as deliver, \
             patch("management.bot_webhook.threading") as webhook_threading:
            response = self.client.post(
                "/bot/webhook/",
                data=raw,
                content_type="application/json",
                HTTP_HOST="management.twocomms.shop",
                HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}",
            )
        self.assertEqual(response.status_code, 200)
        classify.assert_not_called()
        deliver.assert_not_called()
        webhook_threading.Thread.assert_not_called()
        client = IgClient.objects.get(igsid="manager-echo-user")
        self.assertTrue(client.manager_takeover)
        message = InstagramBotMessage.objects.get(mid="manager-echo-mid")
        self.assertEqual(message.role, InstagramBotMessage.Role.MANAGER)
        self.assertEqual(
            IgConversationAnalysisJob.objects.get(client=client).trigger,
            "manager_message",
        )
        self.assertTrue(
            IgBotNotification.objects.filter(client=client, event_type="takeover").exists()
        )
        permission_epoch = client.reply_permission_epoch
        last_manager_message_at = client.last_manager_message_at

        with patch.dict(os.environ, {"IG_APP_SECRET": "test-secret"}, clear=True), \
             patch("management.bot_webhook.bot.record_raw_event"):
            duplicate = self.client.post(
                "/bot/webhook/",
                data=raw,
                content_type="application/json",
                HTTP_HOST="management.twocomms.shop",
                HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}",
            )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(
            InstagramBotMessage.objects.filter(mid="manager-echo-mid").count(),
            1,
        )
        self.assertEqual(IgConversationAnalysisJob.objects.filter(client=client).count(), 1)
        self.assertEqual(
            IgBotNotification.objects.filter(client=client, event_type="takeover").count(),
            1,
        )
        client.refresh_from_db()
        self.assertEqual(client.reply_permission_epoch, permission_epoch)
        self.assertEqual(client.last_manager_message_at, last_manager_message_at)

    def test_signed_inbound_persists_and_defers_analysis_when_scheduling_fails(self):
        payload = {
            "entry": [{
                "messaging": [{
                    "sender": {"id": "durability-user"},
                    "message": {"mid": "durability-mid", "text": "Хочу чорну M"},
                }],
            }],
        }
        raw = json.dumps(payload).encode("utf-8")
        digest = hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()

        def partially_schedule_then_fail(client, message, **_kwargs):
            IgConversationAnalysisJob.objects.create(
                client=client,
                watermark_message_id=message.pk,
                due_at=timezone.now(),
                next_attempt_at=timezone.now(),
                required_state_fingerprint="partial-schedule",
            )
            raise RuntimeError("analysis queue unavailable")

        with patch.dict(os.environ, {"IG_APP_SECRET": "test-secret"}, clear=True), \
             patch("management.bot_webhook.bot.record_raw_event"), \
             patch(
                 "management.services.bot_conversation_analysis.schedule_analysis",
                 side_effect=partially_schedule_then_fail,
             ):
            response = self.client.post(
                "/bot/webhook/",
                data=raw,
                content_type="application/json",
                HTTP_HOST="management.twocomms.shop",
                HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}",
            )
        self.assertEqual(response.status_code, 200)
        message = InstagramBotMessage.objects.get(mid="durability-mid")
        self.assertEqual(message.status, InstagramBotMessage.Status.PENDING)
        self.assertFalse(IgConversationAnalysisJob.objects.filter(client=message.client).exists())
        deferred = InstagramBotLog.objects.get(event="analysis_schedule_deferred")
        self.assertEqual(deferred.level, "warning")
        self.assertEqual(deferred.detail, "RuntimeError")

    def test_signed_manager_echo_returns_retry_without_partial_message_when_scheduling_fails(self):
        payload = {
            "entry": [{
                "messaging": [{
                    "sender": {"id": "page-id"},
                    "recipient": {"id": "manager-durability-user"},
                    "message": {
                        "mid": "manager-durability-mid",
                        "text": "Менеджер уточнює деталі",
                        "is_echo": True,
                    },
                }],
            }],
        }
        raw = json.dumps(payload).encode("utf-8")
        digest = hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"IG_APP_SECRET": "test-secret"}, clear=True), \
             patch("management.bot_webhook.bot.record_raw_event"), \
             patch(
                 "management.services.bot_conversation_analysis.schedule_analysis",
                 side_effect=RuntimeError("analysis queue unavailable"),
             ):
            response = self.client.post(
                "/bot/webhook/",
                data=raw,
                content_type="application/json",
                HTTP_HOST="management.twocomms.shop",
                HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}",
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(
            InstagramBotMessage.objects.filter(mid="manager-durability-mid").exists()
        )
        self.assertFalse(
            IgConversationAnalysisJob.objects.filter(
                client__igsid="manager-durability-user"
            ).exists()
        )
