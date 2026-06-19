"""Тести Phase 4 / Tasks 14-15 — playbook продавця + інжект інструкцій/посилань."""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from management.models import (
    BotInstruction,
    BotQuickLink,
    DEFAULT_BOT_SYSTEM_PROMPT,
    InstagramBotSettings,
)
from management.services import instagram_bot as bot


class PlaybookPromptTests(SimpleTestCase):
    def test_prompt_has_control_tag_protocol(self):
        p = DEFAULT_BOT_SYSTEM_PROMPT
        for token in ["[STAGE:", "[MANAGER]", "[PAYLINK:", "[ORDER]", "[SPAM]"]:
            self.assertIn(token, p)

    def test_prompt_has_sales_and_safety_rules(self):
        p = DEFAULT_BOT_SYSTEM_PROMPT.lower()
        self.assertIn("каталог", p)
        self.assertIn("передоплат", p)  # передоплата 200
        # не вивалювати всі посилання
        self.assertTrue("посилань" in p or "каталог" in p)


class QuickLinkActiveBlockTests(TestCase):
    def test_active_block_lists_links(self):
        BotQuickLink.objects.create(
            kind=BotQuickLink.Kind.SIZE_CHART, label="Розмірна сітка худі",
            url="https://ig/hl/hoodie", garment_type="hoodie",
        )
        BotQuickLink.objects.create(
            kind=BotQuickLink.Kind.CATALOG, label="Каталог футболок",
            url="https://twocomms.shop/c/tshirts", is_active=False,
        )
        block = BotQuickLink.active_block()
        self.assertIn("https://ig/hl/hoodie", block)
        self.assertNotIn("tshirts", block)  # неактивне не потрапляє


class ContextInjectionTests(TestCase):
    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_instructions_and_links_injected(self, mock_gen):
        captured = {}

        def _fake(payload, role="chat", manual_key=None, **kwargs):
            captured["payload"] = payload
            return {"parsed": "ок", "model": "x", "meta": {}}

        mock_gen.side_effect = _fake
        BotInstruction.objects.create(title="Графік", body="Працюємо щодня 10-20")
        BotQuickLink.objects.create(
            kind=BotQuickLink.Kind.SIZE_CHART, label="Сітка худі", url="https://ig/hl/h"
        )
        s = InstagramBotSettings.load()
        bot.gemini_generate(s, [{"role": "user", "text": "привіт"}])
        sysi = captured["payload"].get("system_instruction", {}).get("parts", [{}])[0].get("text", "")
        self.assertIn("Працюємо щодня 10-20", sysi)
        self.assertIn("https://ig/hl/h", sysi)


class BrandKnowledgeTests(TestCase):
    def test_brand_md_filled(self):
        from django.core.cache import cache

        from management.services.bot_knowledge import get_brand_knowledge

        cache.clear()
        kb = get_brand_knowledge()
        self.assertIn("Пошт", kb)  # Нова Пошта / Новою Поштою
        self.assertIn("200 грн", kb)
        self.assertIn("передопла", kb.lower())
        self.assertNotIn("TODO", kb)
