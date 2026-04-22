import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from storefront.models import Category, Product
from storefront.services.catalog_helpers import (
    get_public_category_version,
    get_public_product_order_version,
)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "public-product-ordering-tests",
        },
        "fragments": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "public-product-ordering-tests-fragments",
        },
    }
)
class PublicProductOrderingTests(TestCase):
    def setUp(self):
        cache.clear()

        merchant_patcher = patch("storefront.signals.generate_google_merchant_feed_task.apply_async")
        product_indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        category_indexnow_patcher = patch("storefront.cache_signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(product_indexnow_patcher.stop)
        self.addCleanup(category_indexnow_patcher.stop)
        merchant_patcher.start()
        product_indexnow_patcher.start()
        category_indexnow_patcher.start()

        self.client = Client()
        self.staff_client = Client()
        self.staff_user = get_user_model().objects.create_user(
            username="catalog-staff",
            password="secret123",
            is_staff=True,
        )

        self.category = Category.objects.create(
            name="Ordering Category",
            slug="ordering-category",
            is_active=True,
        )

        self.middle_priority = Product.objects.create(
            title="Priority Mid Older",
            slug="priority-mid-older",
            category=self.category,
            price=1200,
            status="published",
            priority=10,
        )
        self.high_priority = Product.objects.create(
            title="Priority High Middle",
            slug="priority-high-middle",
            category=self.category,
            price=1300,
            status="published",
            priority=20,
        )
        self.low_priority = Product.objects.create(
            title="Priority Low Newest",
            slug="priority-low-newest",
            category=self.category,
            price=1100,
            status="published",
            priority=0,
        )

    def assert_titles_in_order(self, html, titles):
        cursor = -1
        for title in titles:
            position = html.find(title)
            self.assertGreater(position, cursor, f"Expected '{title}' after previous titles in HTML output.")
            cursor = position

    def test_public_lists_follow_admin_priority_order(self):
        expected_titles = [
            self.high_priority.title,
            self.middle_priority.title,
            self.low_priority.title,
        ]

        home_html = self.client.get(reverse("home"), secure=True).content.decode("utf-8")
        self.assert_titles_in_order(home_html, expected_titles)

        catalog_html = self.client.get(
            reverse("catalog_by_cat", args=[self.category.slug]),
            secure=True,
        ).content.decode("utf-8")
        self.assert_titles_in_order(catalog_html, expected_titles)

        search_html = self.client.get(reverse("search"), {"q": "Priority"}, secure=True).content.decode("utf-8")
        self.assert_titles_in_order(search_html, expected_titles)

        load_more_response = self.client.get(reverse("load_more_products"), {"page": 1}, secure=True)
        self.assertEqual(load_more_response.status_code, 200)
        payload = json.loads(load_more_response.content)
        self.assert_titles_in_order(payload["html"], expected_titles)

    def test_admin_reorder_applies_immediately_even_after_cached_home_response(self):
        initial_html = self.client.get(reverse("home"), secure=True).content.decode("utf-8")
        self.assert_titles_in_order(
            initial_html,
            [self.high_priority.title, self.middle_priority.title, self.low_priority.title],
        )

        self.staff_client.force_login(self.staff_user)
        initial_version = get_public_product_order_version()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.staff_client.post(
                reverse("admin_reorder_products"),
                data=json.dumps(
                    {
                        "order": [
                            self.low_priority.id,
                            self.high_priority.id,
                            self.middle_priority.id,
                        ]
                    }
                ),
                content_type="application/json",
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertGreater(get_public_product_order_version(), initial_version)

        self.low_priority.refresh_from_db()
        self.high_priority.refresh_from_db()
        self.middle_priority.refresh_from_db()

        self.assertEqual(self.low_priority.priority, 3)
        self.assertEqual(self.high_priority.priority, 2)
        self.assertEqual(self.middle_priority.priority, 1)

        updated_html = self.client.get(reverse("home"), secure=True).content.decode("utf-8")
        self.assert_titles_in_order(
            updated_html,
            [self.low_priority.title, self.high_priority.title, self.middle_priority.title],
        )

    def test_category_change_bumps_public_category_version(self):
        initial_version = get_public_category_version()

        with self.captureOnCommitCallbacks(execute=True):
            self.category.name = "Ordering Category Updated"
            self.category.save(update_fields=["name"])

        self.assertGreater(get_public_category_version(), initial_version)

    def test_product_save_bumps_public_product_version(self):
        initial_version = get_public_product_order_version()

        with self.captureOnCommitCallbacks(execute=True):
            self.high_priority.title = "Priority High Updated"
            self.high_priority.save(update_fields=["title"])

        self.assertGreater(get_public_product_order_version(), initial_version)

    def test_admin_status_update_bumps_public_product_version(self):
        self.staff_client.force_login(self.staff_user)
        initial_version = get_public_product_order_version()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.staff_client.post(
                reverse("admin_update_product_status"),
                data=json.dumps(
                    {
                        "product_id": self.high_priority.id,
                        "status": "draft",
                    }
                ),
                content_type="application/json",
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertGreater(get_public_product_order_version(), initial_version)
        self.high_priority.refresh_from_db()
        self.assertEqual(self.high_priority.status, "draft")

    def test_admin_catalogs_section_renders_drag_controls(self):
        self.staff_client.force_login(self.staff_user)

        response = self.staff_client.get(reverse("admin_panel"), {"section": "catalogs"}, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-drag-handle", html=False)
        self.assertContains(response, "Порядок зберігається після відпускання", html=False)
        self.assertContains(response, "placeholder.className = 'product-card-placeholder';", html=False)
        self.assertContains(response, "window.addEventListener('pointermove', onGlobalPointerMove, { passive: false });", html=False)
        self.assertContains(response, "document.body.classList.add('is-product-sorting');", html=False)
        self.assertNotContains(response, 'draggable="true"', html=False)
