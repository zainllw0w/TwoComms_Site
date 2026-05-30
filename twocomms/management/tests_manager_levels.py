"""
Тести для системи рівнів менеджерів:
- manager_levels (призначення, права, ієрархія)
- weekly_kpi (межі тижня, множник KPI, розрахунок ставки)
- level_progression (умови переходу, прогрес)
- candidate_potential (оцінка 0-10)
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from management.models import (
    Client,
    ManagerLevel,
    ManagerLevelHistory,
    WeeklySalaryAccrual,
)
from management.services import manager_levels as ml
from management.services import weekly_kpi as wk
from management.services import level_progression as lp
from management.services.candidate_potential import calculate_candidate_potential

User = get_user_model()


class WeekBoundariesTests(SimpleTestCase):
    def test_monday_is_week_start(self):
        # 2026-05-25 is a Monday
        start, end = wk.get_week_boundaries(date(2026, 5, 27))  # Wednesday
        self.assertEqual(start, date(2026, 5, 25))
        self.assertEqual(end, date(2026, 5, 31))

    def test_sunday_belongs_to_same_week(self):
        start, end = wk.get_week_boundaries(date(2026, 5, 31))  # Sunday
        self.assertEqual(start, date(2026, 5, 25))
        self.assertEqual(end, date(2026, 5, 31))

    def test_kpi_multiplier_thresholds(self):
        self.assertEqual(wk.calculate_kpi_multiplier(0), Decimal("0.0"))
        self.assertEqual(wk.calculate_kpi_multiplier(1), Decimal("0.5"))
        self.assertEqual(wk.calculate_kpi_multiplier(2), Decimal("1.0"))
        self.assertEqual(wk.calculate_kpi_multiplier(7), Decimal("1.0"))


class LevelHierarchyTests(SimpleTestCase):
    def test_hierarchy_ordering(self):
        self.assertTrue(ml.has_required_level("level_2", "level_1"))
        self.assertTrue(ml.has_required_level("admin", "candidate"))
        self.assertFalse(ml.has_required_level("candidate", "level_1"))
        self.assertFalse(ml.has_required_level("level_1", "top_manager"))
        self.assertTrue(ml.has_required_level("top_manager", "top_manager"))

    def test_permissions_candidate_no_payouts(self):
        perms = ml.get_level_permissions("candidate")
        self.assertFalse(perms["can_view_payouts"])
        self.assertFalse(perms["can_process_bases"])
        self.assertFalse(perms["can_run_parsing"])

    def test_permissions_level1_has_payouts_no_bases(self):
        perms = ml.get_level_permissions("level_1")
        self.assertTrue(perms["can_view_payouts"])
        self.assertFalse(perms["can_process_bases"])

    def test_permissions_level2_has_bases_no_parsing(self):
        perms = ml.get_level_permissions("level_2")
        self.assertTrue(perms["can_process_bases"])
        self.assertFalse(perms["can_run_parsing"])

    def test_permissions_top_manager_has_parsing(self):
        perms = ml.get_level_permissions("top_manager")
        self.assertTrue(perms["can_run_parsing"])
        self.assertTrue(perms["can_approve_bases"])


class PromoteManagerTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="boss", password="x", is_staff=True)
        self.manager = User.objects.create_user(username="mgr", password="x")

    def test_promote_creates_level_and_history(self):
        level = ml.promote_manager(
            user=self.manager,
            new_level="level_1",
            promoted_by=self.admin,
            weekly_salary=5000,
            commission_percent=Decimal("5.5"),
            start_date=date(2026, 5, 25),
            comment="перше призначення",
        )
        self.assertEqual(level.level, "level_1")
        self.assertEqual(level.weekly_salary_uah, 5000)
        self.assertEqual(level.commission_percent, Decimal("5.5"))
        self.assertTrue(level.is_active)

        history = ManagerLevelHistory.objects.filter(user=self.manager)
        self.assertEqual(history.count(), 1)
        h = history.first()
        self.assertIsNone(h.old_level)
        self.assertEqual(h.new_level, "level_1")
        self.assertEqual(h.changed_by, self.admin)

    def test_promote_twice_records_old_level(self):
        ml.promote_manager(
            user=self.manager, new_level="candidate", promoted_by=self.admin,
            commission_percent=Decimal("3"), start_date=date(2026, 5, 1),
        )
        ml.promote_manager(
            user=self.manager, new_level="level_1", promoted_by=self.admin,
            weekly_salary=5000, commission_percent=Decimal("5"), start_date=date(2026, 5, 25),
        )
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.manager_level.level, "level_1")
        last = ManagerLevelHistory.objects.filter(user=self.manager).order_by("-changed_at").first()
        self.assertEqual(last.old_level, "candidate")
        self.assertEqual(last.new_level, "level_1")

    def test_promote_syncs_userprofile(self):
        ml.promote_manager(
            user=self.manager, new_level="level_1", promoted_by=self.admin,
            weekly_salary=4200, commission_percent=Decimal("6"), start_date=date(2026, 5, 25),
        )
        prof = self.manager.userprofile
        self.assertEqual(prof.manager_base_salary_uah, 4200)
        self.assertEqual(prof.manager_commission_percent, Decimal("6"))

    def test_demote_deactivates_level(self):
        ml.promote_manager(
            user=self.manager, new_level="level_1", promoted_by=self.admin,
            weekly_salary=5000, commission_percent=Decimal("5"), start_date=date(2026, 5, 25),
        )
        ml.demote_manager(user=self.manager, reason="звільнення", demoted_by=self.admin)
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.manager_level.is_active)

    def test_staff_has_all_permissions_without_level(self):
        self.assertTrue(ml.has_permission(self.admin, "can_run_parsing"))
        self.assertTrue(ml.has_permission(self.admin, "can_view_payouts"))


class WeeklySalaryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="boss2", password="x", is_staff=True)
        self.manager = User.objects.create_user(username="mgr2", password="x")
        self.week_start = date(2026, 5, 25)
        self.week_end = date(2026, 5, 31)

    def _make_client(self, call_result, created):
        c = Client.objects.create(
            owner=self.manager,
            shop_name="Shop",
            phone="+380501112233",
            full_name="Test",
            call_result=call_result,
        )
        # created_at is auto_now_add; override explicitly
        Client.objects.filter(pk=c.pk).update(
            created_at=timezone.make_aware(datetime.combine(created, datetime.min.time()) + timedelta(hours=12))
        )
        return c

    def test_candidate_gets_zero_salary(self):
        ml.promote_manager(
            user=self.manager, new_level="candidate", promoted_by=self.admin,
            commission_percent=Decimal("3"), start_date=self.week_start,
        )
        self._make_client(Client.CallResult.ORDER, self.week_start)
        self._make_client(Client.CallResult.ORDER, self.week_start)
        data = wk.calculate_weekly_salary(self.manager, self.week_start, self.week_end)
        self.assertEqual(data["accrued_amount"], Decimal("0"))
        self.assertEqual(data["kpi_status"], "candidate")
        # but conversions are still counted
        self.assertEqual(data["conversions"], 2)

    def test_level1_two_conversions_full_salary(self):
        ml.promote_manager(
            user=self.manager, new_level="level_1", promoted_by=self.admin,
            weekly_salary=5000, commission_percent=Decimal("5"), start_date=self.week_start,
        )
        self._make_client(Client.CallResult.ORDER, self.week_start)
        self._make_client(Client.CallResult.TEST_BATCH, self.week_start)
        data = wk.calculate_weekly_salary(self.manager, self.week_start, self.week_end)
        self.assertEqual(data["conversions"], 2)
        self.assertEqual(data["kpi_multiplier"], Decimal("1.0"))
        self.assertEqual(data["accrued_amount"], Decimal("5000.00"))

    def test_level1_one_conversion_half_salary(self):
        ml.promote_manager(
            user=self.manager, new_level="level_1", promoted_by=self.admin,
            weekly_salary=5000, commission_percent=Decimal("5"), start_date=self.week_start,
        )
        self._make_client(Client.CallResult.ORDER, self.week_start)
        self._make_client(Client.CallResult.NO_ANSWER, self.week_start)
        data = wk.calculate_weekly_salary(self.manager, self.week_start, self.week_end)
        self.assertEqual(data["conversions"], 1)
        self.assertEqual(data["accrued_amount"], Decimal("2500.00"))

    def test_level1_zero_conversions_no_salary(self):
        ml.promote_manager(
            user=self.manager, new_level="level_1", promoted_by=self.admin,
            weekly_salary=5000, commission_percent=Decimal("5"), start_date=self.week_start,
        )
        self._make_client(Client.CallResult.NO_ANSWER, self.week_start)
        data = wk.calculate_weekly_salary(self.manager, self.week_start, self.week_end)
        self.assertEqual(data["conversions"], 0)
        self.assertEqual(data["accrued_amount"], Decimal("0.00"))
        self.assertEqual(data["kpi_status"], "failed")

    def test_accrue_is_idempotent_per_week(self):
        ml.promote_manager(
            user=self.manager, new_level="level_1", promoted_by=self.admin,
            weekly_salary=5000, commission_percent=Decimal("5"), start_date=self.week_start,
        )
        self._make_client(Client.CallResult.ORDER, self.week_start)
        self._make_client(Client.CallResult.ORDER, self.week_start)
        a1 = wk.accrue_weekly_salary(self.manager, self.week_start, self.week_end)
        a2 = wk.accrue_weekly_salary(self.manager, self.week_start, self.week_end)
        self.assertEqual(a1.pk, a2.pk)
        self.assertEqual(WeeklySalaryAccrual.objects.filter(user=self.manager).count(), 1)
        self.assertEqual(a1.accrued_amount, Decimal("5000.00"))


class ProgressionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="boss3", password="x", is_staff=True)
        self.manager = User.objects.create_user(username="mgr3", password="x")

    def _make_clients(self, n, call_result=Client.CallResult.NO_ANSWER):
        for i in range(n):
            Client.objects.create(
                owner=self.manager,
                shop_name=f"Shop {i}",
                phone=f"+38050000{i:04d}",
                full_name="X",
                call_result=call_result,
            )

    def test_candidate_eligible_after_two_conversions(self):
        ml.promote_manager(
            user=self.manager, new_level="candidate", promoted_by=self.admin,
            commission_percent=Decimal("3"), start_date=timezone.localdate(),
        )
        self._make_clients(2, Client.CallResult.ORDER)
        can_promote, _ = lp.check_auto_promotion_conditions(self.manager)
        self.assertTrue(can_promote)

    def test_candidate_eligible_after_hundred_processed(self):
        ml.promote_manager(
            user=self.manager, new_level="candidate", promoted_by=self.admin,
            commission_percent=Decimal("3"), start_date=timezone.localdate(),
        )
        self._make_clients(100, Client.CallResult.NO_ANSWER)
        can_promote, _ = lp.check_auto_promotion_conditions(self.manager)
        self.assertTrue(can_promote)

    def test_candidate_not_eligible_early(self):
        ml.promote_manager(
            user=self.manager, new_level="candidate", promoted_by=self.admin,
            commission_percent=Decimal("3"), start_date=timezone.localdate(),
        )
        self._make_clients(10, Client.CallResult.NO_ANSWER)
        can_promote, _ = lp.check_auto_promotion_conditions(self.manager)
        self.assertFalse(can_promote)

    def test_progression_status_has_next_level(self):
        ml.promote_manager(
            user=self.manager, new_level="candidate", promoted_by=self.admin,
            commission_percent=Decimal("3"), start_date=timezone.localdate(),
        )
        status = lp.get_progression_status(self.manager)
        self.assertEqual(status["current_level"], "candidate")
        self.assertEqual(status["next_level"], "level_1")
        self.assertGreaterEqual(status["progress_pct"], 0)


class CandidatePotentialTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="boss4", password="x", is_staff=True)
        self.manager = User.objects.create_user(username="mgr4", password="x")
        ml.promote_manager(
            user=self.manager, new_level="candidate", promoted_by=self.admin,
            commission_percent=Decimal("3"), start_date=timezone.localdate() - timedelta(days=10),
        )

    def test_no_clients_returns_zero(self):
        result = calculate_candidate_potential(self.manager)
        self.assertEqual(result["score"], Decimal("0"))
        self.assertEqual(result["grade"], "N/A")

    def test_score_in_range_with_clients(self):
        for i in range(20):
            cr = Client.CallResult.ORDER if i < 2 else Client.CallResult.NO_ANSWER
            Client.objects.create(
                owner=self.manager, shop_name=f"S{i}", phone=f"+38050111{i:04d}",
                full_name="N", call_result=cr,
            )
        result = calculate_candidate_potential(self.manager)
        self.assertGreaterEqual(result["score"], Decimal("0"))
        self.assertLessEqual(result["score"], Decimal("10"))
        self.assertIn("components", result)
        self.assertIn("quality", result["components"])
        self.assertIn("results", result["components"])
        self.assertEqual(result["details"]["conversions"], 2)
