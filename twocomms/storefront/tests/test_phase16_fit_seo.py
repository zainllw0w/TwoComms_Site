"""Phase 16 — fit-aware SEO.

Covers:
1. ``build_variant_meta`` — when a 1-segment fit is active, title/desc
   put the fit term in *front*, and ``page_keywords`` is populated.
2. Multi-segment combos keep the legacy suffix-based meta (no fit lead).
3. Base PDP (segments_count=0) returns empty meta + empty keywords.
4. ``product_seo_landing.build_landing`` does not publish generated
   fit-specific copy without a reviewed editorial override.
"""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase

from storefront.models import Category, Product, ProductFitOption
from storefront.services.product_seo_landing import build_landing, FIT_SEO_COPY
from storefront.services.variant_meta import (
    VariantMetaInputs,
    build_variant_meta,
)


class VariantMetaFitAwarenessTests(TestCase):

    def _inputs(self, **overrides):
        defaults = dict(
            product_title="Худі TwoComms",
            base_path="/product/foo/",
            current_path="/product/foo/",
            segments_count=0,
        )
        defaults.update(overrides)
        return VariantMetaInputs(**defaults)

    def test_fit_lead_when_single_segment(self):
        meta = build_variant_meta(self._inputs(
            current_path="/product/foo/oversize/",
            segments_count=1,
            fit_label="Оверсайз", fit_code="oversize",
        ))
        # Title puts fit in front (not "Купити X — оверсайз").
        self.assertTrue(meta["page_title"].startswith("Оверсайз Худі TwoComms"))
        self.assertIn("TwoComms", meta["page_title"])
        # Description leads with the fit and contains brand keywords.
        self.assertTrue(meta["page_description"].startswith("Оверсайз посадка"))
        self.assertIn("DTF-друк", meta["page_description"])
        self.assertIn("Новою Поштою", meta["page_description"])

    def test_keywords_filled_for_fit_only(self):
        meta = build_variant_meta(self._inputs(
            current_path="/product/foo/classic/",
            segments_count=1,
            fit_label="Класична", fit_code="classic",
        ))
        self.assertIn("класична посадка", meta["page_keywords"])
        self.assertIn("classic", meta["page_keywords"])
        self.assertIn("купити", meta["page_keywords"])

    def test_no_fit_lead_for_multi_segment(self):
        meta = build_variant_meta(self._inputs(
            current_path="/product/foo/black/oversize/",
            segments_count=2,
            color_name="Чорний", color_slug="black",
            fit_label="Оверсайз", fit_code="oversize",
        ))
        # Multi-segment uses the legacy suffix template ("Купити X — Y").
        self.assertTrue(meta["page_title"].startswith("Купити Худі TwoComms"))
        self.assertIn("оверсайз", meta["page_title"])
        # Keywords stay empty for multi-segment to avoid keyword stuffing.
        self.assertEqual(meta["page_keywords"], "")

    def test_no_keywords_for_color_or_size_only(self):
        meta = build_variant_meta(self._inputs(
            current_path="/product/foo/black/",
            segments_count=1,
            color_name="Чорний", color_slug="black",
        ))
        self.assertEqual(meta["page_keywords"], "")

    def test_base_pdp_empty(self):
        meta = build_variant_meta(self._inputs(segments_count=0))
        self.assertEqual(meta["page_title"], "")
        self.assertEqual(meta["page_keywords"], "")
        self.assertTrue(meta["is_self_canonical"])


class LandingFitParagraphTests(TestCase):
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

        self.cat = Category.objects.create(
            name="Футболки", slug="tshirts", is_active=True,
        )
        self.product = Product.objects.create(
            title="Футболка Тест",
            slug="ts-test", category=self.cat, price=900,
            status="published",
        )
        ProductFitOption.objects.create(
            product=self.product, code="oversize", label="Оверсайз",
            is_default=False, is_active=True, order=0,
        )
        ProductFitOption.objects.create(
            product=self.product, code="classic", label="Класична",
            is_default=True, is_active=True, order=1,
        )

    def test_oversize_has_no_generated_copy_without_override(self):
        html = build_landing(self.product, fit_code="oversize")["landing_html"]
        self.assertEqual(html, "")

    def test_classic_has_no_generated_copy_without_override(self):
        html = build_landing(self.product, fit_code="classic")["landing_html"]
        self.assertEqual(html, "")

    def test_fit_pages_do_not_publish_hash_or_template_paraphrases(self):
        oversize = build_landing(self.product, fit_code="oversize")["landing_html"]
        classic = build_landing(self.product, fit_code="classic")["landing_html"]
        self.assertEqual(oversize, classic)
        self.assertEqual(oversize, "")

    def test_no_fit_no_h3(self):
        html = build_landing(self.product)["landing_html"]
        self.assertNotIn("Чому оверсайз", html)
        self.assertNotIn("Чому класична", html)

    def test_unknown_fit_does_not_inject_block(self):
        html = build_landing(self.product, fit_code="bogus")["landing_html"]
        for entry in FIT_SEO_COPY.values():
            self.assertNotIn(entry["h3"], html)
