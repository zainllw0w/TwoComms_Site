import json
import re
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from storefront.models import Category, Product
from storefront.views.utils import HOME_PRODUCTS_PER_PAGE


class HomepagePaginationWindowHelperTests(SimpleTestCase):
    def _signature(self, items):
        signature = []
        for item in items:
            if item["type"] == "page":
                signature.append(item["page"])
            else:
                signature.append(item["type"])
        return signature

    def test_build_homepage_pagination_items_shows_all_pages_below_threshold(self):
        from storefront.pagination import build_homepage_pagination_items

        items = build_homepage_pagination_items(
            current_page=3,
            total_pages=5,
            base_path="/",
        )

        self.assertEqual(self._signature(items), ["prev", 1, 2, 3, 4, 5, "next"])
        self.assertEqual(items[1]["url"], "/")
        self.assertEqual(items[5]["url"], "/?page=5")

    def test_build_homepage_pagination_items_compacts_start(self):
        from storefront.pagination import build_homepage_pagination_items

        items = build_homepage_pagination_items(
            current_page=1,
            total_pages=15,
            base_path="/",
        )

        self.assertEqual(self._signature(items), ["prev", 1, 2, 3, "ellipsis", 15, "next"])
        self.assertTrue(items[0]["is_disabled"])
        self.assertEqual(items[-1]["url"], "/?page=2")

    def test_build_homepage_pagination_items_compacts_middle(self):
        from storefront.pagination import build_homepage_pagination_items

        items = build_homepage_pagination_items(
            current_page=8,
            total_pages=15,
            base_path="/",
        )

        self.assertEqual(
            self._signature(items),
            ["prev", 1, "ellipsis", 7, 8, 9, "ellipsis", 15, "next"],
        )
        current_item = next(item for item in items if item["type"] == "page" and item["page"] == 8)
        self.assertTrue(current_item["is_current"])

    def test_build_homepage_pagination_items_compacts_end(self):
        from storefront.pagination import build_homepage_pagination_items

        items = build_homepage_pagination_items(
            current_page=15,
            total_pages=15,
            base_path="/",
        )

        self.assertEqual(self._signature(items), ["prev", 1, "ellipsis", 13, 14, 15, "next"])
        self.assertTrue(items[-1]["is_disabled"])


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
)
class HomepagePaginationWindowViewTests(TestCase):
    def setUp(self):
        cache.clear()
        merchant_patcher = patch("storefront.signals.generate_google_merchant_feed_task.apply_async")
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()
        self.client = Client()
        self.home_url = reverse("home")
        self.load_more_url = reverse("load_more_products")
        self.category = Category.objects.create(
            name="Pagination Test Category",
            slug="pagination-test-category",
            is_active=True,
        )

        for index in range(HOME_PRODUCTS_PER_PAGE * 8):
            Product.objects.create(
                title=f"Pagination Test Product {index}",
                slug=f"pagination-test-product-{index}",
                category=self.category,
                price=1000 + index,
                status="published",
            )

    def _extract_page_numbers(self, html):
        return re.findall(r'class="page-item page-item-number[^"]*" data-page="(\d+)"', html)

    def test_home_page_renders_compact_window_for_large_page_counts(self):
        response = self.client.get(self.home_url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pagination-showcase")
        self.assertContains(response, "page-item-ellipsis")
        self.assertContains(response, 'id="home-pagination-shell"', html=False)
        self.assertEqual(self._extract_page_numbers(response.content.decode("utf-8")), ["1", "2", "3", "8"])

    def test_load_more_returns_pagination_html(self):
        response = self.client.get(self.load_more_url, {"page": 2}, follow=True)

        self.assertEqual(response.status_code, 200)

        payload = json.loads(response.content)

        self.assertIn("pagination_html", payload)
        self.assertIn("page-item-ellipsis", payload["pagination_html"])
        self.assertIn('aria-current="page"', payload["pagination_html"])
        self.assertEqual(self._extract_page_numbers(payload["pagination_html"]), ["1", "2", "3", "8"])
