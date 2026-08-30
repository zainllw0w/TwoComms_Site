"""Disposable MariaDB concurrency proof for Gemini S3b shadow accounting.

Run only through ``test_settings_mariadb`` and an explicitly disposable
``test_twocomms_*`` database.  The normal SQLite suite skips this module.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from management.models import GeminiQuotaState, GeminiRequestAttempt
from management.services import gemini_accounting_runtime as runtime


@skipUnless(connection.vendor == "mysql", "Disposable MariaDB-only S3b proof")
@override_settings(
    GEMINI_ACCOUNTING_V2_MODE="shadow",
    GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM="2026-08-29T00:00:00-07:00",
    GEMINI_ACCOUNTING_IDENTITY_HMAC_KEY="maria-shadow-test-hmac-key",
    GEMINI_KEY_PROJECT_GROUPS={"GEMINI_API": "gemini-project-race"},
)
class GeminiShadowMariaDbConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_database_is_explicitly_disposable(self):
        self.assertRegex(
            str(connection.settings_dict.get("NAME") or ""),
            r"^test_twocomms_[A-Za-z0-9_]+$",
        )

    def test_two_real_dispatches_survive_last_permit_race_and_settle(self):
        model = "gemini-3.7-flash"
        start = Barrier(2)
        dispatched = Barrier(2)

        def worker(index: int):
            close_old_connections()
            try:
                observer = runtime.begin_request(
                    request_id=f"maria-shadow-race-{index}",
                    role="management",
                    reasoning_task="customer_intelligence",
                    candidate_plan=[{
                        "candidate_index": 1,
                        "key_name": "GEMINI_API",
                        "project_identity": "gemini-project-race",
                        "identity_status": "known",
                        "model": model,
                        "skip_reason": "",
                    }],
                    lane="analysis",
                )
                boundary = observer.attempt(
                    key_name="GEMINI_API", model=model, candidate_index=1
                )
                start.wait(timeout=10)
                boundary.before_provider(serialized_bytes=128, inline_count=0)
                self.assertIsNotNone(boundary.attempt_id)
                dispatched.wait(timeout=10)
                boundary.manual_result(
                    succeeded=True,
                    http_code=200,
                    usage={
                        "promptTokenCount": 12,
                        "candidatesTokenCount": 2,
                        "totalTokenCount": 14,
                    },
                )
                return boundary.attempt_id
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            attempt_ids = list(executor.map(worker, (1, 2)))

        self.assertEqual(len(set(attempt_ids)), 2)
        rows = GeminiRequestAttempt.objects.filter(pk__in=attempt_ids)
        self.assertEqual(rows.count(), 2)
        self.assertEqual(
            rows.filter(fsm_state=GeminiRequestAttempt.FsmState.SUCCEEDED).count(),
            2,
        )
        state = GeminiQuotaState.objects.get(
            project_identity="gemini-project-race", model=model
        )
        self.assertEqual(state.rpd_dispatched, 2)
        self.assertEqual(state.in_flight_count, 0)
        # The second dispatch is observed even if the one-per-model shadow
        # permit would have denied it; shadow never changes provider behavior.
        self.assertEqual(
            rows.filter(
                shadow_decision=GeminiRequestAttempt.ShadowDecision.DENY,
                shadow_deny_reason="permit_exhausted",
            ).count(),
            1,
        )
