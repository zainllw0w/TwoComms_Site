"""Tests for the ``translate_products`` management command."""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from storefront.models import Category, Product, ProductFAQ, ProductStatus


class TranslateProductsCommandTests(TestCase):
    def setUp(self):
        self.feed_task_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            return_value=None,
        )
        self.feed_task_patcher.start()
        self.addCleanup(self.feed_task_patcher.stop)

        self.category = Category.objects.create(
            name="Худі",
            slug="hoodie-tp",
            description="Тестовий опис худі",
        )
        # Make sure *_uk mirrors are populated like prod data.
        self.category.name_uk = self.category.name
        self.category.description_uk = self.category.description
        self.category.save()

        self.product = Product.objects.create(
            title="Тестовий принт",
            slug="test-print-tp",
            category=self.category,
            price=1500,
            status=ProductStatus.PUBLISHED,
            short_description="Короткий опис",
        )
        self.product.title_uk = self.product.title
        self.product.short_description_uk = self.product.short_description
        self.product.save()

        self.faq = ProductFAQ.objects.create(
            product=self.product,
            question="Як прати?",
            answer="Машинне прання при 30°C.",
            order=0,
        )
        self.faq.question_uk = self.faq.question
        self.faq.answer_uk = self.faq.answer
        self.faq.save()

    # ------------------------------------------------------------------
    def test_dry_run_does_not_persist(self):
        out = StringIO()
        call_command(
            "translate_products",
            "--dry-run",
            "--mirror-fallback",
            stdout=out,
        )
        self.product.refresh_from_db()
        self.assertFalse(self.product.title_ru)
        self.assertIn("would fill", out.getvalue())

    def test_mirror_fallback_fills_ru_and_en(self):
        out = StringIO()
        call_command(
            "translate_products",
            "--mirror-fallback",
            stdout=out,
        )
        self.product.refresh_from_db()
        self.category.refresh_from_db()
        self.faq.refresh_from_db()

        # Mirror fallback simply copies UA into RU/EN columns.
        self.assertEqual(self.product.title_ru, "Тестовий принт")
        self.assertEqual(self.product.title_en, "Тестовий принт")
        self.assertEqual(self.category.name_ru, "Худі")
        self.assertEqual(self.faq.question_ru, "Як прати?")
        self.assertIn("filled", out.getvalue())

    def test_force_reruns_existing_targets(self):
        # Pre-fill RU/EN with a stale value
        self.product.title_ru = "Старе"
        self.product.title_en = "Stale"
        self.product.save()

        out = StringIO()
        call_command(
            "translate_products",
            "--mirror-fallback",
            "--force",
            "--models",
            "product",
            "--ids",
            str(self.product.pk),
            stdout=out,
        )
        self.product.refresh_from_db()
        # Mirror fallback overwrites with UA source.
        self.assertEqual(self.product.title_ru, "Тестовий принт")
        self.assertEqual(self.product.title_en, "Тестовий принт")

    def test_target_lang_filter(self):
        call_command(
            "translate_products",
            "--mirror-fallback",
            "--target-langs",
            "ru",
            "--models",
            "product",
            "--ids",
            str(self.product.pk),
            stdout=StringIO(),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.title_ru, "Тестовий принт")
        self.assertFalse(self.product.title_en)

    def test_unknown_model_raises(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                "translate_products",
                "--mirror-fallback",
                "--models",
                "unknown",
                stdout=StringIO(),
            )
