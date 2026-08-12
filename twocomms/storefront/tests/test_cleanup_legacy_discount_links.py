"""Regression tests for the exact persisted ``sort=discount`` cleanup."""

from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.test import TestCase

from storefront.models import Category, CategorySeoBlock, CategorySeoBlockItem


class LegacyDiscountLinkCleanupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hoodie = Category.objects.create(
            name="Худі", slug="hoodie", description=(
                '<p>Ціни та <a href="/catalog/hoodie/?sort=discount">знижки</a>.</p>'
                '<p><a href="/delivery/">Доставка</a>.</p>'
            ),
        )
        cls.hoodie.description_uk = cls.hoodie.description
        cls.hoodie.save(update_fields=["description", "description_uk"])
        # modeltranslation may expose the default-language fallback through
        # the descriptor; seed both persisted columns explicitly for the
        # migration contract test.
        Category.objects.filter(pk=cls.hoodie.pk).update(
            description=(
                '<p>Ціни та <a href="/catalog/hoodie/?sort=discount">знижки</a>.</p>'
                '<p><a href="/delivery/">Доставка</a>.</p>'
            ),
            description_uk=(
                '<p>Ціни та <a href="/catalog/hoodie/?sort=discount">знижки</a>.</p>'
                '<p><a href="/delivery/">Доставка</a>.</p>'
            ),
        )
        cls.block = CategorySeoBlock.objects.create(
            category=cls.hoodie, block_type="top_filters", is_active=True,
        )
        cls.bad_item = CategorySeoBlockItem.objects.create(
            block=cls.block, label="Знижки", url="/catalog/hoodie/?sort=discount",
        )
        cls.valid_item = CategorySeoBlockItem.objects.create(
            block=cls.block, label="Чорні", url="/catalog/hoodie/black/",
        )

    def setUp(self):
        super().setUp()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _run_cleanup(self):
        migration = import_module(
            "storefront.migrations.0091_cleanup_legacy_discount_links"
        )
        migration.remove_legacy_discount_links(apps, None)

    def test_cleanup_unwraps_exact_description_links_and_deletes_bad_items(self):
        before = Category.objects.get(pk=self.hoodie.pk)
        self.assertIn("sort=discount", before.description_uk)
        self._run_cleanup()

        hoodie = Category.objects.get(pk=self.hoodie.pk)
        raw = Category.objects.values("description", "description_uk").get(pk=self.hoodie.pk)
        self.assertIn("<p>Ціни та знижки.</p>", raw["description"])
        self.assertIn('<a href="/delivery/">Доставка</a>', hoodie.description)
        self.assertNotIn("sort=discount", raw["description"])
        self.assertNotIn("sort=discount", raw["description_uk"])
        self.assertFalse(
            CategorySeoBlockItem.objects.filter(pk=self.bad_item.pk).exists()
        )
        self.assertTrue(
            CategorySeoBlockItem.objects.filter(pk=self.valid_item.pk).exists()
        )

    def test_cleanup_is_idempotent(self):
        self._run_cleanup()
        first = Category.objects.get(pk=self.hoodie.pk)
        first_values = (first.__dict__["description"], first.__dict__["description_uk"])
        self._run_cleanup()
        second = Category.objects.get(pk=self.hoodie.pk)
        self.assertEqual(
            (second.__dict__["description"], second.__dict__["description_uk"]),
            first_values,
        )

    def test_unrelated_query_links_are_not_modified(self):
        hoodie = Category.objects.get(pk=self.hoodie.pk)
        hoodie.description = (
            '<a href="/catalog/hoodie/?color=black">Чорний</a>'
            '<a href="/catalog/hoodie/?sort=price-asc">Дешевші</a>'
            '<a href="https://example.com/catalog/hoodie/?sort=discount">Зовнішня</a>'
        )
        hoodie.save(update_fields=["description"])
        self._run_cleanup()
        hoodie = Category.objects.get(pk=self.hoodie.pk)
        self.assertIn("?color=black", hoodie.__dict__["description"])
        self.assertIn("?sort=price-asc", hoodie.__dict__["description"])
        self.assertIn(
            "https://example.com/catalog/hoodie/?sort=discount",
            hoodie.__dict__["description"],
        )

    def test_cleanup_matches_locale_and_tracking_aliases_but_not_other_sorts(self):
        hoodie = Category.objects.get(pk=self.hoodie.pk)
        hoodie.description = (
            '<a href="/ru/catalog/hoodie/?utm_source=x&sort=discount">RU</a>'
            '<a href="https://twocomms.shop/en/catalog/tshirts/?sort=discount&utm_medium=x">EN</a>'
            '<a href="/catalog/hoodie/?sort=price-asc">Price</a>'
        )
        hoodie.save(update_fields=["description"])
        self._run_cleanup()
        hoodie = Category.objects.get(pk=self.hoodie.pk)
        raw = Category.objects.values("description").get(pk=hoodie.pk)
        self.assertNotIn("sort=discount", raw["description"])
        self.assertIn("?sort=price-asc", raw["description"])

    def test_malformed_href_is_fail_closed_and_preserved(self):
        hoodie = Category.objects.get(pk=self.hoodie.pk)
        malformed = '<a href="http://[broken/catalog/hoodie/?sort=discount">Broken</a>'
        hoodie.description = malformed
        hoodie.save(update_fields=["description"])

        self._run_cleanup()

        hoodie = Category.objects.get(pk=hoodie.pk)
        self.assertEqual(hoodie.__dict__["description"], malformed)

    def test_category_routes_have_no_retired_discount_links_in_any_locale(self):
        self._run_cleanup()
        for prefix in ("", "/ru", "/en"):
            with self.subTest(prefix=prefix):
                response = self.client.get(f"{prefix}/catalog/hoodie/")
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "sort=discount")
