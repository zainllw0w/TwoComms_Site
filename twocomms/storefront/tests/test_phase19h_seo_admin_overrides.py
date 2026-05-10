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
    _normalize_swatch_overrides,
)


class ShowcaseSwatchesRealColoursTests(TestCase):
    """Phase 19i: swatches reflect REAL DB colours, no fake padding.

    The card honestly shows every distinct colour on stock, even
    one-product outliers (admin can override per-category if they
    want to hide them).
    """

    @classmethod
    def setUpTestData(cls):
        cls.cat = Category.objects.create(name="Hoodie", slug="hoodie", order=3)
        cls.black = Color.objects.create(name="Чорний", primary_hex="#000000")
        cls.pink = Color.objects.create(name="Рожевий", primary_hex="#F7A1B9")
        cls.split = Color.objects.create(
            name="бело-бордовий", primary_hex="#fafafa", secondary_hex="#c1382f",
        )
        # 3 black, 1 pink, 1 white-burgundy.
        for n in range(3):
            p = Product.objects.create(
                title=f"Hoodie black {n}", slug=f"hd-black-{n}",
                category=cls.cat, status="published", price=1000,
            )
            ProductColorVariant.objects.create(product=p, color=cls.black, slug="black")
        for clr, slug in [(cls.pink, "pink"), (cls.split, "wb")]:
            p = Product.objects.create(
                title=f"Hoodie {slug}", slug=f"hd-{slug}",
                category=cls.cat, status="published", price=1000,
            )
            ProductColorVariant.objects.create(product=p, color=clr, slug=slug)

    def test_returns_all_real_colours_no_padding(self):
        result = _compute_showcase_swatches(
            [self.cat.id], {self.cat.id: ('#050505', '#6a6b60')}
        )
        primaries = [s['primary'] for s in result[self.cat.id]]
        # All real colours present; none of the legacy fallback hexes leak in.
        self.assertEqual(len(result[self.cat.id]), 3)
        self.assertEqual(primaries[0], '#000000')  # black leads (3 products)
        self.assertIn('#F7A1B9', primaries)
        self.assertIn('#fafafa', primaries)
        self.assertNotIn('#050505', primaries)

    def test_split_colour_carries_secondary_hex(self):
        result = _compute_showcase_swatches([self.cat.id], {})
        wb = next(s for s in result[self.cat.id] if s['primary'] == '#fafafa')
        self.assertEqual(wb['secondary'], '#c1382f')

    def test_empty_category_falls_back_to_legacy(self):
        empty = Category.objects.create(name="Empty", slug="empty", order=9)
        result = _compute_showcase_swatches(
            [empty.id], {empty.id: ('#111111', '#222222')}
        )
        primaries = [s['primary'] for s in result[empty.id]]
        self.assertEqual(primaries, ['#111111', '#222222'])
        self.assertTrue(all(s['secondary'] is None for s in result[empty.id]))


class NormalizeSwatchOverridesTests(TestCase):
    def test_accepts_hex_strings(self):
        out = _normalize_swatch_overrides([
            "#000000", "FAFAFA", "  #b27815  ", "#000000", "not-a-hex",
            "#abcd", "#abc", 42, None,
        ])
        primaries = [s['primary'] for s in out]
        self.assertIn('#000000', primaries)
        self.assertIn('#fafafa', primaries)
        self.assertIn('#b27815', primaries)
        self.assertNotIn('#abcd', primaries)  # 5-char hex invalid
        self.assertEqual(len(primaries), len(set(primaries)))
        self.assertLessEqual(len(out), 4)
        self.assertTrue(all(s['secondary'] is None for s in out))

    def test_accepts_split_objects(self):
        out = _normalize_swatch_overrides([
            {"primary": "#fafafa", "secondary": "#c1382f"},
            "#000000",
        ])
        self.assertEqual(out[0], {"primary": "#fafafa", "secondary": "#c1382f"})
        self.assertEqual(out[1], {"primary": "#000000", "secondary": None})


class CategorySwatchOverrideTests(TestCase):
    def test_admin_override_wins_over_live(self):
        cat = Category.objects.create(
            name="Hoodie", slug="hoodie", order=1,
            showcase_swatch_hexes=[
                "#112233",
                {"primary": "#fafafa", "secondary": "#c1382f"},
            ],
        )
        clr = Color.objects.create(name="Чорний", primary_hex="#000000")
        for n in range(3):
            p = Product.objects.create(
                title=f"P{n}", slug=f"hp-{n}", category=cat,
                status="published", price=500,
            )
            ProductColorVariant.objects.create(product=p, color=clr, slug="black")
        from storefront.views.catalog import _build_catalog_showcase_cards
        cards = _build_catalog_showcase_cards([cat])
        card = next((c for c in cards if c.get('category') == cat), None)
        self.assertIsNotNone(card)
        # First swatch hex; second swatch carries split secondary.
        self.assertEqual(card['swatch_specs'][0]['primary'], '#112233')
        self.assertIsNone(card['swatch_specs'][0]['secondary'])
        self.assertEqual(card['swatch_specs'][1]['primary'], '#fafafa')
        self.assertEqual(card['swatch_specs'][1]['secondary'], '#c1382f')
        # No padding — exactly 2 admin-defined swatches.
        self.assertEqual(len(card['swatch_specs']), 2)


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
