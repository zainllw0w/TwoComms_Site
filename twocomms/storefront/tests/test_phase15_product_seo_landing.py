"""Phase 15 — per-product SEO landing block."""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase

from productcolors.models import Color, ProductColorVariant
from storefront.models import (
    Category, Product, ProductFitOption,
    CategorySeoBlock, CategorySeoBlockItem,
)
from storefront.services.product_seo_landing import (
    build_landing,
    _top_queries_for_product,
    _category_layout_for_product,
)


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

        self.cat = Category.objects.create(
            name="Худі", slug="hoodie", is_active=True,
        )
        self.product = Product.objects.create(
            title='Худі Тест Модель',
            slug="hd-test",
            category=self.cat,
            price=1500,
            status="published",
        )
        self.color_black = Color.objects.create(name="Чорний", primary_hex="#000")
        self.variant_black = ProductColorVariant.objects.create(
            product=self.product, color=self.color_black,
            order=0, is_default=True,
        )


class LandingHtmlTests(_Base):

    def test_returns_landing_html_with_h2_and_paragraphs(self):
        result = build_landing(self.product)
        self.assertEqual(result["override_html"], "")
        html = result["landing_html"]
        self.assertIn("<h2", html)
        self.assertIn(self.product.title, html)
        # City keywords paragraph.
        self.assertIn("Київ", html)
        self.assertIn("Новою Поштою", html)
        # Brand closing paragraph.
        self.assertIn("TwoComms", html)
        self.assertIn("Збройних Сил", html)

    def test_color_paragraph_links_to_product_variant_url(self):
        html = build_landing(self.product)["landing_html"]
        # The Phase 7 path-URL format: /product/<slug>/<color-slug>/.
        self.assertIn(f'/product/{self.product.slug}/{self.variant_black.slug}/', html)
        self.assertIn("Чорний", html)

    def test_admin_override_takes_priority(self):
        self.product.seo_bottom_html = "<p>Custom admin copy.</p>"
        self.product.save()
        result = build_landing(self.product)
        self.assertEqual(result["override_html"], "<p>Custom admin copy.</p>")
        self.assertEqual(result["landing_html"], "")

    def test_fit_code_changes_h2_and_active_paragraph(self):
        ProductFitOption.objects.create(
            product=self.product, code="oversize", label="Оверсайз",
            is_default=False, is_active=True, order=0,
        )
        ProductFitOption.objects.create(
            product=self.product, code="classic", label="Класична",
            is_default=True, is_active=True, order=1,
        )
        html = build_landing(self.product, fit_code="oversize")["landing_html"]
        self.assertIn("Оверсайз", html)
        # Path URL must include the fit segment.
        self.assertIn(f'/product/{self.product.slug}/oversize/', html)


class TopQueriesTests(_Base):

    def test_includes_color_chip_with_variant_url(self):
        items = _top_queries_for_product(self.product)
        labels = [i["label"] for i in items]
        urls = [i["url"] for i in items]
        self.assertTrue(any("Чорний" in lbl.lower() or "чорний" in lbl.lower()
                            for lbl in labels))
        self.assertIn(
            f"/product/{self.product.slug}/{self.variant_black.slug}/",
            urls,
        )

    def test_does_not_include_city_chips(self):
        """Phase 21 (PR-5) — city chips removed (would be keyword-stuffing
        without real city landing pages).
        """
        items = _top_queries_for_product(self.product)
        labels = " | ".join(i["label"] for i in items)
        for city in ("Київ", "Харків", "Львів", "Одеса", "Дніпро"):
            self.assertNotIn(city, labels)

    def test_includes_custom_print_chips(self):
        items = _top_queries_for_product(self.product)
        urls = [i["url"] for i in items]
        self.assertIn("/custom-print/", urls)

    def test_capped_at_14(self):
        # Add 4 more colors → exhaust slot budget.
        for i, name in enumerate(("Синій", "Червоний", "Білий", "Сірий")):
            c = Color.objects.create(name=name, primary_hex="#abc")
            ProductColorVariant.objects.create(
                product=self.product, color=c, order=i + 1, is_default=False,
            )
        items = _top_queries_for_product(self.product)
        self.assertLessEqual(len(items), 14)


class CategoryLayoutReuseTests(_Base):

    def test_reuses_top_filters_block_only(self):
        # top_filters block on the parent category — must surface on the
        # product page.
        block = CategorySeoBlock.objects.create(
            category=self.cat, block_type="top_filters",
            title="Топ фільтри", is_active=True, order=0,
        )
        CategorySeoBlockItem.objects.create(
            block=block, label="Купити чорне худі",
            url="/catalog/hoodie/?color=black", order=0,
        )
        # best_prices block — must NOT appear on product page.
        bp = CategorySeoBlock.objects.create(
            category=self.cat, block_type="best_prices",
            title="Кращі ціни", is_active=True, order=1,
        )
        CategorySeoBlockItem.objects.create(
            block=bp, label="Топ-1", order=0,
        )

        layout = _category_layout_for_product(self.product)
        types = {e["block"].block_type for e in layout["tab_blocks"]}
        self.assertIn("top_filters", types)
        self.assertNotIn("best_prices", types)
        self.assertIsNone(layout["best_prices"])
        self.assertTrue(layout["has_any"])


class TemplateRenderTests(_Base):

    def test_partial_renders_landing_and_top_queries(self):
        from django.template.loader import render_to_string
        landing = build_landing(self.product)
        out = render_to_string(
            "partials/product_seo_landing.html",
            {"product_seo_landing": landing},
        )
        self.assertIn("product-seo-landing", out)
        self.assertIn(self.product.title, out)
        self.assertIn('data-seo-tabs', out)
        # Top queries chip rendered as <a>.
        self.assertIn("seo-tab-link", out)

    def test_partial_empty_when_no_landing_data(self):
        from django.template.loader import render_to_string
        out = render_to_string(
            "partials/product_seo_landing.html",
            {"product_seo_landing": None},
        )
        self.assertNotIn("product-seo-landing", out)
