"""Route-contract tests for indexable thematic catalog landings."""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product
from storefront.views.catalog import (
    _catalog_cache_prefix,
    thematic_landing,
)
from storefront.views.utils import (
    _build_anon_cache_key,
    public_product_listing_cache_prefix,
)


class ThematicLandingViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Футболки", slug="tshirts", order=10, is_active=True,
        )
        cls.black = Color.objects.create(name="Чорний", primary_hex="#000000")
        cls.white = Color.objects.create(name="Білий", primary_hex="#FFFFFF")
        for index, color in enumerate((cls.black, cls.black, cls.white)):
            product = Product.objects.create(
                title=f"Streetwear theme tee {index}",
                slug=f"streetwear-theme-tee-{index}",
                category=cls.category,
                price=600,
                status="published",
            )
            ProductColorVariant.objects.create(
                product=product, color=color, is_default=True, order=0
            )

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

    def test_clean_and_page_two_remain_indexable_and_self_canonical(self):
        clean = self.client.get("/catalog/theme/streetwear/")
        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            page_two = self.client.get("/catalog/theme/streetwear/?page=2")

        self.assertEqual(clean.status_code, 200)
        self.assertContains(clean, 'content="index, follow')
        self.assertContains(
            clean,
            'href="https://twocomms.shop/catalog/theme/streetwear/"',
        )
        self.assertEqual(page_two.status_code, 200)
        self.assertContains(page_two, 'content="index, follow')
        self.assertContains(
            page_two,
            'href="https://twocomms.shop/catalog/theme/streetwear/?page=2"',
        )

    def test_page_aliases_redirect_once_without_losing_locale_or_color(self):
        clean_alias = self.client.get(
            "/ru/catalog/theme/streetwear/?page=01&utm_source=audit",
            follow=True,
        )
        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            page_two_alias = self.client.get(
                "/ru/catalog/theme/streetwear/?color=black&page=02",
                follow=True,
            )

        self.assertEqual(clean_alias.status_code, 200)
        self.assertEqual(
            clean_alias.redirect_chain,
            [("/ru/catalog/theme/streetwear/?utm_source=audit", 301)],
        )
        self.assertEqual(page_two_alias.status_code, 200)
        self.assertEqual(
            page_two_alias.redirect_chain,
            [("/ru/catalog/theme/streetwear/?page=2&color=black", 301)],
        )

    def test_color_and_page_aliases_preserve_page_when_both_are_noncanonical(self):
        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            response = self.client.get(
                "/ru/catalog/theme/streetwear/?color=BLACK&page=02&utm_source=audit",
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [(
                "/ru/catalog/theme/streetwear/?page=2&utm_source=audit&color=black",
                301,
            )],
        )

    def test_rejects_unsupported_catalog_and_invalid_page_queries(self):
        invalid_queries = (
            "sort=price-asc",
            "theme=streetwear",
            "collection=225",
            "fit=classic",
            "page=",
            "page=abc",
            "page=0",
            "page=١",
            "page=%202%20",
            "page=+2",
            "page=12345678901",
            "page=999",
            "page=1&page=2",
        )

        for query in invalid_queries:
            with self.subTest(query=query):
                response = self.client.get(
                    f"/catalog/theme/streetwear/?{query}"
                )
                self.assertEqual(response.status_code, 404)

    def test_accepts_arbitrary_external_query_without_indexing_it(self):
        response = self.client.get(
            "/catalog/theme/streetwear/?merchant_future_token=value"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex, follow')
        self.assertContains(
            response,
            'href="https://twocomms.shop/catalog/theme/streetwear/"',
        )
        self.assertTrue(response.context["suppress_hreflang"])

    def test_rejects_empty_unknown_malformed_and_duplicate_colors(self):
        invalid_queries = (
            "color=",
            "color=unknown",
            "color=black!",
            "color=%20black%20",
            "color=black,black",
            "color=black&color=BLACK",
        )

        for query in invalid_queries:
            with self.subTest(query=query):
                response = self.client.get(
                    f"/catalog/theme/streetwear/?{query}"
                )
                self.assertEqual(response.status_code, 404)

    def test_color_alias_normalizes_once(self):
        response = self.client.get(
            "/catalog/theme/streetwear/?color=BLACK",
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [("/catalog/theme/streetwear/?color=black", 301)],
        )

    @patch("storefront.views.catalog.get_allowed_color_slugs", return_value=None)
    def test_color_query_fails_closed_when_allowed_colors_cannot_load(self, _colors):
        response = self.client.get("/catalog/theme/streetwear/?color=black")

        self.assertEqual(response.status_code, 404)

    def test_valid_color_state_is_noindex_clean_canonical_without_hreflang(self):
        response = self.client.get(
            "/catalog/theme/streetwear/?color=black"
        )
        body = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex, follow')
        self.assertContains(
            response,
            'href="https://twocomms.shop/catalog/theme/streetwear/"',
        )
        self.assertTrue(response.context["suppress_hreflang"])
        self.assertNotIn('rel="alternate" hreflang=', body)

    def test_tracking_state_bypasses_page_cache_and_suppresses_hreflang(self):
        with (
            patch("storefront.views.utils.cache.get", wraps=cache.get) as cache_get,
            patch("storefront.views.utils.cache.set", wraps=cache.set) as cache_set,
        ):
            response = self.client.get(
                "/catalog/theme/streetwear/?utm_source=audit"
            )

        page_reads = [
            call.args[0]
            for call in cache_get.call_args_list
            if call.args and str(call.args[0]).startswith("anon-page:")
        ]
        page_writes = [
            call.args[0]
            for call in cache_set.call_args_list
            if call.args and str(call.args[0]).startswith("anon-page:")
        ]
        body = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["suppress_hreflang"])
        self.assertTrue(response.context["catalog_landing_has_tracking"])
        self.assertContains(response, 'content="noindex, follow')
        self.assertNotIn('rel="alternate" hreflang=', body)
        self.assertEqual(page_reads, [])
        self.assertEqual(page_writes, [])

    def test_paginated_page_cannot_use_current_or_legacy_cache_namespace(self):
        request = RequestFactory().get("/catalog/theme/streetwear/?page=999")
        legacy_prefix = public_product_listing_cache_prefix(request, thematic_landing)
        current_prefix = _catalog_cache_prefix(request, thematic_landing)
        self.assertNotEqual(legacy_prefix, current_prefix)

        # Even a stale current-namespace body must not be read for a paginated
        # request; strict paginator validation must own the final 404.
        current_key = _build_anon_cache_key(
            request,
            thematic_landing,
            current_prefix,
            query_string="page=999",
        )
        cache.set(current_key, HttpResponse("stale current body"), 600)

        with patch("storefront.views.utils.cache.get", wraps=cache.get) as cache_get:
            response = self.client.get("/catalog/theme/streetwear/?page=999")

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "stale current body", status_code=404)
        page_reads = [
            call.args[0]
            for call in cache_get.call_args_list
            if call.args and str(call.args[0]).startswith("anon-page:")
        ]
        self.assertEqual(page_reads, [])
