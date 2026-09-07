import hashlib
from unittest.mock import patch

from django.test import TestCase

from management.models import BotInstruction, IgClient, IgFollowUpTask, IgBotNotification, InstagramBotMessage, InstagramBotSettings
from management.services import instagram_bot as bot
from management.services.gemini_routing import RoutingDecision, RoutingMode, TaskClass
from management.services.ig_prize_programme import RESERVED_INTENT_TAG, active_shooting_prize_programme


class PrizeLiveIntegrationTests(TestCase):
    def setUp(self):
        self.instruction = BotInstruction.objects.create(
            title="Shooting prize", body="Ask catalog or custom; team checks eligibility.",
            intent_tags=RESERVED_INTENT_TAG, is_active=True, priority=18,
        )
        from management.tests_ig_policy_helpers import publish_current_instructions

        publish_current_instructions()
        self.customer = IgClient.objects.create(igsid="prize-live-customer")
        self.row = InstagramBotMessage.objects.create(
            client=self.customer, sender_id=self.customer.igsid, role="user",
            text="", mid="prize-live-image-only", source="webhook",
            media_capture_eligible=True, private_media_state="active",
        )
        self.raw = b"anonymous-certificate-fixture"
        self.parts = bot._normalize_message_media([{
            "status": "owned", "provenance": "live_webhook", "private_storage": True,
            "storage_name": "private/fixture.png", "mime": "image/png", "original_index": 0,
            "content_hash": hashlib.sha256(self.raw).hexdigest(),
        }], message_scope=self.row.pk)
        self.row.attachment_media = self.parts
        self.row.save(update_fields=["attachment_media"])

    def generate(self, *, type_code="certificate", programme=None):
        programme = programme or active_shooting_prize_programme()
        observation = {
            "source_image_index": 0, "outcome": "uncertain",
            "evidence_code": "visual_content", "type_code": type_code,
        }
        if type_code == "certificate":
            observation["prize_certificate"] = {
                "programme_id": programme.programme_id,
                "programme_version": programme.version, "status": "recognized",
                "cue_codes": ["shooting_target"], "reason_code": "visible_programme_cues",
                "manager_required": True,
            }
        output = {
            "parsed": {
                "reply_text": "Схоже на сертифікат. Цікавить каталог чи власний принт? Умови перевірить команда.",
                "controls": [], "turn_intelligence": {
                    "catalog_candidates": [], "transcript": "", "intent": "media_review",
                    "confidence": 0.8, "image_observations": [observation],
                },
            },
            "usage": {"_request_inline_count": 1, "_request_inline_content_hashes": [hashlib.sha256(self.raw).hexdigest()]}, "model": "actual-vision-model",
            "meta": {"request_id": "prize-live-request"},
        }
        routing = RoutingDecision(
            lane="live", task_class=TaskClass.COMPLEX_LIVE, reason_codes=("media",),
            authority_snapshot_version="test", requires_media_reasoning=True,
            commercial_risk="low", model_chain=("gemini-test",), deadline_ms=1000,
            routing_mode=RoutingMode.ADAPTIVE,
        )
        failure = {}
        with patch.object(bot, "assemble_system_instruction", return_value="system"), patch.object(bot, "select_chat_reasoning_task", return_value="media_analysis"), patch("management.services.call_ai_analysis.gemini_generate_text", return_value=output) as provider:
            result = bot.gemini_generate(
                InstagramBotSettings.load(), [{"role": "user", "text": ""}],
                images=[("image/png", self.raw)], client=self.customer,
                turn_media_binding=bot._source_media_binding(self.row, [{**self.parts[0], "data": self.raw}]),
                routing_decision=routing, failure_context=failure,
            )
        return result, failure, provider

    def test_image_only_uses_one_request_and_creates_one_candidate_case(self):
        result, failure, provider = self.generate()
        self.assertTrue(result.valid)
        self.assertEqual(provider.call_count, 1)
        payload = provider.call_args.args[0]
        instruction = payload["system_instruction"]["parts"][0]["text"]
        self.assertEqual(instruction.count("[CONDITIONAL SHOOTING PRIZE PROGRAMME]"), 1)
        self.assertNotIn("responseJsonSchema", payload["generationConfig"])
        bot._persist_turn_intelligence(self.row, failure["turn_intelligence"])
        bot._record_prize_case_from_intelligence(self.row)
        bot._record_prize_case_from_intelligence(self.row)
        self.assertEqual(IgFollowUpTask.objects.count(), 1)
        self.assertEqual(IgBotNotification.objects.count(), 1)
        case = IgFollowUpTask.objects.get()
        self.assertEqual(case.manager_context["candidate_status"], "uncertain")
        self.assertEqual(case.manager_context["authority"]["entitlement"], "unconfirmed")
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.bot_paused)

    def test_receipt_does_not_create_prize_case(self):
        result, failure, _provider = self.generate(type_code="receipt")
        self.assertTrue(result.valid)
        bot._persist_turn_intelligence(self.row, failure["turn_intelligence"])
        bot._record_prize_case_from_intelligence(self.row)
        self.assertFalse(IgFollowUpTask.objects.exists())

    def test_disabled_programme_before_projection_does_not_create_case(self):
        _result, failure, _provider = self.generate()
        bot._persist_turn_intelligence(self.row, failure["turn_intelligence"])
        self.instruction.is_active = False
        self.instruction.save(update_fields=["is_active"])
        from management.tests_ig_policy_helpers import publish_current_instructions

        publish_current_instructions()
        bot._record_prize_case_from_intelligence(self.row)
        self.assertFalse(IgFollowUpTask.objects.exists())
