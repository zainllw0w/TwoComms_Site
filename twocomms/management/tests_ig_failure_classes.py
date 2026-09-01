"""ЭА.10 — типизированные классы отказов: раздельные счётчики и circuit.

Каждый тест назван по требованию раздела. Рядом с RED-тестом стоит control,
который выполняет тот же сценарий на старом (легаси) пути и показывает, что
дефект был настоящий, а не выдуманный ради теста.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import (
    GeminiKeyState,
    GeminiRequestAttempt,
    IgClient,
    IgFollowUpTask,
    IgProviderIncident,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import gemini_keys
from management.services import ig_failure_classes as classes
from management.services import ig_provider_incidents as incidents


def _inbound(client, text, **kwargs):
    return InstagramBotMessage.objects.create(
        sender_id=client.igsid,
        client=client,
        role=InstagramBotMessage.Role.USER,
        text=text,
        status=kwargs.pop("status", InstagramBotMessage.Status.PENDING),
        **kwargs,
    )


def _attempt(
    *,
    failure_kind="",
    http_code=None,
    outcome="failed",
    role="chat",
    model="gemini-3.7-flash",
    key_name="GEMINI_API",
    created_at=None,
    request_id="req-typed",
    error_detail="",
):
    """Один durable рядок телеметрії — це і є подія для типізованих счётчиків."""
    attempt = gemini_keys.record_attempt(
        request_id=request_id,
        role=role,
        key_name=key_name,
        model=model,
        outcome=outcome,
        failure_kind=failure_kind,
        http_code=http_code,
        error_detail=error_detail,
    )
    if created_at is not None:
        # `created_at` у контракті спроби незмінне, тому вік події у тесті
        # виставляється через базовий менеджер — так само, як це робить
        # `validate_attempt_contract`.
        GeminiRequestAttempt._base_manager.filter(pk=attempt.pk).update(
            created_at=created_at
        )
    return attempt


class ClosedFailureClassListTests(TestCase):
    """Закрытый перечень классов и однозначное отображение kind → класс."""

    def test_closed_class_list_is_exactly_the_documented_nine(self):
        self.assertEqual(
            set(classes.FAILURE_CLASSES),
            {
                "quota",
                "unavailable",
                "timeout",
                "connect",
                "invalid_payload",
                "auth",
                "not_found",
                "empty",
                "unknown",
            },
        )

    def test_every_runtime_failure_kind_maps_into_the_closed_list(self):
        runtime_kinds = {
            "quota_429": "quota",
            "http_5xx": "unavailable",
            "provider_error": "unavailable",
            "read_timeout": "timeout",
            "http_408": "timeout",
            "timeout": "timeout",
            "transport": "connect",
            "transport_error": "connect",
            "invalid_payload": "invalid_payload",
            "request_error": "invalid_payload",
            "invalid_key": "auth",
            "permission_denied": "auth",
            "forbidden": "auth",
            "model_not_found": "not_found",
            "model_unavailable": "not_found",
            "empty": "empty",
            "invalid_response": "empty",
            "malformed_response": "empty",
        }
        for kind, expected in runtime_kinds.items():
            self.assertEqual(classes.classify(kind), expected, f"kind={kind}")
        self.assertEqual(classes.classify("what_is_this"), "unknown")

    def test_http_codes_alone_are_enough_to_type_a_failure(self):
        self.assertEqual(classes.classify("", 429), "quota")
        self.assertEqual(classes.classify("", 503), "unavailable")
        self.assertEqual(classes.classify("", 408), "timeout")
        self.assertEqual(classes.classify("", 400), "invalid_payload")
        self.assertEqual(classes.classify("", 401), "auth")
        self.assertEqual(classes.classify("", 403), "auth")
        self.assertEqual(classes.classify("", 404), "not_found")

    def test_not_found_is_a_separate_class_from_invalid_payload(self):
        """404 — це конфігурація моделі, 400 — наш payload. Різні дії."""
        self.assertNotEqual(
            classes.classify("model_not_found", 404),
            classes.classify("invalid_payload", 400),
        )
        self.assertEqual(classes.classify("model_not_found", 404), "not_found")

    def test_control_legacy_incident_column_has_no_not_found_class(self):
        """Control: у колонці інциденту класу `not_found` не існує.

        Це не претензія до БД, а фіксація факту: рішення приймалось за класом,
        у якому 404 і 400 були одним значенням.
        """
        self.assertNotIn(
            "not_found",
            {choice for choice, _label in IgProviderIncident.FailureClass.choices},
        )


class SeparateCountersTests(TestCase):
    """`timeout` не увеличивает `unavailable` и наоборот."""

    def test_timeout_and_unavailable_have_independent_counters(self):
        for _ in range(3):
            _attempt(failure_kind="read_timeout")
        _attempt(failure_kind="http_5xx", http_code=503)

        counts = classes.failure_counts("chat")
        self.assertEqual(counts["timeout"], 3)
        self.assertEqual(counts["unavailable"], 1)
        self.assertEqual(counts["quota"], 0)

    def test_control_legacy_key_counter_conflates_both_causes(self):
        """Control: єдиний счётчик ключа не розрізняє причини.

        Чотири події (три таймаути й одна недоступність) дають одне число 4 —
        по ньому неможливо вибрати дію: чекати бэкофф чи питати про таймаут.
        """
        for _ in range(3):
            gemini_keys.record_key_failure("GEMINI_API", failure_kind="read_timeout")
        gemini_keys.record_key_failure(
            "GEMINI_API", failure_kind="http_5xx", http_code=503
        )

        state = GeminiKeyState.get("GEMINI_API")
        self.assertEqual(state.consecutive_failures, 4)
        self.assertEqual(state.last_failure_kind, "http_5xx")

    def test_counters_are_scoped_per_model_and_alias(self):
        _attempt(failure_kind="read_timeout", model="gemini-3.7-flash", key_name="A1")
        _attempt(failure_kind="read_timeout", model="gemini-3.5-flash-lite", key_name="A2")

        flash = classes.failure_counts("chat", scope="model:gemini-3.7-flash")
        lite = classes.failure_counts("chat", scope="alias:A2")
        self.assertEqual(flash["timeout"], 1)
        self.assertEqual(lite["timeout"], 1)
        self.assertEqual(classes.failure_counts("chat")["timeout"], 2)

    def test_not_attempted_candidates_are_not_failures(self):
        gemini_keys.record_attempt(
            request_id="req-skip",
            role="chat",
            key_name="GEMINI_API",
            model="gemini-3.7-flash",
            outcome="not_attempted",
            not_attempted_reason="quota_exhausted",
        )
        self.assertEqual(sum(classes.failure_counts("chat").values()), 0)


class ThresholdCircuitTests(TestCase):
    """Circuit открывается по пороговой политике, а не по одному отказу."""

    def test_single_failure_does_not_open_the_circuit(self):
        _attempt(failure_kind="read_timeout")
        state = classes.circuit_state("chat", "timeout")
        self.assertEqual(state.state, classes.CLOSED)
        self.assertEqual(state.failures, 1)
        self.assertGreater(state.threshold, 1)

    def test_control_one_failure_already_declared_provider_degradation(self):
        """Control: одного відказу досі достатньо, щоб роль вважалась деградованою."""
        incidents.register_provider_failure(role="chat", failure_kind="read_timeout")
        self.assertIsNotNone(incidents.active_incident("chat"))
        self.assertEqual(IgProviderIncident.objects.get().failure_count, 1)

    def test_threshold_failures_in_window_open_the_circuit(self):
        policy = classes.policy("timeout")
        for _ in range(policy.threshold):
            _attempt(failure_kind="read_timeout")

        state = classes.circuit_state("chat", "timeout")
        self.assertEqual(state.state, classes.OPEN)
        self.assertEqual(state.failures, policy.threshold)
        # Сусідній клас лишається закритим: це різні причини й різні дії.
        self.assertEqual(
            classes.circuit_state("chat", "unavailable").state, classes.CLOSED
        )

    def test_failures_older_than_the_window_do_not_open_the_circuit(self):
        policy = classes.policy("timeout")
        stale = timezone.now() - timedelta(seconds=policy.window_seconds + 60)
        for _ in range(policy.threshold + 2):
            _attempt(failure_kind="read_timeout", created_at=stale)

        self.assertEqual(classes.circuit_state("chat", "timeout").state, classes.CLOSED)

    def test_success_after_failures_closes_the_circuit(self):
        policy = classes.policy("timeout")
        for _ in range(policy.threshold):
            _attempt(failure_kind="read_timeout")
        _attempt(outcome="succeeded")

        state = classes.circuit_state("chat", "timeout")
        self.assertEqual(state.state, classes.CLOSED)
        self.assertEqual(state.reason, "success_after_failures")

    def test_half_open_allows_exactly_one_probe(self):
        policy = classes.policy("timeout")
        now = timezone.now()
        opened_at = now - timedelta(seconds=policy.cooldown_seconds + 5)
        for _ in range(policy.threshold):
            _attempt(failure_kind="read_timeout", created_at=opened_at)

        half_open = classes.circuit_state("chat", "timeout", now=now)
        self.assertEqual(half_open.state, classes.HALF_OPEN)
        self.assertTrue(half_open.probe_allowed)

        # Пробна спроба витрачена: другої в цьому вікні бути не може.
        _attempt(failure_kind="read_timeout", created_at=now - timedelta(seconds=1))
        spent = classes.circuit_state("chat", "timeout", now=now)
        self.assertEqual(spent.state, classes.OPEN)
        self.assertFalse(spent.probe_allowed)

    @override_settings(IG_TYPED_FAILURE_CIRCUIT=False)
    def test_flag_off_keeps_counters_but_never_opens_a_circuit(self):
        """Наблюдаемость безопасна: счётчики пишутся всегда, решение — по флагу."""
        policy = classes.policy("timeout")
        for _ in range(policy.threshold):
            _attempt(failure_kind="read_timeout")

        self.assertEqual(classes.failure_counts("chat")["timeout"], policy.threshold)
        state = classes.circuit_state("chat", "timeout")
        self.assertEqual(state.state, classes.CLOSED)
        self.assertEqual(state.reason, "circuit_disabled")


class ClassDecisionTests(TestCase):
    """Три отказа разных классов → три разных решения, а не один `provider_outage`."""

    def test_three_classes_yield_three_different_decisions(self):
        quota = classes.decide("quota_429", 429)
        timeout = classes.decide("read_timeout")
        payload = classes.decide("invalid_payload", 400)

        self.assertEqual(
            len({quota.decision, timeout.decision, payload.decision}),
            3,
            "разные классы обязаны давать разные решения",
        )
        self.assertTrue(quota.provider_circuit)
        self.assertTrue(timeout.provider_circuit)
        self.assertFalse(payload.provider_circuit)

    def test_invalid_payload_is_our_defect_not_provider_degradation(self):
        decision = classes.decide("invalid_payload", 400)
        self.assertFalse(decision.provider_circuit)
        self.assertTrue(decision.payload_circuit)
        self.assertFalse(decision.retry_same_payload)
        self.assertFalse(decision.customer_notice_allowed)

    def test_auth_and_not_found_go_straight_to_a_manager_case(self):
        cases = (("invalid_key", 401), ("permission_denied", 403), ("model_not_found", 404))
        for kind, http_code in cases:
            decision = classes.decide(kind, http_code)
            self.assertTrue(decision.manager_case, kind)
            self.assertFalse(decision.retry_allowed, kind)
            self.assertFalse(decision.customer_notice_allowed, kind)
            self.assertFalse(decision.provider_circuit, kind)

    def test_availability_classes_may_still_show_one_customer_notice(self):
        cases = (
            ("quota_429", 429),
            ("http_5xx", 503),
            ("read_timeout", None),
            ("transport", None),
        )
        for kind, http_code in cases:
            decision = classes.decide(kind, http_code)
            self.assertTrue(decision.customer_notice_allowed, kind)
            self.assertTrue(decision.retry_allowed, kind)

    def test_invalid_payload_never_opens_a_provider_circuit_even_in_series(self):
        for _ in range(6):
            _attempt(failure_kind="invalid_payload", http_code=400)

        self.assertEqual(classes.failure_counts("chat")["invalid_payload"], 6)
        state = classes.circuit_state("chat", "invalid_payload")
        self.assertEqual(state.state, classes.CLOSED)
        self.assertEqual(state.reason, "not_a_provider_circuit")


class ConfigurationManagerCaseTests(TestCase):
    """`auth`/`not_found` не превращаются в клиентское «технічна затримка»."""

    def setUp(self):
        settings_obj = InstagramBotSettings.load()
        settings_obj.is_enabled = True
        settings_obj.ai_enabled = True
        settings_obj.save(update_fields=["is_enabled", "ai_enabled"])
        self.client_row = IgClient.get_or_create_for_sender("config-failure-sender")

    def _turn(self, text="Чи є худі розміру L?"):
        row = _inbound(self.client_row, text)
        row.client = self.client_row
        return row

    def _fail_turn_with(self, row, *, failure_kind, http_code):
        from management.services.ig_turn_lineage import Lane, turn_lineage

        with turn_lineage(
            lane=Lane.LIVE,
            client_id=self.client_row.pk,
            source_message_id=row.pk,
            logical_turn_id=f"t{self.client_row.pk}:{row.pk}",
        ):
            _attempt(failure_kind=failure_kind, http_code=http_code)
        incidents.register_provider_failure(
            role="chat", failure_kind=failure_kind, http_code=http_code
        )

    def test_auth_failure_never_produces_a_technical_delay_text(self):
        row = self._turn()
        self._fail_turn_with(row, failure_kind="invalid_key", http_code=401)

        decision = incidents.holding_decision(
            row, logical_turn_id=f"t{self.client_row.pk}:{row.pk}"
        )
        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "manager_case_configuration")

    def test_not_found_failure_never_produces_a_technical_delay_text(self):
        row = self._turn("А коли буде нова колекція?")
        self._fail_turn_with(row, failure_kind="model_not_found", http_code=404)

        decision = incidents.holding_decision(
            row, logical_turn_id=f"t{self.client_row.pk}:{row.pk}"
        )
        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "manager_case_configuration")

    def test_configuration_failure_opens_one_durable_manager_case(self):
        row = self._turn("Хочу оформити замовлення")
        self._fail_turn_with(row, failure_kind="permission_denied", http_code=403)

        turn_id = f"t{self.client_row.pk}:{row.pk}"
        incidents.holding_decision(row, logical_turn_id=turn_id)
        incidents.holding_decision(row, logical_turn_id=turn_id)

        tasks = IgFollowUpTask.objects.filter(
            client=self.client_row, kind=IgFollowUpTask.Kind.MANAGER_TASK
        )
        self.assertEqual(tasks.count(), 1, "один кейс на хід, а не по одному на виклик")
        self.assertEqual(tasks.get().skip_reason, "human_agent_required")

    @override_settings(IG_CONFIGURATION_MANAGER_CASE=False)
    def test_control_flag_off_restores_the_technical_delay_text(self):
        """Control: до правки конфігураційний відказ давав клієнту техтекст."""
        row = self._turn()
        self._fail_turn_with(row, failure_kind="invalid_key", http_code=401)

        decision = incidents.holding_decision(
            row, logical_turn_id=f"t{self.client_row.pk}:{row.pk}"
        )
        self.assertTrue(decision.should_send)
        self.assertEqual(decision.reason, "no_open_incident")

    def test_availability_failure_still_receives_its_single_holding(self):
        """Захист від надмірного придушення: реальна деградація не мовчить."""
        row = self._turn("Скільки коштує лонгслів?")
        self._fail_turn_with(row, failure_kind="read_timeout", http_code=None)

        decision = incidents.holding_decision(
            row, logical_turn_id=f"t{self.client_row.pk}:{row.pk}"
        )
        self.assertTrue(decision.should_send)

    def test_not_found_incident_is_not_availability_degradation(self):
        incidents.register_provider_failure(
            role="chat", failure_kind="model_not_found", http_code=404
        )
        self.assertIsNotNone(IgProviderIncident.objects.get().active_fingerprint)
        self.assertIsNone(incidents.active_incident("chat"))

    def test_configuration_class_is_not_retryable_for_recovery(self):
        from management.models import IgAiReplyRecoveryJob

        row = self._turn("Де моє замовлення?")
        job = IgAiReplyRecoveryJob.objects.create(
            client=self.client_row,
            source_message=row,
            status=IgAiReplyRecoveryJob.Status.PENDING,
        )
        from management.services.ig_turn_lineage import Lane, turn_lineage

        with turn_lineage(
            lane=Lane.RECOVERY,
            client_id=self.client_row.pk,
            source_message_id=row.pk,
            recovery_job_id=job.pk,
        ):
            _attempt(failure_kind="model_not_found", http_code=404)

        self.assertFalse(incidents.recovery_failure_is_retryable(job.pk))
