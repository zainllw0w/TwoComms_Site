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
