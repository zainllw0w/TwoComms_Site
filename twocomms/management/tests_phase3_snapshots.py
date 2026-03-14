from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import (
    Client,
    CommandRunLog,
    ManagementDailyActivity,
    ManagementStatsConfig,
    ManagerDayStatus,
    NightlyScoreSnapshot,
    ScoreAppeal,
)
from management.services.snapshots import build_daily_stats_range, persist_nightly_snapshot
from management.stats_service import get_stats_payload


class SnapshotServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="snapshot_mgr", password="x", is_staff=True)
        call_command("seed_management_defaults")

    def test_build_daily_stats_range_creates_single_local_day_window(self):
        target_date = date(2026, 3, 10)

        result = build_daily_stats_range(target_date)

        self.assertEqual(result.start_date, target_date)
        self.assertEqual(result.end_date, target_date)
        self.assertEqual(result.days, 1)
        self.assertEqual(result.start.hour, 0)
        self.assertEqual(result.start.minute, 0)
        self.assertEqual(result.end.hour, 0)
        self.assertEqual(result.end.minute, 0)

    def test_persist_nightly_snapshot_upserts_payload_and_versions(self):
        target_date = date(2026, 3, 10)
        created_at = timezone.make_aware(datetime.combine(target_date, time(hour=10, minute=15)))
        Client.objects.create(
            shop_name="Snapshot Shop",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            points_override=180,
            source="Instagram",
        )
        Client.objects.filter(owner=self.user).update(created_at=created_at)
        ManagementDailyActivity.objects.create(
            user=self.user,
            date=target_date,
            active_seconds=7_200,
            last_seen_at=created_at,
        )
        ManagerDayStatus.objects.create(
            owner=self.user,
            day=target_date,
            status=ManagerDayStatus.Status.WORKING,
            capacity_factor=Decimal("0.50"),
            source_reason="manual",
        )

        first = persist_nightly_snapshot(owner=self.user, snapshot_date=target_date)
        second = persist_nightly_snapshot(owner=self.user, snapshot_date=target_date)

        self.assertEqual(NightlyScoreSnapshot.objects.count(), 1)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.snapshot_date, target_date)
        self.assertEqual(first.formula_version, "mosaic-v1")
        self.assertEqual(first.defaults_version, "2026-03-13")
        self.assertEqual(first.working_day_factor, Decimal("0.50"))
        self.assertGreater(first.kpd_value, Decimal("0.00"))
        self.assertIn("axes", first.payload)
        self.assertIn("readiness", first.payload)
        self.assertEqual(first.payload["stats_range"]["from"], "2026-03-10")

    def test_stats_payload_exposes_shadow_snapshot_summary(self):
        target_date = date(2026, 3, 10)
        created_at = timezone.make_aware(datetime.combine(target_date, time(hour=12, minute=30)))
        Client.objects.create(
            shop_name="Snapshot Shop",
            phone="+380671112244",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            points_override=180,
            source="Instagram",
        )
        Client.objects.filter(owner=self.user).update(created_at=created_at)
        ManagementDailyActivity.objects.create(user=self.user, date=target_date, active_seconds=7_200, last_seen_at=created_at)

        persist_nightly_snapshot(owner=self.user, snapshot_date=target_date)
        payload = get_stats_payload(user=self.user, range_current=build_daily_stats_range(target_date))

        self.assertIn("shadow_score", payload)
        self.assertEqual(payload["shadow_score"]["state"], "shadow")
        self.assertEqual(payload["shadow_score"]["snapshot_date"], target_date.isoformat())
        self.assertIn("mosaic_score", payload["shadow_score"])
        self.assertIn("score_confidence", payload["shadow_score"])


class ComputeNightlyScoresCommandTests(TestCase):
    def setUp(self):
        cache.clear()
        self.manager = get_user_model().objects.create_user(username="command_mgr", password="x", is_staff=True)
        self.regular_user = get_user_model().objects.create_user(username="plain_user", password="x")
        call_command("seed_management_defaults")

    def test_command_creates_run_log_and_snapshot_for_management_users_only(self):
        target_date = date(2026, 3, 11)
        created_at = timezone.make_aware(datetime.combine(target_date, time(hour=11, minute=0)))
        Client.objects.create(
            shop_name="Manager Shop",
            phone="+380671112200",
            full_name="Owner",
            owner=self.manager,
            call_result=Client.CallResult.THINKING,
            points_override=120,
            source="Instagram",
        )
        Client.objects.filter(owner=self.manager).update(created_at=created_at)
        ManagementDailyActivity.objects.create(user=self.manager, date=target_date, active_seconds=3_600, last_seen_at=created_at)

        call_command("compute_nightly_scores", date=target_date.isoformat())

        self.assertEqual(NightlyScoreSnapshot.objects.filter(owner=self.manager, snapshot_date=target_date).count(), 1)
        self.assertFalse(NightlyScoreSnapshot.objects.filter(owner=self.regular_user, snapshot_date=target_date).exists())

        run_log = CommandRunLog.objects.get(command_name="compute_nightly_scores")
        self.assertEqual(run_log.status, CommandRunLog.Status.SUCCESS)
        self.assertEqual(run_log.rows_processed, 1)
        self.assertEqual(run_log.meta["snapshot_date"], target_date.isoformat())


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class StatsShadowUiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="stats_shadow_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)
        call_command("seed_management_defaults")

    def test_stats_page_renders_shadow_score_card(self):
        target_date = date(2026, 3, 10)
        created_at = timezone.make_aware(datetime.combine(target_date, time(hour=14, minute=10)))
        Client.objects.create(
            shop_name="UI Shop",
            phone="+380671119999",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            points_override=180,
            source="Instagram",
        )
        Client.objects.filter(owner=self.user).update(created_at=created_at)
        ManagementDailyActivity.objects.create(user=self.user, date=target_date, active_seconds=3_600, last_seen_at=created_at)
        persist_nightly_snapshot(owner=self.user, snapshot_date=target_date)

        response = self.client.get(
            f"/stats/?period=range&from={target_date.isoformat()}&to={target_date.isoformat()}",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MOSAIC")
        self.assertContains(response, "SHADOW")


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class ScoreAppealApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="appeal_mgr", password="x", is_staff=True)
        self.admin_user = get_user_model().objects.create_user(username="appeal_admin", password="x", is_staff=True)
        call_command("seed_management_defaults")

        target_date = date(2026, 3, 10)
        created_at = timezone.make_aware(datetime.combine(target_date, time(hour=9, minute=10)))
        Client.objects.create(
            shop_name="Appeal Shop",
            phone="+380671115555",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            points_override=180,
            source="Instagram",
        )
        Client.objects.filter(owner=self.user).update(created_at=created_at)
        ManagementDailyActivity.objects.create(user=self.user, date=target_date, active_seconds=3_600, last_seen_at=created_at)
        self.snapshot = persist_nightly_snapshot(owner=self.user, snapshot_date=target_date)

    def test_manager_can_create_score_appeal_for_own_snapshot(self):
        self.client.force_login(self.user)

        response = self.client.post(
            "/stats/appeals/create/",
            {
                "snapshot_id": self.snapshot.id,
                "reason": "Потрібно перевірити оцінку за цей день",
                "evidence_note": "Була узгоджена відсутність",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(ScoreAppeal.objects.count(), 1)
        self.assertEqual(ScoreAppeal.objects.first().status, ScoreAppeal.Status.OPEN)

    def test_admin_can_resolve_score_appeal(self):
        appeal = ScoreAppeal.objects.create(
            owner=self.user,
            snapshot=self.snapshot,
            reason="Need review",
            evidence={"note": "test"},
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            f"/stats/appeals/{appeal.id}/resolve/",
            {
                "status": ScoreAppeal.Status.APPROVED,
                "resolution_note": "Підтверджено після перевірки",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, ScoreAppeal.Status.APPROVED)
        self.assertEqual(appeal.resolution_note, "Підтверджено після перевірки")
