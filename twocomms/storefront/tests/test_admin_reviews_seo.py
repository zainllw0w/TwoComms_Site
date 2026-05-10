"""Phase 21 (PR-A1/A2) — custom admin endpoints for review moderation
and category SEO overrides.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from reviews.models import Review, ReviewStatus
from storefront.models import Category, Product


class AdminReviewModerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            username="staff", password="x", is_staff=True,
        )
        cls.regular = User.objects.create_user(username="reg", password="x")
        cls.category = Category.objects.create(
            name="Adm", slug="adm", is_active=True,
        )
        cls.product = Product.objects.create(
            title="Adm Tee", slug="adm-tee",
            category=cls.category, price=300, status="published",
        )

    def setUp(self):
        self.client = Client()
        self.review = Review.objects.create(
            product=self.product, author_name="X", anon_key="k",
            rating=4, body="x" * 30, status=ReviewStatus.PENDING,
        )

    def test_non_staff_blocked(self):
        self.client.force_login(self.regular)
        r = self.client.post(
            reverse("admin_review_action", kwargs={"review_id": self.review.pk}),
            {"action": "approve"},
        )
        # ``staff_member_required`` redirects to admin login — not 200.
        self.assertNotEqual(r.status_code, 200)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.PENDING)

    def test_staff_approve_flips_status(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("admin_review_action", kwargs={"review_id": self.review.pk}),
            {"action": "approve", "note": "ok"},
        )
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], ReviewStatus.APPROVED)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.APPROVED)
        self.assertEqual(self.review.moderated_by, self.staff)

    def test_staff_reject(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("admin_review_action", kwargs={"review_id": self.review.pk}),
            {"action": "reject"},
        )
        self.assertEqual(r.status_code, 200)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.REJECTED)

    def test_bulk_approve_walks_each_row(self):
        # Create 2 more pending reviews so the bulk path actually loops.
        extras = [
            Review.objects.create(
                product=self.product, author_name=f"X{i}", anon_key=f"k{i}",
                rating=5, body="x" * 30, status=ReviewStatus.PENDING,
            )
            for i in range(2)
        ]
        ids = ",".join(str(r.pk) for r in [self.review, *extras])
        self.client.force_login(self.staff)
        r = self.client.post(reverse("admin_review_bulk"), {"action": "approve", "ids": ids})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("updated"), 3)
        self.assertEqual(
            Review.objects.filter(status=ReviewStatus.APPROVED).count(), 3,
        )


class AdminCategorySeoSaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            username="seo-staff", password="x", is_staff=True,
        )
        cls.category = Category.objects.create(
            name="SeoCat", slug="seo-cat", is_active=True,
        )

    def test_save_persists_seo_fields(self):
        self.client = Client()
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("admin_seo_category_save"),
            {
                "category_id": self.category.pk,
                "seo_title": "Унікальний тайтл",
                "seo_h1": "H1 категорії",
                "seo_description": "Опис " * 5,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))
        self.category.refresh_from_db()
        self.assertEqual(self.category.seo_title, "Унікальний тайтл")
        self.assertEqual(self.category.seo_h1, "H1 категорії")

    def test_save_truncates_overlong_input(self):
        self.client = Client()
        self.client.force_login(self.staff)
        long_title = "Q" * 500
        r = self.client.post(
            reverse("admin_seo_category_save"),
            {
                "category_id": self.category.pk,
                "seo_title": long_title,
                "seo_h1": "",
                "seo_description": "",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.category.refresh_from_db()
        self.assertEqual(len(self.category.seo_title), 180)


class AdminColorSeoOverrideTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            username="csov-staff", password="x", is_staff=True,
        )
        cls.cat = Category.objects.create(
            name="CSov Cat", slug="csov-cat", is_active=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.staff)

    def test_create_general_scope_idempotent(self):
        from storefront.models import CatalogColorSeoOverride

        url = reverse("admin_color_seo_create")
        first = self.client.post(url, {"scope": "general"})
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json().get("ok"))
        self.assertTrue(first.json().get("created"))

        second = self.client.post(url, {"scope": "general"})
        self.assertTrue(second.json().get("ok"))
        self.assertFalse(second.json().get("created"))
        self.assertEqual(CatalogColorSeoOverride.objects.count(), 1)

    def test_save_persists_h2_body_queries_and_active(self):
        from storefront.models import CatalogColorSeoOverride

        row = CatalogColorSeoOverride.objects.create(scope="general")
        url = reverse("admin_color_seo_save", kwargs={"override_id": row.pk})
        r = self.client.post(url, {
            "h2": "Унікальний заголовок",
            "body_html": "<p>тіло</p>",
            "queries_json": '[{"label":"a","url":"/x","freq":"hf"}]',
            "is_active": "1",
        })
        self.assertEqual(r.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.h2, "Унікальний заголовок")
        self.assertEqual(row.body_html, "<p>тіло</p>")
        self.assertEqual(row.queries_json, [{"label": "a", "url": "/x", "freq": "hf"}])
        self.assertTrue(row.is_active)

    def test_save_rejects_malformed_json(self):
        from storefront.models import CatalogColorSeoOverride

        row = CatalogColorSeoOverride.objects.create(scope="general")
        url = reverse("admin_color_seo_save", kwargs={"override_id": row.pk})
        r = self.client.post(url, {"queries_json": "{not-json"})
        self.assertEqual(r.status_code, 400)

    def test_delete_removes_row(self):
        from storefront.models import CatalogColorSeoOverride

        row = CatalogColorSeoOverride.objects.create(scope="general")
        url = reverse("admin_color_seo_delete", kwargs={"override_id": row.pk})
        r = self.client.post(url)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(CatalogColorSeoOverride.objects.filter(pk=row.pk).exists())


class AdminCategorySwatchesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            username="sw-staff", password="x", is_staff=True,
        )
        cls.cat = Category.objects.create(
            name="Sw Cat", slug="sw-cat", is_active=True,
        )

    def test_save_normalises_hex_tokens(self):
        self.client = Client()
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("admin_category_swatches_save"),
            {"category_id": self.cat.pk, "swatches": "000000, #FFFFFF, badtoken, #abc"},
        )
        self.assertEqual(r.status_code, 200)
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.showcase_swatch_hexes, ["#000000", "#ffffff", "#abc"])

    def test_save_caps_at_six_swatches(self):
        self.client = Client()
        self.client.force_login(self.staff)
        long_list = ",".join([f"#{i:06d}" for i in range(10)])
        self.client.post(
            reverse("admin_category_swatches_save"),
            {"category_id": self.cat.pk, "swatches": long_list},
        )
        self.cat.refresh_from_db()
        self.assertEqual(len(self.cat.showcase_swatch_hexes), 6)


class AdminPanelReviewsSectionRenderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            username="panel-staff", password="x", is_staff=True,
        )

    def test_reviews_section_renders_for_staff(self):
        self.client = Client()
        self.client.force_login(self.staff)
        r = self.client.get("/admin-panel/?section=reviews")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8")
        self.assertIn("data-admin-reviews", body)
        self.assertIn("section=reviews", body)
