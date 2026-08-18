import datetime
import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import GeminiRequestAttempt
from management.services import gemini_health


UTC = datetime.timezone.utc


class GeminiHealthSnapshotTests(TestCase):
    def setUp(self):
        self.now = datetime.datetime(2026, 8, 18, 12, 0, tzinfo=UTC)

        self.pool = [
            {
                "key_name": key_name,
                "present": key_name in {"GEMINI_API", "GEMINI_API2", "GEMINI_API3"},
                "health_state": "available" if key_name != "GEMINI_API3" else "cooldown",
                "role": "chat",
                "project_group": "",
                "project_identity_known": False,
                "available": key_name != "GEMINI_API3",
                "cooldown_until": None,
                "cooldown_scope": "",
                "seconds_remaining": 0,
                "requests_today": 0,
                "last_status": "",
                "needs_topup": False,
                "last_ok_at": None,
                "last_probe_at": None,
                "last_probe_status": "",
                "last_probe_model": "",
                "last_probe_latency_ms": 0,
                "last_probe_finish_reason": "",
                "last_probe_http_code": None,
                "last_probe_error": "",
            }
            for key_name in gemini_health.KEY_ALIASES
        ]

    def _attempt(self, *, request_id, key_name, model, outcome, at, failure_kind="", **kwargs):
        row = GeminiRequestAttempt.objects.create(
            request_id=request_id,
            role="chat",
            key_name=key_name,
            model=model,
            outcome=outcome,
            failure_kind=failure_kind,
            provider_reason=kwargs.get("provider_reason", ""),
            decision=kwargs.get("decision", ""),
            latency_ms=kwargs.get("latency_ms", 0),
        )
        GeminiRequestAttempt.objects.filter(pk=row.pk).update(created_at=at)
        return row

    def _build(self):
        with patch.object(gemini_health.gemini_keys, "pool_status", return_value=self.pool):
            return gemini_health.build_snapshot(now=self.now)

    def test_empty_pool_is_stable_six_rows_with_gray_24_bucket_histories(self):
        snapshot = self._build()

        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["window"]["hours"], 24)
        self.assertEqual(snapshot["window"]["bucket_count"], 24)
        self.assertEqual([row["alias"] for row in snapshot["keys"]], [
            "API key 1", "API key 2", "API key 3",
            "API key 4", "API key 5", "API key 6",
        ])
        self.assertEqual(len(snapshot["keys"]), 6)
        for row in snapshot["keys"]:
            for model in gemini_health.DISPLAY_MODELS:
                model_snapshot = row["models"][model]
                self.assertEqual(model_snapshot["status"], "no_observation")
                self.assertEqual(
                    [bucket["status"] for bucket in model_snapshot["history"]],
                    ["no_observation"] * 24,
                )
        self.assertEqual(
            snapshot["summary"]["models"]["gemini-3.7-flash"]["status"],
            "insufficient_observations",
        )
        self.assertEqual(
            snapshot["summary"]["models"]["gemini-3.6-flash"]["status"],
            "insufficient_observations",
        )

    def test_success_recovered_retry_and_terminal_failure_have_distinct_statuses(self):
        self._attempt(
            request_id="success-request",
            key_name="GEMINI_API",
            model="gemini-3.7-flash",
            outcome="succeeded",
            at=self.now - datetime.timedelta(minutes=20),
            latency_ms=111,
        )
        retry_at = self.now - datetime.timedelta(hours=2, minutes=10)
        self._attempt(
            request_id="recovered-request",
            key_name="GEMINI_API2",
            model="gemini-3.7-flash",
            outcome="failed",
            failure_kind="read_timeout",
            at=retry_at,
        )
        self._attempt(
            request_id="recovered-request",
            key_name="GEMINI_API2",
            model="gemini-3.7-flash",
            outcome="succeeded",
            at=retry_at + datetime.timedelta(minutes=1),
            latency_ms=222,
        )
        self._attempt(
            request_id="terminal-request",
            key_name="GEMINI_API3",
            model="gemini-3.7-flash",
            outcome="failed",
            failure_kind="quota_429",
            at=self.now - datetime.timedelta(hours=3),
        )

        snapshot = self._build()
        by_alias = {row["alias"]: row for row in snapshot["keys"]}
        self.assertEqual(
            by_alias["API key 1"]["models"]["gemini-3.7-flash"]["status"],
            "success",
        )
        self.assertEqual(
            by_alias["API key 2"]["models"]["gemini-3.7-flash"]["status"],
            "recovered",
        )
        self.assertEqual(
            by_alias["API key 3"]["models"]["gemini-3.7-flash"]["status"],
            "terminal",
        )

    def test_fallback_is_emitted_only_for_proven_37_failure_then_36_success(self):
        at = self.now - datetime.timedelta(minutes=4)
        self._attempt(
            request_id="proven-fallback",
            key_name="GEMINI_API",
            model="gemini-3.7-flash",
            outcome="failed",
            failure_kind="read_timeout",
            provider_reason="provider secret detail must not escape",
            at=at,
        )
        self._attempt(
            request_id="proven-fallback",
            key_name="GEMINI_API",
            model="gemini-3.6-flash",
            outcome="succeeded",
            at=at + datetime.timedelta(seconds=2),
        )
        self._attempt(
            request_id="unproven-success",
            key_name="GEMINI_API2",
            model="gemini-3.6-flash",
            outcome="succeeded",
            at=self.now - datetime.timedelta(minutes=2),
        )

        snapshot = self._build()
        fallback = snapshot["fallback"]
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback["from_model"], "gemini-3.7-flash")
        self.assertEqual(fallback["to_model"], "gemini-3.6-flash")
        self.assertEqual(fallback["reason"], "3.7 timed out")
        serialized = json.dumps(snapshot)
        self.assertNotIn("provider secret detail", serialized)
        self.assertNotIn("read_timeout", serialized)
        self.assertNotIn("GEMINI_API", serialized)
        self.assertNotIn("secret", serialized)

    def test_window_and_query_cap_ignore_old_and_excess_rows(self):
        self._attempt(
            request_id="old",
            key_name="GEMINI_API",
            model="gemini-3.7-flash",
            outcome="succeeded",
            at=self.now - datetime.timedelta(hours=25),
        )
        for index in range(4):
            self._attempt(
                request_id=f"recent-{index}",
                key_name="GEMINI_API2",
                model="gemini-3.7-flash",
                outcome="succeeded",
                at=self.now - datetime.timedelta(minutes=index + 1),
            )

        with patch.object(gemini_health, "ATTEMPT_QUERY_CAP", 2):
            snapshot = self._build()

        by_alias = {row["alias"]: row for row in snapshot["keys"]}
        self.assertEqual(
            by_alias["API key 1"]["models"]["gemini-3.7-flash"]["status"],
            "no_observation",
        )
        self.assertEqual(
            by_alias["API key 2"]["models"]["gemini-3.7-flash"]["observations"],
            2,
        )

    def test_snapshot_is_json_safe_and_pool_state_is_not_secret_bearing(self):
        snapshot = self._build()
        json.dumps(snapshot)
        serialized = json.dumps(snapshot)
        self.assertNotIn("key_value", serialized)
        self.assertNotIn("api_key", serialized.lower())
