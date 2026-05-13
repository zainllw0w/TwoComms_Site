"""Phase 21 — regression tests for ``reviews.services.aggregate``.

Verify the single most important business rule: AggregateRating only
surfaces at ≥3 approved reviews, and ``count`` / ``avg`` / ``histogram``
only count approved rows (pending and rejected never leak).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from storefront.models import Category, Product
from reviews.models import Review, ReviewStatus
from reviews.services.aggregate import (
    MIN_APPROVED_REVIEWS_FOR_RATING,
    aggregate_rating_for_product,
)


class AggregateRatingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="reviewer", password="x"
        )
        cls.category = Category.objects.create(
            name="Reviews Test", slug="rev-test", is_active=True,
        )
        cls.product = Product.objects.create(
            title="Reviewed Tee",
            slug="reviewed-tee",
            category=cls.category,
            price=300,
            status="published",
        )

    def _make_review(self, *, rating, status=ReviewStatus.APPROVED, **extra):
        return Review.objects.create(
            product=self.product,
            user=self.user,
            author_name="Reviewer",
            rating=rating,
            body="x" * 30,
            status=status,
            **extra,
        )

    def test_no_reviews_returns_zero_summary(self):
        s = aggregate_rating_for_product(self.product)
        self.assertEqual(s.count, 0)
        self.assertIsNone(s.avg)
        self.assertFalse(s.show_rating)
        self.assertFalse(s.has_any_approved)
        self.assertEqual(s.histogram, {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})

    def test_pending_and_rejected_are_excluded(self):
        self._make_review(rating=5, status=ReviewStatus.PENDING)
        self._make_review(rating=1, status=ReviewStatus.REJECTED)
        s = aggregate_rating_for_product(self.product)
        self.assertEqual(s.count, 0)
        self.assertIsNone(s.avg)

    def test_threshold_constant_is_one(self):
        # SEO v1.0 Phase 12 (2026-05-13) — finding (M). The legacy
        # threshold (3) starved cold-start PDP from earning the
        # SERP star-rating rich result; lowered to 1 so a single
        # approved review unlocks ``aggregateRating`` JSON-LD.
        self.assertEqual(MIN_APPROVED_REVIEWS_FOR_RATING, 1)

    def test_single_approved_review_flips_show_rating_true(self):
        # At the new threshold (1) one approved review is enough
        # to render the rating chip and emit AggregateRating.
        self._make_review(rating=5)
        s = aggregate_rating_for_product(self.product)
        self.assertEqual(s.count, 1)
        self.assertEqual(s.avg, 5.0)
        self.assertTrue(s.show_rating)
        self.assertEqual(s.histogram[5], 1)

    def test_at_three_reviews_show_rating_remains_true(self):
        for r in (5, 5, 4):
            self._make_review(rating=r)
        s = aggregate_rating_for_product(self.product)
        self.assertEqual(s.count, 3)
        self.assertEqual(s.avg, 4.7)
        self.assertTrue(s.show_rating)
        self.assertEqual(s.histogram[5], 2)
        self.assertEqual(s.histogram[4], 1)

    def test_histogram_is_zero_filled_even_when_partial(self):
        for r in (5, 5, 5):
            self._make_review(rating=r)
        s = aggregate_rating_for_product(self.product)
        self.assertEqual(s.histogram[5], 3)
        for r in (1, 2, 3, 4):
            self.assertEqual(s.histogram[r], 0)

    def test_average_alias_matches_avg(self):
        for r in (5, 5, 4):
            self._make_review(rating=r)
        s = aggregate_rating_for_product(self.product)
        # ``average`` is a backwards-compat alias used by the PDP
        # template (``{{ product_review_summary.average }}``).
        self.assertEqual(s.average, s.avg)

    def test_avg_rounded_to_one_decimal(self):
        for r in (5, 4, 3):  # avg = 4.0
            self._make_review(rating=r)
        s = aggregate_rating_for_product(self.product)
        self.assertEqual(s.avg, 4.0)

        # +1 review with rating 1 → 13/4 = 3.25 → rounded to 3.2 (banker?) or 3.3
        self._make_review(rating=1)
        s2 = aggregate_rating_for_product(self.product)
        self.assertEqual(s2.count, 4)
        # round() is banker's in py3 (ROUND_HALF_EVEN). 3.25 → 3.2
        self.assertIn(s2.avg, (3.2, 3.3))


class ReviewModelLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Reviews Lifecycle", slug="rev-life", is_active=True,
        )
        cls.product = Product.objects.create(
            title="Lifecycle Tee", slug="life-tee",
            category=cls.category, price=300, status="published",
        )

    def test_default_status_is_pending(self):
        r = Review.objects.create(
            product=self.product, author_name="Anon",
            anon_key="abc", rating=5, body="x" * 30,
        )
        self.assertEqual(r.status, ReviewStatus.PENDING)
        self.assertIsNone(r.moderated_at)

    def test_mark_approved_stamps_moderation_metadata(self):
        admin_user = get_user_model().objects.create_user(username="mod")
        r = Review.objects.create(
            product=self.product, author_name="Anon",
            anon_key="abc", rating=4, body="x" * 30,
        )
        r.mark_approved(by=admin_user, note="ok")
        r.refresh_from_db()
        self.assertEqual(r.status, ReviewStatus.APPROVED)
        self.assertEqual(r.moderated_by, admin_user)
        self.assertIsNotNone(r.moderated_at)
        self.assertEqual(r.moderation_note, "ok")
