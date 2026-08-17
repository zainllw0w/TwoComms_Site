"""IMP-041 / IMP-059: supervise the real Instagram cron boundary."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import (
    IgBotNotification,
    IgClient,
    InstagramBotMessage,
    InstagramBotSettings,
    InstagramBotTaskHeartbeat,
)
from management.ig_bot_models import IgConversationAnalysisJob
from management.services.ig_task_health import (
    TASK_SPECS,
    check_task_health,
    ensure_task_expectations,
    mark_task_succeeded,
    task_health_snapshot,
    task_heartbeat,
    release_queue_snapshot,
)


class TaskHeartbeatTests(TestCase):
    def _mark_all_successful(self, *, at=None):
        for spec in TASK_SPECS:
            mark_task_succeeded(spec.key, at=at)

    def test_success_records_one_durable_task_row(self):
        with task_heartbeat("ig_deal_payments"):
            pass

        row = InstagramBotTaskHeartbeat.objects.get(task_key="ig_deal_payments")
        self.assertIsNotNone(row.last_started_at)
        self.assertIsNotNone(row.last_succeeded_at)
        self.assertEqual(row.consecutive_failures, 0)
        self.assertEqual(row.last_error_kind, "")

    @patch("management.services.instagram_bot.notify_manager")
    def test_failure_keeps_only_exception_kind_and_raises(self, notify):
        with self.assertRaisesRegex(RuntimeError, "private customer text"):
            with task_heartbeat("ig_deal_payments"):
                raise RuntimeError("private customer text: 0501234567")

        row = InstagramBotTaskHeartbeat.objects.get(task_key="ig_deal_payments")
        self.assertEqual(row.last_error_kind, "RuntimeError")
        self.assertNotIn("0501234567", row.last_error_kind)
        self.assertEqual(row.consecutive_failures, 1)
        notify.assert_called_once()

    def test_unobserved_task_has_a_deploy_grace_period_then_degrades(self):
        self.assertTrue(ensure_task_expectations())
        now = timezone.now()

        fresh = task_health_snapshot(now=now)
        self.assertTrue(fresh["healthy"])

        later = task_health_snapshot(now=now + timedelta(minutes=13))
        payment = next(task for task in later["tasks"] if task["key"] == "ig_deal_payments")
        self.assertEqual(payment["state"], "not_observed")
        self.assertFalse(later["healthy"])

    @patch("management.services.instagram_bot.notify_manager")
    def test_stale_tasks_are_sent_as_one_hourly_summary(self, notify):
        now = timezone.now()
        self._mark_all_successful(at=now)
        stale_at = now - timedelta(minutes=13)
        row = InstagramBotTaskHeartbeat.objects.get(task_key="ig_deal_payments")
        row.last_succeeded_at = stale_at
        row.save(update_fields=["last_succeeded_at", "updated_at"])

        snapshot = check_task_health(now=now)

        self.assertFalse(snapshot["healthy"])
        self.assertEqual(snapshot["unhealthy_count"], 1)
        notify.assert_called_once()
        self.assertEqual(notify.call_args.kwargs["event_type"], "ig_task_health")
        self.assertIn("IG operations", notify.call_args.args[0])

    def test_all_production_cron_tasks_have_an_explicit_specification(self):
        self.assertEqual(
            {spec.key for spec in TASK_SPECS},
            {
                "ig_daemon_watchdog",
                "ig_checkout_reconcile",
                "ig_order_fulfillment",
                "ig_deal_payments",
                "order_telegram_reconcile",
                "nova_poshta_tracking",
            },
        )


class CronCommandHeartbeatTests(TestCase):
    @override_settings(NOVA_POSHTA_API_KEY="")
    def test_nova_poshta_tracking_configuration_failure_is_observed(self):
        with self.assertRaisesRegex(CommandError, "NOVA_POSHTA_API_KEY"):
            call_command("update_tracking_statuses")

        self.assertTrue(
            InstagramBotTaskHeartbeat.objects.filter(
                task_key="nova_poshta_tracking",
                last_failed_at__isnull=False,
                last_error_kind="CommandError",
            ).exists()
        )

    @override_settings(NOVA_POSHTA_API_KEY="test-key")
    @patch("orders.management.commands.update_tracking_statuses.NovaPoshtaService")
    def test_nova_poshta_tracking_records_success(self, service_cls):
        service = service_cls.return_value
        queryset = MagicMock()
        queryset.count.return_value = 1
        service.get_orders_with_tracking_queryset.return_value = queryset
        service.update_all_tracking_statuses.return_value = {
            "total_orders": 1,
            "processed": 1,
            "updated": 0,
            "errors": 0,
        }

        call_command("update_tracking_statuses")

        self.assertTrue(
            InstagramBotTaskHeartbeat.objects.filter(
                task_key="nova_poshta_tracking",
                last_succeeded_at__isnull=False,
            ).exists()
        )

    @patch("management.management.commands.reconcile_ig_checkout.reconcile_ig_checkout")
    def test_checkout_reconciler_records_success(self, reconcile):
        reconcile.return_value = {"repaired": 0}

        call_command("reconcile_ig_checkout")

        self.assertTrue(
            InstagramBotTaskHeartbeat.objects.filter(
                task_key="ig_checkout_reconcile", last_succeeded_at__isnull=False
            ).exists()
        )

    @patch("management.management.commands.poll_ig_deal_payments.bot_payments.poll_pending_deals_locked")
    @patch("management.management.commands.poll_ig_deal_payments.bot_payments.reconcile_payment_projections")
    @patch("management.services.bot_orders.notify_shipped_deals", return_value=0)
    @patch("management.services.bot_orders.fulfill_ready_paid_deals", return_value=0)
    def test_payment_backstop_records_success(self, _fulfilled, _shipped, reconcile, poll):
        reconcile.return_value = 0
        poll.return_value = 0

        call_command("poll_ig_deal_payments")

        self.assertTrue(
            InstagramBotTaskHeartbeat.objects.filter(
                task_key="ig_deal_payments", last_succeeded_at__isnull=False
            ).exists()
        )


@override_settings(ALLOWED_HOSTS=["management.twocomms.shop", "testserver"])
class BotHealthEndpointTests(TestCase):
    def _make_all_tasks_healthy(self):
        for spec in TASK_SPECS:
            mark_task_succeeded(spec.key)

    def test_public_endpoint_is_ready_when_disabled_bot_and_cron_are_healthy(self):
        settings = InstagramBotSettings.load()
        settings.is_enabled = False
        settings.save(update_fields=["is_enabled", "updated_at"])
        self._make_all_tasks_healthy()

        response = self.client.get("/bot/health/", HTTP_HOST="management.twocomms.shop", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertNotIn("tasks", response.json())
        self.assertEqual(response["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")

    def test_public_endpoint_degrades_when_no_cron_heartbeat_exists(self):
        response = self.client.get("/bot/health/", HTTP_HOST="management.twocomms.shop", secure=True)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "degraded")

    def test_public_endpoint_reports_dangerous_queues_and_analysis_failures(self):
        settings = InstagramBotSettings.load()
        settings.is_enabled = False
        settings.save(update_fields=["is_enabled", "updated_at"])
        self._make_all_tasks_healthy()
        client = IgClient.objects.create(igsid="release-health-queue-client")
        InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            status=InstagramBotMessage.Status.PENDING,
            text="pending inbound",
        )
        IgBotNotification.objects.create(
            client=client,
            event_type="release-health",
            dedupe_key="release-health-queue",
            status=IgBotNotification.Status.UNKNOWN,
        )
        IgConversationAnalysisJob.objects.create(
            client=client,
            status=IgConversationAnalysisJob.Status.FAILED,
        )

        snapshot = release_queue_snapshot()
        self.assertEqual(snapshot["dangerous_backlog"], 2)
        self.assertEqual(snapshot["analysis_failed"], 1)

        response = self.client.get("/bot/health/", HTTP_HOST="management.twocomms.shop", secure=True)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["queues"]["dangerous_backlog"], 2)
        self.assertEqual(response.json()["queues"]["analysis_failed"], 1)
