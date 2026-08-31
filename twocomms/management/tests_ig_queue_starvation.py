"""Э2.8 — свіжий потік не має морити старий рядок голодом.

Порядок «найсвіжіше першим» правильний для інтерактивності і НЕ скасовується.
Ламалось інше: у нього не було верхньої межі очікування, тому безперервний потік
нових повідомлень тримав старий рядок нижче голови черги необмежено довго.
Голодували саме дорогі діалоги — той, хто чекає давно, з більшою ймовірністю вже
обрав товар.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, InstagramBotMessage
from management.services import ig_customer_turns as turns
from management.services import ig_queue_priority
from management.services.instagram_bot import _claim_next


class _QueueFixture(TestCase):
    def _client(self, name, *, stage=IgClient.Stage.NEW):
        ig_client = IgClient.get_or_create_for_sender(name)
        IgClient.objects.filter(pk=ig_client.pk).update(stage=stage)
        ig_client.refresh_from_db()
        return ig_client

    def _pending(self, ig_client, *, age_seconds, text="питання"):
        queued_at = timezone.now() - timedelta(seconds=age_seconds)
        row = InstagramBotMessage.objects.create(
            sender_id=ig_client.igsid,
            client=ig_client,
            role=InstagramBotMessage.Role.USER,
            text=text,
            status=InstagramBotMessage.Status.PENDING,
            mid=f"mid-{ig_client.pk}-{age_seconds}-{text[:6]}",
        )
        InstagramBotMessage.objects.filter(pk=row.pk).update(
            created_at=queued_at, provider_created_at=queued_at
        )
        IgClient.objects.filter(pk=ig_client.pk).update(last_message_at=queued_at)
        row.refresh_from_db()
        return row


class AgeCeilingTests(_QueueFixture):
    def test_ceiling_is_derived_from_the_turn_budget_not_invented(self):
        from management.services.ig_turn_budget import (
            customer_notice_threshold_seconds,
        )

        self.assertEqual(
            ig_queue_priority.age_ceiling_seconds(),
            max(60.0, customer_notice_threshold_seconds()),
        )

    def test_continuous_fresh_stream_does_not_delay_an_old_row_beyond_the_ceiling(self):
        ceiling = ig_queue_priority.age_ceiling_seconds()
        old_client = self._client("starving-old")
        old_row = self._pending(old_client, age_seconds=ceiling + 120, text="де розмір L")
        for index in range(5):
            self._pending(self._client(f"fresh-{index}"), age_seconds=1, text="привіт")

        claimed = _claim_next()

        self.assertIsNotNone(claimed)
        self.assertEqual(
            claimed.pk, old_row.pk,
            "старий рядок за потолком віку не може бути обійдений свіжим",
        )

    def test_control_without_the_ceiling_the_fresh_row_wins(self):
        """Контроль: з вимкненим флагом відтворюється старе поведінка."""
        ceiling = ig_queue_priority.age_ceiling_seconds()
        old_client = self._client("starving-old")
        self._pending(old_client, age_seconds=ceiling + 120, text="де розмір L")
        fresh_row = self._pending(self._client("fresh"), age_seconds=1, text="привіт")

        with self.settings(IG_QUEUE_AGE_CEILING=False):
            claimed = _claim_next()

        self.assertEqual(
            claimed.pk, fresh_row.pk,
            "без потолка свіжий рядок обходить старий — це і був дефект",
        )

    def test_below_the_ceiling_freshness_still_wins(self):
        """Інтерактивність не скасовується: до потолка порядок незмінний."""
        self._pending(self._client("older"), age_seconds=10, text="старіше")
        fresh_row = self._pending(self._client("fresher"), age_seconds=1, text="свіжіше")

        claimed = _claim_next()

        self.assertEqual(claimed.pk, fresh_row.pk)

    def test_equal_age_prefers_the_more_advanced_funnel_stage(self):
        ceiling = ig_queue_priority.age_ceiling_seconds()
        age = ceiling + 60
        # Час фіксується однаково для обох рядків: без цього `queued_at`
        # відрізняється на мікросекунди і рівного віку просто не буває, тобто
        # тест перевіряв би не те, що заявляє.
        queued_at = timezone.now() - timedelta(seconds=age)
        new_row = self._pending(
            self._client("new-stage", stage=IgClient.Stage.NEW),
            age_seconds=age,
            text="перший дотик",
        )
        checkout_row = self._pending(
            self._client("checkout-stage", stage=IgClient.Stage.CHECKOUT),
            age_seconds=age,
            text="як оплатити",
        )
        InstagramBotMessage.objects.filter(
            pk__in=[new_row.pk, checkout_row.pk]
        ).update(created_at=queued_at, provider_created_at=queued_at)

        claimed = _claim_next()

        self.assertEqual(
            claimed.pk, checkout_row.pk,
            "при рівному віці клієнт на checkout дорожчий за клієнта на new",
        )

    def test_hidden_client_is_never_promoted_by_age(self):
        ceiling = ig_queue_priority.age_ceiling_seconds()
        hidden = self._client("hidden-old")
        self._pending(hidden, age_seconds=ceiling + 300, text="давнє")
        IgClient.objects.filter(pk=hidden.pk).update(hidden_at=timezone.now())
        fresh_row = self._pending(self._client("visible-fresh"), age_seconds=1)

        claimed = _claim_next()

        self.assertEqual(
            claimed.pk, fresh_row.pk,
            "приховування сильніше за вік — пріоритет не обходить фільтри",
        )

    def test_client_lease_still_blocks_a_second_concurrent_reply(self):
        ceiling = ig_queue_priority.age_ceiling_seconds()
        leased = self._client("leased-old")
        self._pending(leased, age_seconds=ceiling + 300, text="давнє")
        IgClient.objects.filter(pk=leased.pk).update(
            automation_lease_token="held",
            automation_lease_until=timezone.now() + timedelta(minutes=5),
        )
        fresh_row = self._pending(self._client("free-fresh"), age_seconds=1)

        claimed = _claim_next()

        self.assertEqual(
            claimed.pk, fresh_row.pk,
            "справедливість не має права створити другу відповідь одному діалогу",
        )


class StarvingTurnSelectionTests(_QueueFixture):
    """Той самий потолок застосовується до вибору ходу, не тільки рядка."""

    def _due_turn(self, ig_client, *, age_seconds, text="питання"):
        row = self._pending(ig_client, age_seconds=age_seconds, text=text)
        started = timezone.now() - timedelta(seconds=age_seconds)
        turns.ensure_turn_for_inbound(row, now=started)
        return row

    def test_old_due_turn_is_claimed_before_a_fresh_due_turn(self):
        ceiling = ig_queue_priority.age_ceiling_seconds()
        old_row = self._due_turn(
            self._client("turn-old"), age_seconds=ceiling + 200, text="давній хід"
        )
        self._due_turn(self._client("turn-fresh"), age_seconds=30, text="свіжий хід")

        turn, row_id = turns.due_turn_for_claim()

        self.assertEqual(row_id, old_row.pk)
        self.assertEqual(turn.client_id, old_row.client_id)

    def test_control_without_the_flag_the_fresh_turn_wins(self):
        ceiling = ig_queue_priority.age_ceiling_seconds()
        self._due_turn(
            self._client("turn-old"), age_seconds=ceiling + 200, text="давній хід"
        )
        fresh_row = self._due_turn(
            self._client("turn-fresh"), age_seconds=30, text="свіжий хід"
        )

        with self.settings(IG_QUEUE_AGE_CEILING=False):
            _turn, row_id = turns.due_turn_for_claim()

        self.assertEqual(row_id, fresh_row.pk)


class QueueAgeReportTests(_QueueFixture):
    """Метрика мусить бути знімаемою до правки і після, інакше нічого не доказано."""

    def test_report_counts_starving_rows_against_the_ceiling(self):
        ceiling = ig_queue_priority.age_ceiling_seconds()
        self._pending(self._client("old-a"), age_seconds=ceiling + 100)
        self._pending(self._client("old-b"), age_seconds=ceiling + 50)
        self._pending(self._client("fresh"), age_seconds=2)

        report = ig_queue_priority.queue_age_report()

        self.assertEqual(report["pending"], 3)
        self.assertEqual(report["starving"], 2)
        self.assertGreater(report["max_seconds"], ceiling)
        self.assertEqual(report["age_ceiling_seconds"], round(ceiling, 3))

    def test_empty_queue_reports_zeros_not_an_error(self):
        report = ig_queue_priority.queue_age_report()
        self.assertEqual(report["pending"], 0)
        self.assertEqual(report["starving"], 0)
        self.assertEqual(report["max_seconds"], 0.0)

    def test_hidden_clients_are_out_of_the_queue_metric(self):
        hidden = self._client("hidden")
        self._pending(hidden, age_seconds=500)
        IgClient.objects.filter(pk=hidden.pk).update(hidden_at=timezone.now())

        self.assertEqual(ig_queue_priority.queue_age_report()["pending"], 0)


class StageRankTests(TestCase):
    def test_unknown_stage_ranks_as_new_not_zero(self):
        self.assertEqual(
            ig_queue_priority.stage_rank("some_future_stage"),
            ig_queue_priority.DEFAULT_STAGE_RANK,
        )

    def test_checkout_outranks_new_and_spam_ranks_last(self):
        self.assertGreater(
            ig_queue_priority.stage_rank("checkout"),
            ig_queue_priority.stage_rank("new"),
        )
        self.assertEqual(ig_queue_priority.stage_rank("spam"), 0)
