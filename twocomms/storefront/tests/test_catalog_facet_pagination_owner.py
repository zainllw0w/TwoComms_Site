"""Canonical owner regressions for non-indexable catalog facet pagination."""

from __future__ import annotations

from html.parser import HTMLParser
import json
from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase, override_settings
from django.utils import translation
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption


class _CatalogOwnerSignalParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = ""
        self.meta_description = ""
        self.social_urls = {}
        self.json_ld = []
        self._json_ld_parts = []
        self._in_json_ld = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "canonical" in (attrs.get("rel") or "").split():
            self.canonical = attrs.get("href", "")
        elif tag == "meta":
            key = attrs.get("property") or attrs.get("name")
            if key == "description":
                self.meta_description = attrs.get("content", "")
            elif key in {"og:url", "twitter:url"}:
                self.social_urls[key] = attrs.get("content", "")
        elif tag == "script" and attrs.get("type") == "application/ld+json":
            self._in_json_ld = True
            self._json_ld_parts = []

    def handle_endtag(self, tag):
        if tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            self.json_ld.append(json.loads("".join(self._json_ld_parts)))

    def handle_data(self, data):
        if self._in_json_ld:
            self._json_ld_parts.append(data)

    def collection_page(self):
        pages = self.nodes_of_type("CollectionPage")
        if pages:
            return pages[0]
        raise AssertionError("CollectionPage JSON-LD node was not rendered")

    def nodes_of_type(self, node_type):
        return [
            node
            for payload in self.json_ld
            for node in payload.get("@graph", [])
            if node.get("@type") == node_type
        ]


@override_settings(
    SITE_BASE_URL="https://twocomms.shop",
    COMPRESS_ENABLED=False,
    COMPRESS_OFFLINE=False,
    NOVA_POSHTA_FALLBACK_ENABLED=False,
)
class CatalogFacetPaginationOwnerTests(TestCase):
    def setUp(self):
        super().setUp()
        previous_language = translation.get_language()
        self.addCleanup(translation.activate, previous_language or "uk")
        cache.clear()
        caches["fragments"].clear()
        feed_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(feed_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        feed_patcher.start()
        indexnow_patcher.start()

        self.category = Category.objects.create(
            name="Футболки",
            slug="tshirts",
            is_active=True,
        )
        self.other_category = Category.objects.create(
            name="Худі",
            slug="hoodie",
            is_active=True,
        )
        self.black = Color.objects.create(
            name="black",
            primary_hex="#000000",
        )
        self.tee_products = []
        for index in range(3):
            product = Product.objects.create(
                title=f"Facet tee {index}",
                slug=f"facet-tee-{index}",
                category=self.category,
                price=(900, 1100, 1000)[index],
                status="published",
            )
            self.tee_products.append(product)
            if index != 1:
                ProductColorVariant.objects.create(
                    product=product,
                    color=self.black,
                    is_default=True,
                    stock=3,
                )
            ProductFitOption.objects.create(
                product=product,
                code="classic" if index == 1 else "oversize",
                label="Classic" if index == 1 else "Oversize",
                is_default=True,
            )
        Product.objects.create(
            title="Other category product",
            slug="facet-hoodie",
            category=self.other_category,
            price=1200,
            status="published",
        )

    def _signals(self, response):
        parser = _CatalogOwnerSignalParser()
        parser.feed(response.content.decode("utf-8"))
        return parser

    def _assert_non_owner_facet_page(
        self,
        path,
        query,
        expected_owner,
        expected_pagination_state,
        expected_product_id,
    ):
        response = self.client.get(
            f"{path}?{query}",
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        parser = self._signals(response)
        self.assertEqual(parser.canonical, f"https://twocomms.shop{expected_owner}")
        self.assertEqual(
            parser.social_urls,
            {
                "og:url": f"https://twocomms.shop{expected_owner}",
                "twitter:url": f"https://twocomms.shop{expected_owner}",
            },
        )
        self.assertEqual(parser.nodes_of_type("CollectionPage"), [])
        self.assertEqual(len(parser.nodes_of_type("BreadcrumbList")), 1)
        self.assertContains(response, 'content="noindex, follow', html=False)
        self.assertNotIn('rel="alternate" hreflang=', response.content.decode("utf-8"))
        self.assertEqual(response.context["catalog_facet_state"], True)

        # The rendered page remains a real filtered slice, and its navigation
        # must retain the state even though SEO owner signals do not.
        self.assertEqual(
            [product.pk for product in response.context["products"]],
            [expected_product_id],
        )
        self.assertIn(
            expected_pagination_state,
            response.context["pagination_query_prefix"],
        )
        self.assertEqual(
            response.context["pagination_page_one_url"],
            f"{path}?{expected_pagination_state}",
        )

    def test_color_fit_and_root_category_page_two_use_clean_locale_owner(self):
        routes = (
            (
                "/catalog/tshirts/",
                "color=black&page=2",
                "/catalog/tshirts/",
                "color=black",
                self.tee_products[0].pk,
            ),
            (
                "/catalog/tshirts/",
                "fit=oversize&page=2",
                "/catalog/tshirts/",
                "fit=oversize",
                self.tee_products[0].pk,
            ),
            (
                "/catalog/",
                "category=tshirts&page=2",
                "/catalog/",
                "category=tshirts",
                self.tee_products[1].pk,
            ),
            (
                "/catalog/tshirts/",
                "sort=price-asc&page=2",
                "/catalog/tshirts/",
                "sort=price-asc",
                self.tee_products[2].pk,
            ),
            (
                "/ru/catalog/tshirts/",
                "color=black&page=2",
                "/ru/catalog/tshirts/",
                "color=black",
                self.tee_products[0].pk,
            ),
            (
                "/ru/catalog/tshirts/",
                "fit=oversize&page=2",
                "/ru/catalog/tshirts/",
                "fit=oversize",
                self.tee_products[0].pk,
            ),
            (
                "/ru/catalog/",
                "category=tshirts&page=2",
                "/ru/catalog/",
                "category=tshirts",
                self.tee_products[1].pk,
            ),
            (
                "/ru/catalog/tshirts/",
                "sort=price-asc&page=2",
                "/ru/catalog/tshirts/",
                "sort=price-asc",
                self.tee_products[2].pk,
            ),
            (
                "/en/catalog/tshirts/",
                "color=black&page=2",
                "/en/catalog/tshirts/",
                "color=black",
                self.tee_products[0].pk,
            ),
            (
                "/en/catalog/tshirts/",
                "fit=oversize&page=2",
                "/en/catalog/tshirts/",
                "fit=oversize",
                self.tee_products[0].pk,
            ),
            (
                "/en/catalog/",
                "category=tshirts&page=2",
                "/en/catalog/",
                "category=tshirts",
                self.tee_products[1].pk,
            ),
            (
                "/en/catalog/tshirts/",
                "sort=price-asc&page=2",
                "/en/catalog/tshirts/",
                "sort=price-asc",
                self.tee_products[2].pk,
            ),
        )
        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            for path, query, owner, pagination_state, product_id in routes:
                with self.subTest(path=path, query=query):
                    self._assert_non_owner_facet_page(
                        path,
                        query,
                        owner,
                        pagination_state,
                        product_id,
                    )

    def test_clean_page_two_keeps_self_owner_and_hreflang(self):
        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            for path, product_id in (
                ("/catalog/tshirts/", self.tee_products[1].pk),
                ("/ru/catalog/tshirts/", self.tee_products[1].pk),
                ("/en/catalog/tshirts/", self.tee_products[1].pk),
            ):
                with self.subTest(path=path):
                    response = self.client.get(f"{path}?page=2")

                    self.assertEqual(response.status_code, 200)
                    parser = self._signals(response)
                    expected = f"https://twocomms.shop{path}?page=2"
                    self.assertEqual(parser.canonical, expected)
                    self.assertEqual(parser.social_urls["og:url"], expected)
                    self.assertEqual(parser.social_urls["twitter:url"], expected)
                    collection = parser.collection_page()
                    self.assertEqual(collection["@id"], f"{expected}#collection")
                    self.assertEqual(collection["url"], expected)
                    self.assertContains(response, 'content="index, follow', html=False)
                    body = response.content.decode("utf-8")
                    self.assertEqual(body.count('rel="alternate" hreflang='), 4)
                    self.assertEqual(response.context["catalog_facet_state"], False)
                    self.assertEqual(
                        [product.pk for product in response.context["products"]],
                        [product_id],
                    )

    def test_ru_en_page_two_pagination_suffix_is_locale_owned(self):
        cases = (
            ("/ru/catalog/tshirts/", "Страница 2 из 3.", "Сторінка 2 з 3."),
            ("/en/catalog/tshirts/", "Page 2 of 3.", "Сторінка 2 з 3."),
        )
        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            for path, expected_suffix, forbidden_suffix in cases:
                with self.subTest(path=path):
                    response = self.client.get(f"{path}?page=2")
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, 'content="index, follow', html=False)
                    parser = self._signals(response)
                    expected_url = f"https://twocomms.shop{path}?page=2"
                    self.assertEqual(parser.canonical, expected_url)
                    self.assertIn(expected_suffix, parser.meta_description)
                    self.assertNotIn(forbidden_suffix, parser.meta_description)
                    collection = parser.collection_page()
                    self.assertIn(expected_suffix, collection["description"])
                    self.assertNotIn(forbidden_suffix, collection["description"])
                    self.assertEqual(
                        [product.pk for product in response.context["products"]],
                        [self.tee_products[1].pk],
                    )

    def test_tracking_only_page_two_keeps_page_owner_without_facet_state(self):
        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            for path, product_id in (
                ("/catalog/tshirts/", self.tee_products[1].pk),
                ("/ru/catalog/tshirts/", self.tee_products[1].pk),
                ("/en/catalog/tshirts/", self.tee_products[1].pk),
            ):
                with self.subTest(path=path):
                    response = self.client.get(
                        f"{path}?utm_source=audit&page=2"
                    )

                    self.assertEqual(response.status_code, 200)
                    parser = self._signals(response)
                    expected = f"https://twocomms.shop{path}?page=2"
                    self.assertEqual(parser.canonical, expected)
                    self.assertEqual(parser.social_urls["og:url"], expected)
                    self.assertEqual(parser.social_urls["twitter:url"], expected)
                    collection = parser.collection_page()
                    self.assertEqual(collection["@id"], f"{expected}#collection")
                    self.assertEqual(collection["url"], expected)
                    self.assertContains(response, 'content="noindex, follow', html=False)
                    self.assertNotIn(
                        'rel="alternate" hreflang=',
                        response.content.decode("utf-8"),
                    )
                    self.assertFalse(response.context["catalog_facet_state"])
                    self.assertEqual(
                        [product.pk for product in response.context["products"]],
                        [product_id],
                    )

    def test_warm_cache_keeps_clean_and_filtered_page_two_owners_isolated(self):
        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            filtered = self.client.get(
                "/catalog/tshirts/?color=black&page=2",
                follow=True,
            )
            clean = self.client.get("/catalog/tshirts/?page=2")
            filtered_cached = self.client.get(
                "/catalog/tshirts/?page=2&color=black"
            )
            clean_cached = self.client.get("/catalog/tshirts/?page=2")

        self.assertEqual(filtered_cached.content, filtered.content)
        self.assertEqual(clean_cached.content, clean.content)
        self.assertNotEqual(filtered_cached.content, clean_cached.content)
        self.assertEqual(
            self._signals(filtered_cached).canonical,
            "https://twocomms.shop/catalog/tshirts/",
        )
        self.assertEqual(
            self._signals(clean_cached).canonical,
            "https://twocomms.shop/catalog/tshirts/?page=2",
        )
