"""Phase 16 — factual, locale-aware SEO for path-style variants.

The path can provide factual variant tokens (colour, size and fit), so the
title may describe those tokens.  The helper must not manufacture material,
print-method or delivery claims, and it must never emit ``meta keywords``.
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
from storefront.views.product import _is_locale_owned_variant_meta


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

    def test_fit_title_is_localized_and_has_no_unverified_claims(self):
        meta = build_variant_meta(self._inputs(
            current_path="/product/foo/oversize/",
            segments_count=1,
            product_title="Oversize T-shirt",
            fit_label="Оверсайз", fit_code="oversize", language="en",
        ))
        self.assertEqual(meta["page_title"], "Oversize T-shirt — oversize — TwoComms")
        self.assertIn("TwoComms", meta["page_title"])
        self.assertEqual(meta["page_description"], "")
        self.assertEqual(meta["page_keywords"], "")

    def test_fit_title_uses_russian_fit_label(self):
        meta = build_variant_meta(self._inputs(
            current_path="/product/foo/classic/",
            segments_count=1,
            product_title="Классическая футболка",
            fit_label="Класична", fit_code="classic", language="ru",
        ))
        self.assertEqual(
            meta["page_title"],
            "Классическая футболка — классическая — TwoComms",
        )
        self.assertEqual(meta["page_description"], "")
        self.assertEqual(meta["page_keywords"], "")

    def test_no_fit_lead_for_multi_segment(self):
        meta = build_variant_meta(self._inputs(
            current_path="/product/foo/black/oversize/",
            segments_count=2,
            color_name="Чорний", color_slug="black",
            fit_label="Оверсайз", fit_code="oversize",
        ))
        # Multi-segment titles contain only the selected factual tokens.
        self.assertTrue(meta["page_title"].startswith("Худі TwoComms —"))
        self.assertIn("оверсайз", meta["page_title"])
        self.assertEqual(meta["page_description"], "")
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

    def test_variant_override_requires_current_locale_ownership(self):
        self.assertTrue(
            _is_locale_owned_variant_meta(
                {"seo_title_source": "product:ru"}, "seo_title", "ru"
            )
        )
        self.assertFalse(
            _is_locale_owned_variant_meta(
                {"seo_title_source": "color:legacy"}, "seo_title", "ru"
            )
        )
        self.assertTrue(
            _is_locale_owned_variant_meta(
                {"seo_title_source": "color:legacy"}, "seo_title", "uk"
            )
        )


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
