"""Health and release-boundary contract for disabled call auto-analysis."""

from datetime import timedelta
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.utils import timezone

from management.models import CallRecord, InstagramBotTaskHeartbeat
from management.services.ig_task_health import (
    TASK_SPECS,
    check_task_health,
    ensure_task_expectations,
    mark_task_succeeded,
    release_queue_snapshot,
    task_health_snapshot,
)


CALL_TASK_KEY = "binotel_call_ai_analyses"
OTHER_TASK_KEYS = {spec.key for spec in TASK_SPECS} - {CALL_TASK_KEY}


class DisabledCallAutoAnalysisHealthTests(TestCase):
    def _mark_other_tasks_successful(self, *, at):
        for task_key in OTHER_TASK_KEYS:
            mark_task_succeeded(task_key, at=at)

    @patch(
        "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
        return_value=False,
    )
    def test_expectation_refresh_registers_only_six_active_owners(self, _enabled):
        self.assertTrue(ensure_task_expectations())

        self.assertSetEqual(
            set(
                InstagramBotTaskHeartbeat.objects.values_list(
                    "task_key", flat=True
                )
            ),
            OTHER_TASK_KEYS,
        )
        self.assertEqual(len(OTHER_TASK_KEYS), 6)

    @patch(
        "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
        return_value=False,
    )
    def test_expectation_refresh_preserves_historical_call_heartbeat(self, _enabled):
        observed_at = timezone.now() - timedelta(hours=1)
        historical = mark_task_succeeded(CALL_TASK_KEY, at=observed_at)

        self.assertTrue(ensure_task_expectations())

        historical.refresh_from_db()
        self.assertEqual(historical.last_succeeded_at, observed_at)
        self.assertEqual(
            InstagramBotTaskHeartbeat.objects.filter(
                task_key=CALL_TASK_KEY
            ).count(),
            1,
        )

    @patch(
        "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
        return_value=False,
    )
    def test_snapshot_omits_disabled_call_owner_instead_of_synthesizing_it(self, _enabled):
        now = timezone.now()
        self._mark_other_tasks_successful(at=now)
        mark_task_succeeded(CALL_TASK_KEY, at=now - timedelta(hours=1))

        snapshot = task_health_snapshot(now=now)

        self.assertTrue(snapshot["healthy"])
        self.assertNotIn(CALL_TASK_KEY, {task["key"] for task in snapshot["tasks"]})
        self.assertNotIn("disabled", {task["state"] for task in snapshot["tasks"]})

    @patch("management.services.ig_alerts.alert_dedupe_key", return_value="dedupe")
    @patch("management.services.instagram_bot.notify_manager")
    @patch(
        "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
        return_value=False,
    )
    def test_stale_call_owner_is_absent_from_alert_and_fingerprint(
        self, _enabled, notify_manager, alert_dedupe_key
    ):
        now = timezone.now()
        self._mark_other_tasks_successful(at=now)
        mark_task_succeeded(CALL_TASK_KEY, at=now - timedelta(hours=1))
        payment = InstagramBotTaskHeartbeat.objects.get(task_key="ig_deal_payments")
        payment.last_succeeded_at = now - timedelta(minutes=13)
        payment.save(update_fields=["last_succeeded_at", "updated_at"])

        snapshot = check_task_health(now=now)

        self.assertEqual(snapshot["unhealthy_count"], 1)
        self.assertEqual(
            [task["key"] for task in snapshot["tasks"] if not task["healthy"]],
            ["ig_deal_payments"],
        )
        notify_manager.assert_called_once()
        self.assertNotIn("Автоаналіз дзвінків", notify_manager.call_args.args[0])
        self.assertEqual(
            alert_dedupe_key.call_args.kwargs["text"],
            "ig_deal_payments:stale",
        )

    @patch("management.services.ig_alerts.alert_dedupe_key", return_value="dedupe")
    @patch("management.services.instagram_bot.notify_manager")
    @patch(
        "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
        side_effect=DatabaseError("toggle unavailable"),
    )
    def test_toggle_read_error_fails_closed_without_hiding_other_stale_owner(
        self, _enabled, notify_manager, alert_dedupe_key
    ):
        now = timezone.now()
        self._mark_other_tasks_successful(at=now)
        payment = InstagramBotTaskHeartbeat.objects.get(task_key="ig_deal_payments")
        payment.last_succeeded_at = now - timedelta(minutes=13)
        payment.save(update_fields=["last_succeeded_at", "updated_at"])

        snapshot = check_task_health(now=now)

        self.assertEqual(snapshot["unhealthy_count"], 1)
        self.assertEqual(
            alert_dedupe_key.call_args.kwargs["text"],
            "ig_deal_payments:stale",
        )
        notify_manager.assert_called_once()

    @patch(
        "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
        return_value=False,
    )
    def test_release_snapshot_does_not_query_or_count_saved_call_backlog(self, _enabled):
        CallRecord.objects.create(
            provider="binotel",
            external_call_id="saved-disabled-backlog",
            duration_seconds=65,
            payload={"disposition": "ANSWER"},
            ai_status=CallRecord.AiStatus.PENDING,
        )

        with patch(
            "management.models.CallRecord.objects.filter"
        ) as call_filter:
            snapshot = release_queue_snapshot()

        call_filter.assert_not_called()
        self.assertEqual(snapshot["dangerous_backlog"], 0)
        self.assertEqual(snapshot["binotel_eligible_pending"], 0)
        self.assertEqual(snapshot["binotel_metadata_pending"], 0)
        self.assertEqual(snapshot["binotel_ineligible_pending"], 0)
        self.assertEqual(snapshot["binotel_stale_running"], 0)
        self.assertEqual(snapshot["binotel_error"], 0)


class EnabledCallAutoAnalysisHealthTests(TestCase):
    @patch(
        "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
        return_value=True,
    )
    def test_enabled_expectation_refresh_keeps_seventh_owner(self, _enabled):
        self.assertTrue(ensure_task_expectations())

        self.assertSetEqual(
            set(
                InstagramBotTaskHeartbeat.objects.values_list(
                    "task_key", flat=True
                )
            ),
            {spec.key for spec in TASK_SPECS},
        )
