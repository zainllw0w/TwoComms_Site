"""View tests for the colour×category landing pages.

URL: ``/catalog/<cat_slug>/<color_slug>/``.
"""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase
from django.urls import reverse

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, CategoryColorLanding, Product


_LONG = (
    "Чорна футболка TwoComms — це базовий шар стрітвір-гардеробу. "
    "Ми друкуємо принти DTF-методом на щільній бавовні 200 г/м² і "
    "збираємо комплекти для тих, хто звик носити одяг довго. "
    "Кожна модель пройшла тестування у польових умовах: концерт, "
    "тренування, кілька зустрічей у місті. Ми не вигадуємо казок — "
    "просто робимо одяг, у якому впевнено себе почуваєш. "
) * 4


class CategoryColorLandingViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Футболки", slug="tshirts", order=10, is_active=True,
        )
        cls.other_category = Category.objects.create(
            name="Худі", slug="hoodie", order=20, is_active=True,
        )
        cls.black = Color.objects.create(name="Чорний", primary_hex="#000000")
        cls.white = Color.objects.create(name="Білий", primary_hex="#FFFFFF")

        cls.tee = Product.objects.create(
            title="Black tee",
            slug="black-tee",
            category=cls.category,
            price=600,
            status="published",
        )
        ProductColorVariant.objects.create(
            product=cls.tee, color=cls.black, is_default=True, order=0
        )

        cls.tee2 = Product.objects.create(
            title="White tee",
            slug="white-tee",
            category=cls.category,
            price=600,
            status="published",
        )
        ProductColorVariant.objects.create(
            product=cls.tee2, color=cls.white, is_default=True, order=0
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

    def _make_published_landing(self, color=None):
        return CategoryColorLanding.objects.create(
            category=self.category,
            color=color or self.black,
            seo_title="Чорні футболки TwoComms — стрітвір з принтами",
            seo_description="Чорні футболки TwoComms з авторськими принтами.",
            editorial_html=_LONG,
            is_published=True,
        )

    # ---- Happy path ----

    def test_published_landing_renders_200(self):
        self._make_published_landing()
        url = reverse(
            "catalog_by_cat_color",
            kwargs={"cat_slug": "tshirts", "color_slug": "black"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Чорні футболки TwoComms")

    def test_landing_response_lists_only_matching_color_products(self):
        self._make_published_landing()
        url = reverse(
            "catalog_by_cat_color",
            kwargs={"cat_slug": "tshirts", "color_slug": "black"},
        )
        response = self.client.get(url)
        product_ids = [p.id for p in response.context["products"]]
        self.assertIn(self.tee.id, product_ids)
        self.assertNotIn(self.tee2.id, product_ids)

    def test_canonical_url_in_response_context(self):
        self._make_published_landing()
        url = reverse(
            "catalog_by_cat_color",
            kwargs={"cat_slug": "tshirts", "color_slug": "black"},
        )
        response = self.client.get(url)
        canonical = response.context["canonical_url"]
        self.assertTrue(canonical.endswith("/catalog/tshirts/black/"))

    def test_breadcrumb_items_in_context(self):
        self._make_published_landing()
        response = self.client.get("/catalog/tshirts/black/")
        crumbs = response.context["breadcrumb_items"]
        self.assertEqual(len(crumbs), 4)
        self.assertEqual(crumbs[0]["name"], "Головна")
        self.assertEqual(crumbs[1]["name"], "Каталог")
        self.assertEqual(crumbs[2]["name"], "Футболки")
        # Last crumb is the landing's H1.
        self.assertIn("Чорні футболки", crumbs[3]["name"])

    def test_structured_data_emits_collection_and_breadcrumb(self):
        self._make_published_landing()
        response = self.client.get("/catalog/tshirts/black/")
        body = response.content.decode("utf-8")
        self.assertIn('"@type": "BreadcrumbList"', body)
        self.assertIn('"@type": "CollectionPage"', body)

    def test_structured_data_emits_faq_when_present(self):
        landing = self._make_published_landing()
        landing.faq_items = [
            {"question": "Як прати чорні футболки?",
             "answer": "Прохолодна вода і виворіт."},
            {"question": "Який розмір обрати?",
             "answer": "Замовляйте свій звичайний розмір."},
        ]
        landing.save()
        response = self.client.get("/catalog/tshirts/black/")
        body = response.content.decode("utf-8")
        self.assertIn('"@type": "FAQPage"', body)
        self.assertIn("Як прати", body)

    # ---- 404 paths ----

    def test_unpublished_landing_returns_404(self):
        CategoryColorLanding.objects.create(
            category=self.category,
            color=self.black,
            seo_title="Draft чорні футболки",
            seo_description="—",
            editorial_html="—",
            is_published=False,
        )
        response = self.client.get("/catalog/tshirts/black/")
        self.assertEqual(response.status_code, 404)

    def test_unknown_color_slug_returns_404(self):
        self._make_published_landing()
        response = self.client.get("/catalog/tshirts/lemon/")
        self.assertEqual(response.status_code, 404)

    def test_landing_with_zero_matching_products_returns_404(self):
        # Publish a landing for white tees in a category that has none.
        empty_color = Color.objects.create(name="Хакі", primary_hex="#62684A")
        CategoryColorLanding.objects.create(
            category=self.category,
            color=empty_color,
            seo_title="Хакі футболки",
            seo_description="—",
            editorial_html=_LONG,
            is_published=True,
        )
        response = self.client.get("/catalog/tshirts/khaki/")
        self.assertEqual(response.status_code, 404)

    def test_inactive_category_returns_404(self):
        self.category.is_active = False
        self.category.save()
        self._make_published_landing()
        response = self.client.get("/catalog/tshirts/black/")
        self.assertEqual(response.status_code, 404)

    # ---- Internal links ----

    def test_sibling_landings_in_context(self):
        self._make_published_landing()
        # Add a sibling (white) landing for the same category.
        CategoryColorLanding.objects.create(
            category=self.category,
            color=self.white,
            seo_title="Білі футболки TwoComms",
            seo_description="Білі футболки.",
            editorial_html=_LONG,
            is_published=True,
        )
        response = self.client.get("/catalog/tshirts/black/")
        siblings = response.context["sibling_landings"]
        slugs = [s.color_slug for s in siblings]
        self.assertIn("white", slugs)
        self.assertNotIn("black", slugs)
