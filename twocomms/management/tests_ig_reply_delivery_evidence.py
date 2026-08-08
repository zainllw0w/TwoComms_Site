import json
from unittest.mock import patch

from django.test import TestCase

from management.models import (
    IgBotNotification,
    IgClient,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import instagram_bot


class DeliveredChunkEvidenceTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.client = IgClient.get_or_create_for_sender("w12-evidence-client")

    @patch("management.services.instagram_bot._provider_account_id", return_value="account")
    @patch("management.services.instagram_bot.get_page_token", return_value="token")
    @patch("management.services.instagram_bot._provider_url", return_value="https://meta.test/messages")
    @patch("management.services.instagram_bot._provider_http")
    def test_partial_receipt_keeps_every_confirmed_provider_id(
        self, provider_http, _url, _token, _account
    ):
        provider_http.side_effect = [
            (200, json.dumps({"message_id": "meta-chunk-1"})),
            (503, "temporary provider failure"),
        ]

        receipt = instagram_bot.send_text(
            self.settings,
            self.client.igsid,
            "a" * 951,
            return_receipt=True,
        )

        self.assertIsInstance(receipt, instagram_bot.ProviderDeliveryReceipt)
        self.assertFalse(receipt.ok)
        self.assertEqual(receipt.kind, "unknown")
        self.assertEqual(receipt.provider_message_ids, ("meta-chunk-1",))
        self.assertEqual(receipt.planned_chunk_count, 2)
        self.assertEqual(receipt.delivered_chunk_count, 1)
        self.assertEqual(receipt.failure_boundary, "chunk:2:unknown")


class PersistedReplyEvidenceTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.ai_enabled = True
        self.settings.save(update_fields=["is_enabled", "ai_enabled", "updated_at"])
        self.client = IgClient.get_or_create_for_sender("w12-persisted-evidence")
        self.source = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Покажіть деталі",
            mid="w12-persisted-evidence-mid",
            status=InstagramBotMessage.Status.PENDING,
        )

    @patch("management.services.instagram_bot.send_sender_action")
    @patch(
        "management.services.instagram_bot.gemini_generate",
        return_value="RESTRICTED-ORIGINAL-" + ("a" * 1200),
    )
    @patch("management.services.instagram_bot.send_text")
    def test_partial_delivery_persists_restricted_evidence_and_one_redacted_alert(
        self, send_text, _generate, _sender_action
    ):
        send_text.return_value = instagram_bot.ProviderDeliveryReceipt(
            False,
            "unknown",
            "partial delivery",
            "meta-part-1",
            ("meta-part-1",),
            2,
            1,
            "chunk:2:unknown",
        )

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 0)

        self.source.refresh_from_db()
        self.assertEqual(self.source.delivery_original_text[:20], "RESTRICTED-ORIGINAL-")
        self.assertEqual(self.source.delivery_planned_chunk_count, 2)
        self.assertEqual(self.source.delivery_delivered_chunk_count, 1)
        self.assertEqual(self.source.delivery_provider_message_ids, ["meta-part-1"])
        self.assertEqual(self.source.delivery_failure_boundary, "chunk:2:unknown")
        alerts = IgBotNotification.objects.filter(event_type="partial_delivery")
        self.assertEqual(alerts.count(), 1)
        alert_text = alerts.get().payload["text"]
        self.assertIn("1/2", alert_text)
        self.assertIn("meta-part-1", alert_text)
        self.assertNotIn("RESTRICTED-ORIGINAL-", alert_text)

        instagram_bot.notify_manager(
            alert_text,
            dedupe_key=alerts.get().dedupe_key,
            event_type="partial_delivery",
            deliver_immediately=False,
        )
        self.assertEqual(
            IgBotNotification.objects.filter(event_type="partial_delivery").count(),
            1,
        )
