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

    def _legacy_faq(self, *, answer_suffix=""):
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
            order=2,
            is_active=True,
        )

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
