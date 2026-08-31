"""Э2.2B Phase 1 — lifecycle ходу, канонічний ключ і фактичний бюджет очікування.

Три prerequisite-дефекти, які ці тести закріплюють як виправлені:

1. `mark_turn_processed()` викликався ЛИШЕ у деградаційній гілці `_claim_next()`,
   тому жоден реально виконаний хід не ставав `PROCESSED`, а
   `record_completed_customer_turn()` не спрацьовував ніколи.
2. `resolve_logical_turn_key()` будував row-anchor евристикою і розходився з
   членством у ході, коли між повідомленнями клієнта встряв вихідний рядок.
3. `ig_turn_budget` оголошував фазу очікування як 20 с при фактичних 6 с, через
   що технічний текст клієнту стримувався на 14 с довше за реальний дедлайн.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgClient,
    IgCustomerTurn,
    InstagramBotMessage,
)
from management.services import ig_customer_turns as turns
from management.services import ig_turn_budget
from management.services.ig_turn_lineage import (
    logical_turn_key,
    resolve_logical_turn_key,
)


class _TurnFixture(TestCase):
    def setUp(self):
        self.ig_client = IgClient.get_or_create_for_sender("lifecycle-sender")

    def _inbound(self, text, **kwargs):
        kwargs.setdefault("status", InstagramBotMessage.Status.PENDING)
        return InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text=text,
            **kwargs,
        )

    def _outgoing(self, text):
        return InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.MODEL,
            text=text,
            status=InstagramBotMessage.Status.DONE,
        )

    def _claimed_turn(self, *rows, claimed_ago_seconds=0):
        now = timezone.now()
        for row in rows:
            turns.ensure_turn_for_inbound(row, now=now)
        turn = IgCustomerTurn.objects.filter(client=self.ig_client).order_by("-id").first()
        turn.claim_state = IgCustomerTurn.ClaimState.CLAIMED
        turn.claimed_at = now - timedelta(seconds=claimed_ago_seconds)
        turn.claim_token = "token"
        turn.save(update_fields=["claim_state", "claimed_at", "claim_token"])
        return turn


class TerminalTurnLifecycleTests(_TurnFixture):
    """Термінальний рядок мусить робити хід терміналом з класифікованою причиною."""

    def test_delivered_reply_terminalises_the_turn_as_replied(self):
        row = self._inbound("хочу худі", mid="m1")
        turn = self._claimed_turn(row)

        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.DONE, send_state="sent"
        )
        reason = turns.finalize_turn_for_row(row)

        turn.refresh_from_db()
        self.assertEqual(reason, IgCustomerTurn.TerminalReason.REPLIED)
        self.assertEqual(turn.claim_state, IgCustomerTurn.ClaimState.PROCESSED)
        self.assertEqual(turn.terminal_reason, IgCustomerTurn.TerminalReason.REPLIED)
        self.assertIsNotNone(turn.processed_at)
        self.assertEqual(turn.claim_token, "")

    def test_terminal_row_without_send_is_no_reply_needed_not_replied(self):
        row = self._inbound("дякую", mid="m1")
        self._claimed_turn(row)

        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.DONE, send_state=""
        )

        self.assertEqual(
            turns.finalize_turn_for_row(row),
            IgCustomerTurn.TerminalReason.NO_REPLY_NEEDED,
        )

    def test_unknown_delivery_is_classified_and_never_looks_delivered(self):
        row = self._inbound("оплатив", mid="m1")
        self._claimed_turn(row)

        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.FAILED, send_state="unknown"
        )

        self.assertEqual(
            turns.finalize_turn_for_row(row),
            IgCustomerTurn.TerminalReason.SEND_UNKNOWN,
        )

    def test_row_returned_to_pending_keeps_the_turn_alive(self):
        """Провайдерський backoff повертає рядок у pending — хід ще не завершений."""
        row = self._inbound("хочу худі", mid="m1")
        turn = self._claimed_turn(row)

        self.assertEqual(turns.finalize_turn_for_row(row), "")
        turn.refresh_from_db()
        self.assertEqual(turn.claim_state, IgCustomerTurn.ClaimState.CLAIMED)

    def test_row_without_membership_is_not_a_turn_transition(self):
        orphan = self._inbound("без ходу", mid="m1")
        InstagramBotMessage.objects.filter(pk=orphan.pk).update(
            status=InstagramBotMessage.Status.DONE
        )
        self.assertEqual(turns.finalize_turn_for_row(orphan), "")

    def test_materiality_recorder_finally_fires_for_a_real_turn(self):
        """Живий побічний ефект дефекту: shadow-телеметрія була порожня завжди."""
        row = self._inbound("хочу худі", mid="m1")
        self._claimed_turn(row)
        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.DONE, send_state="sent"
        )

        with patch(
            "management.services.ig_analysis_materiality.record_completed_customer_turn"
        ) as recorder:
            turns.finalize_turn_for_row(row)

        recorder.assert_called_once()


class StaleClaimedReconciliationTests(_TurnFixture):
    """Реконсиляція `CLAIMED` — класифікація, а не масовий слепий перехід."""

    def test_fresh_claim_is_never_reconciled(self):
        row = self._inbound("хочу худі", mid="m1")
        self._claimed_turn(row, claimed_ago_seconds=1)
        self.assertEqual(turns.reconcile_stale_claimed_turns()["scanned"], 0)

    def test_dry_run_reports_without_writing(self):
        row = self._inbound("хочу худі", mid="m1")
        turn = self._claimed_turn(
            row, claimed_ago_seconds=turns.turn_lease_seconds() + 60
        )
        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.DONE, send_state="sent"
        )

        outcome = turns.reconcile_stale_claimed_turns(apply=False)

        self.assertEqual(outcome["scanned"], 1)
        self.assertFalse(outcome["applied"])
        turn.refresh_from_db()
        self.assertEqual(turn.claim_state, IgCustomerTurn.ClaimState.CLAIMED)

    def test_apply_terminalises_with_the_classified_reason(self):
        row = self._inbound("хочу худі", mid="m1")
        turn = self._claimed_turn(
            row, claimed_ago_seconds=turns.turn_lease_seconds() + 60
        )
        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.DONE, send_state="sent"
        )

        turns.reconcile_stale_claimed_turns(apply=True)

        turn.refresh_from_db()
        self.assertEqual(turn.claim_state, IgCustomerTurn.ClaimState.PROCESSED)
        self.assertEqual(turn.terminal_reason, IgCustomerTurn.TerminalReason.REPLIED)

    def test_crossed_provider_boundary_is_unknown_not_replied(self):
        """`sending` без receipt — невідома доставка; ретрай заборонений."""
        row = self._inbound("оплатив", mid="m1")
        self._claimed_turn(row, claimed_ago_seconds=turns.turn_lease_seconds() + 60)
        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.PROCESSING, send_state="sending"
        )

        outcome = turns.reconcile_stale_claimed_turns(apply=False)

        self.assertEqual(
            outcome["counts"], {IgCustomerTurn.TerminalReason.SEND_UNKNOWN: 1}
        )

    def test_still_running_row_is_lease_expired_not_replied(self):
        row = self._inbound("хочу худі", mid="m1")
        self._claimed_turn(row, claimed_ago_seconds=turns.turn_lease_seconds() + 60)

        outcome = turns.reconcile_stale_claimed_turns(apply=False)

        self.assertEqual(
            outcome["counts"], {IgCustomerTurn.TerminalReason.LEASE_EXPIRED: 1}
        )


class TurnLifecycleCommandTests(_TurnFixture):
    """Операторська команда read-only за замовчуванням."""

    def _stale_turn(self):
        row = self._inbound("хочу худі", mid="m1")
        turn = self._claimed_turn(
            row, claimed_ago_seconds=turns.turn_lease_seconds() + 60
        )
        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.DONE, send_state="sent"
        )
        return turn

    def test_default_run_reports_and_writes_nothing(self):
        from io import StringIO

        from django.core.management import call_command

        turn = self._stale_turn()
        out = StringIO()
        call_command("ig_turn_lifecycle", stdout=out)

        turn.refresh_from_db()
        self.assertEqual(turn.claim_state, IgCustomerTurn.ClaimState.CLAIMED)
        self.assertIn("read-only", out.getvalue())

    def test_apply_writes_the_classification(self):
        from io import StringIO

        from django.core.management import call_command

        turn = self._stale_turn()
        call_command("ig_turn_lifecycle", "--apply", stdout=StringIO())

        turn.refresh_from_db()
        self.assertEqual(turn.claim_state, IgCustomerTurn.ClaimState.PROCESSED)
        self.assertEqual(turn.terminal_reason, IgCustomerTurn.TerminalReason.REPLIED)

    def test_json_output_is_machine_readable(self):
        import json
        from io import StringIO

        from django.core.management import call_command

        self._stale_turn()
        out = StringIO()
        call_command("ig_turn_lifecycle", "--json", stdout=out)

        payload = json.loads(out.getvalue())
        self.assertEqual(payload["scanned"], 1)
        self.assertFalse(payload["applied"])


class CanonicalLogicalTurnKeyTests(_TurnFixture):
    """Ключ ходу береться з членства, а не з евристики по сусідніх рядках."""

    def test_key_anchors_on_the_first_member_of_the_turn(self):
        first = self._inbound("хочу худі", mid="m1")
        second = self._inbound("чорне", mid="m2")
        now = timezone.now()
        turns.ensure_turn_for_inbound(first, now=now)
        turns.ensure_turn_for_inbound(second, now=now + timedelta(seconds=1))

        self.assertEqual(
            resolve_logical_turn_key(second),
            logical_turn_key(self.ig_client.pk, first.pk),
        )

    def test_membership_wins_over_an_interleaved_outgoing_row(self):
        """Саме тут row-anchor розходився: вихідний рядок посеред ходу.

        Stable ACK або службовий вихідний рядок не закриває смислового ходу, але
        row-anchor евристика вважала, що закриває, і давала ДРУГИЙ ключ — тобто
        другий holding у тому самому ході.
        """
        first = self._inbound("фото сертифіката", mid="m1")
        now = timezone.now()
        turns.ensure_turn_for_inbound(first, now=now)
        self._outgoing("фото отримано")
        second = self._inbound("Отримав сертифікат )", mid="m2")
        turns.ensure_turn_for_inbound(second, now=now + timedelta(seconds=2))

        turn = IgCustomerTurn.objects.get(client=self.ig_client)
        self.assertEqual(turns.turn_message_ids(turn), [first.pk, second.pk])
        self.assertEqual(
            resolve_logical_turn_key(second),
            logical_turn_key(self.ig_client.pk, first.pk),
            "членство в ході канонічне; евристика дала б ключ по другому рядку",
        )

    def test_historical_row_without_membership_uses_the_legacy_anchor(self):
        legacy = self._inbound("історичний рядок", mid="m1")
        self.assertEqual(
            resolve_logical_turn_key(legacy),
            logical_turn_key(self.ig_client.pk, legacy.pk),
        )

    def test_key_format_is_unchanged_so_open_episodes_keep_matching(self):
        """Формат ключа НЕ став `turn:{id}`: живі епізоди деградації співпадають."""
        row = self._inbound("хочу худі", mid="m1")
        turns.ensure_turn_for_inbound(row)
        key = resolve_logical_turn_key(row)
        self.assertTrue(key.startswith(f"t{self.ig_client.pk}:"), key)
        self.assertLessEqual(len(key), 64)


class ActualWaitBudgetTests(TestCase):
    """Оголошений бюджет очікування мусить дорівнювати фактичному."""

    def test_effective_wait_equals_the_real_debounce_not_the_dead_ceiling(self):
        self.assertEqual(
            turns.effective_max_wait_seconds(),
            turns.TURN_DEBOUNCE.total_seconds(),
        )
        self.assertNotEqual(
            turns.effective_max_wait_seconds(),
            turns.MAX_TURN_WAIT.total_seconds(),
            "MAX_TURN_WAIT мертвий, поки дедлайн не продовжується при attach",
        )

    def test_budget_wait_phase_reads_the_effective_wait(self):
        phase = next(
            p for p in ig_turn_budget.turn_phases() if p.name == "turn_debounce"
        )
        self.assertEqual(phase.max_seconds, turns.effective_max_wait_seconds())

    def test_customer_notice_threshold_follows_the_real_deadline(self):
        from management.services.call_ai_analysis import CHAT_COMPLEX_DEADLINE_SECONDS

        self.assertEqual(
            ig_turn_budget.customer_notice_threshold_seconds(),
            turns.effective_max_wait_seconds() + float(CHAT_COMPLEX_DEADLINE_SECONDS),
        )

    def test_heartbeat_window_still_exceeds_the_corrected_budget(self):
        self.assertGreater(
            ig_turn_budget.heartbeat_alive_window_seconds(),
            ig_turn_budget.declared_turn_budget_seconds(),
        )

    def test_wait_phase_collapses_to_zero_when_coalescing_is_disabled(self):
        with patch.object(turns, "_flag", return_value=False):
            self.assertEqual(turns.effective_max_wait_seconds(), 0.0)
