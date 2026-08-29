"""Э2.2 — burst клієнта дає ОДНУ відповідь, а не три.

RED-репродьюсер production-сценарію: клієнт пише «хочу худі», «чорне», «розмір L»
за десять секунд. Перший рядок бачить усю історію і відповідає правильно. Потім
другий і третій викликають ще дві відповіді на той самий контекст.

Три класи шкоди, і найгірший — не вартість:
* повтор питання (виглядає як невнимательність);
* три різні набори варіантів (клієнт не розуміє, який актуальний);
* **конфліктуючі комерційні дії** — перша відповідь створила proposal, друга
  пішла іншим шляхом; ризик кількох pay-link.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgClient,
    IgCustomerTurn,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import instagram_bot as bot
from management.services import ig_customer_turns as turns


class BurstProducesOneReplyTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.ai_enabled = True
        self.settings.save(update_fields=["is_enabled", "ai_enabled"])
        self.ig_client = IgClient.get_or_create_for_sender("burst-sender")

    def _inbound(self, text, *, mid):
        row = InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text=text,
            mid=mid,
            status=InstagramBotMessage.Status.PENDING,
            source="webhook",
        )
        turns.ensure_turn_for_inbound(row)
        return row

    def test_open_turn_is_not_claimed_before_the_window_elapses(self):
        """Клієнт ще друкує — хід не має забиратись у роботу."""
        self._inbound("хочу худі", mid="b1")

        self.assertIsNone(
            bot._claim_next(),
            "хід у межах debounce-вікна не може бути заклеймлений",
        )

    def test_turn_is_claimed_once_the_window_elapsed(self):
        row = self._inbound("хочу худі", mid="b1")
        turn = IgCustomerTurn.objects.get()
        IgCustomerTurn.objects.filter(pk=turn.pk).update(
            window_deadline=timezone.now() - timedelta(seconds=1)
        )

        claimed = bot._claim_next()

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.pk, row.pk)

    def test_burst_of_three_messages_claims_one_row_and_consumes_the_rest(self):
        first = self._inbound("хочу худі", mid="b1")
        second = self._inbound("чорне", mid="b2")
        third = self._inbound("розмір L", mid="b3")
        turn = IgCustomerTurn.objects.get()
        self.assertEqual(turn.message_count, 3, "усі три мусять бути в одному ході")
        IgCustomerTurn.objects.filter(pk=turn.pk).update(
            window_deadline=timezone.now() - timedelta(seconds=1)
        )

        claimed = bot._claim_next()

        self.assertIsNotNone(claimed)
        self.assertEqual(
            claimed.pk, third.pk,
            "відповідати треба на найновіший хід клієнта, а не на перший",
        )
        # Решта рядків поглинуті: вони не породять другої відповіді.
        first.refresh_from_db()
        second.refresh_from_db()
        for absorbed in (first, second):
            self.assertEqual(absorbed.status, InstagramBotMessage.Status.DONE)
            self.assertEqual(absorbed.consumed_by_turn_id, turn.pk)
        # Другий claim не має нічого віддати.
        self.assertIsNone(bot._claim_next())

    def test_absorbed_rows_are_never_deleted(self):
        self._inbound("хочу худі", mid="b1")
        self._inbound("чорне", mid="b2")
        turn = IgCustomerTurn.objects.get()
        IgCustomerTurn.objects.filter(pk=turn.pk).update(
            window_deadline=timezone.now() - timedelta(seconds=1)
        )

        bot._claim_next()

        self.assertEqual(
            InstagramBotMessage.objects.filter(client=self.ig_client).count(), 2,
            "сирі повідомлення лишаються як evidence у CRM",
        )

    def test_postback_is_claimed_immediately_without_waiting(self):
        """Кнопка — завершена дія, її не можна затримувати."""
        row = InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text="Забрав",
            mid="tap-1",
            quick_reply_payload="twc:1:parcel:got:42",
            status=InstagramBotMessage.Status.PENDING,
            source="webhook",
        )
        turns.ensure_turn_for_inbound(row)

        claimed = bot._claim_next()

        self.assertIsNotNone(claimed, "postback не чекає debounce")
        self.assertEqual(claimed.pk, row.pk)

    def test_message_after_the_deadline_is_a_separate_turn_and_gets_its_own_reply(self):
        first = self._inbound("хочу худі", mid="b1")
        first_turn = IgCustomerTurn.objects.get()
        IgCustomerTurn.objects.filter(pk=first_turn.pk).update(
            window_deadline=timezone.now() - timedelta(seconds=1)
        )
        claimed_first = bot._claim_next()
        self.assertEqual(claimed_first.pk, first.pk)
        turns.mark_turn_processed(first_turn.pk)

        later = self._inbound("а ще питання про доставку", mid="b9")
        self.assertEqual(IgCustomerTurn.objects.count(), 2)
        second_turn = IgCustomerTurn.objects.exclude(pk=first_turn.pk).get()
        IgCustomerTurn.objects.filter(pk=second_turn.pk).update(
            window_deadline=timezone.now() - timedelta(seconds=1)
        )

        claimed_second = bot._claim_next()

        self.assertIsNotNone(claimed_second)
        self.assertEqual(claimed_second.pk, later.pk)

    def test_row_without_a_turn_is_still_claimable(self):
        """Деградація: якщо запис ходу не вдався, черга не має стати мертвою."""
        row = InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text="без ходу",
            mid="no-turn",
            status=InstagramBotMessage.Status.PENDING,
            source="webhook",
        )

        claimed = bot._claim_next()

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.pk, row.pk)

    def test_provenance_records_every_source_message_of_the_turn(self):
        first = self._inbound("хочу худі", mid="b1")
        second = self._inbound("чорне", mid="b2")
        turn = IgCustomerTurn.objects.get()

        self.assertEqual(
            turns.turn_message_ids(turn), [first.pk, second.pk],
            "provenance мусить назвати ВСІ вхідні, на які відповідає хід",
        )


class BurstDebounceFlagTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled"])
        self.ig_client = IgClient.get_or_create_for_sender("burst-flag-sender")

    def test_flag_off_restores_one_row_one_turn(self):
        from django.test import override_settings

        row = InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text="хочу худі",
            mid="f1",
            status=InstagramBotMessage.Status.PENDING,
            source="webhook",
        )
        turns.ensure_turn_for_inbound(row)

        with override_settings(IG_TURN_DEBOUNCE=False):
            claimed = bot._claim_next()

        self.assertIsNotNone(
            claimed, "при вимкненому флазі рядок клеймиться одразу, як раніше"
        )
