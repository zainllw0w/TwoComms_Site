"""Phase 21 (PR-6) — image sitemap expansion + Merchant feed labels.

* Image sitemap emits gallery + variant images deduplicated.
* Google Merchant feed carries ``g:custom_label_0..4`` with stable
  values derived from product attributes.
"""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from storefront.models import Category, Product
from storefront.services.marketplace_feeds import _build_merchant_custom_labels
from types import SimpleNamespace


class CustomLabelHelperTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="PR6 Cat", slug="tshirts", is_active=True,
        )
        cls.product = Product.objects.create(
            title="PR6 Tee", slug="pr6-tee",
            category=cls.category, price=600, status="published",
        )

    def _offer(self, **overrides):
        defaults = dict(price=600, base_price=600, available=True)
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_returns_five_slot_list(self):
        labels = _build_merchant_custom_labels(self.product, self._offer())
        self.assertEqual(len(labels), 5)

    def test_category_slug_in_slot_1(self):
        labels = _build_merchant_custom_labels(self.product, self._offer())
        self.assertEqual(labels[1], "tshirts")

    def test_price_tier_classification(self):
        for price, expected in (
            (300, "sub_500"),
            (500, "500_1000"),
            (999, "500_1000"),
            (1500, "1000_plus"),
        ):
            with self.subTest(price=price):
                labels = _build_merchant_custom_labels(self.product, self._offer(price=price))
                self.assertEqual(labels[2], expected)

    def test_discount_flag_reflects_offer(self):
        # ``has_discount`` is a computed property on Product driven by
        # ``discount_percent``. Use an in-memory stand-in that exposes
        # the same surface area as the real model so we can flip the
        # flag explicitly.
        product_stub = SimpleNamespace(
            has_discount=True,
            category=self.category,
            created_at=None, published_at=None,
        )
        labels = _build_merchant_custom_labels(
            product_stub, self._offer(price=400, base_price=600),
        )
        self.assertEqual(labels[3], "on_sale")

        product_stub.has_discount = False
        labels_regular = _build_merchant_custom_labels(
            product_stub, self._offer(price=600, base_price=600),
        )
        self.assertEqual(labels_regular[3], "regular")


class ImageSitemapTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.category = Category.objects.create(
            name="ImgCat", slug="img-cat", is_active=True,
        )
        self.product = Product.objects.create(
            title="Img Tee", slug="img-tee",
            category=self.category, price=300, status="published",
        )

    def test_sitemap_renders_for_zero_image_product(self):
        """Phase 21 — products without any image should be skipped, not
        crash the response (regression: prefetch chains used to throw
        on ``main_image=''``).
        """
        response = self.client.get(reverse("sitemap_images"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<urlset", response.content)
