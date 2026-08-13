from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import translation

from storefront.models import Category, Product, ProductFAQ
from storefront.services.product_copy_v2 import build_copy
from storefront.services.product_seo_autofill import (
    _build_main_image_alt,
    _build_seo_title,
    autofill_product,
)


RETIRED_FIELDS = (
    "seo_description",
    "seo_keywords",
    "short_description",
    "full_description",
    "care_instructions",
    "target_audience",
)


class LegacyProductCopyRetirementTests(TestCase):
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
            title="Retired generated copy",
            slug="retired-generated-copy",
            category=self.category,
            price=1000,
            status="published",
        )

    def test_phase_13_5_builder_no_longer_returns_unowned_editorial_claims(self):
        generated = build_copy(self.product)

        for field in RETIRED_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(generated[field], "")
        self.assertEqual(generated["faqs"], [])
        self.assertTrue(generated["seo_title"])

    def test_long_identifier_title_always_uses_uk_source_suffix(self):
        self.product.title = "A very long product title with enough words to exceed the cap"
        self.product.save(update_fields=["title"])

        with translation.override("en"):
            generated = build_copy(self.product)

        self.assertLessEqual(len(generated["seo_title"]), 60)
        self.assertIn("купити", generated["seo_title"])
        self.assertNotIn("buy the", generated["seo_title"])

    def test_long_title_with_em_dash_preserves_uk_suffix(self):
        self.product.title = (
            "A very long product — limited edition title with enough words"
        )
        self.product.save(update_fields=["title"])

        with translation.override("en"):
            generated = build_copy(self.product)

        self.assertLessEqual(len(generated["seo_title"]), 60)
        self.assertTrue(
            generated["seo_title"].endswith(" — купити футболку TwoComms")
        )

    def test_phase_13_autofill_does_not_recreate_retired_fields_or_faqs(self):
        autofill_product(self.product, faq_model=ProductFAQ)
        self.product.refresh_from_db()

        self.assertTrue(self.product.seo_title)
        for field in RETIRED_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(getattr(self.product, field), "")
        self.assertEqual(ProductFAQ.objects.filter(product=self.product).count(), 0)

    def test_autofill_writes_only_raw_uk_identifiers_in_every_active_locale(self):
        for locale in ("uk", "ru", "en"):
            with self.subTest(locale=locale):
                product = Product.objects.create(
                    title=f"Seed {locale}",
                    slug=f"autofill-locale-{locale}",
                    category=self.category,
                    price=1000,
                    status="published",
                )
                Product.objects.filter(pk=product.pk).update(
                    title_uk=f"Українська назва {locale}",
                    title_ru=f"Русское название {locale}",
                    title_en=f"English title {locale}",
                    seo_title_uk="",
                    seo_title_ru="",
                    seo_title_en="",
                    main_image_alt_uk="",
                    main_image_alt_ru="",
                    main_image_alt_en="",
                )
                product.refresh_from_db()

                with translation.override(locale):
                    autofill_product(product, faq_model=ProductFAQ)

                product.refresh_from_db()
                self.assertIn("Українська назва", product.seo_title_uk)
                self.assertIn("Купити", product.seo_title_uk)
                self.assertIn("Українська назва", product.main_image_alt_uk)
                self.assertIn("футболка", product.main_image_alt_uk)
                self.assertEqual(product.seo_title_ru or "", "")
                self.assertEqual(product.seo_title_en or "", "")
                self.assertEqual(product.main_image_alt_ru or "", "")
                self.assertEqual(product.main_image_alt_en or "", "")

    def test_autofill_preserves_manual_ru_en_identifiers_without_hiding_uk_blank(self):
        Product.objects.filter(pk=self.product.pk).update(
            title_uk="Українська назва",
            title_ru="Русское название",
            title_en="English title",
            seo_title_uk="",
            seo_title_ru="Ручной русский SEO title",
            seo_title_en="Manual English SEO title",
            main_image_alt_uk="",
            main_image_alt_ru="Ручной русский alt",
            main_image_alt_en="Manual English alt",
        )
        self.product.refresh_from_db()

        with translation.override("ru"):
            autofill_product(self.product, faq_model=ProductFAQ)

        self.product.refresh_from_db()
        self.assertTrue(self.product.seo_title_uk)
        self.assertTrue(self.product.main_image_alt_uk)
        self.assertEqual(self.product.seo_title_ru, "Ручной русский SEO title")
        self.assertEqual(self.product.seo_title_en, "Manual English SEO title")
        self.assertEqual(self.product.main_image_alt_ru, "Ручной русский alt")
        self.assertEqual(self.product.main_image_alt_en, "Manual English alt")

    def test_generators_skip_product_without_raw_uk_title(self):
        Product.objects.filter(pk=self.product.pk).update(
            title_uk="",
            title_ru="Только русское название",
            title_en="English-only title",
            seo_title_uk="",
            seo_title_ru="",
            seo_title_en="",
            main_image_alt_uk="",
            main_image_alt_ru="",
            main_image_alt_en="",
        )
        self.product.refresh_from_db()

        with translation.override("ru"):
            autofill_product(self.product, faq_model=ProductFAQ)
            generated = build_copy(self.product)
            call_command(
                "recraft_product_seo",
                "--slug",
                self.product.slug,
                "--force",
                stdout=StringIO(),
            )

        self.product.refresh_from_db()
        self.assertEqual(generated["seo_title"], "")
        self.assertEqual(generated["main_image_alt"], "")
        for field in (
            "seo_title_uk",
            "seo_title_ru",
            "seo_title_en",
            "main_image_alt_uk",
            "main_image_alt_ru",
            "main_image_alt_en",
        ):
            with self.subTest(field=field):
                self.assertEqual(getattr(self.product, field) or "", "")

    def test_recraft_does_not_recreate_retired_fields_or_faqs(self):
        call_command(
            "recraft_product_seo",
            "--slug",
            self.product.slug,
            stdout=StringIO(),
        )
        self.product.refresh_from_db()

        for field in RETIRED_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(getattr(self.product, field), "")
        self.assertEqual(ProductFAQ.objects.filter(product=self.product).count(), 0)

    def test_generators_preserve_manual_editorial_fields_and_faq(self):
        manual = {
            "seo_description": "Manual meta description",
            "seo_keywords": "manual keyword",
            "short_description": "Manual card copy",
            "full_description": "Manual full editorial copy",
            "care_instructions": "Manual care policy",
            "target_audience": "Manual audience note",
        }
        for field, value in manual.items():
            setattr(self.product, field, value)
        self.product.save(update_fields=list(manual))
        faq = ProductFAQ.objects.create(
            product=self.product,
            question="Manual FAQ question",
            answer="Manual FAQ answer",
            order=0,
            is_active=True,
        )

        autofill_product(self.product, faq_model=ProductFAQ)
        call_command(
            "recraft_product_seo",
            "--slug",
            self.product.slug,
            "--force",
            stdout=StringIO(),
        )
        call_command(
            "refresh_product_faqs",
            "--slug",
            self.product.slug,
            stdout=StringIO(),
        )

        self.product.refresh_from_db()
        for field, value in manual.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(self.product, field), value)
        faq.refresh_from_db()
        self.assertEqual(faq.question, "Manual FAQ question")
        self.assertEqual(faq.answer, "Manual FAQ answer")

    def test_recraft_force_preserves_manual_title_and_image_alt(self):
        self.product.seo_title = "Manual reviewed title"
        self.product.main_image_alt = "Manual reviewed image description"
        self.product.save(update_fields=["seo_title", "main_image_alt"])

        call_command(
            "recraft_product_seo",
            "--slug",
            self.product.slug,
            "--force",
            stdout=StringIO(),
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.seo_title, "Manual reviewed title")
        self.assertEqual(
            self.product.main_image_alt,
            "Manual reviewed image description",
        )

    def test_recraft_force_writes_only_raw_uk_and_preserves_ru_en(self):
        for locale in ("uk", "ru", "en"):
            with self.subTest(locale=locale):
                product = Product.objects.create(
                    title=f"Seed recraft {locale}",
                    slug=f"recraft-locale-{locale}",
                    category=self.category,
                    price=1000,
                    status="published",
                )
                Product.objects.filter(pk=product.pk).update(
                    title_uk=f"Українська recraft назва {locale}",
                    title_ru=f"Русское recraft название {locale}",
                    title_en=f"English recraft title {locale}",
                    seo_title_uk="",
                    seo_title_ru=f"Manual RU title {locale}",
                    seo_title_en=f"Manual EN title {locale}",
                    main_image_alt_uk="",
                    main_image_alt_ru=f"Manual RU alt {locale}",
                    main_image_alt_en=f"Manual EN alt {locale}",
                )

                with translation.override(locale):
                    call_command(
                        "recraft_product_seo",
                        "--slug",
                        product.slug,
                        "--force",
                        stdout=StringIO(),
                    )

                product.refresh_from_db()
                self.assertIn("Українська recraft назва", product.seo_title_uk)
                self.assertIn("купити футболку", product.seo_title_uk)
                self.assertIn("Українська recraft назва", product.main_image_alt_uk)
                self.assertEqual(product.seo_title_ru, f"Manual RU title {locale}")
                self.assertEqual(product.seo_title_en, f"Manual EN title {locale}")
                self.assertEqual(product.main_image_alt_ru, f"Manual RU alt {locale}")
                self.assertEqual(product.main_image_alt_en, f"Manual EN alt {locale}")

    def test_retired_refresh_reports_noop_without_claiming_rewrites(self):
        output = StringIO()
        call_command(
            "refresh_product_faqs",
            "--slug",
            self.product.slug,
            stdout=output,
        )

        self.assertIn("Retired: no FAQ rows were changed", output.getvalue())
        self.assertIn("FAQs rewritten:   0", output.getvalue())

    def test_refresh_leaves_legacy_care_faq_for_guarded_cleanup(self):
        faq = ProductFAQ.objects.create(
            product=self.product,
            question="Чи можна прати футболку в машинці?",
            answer="Legacy answer awaiting exact-signature cleanup.",
            order=1,
            is_active=True,
        )

        call_command(
            "refresh_product_faqs",
            "--slug",
            self.product.slug,
            stdout=StringIO(),
        )

        faq.refresh_from_db()
        self.assertEqual(faq.question, "Чи можна прати футболку в машинці?")
        self.assertEqual(faq.answer, "Legacy answer awaiting exact-signature cleanup.")

    def test_autofill_and_commands_ignore_nonstandard_product_categories(self):
        custom_category = Category.objects.create(
            name="Custom Print", slug="custom-print", is_active=True
        )
        custom_product = Product.objects.create(
            title="Custom Print boundary",
            slug="custom-print-boundary",
            category=custom_category,
            price=1000,
            status="published",
        )

        autofill_product(custom_product, faq_model=ProductFAQ)
        autofill_output = StringIO()
        call_command("autofill_product_seo", stdout=autofill_output)
        call_command("recraft_product_seo", stdout=StringIO())
        call_command("refresh_product_faqs", stdout=StringIO())
        custom_product.refresh_from_db()

        self.assertEqual(_build_seo_title(custom_product), "")
        self.assertEqual(_build_main_image_alt(custom_product), "")
        self.assertIn("Processed: 1", autofill_output.getvalue())
        self.assertEqual(custom_product.seo_title, "")
        self.assertEqual(custom_product.main_image_alt or "", "")
        for field in RETIRED_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(getattr(custom_product, field), "")
        self.assertEqual(
            ProductFAQ.objects.filter(product=custom_product).count(), 0
        )

    def test_include_drafts_preserves_safe_standard_draft_semantics(self):
        draft = Product.objects.create(
            title="Draft boundary",
            slug="draft-copy-boundary",
            category=self.category,
            price=1000,
            status="draft",
        )

        autofill_product(draft, faq_model=ProductFAQ)
        call_command("autofill_product_seo", "--include-drafts", stdout=StringIO())
        call_command("recraft_product_seo", "--include-drafts", stdout=StringIO())
        call_command("refresh_product_faqs", "--include-drafts", stdout=StringIO())

        draft.refresh_from_db()
        self.assertTrue(draft.seo_title)
        self.assertTrue(draft.main_image_alt)
        for field in RETIRED_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(getattr(draft, field), "")
        self.assertEqual(ProductFAQ.objects.filter(product=draft).count(), 0)
