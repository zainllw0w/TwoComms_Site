"""ЭА.21 — ідемпотентний намір відправки, `UNKNOWN` і сверка читанням.

Правило «не ретраїти Meta Send після неоднозначного таймауту» вже було вірним,
але трималось на послідовності перевірок у коді. Ці тести переносять його в
обмеження БД: другий намір того самого сенсу в тому самому ході неможливий, а
рестарт процесу посеред відправки не створює другого повідомлення клієнту.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, IgCustomerTurn, InstagramBotMessage
from management.services import ig_customer_turns as turns
from management.services import ig_send_intent


class _Fixture(TestCase):
    def setUp(self):
        self.ig_client = IgClient.get_or_create_for_sender("intent-sender")

    def _inbound(self, text="хочу худі", **kwargs):
        kwargs.setdefault("status", InstagramBotMessage.Status.PROCESSING)
        return InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text=text,
            processing_started_at=timezone.now(),
            **kwargs,
        )

    def _own_claim(self, row):
        return InstagramBotMessage.objects.filter(
            pk=row.pk,
            status=InstagramBotMessage.Status.PROCESSING,
            processing_started_at=row.processing_started_at,
        )


class SendIntentKeyTests(_Fixture):
    def test_turn_scoped_key_when_the_turn_is_known(self):
        self.assertEqual(
            ig_send_intent.build_key(turn_id=8, revision=3, kind="substantive"),
            "t8:r3:substantive",
        )

    def test_row_scoped_key_is_the_fallback_without_a_turn(self):
        row = self._inbound()
        self.assertEqual(
            ig_send_intent.build_key(row=row, kind="ack"), f"m{row.pk}:ack"
        )

    def test_key_fits_the_column(self):
        key = ig_send_intent.build_key(turn_id=10**9, revision=10**6, kind="corrective")
        self.assertLessEqual(len(key), 120)


class SendIntentClaimTests(_Fixture):
    def test_claim_marks_sending_and_stores_the_key(self):
        row = self._inbound()
        key, claimed = ig_send_intent.claim_send_intent(
            self._own_claim(row), row, turn_id=8
        )

        row.refresh_from_db()
        self.assertEqual(claimed, 1)
        self.assertEqual(key, "t8:r0:substantive")
        self.assertEqual(row.send_state, "sending")
        self.assertEqual(row.send_idempotency_key, key)
        self.assertIsNotNone(row.send_started_at)

    def test_a_second_row_of_the_same_turn_cannot_claim_the_same_intent(self):
        """Саме це раніше не було закріплено в БД: другий substantive у ході."""
        first = self._inbound("фото")
        second = self._inbound("Вітаю")
        key_a, claimed_a = ig_send_intent.claim_send_intent(
            self._own_claim(first), first, turn_id=8
        )
        key_b, claimed_b = ig_send_intent.claim_send_intent(
            self._own_claim(second), second, turn_id=8
        )

        self.assertEqual((key_a, claimed_a), ("t8:r0:substantive", 1))
        self.assertEqual(key_b, "t8:r0:substantive")
        self.assertEqual(claimed_b, 0, "друга заявка того самого наміру заборонена")
        second.refresh_from_db()
        self.assertEqual(second.send_state, "")

    def test_replaying_the_same_row_keeps_one_intent(self):
        """Рестарт процесу: та сама строка заявляє той самий ключ — не дублікат."""
        row = self._inbound()
        ig_send_intent.claim_send_intent(self._own_claim(row), row, turn_id=8)
        row.refresh_from_db()
        again = InstagramBotMessage.objects.filter(pk=row.pk)
        key, claimed = ig_send_intent.claim_send_intent(again, row, turn_id=8)

        self.assertEqual(claimed, 1)
        self.assertEqual(
            InstagramBotMessage.objects.filter(send_idempotency_key=key).count(), 1
        )

    def test_ack_and_substantive_are_different_intents_of_one_turn(self):
        ack_row = self._inbound("Вітаю")
        substantive_row = self._inbound("хочу худі")
        _, ack_claimed = ig_send_intent.claim_send_intent(
            self._own_claim(ack_row), ack_row, turn_id=8, kind=ig_send_intent.KIND_ACK
        )
        _, substantive_claimed = ig_send_intent.claim_send_intent(
            self._own_claim(substantive_row), substantive_row, turn_id=8
        )

        self.assertEqual((ack_claimed, substantive_claimed), (1, 1))

    def test_lost_worker_claim_does_not_mark_sending(self):
        row = self._inbound()
        stale = InstagramBotMessage.objects.filter(
            pk=row.pk, processing_started_at=timezone.now() + timedelta(hours=1)
        )
        key, claimed = ig_send_intent.claim_send_intent(stale, row, turn_id=8)

        row.refresh_from_db()
        self.assertEqual(claimed, 0)
        self.assertEqual(row.send_state, "")
        self.assertIsNone(row.send_idempotency_key)
        self.assertEqual(key, "t8:r0:substantive")

    def test_intent_owner_names_the_row_holding_the_key(self):
        row = self._inbound()
        key, _ = ig_send_intent.claim_send_intent(self._own_claim(row), row, turn_id=8)
        self.assertEqual(ig_send_intent.intent_owner(key).pk, row.pk)
        self.assertIsNone(ig_send_intent.intent_owner("t999:r0:substantive"))


class UnknownReconciliationTests(_Fixture):
    """Сверка виконується ЧИТАННЯМ уже збереженого поллінгом, не відправкою."""

    def _unknown_row(self, *, age_seconds, text="ось відповідь"):
        started = timezone.now() - timedelta(seconds=age_seconds)
        row = self._inbound()
        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.FAILED,
            send_state="unknown",
            send_started_at=started,
            delivery_original_text=text,
        )
        row.refresh_from_db()
        return row

    def _page_side(self, text, *, at=None):
        return InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.MODEL,
            text=text,
            status=InstagramBotMessage.Status.DONE,
            mid="poll-mid-1",
            source="poll",
            provider_created_at=at or timezone.now(),
        )

    def test_page_side_evidence_resolves_unknown_to_sent(self):
        row = self._unknown_row(age_seconds=3600)
        self._page_side("ось відповідь")

        outcome = ig_send_intent.reconcile_unknown_sends(apply=True)

        row.refresh_from_db()
        self.assertEqual(outcome["counts"], {"resolved_sent": 1})
        self.assertEqual(row.send_state, "sent")
        self.assertIsNotNone(row.send_completed_at)

    def test_fresh_unknown_stays_pending_because_polling_may_lag(self):
        self._unknown_row(age_seconds=10)
        outcome = ig_send_intent.reconcile_unknown_sends(apply=True)
        self.assertEqual(outcome["counts"], {"pending": 1})

    def test_old_unknown_without_evidence_is_not_delivered_not_resent(self):
        row = self._unknown_row(
            age_seconds=int(ig_send_intent.RECONCILE_MAX_AGE.total_seconds()) + 60
        )

        outcome = ig_send_intent.reconcile_unknown_sends(apply=True)

        row.refresh_from_db()
        self.assertEqual(outcome["counts"], {"not_delivered": 1})
        self.assertEqual(row.send_state, "unknown", "стан не стає sent і не ретраїться")
        self.assertEqual(row.delivery_failure_boundary, "unknown_not_delivered")

    def test_unrelated_page_side_text_is_not_accepted_as_evidence(self):
        self._unknown_row(age_seconds=3600, text="ось відповідь")
        self._page_side("зовсім інший текст")

        outcome = ig_send_intent.reconcile_unknown_sends(apply=False)

        self.assertEqual(outcome["counts"], {"pending": 1})

    def test_page_side_message_before_the_send_is_not_evidence(self):
        row = self._unknown_row(age_seconds=3600)
        self._page_side(
            "ось відповідь", at=row.send_started_at - timedelta(minutes=5)
        )

        outcome = ig_send_intent.reconcile_unknown_sends(apply=False)

        self.assertEqual(outcome["counts"], {"pending": 1})

    def test_dry_run_writes_nothing(self):
        row = self._unknown_row(age_seconds=3600)
        self._page_side("ось відповідь")

        ig_send_intent.reconcile_unknown_sends(apply=False)

        row.refresh_from_db()
        self.assertEqual(row.send_state, "unknown")


class DuplicateOutboundReportTests(_Fixture):
    """Чисельна перевірка того, що джерело позначило як `UNVERIFIED`."""

    def _outbound(self, text, provider_id, created_at):
        row = InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.MODEL,
            text=text,
            status=InstagramBotMessage.Status.DONE,
            provider_message_id=provider_id,
        )
        InstagramBotMessage.objects.filter(pk=row.pk).update(created_at=created_at)
        return row

    def test_two_identical_texts_with_different_provider_ids_are_reported(self):
        now = timezone.now()
        self._outbound("однакова відповідь", "mid-a", now)
        self._outbound("однакова відповідь", "mid-b", now + timedelta(seconds=6))

        report = ig_send_intent.duplicate_outbound_report()

        self.assertEqual(report["duplicate_pairs"], 1)
        self.assertEqual(report["examples"][0]["gap_seconds"], 6)

    def test_the_same_provider_id_is_one_message_not_a_duplicate(self):
        now = timezone.now()
        self._outbound("однакова відповідь", "mid-a", now)
        self._outbound("однакова відповідь", "mid-a", now + timedelta(seconds=6))

        self.assertEqual(ig_send_intent.duplicate_outbound_report()["duplicate_pairs"], 0)

    def test_identical_text_far_apart_is_a_legitimate_repeat(self):
        now = timezone.now()
        self._outbound("однакова відповідь", "mid-a", now)
        self._outbound("однакова відповідь", "mid-b", now + timedelta(hours=3))

        self.assertEqual(ig_send_intent.duplicate_outbound_report()["duplicate_pairs"], 0)


class LiveSendPathIntentTests(_Fixture):
    """Живий шлях відправки бере намір від ходу, а не від рядка."""

    def test_live_helper_derives_the_turn_from_membership(self):
        from management.services.instagram_bot import _claim_send_intent

        row = self._inbound()
        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.PENDING
        )
        row.refresh_from_db()
        turns.ensure_turn_for_inbound(row)
        turn = IgCustomerTurn.objects.get(client=self.ig_client)
        InstagramBotMessage.objects.filter(pk=row.pk).update(
            status=InstagramBotMessage.Status.PROCESSING,
            processing_started_at=timezone.now(),
        )
        row.refresh_from_db()

        key, claimed = _claim_send_intent(row, kind=ig_send_intent.KIND_SUBSTANTIVE)

        self.assertEqual(claimed, 1)
        self.assertEqual(key, f"t{turn.pk}:r0:substantive")
