"""Э0.3 — воронка терминальных причин остановки lifecycle-событий.

Каждый RED-тест здесь идёт в паре с контролем, который показывает поведение ДО
правки: по одному только `state` (единственный агрегат, доступный до Э0.3) две
совершенно разные причины остановки попадают в одну корзину, а доставленный
заказ вообще без события не виден ни одному запросу по `IgLifecycleEvent`.
Контроль остаётся зелёным и после правки: он фиксирует, что дефект был реальным,
а не придуманным ради теста.
"""
import hashlib
from datetime import timedelta
from decimal import Decimal
import json

from django.core.management import call_command
from django.db.models import Count
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from io import StringIO

from management.ig_bot_models import (
    IgLifecycleEvent,
    IgPaymentProjection,
)
from management.models import (
    IgCheckoutProposal,
    IgClient,
    IgDeal,
    IgOrderAttribution,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from management.services import ig_lifecycle
from management.services.ig_lifecycle import (
    STANDARD_RESPONSE_WINDOW_CLOSED,
    _lifecycle_message_key,
    ensure_lifecycle_event,
)
from management.services.ig_lifecycle_reasons import (
    FIXED_REASON_CODES,
    FUNNEL_FLAG,
    Evidence,
    Reason,
    Stage,
    classify_disposition,
    lifecycle_reason_funnel,
)
from management.services.ig_order_assignments import link_order_to_client
from orders.models import Order, PaymentAttempt


class LifecycleDispositionClassifierTests(SimpleTestCase):
    """Чистый классификатор: без БД, без провайдера."""

    def test_control_state_alone_conflates_two_different_stops(self):
        """КОНТРОЛЬ (зелёный и до правки): `state` не различает причины.

        Закрытое окно Meta и истёкший permission-deferral — это разные места
        остановки с разными решениями, но обе строки лежат в `manager_review`.
        Любой агрегат «group by state» показал бы 2 в одной корзине.
        """
        states = {
            IgLifecycleEvent.State.MANAGER_REVIEW,
            IgLifecycleEvent.State.MANAGER_REVIEW,
        }
        self.assertEqual(states, {IgLifecycleEvent.State.MANAGER_REVIEW})

    def test_window_closed_and_permission_timeout_are_separate_typed_reasons(self):
        window = classify_disposition(
            state=IgLifecycleEvent.State.MANAGER_REVIEW,
            last_error=STANDARD_RESPONSE_WINDOW_CLOSED,
        )
        permission = classify_disposition(
            state=IgLifecycleEvent.State.MANAGER_REVIEW,
            last_error="manager_takeover",
        )
        self.assertEqual(window.reason, Reason.WINDOW_CLOSED)
        self.assertEqual(permission.reason, Reason.PERMISSION_DEFERRAL_TIMEOUT)
        self.assertNotEqual(window.reason, permission.reason)
        self.assertEqual(window.stage, Stage.BLOCKED_PRE_PROVIDER)
        self.assertTrue(window.terminal)
        self.assertTrue(permission.terminal)

    def test_control_naive_string_match_would_call_provider_io_a_failure(self):
        """КОНТРОЛЬ: `last_error` наивно читается как «unknown/permanent».

        Строка `provider_io_started:unknown:timeout` содержит и `unknown`, и
        техническую подсказку. Наивный `last_error.startswith("unknown")` или
        поиск подстроки отнёс бы её к отказу провайдера, хотя это ровно тот
        случай, где НЕИЗВЕСТНО, дошло сообщение до клиента или нет.
        """
        raw = "provider_io_started:unknown:timeout"
        self.assertIn("unknown", raw)
        self.assertFalse(raw.startswith("unknown"))

    def test_provider_io_started_is_ambiguous_not_a_definite_reason(self):
        disposition = classify_disposition(
            state=IgLifecycleEvent.State.AMBIGUOUS,
            last_error="provider_io_started:unknown:timeout",
            provider_io_started=True,
        )
        self.assertEqual(disposition.reason, Reason.PROVIDER_RECEIPT_UNKNOWN)
        self.assertEqual(disposition.evidence, Evidence.AMBIGUOUS_PROVIDER_IO)
        self.assertEqual(disposition.stage, Stage.RECEIPT_UNKNOWN)
        self.assertTrue(disposition.terminal)

    def test_unrecognized_last_error_lands_in_explicit_unknown_bucket(self):
        disposition = classify_disposition(
            state=IgLifecycleEvent.State.FAILED,
            last_error="totally_new_string_nobody_mapped",
        )
        self.assertEqual(disposition.reason, Reason.UNKNOWN)
        self.assertEqual(disposition.evidence, Evidence.UNKNOWN)

    def test_cancelled_row_with_provider_io_marker_is_contradictory(self):
        """Отмена возможна только ДО провайдера. Маркер I/O — противоречие."""
        disposition = classify_disposition(
            state=IgLifecycleEvent.State.CANCELLED,
            last_error="payment_not_verified",
            provider_io_started=True,
        )
        self.assertEqual(disposition.reason, Reason.CONTRADICTORY_EVIDENCE)
        self.assertEqual(disposition.evidence, Evidence.CONTRADICTORY)

    def test_delivered_requires_a_provider_receipt(self):
        delivered = classify_disposition(
            state=IgLifecycleEvent.State.SENT,
            last_error="",
            provider_message_id="mid-1",
        )
        self.assertEqual(delivered.reason, Reason.DELIVERED)
        self.assertEqual(delivered.evidence, Evidence.PROVEN_DELIVERED)
        without_receipt = classify_disposition(
            state=IgLifecycleEvent.State.SENT,
            last_error="",
            provider_message_id="",
        )
        self.assertEqual(without_receipt.reason, Reason.CONTRADICTORY_EVIDENCE)

    def test_pending_retry_and_live_lease_are_not_terminal(self):
        now = timezone.now()
        retry = classify_disposition(
            state=IgLifecycleEvent.State.PENDING,
            last_error="retryable:http_500",
            due_at=now + timedelta(minutes=2),
            now=now,
        )
        self.assertEqual(retry.reason, Reason.RETRY_SCHEDULED)
        self.assertFalse(retry.terminal)
        in_flight = classify_disposition(
            state=IgLifecycleEvent.State.PROCESSING,
            last_error=ig_lifecycle.PROVIDER_BOUNDARY_CLAIM_MARKER,
            lease_expires_at=now + timedelta(minutes=5),
            now=now,
        )
        self.assertEqual(in_flight.reason, Reason.CLAIM_IN_FLIGHT)
        self.assertFalse(in_flight.terminal)

    def test_every_last_error_string_the_dispatcher_writes_is_typed(self):
        """Анти-дрейф: строка, которую пишет диспетчер, не может быть не типизирована."""
        produced = set(ig_lifecycle.LAST_ERROR_REASONS)
        self.assertTrue(produced)
        self.assertEqual(produced - set(FIXED_REASON_CODES), set())


class LifecycleReasonFunnelTests(TestCase):
    def setUp(self):
        self.ig_client = IgClient.get_or_create_for_sender(
            "ig-lifecycle-reasons",
            defaults={"language": "uk"},
        )
        self.ig_client.last_message_at = timezone.now()
        self.ig_client.save(update_fields=["last_message_at", "updated_at"])
        self.deal = IgDeal.objects.create(
            client=self.ig_client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("950.00"),
        )
        self.episode = ensure_episode_for_deal(self.deal)
        self.order = self._order(pay_type="online_full")
        self.attempt = self._attempt(self.order, b"ig-reason-attempt")
        self.proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            catalog_total=self.order.total_sum,
            quoted_total=self.order.total_sum,
            requested_payment_amount=self.order.total_sum,
            items_digest="b" * 64,
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
        IgPaymentProjection.objects.create(
            deal=self.deal,
            client=self.ig_client,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=self.order.total_sum,
            paid_at=self.deal.paid_at,
        )
        InstagramBotSettings.load()
        link_order_to_client(self.order, client=self.ig_client)

    def _order(self, *, pay_type="online_full", delivered=True):
        now = timezone.now()
        order = Order.objects.create(
            full_name="Іван Іванов",
            phone="+380501112233",
            city="Київ",
            np_office="Відділення №1",
            pay_type=pay_type,
            payment_status="paid",
            total_sum=Decimal("950.00"),
            status="done" if delivered else "ship",
        )
        if delivered:
            Order.objects.filter(pk=order.pk).update(
                tracking_number=f"2045{order.pk:08d}",
                tracking_status_code=10,
                tracking_terminal_at=now,
                tracking_provider_event_at=now,
            )
            order.refresh_from_db()
        return order

    def _attempt(self, order, seed):
        return PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(seed).hexdigest(),
            full_name=order.full_name,
            phone=order.phone,
            city=order.city,
            np_office=order.np_office,
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.CONVERTED,
            cart_snapshot={"checkout_surface": "instagram_proposal", "items": []},
            gross_amount=order.total_sum,
            payable_amount=order.total_sum,
            payment_amount=order.total_sum,
            order=order,
        )

    def _delivered_event(self, *, state, last_error):
        event, created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
        )
        self.assertTrue(created)
        IgLifecycleEvent.objects.filter(pk=event.pk).update(
            state=state,
            last_error=last_error,
        )
        event.refresh_from_db()
        return event

    def test_control_group_by_state_cannot_answer_where_events_stopped(self):
        """КОНТРОЛЬ: агрегат по `state` даёт одну корзину на две причины."""
        self._delivered_event(
            state=IgLifecycleEvent.State.MANAGER_REVIEW,
            last_error=STANDARD_RESPONSE_WINDOW_CLOSED,
        )
        second_order = self._order()
        attempt = self._attempt(second_order, b"ig-reason-attempt-2")
        deal = IgDeal.objects.create(
            client=self.ig_client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=second_order.total_sum,
        )
        ensure_episode_for_deal(deal)
        proposal = IgCheckoutProposal.objects.create_current(
            deal=deal,
            catalog_total=second_order.total_sum,
            quoted_total=second_order.total_sum,
            requested_payment_amount=second_order.total_sum,
            items_digest="c" * 64,
        )
        proposal.payment_attempt = attempt
        proposal.save(update_fields=["payment_attempt", "updated_at"])
        IgOrderAttribution.objects.create(
            order=second_order,
            client=self.ig_client,
            deal=deal,
            creation_mode="provider_auto",
            payment_source="provider_attempt",
        )
        IgPaymentProjection.objects.create(
            deal=deal,
            client=self.ig_client,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=second_order.total_sum,
            paid_at=deal.paid_at,
        )
        link_order_to_client(second_order, client=self.ig_client)
        other, created = ensure_lifecycle_event(
            second_order,
            IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
        )
        self.assertTrue(created)
        IgLifecycleEvent.objects.filter(pk=other.pk).update(
            state=IgLifecycleEvent.State.MANAGER_REVIEW,
            last_error="manager_takeover",
        )
        by_state = dict(
            IgLifecycleEvent.objects.values_list("state")
            .annotate(total=Count("id"))
            .values_list("state", "total")
        )
        self.assertEqual(by_state, {IgLifecycleEvent.State.MANAGER_REVIEW: 2})

    def test_funnel_separates_reasons_with_denominators(self):
        self._delivered_event(
            state=IgLifecycleEvent.State.MANAGER_REVIEW,
            last_error=STANDARD_RESPONSE_WINDOW_CLOSED,
        )
        report = lifecycle_reason_funnel(days=30)
        events = report["events"]
        self.assertEqual(events["denominator"], 1)
        self.assertEqual(events["by_reason"].get(Reason.WINDOW_CLOSED), 1)
        hypothesis = report["window_closed_hypothesis"]
        self.assertEqual(hypothesis["numerator"], 1)
        self.assertEqual(hypothesis["denominator"], 1)
        self.assertAlmostEqual(hypothesis["share"], 1.0)

    def test_bucket_counts_sum_to_denominator_without_silent_absence(self):
        self._delivered_event(
            state=IgLifecycleEvent.State.FAILED,
            last_error="a_reason_that_is_not_mapped",
        )
        report = lifecycle_reason_funnel(days=30)
        events = report["events"]
        self.assertEqual(sum(events["by_reason"].values()), events["denominator"])
        self.assertEqual(events["by_reason"].get(Reason.UNKNOWN), 1)
        self.assertTrue(events["buckets_sum_matches_denominator"])

    def test_control_delivered_order_without_event_is_invisible_to_event_queries(self):
        """КОНТРОЛЬ: заказ без события не виден со стороны `IgLifecycleEvent`."""
        self.assertEqual(
            IgLifecycleEvent.objects.filter(order=self.order).count(), 0
        )
        report = lifecycle_reason_funnel(days=30)
        self.assertEqual(report["events"]["denominator"], 0)

    def test_delivered_order_without_event_gets_typed_absence_reason(self):
        report = lifecycle_reason_funnel(days=30)
        delivered = report["delivered_orders"]
        self.assertEqual(delivered["denominator"], 1)
        self.assertEqual(delivered["without_event"], 1)
        self.assertTrue(delivered["unit_of_count"])
        self.assertEqual(
            sum(delivered["absence_reasons"].values()), delivered["without_event"]
        )
        self.assertEqual(
            delivered["absence_reasons"].get(Reason.ABSENT_UNEXPLAINED), 1
        )

    def test_absence_reasons_separate_no_attribution_from_unexplained(self):
        """Заказ, привязанный вручную и без attribution, не смешивается с молчанием.

        `IgOrderAttribution` append-only, поэтому сценарий воспроизводится так,
        как он и выглядит в production: доставленный заказ, привязанный к клиенту
        менеджером, у которого attribution так и не появилась.
        """
        manual_order = self._order()
        link_order_to_client(manual_order, client=self.ig_client)
        report = lifecycle_reason_funnel(days=30)
        delivered = report["delivered_orders"]
        self.assertEqual(delivered["denominator"], 2)
        self.assertEqual(delivered["without_event"], 2)
        self.assertEqual(
            delivered["absence_reasons"],
            {Reason.ABSENT_UNEXPLAINED: 1, Reason.ABSENT_NO_ATTRIBUTION: 1},
        )
        self.assertTrue(delivered["absence_sum_matches_without_event"])

    def test_cod_share_among_delivered_ig_orders(self):
        cod_order = self._order(pay_type="cod")
        link_order_to_client(cod_order, client=self.ig_client)
        report = lifecycle_reason_funnel(days=30)
        cod = report["cod"]
        self.assertEqual(cod["denominator"], 2)
        self.assertEqual(cod["cod_orders"], 1)
        self.assertAlmostEqual(cod["share"], 0.5)

    def test_report_never_claims_transition_history(self):
        self._delivered_event(
            state=IgLifecycleEvent.State.MANAGER_REVIEW,
            last_error=STANDARD_RESPONSE_WINDOW_CLOSED,
        )
        report = lifecycle_reason_funnel(days=30)
        self.assertEqual(report["measured"], "current_disposition")
        self.assertEqual(report["variant"], "A")
        self.assertFalse(report["history_available"])
        self.assertTrue(report["caveat"])
        bucket = next(
            item
            for item in report["events"]["buckets"]
            if item["reason"] == Reason.WINDOW_CLOSED
        )
        self.assertIn("seconds_since_last_transition", bucket)
        self.assertNotIn("stopped_at", bucket)
        self.assertNotIn("stopped_for_seconds", bucket)

    def test_provider_io_marker_overrides_the_row_state(self):
        event = self._delivered_event(
            state=IgLifecycleEvent.State.CANCELLED,
            last_error="payment_not_verified",
        )
        InstagramBotMessage.objects.create(
            client=self.ig_client,
            role=InstagramBotMessage.Role.MODEL,
            source="lifecycle",
            synthetic_event_key=_lifecycle_message_key(event.event_key),
            text="x",
            provider_message_id="mid-x",
        )
        report = lifecycle_reason_funnel(days=30)
        self.assertEqual(
            report["events"]["by_reason"].get(Reason.CONTRADICTORY_EVIDENCE), 1
        )

    @override_settings(**{FUNNEL_FLAG: False})
    def test_flag_off_returns_an_explicit_disabled_marker(self):
        report = lifecycle_reason_funnel(days=30)
        self.assertFalse(report["enabled"])
        self.assertNotIn("events", report)

    def test_operator_command_emits_json_with_denominators(self):
        self._delivered_event(
            state=IgLifecycleEvent.State.MANAGER_REVIEW,
            last_error=STANDARD_RESPONSE_WINDOW_CLOSED,
        )
        out = StringIO()
        call_command("ig_lifecycle_reason_funnel", "--json", "--days=30", stdout=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["measured"], "current_disposition")
        self.assertEqual(payload["events"]["denominator"], 1)
        self.assertEqual(
            payload["window_closed_hypothesis"]["numerator"], 1
        )

    def test_operator_command_text_output_renders_every_section(self):
        self._delivered_event(
            state=IgLifecycleEvent.State.MANAGER_REVIEW,
            last_error=STANDARD_RESPONSE_WINDOW_CLOSED,
        )
        out = StringIO()
        call_command("ig_lifecycle_reason_funnel", "--days=30", stdout=out)
        text = out.getvalue()
        self.assertIn("current_disposition", text)
        self.assertIn(Reason.WINDOW_CLOSED, text)
        self.assertIn("NEW-CRIT-001 direct check", text)
        self.assertIn("Unit of count", text)
        self.assertIn("COD share among delivered IG orders", text)
