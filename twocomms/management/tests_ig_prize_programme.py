from django.test import SimpleTestCase, TestCase

from management.models import BotInstruction
from management.services.ig_media_manifest import (
    map_image_observations,
    normalize_attachment_media,
)
from management.services.ig_prize_programme import (
    PROGRAMME_ID,
    RESERVED_INTENT_TAG,
    PrizeProgramme,
    active_shooting_prize_programme,
    validate_prize_observation,
)
from management.services.ig_response_control import parse_structured_response


def _programme(*, version="test-version", confirmed=False):
    return PrizeProgramme(
        programme_id=PROGRAMME_ID,
        version=version,
        instruction="Visible target/range cues only; ask catalogue or custom preference.",
        cue_codes=("programme_mark", "shooting_target"),
        confirmed_visual_sample=confirmed,
    )


def _observation(*, version="test-version", status="uncertain", cues=None, reason="visible_programme_cues"):
    return {
        "programme_id": PROGRAMME_ID,
        "programme_version": version,
        "status": status,
        "cue_codes": list(cues if cues is not None else ["shooting_target"]),
        "reason_code": reason,
        "manager_required": True,
    }


def _payload(observation, *, type_code="certificate"):
    return {
        "reply_text": "Перевіряю зображення.",
        "controls": [],
        "turn_intelligence": {
            "catalog_candidates": [],
            "transcript": "",
            "intent": "media_review",
            "confidence": 0.6,
            "image_observations": [{
                "source_image_index": 0,
                "outcome": "uncertain",
                "evidence_code": "visual_content",
                "type_code": type_code,
                "prize_certificate": observation,
            }],
        },
    }


class PrizeProgrammeLoaderTests(TestCase):
    def test_exact_reserved_tag_selects_one_active_plain_language_instruction(self):
        instruction = BotInstruction.objects.create(
            title="Editable shooting copy",
            body="If visible target and programme mark match, ask catalogue or custom.",
            intent_tags=f"global,{RESERVED_INTENT_TAG}",
            priority=12,
        )

        programme = active_shooting_prize_programme()

        self.assertIsNotNone(programme)
        self.assertEqual(programme.programme_id, PROGRAMME_ID)
        self.assertIn("catalogue", programme.instruction)
        first_version = programme.version
        instruction.body += " Updated."
        instruction.save(update_fields=["body", "updated_at"])
        self.assertNotEqual(active_shooting_prize_programme().version, first_version)

    def test_missing_or_ambiguous_programme_fails_closed(self):
        self.assertIsNone(active_shooting_prize_programme())
        for index in range(2):
            BotInstruction.objects.create(
                body=f"programme {index}", intent_tags=RESERVED_INTENT_TAG,
            )
        self.assertIsNone(active_shooting_prize_programme())


class PrizeObservationContractTests(SimpleTestCase):
    def test_foreign_certificate_is_not_match(self):
        result = parse_structured_response(
            _payload(_observation(status="not_match", cues=[], reason="foreign_certificate")),
            prize_programme=_programme(),
        )

        self.assertTrue(result.valid)
        self.assertEqual(
            result.turn_intelligence.image_observations[0].prize_certificate.status,
            "not_match",
        )

    def test_wrong_version_or_receipt_cannot_be_prize(self):
        self.assertFalse(parse_structured_response(
            _payload(_observation(version="wrong-version")), prize_programme=_programme(),
        ).valid)
        self.assertFalse(parse_structured_response(
            _payload(_observation(cues=["shooting_range"])), prize_programme=_programme(),
        ).valid)
        self.assertFalse(parse_structured_response(
            _payload(_observation(), type_code="receipt"), prize_programme=_programme(),
        ).valid)

    def test_unverified_programme_caps_recognition_and_rejects_financial_fields(self):
        capped = validate_prize_observation(
            _observation(status="recognized"), programme=_programme(),
        )
        self.assertEqual(capped.status, "uncertain")
        financial = _observation()
        financial["paid"] = True
        self.assertIsNone(validate_prize_observation(financial, programme=_programme()))

    def test_manifest_binds_only_configured_prize_to_the_actual_part(self):
        parts = normalize_attachment_media(
            [{"status": "owned", "mime": "image/jpeg", "content_hash": "a" * 64}],
            message_scope="prize-message",
        )
        mapped = map_image_observations(
            parts,
            [{
                "source_image_index": 0,
                "outcome": "uncertain",
                "evidence_code": "visual_content",
                "type_code": "certificate",
                "prize_certificate": _observation(),
            }],
            image_count=1,
            actual_inline_count=1,
            actual_content_hashes=["a" * 64],
            prize_programme=_programme(),
        )

        self.assertEqual(mapped[0]["content_hash"], "a" * 64)
        self.assertEqual(mapped[0]["prize_certificate"]["programme_id"], PROGRAMME_ID)
