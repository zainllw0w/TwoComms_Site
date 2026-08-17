from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import Client as TestClient, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from management.models import CallRecord, CallSession, InstagramBotSettings, InstagramBotTaskHeartbeat
from management import binotel_webhook
from management.services.call_ai_analysis import schedule_call_analysis
from management.services.binotel_runtime import is_binotel_ai_enabled
from management.services.ig_task_health import (
    TASK_SPECS,
    check_task_health,
    mark_task_succeeded,
    release_queue_snapshot,
    task_health_snapshot,
)
from management.tests_call_auto_analysis_helpers import disable_call_auto_analysis


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class BinotelAiToggleTests(TransactionTestCase):
    def setUp(self):
        disable_call_auto_analysis(self)

    def test_toggle_read_fails_closed(self):
        with patch(
            "management.models.InstagramBotSettings.objects.filter",
            side_effect=DatabaseError("settings unavailable"),
        ):
            self.assertFalse(is_binotel_ai_enabled())

    def test_disabled_webhook_keeps_call_link_but_does_not_enqueue(self):
        manager = get_user_model().objects.create_user(username="disabled-binotel-manager")
        record = CallRecord.objects.create(provider="binotel", external_call_id="disabled-webhook")
        CallSession.objects.create(
            manager=manager,
            general_call_id=record.external_call_id,
            status=CallSession.Status.TALKING,
        )
        binotel_webhook._link_call_session_and_enqueue(
            record, {"disposition": "ANSWER", "bill_seconds": 65}
        )
        record.refresh_from_db()
        self.assertEqual(record.ai_status, CallRecord.AiStatus.NONE)
        self.assertEqual(record.manager_id, manager.id)

    def test_disabled_schedule_does_not_create_placeholder(self):
        schedule_call_analysis("disabled-1")
        self.assertFalse(CallRecord.objects.filter(external_call_id="disabled-1").exists())

    def test_disabled_worker_is_noop_without_heartbeat_or_queue_work(self):
        CallRecord.objects.create(
            provider="binotel",
            external_call_id="queued-1",
            ai_status=CallRecord.AiStatus.PENDING,
        )
        with patch(
            "management.models.CallRecord.objects.filter",
            side_effect=AssertionError("disabled worker must not inspect the queue"),
        ), patch("management.services.ig_task_health.task_heartbeat") as heartbeat:
            call_command("run_call_ai_analyses", limit=1, stdout=StringIO())
        heartbeat.assert_not_called()
        self.assertFalse(InstagramBotTaskHeartbeat.objects.filter(task_key="binotel_call_ai_analyses").exists())

    def test_disabled_health_is_healthy_and_does_not_alert(self):
        now = __import__("django.utils.timezone", fromlist=["now"]).now()
        for spec in TASK_SPECS:
            if spec.key != "binotel_call_ai_analyses":
                mark_task_succeeded(spec.key, at=now)
        with patch("management.services.instagram_bot.notify_manager") as notify:
            snapshot = check_task_health()
        self.assertNotIn(
            "binotel_call_ai_analyses", {item["key"] for item in snapshot["tasks"]}
        )
        self.assertTrue(snapshot["healthy"])
        notify.assert_not_called()

    def test_disabled_backlog_is_excluded_from_release_queue(self):
        CallRecord.objects.create(
            provider="binotel",
            external_call_id="queued-2",
            ai_status=CallRecord.AiStatus.PENDING,
        )
        snapshot = release_queue_snapshot()
        self.assertEqual(snapshot["binotel_eligible_pending"], 0)
        self.assertEqual(snapshot["binotel_metadata_pending"], 0)
        self.assertEqual(snapshot["binotel_stale_running"], 0)

    def test_toggle_endpoint_persists_and_reenable_allows_queue(self):
        staff = get_user_model().objects.create_user(username="binotel-admin", password="x", is_staff=True)
        client = TestClient()
        client.force_login(staff)
        url = reverse("management_binotel_ai_toggle")
        response = client.post(url, data={"enabled": True}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["effective"])
        self.assertTrue(InstagramBotSettings.load().call_auto_analysis_enabled)
        schedule_call_analysis("reenabled-1")
        self.assertTrue(CallRecord.objects.filter(external_call_id="reenabled-1").exists())
