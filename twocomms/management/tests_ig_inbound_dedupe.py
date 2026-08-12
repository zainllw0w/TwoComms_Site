from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from management.models import IgClient, InstagramBotMessage, InstagramBotSettings
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
