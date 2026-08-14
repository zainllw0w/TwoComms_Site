import json
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from management.models import IgClient, InstagramBotMessage, InstagramBotSettings
from management.services import gemini_keys


class Gemini37ModelPolicyTests(SimpleTestCase):
    def test_chat_and_management_use_gemini_37_as_primary(self):
        self.assertEqual(gemini_keys.model_chain("chat")[0], "gemini-3.7-flash")
        self.assertEqual(
            gemini_keys.model_chain("management")[0], "gemini-3.7-flash"
        )

    def test_chat_normalization_accepts_37_and_defaults_unknown_to_37(self):
        self.assertEqual(
            gemini_keys.normalize_chat_model("gemini-3.7-flash"),
            "gemini-3.7-flash",
        )
        self.assertEqual(
            gemini_keys.normalize_chat_model("gemini-3-flash-preview"),
            "gemini-3.7-flash",
        )

    def test_checker_keeps_grounded_25_chain(self):
        self.assertEqual(
            gemini_keys.model_chain("checker"),
            ["gemini-2.5-flash", "gemini-2.5-flash-lite"],
        )

    def test_message_model_field_is_bounded_provenance(self):
        field = InstagramBotMessage._meta.get_field("gemini_model")
        self.assertEqual(field.max_length, 80)
        self.assertEqual(field.default, "")


class InstagramBotModelTelemetryTests(TestCase):
    def setUp(self):
        self.client_row = IgClient.objects.create(igsid="model-telemetry-37")

    def test_generated_reply_persists_actual_provider_model(self):
        inbound = InstagramBotMessage.objects.create(
            sender_id=self.client_row.igsid,
            client=self.client_row,
            role=InstagramBotMessage.Role.USER,
            text="Привіт",
            status=InstagramBotMessage.Status.PENDING,
        )

        from management.services import instagram_bot

        instagram_bot._persist_generated_reply_message(
            inbound,
            "Вітаю!",
            provider_message_id="meta-message-37",
            provider_model="gemini-3.6-flash",
            processed_at=instagram_bot.timezone.now(),
        )

        reply = InstagramBotMessage.objects.get(
            role=InstagramBotMessage.Role.MODEL,
            provider_message_id="meta-message-37",
        )
        self.assertEqual(reply.gemini_model, "gemini-3.6-flash")

    def test_generated_reply_rejects_malformed_provider_message_id(self):
        from management.services import instagram_bot

        for provider_message_id in (123, "x" * 256):
            with self.subTest(provider_message_id=str(provider_message_id)[:20]):
                inbound = InstagramBotMessage.objects.create(
                    sender_id=self.client_row.igsid,
                    client=self.client_row,
                    role=InstagramBotMessage.Role.USER,
                    text="Привіт",
                    status=InstagramBotMessage.Status.PENDING,
                )

                reply = instagram_bot._persist_generated_reply_message(
                    inbound,
                    "Вітаю!",
                    provider_message_id=provider_message_id,
                    processed_at=instagram_bot.timezone.now(),
                )

                self.assertEqual(reply.provider_message_id, "")


class InstagramBotModelUiContractTests(SimpleTestCase):
    def test_conversation_payload_and_badge_contract_are_present(self):
        views_source = Path(__file__).with_name("bot_views.py").read_text(
            encoding="utf-8"
        )
        template = (
            Path(__file__).with_name("templates")
            / "management"
            / "bot.html"
        ).read_text(encoding="utf-8")
        self.assertIn('"gemini_model": m.gemini_model', views_source)
        self.assertIn("AI-агент", template)
        self.assertIn("gemini_model", template)
        self.assertIn("bot-model-badge", template)
        self.assertIn("gemini-3.7-flash", template)
