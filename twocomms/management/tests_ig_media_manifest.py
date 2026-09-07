"""B01.3 pure per-part manifest and structured-observation contracts."""
import hashlib
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from management.models import InstagramBotSettings
from management.services import instagram_bot
from management.services.gemini_routing import RoutingDecision, RoutingMode, TaskClass
from management.services.ig_media_manifest import (
    MediaManifestError,
    inline_part_evidence,
    map_image_observations,
    media_coverage,
    normalize_attachment_media,
    public_media_manifest,
)
from management.services.ig_response_control import parse_structured_response


def _digest(character: str) -> str:
    return character * 64


class MediaManifestTests(SimpleTestCase):
    def test_uncertain_content_is_not_counted_as_understood_and_audio_is_not_an_image(self):
        parts = normalize_attachment_media([
            {"status": "owned", "content_hash": _digest("a"), "mime": "audio/ogg",
             "inspection": {"state": "inspected", "outcome": "uncertain"}},
        ], message_scope="mixed-media")
        coverage = media_coverage(parts)
        self.assertEqual(coverage["inspected"], 0)
        self.assertEqual(coverage["uncertain"], 1)
        with self.assertRaisesRegex(MediaManifestError, "audio_is_not_image_observation"):
            map_image_observations(
                parts, [{"source_image_index": 0, "outcome": "understood"}],
                image_count=1, actual_inline_count=1,
                actual_content_hashes=[_digest("a")],
            )

    def test_partial_bundle_keeps_owned_and_missing_parts_separate(self):
        parts = normalize_attachment_media([
            {
                "url": "https://provider.example/one.jpg",
                "status": "owned",
                "content_hash": _digest("a"),
            },
            {
                "url": "https://provider.example/two.jpg",
                "status": "unavailable",
                "error_kind": "download_failed",
            },
        ], message_scope="message:41")

        coverage = media_coverage(parts)
        self.assertEqual(coverage["total"], 2)
        self.assertEqual(coverage["capture_owned"], 1)
        self.assertEqual(coverage["inspected"], 0)
        self.assertEqual(coverage["missing"], 1)

        mapped = map_image_observations(
            [parts[0]],
            [{
                "source_image_index": 0,
                "outcome": "understood",
                "evidence_code": "visual_content",
                "type_code": "product",
            }],
            image_count=1,
            actual_inline_count=1,
            actual_content_hashes=[_digest("a")],
        )
        self.assertEqual(mapped[0]["source_part_id"], parts[0]["source_part_id"])
        self.assertEqual(mapped[0]["content_hash"], _digest("a"))
        self.assertNotIn("url", mapped[0])

    def test_duplicate_urls_remain_distinct_when_their_original_parts_differ(self):
        parts = normalize_attachment_media([
            {"url": "https://provider.example/same.jpg", "original_index": 0},
            {"url": "https://provider.example/same.jpg", "original_index": 1},
        ], message_scope="message:42", identity_origin="ingress")

        self.assertEqual([part["original_index"] for part in parts], [0, 1])
        self.assertNotEqual(parts[0]["source_part_id"], parts[1]["source_part_id"])
        self.assertEqual(parts[0]["identity_origin"], "ingress")

    def test_legacy_positional_identity_is_stable_and_public_manifest_is_redacted(self):
        raw = [{
            "url": "https://provider.example/legacy.jpg",
            "storage_name": "private/legacy.jpg",
            "status": "owned",
            "content_hash": _digest("b"),
        }]
        first = normalize_attachment_media(raw, message_scope="message:43")
        second = normalize_attachment_media(raw, message_scope="message:43")

        self.assertEqual(first[0]["source_part_id"], second[0]["source_part_id"])
        self.assertEqual(first[0]["identity_origin"], "legacy_positional")
        public = public_media_manifest(first)
        self.assertNotIn("url", public[0])
        self.assertNotIn("storage_name", public[0])
        self.assertEqual(public[0]["content_hash"], _digest("b"))

    def test_rejects_wrong_hash_out_of_bound_and_duplicate_image_evidence(self):
        parts = normalize_attachment_media([
            {"status": "owned", "content_hash": _digest("a")},
            {"status": "owned", "content_hash": _digest("b")},
        ], message_scope="message:44")

        with self.assertRaisesRegex(MediaManifestError, "inline_hash_mismatch"):
            inline_part_evidence(
                parts,
                image_count=2,
                actual_inline_count=1,
                actual_content_hashes=[_digest("c")],
            )
        with self.assertRaisesRegex(MediaManifestError, "invalid_image_observation"):
            map_image_observations(
                parts,
                [{
                    "source_image_index": 1,
                    "outcome": "understood",
                    "evidence_code": "visual_content",
                    "type_code": "product",
                }],
                image_count=2,
                actual_inline_count=1,
                actual_content_hashes=[_digest("a")],
            )
        with self.assertRaisesRegex(MediaManifestError, "invalid_image_observation"):
            map_image_observations(
                parts,
                [
                    {
                        "source_image_index": 0,
                        "outcome": "understood",
                        "evidence_code": "visual_content",
                        "type_code": "product",
                    },
                    {
                        "source_image_index": 0,
                        "outcome": "uncertain",
                        "evidence_code": "insufficient_detail",
                        "type_code": "unknown",
                    },
                ],
                image_count=2,
                actual_inline_count=1,
                actual_content_hashes=[_digest("a")],
            )


class StructuredImageObservationTests(SimpleTestCase):
    def test_absent_optional_observations_remain_valid_and_inspect_nothing(self):
        result = parse_structured_response({
            "reply_text": "Бачу вкладення.",
            "controls": [],
            "turn_intelligence": {
                "catalog_candidates": [],
                "transcript": "",
                "intent": "media_review",
                "confidence": 0.7,
            },
        })

        self.assertTrue(result.valid)
        self.assertEqual(result.turn_intelligence.image_observations, ())

    def test_validates_bounded_observations_without_raw_ocr(self):
        result = parse_structured_response({
            "reply_text": "Побачив перше зображення.",
            "controls": [],
            "turn_intelligence": {
                "catalog_candidates": [],
                "transcript": "",
                "intent": "media_review",
                "confidence": 0.7,
                "image_observations": [{
                    "source_image_index": 0,
                    "outcome": "uncertain",
                    "evidence_code": "insufficient_detail",
                    "type_code": "product",
                }],
            },
        })

        observation = result.turn_intelligence.image_observations[0]
        self.assertEqual(observation.source_image_index, 0)
        self.assertEqual(observation.outcome, "uncertain")

    def test_rejects_duplicate_image_indexes(self):
        result = parse_structured_response({
            "reply_text": "Перевіряю.",
            "controls": [],
            "turn_intelligence": {
                "catalog_candidates": [],
                "transcript": "",
                "intent": "media_review",
                "confidence": 0.7,
                "image_observations": [
                    {"source_image_index": 0, "outcome": "understood"},
                    {"source_image_index": 0, "outcome": "uncertain"},
                ],
            },
        })

        self.assertFalse(result.valid)
        self.assertEqual(result.error, "invalid_turn_intelligence")


@patch("management.services.ig_prize_programme.active_shooting_prize_programme", new=lambda: None)
class MediaBundleIntegrationTests(SimpleTestCase):
    def test_live_provider_assigns_identity_before_equal_url_transport_merge(self):
        url = "https://provider.example/shared.jpg"
        parts = instagram_bot._provider_attachment_metadata({
            "mid": "provider-message-55",
            "attachments": [
                {"type": "image", "payload": {"url": url}},
                {"type": "image", "payload": {"url": url}},
            ],
        })

        self.assertEqual(len(parts), 2)
        self.assertEqual([part["original_index"] for part in parts], [0, 1])
        self.assertNotEqual(parts[0]["source_part_id"], parts[1]["source_part_id"])
        self.assertTrue(all(part["identity_origin"] == "ingress" for part in parts))

    def test_merge_preserves_equal_url_parts_and_refreshes_same_part_source(self):
        same_url = "https://provider.example/same.jpg?sig=old"
        parts = instagram_bot._normalize_message_media([
            {"url": same_url, "provenance": "live_webhook", "status": "pending"},
            {"url": same_url, "provenance": "live_webhook", "status": "pending"},
        ], message_scope=51, identity_origin="ingress")

        merged = instagram_bot._merge_attachment_media([], parts, message_scope=51)
        self.assertEqual(len(merged), 2)
        self.assertNotEqual(merged[0]["source_part_id"], merged[1]["source_part_id"])

        owned = dict(merged[0])
        owned.update({
            "status": "owned",
            "storage_name": "private/part-0.jpg",
            "private_storage": True,
            "mime": "image/jpeg",
            "bytes": 3,
            "content_hash": _digest("a"),
        })
        refreshed = {
            **parts[0],
            "url": "https://provider.example/same.jpg?sig=fresh",
        }
        updated = instagram_bot._merge_attachment_media(
            [owned, merged[1]],
            [refreshed],
            message_scope=51,
        )

        self.assertEqual(len(updated), 2)
        self.assertEqual(updated[0]["url"], refreshed["url"])
        self.assertEqual(updated[0]["storage_name"], "private/part-0.jpg")
        self.assertEqual(updated[0]["content_hash"], _digest("a"))

    @patch("management.services.instagram_bot._owned_media_bytes")
    def test_collect_parts_keeps_duplicate_url_identity_and_order(self, owned_bytes):
        owned_bytes.side_effect = [
            ("image/jpeg", b"first"),
            ("image/jpeg", b"second"),
        ]
        media = instagram_bot._normalize_message_media([
            {
                "url": "https://provider.example/same.jpg",
                "provenance": "live_webhook",
                "status": "owned",
                "storage_name": "private/one.jpg",
            },
            {
                "url": "https://provider.example/same.jpg",
                "provenance": "live_webhook",
                "status": "owned",
                "storage_name": "private/two.jpg",
            },
        ], message_scope=52, identity_origin="ingress")

        parts = instagram_bot._collect_media_parts(media, message_id=52)

        self.assertEqual([part["original_index"] for part in parts], [0, 1])
        self.assertEqual([part["data"] for part in parts], [b"first", b"second"])
        self.assertNotEqual(parts[0]["source_part_id"], parts[1]["source_part_id"])

    def _routing(self):
        return RoutingDecision(
            lane="live",
            task_class=TaskClass.COMPLEX_LIVE,
            reason_codes=("media",),
            authority_snapshot_version="test",
            requires_media_reasoning=True,
            commercial_risk="low",
            model_chain=("gemini-test",),
            deadline_ms=1000,
            routing_mode=RoutingMode.ADAPTIVE,
        )

    @patch("management.services.instagram_bot.assemble_system_instruction", return_value="system")
    @patch("management.services.instagram_bot.select_chat_reasoning_task", return_value="media_analysis")
    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_provider_trim_maps_only_actual_successful_part(
        self, generate, _reasoning, _assemble
    ):
        media = instagram_bot._normalize_message_media([
            {"provenance": "live_webhook", "status": "owned", "original_index": 2},
            {"provenance": "live_webhook", "status": "owned", "original_index": 5},
        ], message_scope=53, identity_origin="ingress")
        parts = []
        for item, raw in zip(media, (b"first", b"second"), strict=True):
            parts.append({
                **item,
                "mime": "image/jpeg",
                "bytes": len(raw),
                "content_hash": hashlib.sha256(raw).hexdigest(),
                "data": raw,
            })
        row = SimpleNamespace(
            pk=53,
            created_at=None,
            provider_created_at=None,
            attachment_media=media,
        )
        binding = instagram_bot._source_media_binding(row, parts)
        generate.return_value = {
            "parsed": {
                "reply_text": "Перше зображення зрозуміле; друге не перевірене.",
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
            },
            "usage": {"_request_inline_count": 1, "_request_trimmed_inline": 1},
            "meta": {"used_model": "gemini-actual", "request_id": "request-53"},
        }
        failure = {}

        result = instagram_bot.gemini_generate(
            InstagramBotSettings(),
            [{"role": "user", "text": "Що на фото?"}],
            images=[("image/jpeg", b"first"), ("image/jpeg", b"second")],
            failure_context=failure,
            routing_decision=self._routing(),
            turn_candidate_set={
                "version": "test",
                "complete": True,
                "overflow": False,
                "candidates": [],
                "digest": instagram_bot._turn_candidate_digest([]),
            },
            turn_media_binding=binding,
        )

        self.assertTrue(result.valid)
        intelligence = failure["turn_intelligence"]
        self.assertEqual(len(intelligence["image_observations"]), 1)
        self.assertEqual(
            intelligence["image_observations"][0]["source_part_id"],
            parts[0]["source_part_id"],
        )
        self.assertEqual(intelligence["media_request"]["actual_inline_count"], 1)
        provider_payload = generate.call_args.args[0]
        serialized = str(provider_payload)
        self.assertNotIn("source_part_id", serialized)
        self.assertNotIn("provider.example", serialized)

    @patch("management.services.instagram_bot.assemble_system_instruction", return_value="system")
    @patch("management.services.instagram_bot.select_chat_reasoning_task", return_value="media_analysis")
    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_missing_provider_inline_count_does_not_prove_inspection(
        self, generate, _reasoning, _assemble
    ):
        raw = b"one"
        part = instagram_bot._normalize_message_media([{
            "provenance": "live_webhook",
            "status": "owned",
        }], message_scope=54, identity_origin="ingress")[0]
        part.update({
            "mime": "image/jpeg",
            "bytes": len(raw),
            "content_hash": hashlib.sha256(raw).hexdigest(),
            "data": raw,
        })
        binding = instagram_bot._source_media_binding(
            SimpleNamespace(
                pk=54,
                created_at=None,
                provider_created_at=None,
                attachment_media=[part],
            ),
            [part],
        )
        generate.return_value = {
            "parsed": {
                "reply_text": "Отримав зображення.",
                "controls": [],
                "turn_intelligence": {
                    "catalog_candidates": [],
                    "transcript": "OCR must not become audio",
                    "intent": "media_review",
                    "confidence": 0.6,
                    "image_observations": [{
                        "source_image_index": 0,
                        "outcome": "understood",
                        "evidence_code": "text_visible",
                        "type_code": "document",
                    }],
                },
            },
            "usage": {},
            "model": "gemini-actual",
            "meta": {"request_id": "request-54"},
        }
        failure = {}

        result = instagram_bot.gemini_generate(
            InstagramBotSettings(),
            [{"role": "user", "text": "Що тут?"}],
            images=[("image/jpeg", raw)],
            failure_context=failure,
            routing_decision=self._routing(),
            turn_candidate_set={
                "version": "test",
                "complete": True,
                "overflow": False,
                "candidates": [],
                "digest": instagram_bot._turn_candidate_digest([]),
            },
            turn_media_binding=binding,
        )

        self.assertTrue(result.valid)
        intelligence = failure["turn_intelligence"]
        self.assertEqual(intelligence["image_observations"], [])
        self.assertEqual(intelligence["transcript"], "")
        self.assertFalse(intelligence["media_request"]["inline_count_known"])

    @patch("management.services.instagram_bot.assemble_system_instruction", return_value="system")
    @patch("management.services.instagram_bot.select_chat_reasoning_task", return_value="media_analysis")
    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_four_small_contextual_images_share_one_exact_live_request(
        self, generate, _reasoning, _assemble
    ):
        raw_values = (b"receipt", b"selfie", b"certificate", b"product")
        type_codes = ("receipt", "selfie", "certificate", "product")
        media = instagram_bot._normalize_message_media([
            {
                "provenance": "live_webhook",
                "status": "owned",
                "original_index": index + 3,
            }
            for index in range(4)
        ], message_scope=55, identity_origin="ingress")
        parts = []
        provisional = []
        for index, (item, raw) in enumerate(zip(media, raw_values, strict=True)):
            part = {
                **item,
                "mime": "image/jpeg",
                "bytes": len(raw),
                "content_hash": hashlib.sha256(raw).hexdigest(),
                "data": raw,
            }
            parts.append(part)
            provisional.append({
                "source_part_id": part["source_part_id"],
                "original_index": part["original_index"],
                "role": "receipt" if index == 0 else "product" if index == 3 else "other",
                "intent": "payment_evidence" if index == 0 else "interest",
            })
        binding = instagram_bot._source_media_binding(
            SimpleNamespace(
                pk=55,
                created_at=None,
                provider_created_at=None,
                attachment_media=media,
            ),
            parts,
        )
        generate.return_value = {
            "parsed": {
                "reply_text": "Бачу всі чотири зображення та врахувала їхній контекст.",
                "controls": [],
                "turn_intelligence": {
                    "catalog_candidates": [],
                    "transcript": "",
                    "intent": "media_review",
                    "confidence": 0.8,
                    "image_observations": [
                        {
                            "source_image_index": index,
                            "outcome": "understood",
                            "evidence_code": "visual_content",
                            "type_code": type_code,
                        }
                        for index, type_code in enumerate(type_codes)
                    ],
                },
            },
            "usage": {"_request_inline_count": 4},
            "model": "gemini-actual",
            "meta": {"request_id": "request-55"},
        }
        failure = {}

        result = instagram_bot.gemini_generate(
            InstagramBotSettings(),
            [{"role": "user", "text": "Чек, селфі, сертифікат і товар."}],
            images=[(part["mime"], part["data"]) for part in parts],
            failure_context=failure,
            routing_decision=self._routing(),
            turn_candidate_set={
                "version": "test",
                "complete": True,
                "overflow": False,
                "candidates": [],
                "digest": instagram_bot._turn_candidate_digest([]),
            },
            turn_media_binding=binding,
            turn_media_context=provisional,
        )

        self.assertTrue(result.valid)
        self.assertEqual(len(failure["turn_intelligence"]["image_observations"]), 4)
        payload = generate.call_args.args[0]
        inline = [
            part
            for content in payload["contents"]
            for part in content["parts"]
            if "inline_data" in part
        ]
        self.assertEqual(len(inline), 4)
        system_text = payload["system_instruction"]["parts"][0]["text"]
        for index in range(4):
            self.assertIn(f'"source_image_index":{index}', system_text)
        self.assertIn("not verified payment", system_text)
        self.assertIn("not verified entitlement", system_text)
        self.assertNotIn("source_part_id", system_text)
        self.assertNotIn(parts[0]["content_hash"], system_text)

    def test_actual_inline_image_requires_one_bound_observation(self):
        raw = b"image"
        part = instagram_bot._normalize_message_media([{
            "provenance": "live_webhook",
            "status": "owned",
            "mime": "image/jpeg",
            "content_hash": hashlib.sha256(raw).hexdigest(),
        }], message_scope=56, identity_origin="ingress")[0]
        parsed = parse_structured_response({
            "reply_text": "Бачу вкладення.",
            "controls": [],
            "turn_intelligence": {
                "catalog_candidates": [],
                "transcript": "",
                "intent": "media_review",
                "confidence": 0.7,
                "image_observations": [],
            },
        })
        binding = {
            "version": "owned-media-v2",
            "source_message_id": 56,
            "source_message_revision": "revision",
            "items": [{
                **part,
                "bytes": len(raw),
            }],
            "content_hashes": [part["content_hash"]],
            "count": 1,
            "digest": "digest",
            "provider_model": "gemini-actual",
            "request_id": "request-56",
            "actual_inline_count": 1,
            "actual_content_hashes": [part["content_hash"]],
        }

        self.assertEqual(
            instagram_bot._validated_turn_intelligence(
                parsed.turn_intelligence,
                {
                    "version": "test",
                    "complete": True,
                    "overflow": False,
                    "candidates": [],
                    "digest": instagram_bot._turn_candidate_digest([]),
                },
                binding,
            ),
            {},
        )

    def test_rejects_free_text_evidence_code(self):
        result = parse_structured_response({
            "reply_text": "Перевіряю.",
            "controls": [],
            "turn_intelligence": {
                "catalog_candidates": [],
                "transcript": "",
                "intent": "media_review",
                "confidence": 0.7,
                "image_observations": [{
                    "source_image_index": 0,
                    "outcome": "understood",
                    "evidence_code": "document_number_12345",
                    "type_code": "document",
                }],
            },
        })

        self.assertFalse(result.valid)
        self.assertEqual(result.error, "invalid_turn_intelligence")
