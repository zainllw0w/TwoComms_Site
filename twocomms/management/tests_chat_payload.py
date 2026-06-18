"""Тести payload діалогового бота: 3.5-flash (thinking-модель) має лишати
бюджет на сам текст відповіді, інакше finishReason=MAX_TOKENS → порожньо."""
from unittest.mock import patch

from django.test import TestCase

from management.models import InstagramBotSettings
from management.services import instagram_bot as bot


class ChatPayloadThinkingTests(TestCase):
    def test_chat_payload_caps_thinking_and_has_room_for_reply(self):
        s = InstagramBotSettings.load()
        captured = {}

        def fake_text(payload, *, role="chat", manual_key=None):
            captured["payload"] = payload
            captured["role"] = role
            return {"parsed": "Привіт!", "model": "gemini-3.5-flash", "meta": {"key": "GEMINI_API"}}

        with patch("management.services.call_ai_analysis.gemini_generate_text", side_effect=fake_text):
            out = bot.gemini_generate(s, [{"role": "user", "text": "Привіт"}])

        self.assertEqual(out, "Привіт!")
        cfg = captured["payload"]["generationConfig"]
        # thinking обмежений (0 = вимкнено) — чат потребує прямої швидкої відповіді
        self.assertIn("thinkingConfig", cfg)
        self.assertEqual(cfg["thinkingConfig"]["thinkingBudget"], 0)
        # достатньо токенів на сам текст відповіді (не зʼїдається thinking-ом)
        self.assertGreaterEqual(cfg["maxOutputTokens"], 1536)
        self.assertEqual(captured["role"], "chat")
