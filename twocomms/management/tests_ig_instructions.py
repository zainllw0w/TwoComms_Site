"""Тести Phase 0 / Task 4 — моделі UI-інструкцій бота.

BotInstruction — нескінченні інструкції (інжектяться в промпт), BotQuickLink —
швидкі посилання (розмірні сітки-хайлайти, каталог), BotAdCampaign — мапінг
рекламної кампанії на товар/тему.
"""
from django.test import TestCase

from management.models import BotAdCampaign, BotInstruction, BotQuickLink


class BotInstructionTests(TestCase):
    def test_active_block_joins_active_only(self):
        BotInstruction.objects.create(title="Доставка", body="Доставка 1-3 дні", priority=1)
        BotInstruction.objects.create(title="Промо", body="Знижка діє до п'ятниці", priority=2)
        BotInstruction.objects.create(title="Старе", body="Старе правило", is_active=False)
        block = BotInstruction.active_block()
        self.assertIn("Доставка 1-3 дні", block)
        self.assertIn("Знижка", block)
        self.assertNotIn("Старе правило", block)

    def test_priority_ordering(self):
        BotInstruction.objects.create(title="low", body="x", priority=10)
        BotInstruction.objects.create(title="high", body="y", priority=1)
        self.assertEqual(BotInstruction.objects.first().title, "high")


class BotQuickLinkTests(TestCase):
    def test_for_garment_returns_size_chart(self):
        BotQuickLink.objects.create(
            kind=BotQuickLink.Kind.SIZE_CHART,
            label="Розмірна сітка худі",
            url="https://ig/highlight/hoodie",
            garment_type="hoodie",
        )
        link = BotQuickLink.for_garment("hoodie", kind=BotQuickLink.Kind.SIZE_CHART)
        self.assertIsNotNone(link)
        self.assertEqual(link.url, "https://ig/highlight/hoodie")

    def test_inactive_excluded(self):
        BotQuickLink.objects.create(
            kind=BotQuickLink.Kind.SIZE_CHART, label="x", url="u",
            garment_type="tshirt", is_active=False,
        )
        self.assertIsNone(BotQuickLink.for_garment("tshirt"))


class BotAdCampaignTests(TestCase):
    def test_match_by_ad_id(self):
        BotAdCampaign.objects.create(ad_id="999", title="Hoodie Kharkiv", theme="kharkiv")
        c = BotAdCampaign.match(ad_id="999")
        self.assertIsNotNone(c)
        self.assertEqual(c.theme, "kharkiv")

    def test_match_none_when_absent(self):
        self.assertIsNone(BotAdCampaign.match(ad_id="nope"))
