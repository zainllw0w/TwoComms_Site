"""Phase 19g — colour-aware SEO copy + live showcase swatches.

Covers two distinct features:

A. ``services.color_seo_copy.build_catalog_color_seo``:
   1. Returns brand-level copy for /catalog/ root (no category, no colour).
   2. Returns colour-specific copy for /catalog/?color=black (curated).
   3. Returns category × colour copy for /catalog/<cat>/?color=<slug>.
   4. Falls back to a generic colour copy for non-curated slugs but
      still emits at least one paragraph + queries.
   5. Returns None for /catalog/<cat>/ without colour filter (lets the
      existing ``category.description`` SEO text render alone).
   6. Curated query facets stay out of editorial output while noindex.

B. ``views.catalog._compute_showcase_swatches``:
   1. Replaces hard-coded swatches with live ``ProductColorVariant``
      hexes, ordered by usage.
   2. Pads to exactly 4 entries from the fallback when DB has fewer.
   3. Falls back entirely to the legacy palette for empty categories.
"""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase
from django.urls import reverse

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product
from storefront.services.color_seo_copy import build_catalog_color_seo
from storefront.views.catalog import _compute_showcase_swatches


class _Base(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            p = patch(target)
            self.addCleanup(p.stop)
            p.start()
        self.cat_hd = Category.objects.create(
            name="Худі", slug="hoodie-19g", is_active=True,
        )
        self.cat_ts = Category.objects.create(
            name="Футболки", slug="tshirts-19g", is_active=True,
        )
        self.color_black = Color.objects.create(name="Чорний", primary_hex="#000000")
        self.color_coyote = Color.objects.create(name="Кайот", primary_hex="#A98463")
        self.color_navy = Color.objects.create(name="Темно-синій", primary_hex="#0A1A33")


class ColorSeoCopyTests(_Base):
    def test_general_catalog_without_editorial_override_returns_none(self):
        copy = build_catalog_color_seo(
            category=None, selected_color_slugs=[], available_colors=[],
        )
        # The root catalog has no approved editorial owner in this fixture.
        # It must not publish the retired generic copy as a fallback.
        self.assertIsNone(copy)

    def test_curated_color_copy_does_not_publish_noindex_query_chips(self):
        copy = build_catalog_color_seo(
            category=None, selected_color_slugs=["black"], available_colors=[],
        )
        self.assertIsNotNone(copy)
        self.assertIn("Чорний", copy["h2"])
        # Curated query chips point at noindex UI state and are therefore
        # intentionally absent from the editorial payload.
        self.assertEqual(copy["queries"], [])

    def test_curated_color_copy_for_coyote(self):
        copy = build_catalog_color_seo(
            category=None, selected_color_slugs=["coyote"], available_colors=[],
        )
        self.assertIn("кайот", copy["h2"].lower())
        self.assertEqual(copy["queries"], [])
        self.assertNotIn('href="/catalog/?', " ".join(copy["paragraphs"]))

    def test_category_x_color_copy_includes_category_link(self):
        copy = build_catalog_color_seo(
            category=self.cat_hd,
            selected_color_slugs=["black"],
            available_colors=[],
        )
        self.assertIsNotNone(copy)
        body = " ".join(copy["paragraphs"])
        # Cross-link to the same category landing page (no colour) for
        # users who want to widen the filter.
        self.assertIn(f"/catalog/{self.cat_hd.slug}/", body)
        # Query facets are UI state, not editorial owners.
        self.assertNotIn('href="/catalog/?', body)

    def test_per_category_without_color_returns_none(self):
        # /catalog/<cat>/ without colour filter — the existing
        # category.description block already provides SEO text, so the
        # builder should bow out.
        copy = build_catalog_color_seo(
            category=self.cat_hd,
            selected_color_slugs=[],
            available_colors=[],
        )
        self.assertIsNone(copy)

    def test_generic_color_copy_for_non_curated_slug(self):
        copy = build_catalog_color_seo(
            category=None,
            selected_color_slugs=["navy"],
            available_colors=[
                {"slug": "navy", "label": "Темно-синій"},
            ],
        )
        self.assertIsNotNone(copy)
        # Generic copy embeds the colour label inside the prose.
        self.assertIn("темно-синій", " ".join(copy["paragraphs"]).lower())
        # Generic copy must not publish a noindex query facet as an
        # editorial destination.
        self.assertEqual(copy["queries"], [])


class ColorSeoViewIntegrationTests(_Base):
    def test_general_catalog_without_override_skips_color_seo_section(self):
        resp = self.client.get(reverse("catalog"))
        body = resp.content.decode()
        self.assertNotIn('<section class="catalog-color-seo"', body)
        # Regression marker from the retired unowned fallback.
        self.assertNotIn("30+ циклів", body)

    def test_filtered_catalog_renders_color_seo_section(self):
        # Need at least one product with a black variant so the colour
        # filter actually returns matches AND the chip is in available_colors.
        product = Product.objects.create(
            title="HD",
            slug="hd-19g-color",
            category=self.cat_hd,
            price=100,
            status="published",
        )
        ProductColorVariant.objects.create(
            product=product, color=self.color_black,
            order=0, is_default=True,
        )
        resp = self.client.get(reverse("catalog") + "?color=black")
        body = resp.content.decode()
        self.assertIn("catalog-color-seo", body)
        color_seo = body.split('<section class="catalog-color-seo"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertIn("Чорний", color_seo)
        self.assertNotIn('href="/catalog/?', color_seo)


class ShowcaseSwatchesTests(_Base):
    def test_live_swatches_use_top_used_color(self):
        # Two products in cat_hd: one black (most stocked), one coyote.
        p1 = Product.objects.create(
            title="P1", slug="p1-sw", category=self.cat_hd,
            price=100, status="published",
        )
        p2 = Product.objects.create(
            title="P2", slug="p2-sw", category=self.cat_hd,
            price=100, status="published",
        )
        ProductColorVariant.objects.create(
            product=p1, color=self.color_black, order=0, is_default=True,
        )
        ProductColorVariant.objects.create(
            product=p2, color=self.color_black, order=0, is_default=True,
        )
        ProductColorVariant.objects.create(
            product=p2, color=self.color_coyote, order=1, is_default=False,
        )
        result = _compute_showcase_swatches(
            [self.cat_hd.id],
            fallback_per_category={self.cat_hd.id: ("#FFFFFF", "#888888")},
        )
        swatches = result[self.cat_hd.id]
        self.assertEqual(len(swatches), 4)
        # Black is the most-used → leads.
        self.assertEqual(swatches[0], "#000000")
        self.assertIn("#A98463", swatches)
        # Fallback hexes pad the tail.
        self.assertIn("#FFFFFF", swatches)

    def test_swatches_fall_back_when_no_variants(self):
        # cat_ts has no products at all — fallback palette must surface.
        result = _compute_showcase_swatches(
            [self.cat_ts.id],
            fallback_per_category={
                self.cat_ts.id: ("#050505", "#3a3d3f", "#62684a", "#ede8dc"),
            },
        )
        self.assertEqual(
            result[self.cat_ts.id],
            ("#050505", "#3a3d3f", "#62684a", "#ede8dc"),
        )

    def test_swatches_padded_to_four(self):
        # Single colour in DB → must still produce 4 entries by padding
        # from the fallback (visual integrity of the showcase card).
        p1 = Product.objects.create(
            title="P3", slug="p3-sw", category=self.cat_hd,
            price=100, status="published",
        )
        ProductColorVariant.objects.create(
            product=p1, color=self.color_black, order=0, is_default=True,
        )
        result = _compute_showcase_swatches(
            [self.cat_hd.id],
            fallback_per_category={
                self.cat_hd.id: ("#FFFFFF", "#888888", "#444444", "#222222"),
            },
        )
        self.assertEqual(len(result[self.cat_hd.id]), 4)
        self.assertEqual(result[self.cat_hd.id][0], "#000000")
