from django.test import SimpleTestCase

from management.services.ig_reply_truth import ReplyTruthContext
from management.services.ig_response_guard import ProviderResponseGuard


class ResponseGuardTests(SimpleTestCase):
    def guard(self, **kwargs):
        return ProviderResponseGuard(
            context_factory=lambda _control, _reply_text: ReplyTruthContext(),
            **kwargs,
        )

    def test_false_payment_is_rejected_before_a_successful_response_is_cached(self):
        guard = self.guard()
        result = guard.validate({"reply_text": "Оплата підтверджена.", "controls": []}, usage={})
        self.assertFalse(result.valid)
        self.assertIn("unverified_payment", result.reason_codes)
        self.assertIsNone(guard.response)

    def test_only_actually_attached_images_require_observations(self):
        guard = self.guard(image_mimes=("image/png", "image/png"), require_intelligence=True)
        parsed = {
            "reply_text": "Бачу перше зображення.", "controls": [],
            "turn_intelligence": {"catalog_candidates": [], "transcript": "", "intent": "media_review", "confidence": 0.8,
                "image_observations": [{"source_image_index": 0, "outcome": "understood", "evidence_code": "visual_content", "type_code": "other"}]},
        }
        self.assertTrue(guard.validate(parsed, usage={"_request_inline_count": 1}).valid)
        self.assertIs(guard.source, parsed)
        self.assertIsNotNone(guard.response)
        missing = guard.validate(parsed, usage={"_request_inline_count": 2})
        self.assertFalse(missing.valid)
        self.assertEqual(missing.reason_codes, ("incomplete_image_coverage",))

    def test_legacy_model_tags_are_not_an_operational_response(self):
        guard = self.guard()
        self.assertFalse(guard.validate("Готово [PAYLINK:123]", usage={}).valid)
        self.assertIsNone(guard.response)

    def test_legacy_negotiated_price_control_is_rejected_without_text_amount(self):
        guard = self.guard()
        result = guard.validate({
            "reply_text": "Домовились, можемо оформлювати.",
            "controls": [{"kind": "price", "value": "777"}],
        }, usage={})

        self.assertFalse(result.valid)
        self.assertEqual(result.reason_codes, ("unverified_price",))
        self.assertEqual(guard.last_reasons, ("unverified_price",))
        self.assertIsNone(guard.response)

    def test_repair_keeps_original_media_and_skips_non_model_failures(self):
        payload = {"contents": [{"role": "user", "parts": [{"inline_data": {"mime_type": "image/png", "data": "fixture"}}]}]}
        repaired = ProviderResponseGuard.repair(payload, {"reply_text": "untrusted", "controls": []}, ("unverified_price",))
        self.assertEqual(repaired["contents"][0], payload["contents"][0])
        self.assertEqual(len(payload["contents"]), 1)
        self.assertIn("unverified_price", repaired["contents"][-1]["parts"][0]["text"])
        self.assertIsNone(ProviderResponseGuard.repair(payload, {}, ("authority_unavailable",)))
