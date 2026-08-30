import datetime as dt
import json
import os
from pathlib import Path
from unittest.mock import patch

import requests
from django.db import DatabaseError, connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from management.models import (
    GeminiQuotaProfile,
    GeminiQuotaState,
    GeminiRequest,
    GeminiRequestAttempt,
)
from management.services import call_ai_analysis as ai
from management.services import gemini_accounting_runtime as runtime
from management.services import gemini_probe
from management.services.gemini_routing import TurnFacts, classify_live_turn
from management.services.ig_turn_lineage import Lane, turn_lineage


SHADOW_FROM = "2026-08-29T00:00:00-07:00"
SHADOW = {
    "GEMINI_ACCOUNTING_V2_MODE": "shadow",
    "GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM": SHADOW_FROM,
    "GEMINI_ACCOUNTING_IDENTITY_HMAC_KEY": "shadow-test-hmac-key",
    "GEMINI_KEY_PROJECT_GROUPS": {
        "GEMINI_API": "gemini-project-1",
        "GEMINI_API2": "gemini-project-2",
        "GEMINI_API3": "gemini-project-3",
        "GEMINI_API4": "gemini-project-4",
        "GEMINI_API5": "gemini-project-5",
        "GEMINI_API6": "gemini-project-6",
    },
}
KEY_ENV = {
    "GEMINI_API": "shadow-key-1",
    "GEMINI_API2": "",
    "GEMINI_API3": "",
    "GEMINI_API4": "",
    "GEMINI_API5": "",
    "GEMINI_API6": "shadow-key-6",
}


class _Response:
    def __init__(self, code=200, payload=None):
        self.status_code = code
        self._payload = payload if payload is not None else {
            "candidates": [{
                "finishReason": "STOP",
                "content": {"parts": [{"text": "ok"}]},
            }],
            "usageMetadata": {
                "promptTokenCount": 11,
                "candidatesTokenCount": 3,
                "totalTokenCount": 14,
            },
        }
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


def _raw_plan(model="gemini-3.7-flash", *, identity="gemini-project-1"):
    return [{
        "candidate_index": 1,
        "key_name": "GEMINI_API",
        "key_value": "must-never-be-persisted",
        "project_identity": identity,
        "identity_status": "known" if identity else "unknown",
        "model": model,
        "skip_reason": "",
        "prompt": "customer-sentinel-must-not-be-persisted",
    }]


class GeminiShadowPureContractTests(SimpleTestCase):
    def test_effective_gate_requires_aware_pacific_midnight(self):
        valid = runtime.parse_effective_from(SHADOW_FROM)
        self.assertTrue(runtime.is_pacific_midnight(valid))
        self.assertFalse(runtime.is_pacific_midnight(runtime.parse_effective_from("2026-08-29T01:00:00-07:00")))
        self.assertIsNone(runtime.parse_effective_from("2026-08-29T00:00:00"))

    def test_candidate_plan_has_an_exact_privacy_allowlist(self):
        safe = runtime.sanitize_candidate_plan(_raw_plan())
        self.assertEqual(set(safe[0]), runtime._PLAN_FIELDS)
        encoded = json.dumps(safe, sort_keys=True)
        self.assertNotIn("GEMINI_API", encoded)
        self.assertNotIn("must-never", encoded)
        self.assertNotIn("customer-sentinel", encoded)

    @override_settings(**SHADOW)
    @patch.dict(
        os.environ,
        {
            "GEMINI_API3": "same-private-credential",
            "GEMINI_API4": "same-private-credential",
            "GEMINI_API5": "",
            "GEMINI_API6": "",
        },
        clear=False,
    )
    def test_hmac_detects_env_and_manual_duplicates_without_persisting_digest(self):
        from management.services import gemini_keys

        plan = runtime.generic_candidate_plan(
            role="management",
            models=["gemini-3.6-flash"],
            manual_key="same-private-credential",
        )
        duplicate_rows = [
            row for row in plan if row.get("identity_status") == "duplicate"
        ]
        self.assertGreaterEqual(len(duplicate_rows), 2)
        safe = runtime.sanitize_candidate_plan(plan)
        encoded = json.dumps(safe, sort_keys=True)
        fingerprint = gemini_keys.credential_fingerprint("same-private-credential")
        self.assertTrue(fingerprint)
        self.assertNotIn("same-private-credential", encoded)
        self.assertNotIn(fingerprint.hex(), encoded)
        self.assertFalse(any("key_name" in row for row in safe))

    @override_settings(
        GEMINI_ACCOUNTING_V2_MODE="shadow",
        GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM="2026-08-29T01:00:00-07:00",
    )
    def test_invalid_midnight_gate_fails_closed(self):
        self.assertFalse(runtime.shadow_runtime_active())

    def test_only_registered_python_files_contain_generation_boundary(self):
        root = Path(__file__).resolve().parents[1]
        found = set()
        for path in root.rglob("*.py"):
            if "tests" in path.name or "migrations" in path.parts:
                continue
            if ":generateContent" in path.read_text(encoding="utf-8"):
                found.add(path.relative_to(root).as_posix())
        self.assertEqual(found, {
            "management/services/call_ai_analysis.py",
            "management/services/gemini_probe.py",
        })

    @override_settings(GEMINI_ACCOUNTING_V2_MODE="enforced")
    def test_system_check_rejects_non_s3b_mode(self):
        from management.checks import gemini_accounting_shadow_check

        self.assertEqual(
            [item.id for item in gemini_accounting_shadow_check()],
            ["management.E910"],
        )

    @override_settings(
        GEMINI_ACCOUNTING_V2_MODE="shadow",
        GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM="2026-08-29T02:00:00-07:00",
    )
    def test_system_check_rejects_non_midnight_shadow_gate(self):
        from management.checks import gemini_accounting_shadow_check

        self.assertEqual(
            [item.id for item in gemini_accounting_shadow_check()],
            ["management.E911"],
        )

    @override_settings(**{
        **SHADOW,
        "GEMINI_KEY_PROJECT_GROUPS": {
            "GEMINI_API": "same-project",
            "GEMINI_API2": "same-project",
        },
    })
    @patch.dict(os.environ, {"GEMINI_API": "one", "GEMINI_API2": "two"}, clear=False)
    def test_system_check_rejects_duplicate_project_identity(self):
        from management.checks import gemini_accounting_shadow_check

        self.assertIn(
            "management.E913",
            [item.id for item in gemini_accounting_shadow_check()],
        )

    @override_settings(
        GEMINI_ACCOUNTING_V2_MODE="shadow",
        GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM=SHADOW_FROM,
        GEMINI_ACCOUNTING_IDENTITY_HMAC_KEY="shadow-test-hmac-key",
        GEMINI_KEY_PROJECT_GROUPS={},
    )
    @patch.dict(os.environ, {key: "" for key in KEY_ENV} | {"GEMINI_API": "one"}, clear=False)
    def test_system_check_does_not_treat_default_labels_as_explicit_mapping(self):
        from management.checks import gemini_accounting_shadow_check

        self.assertIn(
            "management.E916",
            [item.id for item in gemini_accounting_shadow_check()],
        )

    @override_settings(**{**SHADOW, "GEMINI_ACCOUNTING_IDENTITY_HMAC_KEY": ""})
    @patch.dict(os.environ, {key: "" for key in KEY_ENV}, clear=False)
    def test_system_check_labels_secret_key_hmac_as_shadow_only_fallback(self):
        from management.checks import gemini_accounting_shadow_check

        self.assertIn(
            "management.W915",
            [item.id for item in gemini_accounting_shadow_check()],
        )


class GeminiShadowRuntimeTests(TestCase):
    def _observer(self, model="gemini-3.7-flash", *, identity="gemini-project-1", lane="analysis"):
        return runtime.begin_request(
            request_id=uuid_for_test(),
            role="management",
            reasoning_task="customer_intelligence",
            candidate_plan=_raw_plan(model, identity=identity),
            lane=lane,
        )

    @override_settings(GEMINI_ACCOUNTING_V2_MODE="off", GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM="")
    @patch.dict(os.environ, KEY_ENV, clear=False)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_default_off_has_absolute_zero_v2_rows(self, _post):
        with CaptureQueriesContext(connection) as captured:
            out = ai.gemini_generate_text(
                {"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
                role="management",
                reasoning_task="memory_summary",
            )
        self.assertEqual(out["parsed"], "ok")
        accounting_sql = "\n".join(query["sql"].casefold() for query in captured)
        self.assertNotIn("management_geminirequest\"", accounting_sql)
        self.assertNotIn("management_geminiquotastate", accounting_sql)
        self.assertEqual(GeminiRequest.objects.count(), 0)
        self.assertEqual(GeminiQuotaState.objects.count(), 0)
        self.assertEqual(
            GeminiRequestAttempt.objects.exclude(fsm_state=GeminiRequestAttempt.FsmState.LEGACY).count(),
            0,
        )

    @override_settings(**SHADOW)
    def test_begin_request_is_one_write_and_plan_is_sanitized(self):
        with CaptureQueriesContext(connection) as captured:
            observer = self._observer()
        self.assertTrue(observer.enabled)
        self.assertLessEqual(len([q for q in captured if q["sql"].lstrip().upper().startswith("SELECT")]), 0)
        graph = GeminiRequest.objects.get(pk=observer.graph_id)
        encoded = json.dumps(graph.candidate_plan, sort_keys=True)
        self.assertNotIn("GEMINI_API", encoded)
        self.assertNotIn("must-never", encoded)
        self.assertNotIn("customer-sentinel", encoded)

    @override_settings(**SHADOW)
    @patch.dict(
        os.environ,
        {
            "GEMINI_API3": "db-private-duplicate",
            "GEMINI_API4": "db-private-duplicate",
            "GEMINI_API5": "",
            "GEMINI_API6": "",
        },
        clear=False,
    )
    def test_duplicate_hmac_and_raw_credential_never_enter_request_database(self):
        from management.services import gemini_keys

        plan = runtime.generic_candidate_plan(
            role="management",
            models=["gemini-3.6-flash"],
            manual_key="db-private-duplicate",
        )
        observer = runtime.begin_request(
            request_id=uuid_for_test(),
            role="management",
            reasoning_task="memory_summary",
            candidate_plan=plan,
            lane="analysis",
        )
        graph = GeminiRequest.objects.get(pk=observer.graph_id)
        encoded = json.dumps(graph.candidate_plan, sort_keys=True)
        fingerprint = gemini_keys.credential_fingerprint("db-private-duplicate")
        self.assertNotIn("db-private-duplicate", encoded)
        self.assertNotIn(fingerprint.hex(), encoded)
        self.assertGreaterEqual(
            sum(row["identity_status"] == "duplicate" for row in graph.candidate_plan),
            2,
        )

    @override_settings(**SHADOW)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_success_creates_one_attempt_state_and_atomic_winner(self, _post):
        observer = self._observer()
        boundary = observer.attempt(
            key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
        )
        parsed, usage = ai._gemini_call_once(
            "gemini-3.7-flash",
            {"contents": [{"parts": [{"text": "private prompt"}]}]},
            "private-key",
            parse=False,
            attempt_boundary=boundary,
        )
        self.assertEqual(parsed, "ok")
        self.assertEqual(usage["promptTokenCount"], 11)
        attempt = GeminiRequestAttempt.objects.get(request_graph_id=observer.graph_id)
        state = GeminiQuotaState.objects.get(
            project_identity="gemini-project-1", model="gemini-3.7-flash"
        )
        graph = GeminiRequest.objects.get(pk=observer.graph_id)
        self.assertEqual(attempt.fsm_state, GeminiRequestAttempt.FsmState.SUCCEEDED)
        self.assertEqual(attempt.prompt_tokens, 11)
        self.assertEqual(attempt.total_tokens, 14)
        self.assertTrue(attempt.winner_claimed)
        self.assertEqual(graph.winner_attempt_id, attempt.pk)
        self.assertEqual(graph.terminal_resolution, "succeeded")
        self.assertEqual(state.rpd_dispatched, 1)
        self.assertEqual(state.in_flight_count, 0)

    @override_settings(**SHADOW)
    @patch("management.services.call_ai_analysis.requests.post", side_effect=requests.ReadTimeout("late"))
    def test_timeout_is_ambiguous_and_conservatively_counted(self, _post):
        observer = self._observer()
        boundary = observer.attempt(
            key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
        )
        with self.assertRaises(ai._GeminiTransient):
            ai._gemini_call_once(
                "gemini-3.7-flash", {"contents": []}, "private-key",
                parse=False, attempt_boundary=boundary,
            )
        attempt = GeminiRequestAttempt.objects.get(pk=boundary.attempt_id)
        state = GeminiQuotaState.objects.get(pk=boundary.state_id)
        self.assertEqual(attempt.fsm_state, GeminiRequestAttempt.FsmState.TIMEOUT_AMBIGUOUS)
        self.assertEqual(attempt.outcome, "timeout_ambiguous")
        self.assertEqual(state.rpd_dispatched, 1)
        self.assertEqual(state.rpd_uncertain, 1)
        self.assertEqual(state.in_flight_count, 0)

        # A caller/reaper replay must not consume or release the same attempt twice.
        boundary.failed(ai._GeminiTransient("timeout: repeated"))
        state.refresh_from_db()
        self.assertEqual(state.rpd_dispatched, 1)
        self.assertEqual(state.rpd_uncertain, 1)
        self.assertEqual(state.in_flight_count, 0)

    @override_settings(**SHADOW)
    @patch("management.services.call_ai_analysis.requests.post")
    def test_malformed_200_envelope_is_not_transport_ambiguous(self, post):
        response = _Response()
        response.json = lambda: (_ for _ in ()).throw(ValueError("bad json"))
        post.return_value = response
        observer = self._observer()
        boundary = observer.attempt(
            key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
        )
        with self.assertRaises(ai._GeminiTransient):
            ai._gemini_call_once(
                "gemini-3.7-flash", {"contents": []}, "private-key",
                parse=False, attempt_boundary=boundary,
            )
        attempt = GeminiRequestAttempt.objects.get(pk=boundary.attempt_id)
        state = GeminiQuotaState.objects.get(pk=boundary.state_id)
        self.assertEqual(attempt.fsm_state, GeminiRequestAttempt.FsmState.FAILED)
        self.assertEqual(attempt.failure_kind, "invalid_response")
        self.assertEqual(state.rpd_uncertain, 0)

    @override_settings(**SHADOW)
    @patch("management.services.call_ai_analysis.requests.post")
    def test_wrong_200_envelope_shape_settles_failed_not_in_flight(self, post):
        response = _Response()
        response.json = lambda: ["not-an-envelope"]
        post.return_value = response
        observer = self._observer()
        boundary = observer.attempt(
            key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
        )
        with self.assertRaises(ai._GeminiTransient):
            ai._gemini_call_once(
                "gemini-3.7-flash", {"contents": []}, "private-key",
                parse=False, attempt_boundary=boundary,
            )
        attempt = GeminiRequestAttempt.objects.get(pk=boundary.attempt_id)
        state = GeminiQuotaState.objects.get(pk=boundary.state_id)
        self.assertEqual(attempt.failure_kind, "invalid_response")
        self.assertEqual(attempt.fsm_state, GeminiRequestAttempt.FsmState.FAILED)
        self.assertEqual(state.in_flight_count, 0)

    @override_settings(**SHADOW)
    def test_final_body_failure_is_linked_cancelled_without_quota_spend(self):
        observer = self._observer()
        boundary = observer.attempt(
            key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
        )
        with patch.object(ai, "PROVIDER_REQUEST_MAX_BYTES", 1):
            with self.assertRaises(ai._GeminiFatal):
                ai._gemini_call_once(
                    "gemini-3.7-flash",
                    {"contents": [{"parts": [{"text": "too large"}]}]},
                    "private-key",
                    parse=False,
                    attempt_boundary=boundary,
                )
        attempt = GeminiRequestAttempt.objects.get(pk=boundary.attempt_id)
        self.assertEqual(
            attempt.fsm_state,
            GeminiRequestAttempt.FsmState.CANCELLED_PRE_DISPATCH,
        )
        self.assertEqual(attempt.outcome, "cancelled_pre_dispatch")
        self.assertIsNone(attempt.provider_started_at)
        self.assertIsNone(attempt.dispatch_pacific_day)
        self.assertEqual(GeminiQuotaState.objects.count(), 0)
        graph = GeminiRequest.objects.get(pk=observer.graph_id)
        self.assertEqual(
            graph.candidate_outcomes["1"]["outcome"],
            "cancelled_pre_dispatch",
        )

    @override_settings(**SHADOW)
    @patch.dict(os.environ, KEY_ENV, clear=False)
    def test_gateway_payload_fatal_updates_same_linked_cancelled_row(self):
        with patch.object(ai, "PROVIDER_REQUEST_MAX_BYTES", 1):
            with self.assertRaises(ai.CallAIAnalysisError):
                ai.gemini_generate_text(
                    {"contents": [{"parts": [{"text": "too large"}]}]},
                    role="management",
                    reasoning_task="memory_summary",
                )
        graph = GeminiRequest.objects.get()
        rows = GeminiRequestAttempt.objects.filter(request_id=graph.request_id)
        self.assertEqual(rows.count(), 1)
        attempt = rows.get()
        self.assertEqual(attempt.request_graph_id, graph.pk)
        self.assertEqual(
            attempt.fsm_state,
            GeminiRequestAttempt.FsmState.CANCELLED_PRE_DISPATCH,
        )
        self.assertEqual(attempt.outcome, "cancelled_pre_dispatch")
        self.assertEqual(graph.terminal_resolution, "failed")

    @override_settings(**SHADOW)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_unknown_custom_and_unprofiled_25_never_create_invented_state(self, _post):
        for model, identity in (
            ("gemini-3.7-flash", ""),
            ("gemini-2.5-flash", "gemini-project-1"),
        ):
            observer = self._observer(model, identity=identity)
            boundary = observer.attempt(
                key_name="(manual)", model=model, candidate_index=1
            )
            ai._gemini_call_once(
                model, {"contents": []}, "unknown-custom", parse=False,
                attempt_boundary=boundary,
            )
            attempt = GeminiRequestAttempt.objects.get(pk=boundary.attempt_id)
            self.assertIsNone(attempt.quota_profile_id)
            self.assertEqual(attempt.shadow_decision, GeminiRequestAttempt.ShadowDecision.UNKNOWN)
        self.assertEqual(GeminiQuotaState.objects.count(), 0)

    @override_settings(**SHADOW)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_provider_truth_is_counted_even_when_shadow_would_deny(self, _post):
        profile = GeminiQuotaProfile.objects.get(
            profile_version=runtime.OWNER_PROFILE_VERSION,
            model="gemini-3.7-flash",
        )
        GeminiQuotaState.objects.create(
            project_identity="gemini-project-1",
            model=profile.model,
            quota_profile=profile,
            pacific_day=timezone.now().astimezone(runtime.PT).date(),
            rpd_dispatched=profile.rpd_limit,
        )
        observer = self._observer()
        boundary = observer.attempt(
            key_name="GEMINI_API", model=profile.model, candidate_index=1
        )
        ai._gemini_call_once(
            profile.model, {"contents": []}, "private-key", parse=False,
            attempt_boundary=boundary,
        )
        attempt = GeminiRequestAttempt.objects.get(pk=boundary.attempt_id)
        state = GeminiQuotaState.objects.get(project_identity="gemini-project-1", model=profile.model)
        self.assertEqual(attempt.shadow_decision, GeminiRequestAttempt.ShadowDecision.DENY)
        self.assertEqual(attempt.shadow_deny_reason, "rpd_exhausted")
        self.assertEqual(state.rpd_dispatched, profile.rpd_limit + 1)

    @override_settings(**SHADOW)
    def test_stale_provider_boundary_reconciles_and_late_success_is_idempotent(self):
        first = self._observer()
        first_boundary = first.attempt(
            key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
        )
        first_boundary.before_provider(serialized_bytes=100, inline_count=0)
        stale_at = timezone.now() - dt.timedelta(seconds=1)
        GeminiRequestAttempt.objects.filter(pk=first_boundary.attempt_id).update(
            permit_expires_at=stale_at,
            reservation_expires_at=stale_at,
        )
        GeminiQuotaState.objects.filter(pk=first_boundary.state_id).update(
            next_permit_expiry_at=stale_at,
        )

        second = self._observer()
        second_boundary = second.attempt(
            key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
        )
        second_boundary.before_provider(serialized_bytes=100, inline_count=0)
        first_attempt = GeminiRequestAttempt.objects.get(pk=first_boundary.attempt_id)
        self.assertEqual(
            first_attempt.fsm_state,
            GeminiRequestAttempt.FsmState.TIMEOUT_AMBIGUOUS,
        )
        second_boundary.manual_result(
            succeeded=True,
            http_code=200,
            usage={"promptTokenCount": 3, "totalTokenCount": 4},
        )
        first_boundary.succeeded({"promptTokenCount": 5, "totalTokenCount": 7})
        first_boundary.succeeded({"promptTokenCount": 5, "totalTokenCount": 7})

        first_attempt.refresh_from_db()
        state = GeminiQuotaState.objects.get(pk=first_boundary.state_id)
        self.assertEqual(
            first_attempt.fsm_state,
            GeminiRequestAttempt.FsmState.SUCCEEDED_LATE,
        )
        self.assertEqual(state.rpd_dispatched, 2)
        self.assertEqual(state.rpd_uncertain, 0)
        self.assertEqual(state.in_flight_count, 0)

    @override_settings(**SHADOW)
    def test_cross_midnight_settlement_keeps_original_dispatch_day(self):
        dispatch_at = dt.datetime(2026, 8, 31, 6, 59, tzinfo=dt.timezone.utc)
        finish_at = dt.datetime(2026, 8, 31, 7, 1, tzinfo=dt.timezone.utc)
        with patch.object(runtime.timezone, "now", return_value=dispatch_at):
            observer = self._observer()
            boundary = observer.attempt(
                key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
            )
            boundary.before_provider(serialized_bytes=100, inline_count=0)
        with patch.object(runtime.timezone, "now", return_value=finish_at):
            boundary.manual_result(
                succeeded=True,
                http_code=200,
                usage={"promptTokenCount": 3, "totalTokenCount": 4},
            )
        attempt = GeminiRequestAttempt.objects.get(pk=boundary.attempt_id)
        self.assertEqual(attempt.dispatch_pacific_day, dt.date(2026, 8, 30))

    @override_settings(**SHADOW)
    @patch("management.services.call_ai_analysis.requests.post")
    def test_structured_429_is_bounded_and_marks_external_drift(self, post):
        post.return_value = _Response(429, {
            "error": {
                "status": "RESOURCE_EXHAUSTED",
                "message": "private provider body",
                "details": [{
                    "retryDelay": "42s",
                    "violations": [{
                        "quotaMetric": "rpd",
                        "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                        "quotaDimensions": {
                            "model": "gemini-3.7-flash",
                            "location": "global",
                            "project": "real-project-id-must-not-persist",
                        },
                    }],
                }],
            },
        })
        observer = self._observer()
        boundary = observer.attempt(
            key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
        )
        with self.assertRaises(ai._Gemini429):
            ai._gemini_call_once(
                "gemini-3.7-flash", {"contents": []}, "private-key",
                parse=False, attempt_boundary=boundary,
            )
        attempt = GeminiRequestAttempt.objects.get(pk=boundary.attempt_id)
        state = GeminiQuotaState.objects.get(pk=boundary.state_id)
        self.assertEqual(attempt.provider_quota_metric, "rpd")
        self.assertEqual(
            attempt.provider_quota_id,
            "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
        )
        self.assertEqual(attempt.provider_quota_dimensions["model"], "gemini-3.7-flash")
        self.assertNotIn("project", attempt.provider_quota_dimensions)
        self.assertEqual(attempt.provider_retry_after_seconds, 44)
        self.assertTrue(state.external_usage_suspected)
        self.assertNotIn("private provider body", json.dumps(state.provider_blocks))

    @override_settings(**SHADOW)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_one_request_has_one_immutable_winner(self, _post):
        plan = _raw_plan()
        plan.append({
            "candidate_index": 2,
            "key_name": "GEMINI_API2",
            "project_identity": "gemini-project-2",
            "identity_status": "known",
            "model": "gemini-3.7-flash",
            "skip_reason": "",
        })
        observer = runtime.begin_request(
            request_id=uuid_for_test(), role="chat", reasoning_task="customer_chat",
            candidate_plan=plan, lane="live",
        )
        boundaries = [
            observer.attempt(key_name=alias, model="gemini-3.7-flash", candidate_index=index)
            for index, alias in ((1, "GEMINI_API"), (2, "GEMINI_API2"))
        ]
        for boundary in boundaries:
            ai._gemini_call_once(
                "gemini-3.7-flash", {"contents": []}, "private-key",
                parse=False, attempt_boundary=boundary,
            )
        graph = GeminiRequest.objects.get(pk=observer.graph_id)
        self.assertEqual(graph.winner_attempt_id, boundaries[0].attempt_id)
        self.assertEqual(
            GeminiRequestAttempt.objects.filter(request_graph=graph, winner_claimed=True).count(),
            1,
        )

    @override_settings(**SHADOW)
    def test_pre_provider_observer_reads_are_bounded(self):
        observer = self._observer()
        boundary = observer.attempt(
            key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
        )
        with CaptureQueriesContext(connection) as captured:
            boundary.before_provider(serialized_bytes=120, inline_count=0)
        reads = [q for q in captured if q["sql"].lstrip().upper().startswith("SELECT")]
        self.assertLessEqual(len(reads), 6, [q["sql"] for q in reads])

    @override_settings(**SHADOW)
    @patch.dict(os.environ, KEY_ENV, clear=False)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_live_uses_the_precreated_attempt_instead_of_double_counting(self, _post):
        out = ai.gemini_generate_text(
            {"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
            role="chat",
            model_chain_override=["gemini-3.5-flash-lite"],
        )
        self.assertEqual(out["parsed"], "ok")
        graph = GeminiRequest.objects.get()
        provider_rows = GeminiRequestAttempt.objects.filter(
            request_id=graph.request_id,
            outcome="succeeded",
        )
        self.assertEqual(provider_rows.count(), 1)
        self.assertEqual(provider_rows.get().request_graph_id, graph.pk)
        self.assertEqual(provider_rows.get().fsm_state, GeminiRequestAttempt.FsmState.SUCCEEDED)
        encoded = json.dumps(graph.candidate_plan)
        self.assertNotIn("GEMINI_API", encoded)
        self.assertNotIn("shadow-key", encoded)

    @override_settings(**SHADOW)
    @patch.dict(os.environ, {key: "" for key in KEY_ENV}, clear=False)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_unknown_live_custom_is_in_plan_but_never_becomes_a_seventh_state(self, _post):
        out = ai.gemini_generate_text(
            {"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
            role="chat",
            manual_key="unknown-custom-key",
            model_chain_override=["gemini-3.5-flash-lite"],
        )
        self.assertEqual(out["parsed"], "ok")
        graph = GeminiRequest.objects.get()
        self.assertEqual(len(graph.candidate_plan), 7)
        self.assertTrue(any(
            item["identity_status"] == "unknown"
            and item["model"] == "gemini-3.5-flash-lite"
            for item in graph.candidate_plan
        ))
        attempt = GeminiRequestAttempt.objects.get(request_graph=graph)
        self.assertEqual(attempt.project_identity, "")
        self.assertIsNone(attempt.quota_profile_id)
        self.assertEqual(GeminiQuotaState.objects.count(), 0)

    @override_settings(
        GEMINI_ACCOUNTING_V2_MODE="shadow",
        GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM=SHADOW_FROM,
        GEMINI_ACCOUNTING_IDENTITY_HMAC_KEY="shadow-test-hmac-key",
        GEMINI_KEY_PROJECT_GROUPS={},
    )
    @patch.dict(os.environ, KEY_ENV, clear=False)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_default_project_labels_are_assumed_not_quota_identities(self, _post):
        ai.gemini_generate_text(
            {"contents": [{"parts": [{"text": "memory"}]}]},
            role="management",
            reasoning_task="memory_summary",
        )
        graph = GeminiRequest.objects.get()
        self.assertTrue(any(
            row["identity_status"] == "assumed" for row in graph.candidate_plan
        ))
        attempt = GeminiRequestAttempt.objects.get(request_graph=graph)
        self.assertEqual(attempt.project_identity, "")
        self.assertIsNone(attempt.quota_profile_id)
        self.assertEqual(GeminiQuotaState.objects.count(), 0)

    @override_settings(**SHADOW)
    @patch.dict(os.environ, KEY_ENV, clear=False)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_generic_memory_and_call_tasks_share_the_observed_gateway(self, _post):
        for task in ("memory_summary", "conversation_reanalysis", "customer_intelligence"):
            ai.gemini_generate_text(
                {"contents": [{"parts": [{"text": "bounded"}]}]},
                role="management",
                reasoning_task=task,
            )
        self.assertEqual(
            set(GeminiRequest.objects.values_list("reasoning_task", flat=True)),
            {"memory_summary", "conversation_reanalysis", "customer_intelligence"},
        )
        self.assertEqual(
            GeminiRequestAttempt.objects.filter(request_graph__isnull=False).count(),
            3,
        )

    @override_settings(**SHADOW)
    @patch.dict(os.environ, KEY_ENV, clear=False)
    @patch("management.services.call_ai_analysis.requests.post")
    def test_call_audio_wrapper_uses_one_profiled_shadow_attempt(self, post):
        post.return_value = _Response(payload={
            "candidates": [{
                "finishReason": "STOP",
                "content": {"parts": [{"text": '{"overall_score": 1}'}]},
            }],
            "usageMetadata": {"promptTokenCount": 20, "totalTokenCount": 24},
        })
        out = ai._gemini_analyze(b"bounded-audio", "audio/mpeg", "", "")
        self.assertEqual(out["parsed"]["overall_score"], 1)
        graph = GeminiRequest.objects.get()
        attempt = GeminiRequestAttempt.objects.get(request_graph=graph)
        self.assertEqual(graph.reasoning_task, "customer_intelligence")
        self.assertEqual(graph.lane, "analysis")
        self.assertIsNotNone(attempt.quota_profile_id)
        self.assertEqual(attempt.fsm_state, GeminiRequestAttempt.FsmState.SUCCEEDED)

    @override_settings(**SHADOW)
    @patch.dict(os.environ, KEY_ENV, clear=False)
    @patch("management.services.call_ai_analysis.requests.post")
    def test_checker_is_graphed_without_inventing_25_profile(self, post):
        post.return_value = _Response(payload={
            "candidates": [{
                "finishReason": "STOP",
                "content": {"parts": [{"text": '{"score": 1}'}]},
            }],
            "usageMetadata": {"promptTokenCount": 4, "totalTokenCount": 8},
        })
        ai.gemini_generate_grounded("system", "user")
        graph = GeminiRequest.objects.get()
        attempt = GeminiRequestAttempt.objects.get(request_graph=graph)
        self.assertEqual(graph.reasoning_task, "conversion_analysis")
        self.assertEqual(attempt.role, "checker")
        self.assertIsNone(attempt.quota_profile_id)
        self.assertEqual(GeminiQuotaState.objects.count(), 0)

    @override_settings(**SHADOW)
    @patch.dict(os.environ, KEY_ENV, clear=False)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_recovery_lineage_is_preserved(self, _post):
        decision = classify_live_turn(TurnFacts(), settings_obj=None)
        with turn_lineage(
            lane=Lane.RECOVERY,
            client_id=7,
            source_message_id=9,
            logical_turn_id="t7:9",
            recovery_job_id=11,
        ):
            ai.gemini_generate_text(
                {"contents": [{"parts": [{"text": "recover"}]}]},
                role="chat",
                model_chain_override=["gemini-3.5-flash-lite"],
                routing_decision=decision,
            )
        graph = GeminiRequest.objects.get()
        self.assertEqual(graph.lane, "recovery")
        self.assertEqual(graph.client_id, 7)
        self.assertEqual(graph.source_message_id, 9)
        self.assertEqual(graph.recovery_job_id, 11)

    @override_settings(**SHADOW)
    @patch.dict(os.environ, KEY_ENV, clear=False)
    @patch("management.services.gemini_probe.requests.post", return_value=_Response())
    def test_quota_consuming_probe_is_diagnostic_generation(self, _post):
        result = gemini_probe.probe_key("gemini-3.7-flash", "shadow-key-1")
        self.assertEqual(result["status"], "ok")
        graph = GeminiRequest.objects.get()
        attempt = GeminiRequestAttempt.objects.get(request_graph=graph)
        self.assertEqual(graph.lane, "diagnostic")
        self.assertEqual(attempt.role, "diagnostic")
        self.assertEqual(attempt.fsm_state, GeminiRequestAttempt.FsmState.SUCCEEDED)

    @override_settings(**SHADOW)
    @patch("management.services.gemini_probe.requests.get")
    def test_metadata_get_never_creates_generation_accounting(self, get):
        response = _Response(payload={"supportedGenerationMethods": ["generateContent"]})
        get.return_value = response
        result = gemini_probe.probe_key_metadata("gemini-3.7-flash", "key")
        self.assertEqual(result["status"], "metadata_ok")
        self.assertEqual(GeminiRequest.objects.count(), 0)
        self.assertEqual(GeminiQuotaState.objects.count(), 0)

    @override_settings(**SHADOW)
    @patch.dict(os.environ, KEY_ENV, clear=False)
    @patch("management.models.GeminiRequest.objects.create", side_effect=DatabaseError("shadow down"))
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_v2_database_failure_is_fail_soft_for_real_generation(self, _post, _create):
        out = ai.gemini_generate_text(
            {"contents": [{"parts": [{"text": "hello"}]}]},
            role="management",
            reasoning_task="memory_summary",
        )
        self.assertEqual(out["parsed"], "ok")

    @override_settings(**SHADOW)
    @patch("management.services.call_ai_analysis.requests.post", return_value=_Response())
    def test_reply_link_is_idempotent_and_targets_the_winner(self, _post):
        observer = self._observer()
        boundary = observer.attempt(
            key_name="GEMINI_API", model="gemini-3.7-flash", candidate_index=1
        )
        ai._gemini_call_once(
            "gemini-3.7-flash", {"contents": []}, "key", parse=False,
            attempt_boundary=boundary,
        )
        self.assertTrue(runtime.link_reply_if_present(request_id=observer.request_id, reply_message_id=77))
        self.assertTrue(runtime.link_reply_if_present(request_id=observer.request_id, reply_message_id=77))
        self.assertEqual(GeminiRequest.objects.get(pk=observer.graph_id).reply_message_id, 77)
        self.assertEqual(GeminiRequestAttempt.objects.get(pk=boundary.attempt_id).reply_message_id, 77)


def uuid_for_test():
    import uuid

    return uuid.uuid4().hex
