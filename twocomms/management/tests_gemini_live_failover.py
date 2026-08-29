import json
import os
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings

from management.models import GeminiRequestAttempt
from management.services import call_ai_analysis as ai
from management.services import gemini_keys


ENV_KEYS = {
    "GEMINI_API": "chat-key-1",
    "GEMINI_API2": "chat-key-2",
    "GEMINI_API3": "reserve-key-1",
}


class LiveGeminiFailoverContractsTests(TestCase):
    def setUp(self):
        gemini_keys.clear_model_overload()
        gemini_keys.clear_model_unavailable()

    def tearDown(self):
        gemini_keys.clear_model_overload()
        gemini_keys.clear_model_unavailable()

    @patch("management.services.call_ai_analysis.requests.post")
    def test_http_408_and_every_5xx_are_transient(self, post):
        for status_code in (408, 500, 501, 503, 599):
            response = type("Response", (), {})()
            response.status_code = status_code
            response.text = json.dumps({"error": {"status": "UNAVAILABLE"}})
            response.json = lambda: {"error": {"status": "UNAVAILABLE"}}
            post.return_value = response

            with self.subTest(status_code=status_code):
                with self.assertRaises(ai._GeminiTransient):
                    ai._gemini_call_once(
                        "gemini-3.6-flash", {"contents": []}, "redacted-key", parse=False
                    )

    @override_settings(GEMINI_KEY_PROJECT_GROUPS={
        "GEMINI_API": "project-a",
        "GEMINI_API2": "project-a",
        "GEMINI_API3": "project-b",
    })
    def test_primary_timeout_moves_to_a_distinct_known_project(self):
        calls = []
        alias_by_value = {value: key for key, value in ENV_KEYS.items()}

        def fake_once(model, payload, key, *, parse=True, timeout=None):
            calls.append((model, alias_by_value[key]))
            if len(calls) == 1:
                raise ai._GeminiTransient("timeout: first project")
            return "recovered", {}

        with patch.dict(os.environ, ENV_KEYS, clear=False), patch.object(
            ai, "_gemini_call_once", side_effect=fake_once
        ):
            result = ai.gemini_generate_text({"contents": []}, role="chat")

        self.assertEqual(result["parsed"], "recovered")
        # ЭБ.4: модель обычного ответа задаёт тир задачи; проверяемое свойство —
        # переход на ДРУГОЙ известный проект, а не конкретное имя модели.
        primary = gemini_keys.task_model_chain("chat", "customer_chat")[0]
        self.assertEqual(calls[:2], [
            (primary, "GEMINI_API"),
            (primary, "GEMINI_API3"),
        ])

    @override_settings(GEMINI_KEY_PROJECT_GROUPS={
        "GEMINI_API": "project-a",
        "GEMINI_API2": "project-a",
    })
    def test_auth_and_permission_failures_quarantine_available_aliases(self):
        def invalid_key(*_args, **_kwargs):
            raise ai._GeminiFatal("HTTP 400: INVALID_ARGUMENT:API_KEY_INVALID")

        with patch.dict(os.environ, ENV_KEYS, clear=False), patch.object(
            ai, "_gemini_call_once", side_effect=invalid_key
        ):
            with self.assertRaises(ai.CallAIAnalysisError):
                ai.gemini_generate_text({"contents": []}, role="chat")

        self.assertFalse(gemini_keys.is_available("GEMINI_API"))

        gemini_keys.GeminiKeyState.objects.all().update(
            cooldown_until=None,
            cooldown_scope="",
        )

        def permission_denied(*_args, **_kwargs):
            raise ai._GeminiModelUnavailable("HTTP 403: PERMISSION_DENIED")

        with patch.dict(os.environ, ENV_KEYS, clear=False), patch.object(
            ai, "_gemini_call_once", side_effect=permission_denied
        ):
            with self.assertRaises(ai.CallAIAnalysisError):
                ai.gemini_generate_text({"contents": []}, role="chat")

        self.assertFalse(gemini_keys.is_available("GEMINI_API"))
        self.assertFalse(gemini_keys.is_available("GEMINI_API2"))

    def test_open_durable_model_circuit_skips_primary_for_live_chat(self):
        primary = gemini_keys.task_model_chain("chat", "customer_chat")[0]
        gemini_keys.open_model_circuit(primary, reason="transport")
        seen_models = []

        def fake_once(model, payload, key, *, parse=True, timeout=None):
            seen_models.append(model)
            return "fallback", {}

        with patch.dict(os.environ, {"GEMINI_API": "chat-key-1"}, clear=False), patch.object(
            ai, "_gemini_call_once", side_effect=fake_once
        ):
            result = ai.gemini_generate_text({"contents": []}, role="chat")

        fallback = gemini_keys.task_model_chain("chat", "customer_chat")[1]
        self.assertEqual(result["model"], fallback)
        self.assertEqual(seen_models, [fallback])

    def test_404_opens_circuit_and_does_not_try_the_same_model_on_next_key(self):
        calls = []

        chain = gemini_keys.task_model_chain("chat", "customer_chat")
        primary, fallback = chain[0], chain[1]

        def fake_once(model, payload, key, *, parse=True, timeout=None):
            calls.append((model, key))
            if model == primary:
                raise ai._GeminiModelUnavailable("HTTP 404: NOT_FOUND")
            return "fallback", {}

        with patch.dict(os.environ, ENV_KEYS, clear=False), patch.object(
            ai, "_gemini_call_once", side_effect=fake_once
        ):
            result = ai.gemini_generate_text({"contents": []}, role="chat")

        self.assertEqual(result["model"], fallback)
        self.assertEqual(
            [model for model, _key in calls].count(primary),
            1,
        )

    def test_attempt_records_bounded_provider_reason(self):
        def permission_denied(*_args, **_kwargs):
            raise ai._GeminiModelUnavailable("HTTP 403: PERMISSION_DENIED")

        with patch.dict(os.environ, {"GEMINI_API": "chat-key-1"}, clear=False), patch.object(
            ai, "_gemini_call_once", side_effect=permission_denied
        ):
            with self.assertRaises(ai.CallAIAnalysisError):
                ai.gemini_generate_text({"contents": []}, role="chat")

        attempt = (
            GeminiRequestAttempt.objects.filter(outcome="failed")
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.provider_reason, "PERMISSION_DENIED")

    def test_invalid_key_preserves_gemini_http_400_in_telemetry(self):
        def invalid_key(*_args, **_kwargs):
            raise ai._GeminiFatal("HTTP 400: INVALID_ARGUMENT:API_KEY_INVALID")

        with patch.dict(os.environ, {"GEMINI_API": "chat-key-1"}, clear=False), patch.object(
            ai, "_gemini_call_once", side_effect=invalid_key
        ):
            with self.assertRaises(ai.CallAIAnalysisError):
                ai.gemini_generate_text({"contents": []}, role="chat")

        attempt = (
            GeminiRequestAttempt.objects.filter(outcome="failed")
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.failure_kind, "invalid_key")
        self.assertEqual(attempt.http_code, 400)
        self.assertEqual(
            gemini_keys.GeminiKeyState.get("GEMINI_API").last_http_code,
            400,
        )

    def test_http_408_attempt_persists_the_transient_status_code(self):
        def request_timeout(*_args, **_kwargs):
            raise ai._GeminiTransient("HTTP 408: DEADLINE_EXCEEDED")

        with patch.dict(os.environ, {"GEMINI_API": "chat-key-1"}, clear=False), patch.object(
            ai, "_gemini_call_once", side_effect=request_timeout
        ):
            with self.assertRaises(ai.CallAIAnalysisError):
                ai.gemini_generate_text({"contents": []}, role="chat")

        attempt = (
            GeminiRequestAttempt.objects.filter(outcome="failed")
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.failure_kind, "http_408")
        self.assertEqual(attempt.http_code, 408)
        self.assertEqual(attempt.provider_reason, "DEADLINE_EXCEEDED")
