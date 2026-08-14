from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from storefront.models import Category, Product


class RemoveLegacyWashDurabilityCopyTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Футболки", slug="tshirts", is_active=True
        )
        self.product = Product.objects.create(
            title="Legacy copy test", slug="legacy-copy-test", category=self.category,
            price=1000, status="published",
            full_description_uk=(
                "Принт нанесено методом DTF-друку — насичені кольори, тонкі деталі "
                "та стійкість до 50+ циклів прання при дотриманні правил догляду."
            ),
            full_description_ru=(
                "Принт нанесён методом DTF-печати — насыщенные цвета, тонкие детали "
                "и стойкость к 50+ циклам стирки при соблюдении правил ухода."
            ),
            full_description_en=(
                "The print is applied by DTF printing — saturated colours, fine detail "
                "and a lifespan of 50+ wash cycles when care instructions are followed."
            ),
        )

    def test_default_mode_reports_exact_product_fields_without_writing(self):
        output = StringIO()
        call_command("remove_legacy_wash_durability_copy", stdout=output)
        self.product.refresh_from_db()
        self.assertIn("candidate products: 1", output.getvalue())
        self.assertIn(str(self.product.pk), output.getvalue())
        self.assertIn("50+", self.product.full_description_ru)

    def test_apply_requires_confirmation_and_backup(self):
        with self.assertRaises(CommandError):
            call_command("remove_legacy_wash_durability_copy", "--apply")
        with self.assertRaises(CommandError):
            call_command("remove_legacy_wash_durability_copy", "--confirm")

    def test_confirmed_apply_replaces_only_known_sentence_and_writes_backup(self):
        with TemporaryDirectory() as tmp:
            backup = Path(tmp) / "copy.json"
            output = StringIO()
            call_command(
                "remove_legacy_wash_durability_copy", "--apply", "--confirm",
                "--backup-path", str(backup), stdout=output,
            )
            self.product.refresh_from_db()
            self.assertNotIn("50+", self.product.full_description_uk)
            self.assertNotIn("50+", self.product.full_description_ru)
            self.assertNotIn("50+", self.product.full_description_en)
            self.assertIn("DTF-друку", self.product.full_description_uk)
            payload = json.loads(backup.read_text(encoding="utf-8"))
            self.assertEqual(payload["candidate_ids"], [self.product.pk])
            self.assertIn("full_description_ru", payload["rows"][0]["fields"])
            self.assertIn("replaced products: 1", output.getvalue())

    def test_edited_or_nonstandard_products_are_not_candidates(self):
        edited = Product.objects.create(
            title="Edited", slug="edited-copy", category=self.category,
            price=1000, status="published",
            full_description_ru="Проверенная редакция: 50+ не является обещанием.",
        )
        other_category = Category.objects.create(
            name="Other", slug="other-service", is_active=True
        )
        other = Product.objects.create(
            title="Other", slug="other-copy", category=other_category,
            price=1000, status="published", full_description_ru=self.product.full_description_ru,
        )
        output = StringIO()
        call_command("remove_legacy_wash_durability_copy", stdout=output)
        self.assertIn("candidate products: 1", output.getvalue())
        edited.refresh_from_db()
        other.refresh_from_db()
        self.assertIn("50+", edited.full_description_ru)
        self.assertIn("50+", other.full_description_ru)

    def test_apply_aborts_on_stale_fingerprint(self):
        module = __import__(
            "storefront.management.commands.remove_legacy_wash_durability_copy",
            fromlist=["_scan"],
        )
        real_scan = module._scan
        calls = 0

        def stale(rows):
            nonlocal calls
            if calls == 1:
                Product.objects.filter(pk=self.product.pk).update(
                    full_description_ru="Changed by editor"
                )
                for row in rows:
                    if row.pk == self.product.pk:
                        row.full_description_ru = "Changed by editor"
            calls += 1
            return real_scan(rows)

        with TemporaryDirectory() as tmp:
            backup = Path(tmp) / "stale.json"
            with __import__("unittest.mock", fromlist=["patch"]).patch.object(
                module, "_scan", side_effect=stale
            ):
                with self.assertRaises(CommandError):
                    call_command(
                        "remove_legacy_wash_durability_copy", "--apply", "--confirm",
                        "--backup-path", str(backup),
                    )
            self.assertFalse(backup.exists())

    def test_import_sources_do_not_reintroduce_retired_wash_durability_claims(self):
        source_paths = (
            Path(settings.BASE_DIR) / "storefront/services/product_copy_v2.py",
            Path(settings.BASE_DIR) / "data/translations/_constants.py",
            Path(settings.BASE_DIR) / "data/translations/_faq.py",
            Path(settings.BASE_DIR) / "data/product_translations.json",
        )
        source_text = "\n".join(
            path.read_text(encoding="utf-8") for path in source_paths
        )
        retired_markers = (
            "стійкість до 50+ циклів прання при дотриманні правил догляду.",
            "стойкость к 50+ циклам стирки при соблюдении правил ухода.",
            "a lifespan of 50+ wash cycles when care instructions are followed.",
            "DTF-принт витримує 50+ циклів такого прання.",
            "DTF-принт выдерживает 50+ циклов такой стирки.",
            "The DTF print easily survives 50+ wash cycles.",
        )
        for marker in retired_markers:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source_text)

    def test_imported_care_faq_answers_have_no_trailing_whitespace(self):
        translation_path = Path(settings.BASE_DIR) / "data/product_translations.json"
        payload = json.loads(translation_path.read_text(encoding="utf-8"))
        care_answers = [
            values[locale]
            for item in payload["by_id"]["faq"].values()
            if item.get("question", {}).get("en")
            == "How should I wash the tee so the print stays intact?"
            for locale, values in (("ru", item["answer"]), ("en", item["answer"]))
        ]

        self.assertTrue(care_answers)
        for answer in care_answers:
            with self.subTest(answer=answer):
                self.assertEqual(answer, answer.rstrip())
