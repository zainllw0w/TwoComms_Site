"""Phase 13 — tests for ``services.product_seo_autofill``."""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.cache import cache, caches
from django.core.management import call_command
from django.test import TestCase

from storefront.models import Category, Product, ProductFAQ
from storefront.services.product_seo_autofill import (
    AutofillReport,
    autofill_product,
    autofill_queryset,
)


class _Base(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        merchant = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        indexnow = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant.stop)
        self.addCleanup(indexnow.stop)
        merchant.start()
        indexnow.start()

        self.cat_h = Category.objects.create(
            name="Худі", slug="hoodie", is_active=True,
        )
        self.cat_t = Category.objects.create(
            name="Футболки", slug="tshirts", is_active=True,
        )

    def _product(self, **kw):
        defaults = dict(title="HD Reality Bends Future",
                        slug="hd-reality-bends-future",
                        category=self.cat_h, price=1490, status="published")
        defaults.update(kw)
        return Product.objects.create(**defaults)


class AutofillCoreTests(_Base):

    def test_fills_all_empty_seo_fields(self):
        p = self._product()
        report = autofill_product(p, faq_model=ProductFAQ)
        p.refresh_from_db()

        self.assertIn("HD Reality Bends Future", p.seo_title)
        self.assertIn("TwoComms", p.seo_title)
        self.assertLessEqual(len(p.seo_title), 160)

        self.assertTrue(p.seo_description)
        self.assertLessEqual(len(p.seo_description), 320)

        self.assertTrue(p.seo_keywords)
        self.assertLessEqual(len(p.seo_keywords), 300)
        self.assertIn("худі", p.seo_keywords)
        self.assertIn("ЗСУ", p.seo_keywords)

        self.assertTrue(p.main_image_alt)
        self.assertLessEqual(len(p.main_image_alt), 200)

        self.assertTrue(p.short_description)
        self.assertLessEqual(len(p.short_description), 300)

        self.assertTrue(p.care_instructions)
        self.assertTrue(p.target_audience)
        self.assertTrue(p.full_description)
        self.assertIn("<p>", p.full_description)
        self.assertIn("DTF", p.full_description)

        self.assertEqual(report.products_seen, 1)
        self.assertEqual(report.products_changed, 1)

    def test_does_not_overwrite_populated_fields(self):
        p = self._product(seo_title="MANUALLY SET TITLE",
                          seo_description="MANUAL DESC",
                          short_description="manual short")
        autofill_product(p, faq_model=ProductFAQ)
        p.refresh_from_db()
        self.assertEqual(p.seo_title, "MANUALLY SET TITLE")
        self.assertEqual(p.seo_description, "MANUAL DESC")
        self.assertEqual(p.short_description, "manual short")
        # But other empty fields ARE filled.
        self.assertTrue(p.main_image_alt)
        self.assertTrue(p.care_instructions)

    def test_creates_5_faqs_when_none_exist(self):
        p = self._product()
        autofill_product(p, faq_model=ProductFAQ)
        faqs = list(ProductFAQ.objects.filter(product=p).order_by("order"))
        self.assertEqual(len(faqs), 5)
        # Standard FAQ shape: question + answer + order + is_active.
        self.assertEqual(faqs[0].order, 0)
        self.assertTrue(faqs[0].is_active)
        # Category-specific phrasing.
        questions = " ".join(f.question for f in faqs)
        self.assertIn("худі", questions.lower())

    def test_does_not_duplicate_faqs_on_second_run(self):
        p = self._product()
        autofill_product(p, faq_model=ProductFAQ)
        autofill_product(p, faq_model=ProductFAQ)
        self.assertEqual(ProductFAQ.objects.filter(product=p).count(), 5)

    def test_category_specific_phrasing_for_tshirts(self):
        p = self._product(title="TC Tryzub Black Print",
                          slug="tc-tryzub-print",
                          category=self.cat_t)
        autofill_product(p, faq_model=ProductFAQ)
        p.refresh_from_db()
        self.assertIn("футболка", p.seo_keywords.lower())
        questions = " ".join(
            f.question for f in ProductFAQ.objects.filter(product=p)
        )
        self.assertIn("футболк", questions.lower())  # футболку / футболки

    def test_dry_run_does_not_write(self):
        p = self._product()
        report = autofill_product(p, faq_model=ProductFAQ, dry_run=True)
        # In-memory object IS mutated (caller may want to inspect).
        self.assertTrue(p.seo_title)
        # But DB is untouched.
        p.refresh_from_db()
        self.assertFalse(p.seo_title)
        self.assertFalse(p.seo_description)
        self.assertEqual(ProductFAQ.objects.filter(product=p).count(), 0)
        self.assertEqual(report.faqs_created, 5)

    def test_queryset_runner_aggregates_report(self):
        for i in range(3):
            self._product(title=f"P{i}", slug=f"p{i}")
        qs = Product.objects.filter(status="published")
        report = autofill_queryset(qs, faq_model=ProductFAQ)
        self.assertEqual(report.products_seen, 3)
        self.assertEqual(report.products_changed, 3)
        self.assertEqual(report.faqs_created, 15)
        self.assertEqual(report.fields_filled["seo_title"], 3)


class AutofillCommandTests(_Base):

    def test_command_processes_only_published_by_default(self):
        self._product(slug="published-1")
        self._product(slug="draft-1", status="draft")
        out = StringIO()
        call_command("autofill_product_seo", stdout=out)
        out_text = out.getvalue()
        self.assertIn("Processed: 1", out_text)
        self.assertIn("Changed:   1", out_text)
        # Draft must remain blank.
        draft = Product.objects.get(slug="draft-1")
        self.assertFalse(draft.seo_title)

    def test_command_include_drafts_processes_all(self):
        self._product(slug="published-1")
        self._product(slug="draft-1", status="draft")
        out = StringIO()
        call_command("autofill_product_seo", "--include-drafts", stdout=out)
        self.assertIn("Processed: 2", out.getvalue())

    def test_command_dry_run_does_not_write(self):
        self._product(slug="p")
        out = StringIO()
        call_command("autofill_product_seo", "--dry-run", stdout=out)
        self.assertIn("Dry-run", out.getvalue())
        self.assertEqual(ProductFAQ.objects.count(), 0)
        self.assertFalse(Product.objects.get(slug="p").seo_title)

    def test_command_slug_filter(self):
        self._product(slug="want")
        self._product(slug="skip")
        out = StringIO()
        call_command("autofill_product_seo", "--slug", "want", stdout=out)
        self.assertIn("Processed: 1", out.getvalue())
        self.assertTrue(Product.objects.get(slug="want").seo_title)
        self.assertFalse(Product.objects.get(slug="skip").seo_title)
