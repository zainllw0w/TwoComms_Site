from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from management.models import InstagramBotTaskHeartbeat
from management.services.ig_runtime_ownership import (
    DAEMON_OWNER,
    PERIODIC_LANES,
    PERIODIC_OWNER,
    RUNTIME_LANE_OWNERS,
    lane_owner,
    validate_runtime_lane_owners,
)


class RuntimeOwnerManifestTests(TestCase):
    def test_every_lane_has_exactly_one_owner(self):
        validate_runtime_lane_owners()
        lanes = [entry.lane for entry in RUNTIME_LANE_OWNERS]
        self.assertEqual(len(lanes), len(set(lanes)))
        self.assertEqual(lane_owner("ig_deal_payments"), PERIODIC_OWNER)
        self.assertEqual(lane_owner("live_reply"), DAEMON_OWNER)

    def test_periodic_manifest_keeps_all_previous_business_lanes(self):
        self.assertEqual(
            {lane.task_key for lane in PERIODIC_LANES},
            {
                "order_telegram_reconcile",
                "ig_checkout_reconcile",
                "ig_order_fulfillment",
                "ig_deal_payments",
                "binotel_call_ai_analyses",
            },
        )


class PeriodicCoordinatorTests(TestCase):
    @patch(
        "management.management.commands.run_instagram_periodic_jobs._call_auto_analysis_enabled",
        return_value=False,
    )
    @patch("management.management.commands.run_instagram_periodic_jobs.call_command")
    def test_due_lanes_run_sequentially_without_optional_disabled_lane(
        self, child_command, _enabled
    ):
        call_command("run_instagram_periodic_jobs", stdout=StringIO())

        self.assertEqual(
            [call.args[0] for call in child_command.call_args_list],
            [
                "reconcile_order_telegram_notifications",
                "reconcile_ig_checkout",
                "reconcile_ig_order_fulfillment",
                "poll_ig_deal_payments",
            ],
        )

    @patch(
        "management.management.commands.run_instagram_periodic_jobs._call_auto_analysis_enabled",
        return_value=False,
    )
    @patch("management.management.commands.run_instagram_periodic_jobs.call_command")
    def test_recent_heartbeat_prevents_duplicate_lane_run(self, child_command, _enabled):
        now = timezone.now()
        InstagramBotTaskHeartbeat.objects.create(
            task_key="ig_checkout_reconcile",
            label="checkout",
            expected_interval_seconds=120,
            stale_after_seconds=480,
            last_started_at=now,
        )
        for lane in PERIODIC_LANES:
            if lane.task_key in {"ig_checkout_reconcile", "binotel_call_ai_analyses"}:
                continue
            InstagramBotTaskHeartbeat.objects.create(
                task_key=lane.task_key,
                label=lane.task_key,
                expected_interval_seconds=lane.interval_seconds,
                stale_after_seconds=lane.interval_seconds * 3,
                last_started_at=now - timedelta(seconds=lane.interval_seconds + 1),
            )

        call_command("run_instagram_periodic_jobs", stdout=StringIO())

        self.assertNotIn(
            "reconcile_ig_checkout",
            [call.args[0] for call in child_command.call_args_list],
        )

    @patch(
        "management.management.commands.run_instagram_periodic_jobs._call_auto_analysis_enabled",
        return_value=False,
    )
    @patch("management.management.commands.run_instagram_periodic_jobs.call_command")
    def test_one_lane_failure_does_not_starve_following_lanes(
        self, child_command, _enabled
    ):
        child_command.side_effect = [RuntimeError("private"), None, None, None]

        with self.assertRaisesMessage(CommandError, "order_telegram_reconcile:RuntimeError"):
            call_command("run_instagram_periodic_jobs", stdout=StringIO())

        self.assertEqual(child_command.call_count, 4)

    def test_force_requires_an_explicit_lane(self):
        with self.assertRaisesMessage(CommandError, "--force requires --lane"):
            call_command("run_instagram_periodic_jobs", force=True, stdout=StringIO())

    @patch(
        "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
        side_effect=RuntimeError("toggle unavailable"),
    )
    @patch("management.management.commands.run_instagram_periodic_jobs.call_command")
    def test_optional_gate_failure_does_not_starve_critical_lanes(
        self, child_command, _enabled
    ):
        call_command("run_instagram_periodic_jobs", stdout=StringIO())

        self.assertEqual(child_command.call_count, 4)
        self.assertNotIn(
            "run_call_ai_analyses",
            [call.args[0] for call in child_command.call_args_list],
        )
