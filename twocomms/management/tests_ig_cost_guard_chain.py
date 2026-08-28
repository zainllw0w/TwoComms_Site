"""Э2.3 — цепочка «сбой кэша → квота → молчание инбокса» разорвана."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, InstagramBotMessage, InstagramBotSettings
from management.services import instagram_bot as bot
from management.services.ig_cost_guard import (
    counted,
    current_count,
    reset_local_counters,
)


class _BrokenCache:
    """Кеш, який падає на будь-якій операції — саме той сценарій из находки."""

    def get(self, *args, **kwargs):
        raise RuntimeError("cache unavailable")

    def set(self, *args, **kwargs):
        raise RuntimeError("cache unavailable")

    def add(self, *args, **kwargs):
        raise RuntimeError("cache unavailable")

    def delete(self, *args, **kwargs):
        raise RuntimeError("cache unavailable")


class CostGuardFailClosedTests(TestCase):
    """Первое звено: сбой кэша больше не выключает cost-гарды."""

    def setUp(self):
        reset_local_counters()
        self.settings = InstagramBotSettings.load()

    def tearDown(self):
        reset_local_counters()

    def test_counter_falls_back_to_the_process_when_cache_is_broken(self):
        with patch("management.services.ig_cost_guard.cache", _BrokenCache()):
            first, shared = counted("k", 60)
            second, _ = counted("k", 60)
            self.assertFalse(shared)
            self.assertEqual((first, second), (1, 2))
            self.assertEqual(current_count("k")[0], 2)

    def test_vision_guard_still_limits_a_photo_burst_without_cache(self):
        with patch("management.services.ig_cost_guard.cache", _BrokenCache()):
            allowed = sum(1 for _ in range(40) if bot._match_allowed("sender-1", limit=15))
        self.assertEqual(
            allowed, 15, "без кешу гард мусить лімітувати, а не відкриватись навстіж"
        )

    def test_reply_rate_guard_still_trips_without_cache(self):
        with patch("management.services.ig_cost_guard.cache", _BrokenCache()):
            results = [
                bot._rate_exceeded(self.settings, "sender-2", limit=5)
                for _ in range(8)
            ]
        self.assertEqual(results.count(False), 5)
        self.assertTrue(results[-1])

    def test_repeated_question_guard_still_counts_without_cache(self):
        with patch("management.services.ig_cost_guard.cache", _BrokenCache()):
            counts = [bot._repeated_question("sender-3", "скільки коштує") for _ in range(4)]
        self.assertEqual(counts, [1, 2, 3, 4])

    def test_in_process_counter_is_bounded(self):
        from management.services.ig_cost_guard import MAX_TRACKED_KEYS, _counter

        with patch("management.services.ig_cost_guard.cache", _BrokenCache()):
            for index in range(MAX_TRACKED_KEYS + 200):
                counted(f"bounded:{index}", 3600)
        self.assertLessEqual(len(_counter._values), MAX_TRACKED_KEYS)


class CooldownDeferralBudgetTests(TestCase):
    """Второе звено: отсрочка ограничена, дальше — детерминированный ответ."""

    def setUp(self):
        # `_defer_for_gemini_cooldown` ставит флаг backoff в кэш с TTL до 10 минут.
        # locmem-кэш живёт весь процесс, поэтому без очистки этот тест заставил бы
        # последующие тесты живого ответа откладывать ход вместо отправки.
        from django.core.cache import cache

        cache.clear()
        self.addCleanup(cache.clear)
        self.settings = InstagramBotSettings.load()
        self.settings.gemini_source = InstagramBotSettings.CredSource.ENV
        self.settings.save(update_fields=["gemini_source"])
        self.ig_client = IgClient.get_or_create_for_sender("cooldown-sender")
        self.row = InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text="Скільки коштує худі?",
            status=InstagramBotMessage.Status.PROCESSING,
        )

    def _defer(self, *, wait_seconds):
        soonest = timezone.now() + timedelta(seconds=wait_seconds)
        with patch(
            "management.services.gemini_keys.has_available_key", return_value=False
        ), patch(
            "management.services.gemini_keys.soonest_cooldown", return_value=soonest
        ):
            return bot._defer_for_gemini_cooldown(self.row, self.settings)

    def test_short_cooldown_is_still_worth_waiting_for(self):
        self.assertTrue(self._defer(wait_seconds=30))
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, InstagramBotMessage.Status.PENDING)

    def test_daily_quota_cooldown_never_buys_silence(self):
        """24 часа тишины в диалоге — потерянный клиент, а не экономия."""
        self.assertFalse(self._defer(wait_seconds=24 * 3600))
        self.row.refresh_from_db()
        self.assertEqual(
            self.row.status,
            InstagramBotMessage.Status.PROCESSING,
            "ход остаётся у воркера и доходит до детерминированного fallback",
        )

    def test_a_turn_that_already_waited_too_long_stops_being_deferred(self):
        InstagramBotMessage.objects.filter(pk=self.row.pk).update(
            created_at=timezone.now() - timedelta(seconds=bot.MAX_COOLDOWN_DEFERRAL_SECONDS + 60)
        )
        self.row.refresh_from_db()
        self.assertFalse(self._defer(wait_seconds=30))

    def test_custom_key_is_never_deferred(self):
        self.settings.gemini_source = InstagramBotSettings.CredSource.CUSTOM
        with patch.object(
            InstagramBotSettings, "custom_gemini_key", "custom-key", create=True
        ):
            self.assertFalse(self._defer(wait_seconds=30))
