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

import re
from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import activate, get_language, override

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
            block=active_b, label="Black", url="/catalog/hoodies/", order=0,
        )
        active_a = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_queries",
            title="Queries", order=1,
        )
        CategorySeoBlockItem.objects.create(
            block=active_a, label="купити худі", url="/delivery/",
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

    def test_product_references_use_live_slug_and_drop_unavailable_items(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_cards", title="Топ",
        )
        live = CategorySeoBlockItem.objects.create(
            block=block,
            label="Promo",
            url="/product/33/",
            extra={"product_id": self.product.id},
        )
        draft_ref = CategorySeoBlockItem.objects.create(
            block=block,
            label="Draft",
            url="/product/44/",
            extra={"product_id": self.draft_product.id},
        )
        missing = CategorySeoBlockItem.objects.create(
            block=block,
            label="Missing",
            url="/product/55/",
            extra={"product_id": 999_999},
        )
        result = get_category_seo_blocks(self.category)
        items = result[0]["items"]
        self.assertEqual([item.id for item in items], [live.id])
        self.assertEqual(items[0].product, self.product)
        self.assertEqual(items[0].url, "/product/promo-hoodie/")

    def test_product_id_accepts_only_positive_int_or_decimal_string(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_cards", title="Strict ids",
        )
        valid = [
            CategorySeoBlockItem.objects.create(
                block=block,
                label="Integer",
                extra={"product_id": self.product.id},
            ),
            CategorySeoBlockItem.objects.create(
                block=block,
                label="Decimal string",
                extra={"product_id": f"00{self.product.id}"},
            ),
        ]
        invalid_values = (
            True,
            float(self.product.id),
            f" {self.product.id}",
            f"+{self.product.id}",
            f"{self.product.id}.0",
            0,
            -1,
            2**63,
            "9" * 5000,
            "",
            None,
        )
        for index, raw_id in enumerate(invalid_values):
            CategorySeoBlockItem.objects.create(
                block=block,
                label=f"Invalid {index}",
                url=f"/product/legacy-invalid-{index}/",
                extra={"product_id": raw_id},
            )

        result = get_category_seo_blocks(self.category)

        self.assertEqual(
            [item.id for item in result[0]["items"]],
            [item.id for item in valid],
        )

    def test_stale_custom_print_url_is_localized_but_valid_links_are_unchanged(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_filters", title="Links",
        )
        stale = CategorySeoBlockItem.objects.create(
            block=block, label="Custom", url="/catalog/custom-print/",
        )
        valid = CategorySeoBlockItem.objects.create(
            block=block, label="Delivery", url="/delivery/?from=seo#faq",
        )

        with override("ru"):
            result = get_category_seo_blocks(self.category)

        items_by_id = {item.id: item for item in result[0]["items"]}
        self.assertEqual(items_by_id[stale.id].url, "/ru/custom-print/")
        self.assertEqual(items_by_id[valid.id].url, "/delivery/?from=seo#faq")

    def test_absolute_custom_print_owner_is_normalized_but_external_links_are_not(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_filters", title="Links",
        )
        internal = CategorySeoBlockItem.objects.create(
            block=block,
            label="Internal custom",
            url=(
                "https://TWOCOMMS.SHOP:443/catalog/custom-print/"
                "?source=seo#form"
            ),
        )
        external = CategorySeoBlockItem.objects.create(
            block=block,
            label="External",
            url="https://example.com/catalog/custom-print/",
        )

        result = get_category_seo_blocks(self.category)
        items_by_id = {item.id: item for item in result[0]["items"]}

        self.assertEqual(
            items_by_id[internal.id].url,
            "https://twocomms.shop/custom-print/?source=seo#form",
        )
        self.assertEqual(items_by_id[external.id].url, external.url)

    def test_malformed_custom_print_candidates_remain_unchanged(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_filters", title="Links",
        )
        malformed_urls = (
            "https://[twocomms.shop/catalog/custom-print/",
            "https://twocomms.shop:not-a-port/catalog/custom-print/",
        )
        items = [
            CategorySeoBlockItem.objects.create(
                block=block,
                label=f"Malformed {index}",
                url=url,
            )
            for index, url in enumerate(malformed_urls)
        ]

        result = get_category_seo_blocks(self.category)

        items_by_id = {item.id: item for item in result[0]["items"]}
        self.assertEqual(
            [items_by_id[item.id].url for item in items],
            list(malformed_urls),
        )

    def test_best_price_uses_current_final_price_and_slug_url(self):
        self.product.discount_percent = 10
        self.product.save(update_fields=["discount_percent"])
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="best_prices", title="Prices",
        )
        CategorySeoBlockItem.objects.create(
            block=block,
            label="Stale label",
            url="/product/33/",
            extra={"product_id": self.product.id, "price": 1},
        )

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/product/promo-hoodie/"')
        self.assertContains(response, "899 грн")
        rendered_item = response.context["category_seo_layout"]["best_prices"]["items"][0]
        self.assertEqual(rendered_item.url, "/product/promo-hoodie/")
        self.assertEqual(rendered_item.product.final_price, 899)

    def test_malformed_product_reference_has_no_rendered_item(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_cards", title="Топ",
        )
        CategorySeoBlockItem.objects.create(
            block=block,
            label="Malformed",
            url="/product/legacy-id/",
            extra={"product_id": "not-a-number"},
        )

        result = get_category_seo_blocks(self.category)

        self.assertEqual(result, [])

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
    def test_category_seo_blocks_obey_locale_ownership_boundary(self):
        self.product.discount_percent = 10
        self.product.save(update_fields=["discount_percent"])
        pricing = CategorySeoBlock.objects.create(
            category=self.category, block_type="best_prices", title="Matrix prices",
        )
        CategorySeoBlockItem.objects.create(
            block=pricing,
            label="Matrix live price",
            url="/product/legacy-live/",
            extra={"product_id": self.product.id, "price": 1},
        )
        links = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_menu", title="Matrix links",
        )
        CategorySeoBlockItem.objects.create(
            block=links,
            label="Matrix custom",
            url="/catalog/custom-print/",
        )
        unavailable = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_cards", title="Unavailable",
        )
        stale_urls = (
            "/product/legacy-draft/",
            "/product/legacy-missing/",
            "/product/legacy-malformed/",
        )
        CategorySeoBlockItem.objects.create(
            block=unavailable,
            label="Draft reference",
            url=stale_urls[0],
            extra={"product_id": self.draft_product.id},
        )
        CategorySeoBlockItem.objects.create(
            block=unavailable,
            label="Missing reference",
            url=stale_urls[1],
            extra={"product_id": 999_999},
        )
        CategorySeoBlockItem.objects.create(
            block=unavailable,
            label="Malformed reference",
            url=stale_urls[2],
            extra={"product_id": "not-a-number"},
        )

        locale_matrix = {
            "uk": "",
            "ru": "/ru",
            "en": "/en",
        }
        for language, prefix in locale_matrix.items():
            with self.subTest(language=language):
                with override(language):
                    response = self.client.get(
                        f"{prefix}/catalog/{self.category.slug}/"
                    )
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                pricing_html = re.search(
                    r'<section class="seo-pricing".*?</section>',
                    html,
                    flags=re.DOTALL,
                )
                if language == "uk":
                    self.assertIsNotNone(pricing_html)
                    self.assertIn(
                        'href="/product/promo-hoodie/"', pricing_html.group()
                    )
                    self.assertIn("899", pricing_html.group())
                    self.assertNotRegex(
                        pricing_html.group(),
                        r'class="seo-pricing__td-price">\s*1(?:\s|<)',
                    )
                    self.assertIn(
                        'href="/custom-print/">Matrix custom</a>', html,
                    )
                else:
                    self.assertIsNone(pricing_html)
                    self.assertNotIn("Matrix prices", html)
                    self.assertNotIn("Matrix custom", html)
                    self.assertEqual(response.context["category_seo_blocks"], [])
                for stale_url in stale_urls:
                    self.assertNotIn(stale_url, html)

    def test_public_context_hides_legacy_query_rails_without_deleting_rows(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="top_filters", title="Топ фільтри",
        )
        CategorySeoBlockItem.objects.create(
            block=block, label="Чорні", url="/catalog/hoodies/",
        )
        response = self.client.get(reverse("catalog_by_cat",
                                          kwargs={"cat_slug": self.category.slug}))
        self.assertEqual(response.status_code, 200)
        seo_blocks = response.context["category_seo_blocks"]
        self.assertEqual(seo_blocks, [])
        self.assertNotContains(response, 'data-seo-tab-trigger="top_filters"')
        self.assertNotContains(response, "Чорні")
        self.assertTrue(CategorySeoBlock.objects.filter(pk=block.pk).exists())

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


class CatalogLocaleSeoIntegrationTests(TestCase):
    """Locale-prefixed category pages must not publish UK-only SEO rails."""

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Футболки",
            name_ru="Футболки",
            name_en="T-shirts",
            slug="tshirts",
            is_active=True,
        )
        cls.sibling = Category.objects.create(
            name="Худі",
            name_ru="Худи",
            name_en="Hoodies",
            slug="hoodie",
            is_active=True,
        )
        cls.product = Product.objects.create(
            title="Українська SEO-картка",
            title_ru="Русская SEO-карточка",
            title_en="English SEO card",
            slug="locale-category-card",
            category=cls.category,
            price=900,
            status="published",
        )
        block = CategorySeoBlock.objects.create(
            category=cls.category,
            block_type="top_menu",
            title="Legacy Ukrainian database block",
            is_active=True,
        )
        CategorySeoBlockItem.objects.create(
            block=block,
            label="Legacy Ukrainian database item",
            url="/catalog/theme/military/",
        )
        cards = CategorySeoBlock.objects.create(
            category=cls.category,
            block_type="top_cards",
            title="Legacy Ukrainian cards",
            is_active=True,
        )
        CategorySeoBlockItem.objects.create(
            block=cards,
            label="Legacy Ukrainian published card",
            url="/product/legacy-card/",
            extra={"product_id": cls.product.id},
        )

    def setUp(self):
        super().setUp()
        previous_language = get_language()
        self.addCleanup(activate, previous_language)
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_ru_and_en_category_rails_are_same_locale_and_ignore_legacy_rows(self):
        for language, prefix, sibling_label in (
            ("ru", "/ru", "Худи"),
            ("en", "/en", "Hoodies"),
        ):
            with self.subTest(language=language):
                response = self.client.get(
                    f"{prefix}/catalog/{self.category.slug}/"
                )

                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn('data-smart-selector="true"', html)
                layout = response.context["category_seo_layout"]
                self.assertEqual(len(layout["tab_blocks"]), 1)
                menu = layout["tab_blocks"][0]
                self.assertEqual(menu["block"].block_type, "top_menu")
                self.assertEqual(menu["block"].title, {
                    "ru": "Разделы каталога",
                    "en": "Catalog sections",
                }[language])

                labels = [item.label for item in menu["items"]]
                urls = [item.url for item in menu["items"]]
                self.assertIn(sibling_label, labels)
                self.assertNotIn("Legacy Ukrainian database item", labels)
                self.assertNotIn("Legacy Ukrainian published card", html)
                self.assertNotIn("Legacy Ukrainian cards", html)
                self.assertNotIn("/catalog/theme/military/", urls)
                self.assertTrue(all(url.startswith(f"{prefix}/") for url in urls))
                self.assertIn(menu["block"].title, html)
                self.assertIn(f'href="{prefix}/catalog/{self.sibling.slug}/"', html)
                self.assertNotIn(
                    f"{prefix}/catalog/{self.category.slug}/", urls,
                )
