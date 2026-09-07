"""B01.5 contextual image producer contracts."""
from unittest.mock import patch

from django.test import SimpleTestCase

from management.services import bot_vision
from management.services.ig_image_context import build_contextual_image_note
from management.services.ig_media_manifest import IMAGE_TYPE_CODES
from management.services.ig_response_control import (
    parse_structured_response,
    structured_response_schema,
)


class ContextualImageNoteTests(SimpleTestCase):
    def test_no_programme_schema_omits_prize_but_accepts_ordinary_certificate(self):
        schema = structured_response_schema()
        observation_properties = (
            schema["properties"]["turn_intelligence"]["properties"]
            ["image_observations"]["items"]["properties"]
        )
        self.assertNotIn("prize_certificate", observation_properties)

        result = parse_structured_response({
            "reply_text": "Бачу сертифікат; це ще не підтверджує право на винагороду.",
            "controls": [],
            "turn_intelligence": {
                "catalog_candidates": [],
                "transcript": "",
                "intent": "media_review",
                "confidence": 0.7,
                "image_observations": [{
                    "source_image_index": 0,
                    "outcome": "understood",
                    "evidence_code": "visual_content",
                    "type_code": "certificate",
                }],
            },
        })

        self.assertTrue(result.valid)
        observation = result.turn_intelligence.image_observations[0]
        self.assertEqual(observation.type_code, "certificate")
        self.assertIsNone(observation.prize_certificate)

    def test_note_binds_only_indexes_and_frames_provisional_context(self):
        note = build_contextual_image_note(
            [
                {
                    "source_part_id": "mp1_" + "a" * 32,
                    "content_hash": "b" * 64,
                    "storage_name": "private/customer.jpg",
                    "mime": "image/jpeg",
                    "original_index": 4,
                },
                {
                    "source_part_id": "mp1_" + "c" * 32,
                    "mime": "audio/ogg",
                    "original_index": 5,
                },
                {
                    "source_part_id": "mp1_" + "d" * 32,
                    "mime": "image/png",
                    "original_index": 6,
                },
            ],
            [
                {
                    "source_part_id": "mp1_" + "a" * 32,
                    "role": "product",
                    "intent": "purchase_candidate",
                },
                {
                    "source_part_id": "mp1_" + "d" * 32,
                    "role": "receipt",
                    "intent": "payment_evidence",
                },
            ],
        )

        self.assertIn('"source_image_index":0', note)
        self.assertIn('"source_image_index":2', note)
        self.assertIn('"original_index":4', note)
        self.assertIn('"provisional_role":"product"', note)
        self.assertIn("hints only", note)
        self.assertIn("not verified payment", note)
        self.assertIn("not verified entitlement", note)
        for forbidden in ("source_part_id", "content_hash", "storage_name", "private/customer.jpg"):
            self.assertNotIn(forbidden, note)

    def test_required_general_types_are_finite(self):
        self.assertTrue({
            "receipt", "payment_screenshot", "product", "custom_reference",
            "selfie", "certificate", "document", "other",
        }.issubset(IMAGE_TYPE_CODES))


class ContextualMediaRoleTests(SimpleTestCase):
    @patch("management.services.bot_vision.gemini_generate_text")
    def test_detailed_types_keep_backward_compatible_broad_roles(self, generate):
        generate.return_value = {
            "parsed": (
                '{"items":['
                '{"source_image_index":0,"role":"other","type_code":"payment_screenshot","confidence":0.9,"reason":"transfer screen"},'
                '{"source_image_index":1,"role":"product","type_code":"selfie","confidence":0.8,"reason":"person wearing garment"},'
                '{"source_image_index":2,"role":"other","type_code":"certificate","confidence":0.7,"reason":"certificate layout"}'
                "]}"
            )
        }

        result = bot_vision.classify_media_roles([
            ("image/jpeg", b"payment"),
            ("image/jpeg", b"selfie"),
            ("image/png", b"certificate"),
        ])

        self.assertEqual([item["role"] for item in result], ["receipt", "other", "other"])
        self.assertEqual(
            [item["type_code"] for item in result],
            ["payment_screenshot", "selfie", "certificate"],
        )
