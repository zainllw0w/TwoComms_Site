from datetime import date

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from management.models import CommandRunLog
from management.services.telephony import build_telephony_health_summary


class TelephonyFoundationModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="telephony_mgr", password="x", is_staff=True)

    def test_telephony_models_can_persist_minimal_records(self):
        webhook_model = apps.get_model("management", "TelephonyWebhookLog")
        call_record_model = apps.get_model("management", "CallRecord")
        health_model = apps.get_model("management", "TelephonyHealthSnapshot")
        qa_model = apps.get_model("management", "CallQAReview")
        supervisor_model = apps.get_model("management", "SupervisorActionLog")
        dtf_model = apps.get_model("management", "DtfBridgeSnapshot")

        webhook = webhook_model.objects.create(
            provider="test_provider",
            external_event_id="evt-1",
            event_type="call.completed",
            payload={"external_call_id": "call-1", "phone": "+380671110000"},
        )
        call_record = call_record_model.objects.create(
            provider="test_provider",
            external_call_id="call-1",
            manager=self.user,
            phone="+380671110000",
            duration_seconds=42,
            payload={"source": "webhook"},
        )
        health = health_model.objects.create(provider="test_provider", status="healthy", total_events=1)
        qa_review = qa_model.objects.create(call_record=call_record, reviewer=self.user, score=85)
        supervisor_action = supervisor_model.objects.create(
            manager=self.user,
            actor=self.user,
            action_type="coaching",
            payload={"call_record_id": call_record.id},
        )
        dtf_snapshot = dtf_model.objects.create(
            source_key="default",
            snapshot_date=date(2026, 3, 14),
            status="degraded",
            payload={"reason": "not_configured"},
        )

        self.assertEqual(webhook.status, "pending")
        self.assertEqual(call_record.qa_status, "pending")
        self.assertEqual(health.status, "healthy")
        self.assertEqual(qa_review.verdict, "pass")
        self.assertEqual(supervisor_action.action_type, "coaching")
        self.assertEqual(dtf_snapshot.status, "degraded")

    def test_telephony_health_summary_uses_snapshot_age_when_field_is_missing(self):
        health_model = apps.get_model("management", "TelephonyHealthSnapshot")
        snapshot = health_model.objects.create(
            provider="test_provider",
            status="healthy",
            total_events=4,
            backlog_count=1,
        )
        stale_at = timezone.now() - timezone.timedelta(minutes=15)
        health_model.objects.filter(pk=snapshot.pk).update(snapshot_at=stale_at)

        summary = build_telephony_health_summary(owner=self.user)

        self.assertEqual(summary["status"], "healthy")
        self.assertEqual(summary["backlog_count"], 1)
        self.assertGreaterEqual(summary["freshness_seconds"], 14 * 60)


class TelephonyFoundationCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="telephony_cmd_mgr", password="x", is_staff=True)

    def test_process_telephony_webhooks_creates_call_record_and_run_log(self):
        webhook_model = apps.get_model("management", "TelephonyWebhookLog")
        call_record_model = apps.get_model("management", "CallRecord")
        webhook_model.objects.create(
            provider="test_provider",
            external_event_id="evt-2",
            event_type="call.completed",
            payload={
                "external_call_id": "call-2",
                "phone": "+380671110001",
                "manager_id": self.user.id,
                "duration_seconds": 64,
            },
        )

        call_command("process_telephony_webhooks")

        self.assertTrue(call_record_model.objects.filter(external_call_id="call-2").exists())
        run_log = CommandRunLog.objects.get(command_name="process_telephony_webhooks")
        self.assertEqual(run_log.status, CommandRunLog.Status.SUCCESS)
        self.assertEqual(run_log.rows_processed, 1)

    def test_reconcile_call_records_and_refresh_dtf_bridge_are_safe_without_live_integrations(self):
        health_model = apps.get_model("management", "TelephonyHealthSnapshot")
        dtf_model = apps.get_model("management", "DtfBridgeSnapshot")

        call_command("reconcile_call_records")
        call_command("refresh_dtf_bridge_snapshot")

        self.assertTrue(health_model.objects.exists())
        self.assertTrue(dtf_model.objects.exists())
        self.assertEqual(
            CommandRunLog.objects.get(command_name="reconcile_call_records").status,
            CommandRunLog.Status.SUCCESS,
        )
        self.assertEqual(
            CommandRunLog.objects.get(command_name="refresh_dtf_bridge_snapshot").status,
            CommandRunLog.Status.SUCCESS,
        )
