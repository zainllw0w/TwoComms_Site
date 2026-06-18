from unittest.mock import patch

from django.test import TestCase

from management.services import call_ai_analysis as caa
from management.services import gemini_keys as gk

ENV6 = {f"GEMINI_API{n}": f"key-val-{n or '1'}" for n in ("", "2", "3", "4", "5", "6")}


class GeminiGroundedPoolTests(TestCase):
    def setUp(self):
        gk.clear_model_overload()

    def test_grounded_skips_gen3_and_uses_25_flash(self):
        """grounded на gen-3 → 429 (не free) → model_skip, успіх на 2.5-flash, ключ НЕ в кулдауні."""
        def fake(model, payload, key, *, parse=True):
            if model == "gemini-2.5-flash":
                return ({"overall_score": 80}, {"totalTokenCount": 50})
            raise caa._Gemini429("quota plan and billing")

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            out = caa.gemini_generate_grounded("SYS", "USER")

        self.assertEqual(out["parsed"], {"overall_score": 80})
        self.assertEqual(out["model"], "gemini-2.5-flash")
        # Ключ checker-пулу НЕ повинен піти в кулдаун через grounding-429 на gen-3.
        self.assertTrue(gk.is_available("GEMINI_API5"))

    def test_grounded_payload_has_google_search_no_json_mime(self):
        captured = {}

        def fake(model, payload, key, *, parse=True):
            captured["payload"] = payload
            return ({"ok": True}, {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            caa.gemini_generate_grounded("SYS", "USER")

        self.assertEqual(captured["payload"]["tools"], [{"google_search": {}}])
        self.assertNotIn("responseMimeType", captured["payload"]["generationConfig"])

    def test_manual_key_tried_first(self):
        seen_keys = []

        def fake(model, payload, key, *, parse=True):
            seen_keys.append(key)
            if model == "gemini-2.5-flash":
                return ({"x": 1}, {})
            raise caa._Gemini429("billing")

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            out = caa.gemini_generate_grounded("S", "U", api_key="manual-key")

        self.assertEqual(out["parsed"], {"x": 1})
        self.assertEqual(seen_keys[0], "manual-key")
        self.assertEqual(out["meta"]["key"], "(manual)")

    def test_400_raises(self):
        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=caa._GeminiFatal("HTTP 400")):
            with self.assertRaises(caa.CallAIAnalysisError):
                caa.gemini_generate_grounded("S", "U")


class GeminiJsonPoolTests(TestCase):
    def setUp(self):
        gk.clear_model_overload()

    def test_free_model_429_cools_key_and_moves_to_next(self):
        """429 на free-моделі (3.5-flash, non-grounded) = вичерпана квота ПРОЕКТУ →
        кулдаун ключа, перехід на наступний ключ пулу."""
        def fake(model, payload, key, *, parse=True):
            if key == "key-val-3":
                raise caa._Gemini429("PerDay quota exceeded, check your plan and billing")
            return ({"ok": True}, {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            out = caa.gemini_generate_json("SYS", "USER", role="management")

        self.assertEqual(out["parsed"], {"ok": True})
        self.assertEqual(out["meta"]["key"], "GEMINI_API4")
        self.assertFalse(gk.is_available("GEMINI_API3"))  # ключ у кулдауні
        self.assertTrue(gk.is_available("GEMINI_API4"))

    def test_503_falls_back_to_next_model_same_key(self):
        def fake(model, payload, key, *, parse=True):
            if model == "gemini-3.5-flash":
                raise caa._GeminiTransient("HTTP 503")
            return ({"ok": True}, {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake), \
             patch("management.services.call_ai_analysis.time.sleep", return_value=None):
            out = caa.gemini_generate_json("S", "U", role="management")

        self.assertEqual(out["parsed"], {"ok": True})
        self.assertNotEqual(out["model"], "gemini-3.5-flash")
        self.assertTrue(gk.is_model_overloaded("gemini-3.5-flash"))
        gk.clear_model_overload()

    def test_all_exhausted_raises(self):
        def fake(model, payload, key, *, parse=True):
            raise caa._Gemini429("PerDay quota plan and billing")

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            with self.assertRaises(caa.CallAIAnalysisError):
                caa.gemini_generate_json("S", "U", role="management")


class GeminiTextPoolTests(TestCase):
    def setUp(self):
        gk.clear_model_overload()

    def test_text_mode_returns_raw_text(self):
        def fake(model, payload, key, *, parse=True):
            assert parse is False
            return ("Привіт! Чим допомогти?", {"totalTokenCount": 12})

        payload = {"contents": [{"role": "user", "parts": [{"text": "хай"}]}],
                   "generationConfig": {"temperature": 0.6, "maxOutputTokens": 700}}
        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            out = caa.gemini_generate_text(payload, role="chat")
        self.assertEqual(out["parsed"], "Привіт! Чим допомогти?")

    def test_chat_role_starts_with_chat_keys(self):
        seen = []

        def fake(model, payload, key, *, parse=True):
            seen.append((key, model))
            return ("ok-text", {})

        payload = {"contents": [{"role": "user", "parts": [{"text": "хай"}]}]}
        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            caa.gemini_generate_text(payload, role="chat")
        # перший ключ chat-пулу = GEMINI_API, перша модель = gemini-3.5-flash
        self.assertEqual(seen[0], ("key-val-1", "gemini-3.5-flash"))

    def test_chat_manual_key_first(self):
        seen = []

        def fake(model, payload, key, *, parse=True):
            seen.append(key)
            return ("ok", {})

        payload = {"contents": [{"role": "user", "parts": [{"text": "хай"}]}]}
        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            caa.gemini_generate_text(payload, role="chat", manual_key="bot-custom")
        self.assertEqual(seen[0], "bot-custom")
