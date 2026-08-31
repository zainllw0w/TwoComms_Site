import datetime as dt
import os
from unittest.mock import patch

from django.db import DatabaseError, connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from management.models import (
    GeminiQuotaProfile,
    GeminiQuotaState,
    GeminiRequestAttempt,
)
from management.services import gemini_accounting_runtime as runtime
from management.services import gemini_keys, gemini_quota


NOW = dt.datetime(2026, 9, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
SHADOW = {
    "GEMINI_ACCOUNTING_V2_MODE": "shadow",
    "GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM": "2026-08-29T00:00:00-07:00",
    "GEMINI_ACCOUNTING_IDENTITY_HMAC_KEY": "ranking-test-hmac-key",
    "GEMINI_KEY_PROJECT_GROUPS": {
        f"GEMINI_API{suffix}": f"gemini-project-{index}"
        for index, suffix in enumerate(("", "2", "3", "4", "5", "6"), start=1)
    },
}
KEY_ENV = {
    f"GEMINI_API{suffix}": f"ranking-private-key-{index}"
    for index, suffix in enumerate(("", "2", "3", "4", "5", "6"), start=1)
}
LIMITS = {
    "gemini-3.7-flash": (5, 250_000, 20, 1, "shadow-calibration-required"),
    "gemini-3.6-flash": (5, 250_000, 20, 1, runtime.ACTIVE_ESTIMATOR_VERSION),
    "gemini-3.5-flash": (5, 250_000, 20, 1, "shadow-calibration-required"),
    "gemini-3.5-flash-lite": (15, 250_000, 500, 2, runtime.ACTIVE_ESTIMATOR_VERSION),
}


@override_settings(**SHADOW)
class GeminiProjectRankingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for model, (rpm, tpm, rpd, permits, estimator) in LIMITS.items():
            GeminiQuotaProfile.objects.get_or_create(
                profile_version=runtime.ACTIVE_QUOTA_PROFILE_VERSION,
                model=model,
                defaults={
                    "rpm_limit": rpm,
                    "input_tpm_limit": tpm,
                    "rpd_limit": rpd,
                    "permit_limit": permits,
                    "estimator_version": estimator,
                    "source": GeminiQuotaProfile.Source.ADMIN,
                    "source_reference": "ranking_test_fixture",
                    "observed_at": NOW - dt.timedelta(days=1),
                    "effective_from": NOW - dt.timedelta(days=1),
                },
            )

    @staticmethod
    def _profile(model):
        return GeminiQuotaProfile.objects.get(
            profile_version=runtime.ACTIVE_QUOTA_PROFILE_VERSION,
            model=model,
        )

    def _state(
        self,
        identity,
        model,
        *,
        dispatched=0,
        in_flight=0,
        latency=0,
        status=GeminiQuotaState.AccountingStatus.AVAILABLE,
        provider_blocks=None,
        day=None,
        last_success_at=None,
        external_usage_suspected=False,
    ):
        return GeminiQuotaState.objects.create(
            project_identity=identity,
            model=model,
            quota_profile=self._profile(model),
            pacific_day=day or gemini_quota.pacific_day(NOW),
            rpd_dispatched=dispatched,
            in_flight_count=in_flight,
            latency_ewma_ms=latency,
            accounting_status=status,
            provider_blocks=provider_blocks or {},
            last_success_at=last_success_at,
            external_usage_suspected=external_usage_suspected,
        )

    def test_snapshot_is_provider_free_bounded_and_uses_rolling_prompt_usage(self):
        model = "gemini-3.6-flash"
        identity = "gemini-project-1"
        self._state(
            identity,
            model,
            dispatched=4,
            in_flight=1,
            latency=120,
            last_success_at=NOW - dt.timedelta(seconds=30),
            external_usage_suspected=True,
        )
        GeminiRequestAttempt.objects.create(
            request_id="ranking-rolling-attempt",
            role="management",
            key_name="GEMINI_API",
            project_group=identity,
            project_identity=identity,
            model=model,
            outcome="provider_started",
            fsm_state=GeminiRequestAttempt.FsmState.PROVIDER_STARTED,
            accounting_mode="shadow",
            prompt_tokens=100,
            reserved_prompt_tokens=150,
            provider_started_at=NOW - dt.timedelta(seconds=20),
            dispatch_pacific_day=gemini_quota.pacific_day(NOW),
            permit_expires_at=NOW + dt.timedelta(seconds=60),
        )

        with CaptureQueriesContext(connection) as queries:
            snapshot = runtime.project_ranking_snapshot(
                project_identities=[identity],
                models=[model],
                now=NOW,
            )

        row = snapshot[(identity, model)]
        self.assertEqual(row["remaining_rpd"], 16)
        self.assertEqual(row["remaining_rpm"], 4)
        self.assertEqual(row["remaining_input_tpm"], 249_900)
        self.assertTrue(row["input_tpm_rankable"])
        self.assertFalse(row["provider_blocked"])
        self.assertEqual(row["in_flight"], 1)
        self.assertEqual(row["latency_ms"], 120)
        self.assertEqual(row["evidence_age_seconds"], 30)
        self.assertTrue(row["evidence_fresh"])
        self.assertTrue(row["external_usage_suspected"])
        reads = [
            query for query in queries
            if query["sql"].lstrip().upper().startswith("SELECT")
        ]
        self.assertLessEqual(len(reads), 3, [query["sql"] for query in reads])

    def test_uncalibrated_models_keep_tpm_advisory_but_rank_rpd_rpm(self):
        model = "gemini-3.7-flash"
        self._state("gemini-project-1", model, dispatched=19)
        self._state("gemini-project-2", model, dispatched=1)

        snapshot = runtime.project_ranking_snapshot(
            project_identities=["gemini-project-1", "gemini-project-2"],
            models=[model],
            now=NOW,
        )

        self.assertIsNone(snapshot[("gemini-project-1", model)]["remaining_input_tpm"])
        self.assertFalse(snapshot[("gemini-project-1", model)]["input_tpm_rankable"])
        ordered = runtime.order_project_aliases(
            ["GEMINI_API", "GEMINI_API2"],
            model=model,
            project_identities={
                "GEMINI_API": "gemini-project-1",
                "GEMINI_API2": "gemini-project-2",
            },
            snapshot=snapshot,
        )
        self.assertEqual(ordered, ["GEMINI_API2", "GEMINI_API"])

    def test_active_provider_block_is_ranked_after_unknown_fallback(self):
        model = "gemini-3.6-flash"
        self._state(
            "gemini-project-1",
            model,
            provider_blocks={
                "rpd": {"until": (NOW + dt.timedelta(hours=1)).isoformat()}
            },
            status=GeminiQuotaState.AccountingStatus.BLOCKED,
        )
        snapshot = runtime.project_ranking_snapshot(
            project_identities=["gemini-project-1", "gemini-project-2"],
            models=[model],
            now=NOW,
        )
        ordered = runtime.order_project_aliases(
            ["GEMINI_API", "GEMINI_API2"],
            model=model,
            project_identities={
                "GEMINI_API": "gemini-project-1",
                "GEMINI_API2": "gemini-project-2",
            },
            snapshot=snapshot,
        )
        self.assertTrue(snapshot[("gemini-project-1", model)]["provider_blocked"])
        self.assertEqual(ordered, ["GEMINI_API2", "GEMINI_API"])

    def test_missing_degraded_unprofiled_and_database_error_fall_back(self):
        model = "gemini-3.6-flash"
        self._state(
            "gemini-project-1",
            model,
            status=GeminiQuotaState.AccountingStatus.DEGRADED,
            last_success_at=NOW - dt.timedelta(seconds=30),
        )
        snapshot = runtime.project_ranking_snapshot(
            project_identities=["gemini-project-1", "gemini-project-2"],
            models=[model, "gemini-unprofiled"],
            now=NOW,
        )
        degraded = snapshot[("gemini-project-1", model)]
        self.assertTrue(degraded["state_degraded"])
        virtual_zero = snapshot[("gemini-project-2", model)]
        self.assertFalse(virtual_zero["state_present"])
        self.assertEqual(virtual_zero["remaining_rpd"], 20)
        self.assertEqual(virtual_zero["remaining_rpm"], 5)
        self.assertNotIn(("gemini-project-1", "gemini-unprofiled"), snapshot)
        original = ["GEMINI_API", "GEMINI_API2"]
        self.assertEqual(
            runtime.order_project_aliases(
                original,
                model=model,
                project_identities={
                    "GEMINI_API": "gemini-project-1",
                    "GEMINI_API2": "gemini-project-2",
                },
                snapshot=snapshot,
            ),
            ["GEMINI_API2", "GEMINI_API"],
        )
        with patch(
            "management.models.GeminiQuotaProfile.objects.filter",
            side_effect=DatabaseError("ranking unavailable"),
        ):
            self.assertEqual(
                runtime.project_ranking_snapshot(
                    project_identities=["gemini-project-1"],
                    models=[model],
                    now=NOW,
                ),
                {},
            )

    def test_stale_pacific_day_does_not_carry_rpd_usage_forward(self):
        model = "gemini-3.6-flash"
        identity = "gemini-project-1"
        self._state(
            identity,
            model,
            dispatched=20,
            day=gemini_quota.pacific_day(NOW) - dt.timedelta(days=1),
        )
        row = runtime.project_ranking_snapshot(
            project_identities=[identity], models=[model], now=NOW
        )[(identity, model)]
        self.assertEqual(row["remaining_rpd"], 20)

    @patch.dict(os.environ, KEY_ENV, clear=False)
    def test_generic_execution_uses_v2_project_order_and_preserves_model_major(self):
        for model in ("gemini-3.6-flash", "gemini-3.5-flash-lite"):
            self._state("gemini-project-6", model, dispatched=LIMITS[model][2] - 1)
            self._state("gemini-project-5", model, dispatched=0)

        with patch("management.services.gemini_keys.timezone.now", return_value=NOW):
            candidates = list(gemini_keys.iter_attempts(
                "management",
                model_chain_override=[
                    "gemini-3.6-flash",
                    "gemini-3.5-flash-lite",
                ],
            ))

        first_model = [row for row in candidates if row[2] == "gemini-3.6-flash"]
        second_model = [
            row for row in candidates if row[2] == "gemini-3.5-flash-lite"
        ]
        self.assertEqual(first_model[0][0], "GEMINI_API5")
        self.assertEqual(second_model[0][0], "GEMINI_API5")
        self.assertEqual(
            [row[2] for row in candidates],
            ["gemini-3.6-flash"] * len(first_model)
            + ["gemini-3.5-flash-lite"] * len(second_model),
        )

    @patch.dict(os.environ, KEY_ENV, clear=False)
    def test_live_plan_uses_v2_project_order_without_changing_model_chain(self):
        self._state("gemini-project-1", "gemini-3.5-flash-lite", dispatched=499)
        self._state("gemini-project-2", "gemini-3.5-flash-lite", dispatched=0)
        with patch("management.services.gemini_keys.timezone.now", return_value=NOW):
            plan = gemini_keys.live_chat_candidate_plan([
                "gemini-3.5-flash-lite",
                "gemini-3.6-flash",
            ])

        lite_rows = [row for row in plan if row["model"] == "gemini-3.5-flash-lite"]
        strong_rows = [row for row in plan if row["model"] == "gemini-3.6-flash"]
        self.assertEqual(lite_rows[0]["key_name"], "GEMINI_API2")
        self.assertEqual(
            [row["model"] for row in plan],
            ["gemini-3.5-flash-lite"] * len(lite_rows)
            + ["gemini-3.6-flash"] * len(strong_rows),
        )

    @patch.dict(os.environ, KEY_ENV, clear=False)
    @override_settings(GEMINI_ACCOUNTING_V2_MODE="off")
    def test_mode_off_preserves_legacy_live_order_without_v2_reads(self):
        with CaptureQueriesContext(connection) as queries, patch(
            "management.services.gemini_keys.timezone.now", return_value=NOW
        ):
            plan = gemini_keys.live_chat_candidate_plan(["gemini-3.5-flash-lite"])
        self.assertEqual(plan[0]["key_name"], "GEMINI_API")
        self.assertFalse(any(
            "management_geminiquotastate" in query["sql"].casefold()
            for query in queries
        ))

    def test_conservative_legacy_headroom_prevents_virtual_zero_overclaim(self):
        model = "gemini-3.6-flash"
        snapshot = {
            ("gemini-project-1", model): {
                "remaining_rpd": 20,
                "remaining_rpm": 5,
                "remaining_input_tpm": 250_000,
                "input_tpm_rankable": True,
                "eligible": True,
                "block_reason": "",
                "state_degraded": False,
                "in_flight": 0,
                "latency_ms": 0,
            },
            ("gemini-project-2", model): {
                "remaining_rpd": 10,
                "remaining_rpm": 5,
                "remaining_input_tpm": 250_000,
                "input_tpm_rankable": True,
                "eligible": True,
                "block_reason": "",
                "state_degraded": False,
                "in_flight": 0,
                "latency_ms": 0,
            },
        }
        legacy = {
            ("GEMINI_API", model): {"rpd": 1, "rpm": 5, "tpm": 250_000},
            ("GEMINI_API2", model): {"rpd": 10, "rpm": 5, "tpm": 250_000},
        }

        ordered = runtime.order_project_aliases(
            ["GEMINI_API", "GEMINI_API2"],
            model=model,
            project_identities={
                "GEMINI_API": "gemini-project-1",
                "GEMINI_API2": "gemini-project-2",
            },
            snapshot=snapshot,
            legacy_snapshot=legacy,
        )

        self.assertEqual(ordered, ["GEMINI_API2", "GEMINI_API"])
        decision = runtime.project_candidate_decision(
            "GEMINI_API",
            model=model,
            project_identity="gemini-project-1",
            snapshot=snapshot,
            legacy_snapshot=legacy,
        )
        self.assertEqual(decision["remaining_rpd"], 1)

    @patch.dict(os.environ, KEY_ENV, clear=False)
    def test_live_plan_records_v2_provider_rpd_rpm_tpm_and_permit_skips(self):
        model = "gemini-3.5-flash-lite"
        future = (NOW + dt.timedelta(hours=1)).isoformat()
        self._state(
            "gemini-project-1",
            model,
            provider_blocks={"rpd": {"until": future}},
            status=GeminiQuotaState.AccountingStatus.BLOCKED,
        )
        self._state("gemini-project-2", model, dispatched=500)
        self._state("gemini-project-3", model)
        self._state("gemini-project-4", model)
        self._state("gemini-project-5", model, in_flight=2)
        self._state("gemini-project-6", model)
        for index in range(2):
            GeminiRequestAttempt.objects.create(
                request_id=f"ranking-permit-{index}",
                role="chat",
                key_name="GEMINI_API5",
                project_group="gemini-project-5",
                project_identity="gemini-project-5",
                model=model,
                outcome="provider_started",
                fsm_state=GeminiRequestAttempt.FsmState.PROVIDER_STARTED,
                accounting_mode="shadow",
                provider_started_at=NOW - dt.timedelta(seconds=10),
                dispatch_pacific_day=gemini_quota.pacific_day(NOW),
                permit_expires_at=NOW + dt.timedelta(seconds=60),
            )
        for index in range(15):
            GeminiRequestAttempt.objects.create(
                request_id=f"ranking-rpm-{index}",
                role="chat",
                key_name="GEMINI_API3",
                project_group="gemini-project-3",
                project_identity="gemini-project-3",
                model=model,
                outcome="succeeded",
                fsm_state=GeminiRequestAttempt.FsmState.SUCCEEDED,
                accounting_mode="shadow",
                prompt_tokens=1,
                provider_started_at=NOW - dt.timedelta(seconds=10),
                dispatch_pacific_day=gemini_quota.pacific_day(NOW),
                settled_at=NOW - dt.timedelta(seconds=9),
            )
        GeminiRequestAttempt.objects.create(
            request_id="ranking-tpm",
            role="chat",
            key_name="GEMINI_API4",
            project_group="gemini-project-4",
            project_identity="gemini-project-4",
            model=model,
            outcome="succeeded",
            fsm_state=GeminiRequestAttempt.FsmState.SUCCEEDED,
            accounting_mode="shadow",
            prompt_tokens=250_000,
            provider_started_at=NOW - dt.timedelta(seconds=10),
            dispatch_pacific_day=gemini_quota.pacific_day(NOW),
            settled_at=NOW - dt.timedelta(seconds=9),
        )

        with patch("management.services.gemini_keys.timezone.now", return_value=NOW):
            plan = gemini_keys.live_chat_candidate_plan([model])

        by_alias = {row["key_name"]: row for row in plan}
        self.assertEqual(by_alias["GEMINI_API"]["skip_reason"], "provider_block")
        self.assertEqual(by_alias["GEMINI_API2"]["skip_reason"], "rpd_exhausted")
        self.assertEqual(by_alias["GEMINI_API3"]["skip_reason"], "rpm_exhausted")
        self.assertEqual(by_alias["GEMINI_API4"]["skip_reason"], "tpm_exhausted")
        self.assertEqual(by_alias["GEMINI_API5"]["skip_reason"], "permit_exhausted")
        self.assertEqual(by_alias["GEMINI_API6"]["skip_reason"], "")

    @patch.dict(os.environ, KEY_ENV, clear=False)
    def test_generic_path_skips_v2_ineligible_and_stays_within_read_budget(self):
        model = "gemini-3.6-flash"
        self._state(
            "gemini-project-1",
            model,
            provider_blocks={
                "rpd": {"until": (NOW + dt.timedelta(hours=1)).isoformat()}
            },
            status=GeminiQuotaState.AccountingStatus.BLOCKED,
        )
        with CaptureQueriesContext(connection) as queries, patch(
            "management.services.gemini_keys.timezone.now",
            return_value=NOW,
        ):
            candidates = list(gemini_keys.iter_attempts(
                "management",
                model_chain_override=[model],
            ))

        self.assertNotIn("GEMINI_API", [row[0] for row in candidates])
        reads = [
            row for row in queries
            if row["sql"].lstrip().upper().startswith("SELECT")
        ]
        self.assertLessEqual(len(reads), 6, [row["sql"] for row in reads])

    def test_expired_permit_and_stale_degradation_do_not_block_forever(self):
        model = "gemini-3.6-flash"
        identity = "gemini-project-1"
        self._state(
            identity,
            model,
            in_flight=1,
            status=GeminiQuotaState.AccountingStatus.DEGRADED,
            last_success_at=NOW - dt.timedelta(days=2),
        )
        GeminiRequestAttempt.objects.create(
            request_id="ranking-expired-permit",
            role="management",
            key_name="GEMINI_API",
            project_group=identity,
            project_identity=identity,
            model=model,
            outcome="provider_started",
            fsm_state=GeminiRequestAttempt.FsmState.PROVIDER_STARTED,
            accounting_mode="shadow",
            provider_started_at=NOW - dt.timedelta(minutes=4),
            dispatch_pacific_day=gemini_quota.pacific_day(NOW),
            permit_expires_at=NOW - dt.timedelta(seconds=1),
        )

        row = runtime.project_ranking_snapshot(
            project_identities=[identity],
            models=[model],
            now=NOW,
        )[(identity, model)]

        self.assertEqual(row["in_flight"], 0)
        self.assertTrue(row["eligible"])
        self.assertEqual(row["block_reason"], "")
        self.assertFalse(row["evidence_fresh"])
        self.assertFalse(row["state_degraded"])

    @override_settings(GEMINI_V2_PROJECT_RANKING_MODE="invalid")
    def test_invalid_ranking_mode_is_rejected_by_system_check(self):
        from management.checks import gemini_v2_project_ranking_check

        self.assertEqual(
            [item.id for item in gemini_v2_project_ranking_check()],
            ["management.E918"],
        )
