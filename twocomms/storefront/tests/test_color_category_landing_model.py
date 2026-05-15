"""Tests for the ``CategoryColorLanding`` model.

Covers the colour×category landing-page model added in
``.kiro/specs/color-category-landings``.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from productcolors.models import Color
from storefront.models import Category, CategoryColorLanding


_LONG_EDITORIAL = (
    "Чорна футболка TwoComms — це базовий, але далеко не нудний шар "
    "стрітвір-гардеробу. Ми друкуємо принти DTF-методом на щільній "
    "бавовні 200 г/м² і збираємо комплекти для тих, кому важливі і "
    "посадка, і деталі. Кожна модель пройшла тестування у польових "
    "умовах: концерт, тренування, пара зустрічей у місті. Ми не "
    "розповідаємо казкових легенд — просто робимо одяг, у якому "
    "впевнено себе почуваєш. Якщо ви шукаєте чорну футболку, що "
    "переживе десяти прань без втрати кольору, потрапили за адресою."
) * 2  # ≥1500 chars; well above the 800-char guard


class CategoryColorLandingModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Футболки",
            slug="tshirts",
            order=10,
        )
        cls.black = Color.objects.create(name="Чорний", primary_hex="#000000")
        cls.white = Color.objects.create(name="Білий", primary_hex="#FFFFFF")

    # ---- Defaults ----

    def test_is_published_defaults_to_false(self):
        landing = CategoryColorLanding.objects.create(
            category=self.category,
            color=self.black,
            seo_title="Чорні футболки TwoComms",
            seo_description="Чорні футболки з принтами TwoComms.",
            editorial_html="any text",
        )
        self.assertFalse(landing.is_published)

    # ---- Auto-derive color_slug ----

    def test_color_slug_is_auto_derived_from_color_name(self):
        landing = CategoryColorLanding.objects.create(
            category=self.category,
            color=self.black,
            seo_title="Чорні футболки",
            seo_description="—",
            editorial_html="—",
        )
        self.assertEqual(landing.color_slug, "black")

    def test_color_slug_can_be_overridden_explicitly(self):
        landing = CategoryColorLanding.objects.create(
            category=self.category,
            color=self.black,
            color_slug="custom-onyx",
            seo_title="Чорні футболки",
            seo_description="—",
            editorial_html="—",
        )
        self.assertEqual(landing.color_slug, "custom-onyx")

    # ---- Anti-thin guard ----

    def test_anti_thin_guard_fires_when_publishing_short_copy(self):
        landing = CategoryColorLanding(
            category=self.category,
            color=self.black,
            seo_title="Чорні футболки",
            seo_description="—",
            editorial_html="too short",
            is_published=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            landing.full_clean()
        self.assertIn("editorial_html", ctx.exception.error_dict)

    def test_anti_thin_guard_silent_for_unpublished_drafts(self):
        landing = CategoryColorLanding(
            category=self.category,
            color=self.black,
            seo_title="Чорні футболки (draft)",
            seo_description="—",
            editorial_html="short draft",
            is_published=False,
        )
        # Drafts should validate even with thin copy.
        landing.full_clean()  # would raise on failure

    def test_anti_thin_guard_passes_for_published_long_copy(self):
        landing = CategoryColorLanding(
            category=self.category,
            color=self.black,
            seo_title="Чорні футболки TwoComms",
            seo_description="Чорні футболки з принтами TwoComms.",
            editorial_html=_LONG_EDITORIAL,
            is_published=True,
        )
        landing.full_clean()  # would raise on failure

    # ---- Uniqueness ----

    def test_unique_together_category_color_slug(self):
        CategoryColorLanding.objects.create(
            category=self.category,
            color=self.black,
            seo_title="Чорні футболки",
            seo_description="—",
            editorial_html="—",
        )
        # Same category + same derived slug → unique violation.
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CategoryColorLanding.objects.create(
                    category=self.category,
                    color=self.black,
                    seo_title="Дубль",
                    seo_description="—",
                    editorial_html="—",
                )

    def test_get_absolute_url_format(self):
        landing = CategoryColorLanding.objects.create(
            category=self.category,
            color=self.black,
            seo_title="Чорні футболки",
            seo_description="—",
            editorial_html="—",
        )
        self.assertEqual(landing.get_absolute_url(), "/catalog/tshirts/black/")

    def test_display_h1_falls_back_to_seo_title(self):
        landing = CategoryColorLanding.objects.create(
            category=self.category,
            color=self.black,
            seo_title="Чорні футболки TwoComms",
            seo_description="—",
            editorial_html="—",
        )
        self.assertEqual(landing.display_h1, "Чорні футболки TwoComms")
        landing.seo_h1 = "Чорні футболки з принтами"
        self.assertEqual(landing.display_h1, "Чорні футболки з принтами")
