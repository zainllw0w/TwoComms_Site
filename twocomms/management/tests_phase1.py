from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone


class ManagementFoundationSeedTests(TestCase):
    def test_seed_management_defaults_creates_singleton_config_and_readiness_rows(self):
        call_command("seed_management_defaults")

        config_model = apps.get_model("management", "ManagementStatsConfig")
        readiness_model = apps.get_model("management", "ComponentReadiness")

        config = config_model.objects.get(pk=1)
        self.assertEqual(config.rollout_state, "shadow")
        self.assertEqual(config.formula_version, "mosaic-v1")
        self.assertEqual(config.defaults_version, "2026-03-13")
        self.assertEqual(config.snapshot_schema_version, "v1")
        self.assertEqual(config.payload_version, "v1")

        components = set(readiness_model.objects.values_list("component", flat=True))
        self.assertTrue(
            {
                "result",
                "source_fairness",
                "process",
                "follow_up",
                "data_quality",
                "verified_communication",
                "telephony",
                "dtf_bridge",
            }.issubset(components)
        )

    def test_seed_management_defaults_is_idempotent(self):
        call_command("seed_management_defaults")
        call_command("seed_management_defaults")

        config_model = apps.get_model("management", "ManagementStatsConfig")
        readiness_model = apps.get_model("management", "ComponentReadiness")

        self.assertEqual(config_model.objects.count(), 1)
        self.assertEqual(readiness_model.objects.count(), 8)


class NightlyScoreSnapshotModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="snapshot_mgr", password="x")

    def test_snapshot_is_unique_per_manager_day(self):
        snapshot_model = apps.get_model("management", "NightlyScoreSnapshot")

        snapshot_model.objects.create(
            owner=self.user,
            snapshot_date=timezone.localdate(),
            formula_version="mosaic-v1",
            defaults_version="2026-03-13",
            snapshot_schema_version="v1",
            payload_version="v1",
            kpd_value=Decimal("2.50"),
            mosaic_score=Decimal("58.40"),
            score_confidence=Decimal("0.82"),
            working_day_factor=Decimal("1.00"),
            payload={"state": "shadow"},
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                snapshot_model.objects.create(
                    owner=self.user,
                    snapshot_date=timezone.localdate(),
                    formula_version="mosaic-v1",
                    defaults_version="2026-03-13",
                    snapshot_schema_version="v1",
                    payload_version="v1",
                    kpd_value=Decimal("2.40"),
                    mosaic_score=Decimal("59.10"),
                    score_confidence=Decimal("0.80"),
                    working_day_factor=Decimal("1.00"),
                    payload={"state": "shadow"},
                )


class CommandRunLogModelTests(TestCase):
    def test_mark_finished_updates_run_log_fields(self):
        log_model = apps.get_model("management", "CommandRunLog")

        log = log_model.objects.create(
            command_name="seed_management_defaults",
            run_key="seed-management-defaults",
            status="running",
        )
        log.mark_finished(status="success", rows_processed=8, warnings_count=1)
        log.refresh_from_db()

        self.assertEqual(log.status, "success")
        self.assertEqual(log.rows_processed, 8)
        self.assertEqual(log.warnings_count, 1)
        self.assertIsNotNone(log.finished_at)


class ManagerDayStatusModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ledger_mgr", password="x")

    def test_capacity_factor_is_clamped_and_day_is_unique(self):
        day_status_model = apps.get_model("management", "ManagerDayStatus")

        first = day_status_model.objects.create(
            owner=self.user,
            day=timezone.localdate(),
            status="tech_failure",
            capacity_factor=Decimal("1.80"),
            source_reason="provider outage",
            reintegration_flag=False,
        )
        first.refresh_from_db()

        self.assertEqual(first.capacity_factor, Decimal("1.00"))

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                day_status_model.objects.create(
                    owner=self.user,
                    day=timezone.localdate(),
                    status="working",
                    capacity_factor=Decimal("0.50"),
                    source_reason="duplicate",
                    reintegration_flag=False,
                )


class ScoreAppealModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="appeal_mgr", password="x")
        self.snapshot_model = apps.get_model("management", "NightlyScoreSnapshot")

    def test_resolve_marks_appeal_as_resolved(self):
        snapshot = self.snapshot_model.objects.create(
            owner=self.user,
            snapshot_date=timezone.localdate(),
            formula_version="mosaic-v1",
            defaults_version="2026-03-13",
            snapshot_schema_version="v1",
            payload_version="v1",
            kpd_value=Decimal("2.10"),
            mosaic_score=Decimal("55.00"),
            score_confidence=Decimal("0.74"),
            working_day_factor=Decimal("0.80"),
            payload={"state": "shadow"},
        )

        appeal_model = apps.get_model("management", "ScoreAppeal")
        appeal = appeal_model.objects.create(
            owner=self.user,
            snapshot=snapshot,
            status="open",
            reason="Incorrect workload factor",
            evidence={"day": str(snapshot.snapshot_date)},
        )
        appeal.mark_resolved("approved", "Adjusted after ledger review")
        appeal.refresh_from_db()

        self.assertEqual(appeal.status, "approved")
        self.assertEqual(appeal.resolution_note, "Adjusted after ledger review")
        self.assertIsNotNone(appeal.resolved_at)
