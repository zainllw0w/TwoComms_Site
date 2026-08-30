import json
import os
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from management.models import (
    AdminAuditLog,
    GeminiRequestAttempt,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import call_ai_analysis, gemini_keys
from management.services.gemini_routing import (
    ANALYSIS_CHAIN,
    COMPLEX_CHAIN,
    ORDINARY_CHAIN,
    RoutingMode,
    TaskClass,
    TurnFacts,
    analysis_escalation_chain,
    classify_live_turn,
    persist_decision,
)


class RoutingDecisionContractTests(SimpleTestCase):
    def test_ordinary_complex_and_analysis_chains_are_explicit(self):
        self.assertEqual(
            ORDINARY_CHAIN,
            (
                "gemini-3.5-flash-lite",
                "gemini-3.5-flash",
                "gemini-3.6-flash",
                "gemini-3.7-flash",
            ),
        )
        self.assertEqual(
            COMPLEX_CHAIN,
            (
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
            ),
        )
        self.assertEqual(
            ANALYSIS_CHAIN,
            (
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
            ),
        )

    def test_plain_text_does_not_promote_itself_without_structured_evidence(self):
        decision = classify_live_turn(TurnFacts())
        self.assertEqual(decision.task_class, TaskClass.ORDINARY_LIVE)
        self.assertEqual(decision.model_chain, ORDINARY_CHAIN)

    def test_media_and_ambiguous_catalog_are_complex(self):
        media = classify_live_turn(TurnFacts(has_image=True))
        ambiguous = classify_live_turn(TurnFacts(unresolved_catalog_candidates=3))
        self.assertEqual(media.task_class, TaskClass.COMPLEX_LIVE)
        self.assertEqual(media.reasoning_task, "media_analysis")
        self.assertEqual(ambiguous.task_class, TaskClass.COMPLEX_LIVE)
        self.assertIn("ambiguous_catalog", ambiguous.reason_codes)

    def test_deterministic_action_never_has_a_model_chain(self):
        decision = classify_live_turn(
            TurnFacts(deterministic_action="provider_native_ugc")
        )
        self.assertEqual(decision.task_class, TaskClass.NO_MODEL)
        self.assertEqual(decision.model_chain, ())

    def test_analysis_escalation_is_one_separate_guarded_37_pass(self):
        eligible = dict(
            schema_valid=True,
            low_confidence=True,
            high_value=True,
            conflict_or_missing_fact=True,
            already_escalated=False,
            capacity_available=True,
        )
        self.assertEqual(
            analysis_escalation_chain(**eligible),
            ("gemini-3.7-flash",),
        )
        for field in eligible:
            changed = dict(eligible)
            changed[field] = not changed[field]
            self.assertEqual(analysis_escalation_chain(**changed), (), field)


class ActualInstagramGeminiRoutingTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.gemini_routing_mode = self.settings.GeminiRoutingMode.ADAPTIVE
        self.settings.gemini_model = "gemini-3.7-flash"
        self.settings.save(
            update_fields=["gemini_routing_mode", "gemini_model"]
        )

    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_actual_entrypoint_ignores_legacy_model_in_adaptive_mode(self, generate):
        from management.services.instagram_bot import gemini_generate

        generate.return_value = {
            "parsed": "Вітаю!",
            "model": "gemini-3.5-flash-lite",
            "meta": {},
        }
        reply = gemini_generate(
            self.settings,
            [{"role": "user", "text": "Яка ціна?"}],
        )

        self.assertEqual(reply, "Вітаю!")
        self.assertEqual(
            tuple(generate.call_args.kwargs["model_chain_override"]),
            ORDINARY_CHAIN,
        )
        self.assertIsNone(generate.call_args.kwargs.get("model_override"))
        self.assertEqual(generate.call_args.kwargs["reasoning_task"], "customer_chat")

    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_actual_entrypoint_routes_an_image_to_complex_chain(self, generate):
        from management.services.instagram_bot import gemini_generate

        generate.return_value = {
            "parsed": "Бачу принт.",
            "model": "gemini-3.7-flash",
            "meta": {},
        }
        gemini_generate(
            self.settings,
            [{"role": "user", "text": "Що це?"}],
            images=[("image/jpeg", b"image")],
        )

        self.assertEqual(
            tuple(generate.call_args.kwargs["model_chain_override"]),
            COMPLEX_CHAIN,
        )
        self.assertEqual(generate.call_args.kwargs["reasoning_task"], "media_analysis")

    def test_routing_decision_is_durable_on_the_source_message(self):
        row = InstagramBotMessage.objects.create(
            sender_id="route-durable",
            role=InstagramBotMessage.Role.USER,
            text="hello",
        )
        decision = classify_live_turn(TurnFacts(has_image=True))
        persist_decision(row, decision)
        row.refresh_from_db()
        self.assertEqual(row.gemini_task_class, TaskClass.COMPLEX_LIVE)
        self.assertEqual(tuple(row.gemini_routing_model_chain), COMPLEX_CHAIN)
        self.assertIn("image_reasoning", row.gemini_routing_reason_codes)
        self.assertEqual(row.gemini_routing_deadline_ms, 45_000)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class PinnedRoutingPolicyTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()

    def test_active_pin_prepends_one_model_and_expired_pin_is_adaptive(self):
        self.settings.gemini_routing_mode = self.settings.GeminiRoutingMode.PINNED
        self.settings.pinned_chat_model = "gemini-3.6-flash"
        self.settings.pinned_until = timezone.now() + timedelta(minutes=10)
        decision = classify_live_turn(TurnFacts(), settings_obj=self.settings)
        self.assertEqual(decision.routing_mode, RoutingMode.PINNED)
        self.assertEqual(decision.model_chain[0], "gemini-3.6-flash")

        self.settings.pinned_until = timezone.now() - timedelta(seconds=1)
        expired = classify_live_turn(TurnFacts(), settings_obj=self.settings)
        self.assertEqual(expired.routing_mode, RoutingMode.ADAPTIVE)
        self.assertEqual(expired.model_chain, ORDINARY_CHAIN)

    def test_settings_api_audits_a_bounded_pin(self):
        user = get_user_model().objects.create_user(
            username="routing-admin",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(user)
        response = self.client.post(
            "/bot/api/settings/",
            {
                "ai_enabled": "on",
                "gemini_model": "gemini-3.6-flash",
                "gemini_routing_mode": "pinned",
                "pinned_minutes": "15",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.gemini_routing_mode, "pinned")
        self.assertEqual(self.settings.pinned_chat_model, "gemini-3.6-flash")
        self.assertLessEqual(
            self.settings.pinned_until,
            timezone.now() + timedelta(minutes=15, seconds=2),
        )
        audit = AdminAuditLog.objects.get(
            action="ig_gemini.routing_policy_changed"
        )
        self.assertEqual(audit.after["mode"], "pinned")
        self.assertNotIn("key", json.dumps(audit.after).casefold())


class SixProjectCandidatePlanTests(TestCase):
    def test_default_identities_are_six_distinct_non_secret_labels(self):
        groups = gemini_keys.key_project_groups()
        self.assertEqual(set(groups), set(gemini_keys.ALL_KEYS))
        self.assertEqual(len(set(groups.values())), 6)
        self.assertTrue(all("secret" not in value for value in groups.values()))

    def test_plan_contains_all_six_projects_for_every_model(self):
        env = {alias: f"test-secret-{index}" for index, alias in enumerate(gemini_keys.ALL_KEYS)}
        with patch.dict(os.environ, env, clear=False):
            plan = gemini_keys.live_chat_candidate_plan(
                model_chain_override=list(ORDINARY_CHAIN)
            )
        self.assertEqual(len(plan), 24)
        for model in ORDINARY_CHAIN:
            rows = [item for item in plan if item["model"] == model]
            self.assertEqual(len(rows), 6)
            self.assertEqual(len({item["project_identity"] for item in rows}), 6)

    def test_legacy_chat_hedge_is_disabled(self):
        self.assertFalse(call_ai_analysis.ENABLE_LEGACY_CHAT_HEDGE)


class TypedQuotaErrorTests(SimpleTestCase):
    def _response(self, details):
        payload = {
            "error": {
                "status": "RESOURCE_EXHAUSTED",
                "message": "quota exceeded",
                "details": details,
            }
        }
        response = type("Response", (), {})()
        response.status_code = 429
        response.json = lambda: payload
        response.text = json.dumps(payload)
        return response

    @patch("management.services.call_ai_analysis.requests.post")
    def test_quota_failure_and_retry_info_become_typed_day_error(self, post):
        post.return_value = self._response([
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{
                    "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                }],
            },
            {
                "@type": "type.googleapis.com/google.rpc.RetryInfo",
                "retryDelay": "48.5s",
            },
        ])
        with self.assertRaises(call_ai_analysis._Gemini429) as raised:
            call_ai_analysis._gemini_call_once(
                "gemini-3.7-flash", {"contents": []}, "redacted", parse=False
            )
        self.assertEqual(raised.exception.scope, "day")
        self.assertEqual(raised.exception.retry_after_seconds, 50)
        self.assertEqual(raised.exception.provider_reason, "RESOURCE_EXHAUSTED")

    @patch("management.services.call_ai_analysis.requests.post")
    def test_per_minute_token_quota_remains_minute_scoped(self, post):
        post.return_value = self._response([{
            "violations": [{"quotaId": "GenerateContentInputTokensPerMinutePerProjectPerModel"}],
            "retryDelay": "1.2s",
        }])
        with self.assertRaises(call_ai_analysis._Gemini429) as raised:
            call_ai_analysis._gemini_call_once(
                "gemini-3.7-flash", {"contents": []}, "redacted", parse=False
            )
        self.assertEqual(raised.exception.scope, "minute")
        self.assertEqual(raised.exception.retry_after_seconds, 3)


class ManualDiagnosticsOnlyTests(TestCase):
    def test_metadata_command_requires_explicit_manual_flag(self):
        with self.assertRaises(CommandError):
            call_command("check_ig_gemini_metadata_health", stdout=StringIO())

    @patch("management.management.commands.check_ig_gemini_metadata_health.gemini_metadata_health.run_hour")
    def test_manual_metadata_command_is_token_free_and_explicit(self, run_hour):
        run_hour.return_value = {
            "checked_aliases": 6,
            "configured_aliases": 6,
            "provider_requests": 6,
            "deadline_skipped_models": 0,
        }
        call_command(
            "check_ig_gemini_metadata_health",
            manual=True,
            stdout=StringIO(),
        )
        run_hour.assert_called_once()

    def test_generation_probe_requires_quota_spend_confirmation(self):
        with self.assertRaises(CommandError):
            call_command("probe_ig_gemini_pool", stdout=StringIO())


class DeadlinePlanEvidenceTests(TestCase):
    @patch.dict(
        os.environ,
        {alias: f"deadline-key-{index}" for index, alias in enumerate(gemini_keys.ALL_KEYS)},
        clear=False,
    )
    @patch("management.services.call_ai_analysis._chat_timeout", return_value=None)
    def test_deadline_records_every_unstarted_project_candidate(self, _timeout):
        with self.assertRaises(call_ai_analysis.CallAIAnalysisError):
            call_ai_analysis.gemini_generate_text(
                {"contents": []},
                role="chat",
                model_chain_override=["gemini-3.7-flash"],
                reasoning_task="media_analysis",
            )
        rows = GeminiRequestAttempt.objects.filter(
            model="gemini-3.7-flash",
            outcome="not_attempted",
        )
        self.assertEqual(rows.count(), 6)
        self.assertEqual(
            set(rows.values_list("not_attempted_reason", flat=True)),
            {"deadline"},
        )

    @patch.dict(
        os.environ,
        {alias: f"slow-key-{index}" for index, alias in enumerate(gemini_keys.ALL_KEYS)},
        clear=False,
    )
    @patch(
        "management.services.call_ai_analysis._gemini_call_once",
        side_effect=call_ai_analysis._GeminiTransient("timeout: slow model"),
    )
    def test_two_slow_calls_skip_the_rest_of_the_same_model_durably(self, _call):
        with self.assertRaises(call_ai_analysis.CallAIAnalysisError):
            call_ai_analysis.gemini_generate_text(
                {"contents": []},
                role="chat",
                model_chain_override=["gemini-3.7-flash"],
                reasoning_task="media_analysis",
            )
        self.assertEqual(
            GeminiRequestAttempt.objects.filter(
                model="gemini-3.7-flash",
                outcome="failed",
                failure_kind="read_timeout",
            ).count(),
            2,
        )
        self.assertEqual(
            GeminiRequestAttempt.objects.filter(
                model="gemini-3.7-flash",
                outcome="not_attempted",
                not_attempted_reason="sla_model_budget",
            ).count(),
            4,
        )
