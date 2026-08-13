from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from storefront.models import Category, Product, ProductFAQ


class RemoveLegacyDeliveryFaqsTests(TestCase):
    def setUp(self):
        super().setUp()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            mocked = patch(target)
            self.addCleanup(mocked.stop)
            mocked.start()
        self.category = Category.objects.create(
            name="Футболки", slug="tshirts", is_active=True
        )
        self.product = Product.objects.create(
            title="Legacy delivery test",
            slug="legacy-delivery-test",
            category=self.category,
            price=1000,
            status="published",
        )

    def _legacy_faq(self, *, answer_suffix="", order=2):
        return ProductFAQ.objects.create(
            product=self.product,
            question="Як швидко доставимо футболку?",
            answer=(
                "Новою Поштою — 1–3 робочі дні по всій Україні. "
                "Відділення/поштомат від 85 ₴, кур'єр від 180 ₴. "
                "Замовлення до 14:00 відправляємо того ж дня."
                + answer_suffix
            ),
            question_uk="Як швидко доставимо футболку?",
            answer_uk=(
                "Новою Поштою — 1–3 робочі дні по всій Україні. "
                "Відділення/поштомат від 85 ₴, кур'єр від 180 ₴. "
                "Замовлення до 14:00 відправляємо того ж дня."
                + answer_suffix
            ),
            question_ru="Как быстро доставим футболку?",
            answer_ru=(
                "Новой Почтой — 1–3 рабочих дня по всей Украине. "
                "Отделение/почтомат от 85 ₴, курьер от 180 ₴. "
                "Заказы до 14:00 отправляем в тот же день."
                + answer_suffix
            ),
            question_en="How fast will the tee arrive?",
            answer_en=(
                "Nova Poshta covers all of Ukraine in 1–3 business days. "
                "Branch/parcel locker from 85 UAH, courier from 180 UAH. "
                "Orders placed before 2 PM ship the same day."
                + answer_suffix
            ),
            order=order,
            is_active=True,
        )

    def _scoped_product(self, *, category_slug, status="published", slug=None):
        category = Category.objects.create(
            name=category_slug,
            slug=category_slug,
            is_active=True,
        )
        return Product.objects.create(
            title=f"{category_slug} test",
            slug=slug or f"{category_slug}-test",
            category=category,
            price=1000,
            status=status,
        )

    def _legacy_faq_for_product(self, product, *, order=2, is_active=True):
        row = self._legacy_faq(order=order)
        row.product = product
        row.order = order
        row.is_active = is_active
        row.save(update_fields=["product", "order", "is_active"])
        return row

    def test_default_mode_reports_only_exact_legacy_rows_without_writing(self):
        exact = self._legacy_faq()
        changed = self._legacy_faq(answer_suffix=" Editorial correction.")
        output = StringIO()

        call_command(
            "remove_legacy_delivery_faqs",
            "--slug",
            self.product.slug,
            stdout=output,
        )

        self.assertEqual(ProductFAQ.objects.filter(product=self.product).count(), 2)
        self.assertIn(f"candidate rows: 1", output.getvalue())
        self.assertIn(str(exact.pk), output.getvalue())
        self.assertNotIn(str(changed.pk), output.getvalue())

    def test_apply_requires_confirmation_and_backup_path(self):
        self._legacy_faq()
        with self.assertRaises(CommandError):
            call_command("remove_legacy_delivery_faqs", "--apply")
        with self.assertRaises(CommandError):
            call_command("remove_legacy_delivery_faqs", "--confirm")
        self.assertEqual(ProductFAQ.objects.filter(product=self.product).count(), 1)

    def test_confirmed_apply_writes_backup_before_deleting_exact_row(self):
        row = self._legacy_faq()
        with TemporaryDirectory() as tmp:
            backup = Path(tmp) / "legacy-delivery-faq-backup.json"
            output = StringIO()
            call_command(
                "remove_legacy_delivery_faqs",
                "--apply",
                "--confirm",
                "--backup-path",
                str(backup),
                stdout=output,
            )

            payload = json.loads(backup.read_text(encoding="utf-8"))
            self.assertEqual(payload["candidate_ids"], [row.pk])
            self.assertEqual(payload["rows"][0]["id"], row.pk)
            self.assertFalse(ProductFAQ.objects.filter(pk=row.pk).exists())
            self.assertIn("deleted rows: 1", output.getvalue())

    def test_apply_aborts_when_exact_row_changes_after_scan(self):
        row = self._legacy_faq()
        command_module = __import__(
            "storefront.management.commands.remove_legacy_delivery_faqs",
            fromlist=["_scan_rows"],
        )
        real_scan = command_module._scan_rows
        calls = 0

        def stale_scan(rows):
            nonlocal calls
            if calls == 1:
                ProductFAQ.objects.filter(pk=row.pk).update(answer_en="changed")
                for item in rows:
                    if item.pk == row.pk:
                        item.answer_en = "changed"
            calls += 1
            return real_scan(rows)

        with TemporaryDirectory() as tmp:
            backup = Path(tmp) / "should-not-exist.json"
            with patch.object(command_module, "_scan_rows", side_effect=stale_scan):
                with self.assertRaises(CommandError):
                    call_command(
                        "remove_legacy_delivery_faqs",
                        "--apply",
                        "--confirm",
                        "--backup-path",
                        str(backup),
                    )
            self.assertFalse(backup.exists())
            self.assertTrue(ProductFAQ.objects.filter(pk=row.pk).exists())

    def test_only_published_standard_order_two_rows_are_candidates(self):
        draft = self._scoped_product(category_slug="tshirts-draft", status="draft")
        other_category = self._scoped_product(category_slug="other-service")
        draft_row = self._legacy_faq_for_product(draft)
        other_row = self._legacy_faq_for_product(other_category)
        wrong_order = self._legacy_faq(order=1)
        inactive = self._legacy_faq()
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        custom_faq = ProductFAQ.objects.create(
            product=self.product,
            question="Можно ли заказать индивидуальный дизайн?",
            answer="Да, через Custom Print.",
            question_uk="Можно ли заказать индивидуальный дизайн?",
            answer_uk="Да, через Custom Print.",
            order=2,
            is_active=True,
        )

        output = StringIO()
        call_command("remove_legacy_delivery_faqs", stdout=output)

        self.assertIn("candidate rows: 0", output.getvalue())
        self.assertTrue(ProductFAQ.objects.filter(pk=draft_row.pk).exists())
        self.assertTrue(ProductFAQ.objects.filter(pk=other_row.pk).exists())
        self.assertTrue(ProductFAQ.objects.filter(pk=wrong_order.pk).exists())
        self.assertTrue(ProductFAQ.objects.filter(pk=inactive.pk).exists())
        self.assertTrue(ProductFAQ.objects.filter(pk=custom_faq.pk).exists())

    def test_dtf_and_custom_print_category_rows_are_never_candidates(self):
        dtf_product = self._scoped_product(category_slug="dtf")
        custom_product = self._scoped_product(
            category_slug="custom-print", slug="custom-print"
        )
        dtf_row = self._legacy_faq_for_product(dtf_product)
        custom_row = self._legacy_faq_for_product(custom_product)

        output = StringIO()
        call_command("remove_legacy_delivery_faqs", stdout=output)

        self.assertIn("candidate rows: 0", output.getvalue())
        self.assertTrue(ProductFAQ.objects.filter(pk=dtf_row.pk).exists())
        self.assertTrue(ProductFAQ.objects.filter(pk=custom_row.pk).exists())
