"""ЭА — приёмочные тесты купирующего среза: спам «технічна затримка».

Каждый тест назван по инварианту из плана (И1…И6), чтобы отказ теста прямо
указывал, какой инвариант нарушен.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import (
    GeminiRequestAttempt,
    IgClient,
    IgClientDegradationEpisode,
    IgProviderIncident,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import ig_provider_incidents as incidents
from management.services.ig_apology_policy import (
    apply_apology_policy,
    contains_apology,
    strip_leading_apology,
)


def _inbound(client, text, **kwargs):
    return InstagramBotMessage.objects.create(
        sender_id=client.igsid,
        client=client,
        role=InstagramBotMessage.Role.USER,
        text=text,
        status=kwargs.pop("status", InstagramBotMessage.Status.PENDING),
        **kwargs,
    )


def _outgoing(client, text, **kwargs):
    return InstagramBotMessage.objects.create(
        sender_id=client.igsid,
        client=client,
        role=InstagramBotMessage.Role.MODEL,
        text=text,
        status=InstagramBotMessage.Status.DONE,
        send_state="sent",
        provider_message_id=kwargs.pop("provider_message_id", "mid-1"),
        **kwargs,
    )


class ProviderIncidentCoalescingTests(TestCase):
    """ЭА.2 — один инцидент на (роль, класс отказа), а не на каждый сбой."""

    def test_twenty_three_quota_failures_across_six_aliases_are_one_incident(self):
        for index in range(23):
            incidents.register_provider_failure(
                role="chat",
                failure_kind="quota_429",
                http_code=429,
                model="gemini-3.7-flash",
                key_name=f"GEMINI_API{index % 6 + 1}",
            )

        self.assertEqual(IgProviderIncident.objects.count(), 1)
        incident = IgProviderIncident.objects.get()
        self.assertEqual(incident.state, IgProviderIncident.State.OPEN)
        self.assertEqual(incident.failure_class, IgProviderIncident.FailureClass.QUOTA)
        self.assertEqual(incident.failure_count, 23)
        # Шість алиасів однієї моделі — шість областей одного інциденту, а не
        # шість інцидентів і шість holding.
        self.assertEqual(
            sorted(incident.observed_scopes),
            ["alias:GEMINI_API1", "alias:GEMINI_API2", "alias:GEMINI_API3",
             "alias:GEMINI_API4", "alias:GEMINI_API5", "alias:GEMINI_API6",
             "model:gemini-3.7-flash"],
        )

    def test_distinct_failure_classes_are_distinct_incidents(self):
        incidents.register_provider_failure(role="chat", failure_kind="quota_429", http_code=429)
        incidents.register_provider_failure(role="chat", failure_kind="read_timeout")

        self.assertEqual(IgProviderIncident.objects.count(), 2)
        self.assertEqual(
            set(IgProviderIncident.objects.values_list("failure_class", flat=True)),
            {
                IgProviderIncident.FailureClass.QUOTA,
                IgProviderIncident.FailureClass.TIMEOUT,
            },
        )

    def test_single_success_between_failures_does_not_close_incident(self):
        incidents.register_provider_failure(role="chat", failure_kind="quota_429", http_code=429)
        incidents.register_provider_success(role="chat")

        incident = IgProviderIncident.objects.get()
        self.assertEqual(incident.state, IgProviderIncident.State.RECOVERING)
        self.assertIsNotNone(incident.active_fingerprint)

        incidents.register_provider_failure(role="chat", failure_kind="quota_429", http_code=429)
        incident.refresh_from_db()
        self.assertEqual(incident.state, IgProviderIncident.State.OPEN)
        self.assertEqual(incident.consecutive_success_count, 0)

    def test_success_streak_closes_incident_and_frees_fingerprint(self):
        incidents.register_provider_failure(role="chat", failure_kind="quota_429", http_code=429)
        for _ in range(incidents.RECOVERING_SUCCESS_STREAK):
            incidents.register_provider_success(role="chat")

        incident = IgProviderIncident.objects.get()
        self.assertEqual(incident.state, IgProviderIncident.State.CLOSED)
        self.assertIsNone(incident.active_fingerprint)
        self.assertIsNone(incidents.active_incident("chat"))

    def test_stale_incident_is_closed_so_holding_is_never_suppressed_forever(self):
        incident = incidents.register_provider_failure(
            role="chat", failure_kind="quota_429", http_code=429
        )
        IgProviderIncident.objects.filter(pk=incident.pk).update(
            last_failure_at=timezone.now() - timedelta(minutes=30)
        )

        self.assertEqual(incidents.close_stale_incidents(), 1)
        incident.refresh_from_db()
        self.assertEqual(incident.state, IgProviderIncident.State.CLOSED)
        self.assertEqual(incident.close_reason, "coalesce_window_elapsed")

    def test_invalid_payload_is_not_treated_as_availability_degradation(self):
        incidents.register_provider_failure(
            role="chat", failure_kind="invalid_payload", http_code=400
        )

        self.assertIsNotNone(IgProviderIncident.objects.get().active_fingerprint)
        self.assertIsNone(incidents.active_incident("chat"))

    def test_attempt_telemetry_opens_incident_and_records_lineage(self):
        from management.services import gemini_keys
        from management.services.ig_turn_lineage import Lane, turn_lineage

        client = IgClient.get_or_create_for_sender("lineage-sender")
        row = _inbound(client, "Скільки коштує худі?")
        with turn_lineage(
            lane=Lane.LIVE,
            client_id=client.pk,
            source_message_id=row.pk,
            logical_turn_id=f"t{client.pk}:{row.pk}",
        ):
            gemini_keys.record_attempt(
                request_id="req-1",
                role="chat",
                key_name="GEMINI_API",
                model="gemini-3.7-flash",
                outcome="failed",
                failure_kind="quota_429",
                http_code=429,
                attempt_index=1,
                candidate_index=1,
            )

        attempt = GeminiRequestAttempt.objects.get()
        self.assertEqual(attempt.lane, Lane.LIVE)
        self.assertEqual(attempt.client_id, client.pk)
        self.assertEqual(attempt.source_message_id, row.pk)
        self.assertEqual(attempt.attempt_index, 1)
        self.assertEqual(IgProviderIncident.objects.count(), 1)


class HoldingCoalescingTests(TestCase):
    """И1 — за один инцидент один клиент получает ≤1 техническое сообщение."""

    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.ai_enabled = True
        self.settings.save(update_fields=["is_enabled", "ai_enabled"])
        self.ig_client = IgClient.get_or_create_for_sender("degradation-sender")
        self.incident = incidents.register_provider_failure(
            role="chat", failure_kind="quota_429", http_code=429,
            model="gemini-3.7-flash", key_name="GEMINI_API",
        )

    def _decide(self, row):
        return incidents.holding_decision(row, logical_turn_id=f"t{self.ig_client.pk}:{row.pk}")

    def test_three_inbounds_in_one_incident_yield_one_holding(self):
        first = _inbound(self.ig_client, "А це не ваш бренд Полуничка?")
        decision = self._decide(first)
        self.assertTrue(decision.should_send)
        self.assertEqual(decision.reason, "first_holding_in_incident")

        self.assertTrue(incidents.reserve_holding(decision.episode_id))
        holding = _outgoing(
            self.ig_client, "Перепрошую за технічну затримку.",
            source=incidents.HOLDING_MESSAGE_SOURCE, provider_message_id="mid-holding-1",
        )
        incidents.confirm_holding_sent(decision.episode_id, holding)

        second = _inbound(self.ig_client, "Можете розказати що у вас в асортименті")
        third = _inbound(self.ig_client, "Я спитав щоб знати просто що у вас")
        for row in (second, third):
            repeat = self._decide(row)
            self.assertFalse(repeat.should_send)
            self.assertEqual(repeat.reason, "already_sent_in_incident")

        episode = IgClientDegradationEpisode.objects.get()
        self.assertEqual(episode.state, IgClientDegradationEpisode.State.HOLDING_SENT)
        self.assertEqual(episode.inbound_count, 3)
        self.assertEqual(episode.latest_source_message_id, third.pk)
        self.assertEqual(episode.apology_count, 1)
        self.assertEqual(
            InstagramBotMessage.objects.filter(
                source=incidents.HOLDING_MESSAGE_SOURCE
            ).count(),
            1,
        )

    def test_ten_inbounds_in_one_incident_yield_one_holding(self):
        first = _inbound(self.ig_client, "Чи є худі розміру L?")
        decision = self._decide(first)
        self.assertTrue(incidents.reserve_holding(decision.episode_id))
        incidents.confirm_holding_sent(
            decision.episode_id,
            _outgoing(
                self.ig_client, "Перепрошую за технічну затримку.",
                source=incidents.HOLDING_MESSAGE_SOURCE,
                provider_message_id="mid-holding-2",
            ),
        )
        sends = 0
        for index in range(9):
            row = _inbound(self.ig_client, f"А чи є доставка Новою поштою {index}?")
            if self._decide(row).should_send:
                sends += 1
        self.assertEqual(sends, 0)
        self.assertEqual(IgClientDegradationEpisode.objects.count(), 1)

    def test_second_reservation_is_impossible_even_without_receipt(self):
        row = _inbound(self.ig_client, "Скільки коштує лонгслів?")
        decision = self._decide(row)
        self.assertTrue(incidents.reserve_holding(decision.episode_id))
        self.assertFalse(incidents.reserve_holding(decision.episode_id))

    def test_new_incident_after_closed_window_may_send_a_new_holding(self):
        first = _inbound(self.ig_client, "Чи є термохром?")
        decision = self._decide(first)
        incidents.reserve_holding(decision.episode_id)
        incidents.confirm_holding_sent(
            decision.episode_id,
            _outgoing(
                self.ig_client, "Перепрошую за технічну затримку.",
                source=incidents.HOLDING_MESSAGE_SOURCE,
                provider_message_id="mid-holding-3",
            ),
        )
        IgProviderIncident.objects.filter(pk=self.incident.pk).update(
            last_failure_at=timezone.now() - timedelta(minutes=30)
        )
        incidents.close_stale_incidents()

        new_incident = incidents.register_provider_failure(
            role="chat", failure_kind="quota_429", http_code=429
        )
        self.assertNotEqual(new_incident.pk, self.incident.pk)

        later = _inbound(self.ig_client, "А коли буде нова колекція?")
        repeat = self._decide(later)
        self.assertTrue(repeat.should_send, "нова деградація — це нова проблема")
        self.assertEqual(IgClientDegradationEpisode.objects.count(), 2)

    def test_daily_cap_blocks_the_third_incident_holding(self):
        for index in range(incidents.MAX_HOLDINGS_PER_CLIENT_PER_DAY):
            _outgoing(
                self.ig_client, "Перепрошую за технічну затримку.",
                source=incidents.HOLDING_MESSAGE_SOURCE,
                provider_message_id=f"mid-cap-{index}",
            )
        row = _inbound(self.ig_client, "Чи можна оформити замовлення?")
        decision = self._decide(row)
        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "daily_cap_reached")

    def test_manager_takeover_and_opt_out_never_receive_technical_text(self):
        self.ig_client.manager_takeover = True
        self.ig_client.save(update_fields=["manager_takeover"])
        row = _inbound(self.ig_client, "Де моє замовлення TWC12345?")
        row.client = self.ig_client
        self.assertEqual(self._decide(row).reason, "manager_takeover")

        self.ig_client.manager_takeover = False
        self.ig_client.opted_out_at = timezone.now()
        self.ig_client.save(update_fields=["manager_takeover", "opted_out_at"])
        row2 = _inbound(self.ig_client, "Скільки коштує?")
        row2.client = self.ig_client
        self.assertEqual(self._decide(row2).reason, "opted_out")

    def test_takeover_cancels_open_episode(self):
        row = _inbound(self.ig_client, "Чи є розмір M?")
        decision = self._decide(row)
        self.assertTrue(decision.episode_id)

        self.assertEqual(
            incidents.cancel_episodes_for_client(
                self.ig_client.pk, reason="manager_takeover"
            ),
            1,
        )
        episode = IgClientDegradationEpisode.objects.get(pk=decision.episode_id)
        self.assertEqual(episode.state, IgClientDegradationEpisode.State.CANCELLED)

    @override_settings(IG_OUTAGE_HOLDING_COALESCING=False)
    def test_flag_off_restores_previous_behaviour(self):
        row = _inbound(self.ig_client, "Привіт, що є в наявності?")
        decision = self._decide(row)
        self.assertTrue(decision.should_send)
        self.assertEqual(decision.reason, "coalescing_disabled")


class LowIntentGateTests(TestCase):
    """И3 — клиент, который не задавал вопроса, не получает техтекста."""

    def setUp(self):
        self.ig_client = IgClient.get_or_create_for_sender("low-intent-sender")
        incidents.register_provider_failure(
            role="chat", failure_kind="read_timeout", model="gemini-3.7-flash"
        )

    def _reason(self, text, **kwargs):
        row = _inbound(self.ig_client, text, **kwargs)
        row.client = self.ig_client
        return incidents.holding_decision(row).reason

    def test_acknowledgement_turns_are_suppressed(self):
        for text in ("Добре", "ок", "Дякую", "👍", "Ясно", "Норм"):
            _outgoing(self.ig_client, "Гарного дня!", provider_message_id=f"mid-{text}")
            self.assertEqual(
                self._reason(text), "low_intent_turn", f"текст: {text}"
            )

    def test_commercial_and_service_signals_are_never_suppressed(self):
        for text in (
            "Де моє замовлення?",
            "Скільки коштує худі",
            "Хочу оплатити",
            "Товар не прийшов",
            "потрібен розмір L",
        ):
            _outgoing(self.ig_client, "Вітаю!", provider_message_id=f"mid-c-{text[:8]}")
            self.assertNotEqual(self._reason(text), "low_intent_turn", f"текст: {text}")

    def test_acknowledgement_after_unanswered_question_is_not_suppressed(self):
        _outgoing(self.ig_client, "Вітаю!", provider_message_id="mid-ack-0")
        _inbound(self.ig_client, "А є розмір XL?")
        self.assertNotEqual(self._reason("Добре"), "low_intent_turn")

    def test_short_reply_to_a_bot_question_is_not_suppressed(self):
        _outgoing(
            self.ig_client, "Який розмір вам потрібен?", provider_message_id="mid-ask-1"
        )
        self.assertNotEqual(self._reason("Так"), "low_intent_turn")

    @override_settings(IG_LOW_INTENT_HOLDING_GATE=False)
    def test_flag_off_disables_only_the_intent_rule(self):
        _outgoing(self.ig_client, "Гарного дня!", provider_message_id="mid-off-1")
        self.assertNotEqual(self._reason("Добре"), "low_intent_turn")


class ApologyPolicyTests(TestCase):
    """И2 — сумма извинений в одном логическом ходе ≤1."""

    def test_production_double_apology_is_reduced_to_one(self):
        draft = "Вибачте за технічну затримку. Вибачте за затримку з відповіддю! Ось асортимент."
        text, count = apply_apology_policy(
            draft, language="uk", apology_already_delivered=False
        )
        self.assertEqual(count, 1)
        self.assertEqual(text.count("Вибачте"), 1)
        self.assertIn("Ось асортимент", text)

    def test_delivered_holding_removes_apology_entirely(self):
        draft = "Вибачте за затримку з відповіддю! У нас є худі, лонгсліви та футболки."
        text, count = apply_apology_policy(
            draft, language="uk", apology_already_delivered=True
        )
        self.assertEqual(count, 0)
        self.assertFalse(contains_apology(text))
        self.assertTrue(text.startswith("У нас є худі"))

    def test_model_apology_is_not_duplicated_by_code(self):
        for draft, language in (
            ("Перепрошую, що довелося чекати. Ось деталі.", "uk"),
            ("Извините за ожидание. Вот детали.", "ru"),
            ("Sorry for the wait. Here are the details.", "en"),
        ):
            text, count = apply_apology_policy(
                draft, language=language, apology_already_delivered=False
            )
            self.assertEqual(count, 1, draft)
            self.assertEqual(text, draft, draft)

    def test_missing_apology_is_added_once_per_language(self):
        for language, marker in (("uk", "Вибачте"), ("ru", "Извините"), ("en", "Sorry")):
            text, count = apply_apology_policy(
                "Ось повна відповідь.", language=language,
                apology_already_delivered=False,
            )
            self.assertEqual(count, 1)
            self.assertTrue(text.startswith(marker), text)

    def test_delivery_delay_wording_is_not_mistaken_for_an_apology(self):
        draft = "На складі є затримка через постачальника, тому відправка буде у вівторок."
        self.assertFalse(contains_apology(draft))
        text, count = apply_apology_policy(
            draft, language="uk", apology_already_delivered=True
        )
        self.assertEqual(count, 0)
        self.assertEqual(text, draft)

    def test_stripping_never_produces_a_truncated_fragment(self):
        draft = "Вибачте за затримку."
        stripped = strip_leading_apology(draft)
        self.assertEqual(stripped, draft, "нічого змістовного не залишилось — не ріжемо")

        inline = "Вибачте за затримку, ваше замовлення вже відправлено."
        self.assertTrue(strip_leading_apology(inline).startswith("Ваше замовлення"))

    def test_apology_in_the_middle_is_not_removed(self):
        draft = "Ваше замовлення відправлено. Вибачте за затримку."
        self.assertEqual(strip_leading_apology(draft), draft)


class RecoveryCursorTests(TestCase):
    """ЭА.7/ЭА.8 — один курсор восстановления и бюджет от состояния инцидента."""

    def setUp(self):
        from management.services import ig_ai_reply_recovery as recovery

        self.recovery = recovery
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled"])
        self.ig_client = IgClient.get_or_create_for_sender("cursor-sender")
        self.incident = incidents.register_provider_failure(
            role="chat", failure_kind="quota_429", http_code=429
        )

    def _episode(self, row):
        return incidents.ensure_client_episode(
            row, self.incident, logical_turn_id=f"t{self.ig_client.pk}:{row.pk}"
        )

    def test_three_inbounds_create_one_active_cursor(self):
        first = _inbound(self.ig_client, "Що у вас в асортименті?",
                         status=InstagramBotMessage.Status.DONE)
        episode = self._episode(first)
        job = self.recovery.schedule_recovery(first, degradation_episode=episode)

        second = _inbound(self.ig_client, "Я спитав просто щоб знати що у вас",
                          status=InstagramBotMessage.Status.DONE)
        self._episode(second)
        same = self.recovery.schedule_recovery(second, degradation_episode=episode)

        self.assertEqual(job.pk, same.pk)
        self.assertEqual(
            self.recovery.IgAiReplyRecoveryJob.objects.filter(
                active_cursor_key__isnull=False
            ).count(),
            1,
        )

    def test_cursor_answers_the_latest_customer_turn(self):
        first = _inbound(self.ig_client, "Що у вас в асортименті?",
                         status=InstagramBotMessage.Status.DONE)
        episode = self._episode(first)
        job = self.recovery.schedule_recovery(first, degradation_episode=episode)
        latest = _inbound(self.ig_client, "Я спитав просто щоб знати що у вас",
                          status=InstagramBotMessage.Status.DONE)
        self._episode(latest)

        job.refresh_from_db()
        self.assertEqual(self.recovery.effective_target_id(job), latest.pk)
        self.assertEqual(self.recovery.recovery_target_message(job).pk, latest.pk)

    def test_newer_inbound_does_not_cancel_the_cursor(self):
        first = _inbound(self.ig_client, "Що у вас є?",
                         status=InstagramBotMessage.Status.DONE)
        episode = self._episode(first)
        job = self.recovery.schedule_recovery(first, degradation_episode=episode)
        _inbound(self.ig_client, "Ще питання про доставку",
                 status=InstagramBotMessage.Status.DONE)

        job.refresh_from_db()
        reason = self.recovery._guard_reason(
            job, self.settings, self.ig_client, job.source_message, now=timezone.now()
        )
        self.assertEqual(reason, "")

    def test_manager_reply_still_cancels_the_cursor(self):
        first = _inbound(self.ig_client, "Що у вас є?",
                         status=InstagramBotMessage.Status.DONE)
        episode = self._episode(first)
        job = self.recovery.schedule_recovery(first, degradation_episode=episode)
        InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.MANAGER,
            text="Вітаю, я менеджер",
            status=InstagramBotMessage.Status.DONE,
        )

        job.refresh_from_db()
        reason = self.recovery._guard_reason(
            job, self.settings, self.ig_client, job.source_message, now=timezone.now()
        )
        self.assertEqual(reason, "newer_inbound_or_manager_reply")

    def test_holding_row_is_not_treated_as_a_substantive_reply(self):
        first = _inbound(self.ig_client, "Що у вас є?",
                         status=InstagramBotMessage.Status.DONE)
        episode = self._episode(first)
        job = self.recovery.schedule_recovery(first, degradation_episode=episode)
        _outgoing(
            self.ig_client, "Перепрошую за технічну затримку.",
            source=incidents.HOLDING_MESSAGE_SOURCE, provider_message_id="mid-h-1",
        )

        job.refresh_from_db()
        reason = self.recovery._guard_reason(
            job, self.settings, self.ig_client, job.source_message, now=timezone.now()
        )
        self.assertEqual(reason, "")

    def test_open_incident_spends_no_provider_attempts(self):
        first = _inbound(self.ig_client, "Що у вас є?",
                         status=InstagramBotMessage.Status.DONE)
        episode = self._episode(first)
        job = self.recovery.schedule_recovery(first, degradation_episode=episode)

        with patch.object(self.recovery, "_generate_recovery_draft") as generate, \
                patch.object(self.recovery, "send_text") as send:
            self.recovery.process_recovery_job(job.pk)

        generate.assert_not_called()
        send.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, job.Status.PENDING)
        self.assertEqual(job.attempts, 0)
        self.assertEqual(job.last_error, "incident_open_wait_for_recovery")

    def test_expired_cursor_hands_off_to_a_manager_without_customer_text(self):
        first = _inbound(self.ig_client, "Що у вас є?",
                         status=InstagramBotMessage.Status.DONE)
        episode = self._episode(first)
        job = self.recovery.schedule_recovery(first, degradation_episode=episode)
        stale = timezone.now() - incidents.RECOVERY_CURSOR_MAX_LIFETIME - timedelta(minutes=1)
        self.recovery.IgAiReplyRecoveryJob.objects.filter(pk=job.pk).update(
            activated_at=stale, created_at=stale
        )

        outgoing_before = InstagramBotMessage.objects.filter(
            role=InstagramBotMessage.Role.MODEL
        ).count()
        with patch.object(self.recovery, "notify_manager") as notify, \
                patch.object(self.recovery, "send_text") as send:
            self.recovery.process_recovery_job(job.pk)

        send.assert_not_called()
        notify.assert_called_once()
        self.assertEqual(
            InstagramBotMessage.objects.filter(
                role=InstagramBotMessage.Role.MODEL
            ).count(),
            outgoing_before,
            "виснаження recovery не має створювати другого технічного тексту",
        )
        job.refresh_from_db()
        self.assertEqual(job.status, job.Status.FAILED)
        self.assertIsNone(job.active_cursor_key)
        episode.refresh_from_db()
        self.assertEqual(episode.state, IgClientDegradationEpisode.State.MANUAL)

    def test_recovery_after_incident_recovery_sends_one_reply_without_apology(self):
        first = _inbound(self.ig_client, "Що у вас в асортименті?",
                         status=InstagramBotMessage.Status.DONE)
        episode = self._episode(first)
        holding = _outgoing(
            self.ig_client, "Перепрошую за технічну затримку.",
            source=incidents.HOLDING_MESSAGE_SOURCE, provider_message_id="mid-h-2",
        )
        incidents.reserve_holding(episode.pk)
        incidents.confirm_holding_sent(episode.pk, holding)
        job = self.recovery.schedule_recovery(
            first, holding_message=holding, degradation_episode=episode
        )
        for _ in range(incidents.RECOVERING_SUCCESS_STREAK):
            incidents.register_provider_success(role="chat")

        from management.services.instagram_bot import ProviderDeliveryReceipt

        with patch.object(
            self.recovery, "_generate_recovery_draft",
            return_value="У нас є худі, лонгсліви та футболки з авторськими принтами.",
        ), patch.object(
            self.recovery, "send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "mid-recovery-1"),
        ) as send:
            result = self.recovery.process_recovery_job(job.pk)

        send.assert_called_once()
        result.refresh_from_db()
        self.assertEqual(result.status, result.Status.SENT)
        self.assertFalse(contains_apology(result.draft_text))
        episode.refresh_from_db()
        self.assertEqual(episode.apology_count, 1)
        self.assertEqual(episode.state, IgClientDegradationEpisode.State.RECOVERED)


class DegradationBaselineCommandTests(TestCase):
    """ЭА.0 — замер повторяем одной командой до и после правки."""

    def test_command_reports_durable_and_proxy_metrics_without_customer_text(self):
        from io import StringIO
        import json as _json

        from django.core.management import call_command

        ig_client = IgClient.get_or_create_for_sender("baseline-sender")
        inbound = _inbound(ig_client, "Скільки коштує худі?",
                           status=InstagramBotMessage.Status.DONE)
        incident = incidents.register_provider_failure(
            role="chat", failure_kind="quota_429", http_code=429
        )
        episode = incidents.ensure_client_episode(inbound, incident)
        incidents.reserve_holding(episode.pk)
        incidents.confirm_holding_sent(
            episode.pk,
            _outgoing(
                ig_client, "Перепрошую за технічну затримку.",
                source=incidents.HOLDING_MESSAGE_SOURCE,
                provider_message_id="mid-baseline-1",
            ),
        )

        out = StringIO()
        call_command("ig_degradation_baseline", "--days", "2", "--json", stdout=out)
        payload = _json.loads(out.getvalue())

        self.assertEqual(payload["window_days"], 2)
        self.assertEqual(payload["metrics"]["durable"]["incidents"], 1)
        self.assertEqual(payload["metrics"]["durable"]["incident_client_pairs"], 1)
        self.assertEqual(payload["metrics"]["durable"]["holding_rows"], 1)
        self.assertEqual(
            payload["metrics"]["durable"]["holding_per_incident_client"], 1.0
        )
        self.assertEqual(payload["metrics"]["holding_rows"]["total"], 1)
        self.assertNotIn("Скільки коштує худі", out.getvalue())
        self.assertNotIn("Перепрошую", out.getvalue())

    def test_text_report_runs_on_an_empty_window(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("ig_degradation_baseline", "--days", "1", stdout=out)
        self.assertIn("Holding per incident-client", out.getvalue())
        self.assertIn("proxy-incident window = 5 minutes", out.getvalue())
