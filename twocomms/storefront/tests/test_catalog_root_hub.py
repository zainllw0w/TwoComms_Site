"""Root catalog is a category-first hub, not a hidden product paginator."""

from __future__ import annotations

from html.parser import HTMLParser
import json
from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase, override_settings

from storefront.models import Category, Product


class _RootHubSignals(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = ""
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
            if key in {"og:url", "twitter:url"}:
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

    def nodes_of_type(self, node_type):
        return [
            node
            for payload in self.json_ld
            for node in payload.get("@graph", [payload])
            if node.get("@type") == node_type
        ]


@override_settings(
    SITE_BASE_URL="https://twocomms.shop",
    COMPRESS_ENABLED=False,
    COMPRESS_OFFLINE=False,
    NOVA_POSHTA_FALLBACK_ENABLED=False,
)
class CatalogRootHubTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categories = []
        for slug, uk, ru, en in (
            ("long-sleeve", "Лонгсліви", "Лонгсливы", "Long sleeves"),
            ("tshirts", "Футболки", "Футболки", "T-shirts"),
            ("hoodie", "Худі", "Худи", "Hoodies"),
        ):
            category = Category.objects.create(
                name=uk,
                name_ru=ru,
                name_en=en,
                slug=slug,
                is_active=True,
            )
            cls.categories.append(category)

        cls.tshirts = []
        for index in range(3):
            cls.tshirts.append(
                Product.objects.create(
                    title=f"Root hub tee {index}",
                    slug=f"root-hub-tee-{index}",
                    category=cls.categories[1],
                    price=900 + index,
                    priority=index,
                    status="published",
                )
            )
        for category in (cls.categories[0], cls.categories[2]):
            Product.objects.create(
                title=f"Root hub {category.slug}",
                slug=f"root-hub-{category.slug}",
                category=category,
                price=1200,
                status="published",
            )

    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _signals(self, response):
        parser = _RootHubSignals()
        parser.feed(response.content.decode("utf-8"))
        return parser

    def _assert_page_cache_was_not_touched(self, *mocked_calls):
        for mocked_call in mocked_calls:
            self.assertFalse(
                any(
                    call.args
                    and str(call.args[0]).startswith("anon-page:")
                    for call in mocked_call.call_args_list
                ),
                mocked_call.call_args_list,
            )

    def test_clean_root_pages_above_one_collapse_to_locale_hub(self):
        for path in ("/catalog/", "/ru/catalog/", "/en/catalog/"):
            for page in ("2", "02", "999"):
                with self.subTest(path=path, page=page):
                    response = self.client.get(f"{path}?page={page}", follow=False)
                    self.assertEqual(response.status_code, 301)
                    self.assertEqual(response["Location"], path)

    def test_tracking_root_redirect_preserves_opaque_values_and_drops_only_page(self):
        response = self.client.get(
            "/catalog/?utm_source=first&utm_source=second&page=02&campaign=A%20B",
            follow=False,
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "/catalog/?utm_source=first&utm_source=second&campaign=A+B",
        )
        final = self.client.get(response["Location"], follow=False)
        self.assertEqual(final.status_code, 200)
        self.assertContains(final, 'content="noindex, follow', html=False)
        self.assertEqual(self._signals(final).nodes_of_type("CollectionPage"), [])

    def test_default_sort_and_root_page_collapse_in_one_hop(self):
        cases = (
            ("/catalog/?sort=recommended&page=02", "/catalog/"),
            (
                "/ru/catalog/?utm_medium=organic&sort=recommended&page=2",
                "/ru/catalog/?utm_medium=organic",
            ),
        )
        for source, target in cases:
            with self.subTest(source=source):
                response = self.client.get(source, follow=False)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response["Location"], target)

    def test_invalid_root_page_values_are_404_before_cache(self):
        queries = (
            "page=2&page=3",
            "page=nope",
            "page=0",
            "page=-1",
            "page=99999999999",
            "page=٢",
        )
        for query in queries:
            with self.subTest(query=query), patch(
                "storefront.views.utils.cache.get", wraps=cache.get
            ) as cache_get:
                response = self.client.get(f"/catalog/?{query}", follow=False)
                self.assertEqual(response.status_code, 404)
                self._assert_page_cache_was_not_touched(cache_get)

    def test_real_root_result_state_keeps_strict_pagination(self):
        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            page_one = self.client.get("/catalog/?category=tshirts")
            page_two = self.client.get("/catalog/?category=tshirts&page=2")
            missing = self.client.get("/catalog/?category=tshirts&page=999")

        self.assertEqual(page_one.status_code, 200)
        self.assertEqual(page_two.status_code, 200)
        self.assertEqual(missing.status_code, 404)
        self.assertNotEqual(
            [product.pk for product in page_one.context["products"]],
            [product.pk for product in page_two.context["products"]],
        )
        self.assertContains(page_two, "catalog-products-grid")
        self.assertContains(page_two, "catalog-pagination")
        self.assertContains(page_two, 'content="noindex, follow', html=False)
        self.assertEqual(page_two.context["catalog_owner_path"], "/catalog/")
        self.assertEqual(self._signals(page_two).nodes_of_type("CollectionPage"), [])

    def test_category_clean_page_two_remains_a_real_indexable_page(self):
        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            response = self.client.get("/catalog/tshirts/?page=2")

        self.assertEqual(response.status_code, 200)
        signals = self._signals(response)
        self.assertEqual(
            signals.canonical,
            "https://twocomms.shop/catalog/tshirts/?page=2",
        )
        self.assertContains(response, 'content="index, follow', html=False)
        self.assertEqual(len(signals.nodes_of_type("CollectionPage")), 1)

    def test_root_redirect_is_resolved_before_page_cache(self):
        with patch(
            "storefront.views.utils.cache.get", wraps=cache.get
        ) as cache_get, patch(
            "storefront.views.utils.cache.set", wraps=cache.set
        ) as cache_set:
            response = self.client.get("/catalog/?page=2", follow=False)

        self.assertEqual(response.status_code, 301)
        self._assert_page_cache_was_not_touched(cache_get, cache_set)

    def test_clean_locale_hub_has_category_dom_head_and_truthful_schema(self):
        for path in ("/catalog/", "/ru/catalog/", "/en/catalog/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                body = response.content.decode("utf-8")
                signals = self._signals(response)
                expected_url = f"https://twocomms.shop{path}"

                self.assertTrue(response.context["show_category_cards"])
                self.assertIn('class="catalog-showcase"', body)
                self.assertIn('class="catalog-mobile-reference"', body)
                self.assertNotIn("catalog-products-grid", body)
                self.assertNotIn("catalog-pagination", body)
                self.assertNotIn('rel="prev"', body)
                self.assertNotIn('rel="next"', body)
                self.assertEqual(signals.canonical, expected_url)
                self.assertEqual(
                    signals.social_urls,
                    {"og:url": expected_url, "twitter:url": expected_url},
                )
                self.assertEqual(body.count('rel="alternate" hreflang='), 4)

                self.assertEqual(len(signals.nodes_of_type("BreadcrumbList")), 1)
                collection = signals.nodes_of_type("CollectionPage")
                self.assertEqual(len(collection), 1)
                item_list = collection[0]["mainEntity"]
                cards = response.context["catalog_showcase_cards"]
                self.assertEqual(item_list["numberOfItems"], 3)
                self.assertEqual(
                    item_list["itemListElement"],
                    [
                        {
                            "@type": "ListItem",
                            "position": index,
                            "url": f"https://twocomms.shop{card['url']}",
                            "name": str(card["title"]),
                        }
                        for index, card in enumerate(cards, start=1)
                    ],
                )
                self.assertFalse(
                    any(
                        "/product/" in item["url"]
                        for item in item_list["itemListElement"]
                    )
                )
                self.assertNotIn("itemListOrder", item_list)

    def test_legacy_catalog_pagination_redirects_directly_to_locale_hub(self):
        for source, target in (
            ("/catalog/page/1/", "/catalog/"),
            ("/catalog/page/3/", "/catalog/"),
            ("/ru/catalog/page/3/", "/ru/catalog/"),
            ("/en/catalog/page/3/", "/en/catalog/"),
        ):
            with self.subTest(source=source):
                response = self.client.get(source, follow=False)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response["Location"], target)
