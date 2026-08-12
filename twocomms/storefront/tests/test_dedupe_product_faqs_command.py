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


class DedupeProductFaqsCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        self.merchant_patch = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        self.indexnow_patch = patch("storefront.signals.enqueue_indexnow_urls")
        self.merchant_patch.start()
        self.indexnow_patch.start()
        self.addCleanup(self.merchant_patch.stop)
        self.addCleanup(self.indexnow_patch.stop)

        category = Category.objects.create(
            name="Футболки",
            slug="faq-dedupe-test",
            is_active=True,
        )
        self.product = Product.objects.create(
            title="FAQ dedupe test",
            slug="faq-dedupe-test-product",
            category=category,
            price=1000,
            status="published",
        )

    def _faq(self, *, order, question, answer, suffix=""):
        return ProductFAQ.objects.create(
            product=self.product,
            question=question,
            answer=answer,
            question_uk=question,
            answer_uk=answer,
            question_ru=f"RU {question}{suffix}",
            answer_ru=f"RU {answer}{suffix}",
            question_en=f"EN {question}{suffix}",
            answer_en=f"EN {answer}{suffix}",
            order=order,
            is_active=True,
        )

    def test_default_mode_reports_exact_candidates_without_writing(self):
        keeper = self._faq(order=2, question="Як прати?", answer="При 30 °C.")
        duplicate = self._faq(
            order=8,
            question="  Як   прати? ",
            answer="При 30 °C.",
        )
        unique = self._faq(order=9, question="Як обрати розмір?", answer="За сіткою.")
        output = StringIO()

        call_command("dedupe_product_faqs", stdout=output)

        self.assertEqual(ProductFAQ.objects.filter(product=self.product).count(), 3)
        self.assertIn("dry-run", output.getvalue().lower())
        self.assertIn("candidate rows: 1", output.getvalue().lower())
        self.assertIn(str(keeper.pk), output.getvalue())
        self.assertIn(str(duplicate.pk), output.getvalue())
        self.assertNotIn(str(unique.pk), output.getvalue())

    def test_apply_requires_explicit_confirmation_and_backup_path(self):
        self._faq(order=0, question="Q", answer="A")
        with self.assertRaises(CommandError):
            call_command("dedupe_product_faqs", "--apply")

        with self.assertRaises(CommandError):
            call_command("dedupe_product_faqs", "--confirm")

        self.assertEqual(ProductFAQ.objects.filter(product=self.product).count(), 1)

    def test_confirmed_apply_writes_json_backup_before_deleting_candidates(self):
        keeper = self._faq(order=0, question="Як прати?", answer="При 30 °C.")
        duplicate = self._faq(order=4, question="Як прати?", answer="При 30 °C.")
        with TemporaryDirectory() as tmp:
            backup = Path(tmp) / "faq-backup.json"
            output = StringIO()

            call_command(
                "dedupe_product_faqs",
                "--apply",
                "--confirm",
                "--backup-path",
                str(backup),
                stdout=output,
            )

            self.assertTrue(backup.exists())
            payload = json.loads(backup.read_text(encoding="utf-8"))
            self.assertEqual(payload["candidate_ids"], [duplicate.pk])
            self.assertEqual(payload["clusters"][0]["keeper_id"], keeper.pk)
            self.assertEqual(payload["rows"][0]["id"], duplicate.pk)
            self.assertTrue(ProductFAQ.objects.filter(pk=keeper.pk).exists())
            self.assertFalse(ProductFAQ.objects.filter(pk=duplicate.pk).exists())
            self.assertIn("deleted rows: 1", output.getvalue().lower())

    def test_conflicting_answers_are_reported_and_never_deleted(self):
        keeper = self._faq(order=0, question="Як прати?", answer="При 30 °C.")
        duplicate = self._faq(order=1, question="Як прати?", answer="При 30 °C.")
        conflict = self._faq(order=2, question="Як прати?", answer="Лише вручну.", suffix=" conflict")
        output = StringIO()

        call_command("dedupe_product_faqs", stdout=output)

        self.assertEqual(ProductFAQ.objects.filter(product=self.product).count(), 3)
        self.assertIn("conflict", output.getvalue().lower())
        self.assertIn(str(conflict.pk), output.getvalue())
        self.assertNotIn("candidate rows: 1", output.getvalue().lower())
        self.assertTrue(ProductFAQ.objects.filter(pk=keeper.pk).exists())
        self.assertTrue(ProductFAQ.objects.filter(pk=duplicate.pk).exists())

    def test_apply_aborts_when_rows_change_after_initial_scan(self):
        keeper = self._faq(order=0, question="Як прати?", answer="При 30 °C.")
        duplicate = self._faq(order=1, question="Як прати?", answer="При 30 °C.")
        command_module = __import__(
            "storefront.management.commands.dedupe_product_faqs",
            fromlist=["_scan_rows"],
        )
        real_scan = command_module._scan_rows
        calls = 0

        def scan_with_stale_update(rows):
            nonlocal calls
            if calls == 1:
                ProductFAQ.objects.filter(pk=keeper.pk).update(answer_en="changed")
                for row in rows:
                    if row.pk == keeper.pk:
                        row.answer_en = "changed"
            calls += 1
            return real_scan(rows)

        with TemporaryDirectory() as tmp:
            backup = Path(tmp) / "should-not-exist.json"
            with patch.object(command_module, "_scan_rows", side_effect=scan_with_stale_update):
                with self.assertRaises(CommandError):
                    call_command(
                        "dedupe_product_faqs",
                        "--apply",
                        "--confirm",
                        "--backup-path",
                        str(backup),
                    )

            self.assertFalse(backup.exists())
            self.assertTrue(ProductFAQ.objects.filter(pk=keeper.pk).exists())
            self.assertTrue(ProductFAQ.objects.filter(pk=duplicate.pk).exists())
