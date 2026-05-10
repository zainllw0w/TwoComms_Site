"""
Phase 10 — category SEO blocks regression tests.

Covers:
  * `get_category_seo_blocks` — ordering, item hydration with Product,
    skip empty non-best-prices blocks, isolation per category.
  * Catalog view exposes ``category_seo_blocks`` only on category pages.
  * `pages/catalog.html` renders the partial when blocks exist.
  * ``Category.seo_text_title`` overrides the H2 of the long SEO text.
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
from storefront.services.category_seo_blocks import get_category_seo_blocks


class _BasePhase10Tests(TestCase):
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
            name="Hoodies", slug="hoodies", is_active=True,
            seo_text_title="Худі для стрітвір-ентузіастів",
            description="<p>Кращі худі TwoComms.</p>",
        )
        self.other_category = Category.objects.create(
            name="Tees", slug="tees", is_active=True,
        )

        self.product = Product.objects.create(
            title="Promo Hoodie", slug="promo-hoodie",
            category=self.category, price=999, status="published",
        )
        self.draft_product = Product.objects.create(
            title="Draft Hoodie", slug="draft-hoodie",
            category=self.category, price=999, status="draft",
        )


class GetCategorySeoBlocksTests(_BasePhase10Tests):
    def test_returns_empty_for_none(self):
        self.assertEqual(get_category_seo_blocks(None), [])

    def test_returns_empty_when_no_blocks(self):
        self.assertEqual(get_category_seo_blocks(self.category), [])

    def test_orders_active_blocks_and_drops_inactive(self):
        active_b = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_filters",
            title="Topics", order=2,
        )
        CategorySeoBlockItem.objects.create(
            block=active_b, label="Black", url="/catalog/hoodies/?color=black", order=0,
        )
        active_a = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_queries",
            title="Queries", order=1,
        )
        CategorySeoBlockItem.objects.create(
            block=active_a, label="купити худі", url="/search/?q=hoodie",
        )
        CategorySeoBlock.objects.create(
            category=self.category, block_type="top_menu",
            title="Hidden", order=3, is_active=False,
        )

        result = get_category_seo_blocks(self.category)
        self.assertEqual(
            [entry["block"].id for entry in result],
            [active_a.id, active_b.id],
        )
        self.assertEqual(len(result[0]["items"]), 1)
        self.assertEqual(len(result[1]["items"]), 1)

    def test_drops_blocks_without_items_except_best_prices(self):
        empty_filters = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_filters",
            title="Empty Filters", order=1,
        )
        empty_prices = CategorySeoBlock.objects.create(
            category=self.category, block_type="best_prices",
            title="Empty Prices", order=2,
        )
        result = get_category_seo_blocks(self.category)
        block_ids = [entry["block"].id for entry in result]
        self.assertNotIn(empty_filters.id, block_ids)
        self.assertIn(empty_prices.id, block_ids)

    def test_top_cards_hydrates_published_product(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_cards", title="Топ",
        )
        live = CategorySeoBlockItem.objects.create(
            block=block, label="Promo", extra={"product_id": self.product.id},
        )
        draft_ref = CategorySeoBlockItem.objects.create(
            block=block, label="Draft", extra={"product_id": self.draft_product.id},
        )
        missing = CategorySeoBlockItem.objects.create(
            block=block, label="Missing", extra={"product_id": 999_999},
        )
        result = get_category_seo_blocks(self.category)
        items = result[0]["items"]
        items_by_id = {item.id: item for item in items}
        self.assertEqual(items_by_id[live.id].product, self.product)
        # Draft products are filtered out — item.product stays None.
        self.assertIsNone(items_by_id[draft_ref.id].product)
        self.assertIsNone(items_by_id[missing.id].product)

    def test_isolated_per_category(self):
        block_self = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_filters", title="Self",
        )
        CategorySeoBlockItem.objects.create(block=block_self, label="A", url="/a/")
        block_other = CategorySeoBlock.objects.create(
            category=self.other_category, block_type="top_filters", title="Other",
        )
        CategorySeoBlockItem.objects.create(block=block_other, label="B", url="/b/")

        own = get_category_seo_blocks(self.category)
        self.assertEqual([e["block"].title for e in own], ["Self"])


class CatalogIntegrationTests(_BasePhase10Tests):
    def test_context_exposes_seo_blocks_on_category_page(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_filters", title="Топ фільтри",
        )
        CategorySeoBlockItem.objects.create(
            block=block, label="Чорні", url="/catalog/hoodies/?color=black",
        )
        response = self.client.get(reverse("catalog_by_cat",
                                          kwargs={"cat_slug": self.category.slug}))
        self.assertEqual(response.status_code, 200)
        seo_blocks = response.context["category_seo_blocks"]
        self.assertEqual(len(seo_blocks), 1)
        self.assertEqual(seo_blocks[0]["block"].block_type, "top_filters")
        # Phase 10b — partial renders a tabs component, not legacy
        # ``seo-block--<type>`` classes. Check the tab trigger + label.
        self.assertContains(response, 'data-seo-tab-trigger="top_filters"')
        self.assertContains(response, "Чорні")

    def test_root_catalog_has_no_db_seo_blocks_but_renders_synthetic_layout(self):
        # Phase 19f (2026-05-10): /catalog/ root no longer relies on
        # CategorySeoBlock rows (still empty here) but now receives a
        # synthesised layout via ``services.general_catalog_seo`` so
        # the bottom SEO section IS rendered. The Phase 10 flat list
        # (``category_seo_blocks``) remains empty for the root.
        response = self.client.get(reverse("catalog"))
        self.assertEqual(response.context["category_seo_blocks"], [])
        self.assertTrue(response.context["category_seo_layout"]["has_any"])
        self.assertContains(response, 'class="category-seo-blocks"')

    def test_category_h2_uses_seo_text_title_when_set(self):
        response = self.client.get(reverse("catalog_by_cat",
                                          kwargs={"cat_slug": self.category.slug}))
        self.assertContains(response, "Худі для стрітвір-ентузіастів — TwoComms")

    def test_category_h2_falls_back_to_name(self):
        response = self.client.get(reverse("catalog_by_cat",
                                          kwargs={"cat_slug": self.other_category.slug}))
        # Other category has no description either, so the panel is hidden.
        # Add a description and re-check.
        self.other_category.description = "<p>Tees rule.</p>"
        self.other_category.save(update_fields=["description"])
        cache.clear()
        caches["fragments"].clear()
        response = self.client.get(reverse("catalog_by_cat",
                                          kwargs={"cat_slug": self.other_category.slug}))
        self.assertContains(response, "Tees — TwoComms")
