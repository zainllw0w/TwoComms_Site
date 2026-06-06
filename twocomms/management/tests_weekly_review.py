"""Тести Фази 5: тижневі рішення по базовій винагороді."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from orders.models import WholesaleInvoice
from management.models import (
    ManagerWeeklyReview, ManagerCompensationSettings, ManagerEarningsLedger, AdminAuditLog,
)
from management.services import weekly_review

User = get_user_model()


class WeeklyReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="wr_mgr", password="x")
        cls.manager.userprofile.is_manager = True
        cls.manager.userprofile.save()
        cls.staff = User.objects.create_user(username="wr_boss", password="x", is_staff=True)
        ManagerCompensationSettings.objects.create(
            owner=cls.manager, monthly_base_amount=Decimal("8000.00"), weeks_per_month=4,
            commission_percent=Decimal("10"), effective_from=date.today() - timedelta(days=30),
        )

    def test_week_bounds(self):
        ws, we = weekly_review.week_bounds(date(2026, 6, 3))  # середа
        self.assertEqual(ws, date(2026, 6, 1))  # понеділок
        self.assertEqual(we, date(2026, 6, 7))  # неділя

    def test_calculated_weekly_base(self):
        base = weekly_review.calculated_weekly_base(self.manager)
        self.assertEqual(base, Decimal("2000.00"))  # 8000 / 4

    def test_generate_and_decide_full(self):
        ws, we = weekly_review.previous_week_bounds()
        result = weekly_review.generate_for_week(ws, we, only_user=self.manager.id)
        self.assertEqual(result["created"], 1)
        review = ManagerWeeklyReview.objects.get(owner=self.manager, week_start=ws)
        self.assertEqual(review.calculated_weekly_base, Decimal("2000.00"))
        self.assertEqual(review.admin_decision, "")

        ok, err = weekly_review.apply_decision(review, decision="full", admin=self.staff)
        self.assertTrue(ok, err)
        review.refresh_from_db()
        self.assertEqual(review.awarded_amount, Decimal("2000.00"))
        # ledger-запис створено
        self.assertTrue(ManagerEarningsLedger.objects.filter(
            source_type=ManagerEarningsLedger.SourceType.WEEKLY_BASE, source_id=f"review-{review.id}"
        ).exists())
        # audit
        self.assertTrue(AdminAuditLog.objects.filter(action="weekly_review_decision", entity_id=str(review.id)).exists())

    def test_decide_half_requires_reason(self):
        ws, we = weekly_review.previous_week_bounds()
        review = ManagerWeeklyReview.objects.create(
            owner=self.manager, week_start=ws, week_end=we, calculated_weekly_base=Decimal("2000"),
        )
        ok, err = weekly_review.apply_decision(review, decision="half", admin=self.staff)
        self.assertFalse(ok)
        ok, err = weekly_review.apply_decision(review, decision="half", reason="мало активності", admin=self.staff)
        self.assertTrue(ok, err)
        review.refresh_from_db()
        self.assertEqual(review.awarded_amount, Decimal("1000.00"))

    def test_decide_custom_and_none(self):
        ws, we = weekly_review.previous_week_bounds()
        r1 = ManagerWeeklyReview.objects.create(owner=self.manager, week_start=ws, week_end=we, calculated_weekly_base=Decimal("2000"))
        ok, _ = weekly_review.apply_decision(r1, decision="custom", custom_amount="1234.50", reason="бонус", admin=self.staff)
        self.assertTrue(ok)
        r1.refresh_from_db()
        self.assertEqual(r1.awarded_amount, Decimal("1234.50"))

        r2 = ManagerWeeklyReview.objects.create(owner=self.manager, week_start=ws - timedelta(days=7), week_end=we - timedelta(days=7), calculated_weekly_base=Decimal("2000"))
        ok, _ = weekly_review.apply_decision(r2, decision="none", reason="без результату", admin=self.staff)
        self.assertTrue(ok)
        r2.refresh_from_db()
        self.assertEqual(r2.awarded_amount, Decimal("0.00"))
        # для none/0 ledger не створюється
        self.assertFalse(ManagerEarningsLedger.objects.filter(source_id=f"review-{r2.id}").exists())

    def test_generate_does_not_override_decided(self):
        ws, we = weekly_review.previous_week_bounds()
        review = ManagerWeeklyReview.objects.create(
            owner=self.manager, week_start=ws, week_end=we, calculated_weekly_base=Decimal("2000"),
            admin_decision="full", awarded_amount=Decimal("2000"),
        )
        weekly_review.generate_for_week(ws, we, only_user=self.manager.id)
        review.refresh_from_db()
        self.assertEqual(review.admin_decision, "full")  # не перезаписано

    def test_command_runs(self):
        call_command("generate_weekly_reviews", "--user-id", str(self.manager.id))
        ws, we = weekly_review.previous_week_bounds()
        self.assertTrue(ManagerWeeklyReview.objects.filter(owner=self.manager, week_start=ws).exists())


@override_settings(ROOT_URLCONF="twocomms.urls_management",
                   ALLOWED_HOSTS=["testserver", "management.twocomms.shop"])
class WeeklyReviewEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="wr_mgr2", password="x")
        cls.staff = User.objects.create_user(username="wr_boss2", password="x", is_staff=True)

    def test_decide_endpoint(self):
        ws, we = weekly_review.previous_week_bounds()
        review = ManagerWeeklyReview.objects.create(
            owner=self.manager, week_start=ws, week_end=we, calculated_weekly_base=Decimal("1500"),
        )
        self.client.force_login(self.staff)
        resp = self.client.post(
            f"/admin-panel/weekly-reviews/{review.id}/decide/",
            data='{"decision": "full"}', content_type="application/json",
            HTTP_HOST="management.twocomms.shop", secure=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        review.refresh_from_db()
        self.assertEqual(review.awarded_amount, Decimal("1500.00"))
