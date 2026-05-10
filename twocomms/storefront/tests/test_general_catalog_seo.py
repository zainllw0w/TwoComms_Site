"""Tests for ``services.general_catalog_seo`` and bottom SEO block on /catalog/.

Covers:
1. Service builds tab_blocks (top_menu, top_filters, top_queries) with the
   right shape and URLs.
2. Empty inputs gracefully degrade (no menu items / no colours).
3. View wiring: GET /catalog/ produces a context with ``category_seo_layout.has_any``.
4. Template renders bottom SEO section on /catalog/ root (was previously
   gated behind ``{% if category %}``).
"""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase
from django.urls import reverse

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product
from storefront.services.general_catalog_seo import (
    get_general_catalog_seo_layout,
)


class _Base(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            p = patch(target)
            self.addCleanup(p.stop)
            p.start()

        self.cat_hd = Category.objects.create(
            name="Худі", slug="hoodie-gen", is_active=True,
        )
        self.cat_ts = Category.objects.create(
            name="Футболки", slug="tshirts-gen", is_active=True,
        )
        self.color_black = Color.objects.create(name="Чорний", primary_hex="#000000")
        self.color_coyote = Color.objects.create(name="Кайот", primary_hex="#A98463")

        # Two products with colour variants so the available-colours
        # builder produces a non-empty chip list when the view runs.
        self.p1 = Product.objects.create(
            title="HD Test", slug="hd-test-gen",
            category=self.cat_hd, price=1500, status="published",
        )
        ProductColorVariant.objects.create(
            product=self.p1, color=self.color_black,
            order=0, is_default=True,
        )
        self.p2 = Product.objects.create(
            title="TS Test", slug="ts-test-gen",
            category=self.cat_ts, price=900, status="published",
        )
        ProductColorVariant.objects.create(
            product=self.p2, color=self.color_coyote,
            order=0, is_default=True,
        )


class GeneralCatalogSeoServiceTests(_Base):
    def test_layout_has_three_tabs(self):
        layout = get_general_catalog_seo_layout(
            categories=[self.cat_hd, self.cat_ts],
            available_colors=[
                {"slug": "black", "label": "Чорний", "count": 1},
                {"slug": "coyote", "label": "Кайот", "count": 1},
            ],
        )
        self.assertTrue(layout["has_any"])
        types = [entry["block"].block_type for entry in layout["tab_blocks"]]
        self.assertEqual(types, ["top_menu", "top_filters", "top_queries"])
        self.assertIsNone(layout["best_prices"])

    def test_top_menu_links_are_category_urls(self):
        layout = get_general_catalog_seo_layout(
            categories=[self.cat_hd, self.cat_ts],
            available_colors=[],
        )
        menu = next(e for e in layout["tab_blocks"] if e["block"].block_type == "top_menu")
        urls = [item.url for item in menu["items"]]
        self.assertIn("/catalog/hoodie-gen/", urls)
        self.assertIn("/catalog/tshirts-gen/", urls)

    def test_top_filters_links_use_colour_query(self):
        layout = get_general_catalog_seo_layout(
            categories=[],
            available_colors=[
                {"slug": "black", "label": "Чорний", "count": 5},
                {"slug": "coyote", "label": "Кайот", "count": 2},
            ],
        )
        filters = next(e for e in layout["tab_blocks"] if e["block"].block_type == "top_filters")
        urls = {item.url for item in filters["items"]}
        self.assertEqual(urls, {"/catalog/?color=black", "/catalog/?color=coyote"})

    def test_top_queries_always_present(self):
        layout = get_general_catalog_seo_layout(
            categories=[],
            available_colors=[],
        )
        # Even with empty inputs, curated queries keep the section useful
        # for SEO crawlers landing on /catalog/.
        self.assertTrue(layout["has_any"])
        types = [e["block"].block_type for e in layout["tab_blocks"]]
        self.assertEqual(types, ["top_queries"])

    def test_block_get_block_type_display_callable(self):
        # Django templates auto-invoke callable attributes; SimpleNamespace
        # must expose ``get_block_type_display`` as a callable so
        # ``{{ block.title|default:block.get_block_type_display }}`` works.
        layout = get_general_catalog_seo_layout(
            categories=[self.cat_hd], available_colors=[],
        )
        block = layout["tab_blocks"][0]["block"]
        self.assertTrue(callable(block.get_block_type_display))
        self.assertEqual(block.get_block_type_display(), block.title)


class GeneralCatalogViewIntegrationTests(_Base):
    def test_general_catalog_renders_seo_section(self):
        resp = self.client.get(reverse("catalog"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("category_seo_layout", resp.context)
        layout = resp.context["category_seo_layout"]
        self.assertTrue(layout["has_any"])
        # All three synthetic tabs should be present on the general
        # /catalog/ page (top_menu / top_filters / top_queries).
        types = [e["block"].block_type for e in layout["tab_blocks"]]
        self.assertIn("top_menu", types)
        self.assertIn("top_filters", types)
        self.assertIn("top_queries", types)

    def test_general_catalog_html_renders_bottom_seo_block(self):
        resp = self.client.get(reverse("catalog"))
        body = resp.content.decode()
        # Aria-label confirms the bottom SEO section was emitted.
        self.assertIn("Додаткові розділи каталогу", body)
        # Curated query label should appear inside the rendered tabs.
        self.assertIn("Купити худі ЗСУ", body)

    def test_general_catalog_html_renders_color_chips(self):
        resp = self.client.get(reverse("catalog"))
        body = resp.content.decode()
        # color_filter_chips partial uses this aria-label.
        self.assertIn("Фільтр за кольором", body)
        # Both seeded colours should appear as chip URLs.
        self.assertIn("color=black", body)
        self.assertIn("color=coyote", body)
