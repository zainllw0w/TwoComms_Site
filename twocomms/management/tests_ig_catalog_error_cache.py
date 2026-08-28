"""Э3.8 — технический сбой каталога не кэшируется как валидный пустой каталог."""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from management.services import bot_catalog


class CatalogErrorIsNotCachedAsEmptyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_build_failure_is_not_cached_as_a_valid_empty_catalog(self):
        with patch.object(
            bot_catalog, "_build", side_effect=RuntimeError("catalog exploded")
        ), patch.object(bot_catalog, "_alert_catalog_build_failure") as alert:
            first = bot_catalog.get_catalog_context()

        self.assertEqual(first, "")
        alert.assert_called_once()
        self.assertIsNone(
            cache.get(bot_catalog.CACHE_KEY),
            "ошибка не должна занимать кэш на 600 секунд",
        )

    def test_last_known_good_snapshot_is_served_with_a_stale_marker(self):
        with patch.object(bot_catalog, "_build", return_value="КАТАЛОГ: худі, лонгслів"):
            good = bot_catalog.get_catalog_context(force=True)
        self.assertIn("худі", good)

        with patch.object(
            bot_catalog, "_build", side_effect=RuntimeError("catalog exploded")
        ), patch.object(bot_catalog, "_alert_catalog_build_failure") as alert:
            degraded = bot_catalog.get_catalog_context(force=True)

        self.assertIn("ОСТАННІЙ ВІДОМИЙ ЗНІМОК", degraded)
        self.assertIn("худі", degraded)
        self.assertIn("уточни в менеджера", degraded)
        alert.assert_called_once()
        self.assertTrue(alert.call_args.kwargs["has_fallback"])

    def test_stale_snapshot_ttl_is_much_shorter_than_the_valid_one(self):
        self.assertLess(bot_catalog.CATALOG_ERROR_TTL, bot_catalog.CACHE_TTL)

    def test_a_genuinely_empty_build_is_still_cached_normally(self):
        with patch.object(bot_catalog, "_build", return_value=""):
            result = bot_catalog.get_catalog_context(force=True)
        self.assertEqual(result, "")
        self.assertEqual(cache.get(bot_catalog.CACHE_KEY), "")
        self.assertIsNone(
            cache.get(f"{bot_catalog.CACHE_KEY}:last_known_good"),
            "пустой результат не становится last-known-good",
        )

    def test_compact_and_full_contexts_keep_separate_snapshots(self):
        with patch.object(bot_catalog, "_build", side_effect=["ПОВНИЙ", "КОМПАКТ"]):
            full = bot_catalog.get_catalog_context(force=True)
            compact = bot_catalog.get_catalog_context(force=True, compact=True)
        self.assertEqual(full, "ПОВНИЙ")
        self.assertEqual(compact, "КОМПАКТ")
        self.assertEqual(
            cache.get(f"{bot_catalog.CACHE_COMPACT_KEY}:last_known_good"), "КОМПАКТ"
        )
