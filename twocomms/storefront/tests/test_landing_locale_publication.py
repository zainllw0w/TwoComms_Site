"""Locale ownership tests for thematic and colour-category landings."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, CategoryColorLanding, Product
from storefront.services.index_targets import build_color_landing_urls


_LONG = (
    "Чорні футболки TwoComms для повсякденного гардероба. "
    "Опис колекції містить фактичні характеристики, посадку та догляд. "
) * 8


class LandingLocalePublicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Футболки", slug="tshirts", is_active=True,
        )
        cls.black = Color.objects.create(name="Чорний", primary_hex="#000000")
        cls.product = Product.objects.create(
            title="Black tee", slug="landing-locale-tee",
            category=cls.category, price=600, status="published",
        )
        ProductColorVariant.objects.create(
            product=cls.product, color=cls.black, is_default=True, order=0,
        )
        cls.landing = CategoryColorLanding.objects.create(
            category=cls.category, color=cls.black,
            seo_title="Чорні футболки TwoComms",
            seo_description="Чорні футболки TwoComms.",
            editorial_html=_LONG, is_published=True,
        )

    def setUp(self):
        super().setUp()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_color_landing_only_uk_owner_is_indexable(self):
        uk = self.client.get("/catalog/tshirts/black/")
        ru = self.client.get("/ru/catalog/tshirts/black/")
        en = self.client.get("/en/catalog/tshirts/black/")

        self.assertEqual(uk.status_code, 200)
        self.assertContains(uk, "index, follow")
        uk_body = uk.content.decode("utf-8")
        self.assertIn('hreflang="uk-UA"', uk_body)
        self.assertIn('hreflang="x-default"', uk_body)
        self.assertNotIn('hreflang="ru-UA"', uk_body)
        self.assertNotIn('hreflang="en-UA"', uk_body)

        for response in (ru, en):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "noindex, follow")
            self.assertNotIn('rel="alternate" hreflang=', response.content.decode("utf-8"))

    def test_thematic_landing_only_uk_owner_is_indexable(self):
        with patch("storefront.views.catalog.THEMATIC_LANDINGS_CONFIG") as config:
            config.__getitem__.side_effect = lambda key: {
                "h1": "Streetwear",
                "title": "Streetwear",
                "description": "Streetwear",
                "intro": "Streetwear",
                "keywords": "streetwear",
                "match_keywords": ["street"],
            }
            config.get.side_effect = config.__getitem__.side_effect
            uk = self.client.get("/catalog/theme/streetwear/")
            ru = self.client.get("/ru/catalog/theme/streetwear/")

        self.assertEqual(uk.status_code, 200)
        self.assertContains(uk, "index, follow")
        uk_body = uk.content.decode("utf-8")
        self.assertIn('hreflang="uk-UA"', uk_body)
        self.assertIn('hreflang="x-default"', uk_body)
        self.assertNotIn('hreflang="ru-UA"', uk_body)
        self.assertNotIn('hreflang="en-UA"', uk_body)
        self.assertEqual(ru.status_code, 200)
        self.assertContains(ru, "noindex, follow")
        self.assertNotIn('rel="alternate" hreflang=', ru.content.decode("utf-8"))

    def test_color_landing_index_targets_are_limited_to_owned_locale(self):
        urls = build_color_landing_urls(["uk", "ru", "en"])
        self.assertEqual(
            urls,
            ["https://twocomms.shop/catalog/tshirts/black/"],
        )
