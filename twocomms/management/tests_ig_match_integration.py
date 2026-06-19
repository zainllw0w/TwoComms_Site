"""Тести Phase 2 / Task 9 — інтеграція матчингу у воркер.

Коли клієнт присилає фото/пост, бот запускає bot_vision.match і додає в контекст
підказку: при високій впевненості — назву+ціну товару; при низькій — «не вигадуй».
"""
from unittest.mock import patch

from django.test import TestCase

from management.models import InstagramBotSettings
from management.services import instagram_bot as bot


class MatchHintTextTests(TestCase):
    def setUp(self):
        from storefront.models import Category, Product, ProductStatus

        cat = Category.objects.create(name="Худі", slug="hudi-mh")
        self.p = Product.objects.create(
            title="Худі Kharkiv", slug="hk-mh", category=cat, price=950,
            status=ProductStatus.PUBLISHED,
        )

    def test_high_confidence_names_product_and_price(self):
        hint = bot._match_hint_text({"product_id": self.p.id, "confidence": 0.9, "reason": "x"})
        self.assertIn("Худі Kharkiv", hint)
        self.assertIn("950", hint)

    def test_low_confidence_says_dont_invent(self):
        hint = bot._match_hint_text({"product_id": None, "confidence": 0.0, "reason": "x"})
        self.assertIn("не вигадуй", hint.lower())

    def test_none_returns_none(self):
        self.assertIsNone(bot._match_hint_text(None))


class GeminiMatchHintInjectionTests(TestCase):
    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_match_hint_injected_into_system_instruction(self, mock_gen):
        captured = {}

        def _fake(payload, role="chat", manual_key=None):
            captured["payload"] = payload
            return {"parsed": "ок", "model": "x", "meta": {}}

        mock_gen.side_effect = _fake
        s = InstagramBotSettings.load()
        bot.gemini_generate(
            s, [{"role": "user", "text": "скільки?"}], match_hint="ТЕСТ-ХІНТ-123"
        )
        sysi = (
            captured["payload"].get("system_instruction", {}).get("parts", [{}])[0].get("text", "")
        )
        self.assertIn("ТЕСТ-ХІНТ-123", sysi)
