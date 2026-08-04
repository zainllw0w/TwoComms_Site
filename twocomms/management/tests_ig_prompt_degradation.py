"""W2 / IMP-011 — деградация промпта перестаёт быть невидимой (F-AI-001, F-AI-002).

Сборка system instruction берёт базу знаний, каталог и playbook-инструкции,
и каждый источник обёрнут в `except Exception: pass`. При сбое любого из них
бот всё равно уходит в Gemini — но без каталога, без цен и без правил
доставки, то есть отвечает по общим знаниям модели. Внешне работает,
фактически выдумывает. В логе — ничего.

Инвариант: невозможность получить контекст всегда оставляет запись уровня
`error` с указанием, какой именно источник отвалился.
"""
from unittest.mock import patch

from django.test import TestCase

from management.models import BotQuickLink, IgClient, InstagramBotLog, InstagramBotSettings


class PromptDegradationVisibilityTests(TestCase):
    def setUp(self):
        self.settings_row = InstagramBotSettings.load()
        self.settings_row.system_prompt = "Ти продавець TwoComms."
        self.settings_row.save(update_fields=["system_prompt"])
        self.client_card = IgClient.objects.create(
            igsid="9000000001", username="prompt_client"
        )

    def _build(self):
        from management.services import instagram_bot as bot

        return bot._context_sections(self.client_card)

    def _errors(self):
        return list(
            InstagramBotLog.objects.filter(level="error").values_list(
                "event", "detail"
            )
        )

    def test_catalog_failure_is_logged(self):
        with patch(
            "management.services.bot_catalog.get_catalog_context",
            side_effect=RuntimeError("catalog exploded"),
        ):
            self._build()

        events = [e for e, _ in self._errors()]
        self.assertIn(
            "prompt_context",
            events,
            "падение каталога обязано оставить error-запись",
        )
        details = " ".join(d for _, d in self._errors())
        self.assertIn("catalog", details)

    def test_brand_knowledge_failure_is_logged(self):
        with patch(
            "management.services.bot_knowledge.get_brand_knowledge",
            side_effect=RuntimeError("kb exploded"),
        ):
            self._build()

        details = " ".join(d for _, d in self._errors())
        self.assertIn("brand_knowledge", details)

    def test_playbook_failure_is_logged(self):
        with patch(
            "management.services.bot_playbooks.active_instruction_block",
            side_effect=RuntimeError("playbook exploded"),
        ):
            self._build()

        details = " ".join(d for _, d in self._errors())
        self.assertIn("playbook", details)

    def test_healthy_build_writes_no_error(self):
        """Без сбоя лишних error-записей быть не должно."""
        self._build()

        self.assertEqual(
            self._errors(), [], "здоровая сборка промпта не пишет ошибок"
        )

    def test_failure_detail_names_the_source_not_just_the_exception(self):
        with patch(
            "management.services.bot_catalog.get_catalog_context",
            side_effect=RuntimeError("catalog exploded"),
        ):
            self._build()

        details = " ".join(d for _, d in self._errors())
        self.assertIn("catalog exploded", details)
        self.assertIn("catalog", details)


class PromptContextBudgetTests(TestCase):
    def setUp(self):
        self.client_card = IgClient.objects.create(
            igsid="9000000099", username="prompt_budget_client"
        )

    def test_catalog_is_requested_in_compact_mode_for_sales_prompt(self):
        from management.services import instagram_bot as bot

        with patch(
            "management.services.bot_catalog.get_catalog_context",
            return_value="CATALOG-ROW",
        ) as get_catalog:
            context = bot._context_sections(self.client_card)

        get_catalog.assert_called_once_with(compact=True)
        self.assertIn("CATALOG-ROW", context)

    def test_brand_knowledge_is_bounded_by_complete_paragraphs(self):
        from management.services import instagram_bot as bot

        first = "BRAND-ONE " + "a" * 1400
        second = "BRAND-TWO " + "b" * 1400
        third = "BRAND-THREE " + "c" * 1400
        with patch(
            "management.services.bot_knowledge.get_brand_knowledge",
            return_value="\n\n".join((first, second, third)),
        ):
            context = bot._context_sections(self.client_card)

        self.assertIn(first, context)
        self.assertIn(second, context)
        self.assertNotIn("BRAND-THREE", context)
        self.assertIn("бази знань: 1 блок(ів) не вмістилися", context)

    def test_quick_links_are_bounded_by_complete_lines(self):
        from management.services import instagram_bot as bot

        urls = []
        for index in range(3):
            url = f"https://links.example/{index}/" + chr(97 + index) * 520
            urls.append(url)
            BotQuickLink.objects.create(label=f"Link {index}", url=url, order=index)

        context = bot._context_sections(self.client_card)

        self.assertIn(urls[0], context)
        self.assertIn(urls[1], context)
        self.assertNotIn(urls[2], context)
        self.assertIn("швидких посилань: 1 блок(ів) не вмістилися", context)


class PinProductVisibilityTests(TestCase):
    """F-AI-002: тихая потеря `pin_product` ломает детерминизм оплаты."""

    def test_pin_product_failure_is_logged(self):
        from management.services import instagram_bot as bot

        client = IgClient.objects.create(igsid="9000000002", username="pin_client")

        with patch(
            "management.services.bot_orders.pin_product",
            side_effect=RuntimeError("pin exploded"),
        ):
            bot._pin_control_product(client, 12345)

        events = list(
            InstagramBotLog.objects.filter(level="error").values_list(
                "event", "detail"
            )
        )
        self.assertTrue(events, "сбой pin_product обязан быть виден в логе")
        self.assertIn("pin_product", " ".join(e for e, _ in events))
