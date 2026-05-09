"""
Phase 10b — tabs layout, pricing table, intro section, seed migration.

Covers:
  * ``get_category_seo_layout`` — splits blocks into ``tab_blocks`` (in
    canonical order) and ``best_prices``, drops empty entries, exposes
    ``has_any``.
  * Catalog template — renders intro section above grid, tabs component
    below grid, pricing table when ``best_prices`` has items.
  * Seed migration — populated SEO copy + structured blocks for
    ``hoodie``/``tshirts``/``long-sleeve`` if categories exist (smoke
    test using fixtures created in setUp).
"""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase
from django.urls import reverse

from storefront.models import (
    Category,
    CategorySeoBlock,
    CategorySeoBlockItem,
    Product,
)
from storefront.services.category_seo_blocks import (
    TAB_BLOCK_TYPES,
    get_category_seo_layout,
)


class _BasePhase10bTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        merchant_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()

        self.category = Category.objects.create(
            name="Худі", slug="hoodie", is_active=True,
        )
        self.product = Product.objects.create(
            title="Худі ZSU", slug="hoodi-zsu",
            category=self.category, price=1490, status="published",
            priority=10,
        )


class CategorySeoLayoutServiceTests(_BasePhase10bTests):
    def _block(self, btype, items, **kwargs):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type=btype,
            title=kwargs.get("title", btype),
            is_active=kwargs.get("is_active", True),
            order=kwargs.get("order", 0),
        )
        for idx, payload in enumerate(items):
            CategorySeoBlockItem.objects.create(
                block=block,
                label=payload["label"],
                url=payload.get("url", ""),
                extra=payload.get("extra") or {},
                order=idx,
            )
        return block

    def test_layout_returns_canonical_tab_order_regardless_of_block_order(self):
        # Insert blocks in REVERSE canonical order with random ``order`` values.
        self._block("top_cards",
                    [{"label": "card", "extra": {"product_id": self.product.id}}],
                    order=5)
        self._block("top_queries", [{"label": "q", "url": "/catalog/hoodie/"}],
                    order=1)
        self._block("top_filters", [{"label": "f", "url": "/catalog/hoodie/?color=black"}],
                    order=99)
        self._block("top_menu", [{"label": "m", "url": "/catalog/hoodie/"}],
                    order=10)

        layout = get_category_seo_layout(self.category)
        types = [e["block"].block_type for e in layout["tab_blocks"]]
        self.assertEqual(types, list(TAB_BLOCK_TYPES))
        self.assertTrue(layout["has_any"])

    def test_best_prices_returned_separately_from_tabs(self):
        self._block("best_prices",
                    [{"label": "Худі", "extra": {"product_id": self.product.id, "price": 1490}}])
        self._block("top_filters",
                    [{"label": "Чорний", "url": "/catalog/hoodie/?color=black"}])
        layout = get_category_seo_layout(self.category)
        # ``best_prices`` is NEVER in tab_blocks.
        self.assertNotIn(
            "best_prices",
            [e["block"].block_type for e in layout["tab_blocks"]],
        )
        self.assertIsNotNone(layout["best_prices"])
        self.assertEqual(layout["best_prices"]["block"].block_type, "best_prices")

    def test_empty_blocks_and_pricing_with_no_items_dropped(self):
        # top_filters with NO items at all → service drops the block.
        CategorySeoBlock.objects.create(
            category=self.category, block_type="top_filters",
            title="filters", is_active=True,
        )
        # best_prices with NO items at all → layout returns None.
        CategorySeoBlock.objects.create(
            category=self.category, block_type="best_prices",
            title="prices", is_active=True,
        )
        layout = get_category_seo_layout(self.category)
        self.assertEqual(layout["tab_blocks"], [])
        self.assertIsNone(layout["best_prices"])
        self.assertFalse(layout["has_any"])

    def test_layout_for_none_category(self):
        layout = get_category_seo_layout(None)
        self.assertEqual(layout, {"tab_blocks": [], "best_prices": None, "has_any": False})


class CatalogIntegrationLayoutTests(_BasePhase10bTests):
    def test_intro_section_rendered_above_products_when_set(self):
        self.category.seo_intro_html = (
            '<p>Patriotic <strong>hoodie</strong> intro</p>'
            '<details><summary>Що таке худі?</summary><p>Hoodies info.</p></details>'
        )
        self.category.save(update_fields=["seo_intro_html"])
        response = self.client.get(reverse("catalog_by_cat",
                                           kwargs={"cat_slug": self.category.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "catalog-category-intro")
        self.assertContains(response, "Patriotic")
        self.assertContains(response, "Що таке худі?")

    def test_intro_section_skipped_when_empty(self):
        self.assertEqual(self.category.seo_intro_html, "")
        response = self.client.get(reverse("catalog_by_cat",
                                           kwargs={"cat_slug": self.category.slug}))
        self.assertNotContains(response, "catalog-category-intro")

    def test_tabs_component_renders_with_canonical_buttons(self):
        for btype, label in (
            ("top_filters", "Чорний худі"),
            ("top_menu", "Усі худі"),
            ("top_queries", "Купити ЗСУ худі"),
        ):
            block = CategorySeoBlock.objects.create(
                category=self.category, block_type=btype,
                title=btype, is_active=True,
            )
            CategorySeoBlockItem.objects.create(
                block=block, label=label, url="/catalog/hoodie/",
            )
        response = self.client.get(reverse("catalog_by_cat",
                                           kwargs={"cat_slug": self.category.slug}))
        self.assertContains(response, 'data-seo-tab-trigger="top_menu"')
        self.assertContains(response, 'data-seo-tab-trigger="top_filters"')
        self.assertContains(response, 'data-seo-tab-trigger="top_queries"')
        # First tab in canonical order (``top_menu``) should be the active one.
        self.assertContains(response, 'data-seo-tab-panel="top_menu"')

    def test_pricing_table_renders_with_price_label(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="best_prices",
            title="Найкращі ціни", is_active=True,
        )
        CategorySeoBlockItem.objects.create(
            block=block, label="Худі ZSU patriot", url="/product/x/",
            extra={"product_id": self.product.id, "price": 1490},
        )
        response = self.client.get(reverse("catalog_by_cat",
                                           kwargs={"cat_slug": self.category.slug}))
        self.assertContains(response, "seo-pricing__table")
        self.assertContains(response, "1490")
        self.assertContains(response, "грн")

    def test_layout_context_present_on_category_root_with_no_blocks(self):
        response = self.client.get(reverse("catalog_by_cat",
                                           kwargs={"cat_slug": self.category.slug}))
        layout = response.context["category_seo_layout"]
        self.assertEqual(layout["tab_blocks"], [])
        self.assertIsNone(layout["best_prices"])
        self.assertFalse(layout["has_any"])


class SeedMigrationSmokeTests(TestCase):
    """Phase 10b — re-run the seed function in a fresh transaction and
    assert it populated copy + blocks for the live category slugs."""

    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        merchant_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()

        # Build empty-stub categories matching the production slugs so
        # the seed function has something to write to.
        self.cats = {}
        for slug, name in (
            ("hoodie", "Худі"),
            ("tshirts", "Футболки"),
            ("long-sleeve", "Лонгсліви"),
        ):
            self.cats[slug] = Category.objects.create(
                name=name, slug=slug, is_active=True,
            )

    def test_seed_populates_copy_and_blocks(self):
        # Re-import the function — it's not part of public API but stable.
        from importlib import import_module
        seed = import_module(
            "storefront.migrations.0053_phase10b_seed_category_seo"
        )
        from django.apps import apps

        seed.seed_seo_copy(apps, schema_editor=None)

        for slug in ("hoodie", "tshirts", "long-sleeve"):
            cat = Category.objects.get(slug=slug)
            self.assertTrue(cat.seo_intro_html.strip(),
                            msg=f"intro empty for {slug}")
            self.assertTrue(cat.description.strip(),
                            msg=f"description empty for {slug}")
            self.assertTrue(cat.seo_text_title.strip(),
                            msg=f"seo_text_title empty for {slug}")
            block_types = set(
                CategorySeoBlock.objects.filter(category=cat, is_active=True)
                .values_list("block_type", flat=True)
            )
            # best_prices is conditional on having Products; the others
            # must always seed.
            self.assertTrue({"top_menu", "top_filters", "top_queries"} <= block_types,
                            msg=f"missing tab blocks for {slug}: {block_types}")

    def test_seed_idempotent_on_second_run(self):
        from importlib import import_module
        seed = import_module(
            "storefront.migrations.0053_phase10b_seed_category_seo"
        )
        from django.apps import apps
        seed.seed_seo_copy(apps, schema_editor=None)
        before_count = CategorySeoBlock.objects.count()
        # Manually edit a description — second run must NOT overwrite.
        cat = Category.objects.get(slug="hoodie")
        cat.description = "<p>Manual edit</p>"
        cat.save(update_fields=["description"])

        seed.seed_seo_copy(apps, schema_editor=None)
        cat.refresh_from_db()
        self.assertIn("Manual edit", cat.description)
        self.assertEqual(CategorySeoBlock.objects.count(), before_count,
                         msg="seed re-run should not duplicate blocks")
