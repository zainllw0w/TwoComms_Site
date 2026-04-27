"""
Regression tests for storefront home/catalog/search endpoints.
"""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from storefront.models import Category, Product


class CatalogViewTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        merchant_patcher = patch("storefront.signals.generate_google_merchant_feed_task.apply_async")
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()
        self.category = Category.objects.create(
            name="Category 1",
            slug="category-1",
            is_active=True,
        )
        self.other_category = Category.objects.create(
            name="Category 2",
            slug="category-2",
            is_active=True,
        )

    def create_product(
        self,
        *,
        title: str,
        slug: str,
        category: Category | None = None,
        price: int = 100,
        description: str = "",
        status: str = "published",
        featured: bool = False,
    ) -> Product:
        return Product.objects.create(
            title=title,
            slug=slug,
            category=category or self.category,
            price=price,
            description=description,
            status=status,
            featured=featured,
        )


class HomeViewTests(CatalogViewTestCase):
    def test_home_page_loads_with_published_products_only(self):
        published = self.create_product(title="Published Product", slug="published-product", featured=True)
        self.create_product(title="Draft Product", slug="draft-product", status="draft")

        response = self.client.get(reverse("home"))
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertIn(published.title, product_titles)
        self.assertNotIn("Draft Product", product_titles)
        self.assertEqual(response.context["featured"].pk, published.pk)

    def test_home_page_caches_anonymous_response(self):
        self.create_product(title="Cached Product", slug="cached-product")

        first = self.client.get(reverse("home"))
        second = self.client.get(reverse("home"))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.content, second.content)


class CatalogViewTests(CatalogViewTestCase):
    def test_catalog_root_shows_published_products_and_category_cards(self):
        self.create_product(title="Root Product", slug="root-product")
        self.create_product(
            title="Other Product",
            slug="other-product",
            category=self.other_category,
        )
        self.create_product(title="Hidden Product", slug="hidden-product", status="draft")

        response = self.client.get(reverse("catalog"))
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_category_cards"])
        self.assertIn("Root Product", product_titles)
        self.assertIn("Other Product", product_titles)
        self.assertNotIn("Hidden Product", product_titles)

    def test_catalog_by_category_limits_results_to_selected_category(self):
        in_category = self.create_product(title="Category Product", slug="category-product")
        self.create_product(
            title="Other Category Product",
            slug="other-category-product",
            category=self.other_category,
        )

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["category"].pk, self.category.pk)
        product_titles = [product.title for product in response.context["products"]]
        self.assertIn(in_category.title, product_titles)
        self.assertNotIn("Other Category Product", product_titles)

    def test_catalog_by_category_returns_404_for_inactive_category(self):
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug}))

        self.assertEqual(response.status_code, 404)


class SearchViewTests(CatalogViewTestCase):
    def test_search_finds_products_by_title_case_insensitively(self):
        self.create_product(title="Red T-Shirt", slug="red-t-shirt")
        self.create_product(title="Blue Jeans", slug="blue-jeans")

        response = self.client.get(reverse("search"), {"q": "RED"})
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertIn("Red T-Shirt", product_titles)
        self.assertNotIn("Blue Jeans", product_titles)
        self.assertEqual(response.context["results_count"], 1)

    def test_search_finds_products_by_description(self):
        self.create_product(
            title="Utility Hoodie",
            slug="utility-hoodie",
            description="Comfortable field-tested hoodie",
        )
        self.create_product(title="Plain Tee", slug="plain-tee", description="Minimal cotton tee")

        response = self.client.get(reverse("search"), {"q": "field-tested"})
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertIn("Utility Hoodie", product_titles)
        self.assertNotIn("Plain Tee", product_titles)

    def test_search_with_empty_query_returns_all_published_products(self):
        self.create_product(title="Published One", slug="published-one")
        self.create_product(title="Published Two", slug="published-two")
        self.create_product(title="Draft Product", slug="draft-product", status="draft")

        response = self.client.get(reverse("search"), {"q": ""})
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["results_count"], 2)
        self.assertIn("Published One", product_titles)
        self.assertIn("Published Two", product_titles)
        self.assertNotIn("Draft Product", product_titles)


class LoadMoreProductsTests(CatalogViewTestCase):
    def test_load_more_returns_json_page_metadata(self):
        for index in range(9):
            self.create_product(
                title=f"Paged Product {index}",
                slug=f"paged-product-{index}",
            )

        response = self.client.get(reverse("load_more_products"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("html", payload)
        self.assertEqual(payload["current_page"], 2)
        self.assertFalse(payload["has_more"])
        self.assertEqual(payload["total_pages"], 2)

    def test_load_more_clamps_page_beyond_range_to_last_page(self):
        for index in range(9):
            self.create_product(
                title=f"Paged Product {index}",
                slug=f"paged-product-{index}",
            )

        response = self.client.get(reverse("load_more_products"), {"page": 99})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["current_page"], 2)
        self.assertFalse(payload["has_more"])

    def test_load_more_handles_invalid_page_as_first_page(self):
        for index in range(9):
            self.create_product(
                title=f"Invalid Page Product {index}",
                slug=f"invalid-page-product-{index}",
            )

        response = self.client.get(reverse("load_more_products"), {"page": "bad"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["current_page"], 1)
        self.assertTrue(payload["has_more"])
