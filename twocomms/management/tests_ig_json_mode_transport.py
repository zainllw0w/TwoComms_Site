from django.test import TestCase, override_settings

from management.services import gemini_payload_contract as contract
from management.services.ig_response_control import (
    parse_structured_response,
    structured_response_instruction,
    structured_response_schema,
)


def _json_mode_payload():
    return {
        "contents": [{"role": "user", "parts": [{"text": "vision"}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 4096,
        },
    }


@override_settings(GEMINI_PAYLOAD_CONTRACT_CIRCUIT=True)
class JsonModeTransportTests(TestCase):
    def test_json_mode_has_distinct_fingerprint_and_no_schema(self):
        payload = _json_mode_payload()

        guarded, report = contract.guard_payload(payload)

        self.assertEqual(guarded, payload)
        self.assertEqual(report.variant, contract.JSON_MODE_VARIANT)
        self.assertEqual(report.reason, "json_mode")
        self.assertTrue(report.fingerprint)
        self.assertNotEqual(report.fingerprint, "dd29d56d6a3adda9")
        config = guarded["generationConfig"]
        for key in ("responseSchema", "responseJsonSchema", "_responseJsonSchema"):
            self.assertNotIn(key, config)

    def test_rejected_schema_fingerprint_does_not_block_json_mode(self):
        contract.record_invalid_payload(
            fingerprint="dd29d56d6a3adda9",
            variant=contract.DOCUMENTED_VARIANT,
            model="gemini-3.7-flash",
            facts={"code": 400, "status": "INVALID_ARGUMENT", "field": ""},
        )

        _guarded, report = contract.guard_payload(_json_mode_payload())

        self.assertFalse(report.blocked)
        self.assertEqual(report.variant, contract.JSON_MODE_VARIANT)

    def test_new_json_mode_400_blocks_only_the_same_fingerprint(self):
        payload = _json_mode_payload()
        _guarded, first = contract.guard_payload(payload)
        contract.record_invalid_payload(
            fingerprint=first.fingerprint,
            variant=first.variant,
            model="gemini-3.7-flash",
            facts={"code": 400, "status": "INVALID_ARGUMENT", "field": ""},
        )

        _guarded, repeated = contract.guard_payload(payload)

        self.assertTrue(repeated.blocked)
        self.assertEqual(repeated.reason, "json_mode_rejected")
        self.assertFalse(contract.retry_variant_available(payload))

    def test_semantic_instruction_is_bounded_and_names_full_image_contract(self):
        instruction = structured_response_instruction()

        self.assertLess(len(instruction), 4000)
        self.assertIn("exactly one JSON object", instruction)
        self.assertIn("turn_intelligence", instruction)
        self.assertIn("catalog_candidates", instruction)
        self.assertIn("image_observations", instruction)
        self.assertIn("source_image_index", instruction)
        self.assertIn("evidence_code", instruction)
        self.assertIn("type_code", instruction)
        self.assertIn("Never emit the legacy price control", instruction)
        self.assertIn("price_quoted", instruction)
        self.assertNotIn(
            "price",
            structured_response_schema()["properties"]["controls"]["items"]
            ["properties"]["kind"]["enum"],
        )

    def test_strict_application_parser_remains_the_authority(self):
        invalid = parse_structured_response({
            "reply_text": "Ок",
            "controls": [{"kind": "stage", "value": "paid"}],
        })
        valid = parse_structured_response({
            "reply_text": "Бачу фото.",
            "controls": [],
            "turn_intelligence": {
                "catalog_candidates": [],
                "transcript": "",
                "intent": "media_review",
                "confidence": 0.8,
                "image_observations": [{
                    "source_image_index": 0,
                    "outcome": "understood",
                    "evidence_code": "visual_content",
                    "type_code": "product",
                }],
            },
        })

        self.assertFalse(invalid.valid)
        self.assertEqual(invalid.control, {})
        self.assertTrue(valid.valid)
        self.assertEqual(
            valid.turn_intelligence.image_observations[0].source_image_index,
            0,
        )
