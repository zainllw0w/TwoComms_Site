"""Э0.7 — SLO пути клиента: метрика обязана быть фальсифицируемой.

Главный тест здесь — `SloFalsifiabilityTests`. Он строит данные, на которых
метрика ОБЯЗАНА выйти плохой. Если реализация определена небрежно (unknown в
числителе, блокировка политикой посчитана как «ответ не требовался», подавление
всех ответов зачтено как успех), эти тесты падают. Число, которое всегда
выглядит хорошо, — это и есть тот отказ, который здесь ловится.
"""
import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgBotNotification,
    IgCheckoutProposal,
    IgClient,
    IgCustomerTurn,
    IgDeal,
    IgLifecycleEvent,
    IgOrderAttribution,
    IgTurnMessage,
    InstagramBotMessage,
)
from management.services import ig_slo
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from orders.models import Order, PaymentAttempt


class SloFixtureMixin:
    """Фикстуры трёх путей без единой записи в рантайм-сервисы."""

    def make_client(self, suffix, *, stage=IgClient.Stage.QUALIFYING, purchases=0):
        client = IgClient.objects.create(
            igsid=f"slo-igsid-{suffix}",
            username=f"user{suffix}",
            stage=stage,
            purchases_count=purchases,
        )
        return client

    def make_turn(
        self,
        client,
        *,
        started_at,
        claim_state=IgCustomerTurn.ClaimState.PROCESSED,
        terminal_reason="",
        processed_after=timedelta(seconds=5),
        send_state="",
        extra_send_states=(),
    ):
        """Один ход клиента с durable-состоянием отправки на его строках."""
        row = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="секретный текст клиента",
            status=InstagramBotMessage.Status.DONE,
            send_state=send_state,
        )
        turn = IgCustomerTurn.objects.create(
            client=client,
            primary_source_message=row,
            window_started_at=started_at,
            window_deadline=started_at + timedelta(seconds=6),
            claim_state=claim_state,
            terminal_reason=terminal_reason,
            processed_at=(started_at + processed_after) if processed_after else None,
            message_count=1 + len(extra_send_states),
        )
        IgTurnMessage.objects.create(turn=turn, message=row, ordinal=1, role=row.role)
        for index, state in enumerate(extra_send_states, start=2):
            extra = InstagramBotMessage.objects.create(
                sender_id=client.igsid,
                client=client,
                role=InstagramBotMessage.Role.USER,
                text="ещё текст клиента",
                status=InstagramBotMessage.Status.DONE,
                send_state=state,
            )
            IgTurnMessage.objects.create(
                turn=turn, message=extra, ordinal=index, role=extra.role
            )
        return turn

    def make_notification(
        self,
        client,
        *,
        event_type="escalation",
        status=IgBotNotification.Status.SENT,
        created_at=None,
        sent_at=None,
        suffix="",
    ):
        notification = IgBotNotification.objects.create(
            client=client,
            event_type=event_type,
            dedupe_key=f"slo-{event_type}-{client.pk}-{status}-{suffix}",
            status=status,
            sent_at=sent_at,
        )
        if created_at is not None:
            IgBotNotification.objects.filter(pk=notification.pk).update(
                created_at=created_at
            )
            notification.refresh_from_db()
        return notification


class SloFalsifiabilityTests(SloFixtureMixin, TestCase):
    """Данные, на которых метрика ОБЯЗАНА выйти плохой."""

    def setUp(self):
        self.now = timezone.now()
        self.started = self.now - timedelta(hours=1)

    def _sales(self, days=7):
        return ig_slo.slo_report(days=days, now=self.now)["paths"][
            ig_slo.PATH_SALES_REPLY
        ]

    def test_unknown_delivery_is_a_disposition_but_never_a_correct_outcome(self):
        """`unknown` — валидный terminal_disposition и НЕ успех.

        Опровергает реализацию, которая считает «процесс завершился» успехом:
        там оба числа вышли бы 100%, и метрика показала бы благополучие ровно в
        момент неизвестной доставки.
        """
        replied = self.make_client("ok")
        unknown = self.make_client("unk")
        self.make_turn(
            replied,
            started_at=self.started,
            terminal_reason=IgCustomerTurn.TerminalReason.REPLIED,
            send_state="sent",
        )
        self.make_turn(
            unknown,
            started_at=self.started,
            terminal_reason=IgCustomerTurn.TerminalReason.SEND_UNKNOWN,
            send_state="unknown",
        )

        sales = self._sales()
        self.assertEqual(sales["terminal_disposition"]["numerator"], 2)
        self.assertEqual(sales["terminal_disposition"]["denominator"], 2)
        self.assertEqual(sales["terminal_disposition"]["rate"], 1.0)
        self.assertEqual(sales["correct_final_outcome"]["numerator"], 1)
        self.assertEqual(sales["correct_final_outcome"]["denominator"], 2)
        self.assertEqual(sales["correct_final_outcome"]["rate"], 0.5)
        self.assertEqual(sales["guardrails"]["unknown_share"], 0.5)

    def test_suppressing_every_reply_drives_the_metric_to_zero(self):
        """Главный анти-геймингный тест.

        Система, которая никому не ответила, но всё закрыла как «ответ не
        требовался», обязана получить 0%. Если бы `no_send_needed` попал в
        числитель, эта же выборка дала бы 100% — то есть метрику можно было бы
        улучшить, перестав отвечать клиентам. Ровно этого допускать нельзя.
        """
        for index in range(5):
            client = self.make_client(f"silent{index}")
            self.make_turn(
                client,
                started_at=self.started,
                terminal_reason=IgCustomerTurn.TerminalReason.NO_REPLY_NEEDED,
            )

        sales = self._sales()
        self.assertEqual(sales["terminal_disposition"]["rate"], 1.0)
        self.assertEqual(sales["correct_final_outcome"]["numerator"], 0)
        self.assertEqual(sales["correct_final_outcome"]["rate"], 0.0)
        self.assertEqual(sales["guardrails"]["no_send_needed_share"], 1.0)
        # Вспомогательная доля при пустом знаменателе — None, а не 0.0 и не 1.0.
        self.assertEqual(sales["denominator_owed"], 0)
        self.assertIsNone(sales["answer_rate_when_owed"]["rate"])

    def test_policy_block_is_not_counted_as_no_reply_needed(self):
        """Блокировка политикой вынимается из `no_reply_needed` по `send_state`.

        Рантайм пишет обеим ситуациям одну причину `no_reply_needed`. Если
        проекция этого не расщепляет, бот, которому запретили отвечать, выглядит
        как бот, которому отвечать было не нужно.
        """
        blocked = self.make_client("blocked")
        duplicate = self.make_client("dup")
        genuine = self.make_client("genuine")
        self.make_turn(
            blocked,
            started_at=self.started,
            terminal_reason=IgCustomerTurn.TerminalReason.NO_REPLY_NEEDED,
            send_state="cancelled",
        )
        self.make_turn(
            duplicate,
            started_at=self.started,
            terminal_reason=IgCustomerTurn.TerminalReason.NO_REPLY_NEEDED,
            send_state="duplicate",
        )
        self.make_turn(
            genuine,
            started_at=self.started,
            terminal_reason=IgCustomerTurn.TerminalReason.NO_REPLY_NEEDED,
        )

        sales = self._sales()
        self.assertEqual(sales["buckets"][ig_slo.OUTCOME_POLICY_BLOCKED], 1)
        self.assertEqual(sales["buckets"][ig_slo.OUTCOME_SUPPRESSED_DUPLICATE], 1)
        self.assertEqual(sales["buckets"][ig_slo.OUTCOME_NO_SEND_NEEDED], 1)
        self.assertEqual(
            sales["policy_blocks_by_reason"].get("permission_epoch_changed"), 1
        )
        # Причина «настоящего» молчания нигде не записана — размер незнания
        # обязан быть числом, а не догадкой. Но он НЕ подмешивается в разбивку
        # блокировок: разбивка обязана суммироваться в свою корзину.
        self.assertNotIn(
            ig_slo.POLICY_REASON_NOT_RECORDED, sales["policy_blocks_by_reason"]
        )
        self.assertEqual(sales["guardrails"]["policy_reason_not_recorded"], 1)
        self.assertEqual(
            sum(sales["policy_blocks_by_reason"].values()),
            sales["buckets"][ig_slo.OUTCOME_POLICY_BLOCKED],
        )
        self.assertTrue(sales["invariants"]["policy_reasons_sum_equals_policy_bucket"])

    def test_terminal_reason_left_blank_becomes_its_own_bucket(self):
        """Ход, закрытый без типизированной причины, — отдельная корзина.

        Историческая строка до миграции `terminal_reason` не должна ни считаться
        успехом, ни тихо попасть в «ответ не требовался».
        """
        legacy = self.make_client("legacy")
        self.make_turn(legacy, started_at=self.started, terminal_reason="")

        sales = self._sales()
        self.assertEqual(sales["buckets"][ig_slo.OUTCOME_UNCLASSIFIED], 1)
        self.assertEqual(sales["buckets"][ig_slo.OUTCOME_NO_SEND_NEEDED], 0)
        self.assertEqual(sales["correct_final_outcome"]["numerator"], 0)
        self.assertEqual(sales["guardrails"]["unclassified_share"], 1.0)

    def test_fast_reply_followed_by_escalation_is_not_a_success(self):
        """Быстрый неверный ответ — не успех, даже с квитанцией провайдера.

        Латентность здесь минимальная, квитанция есть, а через пять минут по
        этому клиенту открылся человеческий кейс. Реализация, смотрящая только на
        `terminal_reason=replied`, зачла бы это как корректный исход.
        """
        wrong = self.make_client("wrong")
        right = self.make_client("right")
        self.make_turn(
            wrong,
            started_at=self.started,
            terminal_reason=IgCustomerTurn.TerminalReason.REPLIED,
            send_state="sent",
            processed_after=timedelta(seconds=2),
        )
        self.make_turn(
            right,
            started_at=self.started,
            terminal_reason=IgCustomerTurn.TerminalReason.REPLIED,
            send_state="sent",
            processed_after=timedelta(seconds=2),
        )
        self.make_notification(
            wrong,
            event_type="escalation",
            created_at=self.started + timedelta(minutes=5),
            sent_at=self.started + timedelta(minutes=5),
        )

        sales = self._sales()
        self.assertEqual(sales["buckets"][ig_slo.OUTCOME_DELIVERED], 1)
        self.assertEqual(
            sales["buckets"][ig_slo.OUTCOME_DELIVERED_THEN_ESCALATED], 1
        )
        self.assertEqual(sales["correct_final_outcome"]["rate"], 0.5)
        self.assertEqual(
            sales["guardrails"]["delivered_then_escalated_share"], 0.5
        )

    def test_p50_stays_good_while_p95_shows_the_real_pain(self):
        """p50 и p95/p99 нельзя показывать одним числом.

        Двадцать быстрых ходов и два десятиминутных: медиана здесь остаётся
        прекрасной, а хвост показывает тех двух клиентов, которых система
        подвела. Агрегат из одного числа спрятал бы их полностью.
        """
        for index in range(20):
            client = self.make_client(f"fast{index}")
            self.make_turn(
                client,
                started_at=self.started,
                terminal_reason=IgCustomerTurn.TerminalReason.REPLIED,
                send_state="sent",
                processed_after=timedelta(seconds=3),
            )
        for index in range(2):
            slow = self.make_client(f"slow{index}")
            self.make_turn(
                slow,
                started_at=self.started,
                terminal_reason=IgCustomerTurn.TerminalReason.REPLIED,
                send_state="sent",
                processed_after=timedelta(minutes=10),
            )

        latency = self._sales()["latency_to_terminal_seconds"]
        self.assertEqual(latency["count"], 22)
        self.assertEqual(latency["p50"], 3.0)
        self.assertEqual(latency["p95"], 600.0)
        self.assertEqual(latency["p99"], 600.0)
        self.assertEqual(latency["max"], 600.0)
        self.assertNotEqual(latency["p50"], latency["p95"])

    def test_overdue_turn_without_outcome_is_not_terminal(self):
        """Вход без исхода дольше SLA — не терминал, а нарушенный SLO."""
        stuck = self.make_client("stuck")
        self.make_turn(
            stuck,
            started_at=self.now - timedelta(hours=6),
            claim_state=IgCustomerTurn.ClaimState.CLAIMED,
            terminal_reason="",
            processed_after=None,
        )
        fresh = self.make_client("fresh")
        self.make_turn(
            fresh,
            started_at=self.now - timedelta(seconds=5),
            claim_state=IgCustomerTurn.ClaimState.OPEN,
            terminal_reason="",
            processed_after=None,
        )

        sales = self._sales()
        self.assertEqual(sales["buckets"][ig_slo.OUTCOME_OVERDUE], 1)
        self.assertEqual(sales["buckets"][ig_slo.OUTCOME_OPEN_WITHIN_SLA], 1)
        self.assertEqual(sales["terminal_disposition"]["numerator"], 0)
        self.assertEqual(sales["terminal_disposition"]["denominator"], 2)
        self.assertEqual(sales["guardrails"]["overdue_share"], 0.5)


class SloBucketInvariantTests(SloFixtureMixin, TestCase):
    """Инвариант «каждый исход ровно в одной корзине, сумма = знаменателю».

    Это ровно тот тест, который останавливает молча потерянную категорию: любая
    новая ветка исхода, не попавшая в словарь, ломает сумму.
    """

    def setUp(self):
        self.now = timezone.now()
        started = self.now - timedelta(hours=2)
        reasons = IgCustomerTurn.TerminalReason
        recipe = (
            (reasons.REPLIED, "sent"),
            (reasons.SEND_UNKNOWN, "unknown"),
            (reasons.FAILED, "failed"),
            (reasons.ROW_MISSING, ""),
            (reasons.LEASE_EXPIRED, ""),
            (reasons.SUPERSEDED, ""),
            (reasons.NO_REPLY_NEEDED, ""),
            (reasons.NO_REPLY_NEEDED, "cancelled"),
            (reasons.NO_REPLY_NEEDED, "duplicate"),
            ("", ""),
        )
        for index, (reason, send_state) in enumerate(recipe):
            self.make_turn(
                self.make_client(f"inv{index}"),
                started_at=started,
                terminal_reason=reason,
                send_state=send_state,
            )
        # Ход, ещё не получивший исхода, и просроченный ход.
        self.make_turn(
            self.make_client("inv-open"),
            started_at=self.now - timedelta(seconds=3),
            claim_state=IgCustomerTurn.ClaimState.OPEN,
            processed_after=None,
        )
        self.make_turn(
            self.make_client("inv-late"),
            started_at=self.now - timedelta(hours=5),
            claim_state=IgCustomerTurn.ClaimState.CLAIMED,
            processed_after=None,
        )
        self.report = ig_slo.slo_report(days=7, now=self.now)

    def test_every_path_satisfies_every_bucket_invariant(self):
        for path in ig_slo.PATHS:
            path_report = self.report["paths"][path]
            for name, holds in path_report["invariants"].items():
                self.assertTrue(holds, msg=f"{path}: инвариант {name} нарушен")

    def test_buckets_sum_to_the_denominator_and_split_terminal_from_open(self):
        sales = self.report["paths"][ig_slo.PATH_SALES_REPLY]
        self.assertEqual(sum(sales["buckets"].values()), 12)
        self.assertEqual(sales["denominator_total"], 12)
        self.assertEqual(sales["denominator_terminal"], 10)
        open_count = sum(
            sales["buckets"][name] for name in ig_slo.OPEN_OUTCOMES
        )
        self.assertEqual(open_count, 2)
        self.assertEqual(
            sales["denominator_terminal"] + open_count, sales["denominator_total"]
        )

    def test_each_typed_terminal_reason_lands_in_exactly_one_bucket(self):
        sales = self.report["paths"][ig_slo.PATH_SALES_REPLY]
        self.assertEqual(
            {name: count for name, count in sales["buckets"].items() if count},
            {
                ig_slo.OUTCOME_DELIVERED: 1,
                ig_slo.OUTCOME_UNKNOWN: 1,
                ig_slo.OUTCOME_FAILED: 1,
                ig_slo.OUTCOME_EVIDENCE_LOST: 1,
                ig_slo.OUTCOME_ABANDONED: 1,
                ig_slo.OUTCOME_SUPERSEDED: 1,
                ig_slo.OUTCOME_NO_SEND_NEEDED: 1,
                ig_slo.OUTCOME_POLICY_BLOCKED: 1,
                ig_slo.OUTCOME_SUPPRESSED_DUPLICATE: 1,
                ig_slo.OUTCOME_UNCLASSIFIED: 1,
                ig_slo.OUTCOME_OPEN_WITHIN_SLA: 1,
                ig_slo.OUTCOME_OVERDUE: 1,
            },
        )

    def test_all_paths_publish_the_same_outcome_vocabulary(self):
        """Разные наборы корзин по путям = три знаменателя в одном отчёте."""
        for path in ig_slo.PATHS:
            self.assertEqual(
                set(self.report["paths"][path]["buckets"]), set(ig_slo.ALL_OUTCOMES)
            )


class SloHandoffPathTests(SloFixtureMixin, TestCase):
    """Путь передачи человеку: корректный исход = человек реально узнал."""

    def setUp(self):
        self.now = timezone.now()
        self.created = self.now - timedelta(minutes=30)

    def _handoff(self):
        return ig_slo.slo_report(days=7, now=self.now)["paths"][
            ig_slo.PATH_HUMAN_HANDOFF
        ]

    def test_dead_letter_escalation_is_a_failure_not_a_success(self):
        """Клиент ждёт менеджера, который ничего не узнал.

        Ход при этом может быть закрыт безупречно — именно этот разрыв прежние
        покомпонентные метрики не видели.
        """
        reached = self.make_client("reached")
        lost = self.make_client("lost")
        ambiguous = self.make_client("amb")
        self.make_notification(
            reached, created_at=self.created, sent_at=self.created
        )
        self.make_notification(
            lost, status=IgBotNotification.Status.DEAD_LETTER, created_at=self.created
        )
        self.make_notification(
            ambiguous, status=IgBotNotification.Status.UNKNOWN, created_at=self.created
        )

        handoff = self._handoff()
        self.assertEqual(handoff["buckets"][ig_slo.OUTCOME_DELIVERED], 1)
        self.assertEqual(handoff["buckets"][ig_slo.OUTCOME_FAILED], 1)
        self.assertEqual(handoff["buckets"][ig_slo.OUTCOME_UNKNOWN], 1)
        self.assertAlmostEqual(handoff["correct_final_outcome"]["rate"], 1 / 3, places=5)

    def test_infrastructure_alerts_stay_out_of_the_customer_path(self):
        """Алерт про демона не относится к пути клиента и не разбавляет метрику."""
        client = self.make_client("infra")
        self.make_notification(
            client,
            event_type="ig_daemon_stalled",
            status=IgBotNotification.Status.FAILED,
            created_at=self.created,
        )
        self.assertEqual(self._handoff()["denominator_total"], 0)

    def test_client_less_alert_is_excluded(self):
        IgBotNotification.objects.create(
            client=None,
            event_type="escalation",
            dedupe_key="slo-no-client",
            status=IgBotNotification.Status.FAILED,
        )
        self.assertEqual(self._handoff()["denominator_total"], 0)


class SloLifecyclePathTests(SloFixtureMixin, TestCase):
    """Post-purchase путь: вторая по важности метрика плана."""

    def setUp(self):
        self.now = timezone.now()
        self.ig_client = IgClient.get_or_create_for_sender(
            "slo-lifecycle", defaults={"language": "uk"}
        )
        self.deal = IgDeal.objects.create(
            client=self.ig_client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=self.now,
            amount=Decimal("950.00"),
        )
        self.episode = ensure_episode_for_deal(self.deal)
        self.order = Order.objects.create(
            full_name="Іван Іванов",
            phone="+380501112233",
            email="buyer@example.com",
            city="Київ",
            np_office="Відділення №1",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("950.00"),
        )
        self.attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"slo-lifecycle-attempt").hexdigest(),
            full_name=self.order.full_name,
            phone=self.order.phone,
            email=self.order.email,
            city=self.order.city,
            np_office=self.order.np_office,
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.CONVERTED,
            cart_snapshot={"checkout_surface": "instagram_proposal", "items": []},
            gross_amount=self.order.total_sum,
            payable_amount=self.order.total_sum,
            payment_amount=self.order.total_sum,
            order=self.order,
        )
        self.proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            catalog_total=self.order.total_sum,
            quoted_total=self.order.total_sum,
            requested_payment_amount=self.order.total_sum,
            items_digest="a" * 64,
        )
        self.proposal.payment_attempt = self.attempt
        self.proposal.save(update_fields=["payment_attempt", "updated_at"])
        self.attribution = IgOrderAttribution.objects.create(
            order=self.order,
            client=self.ig_client,
            deal=self.deal,
            creation_mode="provider_auto",
            payment_source="provider_attempt",
        )

    def _event(self, suffix, state, *, completed=False):
        event = IgLifecycleEvent.objects.create(
            event_key=f"slo-life-{suffix}",
            kind=IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            client=self.ig_client,
            deal=self.deal,
            proposal=self.proposal,
            order=self.order,
            commercial_episode=self.proposal.commercial_episode,
            attribution=self.attribution,
            locale="uk",
            payload={"attempt_id": self.attempt.pk},
        )
        created_at = self.now - timedelta(hours=2)
        IgLifecycleEvent.objects.filter(pk=event.pk).update(
            state=state,
            created_at=created_at,
            completed_at=(created_at + timedelta(minutes=1)) if completed else None,
        )
        return event

    def _lifecycle(self):
        return ig_slo.slo_report(days=7, now=self.now)["paths"][
            ig_slo.PATH_LIFECYCLE_EVENT
        ]

    def test_waiting_window_and_ambiguous_are_never_delivered(self):
        """Полностью написанная инфраструктура не равна доставленному сообщению.

        `waiting_window` — блокировка политикой платформы, `ambiguous` —
        неизвестная доставка. Обе выглядели бы как «система работает», и именно
        поэтому обе обязаны стоять вне числителя.
        """
        self._event("sent", IgLifecycleEvent.State.SENT, completed=True)
        self._event("window", IgLifecycleEvent.State.WAITING_WINDOW)
        self._event("ambiguous", IgLifecycleEvent.State.AMBIGUOUS)
        self._event("manager", IgLifecycleEvent.State.MANAGER_REVIEW)

        lifecycle = self._lifecycle()
        self.assertEqual(lifecycle["buckets"][ig_slo.OUTCOME_DELIVERED], 1)
        self.assertEqual(lifecycle["buckets"][ig_slo.OUTCOME_POLICY_BLOCKED], 1)
        self.assertEqual(lifecycle["buckets"][ig_slo.OUTCOME_UNKNOWN], 1)
        self.assertEqual(lifecycle["buckets"][ig_slo.OUTCOME_HUMAN_CASE], 1)
        self.assertEqual(lifecycle["correct_final_outcome"]["rate"], 0.25)
        self.assertEqual(
            lifecycle["policy_blocks_by_reason"].get("meta_window_closed"), 1
        )
        self.assertTrue(
            all(lifecycle["invariants"].values()), msg=lifecycle["invariants"]
        )

    def test_pending_event_inside_sla_is_open_not_terminal(self):
        event = self._event("pending", IgLifecycleEvent.State.PENDING)
        IgLifecycleEvent.objects.filter(pk=event.pk).update(
            created_at=self.now - timedelta(minutes=5)
        )
        lifecycle = self._lifecycle()
        self.assertEqual(lifecycle["buckets"][ig_slo.OUTCOME_OPEN_WITHIN_SLA], 1)
        self.assertEqual(lifecycle["denominator_terminal"], 0)

    def test_pending_event_past_sla_is_overdue(self):
        self._event("stale", IgLifecycleEvent.State.PROCESSING)
        IgLifecycleEvent.objects.filter(event_key="slo-life-stale").update(
            created_at=self.now - timedelta(days=3)
        )
        lifecycle = self._lifecycle()
        self.assertEqual(lifecycle["buckets"][ig_slo.OUTCOME_OVERDUE], 1)


class SloQueryBudgetTests(SloFixtureMixin, TestCase):
    """Бюджет запросов ограничен: read-only замер не должен грузить боевую БД."""

    def _build(self, clients):
        now = timezone.now()
        started = now - timedelta(hours=1)
        for index in range(clients):
            client = self.make_client(f"budget{index}")
            self.make_turn(
                client,
                started_at=started,
                terminal_reason=IgCustomerTurn.TerminalReason.REPLIED,
                send_state="sent",
                extra_send_states=("", ""),
            )
            self.make_notification(client, created_at=started, sent_at=started)
        return now

    def test_query_count_does_not_grow_with_the_sample(self):
        """Тот же счёт запросов на 5 и на 40 клиентах.

        Наивная реализация спрашивала бы строки каждого хода отдельно, то есть
        N+1 по сообщениям, и на боевом окне превратила бы отчёт в многоминутную
        нагрузку.
        """
        # Прогрев ленивых импортов (бюджет хода, реестр моделей) вне замера.
        ig_slo.sales_sla_seconds()
        now = self._build(5)
        with self.assertNumQueries(7):
            ig_slo.slo_report(days=7, now=now)

        IgTurnMessage.objects.all().delete()
        IgCustomerTurn.objects.all().delete()
        InstagramBotMessage.objects.all().delete()
        IgBotNotification.objects.all().delete()
        IgClient.objects.all().delete()

        now = self._build(40)
        with self.assertNumQueries(7):
            ig_slo.slo_report(days=7, now=now)


class SloRedactionTests(SloFixtureMixin, TestCase):
    """В выводе нет PII: ни IGSID, ни токена, ни ссылки на медиа, ни текста."""

    def test_report_json_contains_no_customer_identifiers_or_text(self):
        now = timezone.now()
        client = self.make_client("redact")
        client.username = "secret_username"
        client.phone = "+380509998877"
        client.save(update_fields=["username", "phone", "phone_normalized"])
        turn = self.make_turn(
            client,
            started_at=now - timedelta(minutes=10),
            terminal_reason=IgCustomerTurn.TerminalReason.REPLIED,
            send_state="sent",
        )
        InstagramBotMessage.objects.filter(pk=turn.primary_source_message_id).update(
            private_media_use_token="private-media-token",
            delivery_original_text="ответ бота, который нельзя публиковать",
        )
        self.make_notification(client, created_at=now - timedelta(minutes=9))

        dumped = json.dumps(
            ig_slo.slo_report(days=7, now=now), ensure_ascii=False, default=str
        )
        for forbidden in (
            client.igsid,
            "secret_username",
            "+380509998877",
            "private-media-token",
            "секретный текст клиента",
            "ответ бота",
        ):
            self.assertNotIn(forbidden, dumped)


class SloSingleSourceOfNumbersTests(SloFixtureMixin, TestCase):
    """Одинаковые числитель и знаменатель в UI, в отчёте и в решении о выкате."""

    def test_panel_payload_is_the_same_numbers_as_the_report(self):
        now = timezone.now()
        client = self.make_client("panel")
        self.make_turn(
            client,
            started_at=now - timedelta(minutes=5),
            terminal_reason=IgCustomerTurn.TerminalReason.REPLIED,
            send_state="sent",
        )
        report = ig_slo.slo_report(days=7, now=now)
        panel = ig_slo.slo_panel_payload(days=7, now=now)
        for path in ig_slo.PATHS:
            self.assertEqual(report["paths"][path]["buckets"], panel["paths"][path]["buckets"])
            self.assertEqual(
                report["paths"][path]["correct_final_outcome"],
                panel["paths"][path]["correct_final_outcome"],
            )
            self.assertEqual(
                report["paths"][path]["terminal_disposition"],
                panel["paths"][path]["terminal_disposition"],
            )

    def test_gate_reads_the_report_and_never_recomputes_a_rate(self):
        now = timezone.now()
        for index in range(ig_slo.MIN_SAMPLE_PER_PATH):
            self.make_turn(
                self.make_client(f"gate{index}"),
                started_at=now - timedelta(minutes=5),
                terminal_reason=IgCustomerTurn.TerminalReason.SEND_UNKNOWN,
                send_state="unknown",
            )
        report = ig_slo.slo_report(days=7, now=now)
        gate = ig_slo.policy_rollout_gate(report)
        sales = report["paths"][ig_slo.PATH_SALES_REPLY]
        self.assertEqual(sales["correct_final_outcome"]["rate"], 0.0)
        self.assertEqual(gate["decision"], "blocked")
        self.assertIn(
            f"{ig_slo.PATH_SALES_REPLY}: correct_final_outcome 0.0", " ".join(gate["reasons"])
        )


class SloErrorBudgetGateTests(SloFixtureMixin, TestCase):
    """Бюджет ошибок останавливает выкат политики, но не поддержку клиентов."""

    def _report_with(self, reason, send_state="", count=None):
        now = timezone.now()
        count = count or ig_slo.MIN_SAMPLE_PER_PATH
        for index in range(count):
            self.make_turn(
                self.make_client(f"budget-{reason or 'blank'}-{index}"),
                started_at=now - timedelta(minutes=5),
                terminal_reason=reason,
                send_state=send_state,
            )
        return ig_slo.slo_report(days=7, now=now)

    def test_exhausted_budget_never_stops_customer_support(self):
        """Инвариант пункта, а не значение по умолчанию.

        Выключенный бот — это гарантированное молчание вместо вероятной ошибки,
        то есть замена риска на ущерб. Поэтому гейт физически не умеет
        останавливать поддержку.
        """
        gate = ig_slo.policy_rollout_gate(
            self._report_with(IgCustomerTurn.TerminalReason.SEND_UNKNOWN, "unknown")
        )
        self.assertEqual(gate["decision"], "blocked")
        self.assertFalse(gate["allow_new_automatic_policy"])
        self.assertFalse(gate["blocks_customer_support"])

    def test_small_sample_is_not_a_green_light(self):
        """Отсутствие данных — не разрешение на выкат."""
        gate = ig_slo.policy_rollout_gate(self._report_with("", count=2))
        self.assertEqual(gate["decision"], "insufficient_sample")
        self.assertFalse(gate["allow_new_automatic_policy"])
        self.assertEqual(sorted(gate["insufficient_sample_paths"]), sorted(ig_slo.PATHS))

    def test_healthy_sample_allows_rollout(self):
        report = self._report_with(IgCustomerTurn.TerminalReason.REPLIED, "sent")
        # Пути без выборки не должны разрешать выкат сами по себе; здесь они
        # пусты, поэтому решение — недостаточная выборка, а не «разрешено».
        gate = ig_slo.policy_rollout_gate(report)
        self.assertEqual(gate["reasons"], [])
        self.assertEqual(
            sorted(gate["insufficient_sample_paths"]),
            sorted([ig_slo.PATH_HUMAN_HANDOFF, ig_slo.PATH_LIFECYCLE_EVENT]),
        )
        self.assertEqual(gate["decision"], "insufficient_sample")

    def test_regression_in_a_critical_cohort_blocks_rollout(self):
        """Регрессия у клиента с деньгами в полёте останавливает выкат.

        Общая метрика при этом может остаться высокой: критическая когорта —
        маленькая доля выборки, и агрегат её растворяет. Именно поэтому решение
        принимается по когортам, а не по одному числу.
        """
        now = timezone.now()
        started = now - timedelta(minutes=5)
        for index in range(ig_slo.MIN_SAMPLE_PER_PATH):
            self.make_turn(
                self.make_client(f"mass{index}"),
                started_at=started,
                terminal_reason=IgCustomerTurn.TerminalReason.REPLIED,
                send_state="sent",
            )
        for index in range(4):
            self.make_turn(
                self.make_client(
                    f"money{index}", stage=IgClient.Stage.PAYMENT_PENDING
                ),
                started_at=started,
                terminal_reason=IgCustomerTurn.TerminalReason.SEND_UNKNOWN,
                send_state="unknown",
            )
        current = ig_slo.slo_report(days=7, now=now)
        baseline = {
            "paths": {
                ig_slo.PATH_SALES_REPLY: {
                    "cohorts": {
                        ig_slo.COHORT_MONEY_IN_FLIGHT: {
                            "correct_final_outcome_rate": 1.0
                        }
                    }
                }
            }
        }
        gate = ig_slo.policy_rollout_gate(current, baseline=baseline)
        self.assertEqual(gate["decision"], "blocked")
        self.assertTrue(
            any("money_in_flight" in reason for reason in gate["reasons"]),
            msg=gate["reasons"],
        )
        cohorts = current["paths"][ig_slo.PATH_SALES_REPLY]["cohorts"]
        self.assertEqual(cohorts[ig_slo.COHORT_MONEY_IN_FLIGHT]["correct_numerator"], 0)
        self.assertEqual(
            cohorts[ig_slo.COHORT_MONEY_IN_FLIGHT]["denominator_terminal"], 4
        )


class SloCommandTests(SloFixtureMixin, TestCase):
    """Отчёт для оператора: читаемый текст и `--json`."""

    def setUp(self):
        self.now = timezone.now()
        client = self.make_client("cmd", stage=IgClient.Stage.PAYMENT_PENDING)
        self.make_turn(
            client,
            started_at=self.now - timedelta(minutes=5),
            terminal_reason=IgCustomerTurn.TerminalReason.REPLIED,
            send_state="sent",
        )
        self.make_turn(
            self.make_client("cmd-unknown"),
            started_at=self.now - timedelta(minutes=6),
            terminal_reason=IgCustomerTurn.TerminalReason.SEND_UNKNOWN,
            send_state="unknown",
        )

    def _run(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("ig_slo_report", *args, stdout=out)
        return out.getvalue()

    def test_text_report_names_both_definitions_and_separates_percentiles(self):
        output = self._run("--days", "7")
        self.assertIn("terminal_disposition", output)
        self.assertIn("correct_final_outcome", output)
        self.assertIn("p50=", output)
        self.assertIn("p95=", output)
        self.assertIn("p99=", output)
        self.assertIn("Бюджет ошибок", output)
        self.assertIn("поддержка клиентов: НЕ останавливается", output)
        for path in ig_slo.PATHS:
            self.assertIn(path, output)

    def test_json_report_is_machine_readable_and_carries_the_gate(self):
        payload = json.loads(self._run("--days", "7", "--json"))
        self.assertEqual(set(payload["paths"]), set(ig_slo.PATHS))
        self.assertIn("policy_rollout_gate", payload)
        self.assertEqual(
            payload["paths"][ig_slo.PATH_SALES_REPLY]["correct_final_outcome"]["rate"],
            0.5,
        )
        self.assertFalse(payload["policy_rollout_gate"]["blocks_customer_support"])

    def test_text_report_does_not_leak_customer_identifiers(self):
        output = self._run("--days", "7")
        for client in IgClient.objects.all():
            self.assertNotIn(client.igsid, output)
            self.assertNotIn(client.username, output)
        self.assertNotIn("секретный текст клиента", output)
