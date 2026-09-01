"""ЭА.20 — контракт structured-output и HTTP 400 INVALID_ARGUMENT.

Порядок тестов повторяет порядок раздела: сначала получить факт (чем именно
живая схема выходит за документированное подмножество и что фиксируется из
ответа 400), потом привести контракт в порядок и доказать, что тот же payload
больше не повторяется, а валидация приложения не ослабла.
"""
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from management.models import AdminAuditLog
from management.services import call_ai_analysis, gemini_payload_contract as contract
from management.services.ig_response_control import (
    parse_structured_response,
    structured_response_schema,
)


class _FakeResponse:
    """Минимальный ответ провайдера: только то, что читает наш код."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


INVALID_ARGUMENT_BODY = {
    "error": {
        "code": 400,
        "message": (
            "Invalid JSON payload received. Unknown name \"minLength\" at "
            "generationConfig.responseJsonSchema.properties.reply_text.minLength: "
            "Cannot find field."
        ),
        "status": "INVALID_ARGUMENT",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.BadRequest",
                "fieldViolations": [
                    {
                        "field": (
                            "generationConfig.responseJsonSchema.properties."
                            "reply_text.minLength"
                        ),
                        "description": "Cannot find field.",
                    }
                ],
            }
        ],
    }
}

OK_BODY = {
    "candidates": [
        {
            "content": {"parts": [{"text": "{\"reply_text\": \"Ок\", \"controls\": []}"}]},
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {"totalTokenCount": 10},
}


def _live_payload():
    """Точная форма живого запроса чата: json-mime плюс responseJsonSchema."""
    return {
        "contents": [{"role": "user", "parts": [{"text": "Привіт"}]}],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
            "responseJsonSchema": structured_response_schema(),
        },
    }


class DocumentedSubsetTests(TestCase):
    """Сверить схему с документированным подмножеством — сначала факт."""

    def test_live_schema_uses_keywords_outside_the_documented_subset(self):
        found = contract.unsupported_keywords(structured_response_schema())
        keywords = {keyword for _path, keyword in found}
        self.assertIn("minLength", keywords)
        self.assertIn("maxLength", keywords)
        paths = {path for path, keyword in found if keyword == "minLength"}
        self.assertTrue(
            any("reply_text" in path or "follow_cta" in path for path in paths),
            f"очікували шлях до конкретного поля, отримали {paths}",
        )

    def test_property_named_like_a_keyword_is_not_reported_as_one(self):
        schema = {
            "type": "object",
            "properties": {"pattern": {"type": "string"}, "default": {"type": "string"}},
        }
        self.assertEqual(contract.unsupported_keywords(schema), ())

    def test_simplified_schema_keeps_the_whole_contract_structure(self):
        live = structured_response_schema()
        simplified = contract.simplify_schema(live)

        self.assertEqual(contract.unsupported_keywords(simplified), ())
        self.assertEqual(simplified["type"], "object")
        self.assertEqual(set(simplified["required"]), set(live["required"]))
        self.assertEqual(
            set(simplified["properties"]), set(live["properties"])
        )
        self.assertEqual(
            simplified["properties"]["controls"]["items"]["properties"]["kind"]["enum"],
            live["properties"]["controls"]["items"]["properties"]["kind"]["enum"],
        )
        self.assertIn(
            "anyOf",
            simplified["properties"]["controls"]["items"]["properties"]["value"],
        )
        self.assertNotIn("minLength", simplified["properties"]["reply_text"])

    def test_fingerprint_separates_variants_and_ignores_conversation(self):
        live = _live_payload()
        other_conversation = _live_payload()
        other_conversation["contents"][0]["parts"][0]["text"] = "Інший клієнт"
        simplified = dict(live)
        simplified["generationConfig"] = dict(live["generationConfig"])
        simplified["generationConfig"]["responseJsonSchema"] = contract.simplify_schema(
            structured_response_schema()
        )

        self.assertEqual(
            contract.contract_fingerprint(live),
            contract.contract_fingerprint(other_conversation),
        )
        self.assertNotEqual(
            contract.contract_fingerprint(live),
            contract.contract_fingerprint(simplified),
        )


class PreflightTests(TestCase):
    """Недопустимое тело не должно доходить до провайдера."""

    def _dispatch(self, payload, response):
        with patch(
            "management.services.call_ai_analysis.requests.post",
            return_value=response,
        ) as post:
            call_ai_analysis._gemini_call_once(
                "gemini-3.7-flash", payload, "test-key", parse=True
            )
        return json.loads(post.call_args.kwargs["data"])

    def test_preflight_strips_undocumented_keywords_before_dispatch(self):
        sent = self._dispatch(_live_payload(), _FakeResponse(200, OK_BODY))
        schema = sent["generationConfig"]["responseJsonSchema"]

        self.assertEqual(contract.unsupported_keywords(schema), ())
        self.assertEqual(sent["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(set(schema["required"]), {"reply_text", "controls"})

    @override_settings(GEMINI_PAYLOAD_CONTRACT_PREFLIGHT=False)
    def test_control_flag_off_sends_the_undocumented_keywords_as_before(self):
        """Control: до правки тіло їхало з `minLength`/`maxLength` як є."""
        sent = self._dispatch(_live_payload(), _FakeResponse(200, OK_BODY))
        schema = sent["generationConfig"]["responseJsonSchema"]

        self.assertIn("minLength", schema["properties"]["reply_text"])
        self.assertNotEqual(contract.unsupported_keywords(schema), ())

    def test_payload_without_a_response_contract_is_untouched(self):
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Привіт"}]}],
            "generationConfig": {"maxOutputTokens": 128},
        }
        sent = self._dispatch(payload, _FakeResponse(200, OK_BODY))
        self.assertEqual(sent["generationConfig"]["maxOutputTokens"], 128)


class InvalidArgumentEvidenceTests(TestCase):
    """Причина 400 фиксируется: код, статус и путь поля — и ничего больше."""

    def _fail_once(self, payload=None):
        payload = payload if payload is not None else _live_payload()
        with patch(
            "management.services.call_ai_analysis.requests.post",
            return_value=_FakeResponse(400, INVALID_ARGUMENT_BODY),
        ) as post:
            with self.assertRaises(call_ai_analysis._GeminiFatal) as raised:
                call_ai_analysis._gemini_call_once(
                    "gemini-3.7-flash", payload, "test-key", parse=True
                )
        return raised.exception, post

    def test_four_hundred_is_attributed_to_the_exact_schema_field(self):
        error, _post = self._fail_once()

        self.assertEqual(error.http_code, 400)
        self.assertEqual(error.error_status, "INVALID_ARGUMENT")
        self.assertEqual(
            error.schema_field_path,
            "generationConfig.responseJsonSchema.properties.reply_text.minLength",
        )

        row = AdminAuditLog.objects.get(action=contract.AUDIT_ACTION)
        self.assertEqual(row.after["code"], 400)
        self.assertEqual(row.after["status"], "INVALID_ARGUMENT")
        self.assertEqual(
            row.after["field"],
            "generationConfig.responseJsonSchema.properties.reply_text.minLength",
        )
        self.assertEqual(row.entity_id, error.contract_fingerprint)

    def test_control_legacy_summary_could_not_name_the_field(self):
        """Control: старе зведення давало лише `INVALID_ARGUMENT` без поля.

        Саме тому висновок розбору production звучав як «точне поле не доказано».
        """
        details = call_ai_analysis._provider_error_details(
            _FakeResponse(400, INVALID_ARGUMENT_BODY)
        )
        legacy_summary = call_ai_analysis._safe_provider_error_summary(
            _FakeResponse(400, INVALID_ARGUMENT_BODY)
        )

        self.assertEqual(legacy_summary, "INVALID_ARGUMENT")
        self.assertNotIn("minLength", legacy_summary)
        self.assertIn("minLength", details["field_path"])

    def test_provider_message_body_is_never_stored(self):
        self._fail_once()
        row = AdminAuditLog.objects.get(action=contract.AUDIT_ACTION)
        stored = json.dumps(row.after, ensure_ascii=False)

        self.assertNotIn("Invalid JSON payload received", stored)
        self.assertNotIn("Cannot find field", stored)
        self.assertNotIn("test-key", stored)

    def test_free_text_and_secrets_never_become_a_field_path(self):
        self.assertEqual(contract.bounded_field_path("secret-key-value"), "")
        self.assertEqual(contract.bounded_field_path("AIzaSyD-super-secret"), "")
        self.assertEqual(
            contract.bounded_field_path("Request contains an invalid argument."), ""
        )
        self.assertEqual(
            contract.bounded_field_path("generationConfig.responseJsonSchema"),
            "generationConfig.responseJsonSchema",
        )

    def test_quota_error_still_keeps_its_typed_retry_evidence(self):
        """Захист від регресії: нові поля не мають ламати розбір 429."""
        body = {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "Quota exceeded for quota metric per minute",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "12s",
                    }
                ],
            }
        }
        details = call_ai_analysis._provider_error_details(_FakeResponse(429, body))
        self.assertEqual(details["quota_scope"], "minute")
        self.assertEqual(details["retry_after_seconds"], 14)
        self.assertEqual(details["field_path"], "")


class NoBlindRetryTests(TestCase):
    """Тот же неверный payload не отправляется второй раз."""

    def _post(self, payload, response):
        with patch(
            "management.services.call_ai_analysis.requests.post",
            return_value=response,
        ) as post:
            try:
                call_ai_analysis._gemini_call_once(
                    "gemini-3.7-flash", payload, "test-key", parse=True
                )
            except call_ai_analysis._GeminiFatal:
                pass
        return post

    @override_settings(GEMINI_PAYLOAD_CONTRACT_PREFLIGHT=False)
    def test_rejected_variant_is_replaced_by_the_predefined_simplified_one(self):
        payload = _live_payload()
        first = self._post(payload, _FakeResponse(400, INVALID_ARGUMENT_BODY))
        first_body = json.loads(first.call_args.kwargs["data"])
        self.assertIn("minLength", first_body["generationConfig"]["responseJsonSchema"]["properties"]["reply_text"])

        # Другий виклик тим самим payload: circuit варіанта вже відкритий, тому
        # тіло підмінюється на заздалегідь визначене спрощене.
        second = self._post(payload, _FakeResponse(200, OK_BODY))
        second_body = json.loads(second.call_args.kwargs["data"])
        self.assertEqual(
            contract.unsupported_keywords(
                second_body["generationConfig"]["responseJsonSchema"]
            ),
            (),
        )

    @override_settings(
        GEMINI_PAYLOAD_CONTRACT_PREFLIGHT=False,
        GEMINI_PAYLOAD_CONTRACT_CIRCUIT=False,
    )
    def test_control_flag_off_repeats_the_identical_rejected_body(self):
        """Control: до правки другий виклик відправляв те саме тіло."""
        payload = _live_payload()
        first = self._post(payload, _FakeResponse(400, INVALID_ARGUMENT_BODY))
        second = self._post(payload, _FakeResponse(400, INVALID_ARGUMENT_BODY))

        self.assertEqual(
            first.call_args.kwargs["data"], second.call_args.kwargs["data"]
        )

    def test_when_every_variant_is_rejected_nothing_reaches_the_provider(self):
        payload = _live_payload()
        # Перший відказ приходить на спрощений варіант (preflight увімкнений).
        self._post(payload, _FakeResponse(400, INVALID_ARGUMENT_BODY))
        self.assertTrue(
            AdminAuditLog.objects.filter(action=contract.AUDIT_ACTION).exists()
        )

        with patch(
            "management.services.call_ai_analysis.requests.post"
        ) as post:
            with self.assertRaises(call_ai_analysis._GeminiFatal):
                call_ai_analysis._gemini_call_once(
                    "gemini-3.7-flash", payload, "test-key", parse=True
                )
        post.assert_not_called()

    def test_invalid_payload_opens_a_contract_circuit_not_a_provider_one(self):
        from management.services import ig_failure_classes as classes

        payload = _live_payload()
        self._post(payload, _FakeResponse(400, INVALID_ARGUMENT_BODY))
        fingerprint = AdminAuditLog.objects.get(action=contract.AUDIT_ACTION).entity_id

        self.assertTrue(contract.contract_circuit_open(fingerprint))
        decision = classes.decide("invalid_payload", 400)
        self.assertTrue(decision.payload_circuit)
        self.assertFalse(decision.provider_circuit)
        self.assertEqual(
            classes.circuit_state("chat", "invalid_payload").reason,
            "not_a_provider_circuit",
        )

    def test_invalid_payload_metric_counts_events(self):
        self._post(_live_payload(), _FakeResponse(400, INVALID_ARGUMENT_BODY))
        self.assertEqual(contract.invalid_payload_count(), 1)


class ApplicationValidationTests(TestCase):
    """Сужение схемы не ослабляет проверку ответа."""

    def test_every_removed_string_bound_is_still_enforced_by_the_validator(self):
        live = structured_response_schema()
        simplified = contract.simplify_schema(live)
        self.assertIn("maxLength", live["properties"]["reply_text"])
        self.assertNotIn("maxLength", simplified["properties"]["reply_text"])

        too_long = parse_structured_response(
            {"reply_text": "я" * 4001, "controls": []}
        )
        self.assertFalse(too_long.valid)
        self.assertEqual(too_long.control, {})

    def test_follow_cta_bounds_are_enforced_after_schema_simplification(self):
        short_cta = parse_structured_response(
            {
                "reply_text": "Ось варіанти.",
                "controls": [],
                "follow_cta": {"include": True, "text": "Підписуйтесь"},
            }
        )
        self.assertIsNone(short_cta.follow_cta)

    def test_response_failing_application_validation_is_not_delivered(self):
        invalid = parse_structured_response({"reply_text": "", "controls": []})
        self.assertFalse(invalid.valid)
        self.assertEqual(invalid.reply_text, "")
        self.assertEqual(invalid.control, {})

    def test_invalid_controls_stay_a_proposal_and_never_become_actions(self):
        result = parse_structured_response(
            {
                "reply_text": "Ось посилання на оплату.",
                "controls": [{"kind": "definitely_not_a_control", "value": True}],
            }
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.control, {})
