from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from management.models import (
    IgClient,
    InstagramBotLog,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import instagram_bot


class SyntheticInboundDedupeTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.allowed_senders = ""
        self.settings.reply_after = None
        self.settings.save(update_fields=["is_enabled", "allowed_senders", "reply_after"])
        self.client = IgClient.get_or_create_for_sender("synthetic-dedupe-client")
        self.received_at = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)

    def _enqueue(self, *, text="Hello", attachments=None, received_at=None):
        return instagram_bot.enqueue_inbound(
            self.settings,
            sender_id=self.client.igsid,
            text=text,
            mid="",
            source="webhook",
            attachments=attachments or [],
            received_at=received_at or self.received_at,
        )

    def test_same_midless_provider_event_creates_one_processing_path(self):
        with patch("management.services.bot_sales_classifier.classify_message", return_value={}):
            self.assertTrue(self._enqueue())
            self.assertFalse(self._enqueue(text="  HELLO  "))

        rows = InstagramBotMessage.objects.filter(
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
        )
        self.assertEqual(rows.count(), 1)
        self.assertTrue(rows.get().synthetic_event_key)

    def test_same_text_later_or_different_attachment_is_new_event(self):
        with patch("management.services.bot_sales_classifier.classify_message", return_value={}):
            self.assertTrue(self._enqueue())
            self.assertTrue(
                self._enqueue(received_at=self.received_at.replace(minute=1))
            )
            self.assertTrue(
                self._enqueue(attachments=["https://cdn.example/other.jpg"])
            )

        rows = InstagramBotMessage.objects.filter(
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
        )
        self.assertEqual(rows.count(), 3)
        self.assertEqual(rows.values_list("synthetic_event_key", flat=True).distinct().count(), 3)

    def test_midless_event_without_provider_time_is_rejected_fail_closed(self):
        with patch("management.services.bot_sales_classifier.classify_message", return_value={}):
            self.assertFalse(
                instagram_bot.enqueue_inbound(
                    self.settings,
                    sender_id=self.client.igsid,
                    text="No provider timestamp",
                    mid="",
                    source="webhook",
                    attachments=[],
                    received_at=None,
                )
            )

        self.assertFalse(
            InstagramBotMessage.objects.filter(sender_id=self.client.igsid).exists()
        )

    def test_midless_opt_out_without_provider_time_does_not_bypass_dedupe(self):
        self.settings.allowed_senders = self.client.igsid
        self.settings.save(update_fields=["allowed_senders"])

        self.assertFalse(
            instagram_bot.enqueue_inbound(
                self.settings,
                sender_id=self.client.igsid,
                text="Стоп, не пишіть мені",
                mid="",
                source="webhook",
                attachments=[],
                received_at=None,
            )
        )
        self.assertFalse(
            InstagramBotMessage.objects.filter(sender_id=self.client.igsid).exists()
        )


class AllowlistObservationTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.allowed_senders = "allowed-sender"
        self.settings.reply_after = None
        self.settings.save(update_fields=["is_enabled", "allowed_senders", "reply_after"])

    @patch("management.services.instagram_bot._schedule_inbound_analysis")
    @patch("management.services.bot_sales_classifier.classify_message")
    @patch("management.services.bot_followups.schedule_after_inbound")
    def test_valid_nonallowed_inbound_is_observed_without_automation(
        self,
        schedule_followup,
        classify_message,
        schedule_analysis,
    ):
        observed = instagram_bot.enqueue_inbound(
            self.settings,
            sender_id="unlisted-sender",
            text="Please share a phone number",
            mid="unlisted-inbound-mid",
            source="webhook",
        )
        repeated = instagram_bot.enqueue_inbound(
            self.settings,
            sender_id="unlisted-sender",
            text="Please share a phone number",
            mid="unlisted-inbound-mid",
            source="webhook",
        )

        self.assertTrue(observed)
        self.assertFalse(repeated)
        client = IgClient.objects.get(igsid="unlisted-sender")
        message = InstagramBotMessage.objects.get(mid="unlisted-inbound-mid")
        self.assertEqual(message.client_id, client.pk)
        self.assertEqual(message.role, InstagramBotMessage.Role.USER)
        self.assertEqual(message.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(message.source, "webhook")
        self.assertIsNotNone(message.processed_at)
        self.assertIsNotNone(client.first_contact_at)
        self.assertIsNotNone(client.last_message_at)
        self.assertEqual(
            InstagramBotMessage.objects.filter(mid="unlisted-inbound-mid").count(), 1
        )
        self.assertFalse(
            InstagramBotMessage.objects.filter(
                sender_id="unlisted-sender",
                status=InstagramBotMessage.Status.PENDING,
            ).exists()
        )
        self.settings.refresh_from_db()
        self.assertIsNotNone(self.settings.last_inbound_at)
        record = InstagramBotLog.objects.get(event="observed_not_allowed")
        self.assertNotIn("unlisted-sender", record.detail)
        self.assertNotIn("Please share a phone number", record.detail)
        classify_message.assert_not_called()
        schedule_analysis.assert_not_called()
        schedule_followup.assert_not_called()

    @patch("management.services.instagram_bot.download_image")
    def test_nonallowed_webhook_attachment_is_metadata_only_and_never_captured(
        self,
        download_image,
    ):
        url = "https://lookaside.example/restricted-ingress.jpg"

        self.assertTrue(
            instagram_bot.enqueue_inbound(
                self.settings,
                sender_id="unlisted-media-sender",
                text="Ось фото",
                mid="unlisted-media-inbound-mid",
                source="webhook",
                attachments=[url],
            )
        )

        message = InstagramBotMessage.objects.get(mid="unlisted-media-inbound-mid")
        self.assertFalse(message.media_capture_eligible)
        self.assertEqual(len(message.attachment_media), 1)
        self.assertEqual(message.attachment_media[0]["url"], url)
        self.assertEqual(
            message.attachment_media[0]["provenance"], "historical_import"
        )
        self.assertEqual(message.attachment_media[0]["status"], "metadata_only")

        instagram_bot._capture_message_media(message)

        download_image.assert_not_called()

    @patch("management.services.instagram_bot._schedule_inbound_analysis")
    @patch("management.services.bot_sales_classifier.classify_message")
    @patch("management.services.bot_followups.schedule_after_inbound")
    def test_hidden_nonallowed_client_is_observed_once_without_automation(
        self,
        schedule_followup,
        classify_message,
        schedule_analysis,
    ):
        client = IgClient.get_or_create_for_sender("hidden-unlisted-sender")
        client.hidden_at = datetime.now(timezone.utc)
        client.save(update_fields=["hidden_at", "updated_at"])

        self.assertTrue(
            instagram_bot.enqueue_inbound(
                self.settings,
                sender_id=client.igsid,
                text="Do not show this in CRM",
                mid="hidden-unlisted-inbound-mid",
                source="webhook",
                attachments=["https://lookaside.example/hidden.jpg"],
            )
        )
        self.assertFalse(
            instagram_bot.enqueue_inbound(
                self.settings,
                sender_id=client.igsid,
                text="Do not show this in CRM",
                mid="hidden-unlisted-inbound-mid",
                source="webhook",
                attachments=["https://lookaside.example/hidden.jpg"],
            )
        )
        message = InstagramBotMessage.objects.get(mid="hidden-unlisted-inbound-mid")
        self.assertEqual(message.status, InstagramBotMessage.Status.DONE)
        self.assertFalse(message.media_capture_eligible)
        self.assertEqual(
            InstagramBotMessage.objects.filter(mid="hidden-unlisted-inbound-mid").count(),
            1,
        )
        self.settings.refresh_from_db()
        self.assertIsNotNone(self.settings.last_inbound_at)
        schedule_followup.assert_not_called()
        classify_message.assert_not_called()
        schedule_analysis.assert_not_called()

    def test_hidden_explicit_opt_out_is_applied_without_media_capture(self):
        client = IgClient.get_or_create_for_sender("hidden-opt-out-sender")
        client.hidden_at = datetime.now(timezone.utc)
        client.save(update_fields=["hidden_at", "updated_at"])

        observed = instagram_bot.enqueue_inbound(
            self.settings,
            sender_id=client.igsid,
            text="Стоп, не пишіть мені",
            mid="hidden-opt-out-mid",
            source="webhook",
            attachments=["https://lookaside.example/hidden-opt-out.jpg"],
        )

        self.assertTrue(observed)
        client.refresh_from_db()
        self.assertIsNotNone(client.opted_out_at)
        message = InstagramBotMessage.objects.get(mid="hidden-opt-out-mid")
        self.assertEqual(message.client_id, client.pk)
        self.assertEqual(message.status, InstagramBotMessage.Status.DONE)
        self.assertFalse(message.media_capture_eligible)

    def test_erasure_fence_and_owner_echo_remain_unattached(self):
        erased = IgClient.get_or_create_for_sender("erased-hidden-sender")
        erased.privacy_erasure_started_at = datetime.now(timezone.utc)
        erased.save(update_fields=["privacy_erasure_started_at", "updated_at"])
        self.settings.ig_user_id = "provider-owner-id"
        self.settings.save(update_fields=["ig_user_id"])

        self.assertFalse(instagram_bot.enqueue_inbound(
            self.settings,
            sender_id=erased.igsid,
            text="must remain erased",
            mid="erased-hidden-mid",
            source="webhook",
        ))
        self.assertFalse(instagram_bot.enqueue_inbound(
            self.settings,
            sender_id="provider-owner-id",
            text="owner echo",
            mid="owner-echo-mid",
            source="webhook",
        ))
        self.assertFalse(InstagramBotMessage.objects.filter(
            mid__in=["erased-hidden-mid", "owner-echo-mid"]
        ).exists())
