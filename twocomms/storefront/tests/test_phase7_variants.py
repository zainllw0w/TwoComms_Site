"""Phase 7 — path-URL variants regression tests.

Sub-phase 7.1 covers only the foundation: ``ProductColorVariant.slug``
auto-generation, uniqueness, and size-collision avoidance. URL routing,
canonical strategy, dynamic meta tags and the variant sitemap are
exercised by later sub-phases (7.2+) that build on top of this slug.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption


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


class PathVariantUrlTests(TestCase):
    """Phase 7.2 — path-style variant URL routing + parser.

    Segments can arrive in any order; the view dispatches them content-
    addressably (size vs colour-slug vs fit-code), overrides query-string
    preselections, and 404s on anything that doesn't match.
    """

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Футболки 7.2", slug="phase72-tshirts", is_active=True
        )
        cls.product = Product.objects.create(
            title="Тестова футболка 7.2",
            slug="phase72-tshirt",
            category=cls.category,
            price=1000,
            description="Phase 7.2 routing coverage.",
            status="published",
        )
        cls.black = Color.objects.create(name="Чорний", primary_hex="#000000")
        cls.white = Color.objects.create(name="Білий", primary_hex="#FFFFFF")
        cls.variant_black = ProductColorVariant.objects.create(
            product=cls.product, color=cls.black, order=0, is_default=True
        )
        cls.variant_white = ProductColorVariant.objects.create(
            product=cls.product, color=cls.white, order=1
        )
        ProductFitOption.objects.create(
            product=cls.product,
            code="classic",
            label="Класичний",
            is_default=True,
            order=0,
        )
        ProductFitOption.objects.create(
            product=cls.product,
            code="oversize",
            label="Оверсайз",
            order=1,
        )

    def test_color_only_path_preselects_color_variant(self):
        url = reverse("product", kwargs={"slug": self.product.slug, "v1": "white"})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preselected_color"], self.variant_white.pk)

    def test_color_and_size_path_preselects_both(self):
        url = reverse(
            "product",
            kwargs={"slug": self.product.slug, "v1": "white", "v2": "m"},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preselected_color"], self.variant_white.pk)
        self.assertEqual(response.context["preselected_size"], "M")

    def test_order_insensitive_parsing(self):
        """Phase 7.2 parser is content-addressable — segment order
        shouldn't matter. ``/white/m/`` and ``/m/white/`` are equivalent.
        """
        url = reverse(
            "product",
            kwargs={"slug": self.product.slug, "v1": "m", "v2": "white"},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preselected_color"], self.variant_white.pk)
        self.assertEqual(response.context["preselected_size"], "M")

    def test_fit_path_preselects_fit_code(self):
        url = reverse(
            "product",
            kwargs={"slug": self.product.slug, "v1": "oversize"},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preselected_fit_code"], "oversize")

    def test_three_segment_path_preselects_everything(self):
        url = reverse(
            "product",
            kwargs={
                "slug": self.product.slug,
                "v1": "black",
                "v2": "l",
                "v3": "oversize",
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preselected_color"], self.variant_black.pk)
        self.assertEqual(response.context["preselected_size"], "L")
        self.assertEqual(response.context["preselected_fit_code"], "oversize")

    def test_unknown_segment_returns_404(self):
        url = reverse(
            "product", kwargs={"slug": self.product.slug, "v1": "not-a-real-variant"}
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_path_overrides_query_string(self):
        """When both a path segment and a ``?color=`` query are present,
        the path wins — single source of truth for canonical URLs.
        """
        base = reverse("product", kwargs={"slug": self.product.slug, "v1": "white"})

        response = self.client.get(f"{base}?color={self.variant_black.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preselected_color"], self.variant_white.pk)
