"""Phase 19h (2026-05-10) — admin-editable SEO overrides.

Covers:
* ``CatalogColorSeoOverride`` row overrides H2 / body / queries on /catalog/
  root, /catalog/?color= and /catalog/<cat>/?color=.
* ``Category.showcase_swatch_hexes`` overrides live swatch computation.
* ``_compute_showcase_swatches`` min_usage threshold suppresses one-product
  outliers.
* SEO dashboard surfaces override summary correctly.
"""
from __future__ import annotations

from django.test import TestCase

from productcolors.models import Color, ProductColorVariant
from storefront.models import (
    CatalogColorSeoOverride,
    Category,
    Product,
)
from storefront.services.color_seo_copy import build_catalog_color_seo
from storefront.services.seo_dashboard import build_color_seo_overrides_summary
from storefront.views.catalog import (
    _compute_showcase_swatches,
    _normalize_swatch_hexes,
)


class SwatchOutlierThresholdTests(TestCase):
    """Min-usage threshold filters out one-product colour outliers."""

    @classmethod
    def setUpTestData(cls):
        cls.cat = Category.objects.create(name="Hoodie", slug="hoodie", order=3)
        cls.black = Color.objects.create(name="Чорний", primary_hex="#000000")
        cls.pink = Color.objects.create(name="Рожевий", primary_hex="#F7A1B9")
        # 3 black hoodies, 1 pink hoodie — pink should be suppressed.
        for n in range(3):
            p = Product.objects.create(
                title=f"Hoodie black {n}", slug=f"hd-black-{n}",
                category=cls.cat, status="published", price=1000,
            )
            ProductColorVariant.objects.create(product=p, color=cls.black, slug="black")
        p = Product.objects.create(
            title="Hoodie pink", slug="hd-pink", category=cls.cat,
            status="published", price=1000,
        )
        ProductColorVariant.objects.create(product=p, color=cls.pink, slug="pink")

    def test_pink_outlier_suppressed_by_default(self):
        result = _compute_showcase_swatches(
            [self.cat.id], {self.cat.id: ('#050505', '#6a6b60', '#e7e1d3', '#8c8f79')}
        )
        # First swatch is live black; pink (1 usage) should NOT appear.
        self.assertIn('#000000', result[self.cat.id])
        self.assertNotIn('#F7A1B9', result[self.cat.id])
        # Padding from fallback fills the rest.
        self.assertEqual(len(result[self.cat.id]), 4)

    def test_min_usage_one_includes_outliers(self):
        result = _compute_showcase_swatches(
            [self.cat.id], {self.cat.id: ('#050505',)}, min_usage=1,
        )
        self.assertIn('#F7A1B9', result[self.cat.id])


class NormalizeSwatchHexesTests(TestCase):
    def test_strips_invalid_entries_and_dedupes(self):
        out = _normalize_swatch_hexes([
            "#000000", "FAFAFA", "  #b27815  ", "#000000", "not-a-hex",
            "#abcd", "#abc", 42, None,
        ])
        # #000000 once, #fafafa (autoprefix), #b27815, #abc — and #abcd
        # rejected (5-char), invalid strings rejected, duplicates dropped.
        self.assertIn('#000000', out)
        self.assertIn('#fafafa', out)
        self.assertIn('#b27815', out)
        self.assertNotIn('#abcd', out)
        self.assertEqual(len(set(out)), len(out))
        self.assertLessEqual(len(out), 4)


class CategorySwatchOverrideTests(TestCase):
    def test_admin_override_wins_over_live(self):
        cat = Category.objects.create(
            name="Hoodie", slug="hoodie", order=1,
            showcase_swatch_hexes=["#112233", "#445566"],
        )
        clr = Color.objects.create(name="Чорний", primary_hex="#000000")
        for n in range(3):
            p = Product.objects.create(
                title=f"P{n}", slug=f"hp-{n}", category=cat,
                status="published", price=500,
            )
            ProductColorVariant.objects.create(product=p, color=clr, slug="black")
        # Direct call to the higher-level builder — verify override is honoured.
        from storefront.views.catalog import _build_catalog_showcase_cards
        cards = _build_catalog_showcase_cards([cat])
        # Find the card matching this hoodie category by slug match.
        card = next((c for c in cards if c.get('category') == cat), None)
        self.assertIsNotNone(card)
        self.assertEqual(card['swatches'][0], '#112233')
        self.assertEqual(card['swatches'][1], '#445566')
        # Pad to 4 from fallback (legacy palette).
        self.assertEqual(len(card['swatches']), 4)


class ColorSeoOverrideTests(TestCase):
    def test_general_override_replaces_h2_and_body(self):
        CatalogColorSeoOverride.objects.create(
            scope="general", color_slug="", category=None,
            h2="MY CUSTOM H2",
            body_html="<p>First.</p><p>Second.</p>",
            queries_json=[
                {"label": "X", "url": "/catalog/", "freq": "hf"},
            ],
            is_active=True,
        )
        out = build_catalog_color_seo(
            category=None, selected_color_slugs=None, available_colors=[],
        )
        self.assertEqual(out["h2"], "MY CUSTOM H2")
        self.assertEqual(out["paragraphs"], ["First.", "Second."])
        self.assertEqual(out["queries"], [
            {"label": "X", "url": "/catalog/", "freq": "hf"},
        ])

    def test_brand_override_partial_keeps_curated(self):
        # Only override the H2; body & queries fall back to curated black copy.
        CatalogColorSeoOverride.objects.create(
            scope="brand", color_slug="black", category=None,
            h2="Чорний переосмислений",
            body_html="",
            queries_json=[],
            is_active=True,
        )
        out = build_catalog_color_seo(
            category=None, selected_color_slugs=["black"], available_colors=[],
        )
        self.assertEqual(out["h2"], "Чорний переосмислений")
        # Curated paragraphs preserved.
        self.assertTrue(any("Чорний" in p for p in out["paragraphs"]))
        # Curated queries preserved.
        self.assertTrue(any(q["label"] == "Купити чорне худі" for q in out["queries"]))

    def test_inactive_override_is_ignored(self):
        CatalogColorSeoOverride.objects.create(
            scope="general", color_slug="", category=None,
            h2="WILL NOT SHOW",
            is_active=False,
        )
        out = build_catalog_color_seo(
            category=None, selected_color_slugs=None, available_colors=[],
        )
        self.assertNotEqual(out["h2"], "WILL NOT SHOW")

    def test_category_scope_override(self):
        cat = Category.objects.create(name="Hoodie", slug="hoodie", order=1)
        CatalogColorSeoOverride.objects.create(
            scope="category", color_slug="black", category=cat,
            h2="Чорне худі — preview",
            body_html="<p>Per-category override.</p>",
            is_active=True,
        )
        out = build_catalog_color_seo(
            category=cat, selected_color_slugs=["black"], available_colors=[],
        )
        self.assertEqual(out["h2"], "Чорне худі — preview")
        self.assertIn("Per-category override.", out["paragraphs"])

    def test_query_freq_validation(self):
        CatalogColorSeoOverride.objects.create(
            scope="general", color_slug="", category=None,
            queries_json=[
                {"label": "ok", "url": "/", "freq": "hf"},
                {"label": "", "url": "/", "freq": "hf"},   # empty label dropped
                {"label": "bad-freq", "url": "/", "freq": "ZZZ"},  # default mf
                {"label": "ok2", "url": "", "freq": "lf"},  # empty url dropped
                "not-a-dict",
            ],
            is_active=True,
        )
        out = build_catalog_color_seo(
            category=None, selected_color_slugs=None, available_colors=[],
        )
        labels = [q["label"] for q in out["queries"]]
        self.assertIn("ok", labels)
        self.assertIn("bad-freq", labels)
        self.assertNotIn("", labels)
        self.assertNotIn("ok2", labels)
        bad_freq_chip = next(q for q in out["queries"] if q["label"] == "bad-freq")
        self.assertEqual(bad_freq_chip["freq"], "mf")


class SeoDashboardSummaryTests(TestCase):
    def test_summary_counts_by_scope(self):
        CatalogColorSeoOverride.objects.create(
            scope="general", color_slug="", h2="A", is_active=True,
        )
        CatalogColorSeoOverride.objects.create(
            scope="brand", color_slug="black", h2="B", is_active=True,
        )
        CatalogColorSeoOverride.objects.create(
            scope="brand", color_slug="coyote", h2="C", is_active=False,
        )
        summary = build_color_seo_overrides_summary()
        self.assertEqual(summary["counts"]["total"], 3)
        self.assertEqual(summary["counts"]["active"], 2)
        self.assertEqual(summary["counts"]["general"], 1)
        self.assertEqual(summary["counts"]["brand"], 2)
        self.assertEqual(summary["counts"]["category"], 0)
        # Rows include all (including inactive) for visibility.
        self.assertEqual(len(summary["rows"]), 3)

    def test_categories_with_swatches_listed(self):
        Category.objects.create(
            name="Hoodie", slug="hoodie", order=1,
            showcase_swatch_hexes=["#000000", "#fafafa"],
        )
        Category.objects.create(name="Empty", slug="empty", order=2)
        summary = build_color_seo_overrides_summary()
        slugs = [c["slug"] for c in summary["categories_with_swatches"]]
        self.assertIn("hoodie", slugs)
        self.assertNotIn("empty", slugs)
