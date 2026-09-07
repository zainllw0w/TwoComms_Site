"""Э0.6 — `CustomerTurn`: одно понятие хода клиента для трёх механизмов."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import (
    IgClient,
    IgCustomerTurn,
    IgCustomerTurnRevision,
    IgTurnMessage,
    InstagramBotMessage,
)
from management.services import ig_customer_turns as turns


class CustomerTurnGroupingTests(TestCase):
    def setUp(self):
        self.ig_client = IgClient.get_or_create_for_sender("turn-sender")

    def _inbound(self, text, **kwargs):
        return InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text=text,
            status=InstagramBotMessage.Status.PENDING,
            **kwargs,
        )

    def test_burst_of_three_messages_is_one_turn(self):
        first = self._inbound("хочу худі", mid="m1")
        second = self._inbound("чорне", mid="m2")
        third = self._inbound("розмір L", mid="m3")

        now = timezone.now()
        created = turns.ensure_turn_for_inbound(first, now=now)
        attached_2 = turns.ensure_turn_for_inbound(second, now=now + timedelta(seconds=2))
        attached_3 = turns.ensure_turn_for_inbound(third, now=now + timedelta(seconds=4))

        self.assertTrue(created.created)
        self.assertFalse(attached_2.created)
        self.assertFalse(attached_3.created)
        self.assertEqual(IgCustomerTurn.objects.count(), 1)

        turn = IgCustomerTurn.objects.get()
        self.assertEqual(turn.message_count, 3)
        self.assertEqual(turn.primary_source_message_id, first.pk)
        self.assertEqual(
            turns.turn_message_ids(turn), [first.pk, second.pk, third.pk]
        )
        revisions = list(
            IgCustomerTurnRevision.objects.filter(client=self.ig_client)
            .order_by("revision")
        )
        self.assertEqual([revision.revision for revision in revisions], [1, 2, 3])
        self.assertEqual(
            revisions[-1].quiet_deadline,
            revisions[-1].quiet_cap_at,
        )
        self.assertEqual(
            revisions[-1].quiet_cap_at,
            now + timedelta(seconds=4),
        )
        self.assertEqual(revisions[-1].sources.count(), 3)
        self.assertEqual(
            turns.current_revision_id_for_message(third.pk), revisions[-1].pk
        )

    def test_primary_source_message_keeps_existing_one_to_one_contracts_usable(self):
        first = self._inbound("хочу худі", mid="m1")
        turns.ensure_turn_for_inbound(first)
        turn = IgCustomerTurn.objects.get()
        # Существующие OneToOneField(source_message) продолжают адресовать
        # ровно одну строку — иначе схема стала бы противоречивой.
        self.assertEqual(turn.primary_source_message.pk, first.pk)

    def test_message_after_the_deadline_opens_a_new_turn(self):
        first = self._inbound("хочу худі", mid="m1")
        now = timezone.now()
        turns.ensure_turn_for_inbound(first, now=now)

        late = self._inbound("а ще питання", mid="m2")
        result = turns.ensure_turn_for_inbound(
            late, now=now + turns.TURN_DEBOUNCE + timedelta(seconds=1)
        )

        self.assertTrue(result.created)
        self.assertEqual(IgCustomerTurn.objects.count(), 2)

    def test_closed_turn_is_never_reopened_by_a_late_message(self):
        first = self._inbound("хочу худі", mid="m1")
        now = timezone.now()
        turns.ensure_turn_for_inbound(first, now=now)
        turn = IgCustomerTurn.objects.get()
        turns.mark_turn_processed(turn.pk)

        late = self._inbound("ще одне", mid="m2")
        result = turns.ensure_turn_for_inbound(late, now=now + timedelta(seconds=1))

        self.assertTrue(result.created)
        self.assertNotEqual(result.turn.pk, turn.pk)
        turn.refresh_from_db()
        self.assertEqual(turn.claim_state, IgCustomerTurn.ClaimState.PROCESSED)

    def test_duplicate_webhook_of_the_same_row_adds_nothing(self):
        first = self._inbound("хочу худі", mid="m1")
        turns.ensure_turn_for_inbound(first)
        repeat = turns.ensure_turn_for_inbound(first)

        self.assertFalse(repeat.attached)
        self.assertEqual(repeat.reason, "already_attached")
        self.assertEqual(IgTurnMessage.objects.count(), 1)
        self.assertEqual(IgCustomerTurnRevision.objects.count(), 1)

    def test_same_attachment_with_a_new_url_signature_is_one_turn_message(self):
        """Э2.11: подписанные media URL одноразовые, они не идентичность."""
        first = self._inbound(
            "ось фото",
            mid=None,
            synthetic_event_key="syn-1",
            attachment_media=[{"provider_object_id": "obj-42", "url": "https://a/1?sig=A"}],
        )
        second = self._inbound(
            "ось фото",
            mid=None,
            synthetic_event_key="syn-2",
            attachment_media=[{"provider_object_id": "obj-42", "url": "https://a/1?sig=B"}],
        )

        now = timezone.now()
        turns.ensure_turn_for_inbound(first, now=now)
        result = turns.ensure_turn_for_inbound(second, now=now + timedelta(seconds=1))

        self.assertFalse(result.attached)
        self.assertEqual(result.reason, "duplicate_identity")
        self.assertEqual(IgCustomerTurn.objects.count(), 1)
        self.assertEqual(IgTurnMessage.objects.count(), 1)

    def test_different_attachments_stay_different_messages(self):
        first = self._inbound(
            "фото 1",
            mid=None,
            synthetic_event_key="syn-a",
            attachment_media=[{"provider_object_id": "obj-1"}],
        )
        second = self._inbound(
            "фото 2",
            mid=None,
            synthetic_event_key="syn-b",
            attachment_media=[{"provider_object_id": "obj-2"}],
        )
        now = timezone.now()
        turns.ensure_turn_for_inbound(first, now=now)
        result = turns.ensure_turn_for_inbound(second, now=now + timedelta(seconds=1))

        self.assertTrue(result.attached)
        self.assertEqual(IgTurnMessage.objects.count(), 2)

    def test_dedupe_key_prefers_the_native_provider_identity(self):
        row = self._inbound("текст", mid="native-mid")
        self.assertEqual(turns.message_dedupe_key(row), "mid:native-mid")

        media_row = self._inbound(
            "фото",
            mid=None,
            synthetic_event_key="syn-x",
            attachment_media=[{"attachment_id": "obj-9"}],
        )
        self.assertEqual(turns.message_dedupe_key(media_row), "object:obj-9")

        synthetic_row = self._inbound("текст", mid=None, synthetic_event_key="syn-y")
        self.assertEqual(turns.message_dedupe_key(synthetic_row), "synthetic:syn-y")

    def test_raw_messages_are_never_deleted_or_merged(self):
        first = self._inbound("хочу худі", mid="m1")
        second = self._inbound("чорне", mid="m2")
        now = timezone.now()
        turns.ensure_turn_for_inbound(first, now=now)
        turns.ensure_turn_for_inbound(second, now=now + timedelta(seconds=1))

        self.assertEqual(
            InstagramBotMessage.objects.filter(client=self.ig_client).count(), 2
        )

    def test_prospective_overflow_routes_whole_source_to_ordered_successor(self):
        first = self._inbound("x" * 63_999, mid="overflow-first")
        second = self._inbound("друге ціле джерело", mid="overflow-second")
        now = timezone.now()
        original = turns.ensure_turn_for_inbound(first, now=now)

        successor = turns.ensure_turn_for_inbound(
            second, now=now + timedelta(seconds=1)
        )

        self.assertTrue(successor.created)
        self.assertEqual(successor.reason, "overflow_successor")
        self.assertNotEqual(successor.turn.pk, original.turn.pk)
        self.assertEqual(turns.turn_message_ids(original.turn), [first.pk])
        self.assertEqual(turns.turn_message_ids(successor.turn), [second.pk])
        revisions = list(
            IgCustomerTurnRevision.objects.filter(client=self.ig_client)
            .order_by("revision")
        )
        self.assertEqual(len(revisions), 2)
        self.assertEqual(revisions[1].parent_id, revisions[0].pk)
        self.assertEqual(revisions[0].sources.get().message_id, first.pk)
        self.assertEqual(revisions[1].sources.get().message_id, second.pk)

        oversized = self._inbound("y" * 64_001, mid="overflow-single")
        blocked = turns.ensure_turn_for_inbound(
            oversized, now=now + timedelta(seconds=7)
        )
        blocked_revision = IgCustomerTurnRevision.objects.get(
            pk=blocked.revision_id
        )
        self.assertEqual(blocked.reason, "oversize_blocked")
        self.assertTrue(blocked.successor_required)
        self.assertEqual(blocked_revision.state, blocked_revision.State.OVERFLOW)
        self.assertEqual(
            blocked_revision.overflow["source_message_ids"], [oversized.pk]
        )

    @override_settings(IG_CUSTOMER_TURNS=False)
    def test_flag_off_records_no_turns(self):
        self.assertIsNone(turns.ensure_turn_for_inbound(self._inbound("текст", mid="m1")))
        self.assertEqual(IgCustomerTurn.objects.count(), 0)


class TurnDebounceBypassTests(TestCase):
    def setUp(self):
        self.ig_client = IgClient.get_or_create_for_sender("turn-bypass-sender")

    def _inbound(self, text, **kwargs):
        return InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text=text,
            status=InstagramBotMessage.Status.PENDING,
            **kwargs,
        )

    def test_postback_does_not_wait_for_debounce(self):
        row = self._inbound("Забрав ✅", mid="m1", quick_reply_payload="twc:1:parcel:got:42")
        now = timezone.now()
        result = turns.ensure_turn_for_inbound(row, now=now)

        self.assertTrue(result.turn.bypass_debounce)
        self.assertEqual(result.turn.window_deadline, now)
        self.assertTrue(turns.turn_is_due(result.turn, now=now))
        revision = IgCustomerTurnRevision.objects.get(pk=result.revision_id)
        self.assertEqual(revision.quiet_deadline, now)

    def test_opt_out_and_support_never_wait(self):
        for text in ("не пишіть мені більше", "товар не прийшов, це проблема"):
            self.assertTrue(turns.bypasses_debounce(self._inbound(text)), text)

    def test_ordinary_text_waits_for_the_debounce_window(self):
        row = self._inbound("скільки коштує худі", mid="m1")
        now = timezone.now()
        result = turns.ensure_turn_for_inbound(row, now=now)

        self.assertFalse(result.turn.bypass_debounce)
        self.assertFalse(turns.turn_is_due(result.turn, now=now))
        self.assertTrue(
            turns.turn_is_due(result.turn, now=now + turns.TURN_DEBOUNCE)
        )

    def test_button_press_in_the_middle_of_a_burst_stops_the_wait(self):
        first = self._inbound("хочу худі", mid="m1")
        now = timezone.now()
        turns.ensure_turn_for_inbound(first, now=now)
        tap = self._inbound("Забрав", mid="m2", quick_reply_payload="twc:1:parcel:got:7")
        result = turns.ensure_turn_for_inbound(tap, now=now + timedelta(seconds=1))

        self.assertTrue(result.attached)
        result.turn.refresh_from_db()
        self.assertTrue(result.turn.bypass_debounce)
        self.assertTrue(turns.turn_is_due(result.turn, now=now + timedelta(seconds=1)))

    def test_wait_is_bounded_from_above(self):
        self.assertLessEqual(turns.TURN_DEBOUNCE, turns.MAX_TURN_WAIT)
        row = self._inbound("довге питання", mid="m1")
        now = timezone.now()
        result = turns.ensure_turn_for_inbound(row, now=now)
        self.assertLessEqual(result.turn.window_deadline, now + turns.MAX_TURN_WAIT)


class TurnClaimAndMetricTests(TestCase):
    def setUp(self):
        self.ig_client = IgClient.get_or_create_for_sender("turn-claim-sender")
        self.row = InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text="питання",
            mid="claim-1",
            status=InstagramBotMessage.Status.PENDING,
        )

    def test_only_one_worker_can_claim_a_turn(self):
        turns.ensure_turn_for_inbound(self.row)
        turn = IgCustomerTurn.objects.get()

        _first, token_a = turns.claim_turn(turn.pk)
        _second, token_b = turns.claim_turn(turn.pk)

        self.assertTrue(token_a)
        self.assertEqual(token_b, "")
        turn.refresh_from_db()
        self.assertEqual(turn.claim_state, IgCustomerTurn.ClaimState.CLAIMED)

    def test_legacy_completion_retires_shadow_without_touching_newer_head(self):
        from management.services.ig_turn_revisions import (
            claim_revision_preparation,
        )

        turns.ensure_turn_for_inbound(self.row)
        turn = IgCustomerTurn.objects.get()
        revision = IgCustomerTurnRevision.objects.get(turn=turn)
        self.row.status = InstagramBotMessage.Status.DONE
        self.row.send_state = "sent"
        self.row.save(update_fields=["status", "send_state"])

        reason = turns.finalize_turn_for_row(self.row)

        revision.refresh_from_db()
        self.assertEqual(reason, IgCustomerTurn.TerminalReason.REPLIED)
        self.assertEqual(revision.state, revision.State.PROCESSED)
        self.assertEqual(revision.bundle_snapshot, {})
        self.assertEqual(revision.snapshot_digest, "")
        rejected = claim_revision_preparation(
            revision.pk, now=timezone.now() + timedelta(seconds=30)
        )
        self.assertFalse(rejected.token)
        self.assertEqual(rejected.reason, "legacy_turn_terminal")

        other = IgClient.get_or_create_for_sender("turn-newer-head")
        old_source = InstagramBotMessage.objects.create(
            sender_id=other.igsid,
            client=other,
            role=InstagramBotMessage.Role.USER,
            text="старе питання",
            mid="newer-head-old",
            status=InstagramBotMessage.Status.PENDING,
        )
        now = timezone.now()
        old_attachment = turns.ensure_turn_for_inbound(old_source, now=now)
        new_source = InstagramBotMessage.objects.create(
            sender_id=other.igsid,
            client=other,
            role=InstagramBotMessage.Role.USER,
            text="нове питання",
            mid="newer-head-new",
            status=InstagramBotMessage.Status.PENDING,
        )
        new_attachment = turns.ensure_turn_for_inbound(
            new_source, now=now + turns.TURN_DEBOUNCE + timedelta(seconds=1)
        )
        old_source.status = InstagramBotMessage.Status.DONE
        old_source.send_state = "sent"
        old_source.save(update_fields=["status", "send_state"])
        turns.finalize_turn_for_row(old_source)

        newer = IgCustomerTurnRevision.objects.get(pk=new_attachment.revision_id)
        old_revision = IgCustomerTurnRevision.objects.get(
            pk=old_attachment.revision_id
        )
        newer.refresh_from_db()
        self.assertEqual(newer.active_slot, 1)
        self.assertEqual(newer.state, newer.State.COLLECTING)
        self.assertIsNone(old_revision.active_slot)

        unknown_client = IgClient.get_or_create_for_sender("turn-unknown-shadow")
        unknown_source = InstagramBotMessage.objects.create(
            sender_id=unknown_client.igsid,
            client=unknown_client,
            role=InstagramBotMessage.Role.USER,
            text="невизначена доставка",
            mid="unknown-shadow-source",
            status=InstagramBotMessage.Status.PENDING,
        )
        unknown_attachment = turns.ensure_turn_for_inbound(unknown_source)
        unknown_source.status = InstagramBotMessage.Status.FAILED
        unknown_source.send_state = "unknown"
        unknown_source.save(update_fields=["status", "send_state"])
        unknown_reason = turns.finalize_turn_for_row(unknown_source)
        unknown_revision = IgCustomerTurnRevision.objects.get(
            pk=unknown_attachment.revision_id
        )

        self.assertEqual(
            unknown_reason, IgCustomerTurn.TerminalReason.SEND_UNKNOWN
        )
        self.assertEqual(unknown_revision.state, unknown_revision.State.COLLECTING)
        unknown_claim = claim_revision_preparation(
            unknown_revision.pk, now=timezone.now() + timedelta(seconds=30)
        )
        self.assertFalse(unknown_claim.token)
        self.assertEqual(unknown_claim.reason, "legacy_turn_terminal")

    def test_due_turn_ids_respects_the_debounce_window(self):
        now = timezone.now()
        turns.ensure_turn_for_inbound(self.row, now=now)
        self.assertEqual(turns.due_turn_ids(now=now), [])
        self.assertEqual(
            len(turns.due_turn_ids(now=now + turns.TURN_DEBOUNCE)), 1
        )

    def test_hidden_client_turns_are_not_due(self):
        now = timezone.now()
        turns.ensure_turn_for_inbound(self.row, now=now)
        IgClient.objects.filter(pk=self.ig_client.pk).update(hidden_at=now)
        self.assertEqual(turns.due_turn_ids(now=now + turns.TURN_DEBOUNCE), [])

    def test_messages_per_turn_reports_distribution_not_only_average(self):
        now = timezone.now()
        turns.ensure_turn_for_inbound(self.row, now=now)
        second = InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text="ще",
            mid="claim-2",
            status=InstagramBotMessage.Status.PENDING,
        )
        turns.ensure_turn_for_inbound(second, now=now + timedelta(seconds=1))

        metric = turns.messages_per_turn(days=1)
        self.assertEqual(metric["turns"], 1)
        self.assertEqual(metric["messages"], 2)
        self.assertEqual(metric["distribution"], {2: 1})
