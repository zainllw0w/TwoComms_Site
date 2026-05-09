"""Phase 7 — path-URL variants regression tests.

Sub-phase 7.1 covers only the foundation: ``ProductColorVariant.slug``
auto-generation, uniqueness, and size-collision avoidance. URL routing,
canonical strategy, dynamic meta tags and the variant sitemap are
exercised by later sub-phases (7.2+) that build on top of this slug.
"""

from __future__ import annotations

from django.test import TestCase

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product


class ProductColorVariantSlugTests(TestCase):
    """Phase 7.1 — slug field on ProductColorVariant."""

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Футболки 7.1", slug="phase7-tshirts", is_active=True
        )
        cls.product = Product.objects.create(
            title="Тестова футболка 7.1",
            slug="phase7-tshirt",
            category=cls.category,
            price=1000,
            description="Phase 7.1 slug coverage.",
            status="published",
        )

    def test_slug_uses_english_translation_for_known_colors(self):
        color = Color.objects.create(name="Чорний", primary_hex="#000000")
        variant = ProductColorVariant.objects.create(
            product=self.product, color=color, order=0, is_default=True
        )

        # English translation map preferred over transliteration —
        # "Чорний" → "black", not "chornyi".
        self.assertEqual(variant.slug, "black")

    def test_slug_falls_back_to_transliteration_for_unknown_colors(self):
        color = Color.objects.create(name="Невідомий", primary_hex="#123456")
        variant = ProductColorVariant.objects.create(
            product=self.product, color=color, order=0
        )

        self.assertTrue(variant.slug)
        self.assertNotIn(" ", variant.slug)
        self.assertNotEqual(variant.slug, "невідомий")  # must be ASCII

    def test_slug_handles_compound_color_names(self):
        color = Color.objects.create(name="Чорний + Білий", primary_hex="#000000")
        variant = ProductColorVariant.objects.create(
            product=self.product, color=color, order=0
        )

        self.assertEqual(variant.slug, "black-white")

    def test_short_slug_is_disambiguated_from_size_codes(self):
        """One/two-letter colour names like 'M' must not collide with
        the ``M`` size code in path-style variant URLs.
        """
        color = Color.objects.create(name="M", primary_hex="#111111")
        variant = ProductColorVariant.objects.create(
            product=self.product, color=color, order=0
        )

        self.assertNotEqual(variant.slug.lower(), "m")
        self.assertTrue(variant.slug.endswith("-c") or len(variant.slug) > 4)

    def test_duplicate_color_names_get_unique_slugs_per_product(self):
        c1 = Color.objects.create(name="Хакі", primary_hex="#3C341F")
        c2 = Color.objects.create(name="Хакі", primary_hex="#4D4327")

        v1 = ProductColorVariant.objects.create(product=self.product, color=c1, order=0)
        v2 = ProductColorVariant.objects.create(product=self.product, color=c2, order=1)

        self.assertNotEqual(v1.slug, v2.slug)

    def test_explicit_slug_is_preserved(self):
        color = Color.objects.create(name="Олива", primary_hex="#556B2F")
        variant = ProductColorVariant.objects.create(
            product=self.product, color=color, order=0, slug="olive-edition"
        )

        self.assertEqual(variant.slug, "olive-edition")

    def test_fallback_to_hex_when_name_is_empty(self):
        color = Color.objects.create(name="", primary_hex="#A1B2C3")
        variant = ProductColorVariant.objects.create(
            product=self.product, color=color, order=0
        )

        self.assertTrue(variant.slug)
        self.assertIn("a1b2c3", variant.slug)
