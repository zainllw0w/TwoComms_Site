"""Phase 13.5 — tests for plain-text theme-aware recraft."""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.cache import cache, caches
from django.core.management import call_command
from django.test import TestCase

from storefront.models import Category, Product, ProductFAQ
from storefront.services.product_copy_v2 import (
    build_copy,
    get_theme_for_product,
    looks_like_phase13_autofill,
    looks_like_phase13_faq,
)


class _Base(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        for patch_target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            p = patch(patch_target)
            self.addCleanup(p.stop)
            p.start()

        self.cat_h = Category.objects.create(name="Худі", slug="hoodie", is_active=True)
        self.cat_t = Category.objects.create(name="Футболки", slug="tshirts", is_active=True)
        self.cat_l = Category.objects.create(name="Лонгсліви", slug="long-sleeve", is_active=True)

    def _product(self, pk, **kw):
        defaults = dict(id=pk, title="Test", slug=f"p-{pk}", category=self.cat_t,
                        price=1000, status="published")
        defaults.update(kw)
        return Product.objects.create(**defaults)


class CopyBuilderTests(_Base):

    def test_reality_bends_theme_unique_intro(self):
        p = self._product(pk=102, category=self.cat_h,
                          title='Худі TWOCOMMS "Reality Bends"')
        copy = build_copy(p)
        self.assertIn("Reality Bends", copy["full_description"])
        self.assertIn("cyberpunk", copy["full_description"].lower())
        self.assertIn("Future 2026", copy["full_description"])
        # Plain text — no HTML tags.
        for f in ("full_description", "care_instructions", "target_audience", "short_description"):
            self.assertNotIn("<p>", copy[f])
            self.assertNotIn("<h3>", copy[f])
            self.assertNotIn("<ul>", copy[f])
            self.assertNotIn("<li>", copy[f])

    def test_kharkiv_theme_different_from_kha_edition(self):
        p1 = self._product(pk=19, category=self.cat_t,
                           title='Футболка "Харківська Область"')
        p2 = self._product(pk=40, category=self.cat_t,
                           title='Футболка "Харків Edition"')
        c1 = build_copy(p1)
        c2 = build_copy(p2)
        self.assertNotEqual(c1["full_description"], c2["full_description"])
        self.assertIn("Харківська Область", c1["full_description"])
        self.assertIn("Харків Edition", c2["full_description"])

    def test_faqs_first_is_theme_specific(self):
        p = self._product(pk=19, category=self.cat_t,
                          title='Футболка "Харківська Область"')
        copy = build_copy(p)
        first_q = copy["faqs"][0][0]
        self.assertIn("Харківська Область", first_q)
        # Delivery policy belongs to the canonical /delivery/ page. The
        # product generator keeps only theme, size, care and custom-print
        # questions whose answers are useful in the product context.
        self.assertEqual(len(copy["faqs"]), 4)
        self.assertFalse(any("достав" in q.lower() for q, _ in copy["faqs"]))

    def test_fallback_for_unmapped_product(self):
        p = self._product(pk=99999, category=self.cat_t,
                          title="Unknown Theme Product")
        self.assertIsNone(get_theme_for_product(p))
        copy = build_copy(p)
        # Fallback copy still produces all fields.
        self.assertTrue(copy["seo_title"])
        self.assertTrue(copy["full_description"])
        self.assertEqual(len(copy["faqs"]), 4)

    def test_delivery_policy_is_not_generated_for_standard_garments(self):
        products = (
            self._product(pk=99101, category=self.cat_t, title="Test T-shirt"),
            self._product(pk=99102, category=self.cat_h, title="Test Hoodie"),
            self._product(pk=99103, category=self.cat_l, title="Test Longsleeve"),
        )

        for product in products:
            rendered = " ".join(
                text for pair in build_copy(product)["faqs"] for text in pair
            )
            with self.subTest(category=product.category.slug):
                self.assertNotIn("1–3 робоч", rendered)
                self.assertNotIn("від 85", rendered)
                self.assertNotIn("від 180", rendered)
                self.assertNotIn("до 14:00", rendered)

    def test_category_labels_used(self):
        p_h = self._product(pk=32, category=self.cat_h,
                            title='Худі "Lord Of The Lending"')
        p_t = self._product(pk=31, category=self.cat_t,
                            title='Футболка "Lord Of The Lending"')
        p_l = self._product(pk=33, category=self.cat_l,
                            title='Лонгслів "Lord Of The Lending"')
        self.assertIn("худі", build_copy(p_h)["faqs"][1][0].lower())
        self.assertIn("футболк", build_copy(p_t)["faqs"][1][0].lower())
        self.assertIn("лонгслів", build_copy(p_l)["faqs"][1][0].lower())

    def test_seo_lengths_respected(self):
        p = self._product(pk=102, category=self.cat_h,
                          title='Худі TWOCOMMS "Reality Bends"')
        c = build_copy(p)
        self.assertLessEqual(len(c["seo_title"]), 160)
        self.assertLessEqual(len(c["seo_description"]), 320)
        self.assertLessEqual(len(c["seo_keywords"]), 300)
        self.assertLessEqual(len(c["main_image_alt"]), 200)
        self.assertLessEqual(len(c["short_description"]), 300)


class SignatureDetectorTests(_Base):

    def test_detects_phase13_full_description(self):
        val = ('<p><strong>Хто</strong> — це авторський худі TwoComms у '
               'мілітарно-streetwear ДНК. Виготовлений</p>')
        self.assertTrue(looks_like_phase13_autofill("full_description", val))

    def test_not_flagging_manual_html(self):
        val = "<p>Manual editorial description with custom HTML</p>"
        self.assertFalse(looks_like_phase13_autofill("full_description", val))

    def test_detects_phase13_care(self):
        val = ("Прання при 30 °C у режимі для бавовни, без агресивних "
               "відбілювачів. Сушити природним способом.")
        self.assertTrue(looks_like_phase13_autofill("care_instructions", val))

    def test_detects_phase13_faq(self):
        self.assertTrue(looks_like_phase13_faq("Як обрати розмір худі?"))
        self.assertTrue(looks_like_phase13_faq("Чи можна прати худі в машинці?"))
        self.assertFalse(looks_like_phase13_faq("Що означає принт Reality Bends?"))


class RecraftCommandTests(_Base):

    def test_recraft_preserves_existing_faqs_while_updating_owned_fields(self):
        # Product in kharkiv_district theme.
        p = self._product(pk=19, category=self.cat_t,
                          title='Футболка "Харківська Область"',
                          care_instructions=(
                              "Прання при 30 °C у режимі для бавовни, без агресивних "
                              "відбілювачів. Сушити природним способом, без сушильної "
                              "машини."),
                          short_description="Custom editorial text — must be preserved!")
        # Mix of phase13 + custom FAQs.
        ProductFAQ.objects.create(product=p, question="Як обрати розмір футболки?",
                                  answer="phase13 answer", order=0, is_active=True)
        ProductFAQ.objects.create(product=p, question="Custom editorial FAQ kept intact?",
                                  answer="yes", order=1, is_active=True)

        out = StringIO()
        call_command("recraft_product_seo", "--slug", "p-19", stdout=out)

        p.refresh_from_db()
        # phase13 care overwritten with the v2 plain-text; custom short_description kept.
        self.assertTrue(p.care_instructions.startswith("Прати при 30"))
        self.assertNotIn("у режимі для бавовни, без агресивних", p.care_instructions)
        self.assertEqual(p.short_description, "Custom editorial text — must be preserved!")

        # Existing FAQ data is intentionally left for the guarded cleanup.
        qs = list(ProductFAQ.objects.filter(product=p).order_by("order"))
        questions = [f.question for f in qs]
        self.assertIn("Custom editorial FAQ kept intact?", questions)
        self.assertIn("Як обрати розмір футболки?", questions)
        self.assertEqual(len(qs), 2)
        self.assertIn("FAQs created: 0 (kept 2 existing)", out.getvalue())

    def test_recraft_creates_four_current_faqs_only_for_products_without_faqs(self):
        product = self._product(pk=102, category=self.cat_h, title="No FAQ product")

        call_command("recraft_product_seo", "--slug", product.slug, stdout=StringIO())

        faqs = list(ProductFAQ.objects.filter(product=product).order_by("order", "id"))
        self.assertEqual(len(faqs), 4)
        self.assertFalse(any("достав" in faq.question.lower() for faq in faqs))

    def test_dry_run(self):
        p = self._product(pk=19, category=self.cat_t,
                          title='Футболка "Харківська Область"')
        out = StringIO()
        call_command("recraft_product_seo", "--slug", "p-19", "--dry-run", stdout=out)
        self.assertIn("Dry-run", out.getvalue())
        p.refresh_from_db()
        self.assertEqual(p.short_description, "")
