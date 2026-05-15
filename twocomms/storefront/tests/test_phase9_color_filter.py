"""
Phase 9 — colour filter regression tests.

Covers:
  * ``parse_color_filter`` slug parsing from comma-separated and repeated params,
  * ``apply_color_filter`` OR-matching against ``ProductColorVariant.slug``,
  * ``build_available_colors`` chip aggregation (count, label, toggle URL),
  * homepage chip strip (``home_color_chips`` context var),
  * catalog/search views surface filtered products + ``noindex`` robots.
"""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import RequestFactory, TestCase
from django.urls import reverse

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product
from storefront.services.color_filter import (
    apply_color_filter,
    build_available_colors,
    build_home_color_chips,
    build_reset_url,
    parse_color_filter,
)


class _BaseColorFilterTests(TestCase):
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
            name="Category 1", slug="category-1", is_active=True
        )

        self.black_color = Color.objects.create(
            name="black", primary_hex="#000000"
        )
        self.coyote_color = Color.objects.create(
            name="coyote", primary_hex="#7A5A3A"
        )

        self.black_product = Product.objects.create(
            title="Black Tee", slug="black-tee",
            category=self.category, price=500, status="published",
        )
        self.coyote_product = Product.objects.create(
            title="Coyote Hoodie", slug="coyote-hoodie",
            category=self.category, price=900, status="published",
        )
        self.both_product = Product.objects.create(
            title="Multi Tee", slug="multi-tee",
            category=self.category, price=600, status="published",
        )
        self.uncoloured_product = Product.objects.create(
            title="Plain Longsleeve", slug="plain-longsleeve",
            category=self.category, price=700, status="published",
        )

        ProductColorVariant.objects.create(
            product=self.black_product, color=self.black_color, is_default=True
        )
        ProductColorVariant.objects.create(
            product=self.coyote_product, color=self.coyote_color, is_default=True
        )
        ProductColorVariant.objects.create(
            product=self.both_product, color=self.black_color, is_default=True,
        )
        ProductColorVariant.objects.create(
            product=self.both_product, color=self.coyote_color, order=1,
        )

    def _request(self, path, query=""):
        factory = RequestFactory()
        return factory.get(f"{path}{('?' + query) if query else ''}")


class ColorFilterServiceTests(_BaseColorFilterTests):
    def test_parse_color_filter_accepts_comma_separated(self):
        request = self._request("/catalog/", "color=black,coyote")
        self.assertEqual(parse_color_filter(request), ["black", "coyote"])

    def test_parse_color_filter_accepts_repeated_params(self):
        request = self._request("/catalog/", "color=black&color=coyote")
        self.assertEqual(parse_color_filter(request), ["black", "coyote"])

    def test_parse_color_filter_dedupes_and_normalises(self):
        request = self._request("/catalog/", "color=Black,BLACK,,coyote!@#")
        # Note: special chars stripped from "coyote!@#"
        self.assertEqual(parse_color_filter(request), ["black", "coyote"])

    def test_parse_color_filter_empty(self):
        self.assertEqual(parse_color_filter(self._request("/catalog/")), [])

    def test_apply_color_filter_or_matches_variants(self):
        qs = Product.objects.filter(status="published")
        filtered = apply_color_filter(qs, ["black"])
        self.assertCountEqual(
            list(filtered.values_list("slug", flat=True)),
            ["black-tee", "multi-tee"],
        )
        filtered_or = apply_color_filter(qs, ["black", "coyote"])
        self.assertCountEqual(
            list(filtered_or.values_list("slug", flat=True)),
            ["black-tee", "coyote-hoodie", "multi-tee"],
        )

    def test_apply_color_filter_noop_for_empty_slug_list(self):
        qs = Product.objects.filter(status="published")
        self.assertEqual(apply_color_filter(qs, []).count(), qs.count())

    def test_build_available_colors_counts_and_toggle_url(self):
        request = self._request("/catalog/", "color=black")
        chips = build_available_colors(
            Product.objects.filter(status="published"), request, ["black"]
        )
        by_slug = {c["slug"]: c for c in chips}
        self.assertIn("black", by_slug)
        self.assertIn("coyote", by_slug)
        # Black is selected (toggling removes it from URL).
        self.assertTrue(by_slug["black"]["is_selected"])
        self.assertNotIn("color=", by_slug["black"]["url"])
        # Coyote is not selected (toggling adds it).
        self.assertFalse(by_slug["coyote"]["is_selected"])
        self.assertIn("color=black%2Ccoyote", by_slug["coyote"]["url"])
        # Counts: black variants on 2 products, coyote on 2.
        self.assertEqual(by_slug["black"]["count"], 2)
        self.assertEqual(by_slug["coyote"]["count"], 2)

    def test_build_reset_url_drops_color_param(self):
        request = self._request("/catalog/", "color=black,coyote&utm_source=ig")
        url = build_reset_url(request)
        self.assertNotIn("color=", url)
        self.assertIn("utm_source=ig", url)

    def test_build_home_color_chips_links_to_target_path(self):
        chips = build_home_color_chips(
            Product.objects.filter(status="published"), "/catalog/"
        )
        self.assertTrue(chips)
        for chip in chips:
            self.assertTrue(chip["url"].startswith("/catalog/?color="))


class CatalogColorFilterIntegrationTests(_BaseColorFilterTests):
    def test_catalog_filters_by_single_color(self):
        response = self.client.get(reverse("catalog") + "?color=coyote")
        product_slugs = [p.slug for p in response.context["products"]]
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(product_slugs, ["coyote-hoodie", "multi-tee"])
        self.assertTrue(response.context["has_active_color_filter"])
        self.assertEqual(response.context["selected_color_slugs"], ["coyote"])
        # Showcase cards must be hidden when the filter is active so the
        # product grid is visible on the catalog root URL.
        self.assertFalse(response.context["show_category_cards"])
        # Filtered listings should not be indexed.
        self.assertContains(response, "noindex, follow")

    def test_catalog_filters_by_multiple_colors_or_match(self):
        response = self.client.get(reverse("catalog") + "?color=black,coyote")
        product_slugs = [p.slug for p in response.context["products"]]
        self.assertCountEqual(
            product_slugs, ["black-tee", "coyote-hoodie", "multi-tee"]
        )

    def test_catalog_renders_chips_partial(self):
        response = self.client.get(reverse("catalog_by_cat",
                                          kwargs={"cat_slug": self.category.slug}))
        self.assertContains(response, 'class="color-filter-chips"')
        self.assertContains(response, 'data-color-slug="black"')
        self.assertContains(response, 'data-color-slug="coyote"')

    def test_homepage_exposes_color_chips(self):
        response = self.client.get(reverse("home"))
        chips = response.context["home_color_chips"]
        self.assertTrue(chips)
        self.assertContains(response, 'class="home-color-filter')
        self.assertContains(response, "Обери одяг за кольором")

    def test_search_view_applies_color_filter(self):
        response = self.client.get(reverse("search") + "?q=tee&color=coyote")
        product_slugs = [p.slug for p in response.context["products"]]
        # Only "Multi Tee" matches both "tee" query and coyote variant.
        self.assertIn("multi-tee", product_slugs)
        self.assertNotIn("black-tee", product_slugs)
