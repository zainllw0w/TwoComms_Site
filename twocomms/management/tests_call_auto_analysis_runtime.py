from io import StringIO
from datetime import timedelta
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client as TestClient, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from management.models import (
    CallAIAnalysis,
    CallRecord,
    CallSession,
    InstagramBotSettings,
)
from management import binotel_webhook
from management.services.call_ai_analysis import schedule_call_analysis
from management.services.call_auto_analysis import (
    is_call_auto_analysis_enabled,
    publish_call_auto_analysis_marker,
    set_call_auto_analysis_enabled,
)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class CallAutoAnalysisRuntimeToggleTests(TestCase):
    def test_worker_claim_locks_settings_then_rechecks_state_before_record(self):
        with TemporaryDirectory() as tmp, override_settings(BASE_DIR=tmp):
            InstagramBotSettings.objects.create(
                pk=1, call_auto_analysis_enabled=True
            )
            publish_call_auto_analysis_marker()
            record = CallRecord.objects.create(
                provider="binotel",
                external_call_id="runtime-lock-order",
                duration_seconds=65,
                payload={"disposition": "ANSWER"},
                ai_status=CallRecord.AiStatus.PENDING,
            )
            CallRecord.objects.filter(pk=record.pk).update(
                created_at=timezone.now() - timedelta(minutes=5)
            )
            events = []
            real_settings_lock = InstagramBotSettings.objects.select_for_update
            real_record_lock = CallRecord.objects.select_for_update

            def settings_lock(*args, **kwargs):
                events.append("settings_lock")
                return real_settings_lock(*args, **kwargs)

            def record_lock(*args, **kwargs):
                events.append("record_lock")
                return real_record_lock(*args, **kwargs)

            def strict_state_check():
                events.append("strict_state")
                return is_call_auto_analysis_enabled()

            def save_done_analysis(_general_call_id, *, force):
                self.assertTrue(force)
                return CallAIAnalysis.objects.create(
                    call_record=record, status=CallAIAnalysis.Status.DONE
                )

            with (
                patch.object(
                    InstagramBotSettings.objects,
                    "select_for_update",
                    side_effect=settings_lock,
                ),
                patch.object(
                    CallRecord.objects,
                    "select_for_update",
                    side_effect=record_lock,
                ),
                patch(
                    "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
                    side_effect=strict_state_check,
                ),
                patch(
                    "management.services.call_ai_analysis.analyze_call",
                    side_effect=save_done_analysis,
                ),
            ):
                call_command(
                    "run_call_ai_analyses", limit=1, stdout=StringIO()
                )

        self.assertIn("settings_lock", events)
        self.assertIn("record_lock", events)
        settings_index = events.index("settings_lock")
        record_index = events.index("record_lock")
        self.assertLess(settings_index, record_index)
        self.assertIn("strict_state", events[settings_index + 1 : record_index])

    def test_worker_treats_missing_singleton_as_off_even_with_valid_marker(self):
        with TemporaryDirectory() as tmp, override_settings(BASE_DIR=tmp):
            publish_call_auto_analysis_marker()
            record = CallRecord.objects.create(
                provider="binotel",
                external_call_id="runtime-missing-settings",
                duration_seconds=65,
                payload={"disposition": "ANSWER"},
                ai_status=CallRecord.AiStatus.PENDING,
            )
            CallRecord.objects.filter(pk=record.pk).update(
                created_at=timezone.now() - timedelta(minutes=5)
            )

            with patch(
                "management.services.call_ai_analysis.analyze_call"
            ) as analyze:
                call_command(
                    "run_call_ai_analyses", limit=1, stdout=StringIO()
                )

        record.refresh_from_db()
        self.assertEqual(record.ai_status, CallRecord.AiStatus.PENDING)
        self.assertFalse(InstagramBotSettings.objects.exists())
        analyze.assert_not_called()

    def test_schedule_does_not_create_automatic_job_when_disabled(self):
        with patch(
            "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
            return_value=False,
        ):
            schedule_call_analysis("runtime-disabled-schedule")

        self.assertFalse(
            CallRecord.objects.filter(
                provider="binotel", external_call_id="runtime-disabled-schedule"
            ).exists()
        )

    def test_schedule_rechecks_effective_state_inside_locked_transition(self):
        with patch(
            "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
            side_effect=[True, False],
        ):
            schedule_call_analysis("runtime-disabled-before-create")

        self.assertFalse(
            CallRecord.objects.filter(
                provider="binotel",
                external_call_id="runtime-disabled-before-create",
            ).exists()
        )

    def test_webhook_still_ingests_and_links_call_when_disabled(self):
        manager = get_user_model().objects.create_user(
            username="runtime-disabled-webhook"
        )
        record = CallRecord.objects.create(
            provider="binotel", external_call_id="runtime-disabled-webhook"
        )
        CallSession.objects.create(
            manager=manager,
            general_call_id=record.external_call_id,
            status=CallSession.Status.TALKING,
        )
        with patch(
            "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
            return_value=False,
        ):
            binotel_webhook._link_call_session_and_enqueue(
                record, {"disposition": "ANSWER", "bill_seconds": 65}
            )

        record.refresh_from_db()
        self.assertEqual(record.manager_id, manager.id)
        self.assertEqual(record.ai_status, CallRecord.AiStatus.NONE)

    def test_webhook_rechecks_effective_state_inside_locked_transition(self):
        record = CallRecord.objects.create(
            provider="binotel", external_call_id="runtime-webhook-disable-race"
        )

        with patch(
            "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
            side_effect=[True, False],
        ):
            binotel_webhook._link_call_session_and_enqueue(
                record, {"disposition": "ANSWER", "bill_seconds": 65}
            )

        record.refresh_from_db()
        self.assertEqual(record.ai_status, CallRecord.AiStatus.NONE)

    def test_worker_checks_canonical_state_before_heartbeat(self):
        with (
            patch(
                "management.services.binotel_runtime.is_binotel_ai_enabled",
                return_value=True,
            ),
            patch(
                "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
                return_value=False,
            ),
            patch("management.services.ig_task_health.task_heartbeat") as heartbeat,
        ):
            call_command(
                "run_call_ai_analyses", limit=1, stdout=StringIO()
            )

        heartbeat.assert_not_called()

    def test_disable_after_claim_releases_work_without_provider_call(self):
        record = CallRecord.objects.create(
            provider="binotel",
            external_call_id="runtime-disable-race",
            duration_seconds=65,
            payload={"disposition": "ANSWER"},
            ai_status=CallRecord.AiStatus.PENDING,
        )
        CallRecord.objects.filter(pk=record.pk).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )

        with (
            patch(
                "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
                side_effect=[True, True, True, True, True, False],
            ),
            patch("management.services.call_ai_analysis.analyze_call") as analyze,
        ):
            call_command("run_call_ai_analyses", limit=1, stdout=StringIO())

        record.refresh_from_db()
        self.assertEqual(record.ai_status, CallRecord.AiStatus.PENDING)
        self.assertEqual(record.ai_attempts, 0)
        self.assertIsNone(record.ai_locked_at)
        analyze.assert_not_called()

    def test_disable_after_saved_analysis_keeps_record_done(self):
        InstagramBotSettings.objects.create(
            pk=1, call_auto_analysis_enabled=True
        )
        record = CallRecord.objects.create(
            provider="binotel",
            external_call_id="runtime-disable-after-done",
            duration_seconds=65,
            payload={"disposition": "ANSWER"},
            ai_status=CallRecord.AiStatus.PENDING,
        )
        CallRecord.objects.filter(pk=record.pk).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )

        def save_done_analysis(_general_call_id, *, force):
            self.assertTrue(force)
            return CallAIAnalysis.objects.create(
                call_record=record, status=CallAIAnalysis.Status.DONE
            )

        with (
            patch(
                "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
                side_effect=[True, True, True, True, True, True, True, False],
            ),
            patch(
                "management.services.call_ai_analysis.analyze_call",
                side_effect=save_done_analysis,
            ) as analyze,
        ):
            call_command("run_call_ai_analyses", limit=1, stdout=StringIO())

        record.refresh_from_db()
        self.assertEqual(record.ai_status, CallRecord.AiStatus.DONE)
        self.assertEqual(record.ai_attempts, 1)
        self.assertIsNone(record.ai_locked_at)
        analyze.assert_called_once()

        with (
            patch(
                "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
                return_value=True,
            ),
            patch(
                "management.services.call_ai_analysis.analyze_call"
            ) as repeated_analysis,
        ):
            call_command("run_call_ai_analyses", limit=1, stdout=StringIO())

        repeated_analysis.assert_not_called()

    def test_in_flight_analysis_finishes_once_when_switch_turns_off(self):
        with TemporaryDirectory() as tmp, override_settings(BASE_DIR=tmp):
            settings_row = InstagramBotSettings.objects.create(
                pk=1, call_auto_analysis_enabled=True
            )
            publish_call_auto_analysis_marker()
            record = CallRecord.objects.create(
                provider="binotel",
                external_call_id="runtime-in-flight-disable",
                duration_seconds=65,
                payload={"disposition": "ANSWER"},
                ai_status=CallRecord.AiStatus.PENDING,
            )
            CallRecord.objects.filter(pk=record.pk).update(
                created_at=timezone.now() - timedelta(minutes=5)
            )

            def finish_after_disable(_general_call_id, *, force):
                self.assertTrue(force)
                result = CallAIAnalysis.objects.create(
                    call_record=record, status=CallAIAnalysis.Status.DONE
                )
                disabled = set_call_auto_analysis_enabled(False)
                self.assertFalse(disabled.effective_enabled)
                return result

            with patch(
                "management.services.call_ai_analysis.analyze_call",
                side_effect=finish_after_disable,
            ) as analyze:
                call_command(
                    "run_call_ai_analyses", limit=1, stdout=StringIO()
                )

            record.refresh_from_db()
            self.assertEqual(record.ai_status, CallRecord.AiStatus.DONE)
            self.assertEqual(record.ai_attempts, 1)
            self.assertIsNone(record.ai_locked_at)
            self.assertEqual(
                record.ai_analyses.filter(status=CallAIAnalysis.Status.DONE).count(),
                1,
            )
            analyze.assert_called_once()

            settings_row.refresh_from_db()
            settings_row.call_auto_analysis_enabled = True
            settings_row.save(
                update_fields=["call_auto_analysis_enabled", "updated_at"]
            )
            publish_call_auto_analysis_marker()
            with patch(
                "management.services.call_ai_analysis.analyze_call"
            ) as repeated_analysis:
                call_command(
                    "run_call_ai_analyses", limit=1, stdout=StringIO()
                )

            repeated_analysis.assert_not_called()
            self.assertEqual(
                record.ai_analyses.filter(status=CallAIAnalysis.Status.DONE).count(),
                1,
            )

    def test_schedule_resumes_after_the_canonical_state_is_enabled(self):
        with TemporaryDirectory() as tmp:
            with override_settings(BASE_DIR=tmp):
                from management.models import InstagramBotSettings

                InstagramBotSettings.objects.create(
                    pk=1, call_auto_analysis_enabled=True
                )
                publish_call_auto_analysis_marker()
                schedule_call_analysis("runtime-enabled-schedule")

        self.assertTrue(
            CallRecord.objects.filter(
                provider="binotel", external_call_id="runtime-enabled-schedule"
            ).exists()
        )

    def test_manual_analysis_is_not_blocked_by_the_automatic_switch(self):
        staff = get_user_model().objects.create_user(
            username="runtime-manual-analysis", password="x", is_staff=True
        )
        client = TestClient()
        client.force_login(staff)
        with (
            patch(
                "management.services.call_auto_analysis.is_call_auto_analysis_enabled",
                return_value=False,
            ),
            patch(
                "management.services.call_ai_analysis.analyze_call",
                return_value=SimpleNamespace(status="done"),
            ) as analyze,
            patch(
                "management.services.call_ai_analysis.serialize_analysis",
                return_value={"status": "done"},
            ),
        ):
            response = client.post(
                reverse("management_binotel_call_ai_analysis"),
                data=json.dumps({"generalCallID": "manual-when-off"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        analyze.assert_called_once()
