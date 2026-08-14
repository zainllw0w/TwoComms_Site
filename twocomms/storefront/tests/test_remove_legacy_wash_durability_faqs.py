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


class RemoveLegacyWashDurabilityFaqsTests(TestCase):
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
            title="Legacy wash test",
            slug="legacy-wash-test",
            category=self.category,
            price=1000,
            status="published",
        )

    def _legacy_faq(
        self,
        *,
        answer_suffix="",
        order=1,
        is_active=True,
        question_en="How do I wash the tee without damaging the print?",
    ):
        return ProductFAQ.objects.create(
            product=self.product,
            question="Як прати футболку, щоб принт не зіпсувався?",
            answer=(
                "Виверніть навиворіт, періть при 30 °C у режимі для бавовни "
                "без відбілювачів. Сушіть на повітрі. Прасувати можна з "
                "вивороту або через марлю. DTF-принт витримує 50+ циклів "
                "такого прання."
                + answer_suffix
            ),
            question_uk="Як прати футболку, щоб принт не зіпсувався?",
            answer_uk=(
                "Виверніть навиворіт, періть при 30 °C у режимі для бавовни "
                "без відбілювачів. Сушіть на повітрі. Прасувати можна з "
                "вивороту або через марлю. DTF-принт витримує 50+ циклів "
                "такого прання."
                + answer_suffix
            ),
            question_ru="Как стирать футболку, чтобы принт не испортился?",
            answer_ru=(
                "Выверните наизнанку, стирайте при 30 °C в режиме для хлопка "
                "без отбеливателей. Сушите на воздухе. Гладить можно с "
                "изнанки или через марлю. DTF-принт выдерживает 50+ циклов "
                "такой стирки."
                + answer_suffix
            ),
            question_en=question_en,
            answer_en=(
                "Turn inside out, wash at 30 °C on a cotton cycle without "
                "bleach. Air-dry only. Iron inside out or through cheesecloth. "
                "The DTF print easily survives 50+ wash cycles."
                + answer_suffix
            ),
            order=order,
            is_active=is_active,
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

    def _legacy_faq_for_product(self, product, *, order=1, is_active=True):
        row = self._legacy_faq(order=order, is_active=is_active)
        row.product = product
        row.save(update_fields=["product"])
        return row

    def test_default_mode_reports_only_exact_rows_without_writing(self):
        exact = self._legacy_faq()
        changed = self._legacy_faq(answer_suffix=" Editorial correction.")
        output = StringIO()

        call_command(
            "remove_legacy_wash_durability_faqs",
            "--slug",
            self.product.slug,
            stdout=output,
        )

        self.assertEqual(ProductFAQ.objects.filter(product=self.product).count(), 2)
        self.assertIn("candidate rows: 1", output.getvalue())
        self.assertIn(str(exact.pk), output.getvalue())
        self.assertNotIn(str(changed.pk), output.getvalue())

    def test_reports_confirmed_imported_english_question_signature(self):
        imported = self._legacy_faq(
            question_en="How should I wash the tee so the print stays intact?"
        )
        output = StringIO()

        call_command(
            "remove_legacy_wash_durability_faqs",
            "--slug",
            self.product.slug,
            stdout=output,
        )

        self.assertIn("candidate rows: 1", output.getvalue())
        self.assertIn(str(imported.pk), output.getvalue())

    def test_apply_requires_confirmation_and_backup_path(self):
        self._legacy_faq()
        with self.assertRaises(CommandError):
            call_command("remove_legacy_wash_durability_faqs", "--apply")
        with self.assertRaises(CommandError):
            call_command("remove_legacy_wash_durability_faqs", "--confirm")
        self.assertEqual(ProductFAQ.objects.filter(product=self.product).count(), 1)

    def test_confirmed_apply_writes_backup_before_deleting_exact_row(self):
        row = self._legacy_faq()
        with TemporaryDirectory() as tmp:
            backup = Path(tmp) / "legacy-wash-faq-backup.json"
            output = StringIO()
            call_command(
                "remove_legacy_wash_durability_faqs",
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
            "storefront.management.commands.remove_legacy_wash_durability_faqs",
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
                        "remove_legacy_wash_durability_faqs",
                        "--apply",
                        "--confirm",
                        "--backup-path",
                        str(backup),
                    )
            self.assertFalse(backup.exists())
            self.assertTrue(ProductFAQ.objects.filter(pk=row.pk).exists())

    def test_only_published_standard_order_one_rows_are_candidates(self):
        draft = self._scoped_product(category_slug="tshirts-draft", status="draft")
        other_category = self._scoped_product(category_slug="other-service")
        draft_row = self._legacy_faq_for_product(draft)
        other_row = self._legacy_faq_for_product(other_category)
        wrong_order = self._legacy_faq(order=2)
        inactive = self._legacy_faq(is_active=False)

        output = StringIO()
        call_command("remove_legacy_wash_durability_faqs", stdout=output)

        self.assertIn("candidate rows: 0", output.getvalue())
        self.assertTrue(ProductFAQ.objects.filter(pk=draft_row.pk).exists())
        self.assertTrue(ProductFAQ.objects.filter(pk=other_row.pk).exists())
        self.assertTrue(ProductFAQ.objects.filter(pk=wrong_order.pk).exists())
        self.assertTrue(ProductFAQ.objects.filter(pk=inactive.pk).exists())

    def test_dtf_and_custom_print_category_rows_are_never_candidates(self):
        dtf_product = self._scoped_product(category_slug="dtf")
        custom_product = self._scoped_product(
            category_slug="custom-print", slug="custom-print"
        )
        dtf_row = self._legacy_faq_for_product(dtf_product)
        custom_row = self._legacy_faq_for_product(custom_product)

        output = StringIO()
        call_command("remove_legacy_wash_durability_faqs", stdout=output)

        self.assertIn("candidate rows: 0", output.getvalue())
        self.assertTrue(ProductFAQ.objects.filter(pk=dtf_row.pk).exists())
        self.assertTrue(ProductFAQ.objects.filter(pk=custom_row.pk).exists())

    def test_mysql_table_lock_covers_every_table_used_by_the_scoped_scan(self):
        command_module = __import__(
            "storefront.management.commands.remove_legacy_wash_durability_faqs",
            fromlist=["_mysql_table_lock"],
        )
        cursor = __import__("unittest.mock", fromlist=["Mock"]).Mock()

        with command_module._mysql_table_lock(cursor):
            pass

        first_sql = cursor.execute.call_args_list[0].args[0]
        self.assertIn("storefront_productfaq WRITE", first_sql)
        self.assertIn("storefront_product READ", first_sql)
        self.assertIn("storefront_category READ", first_sql)
        self.assertEqual(cursor.execute.call_args_list[-1].args[0], "UNLOCK TABLES")

    def test_mysql_delete_uses_exact_sql_without_django_delete_collector(self):
        command_module = __import__(
            "storefront.management.commands.remove_legacy_wash_durability_faqs",
            fromlist=["_delete_mysql_candidates"],
        )
        cursor = __import__("unittest.mock", fromlist=["Mock"]).Mock()
        cursor.rowcount = 2

        command_module._delete_mysql_candidates(cursor, [17, 23])

        sql, params = cursor.execute.call_args.args
        self.assertEqual(
            " ".join(sql.split()),
            "DELETE FROM storefront_productfaq "
            "WHERE id IN (%s, %s) AND is_active = %s",
        )
        self.assertEqual(params, [17, 23, True])
