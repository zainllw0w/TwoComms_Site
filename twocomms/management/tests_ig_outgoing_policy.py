"""Э0.4 — тесты политики исходящего БЕЗ обращения к провайдеру.

`OutgoingPolicyTests` — `SimpleTestCase` с пустым `databases`: если в чистую
функцию когда-нибудь просочится запрос к базе, тест упадёт. Сети политика не
умеет звать вообще, и это проверяется отдельным тестом на импорты модуля.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import datetime, time, timedelta, timezone as dt_timezone

from django.test import SimpleTestCase, override_settings

from management.services.ig_outgoing_policy import (
    ALLOW,
    APP_TYPE_INSTAGRAM_LOGIN,
    APP_TYPE_LEGACY_PAGE,
    BASIS_PROVEN_CONSENT,
    BASIS_PROVIDER_ALLOWED_TYPE,
    BASIS_STANDARD_WINDOW,
    BLOCK,
    DECISIONS,
    DEFER,
    DEFER_WITHOUT_HORIZON_REASONS,
    ESCALATE,
    EVENT_KIND_PURPOSE,
    PERMISSION_BLOCK_REASONS,
    PERMISSION_DEFER_REASONS,
    POLICY_BASES,
    PURPOSE_MARKETING,
    PURPOSE_SERVICE,
    PURPOSE_TRANSACTIONAL,
    REASON_CODES,
    STANDARD_WINDOW,
    VERIFIED_CONTRACT_VERSION,
    VERIFIED_PLATFORM_CONTRACTS,
    CaseRiskState,
    ConsentScope,
    FrequencyState,
    OutgoingDecision,
    OutgoingRequest,
    PlatformContract,
    ProviderMessageType,
    QuietHours,
    UnstablePolicyDecision,
    decide_outgoing,
    documented_reason_codes,
    reason_code_decision,
)

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=dt_timezone.utc)
TRANSACTIONAL_KIND = "lifecycle.payment_verified"
SERVICE_KIND = "lifecycle.delivered_review_requested"


def make_request(**overrides) -> OutgoingRequest:
    base = {
        "platform_contract_version": VERIFIED_CONTRACT_VERSION,
        "event_kind": TRANSACTIONAL_KIND,
        "message_purpose": PURPOSE_TRANSACTIONAL,
        "channel_app_type": APP_TYPE_INSTAGRAM_LOGIN,
        "latest_user_provider_ts": NOW - timedelta(hours=1),
    }
    base.update(overrides)
    return OutgoingRequest(**base)


# Гипотетический канал, где consent ДОКАЗАН документом. В production такого
# контракта нет; он существует только чтобы ветвь consent была проверяемой и
# не превратилась в мёртвый код.
CONSENT_APP_TYPE = "hypothetical_channel"
CONSENT_CONTRACTS = {
    (CONSENT_APP_TYPE, VERIFIED_CONTRACT_VERSION): PlatformContract(
        channel_app_type=CONSENT_APP_TYPE,
        version=VERIFIED_CONTRACT_VERSION,
        standard_window=STANDARD_WINDOW,
        consent_basis_proven=True,
    ),
}


class OutgoingPolicyTests(SimpleTestCase):
    """Только политика: ни базы, ни провайдера, ни текущего времени."""

    databases: set[str] = set()

    # --- основание «внутри стандартного окна» ------------------------------

    def test_inside_standard_window_allows_with_window_basis(self):
        decision = decide_outgoing(make_request(), now=NOW)
        self.assertEqual(decision.decision, ALLOW)
        self.assertEqual(decision.reason_code, "within_standard_window")
        self.assertEqual(decision.policy_basis, BASIS_STANDARD_WINDOW)
        self.assertIsNone(decision.eligible_at)
        self.assertTrue(decision.allowed)

    def test_window_edge_is_inclusive_and_next_second_escalates(self):
        inside = decide_outgoing(
            make_request(latest_user_provider_ts=NOW - STANDARD_WINDOW), now=NOW
        )
        self.assertEqual(inside.decision, ALLOW)
        outside = decide_outgoing(
            make_request(
                latest_user_provider_ts=NOW - STANDARD_WINDOW - timedelta(seconds=1)
            ),
            now=NOW,
        )
        self.assertEqual(outside.decision, ESCALATE)
        self.assertEqual(outside.reason_code, "outside_standard_window")
        self.assertEqual(outside.policy_basis, "")

    def test_anchor_in_the_future_is_not_a_window(self):
        decision = decide_outgoing(
            make_request(latest_user_provider_ts=NOW + timedelta(minutes=5)), now=NOW
        )
        self.assertNotEqual(decision.decision, ALLOW)

    def test_no_customer_message_at_all_blocks(self):
        decision = decide_outgoing(make_request(latest_user_provider_ts=None), now=NOW)
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "window_anchor_missing")

    def test_both_transports_share_one_window_contract(self):
        for app_type in (APP_TYPE_INSTAGRAM_LOGIN, APP_TYPE_LEGACY_PAGE):
            decision = decide_outgoing(
                make_request(channel_app_type=app_type), now=NOW
            )
            self.assertEqual(decision.decision, ALLOW, app_type)

    # --- ключевая поправка Э0.4 -------------------------------------------

    def test_human_reply_alone_is_not_a_window_bypass(self):
        """«Человек ответил текстом» не отменяет ограничение платформы."""
        decision = decide_outgoing(
            make_request(
                latest_user_provider_ts=NOW - timedelta(days=2),
                human_authored=True,
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, ESCALATE)
        self.assertEqual(decision.reason_code, "outside_standard_window")
        self.assertEqual(decision.policy_basis, "")

    def test_no_input_combination_reaches_allow_without_a_basis(self):
        outside = NOW - timedelta(days=3)
        for purpose, kind in (
            (PURPOSE_TRANSACTIONAL, TRANSACTIONAL_KIND),
            (PURPOSE_SERVICE, SERVICE_KIND),
        ):
            for human in (False, True):
                for consent in (None, ConsentScope(topic="reactivation")):
                    decision = decide_outgoing(
                        make_request(
                            event_kind=kind,
                            message_purpose=purpose,
                            latest_user_provider_ts=outside,
                            human_authored=human,
                            consent_scope=consent,
                        ),
                        now=NOW,
                    )
                    self.assertNotEqual(decision.decision, ALLOW, decision)
                    self.assertEqual(decision.policy_basis, "", decision)

    # --- правило по умолчанию: непроверенная capability --------------------

    def test_unverified_contract_version_blocks(self):
        decision = decide_outgoing(
            make_request(platform_contract_version="meta-someday"), now=NOW
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "platform_contract_unverified")

    def test_unverified_app_type_blocks(self):
        decision = decide_outgoing(
            make_request(channel_app_type="whatsapp_cloud"), now=NOW
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "channel_app_type_unverified")

    def test_unregistered_event_kind_blocks_so_new_flows_cannot_slip_through(self):
        decision = decide_outgoing(make_request(event_kind="ltv.reactivation"), now=NOW)
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "event_kind_unregistered")

    def test_unknown_purpose_blocks(self):
        decision = decide_outgoing(make_request(message_purpose="nudge"), now=NOW)
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "message_purpose_unknown")

    def test_purpose_cannot_contradict_event_kind(self):
        decision = decide_outgoing(
            make_request(
                event_kind=SERVICE_KIND, message_purpose=PURPOSE_TRANSACTIONAL
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "message_purpose_conflicts_event_kind")

    def test_no_registered_event_kind_is_marketing(self):
        marketing = {
            kind
            for kind, purpose in EVENT_KIND_PURPOSE.items()
            if purpose == PURPOSE_MARKETING
        }
        self.assertEqual(marketing, set())

    def test_marketing_purpose_is_blocked_even_with_an_open_window(self):
        """Реактивация не разрешена ничем: ни окном, ни человеком, ни тегом."""
        event_kinds = dict(EVENT_KIND_PURPOSE)
        event_kinds["test.reactivation_blast"] = PURPOSE_MARKETING
        decision = decide_outgoing(
            make_request(
                event_kind="test.reactivation_blast",
                message_purpose=PURPOSE_MARKETING,
                latest_user_provider_ts=NOW - timedelta(minutes=5),
                human_authored=True,
            ),
            now=NOW,
            event_kinds=event_kinds,
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "marketing_capability_unverified")

    def test_naive_now_blocks_instead_of_guessing_the_window(self):
        decision = decide_outgoing(make_request(), now=NOW.replace(tzinfo=None))
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "evaluation_time_not_aware")

    def test_empty_contract_registry_blocks_everything(self):
        decision = decide_outgoing(make_request(), now=NOW, contracts={})
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "channel_app_type_unverified")

    # --- основание «доказанный consent» -------------------------------------

    def test_consent_with_proven_basis_in_scope_and_not_expired_allows(self):
        decision = decide_outgoing(
            make_request(
                channel_app_type=CONSENT_APP_TYPE,
                latest_user_provider_ts=NOW - timedelta(days=3),
                consent_scope=ConsentScope(
                    topic="reactivation",
                    granted_at=NOW - timedelta(days=10),
                    expires_at=NOW + timedelta(days=80),
                    evidence_message_id=123,
                ),
                consent_topic_required="reactivation",
            ),
            now=NOW,
            contracts=CONSENT_CONTRACTS,
        )
        self.assertEqual(decision.decision, ALLOW)
        self.assertEqual(decision.reason_code, "proven_consent_in_scope")
        self.assertEqual(decision.policy_basis, BASIS_PROVEN_CONSENT)

    def test_consent_without_evidence_message_id_blocks(self):
        decision = decide_outgoing(
            make_request(
                channel_app_type=CONSENT_APP_TYPE,
                latest_user_provider_ts=NOW - timedelta(days=3),
                consent_scope=ConsentScope(
                    topic="reactivation",
                    granted_at=NOW - timedelta(days=10),
                    evidence_message_id=None,
                ),
                consent_topic_required="reactivation",
            ),
            now=NOW,
            contracts=CONSENT_CONTRACTS,
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "consent_out_of_scope")

    def test_consent_basis_unverified_when_the_contract_does_not_prove_it(self):
        decision = decide_outgoing(
            make_request(
                latest_user_provider_ts=NOW - timedelta(days=3),
                consent_scope=ConsentScope(
                    topic="reactivation",
                    granted_at=NOW - timedelta(days=10),
                    expires_at=NOW + timedelta(days=80),
                    evidence_message_id=123,
                ),
                consent_topic_required="reactivation",
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "consent_basis_unverified")

    def test_consent_expired_blocks(self):
        decision = decide_outgoing(
            make_request(
                channel_app_type=CONSENT_APP_TYPE,
                latest_user_provider_ts=NOW - timedelta(days=3),
                consent_scope=ConsentScope(
                    topic="reactivation",
                    granted_at=NOW - timedelta(days=100),
                    expires_at=NOW - timedelta(seconds=1),
                    evidence_message_id=123,
                ),
                consent_topic_required="reactivation",
            ),
            now=NOW,
            contracts=CONSENT_CONTRACTS,
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "consent_out_of_scope")

    def test_consent_without_topic_does_not_grant_a_basis(self):
        decision = decide_outgoing(
            make_request(
                channel_app_type=CONSENT_APP_TYPE,
                latest_user_provider_ts=NOW - timedelta(days=3),
                consent_scope=ConsentScope(topic=""),
            ),
            now=NOW,
            contracts=CONSENT_CONTRACTS,
        )
        self.assertNotEqual(decision.decision, ALLOW)

    # --- основание «provider-allowed message type» -------------------------

    def test_human_agent_within_seven_days_with_human_authored_allows(self):
        decision = decide_outgoing(
            make_request(
                latest_user_provider_ts=NOW - timedelta(days=6),
                human_authored=True,
                requested_message_type="HUMAN_AGENT",
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, ALLOW)
        self.assertEqual(decision.reason_code, "provider_allowed_message_type")
        self.assertEqual(decision.policy_basis, BASIS_PROVIDER_ALLOWED_TYPE)

    def test_human_agent_over_seven_days_blocks(self):
        decision = decide_outgoing(
            make_request(
                latest_user_provider_ts=NOW - timedelta(days=8),
                human_authored=True,
                requested_message_type="HUMAN_AGENT",
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "provider_message_type_conditions_unmet")

    def test_human_agent_without_human_authored_blocks(self):
        decision = decide_outgoing(
            make_request(
                latest_user_provider_ts=NOW - timedelta(hours=6),
                human_authored=False,
                requested_message_type="HUMAN_AGENT",
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "provider_message_type_conditions_unmet")

    def test_human_agent_does_not_allow_marketing(self):
        event_kinds = dict(EVENT_KIND_PURPOSE)
        event_kinds["test.marketing"] = PURPOSE_MARKETING
        decision = decide_outgoing(
            make_request(
                event_kind="test.marketing",
                message_purpose=PURPOSE_MARKETING,
                latest_user_provider_ts=NOW - timedelta(hours=6),
                human_authored=True,
                requested_message_type="HUMAN_AGENT",
            ),
            now=NOW,
            event_kinds=event_kinds,
        )
        self.assertNotEqual(decision.decision, ALLOW)

    def test_unverified_provider_message_type_blocks(self):
        decision = decide_outgoing(
            make_request(
                latest_user_provider_ts=NOW - timedelta(hours=1),
                requested_message_type="CONFIRMED_EVENT_UPDATE",
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "provider_message_type_unverified")

    # --- права: BLOCK и DEFER ----------------------------------------------

    def test_permission_reason_maps_to_block_decisions(self):
        for legacy, code in PERMISSION_BLOCK_REASONS.items():
            decision = decide_outgoing(
                make_request(case_risk_state=CaseRiskState(permission_reason=legacy)),
                now=NOW,
            )
            self.assertEqual(decision.decision, BLOCK, legacy)
            self.assertEqual(decision.reason_code, code, legacy)

    def test_permission_reason_maps_to_defer_decisions(self):
        for legacy, code in PERMISSION_DEFER_REASONS.items():
            decision = decide_outgoing(
                make_request(case_risk_state=CaseRiskState(permission_reason=legacy)),
                now=NOW,
            )
            self.assertEqual(decision.decision, DEFER, legacy)
            self.assertEqual(decision.reason_code, code, legacy)
            self.assertIsNone(decision.eligible_at, legacy)

    def test_unrecognized_permission_reason_blocks(self):
        decision = decide_outgoing(
            make_request(
                case_risk_state=CaseRiskState(permission_reason="forged_client_id")
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, BLOCK)
        self.assertEqual(decision.reason_code, "permission_reason_unrecognized")

    # --- жалоба и заявка важнее временной паузы ---------------------------

    def test_open_complaint_escalates(self):
        decision = decide_outgoing(
            make_request(case_risk_state=CaseRiskState(open_complaint=True)),
            now=NOW,
        )
        self.assertEqual(decision.decision, ESCALATE)
        self.assertEqual(decision.reason_code, "open_complaint")

    def test_case_requires_human_escalates(self):
        decision = decide_outgoing(
            make_request(case_risk_state=CaseRiskState(case_requires_human=True)),
            now=NOW,
        )
        self.assertEqual(decision.decision, ESCALATE)
        self.assertEqual(decision.reason_code, "case_requires_human")

    def test_open_complaint_escalates_even_when_paused(self):
        decision = decide_outgoing(
            make_request(
                case_risk_state=CaseRiskState(
                    permission_reason="client_paused", open_complaint=True
                )
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, ESCALATE)
        self.assertEqual(decision.reason_code, "open_complaint")

    # --- тихие часы: дефер в локальном времени клиента ---------------------

    def test_quiet_hours_defer_service_purpose_inside_the_window(self):
        kyiv_offset = timedelta(hours=3)
        now_19_utc = datetime(2026, 9, 1, 19, 0, tzinfo=dt_timezone.utc)
        decision = decide_outgoing(
            make_request(
                event_kind=SERVICE_KIND,
                message_purpose=PURPOSE_SERVICE,
                quiet_hours=QuietHours(
                    start=time(22, 0), end=time(9, 0), utc_offset=kyiv_offset
                ),
            ),
            now=now_19_utc,
        )
        self.assertEqual(decision.decision, DEFER)
        self.assertEqual(decision.reason_code, "quiet_hours")
        self.assertIsNotNone(decision.eligible_at)

    def test_quiet_hours_do_not_defer_transactional_purpose(self):
        now_19_utc = datetime(2026, 9, 1, 19, 0, tzinfo=dt_timezone.utc)
        decision = decide_outgoing(
            make_request(
                quiet_hours=QuietHours(
                    start=time(22, 0), end=time(9, 0), utc_offset=timedelta(hours=3)
                )
            ),
            now=now_19_utc,
        )
        self.assertEqual(decision.decision, ALLOW)

    def test_quiet_hours_wraparound_midnight(self):
        now_22_utc = datetime(2026, 9, 1, 22, 0, tzinfo=dt_timezone.utc)
        decision = decide_outgoing(
            make_request(
                event_kind=SERVICE_KIND,
                message_purpose=PURPOSE_SERVICE,
                quiet_hours=QuietHours(
                    start=time(22, 0), end=time(9, 0), utc_offset=timedelta(hours=3)
                ),
            ),
            now=now_22_utc,
        )
        self.assertEqual(decision.decision, DEFER)
        self.assertEqual(decision.reason_code, "quiet_hours")

    def test_quiet_hours_allow_during_permitted_interval(self):
        now_09_utc = datetime(2026, 9, 1, 9, 0, tzinfo=dt_timezone.utc)
        decision = decide_outgoing(
            make_request(
                event_kind=SERVICE_KIND,
                message_purpose=PURPOSE_SERVICE,
                latest_user_provider_ts=now_09_utc - timedelta(hours=1),
                quiet_hours=QuietHours(
                    start=time(22, 0), end=time(9, 0), utc_offset=timedelta(hours=3)
                ),
            ),
            now=now_09_utc,
        )
        self.assertEqual(decision.decision, ALLOW)

    # --- частота: max_in_window и min_interval -----------------------------

    def test_frequency_cap_reached_defers_with_horizon(self):
        decision = decide_outgoing(
            make_request(
                frequency_state=FrequencyState(
                    sent_in_window=5,
                    max_in_window=3,
                    window=timedelta(hours=24),
                    last_sent_at=NOW - timedelta(hours=12),
                )
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, DEFER)
        self.assertEqual(decision.reason_code, "frequency_cap_reached")
        self.assertIsNotNone(decision.eligible_at)
        self.assertGreater(decision.eligible_at, NOW)

    def test_frequency_within_cap_allows(self):
        decision = decide_outgoing(
            make_request(
                frequency_state=FrequencyState(
                    sent_in_window=2,
                    max_in_window=3,
                    window=timedelta(hours=24),
                    last_sent_at=NOW - timedelta(hours=12),
                )
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, ALLOW)

    def test_frequency_min_interval_defers(self):
        decision = decide_outgoing(
            make_request(
                frequency_state=FrequencyState(
                    last_sent_at=NOW - timedelta(seconds=30),
                    min_interval=timedelta(seconds=60),
                )
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, DEFER)
        self.assertEqual(decision.reason_code, "frequency_min_interval")
        self.assertIsNotNone(decision.eligible_at)

    def test_frequency_min_interval_respects_elapsed_time(self):
        decision = decide_outgoing(
            make_request(
                frequency_state=FrequencyState(
                    last_sent_at=NOW - timedelta(seconds=61),
                    min_interval=timedelta(seconds=60),
                )
            ),
            now=NOW,
        )
        self.assertEqual(decision.decision, ALLOW)

    # --- reason_code -> decision контракт ----------------------------------

    def test_reason_code_decision_matches_REASON_CODES_registry(self):
        for code, (expected_decision, _description) in REASON_CODES.items():
            inferred = reason_code_decision(code)
            self.assertEqual(inferred, expected_decision, code)

    def test_unknown_reason_code_returns_empty_for_metrics(self):
        self.assertEqual(reason_code_decision("foo"), "")

    def test_documented_reason_codes_returns_stable_sorted_tuple(self):
        codes = documented_reason_codes()
        self.assertIsInstance(codes, tuple)
        self.assertEqual(codes, tuple(sorted(codes)))
        self.assertTrue(all(c in REASON_CODES for c in codes))

    def test_every_returned_reason_code_is_documented(self):
        seen_codes = set()
        for purpose, kind in (
            (PURPOSE_TRANSACTIONAL, TRANSACTIONAL_KIND),
            (PURPOSE_SERVICE, SERVICE_KIND),
        ):
            for permission in list(PERMISSION_BLOCK_REASONS) + list(
                PERMISSION_DEFER_REASONS
            ):
                decision = decide_outgoing(
                    make_request(
                        event_kind=kind,
                        message_purpose=purpose,
                        case_risk_state=CaseRiskState(permission_reason=permission),
                    ),
                    now=NOW,
                )
                seen_codes.add(decision.reason_code)
        for code in seen_codes:
            self.assertIn(code, REASON_CODES, code)

    # --- OutgoingDecision invariant: allow requires basis ------------------

    def test_allow_without_a_basis_raises_UnstablePolicyDecision(self):
        with self.assertRaises(UnstablePolicyDecision):
            OutgoingDecision(decision=ALLOW, reason_code="within_standard_window")

    def test_non_allow_with_a_basis_raises_UnstablePolicyDecision(self):
        for decision in (DEFER, BLOCK, ESCALATE):
            with self.assertRaises(UnstablePolicyDecision):
                OutgoingDecision(
                    decision=decision,
                    reason_code="outside_standard_window",
                    policy_basis=BASIS_STANDARD_WINDOW,
                )

    def test_defer_without_eligible_at_but_reason_allows_it_succeeds(self):
        for code in DEFER_WITHOUT_HORIZON_REASONS:
            decision = OutgoingDecision(decision=DEFER, reason_code=code)
            self.assertEqual(decision.decision, DEFER)
            self.assertIsNone(decision.eligible_at)

    def test_defer_with_a_horizon_required_reason_but_no_eligible_at_raises(self):
        with self.assertRaises(UnstablePolicyDecision):
            OutgoingDecision(decision=DEFER, reason_code="quiet_hours")

    def test_non_defer_with_eligible_at_raises(self):
        for decision in (ALLOW, BLOCK, ESCALATE):
            with self.assertRaises(UnstablePolicyDecision):
                OutgoingDecision(
                    decision=decision,
                    reason_code=(
                        "within_standard_window"
                        if decision == ALLOW
                        else "outside_standard_window"
                    ),
                    policy_basis=(BASIS_STANDARD_WINDOW if decision == ALLOW else ""),
                    eligible_at=NOW,
                )

    def test_undocumented_reason_code_raises_UnstablePolicyDecision(self):
        with self.assertRaises(UnstablePolicyDecision):
            OutgoingDecision(
                decision=ALLOW,
                reason_code="forged_code",
                policy_basis=BASIS_STANDARD_WINDOW,
            )

    def test_reason_code_decision_mismatch_raises(self):
        with self.assertRaises(UnstablePolicyDecision):
            OutgoingDecision(decision=BLOCK, reason_code="within_standard_window")

    def test_unknown_decision_raises(self):
        with self.assertRaises(UnstablePolicyDecision):
            OutgoingDecision(decision="maybe", reason_code="within_standard_window")

    # --- политика не использует сеть и не зовёт ORM ------------------------

    def test_policy_module_does_not_import_requests_or_httpx(self):
        src = pathlib.Path("management/services/ig_outgoing_policy.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(
                        alias.name, {"requests", "httpx", "urllib3", "aiohttp"}
                    )
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    self.assertNotIn(
                        node.module.split(".")[0],
                        {"requests", "httpx", "urllib3", "aiohttp"},
                    )

    def test_policy_module_does_not_import_django_db(self):
        src = pathlib.Path("management/services/ig_outgoing_policy.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("django.db"):
                    self.fail(f"policy imports {node.module}")
