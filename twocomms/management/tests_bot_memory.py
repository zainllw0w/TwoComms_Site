"""Тести Phase 3 / Task 10 — пам'ять діалогу (rolling summary) + ретеншн.

Щоб бот «пам'ятав» клієнта на 6 місяців без перегріву токенів: стара історія
стискається у memory_summary (management-модель), у контекст іде summary +
свіже вікно. purge_stale_clients чистить картки, неактивні понад 180 днів.
"""
import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, InstagramBotMessage
from management.services import bot_memory


class MemoryNoteTests(TestCase):
    def test_none_when_empty(self):
        c = IgClient.get_or_create_for_sender("m1")
        self.assertIsNone(bot_memory.memory_note(c))

    def test_text_when_set(self):
        c = IgClient.get_or_create_for_sender("m2")
        c.memory_summary = "хоче худі Kharkiv, розмір M, 950 грн"
        c.save()
        note = bot_memory.memory_note(c)
        self.assertIsNotNone(note)
        self.assertIn("Kharkiv", note)


class UpdateMemoryTests(TestCase):
    @patch("management.services.bot_memory.gemini_generate_text")
    def test_update_sets_summary_and_timestamp(self, mock_gen):
        mock_gen.return_value = {"parsed": "Клієнт хоче худі Kharkiv розмір M за 950 грн."}
        c = IgClient.get_or_create_for_sender("m3")
        InstagramBotMessage.objects.create(sender_id="m3", client=c, role="user", text="скільки худі Kharkiv?")
        self.assertTrue(bot_memory.update_client_memory(c))
        c.refresh_from_db()
        self.assertIn("Kharkiv", c.memory_summary)
        self.assertIsNotNone(c.memory_updated_at)

    @patch("management.services.bot_memory.update_client_memory")
    def test_maybe_update_triggers_on_threshold(self, mock_upd):
        c = IgClient.get_or_create_for_sender("m4")
        for i in range(8):
            InstagramBotMessage.objects.create(sender_id="m4", client=c, role="user", text=f"t{i}")
        bot_memory.maybe_update_memory(c, every=8)
        self.assertEqual(mock_upd.call_count, 1)

    @patch("management.services.bot_memory.update_client_memory")
    def test_maybe_update_skips_below_threshold(self, mock_upd):
        c = IgClient.get_or_create_for_sender("m5")
        InstagramBotMessage.objects.create(sender_id="m5", client=c, role="user", text="hi")
        bot_memory.maybe_update_memory(c, every=8)
        self.assertEqual(mock_upd.call_count, 0)


class RetentionTests(TestCase):
    def test_purge_stale_clients(self):
        old = IgClient.get_or_create_for_sender("old1")
        old.last_message_at = timezone.now() - datetime.timedelta(days=200)
        old.save()
        fresh = IgClient.get_or_create_for_sender("fresh1")
        fresh.last_message_at = timezone.now()
        fresh.save()
        n = bot_memory.purge_stale_clients(days=180)
        self.assertEqual(n, 1)
        self.assertFalse(IgClient.objects.filter(igsid="old1").exists())
        self.assertTrue(IgClient.objects.filter(igsid="fresh1").exists())


class MemoryNoteInjectionTests(TestCase):
    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_memory_note_injected_into_system(self, mock_gen):
        from management.models import InstagramBotSettings
        from management.services import instagram_bot as bot

        captured = {}

        def _fake(payload, role="chat", manual_key=None):
            captured["payload"] = payload
            return {"parsed": "ок", "model": "x", "meta": {}}

        mock_gen.side_effect = _fake
        s = InstagramBotSettings.load()
        bot.gemini_generate(
            s, [{"role": "user", "text": "ще раз?"}], memory_note="ПАМ-ЯТЬ-XYZ"
        )
        sysi = captured["payload"].get("system_instruction", {}).get("parts", [{}])[0].get("text", "")
        self.assertIn("ПАМ-ЯТЬ-XYZ", sysi)


class PurgeCommandTests(TestCase):
    def test_command_runs(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("purge_ig_clients", stdout=out)
        self.assertIn("Видалено карток", out.getvalue())


class ClientContextNoteTests(TestCase):
    def test_none_when_nothing(self):
        c = IgClient.get_or_create_for_sender("cc0")
        self.assertIsNone(bot_memory.client_context_note(c))

    def test_ad_attribution_with_mapped_product(self):
        from management.models import BotAdCampaign
        from storefront.models import Category, Product, ProductStatus

        cat = Category.objects.create(name="Худі", slug="h-cc")
        p = Product.objects.create(
            title="Худі Kharkiv", slug="hk-cc", category=cat, price=950, status=ProductStatus.PUBLISHED
        )
        BotAdCampaign.objects.create(ad_id="555", title="Промо худі", theme="hoodie", product=p)
        c = IgClient.get_or_create_for_sender("cc1")
        c.ad_id = "555"
        c.ad_title = "Промо худі"
        c.save()
        note = bot_memory.client_context_note(c)
        self.assertIn("Худі Kharkiv", note)
        self.assertIn("950", note)

    def test_ad_title_only(self):
        c = IgClient.get_or_create_for_sender("cc2")
        c.ad_title = "Розпродаж футболок"
        c.save()
        note = bot_memory.client_context_note(c)
        self.assertIn("реклам", note.lower())
        self.assertIn("Розпродаж футболок", note)

    def test_returning_customer(self):
        c = IgClient.get_or_create_for_sender("cc3")
        c.purchases_count = 2
        c.total_spent = 1900
        c.save()
        note = bot_memory.client_context_note(c)
        self.assertIn("постій", note.lower())


class ContextNoteInjectionTests(TestCase):
    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_context_note_injected(self, mock_gen):
        from management.models import InstagramBotSettings
        from management.services import instagram_bot as bot

        captured = {}

        def _fake(payload, role="chat", manual_key=None):
            captured["p"] = payload
            return {"parsed": "ок", "model": "x", "meta": {}}

        mock_gen.side_effect = _fake
        bot.gemini_generate(
            InstagramBotSettings.load(), [{"role": "user", "text": "привіт"}],
            context_note="КОНТЕКСТ-XYZ",
        )
        sysi = captured["p"].get("system_instruction", {}).get("parts", [{}])[0].get("text", "")
        self.assertIn("КОНТЕКСТ-XYZ", sysi)
