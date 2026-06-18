from unittest.mock import patch

from django.test import SimpleTestCase

from management.services import call_ai_analysis as caa


class GeminiGroundedTests(SimpleTestCase):
    def test_builds_grounded_payload_and_returns_parsed(self):
        captured = {}

        def fake_call_once(model, payload, key):
            captured["model"] = model
            captured["payload"] = payload
            captured["key"] = key
            return {"overall_score": 80}, {"totalTokenCount": 123}

        with patch.object(caa, "_resolve_gemini_key", return_value="env-key"), \
             patch.object(caa, "_gemini_call_once", side_effect=fake_call_once):
            out = caa.gemini_generate_grounded("SYS", "USER", models=["gemini-2.5-flash"])

        self.assertEqual(out["parsed"], {"overall_score": 80})
        self.assertEqual(out["model"], "gemini-2.5-flash")
        self.assertEqual(captured["payload"]["tools"], [{"google_search": {}}])
        self.assertNotIn("responseMimeType", captured["payload"]["generationConfig"])
        self.assertEqual(captured["key"], "env-key")

    def test_api_key_override_wins(self):
        with patch.object(caa, "_gemini_call_once", return_value=({"x": 1}, {})):
            out = caa.gemini_generate_grounded("S", "U", api_key="override-key", models=["m"])
        self.assertEqual(out["parsed"], {"x": 1})

    def test_400_skips_to_next_model(self):
        calls = []

        def fake_call_once(model, payload, key):
            calls.append(model)
            if model == "bad-model":
                raise caa._GeminiFatal("HTTP 400: tool not supported")
            return {"ok": True}, {}

        with patch.object(caa, "_resolve_gemini_key", return_value="k"), \
             patch.object(caa, "_gemini_call_once", side_effect=fake_call_once):
            out = caa.gemini_generate_grounded("S", "U", models=["bad-model", "good-model"])

        self.assertEqual(out["parsed"], {"ok": True})
        self.assertEqual(calls, ["bad-model", "good-model"])

    def test_no_key_raises(self):
        with patch.object(caa, "_resolve_gemini_key", return_value=""):
            with self.assertRaises(caa.CallAIAnalysisError):
                caa.gemini_generate_grounded("S", "U", models=["m"])
