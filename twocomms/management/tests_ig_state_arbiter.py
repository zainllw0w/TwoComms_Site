"""W6 — арбитр состояния и воронка с ветвями.

F-STATE-001: шесть машин состояний без арбитра — корень целого класса симптомов,
а не отдельный баг. Клиент #59 одновременно противоречил себе в пяти
представлениях: `stage=paid`, `intent=size`, `objection=size`,
`purchases_count=0`, снапшот `cold / support_complaint / 0%`.

W3 лечила проявления по одному (`_display_band`, `_display_interaction_type`).
Это работало, но каждое следующее представление требовало своей заплатки.
`resolve_client_state` даёт один производный read-model с явным приоритетом
источников, и UI с промптом читают его, а не собирают состояние заново.

F-STATE-003: возврат денег не откатывал состояние — в UI жила псевдо-стадия
`payment_reversed`, которой нет в `IgClient.Stage`, потому что настоящая стадия
оставалась `paid`.

F-SCORE-011: обмен и возврат гасили прогресс-бар до нуля, хотя покупка
состоялась. Ветка обслуживания — не откат воронки.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from management.ig_bot_models import (
    IgClient,
    IgDeal,
    IgPaymentConfirmationReview,
    IgPaymentReviewDecision,
    IgPostSaleCase,
)
from management.models import InstagramBotMessage
from orders.models import Order


class StateArbiterMixin:
    def _client(self, key):
        return IgClient.get_or_create_for_sender(key)

    def _buyer(self, key):
        client = self._client(key)
        review = IgPaymentConfirmationReview.objects.create(
            client=client,
            dedupe_key=f"{key}:review",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        IgPaymentReviewDecision.objects.create(
            review=review,
            client=client,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.FULL_PAYMENT,
            confirmed_amount=Decimal("2100.00"),
            amount_source="manager_input",
            actor=self.manager,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.manager.pk),
        )
        from management.services.bot_payment_truth import (
            recalculate_client_payment_aggregates,
        )

        recalculate_client_payment_aggregates(client)
        client.refresh_from_db()
        return client

    def _case(self, client, *, case_type=None, status=None, key="c"):
        order = Order.objects.create(
            order_number=f"TWC-ARB-{client.pk}-{key}",
            full_name="Buyer",
            phone="380500000000",
            total_sum=Decimal("2100.00"),
            payment_status="paid",
            status="ship",
        )
        return IgPostSaleCase.objects.create(
            client=client,
            order=order,
            source_message=InstagramBotMessage.objects.create(
                client=client, role=InstagramBotMessage.Role.USER, text="хочу обмін"
            ),
            case_type=case_type or IgPostSaleCase.CaseType.EXCHANGE,
            status=status or IgPostSaleCase.Status.IN_TRANSIT,
            requested_size="XL",
        )


class CoherentStateTests(StateArbiterMixin, TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "arbiter-manager", password="x", is_staff=True
        )

    def test_provider_payment_outranks_conversation_analysis(self):
        from management.services.ig_client_state import resolve_client_state

        client = self._client("arbiter-provider")
        IgDeal.objects.create(
            client=client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=__import__("django.utils.timezone", fromlist=["now"]).now(),
            amount=Decimal("990.00"),
        )
        client.stage = IgClient.Stage.QUALIFYING
        client.save(update_fields=["stage", "updated_at"])

        state = resolve_client_state(client)

        self.assertTrue(state.is_buyer)
        self.assertEqual(state.payment_source, "provider")

    def test_manager_confirmation_is_named_as_its_own_source(self):
        from management.services.ig_client_state import resolve_client_state

        state = resolve_client_state(self._buyer("arbiter-manager-source"))

        self.assertTrue(state.is_buyer)
        self.assertEqual(state.payment_source, "manager")

    def test_open_service_case_becomes_a_side_flow_not_a_stage(self):
        """F-SCORE-011: обмен — ветка обслуживания, а не откат воронки."""
        from management.services.ig_client_state import resolve_client_state

        client = self._buyer("arbiter-side-flow")
        self._case(client)

        state = resolve_client_state(client)

        self.assertEqual(state.side_flow, "exchange")
        self.assertTrue(state.off_funnel)
        self.assertTrue(state.is_buyer)

    def test_side_flow_does_not_reset_funnel_progress(self):
        from management.services.ig_client_state import resolve_client_state

        client = self._buyer("arbiter-progress")
        client.stage = IgClient.Stage.ORDER_CREATED
        client.save(update_fields=["stage", "updated_at"])
        self._case(client)

        state = resolve_client_state(client)

        self.assertGreater(state.funnel_progress, 0)

    def test_client_without_evidence_is_not_a_buyer(self):
        from management.services.ig_client_state import resolve_client_state

        state = resolve_client_state(self._client("arbiter-stranger"))

        self.assertFalse(state.is_buyer)
        self.assertEqual(state.payment_source, "none")
        self.assertEqual(state.side_flow, "")

    def test_state_exposes_a_single_human_headline(self):
        """Ровно то, чего требовал критерий приёмки W3 для клиента #59."""
        from management.services.ig_client_state import resolve_client_state

        client = self._buyer("arbiter-headline")
        self._case(client)

        headline = resolve_client_state(client).headline

        self.assertIn("плачено", headline)
        self.assertIn("обмін", headline.lower())
        self.assertIn("XL", headline)

    def test_headline_of_a_plain_buyer_mentions_the_purchase_only(self):
        from management.services.ig_client_state import resolve_client_state

        headline = resolve_client_state(self._buyer("arbiter-plain")).headline

        self.assertIn("плачено", headline)
        self.assertNotIn("обмін", headline.lower())

    def test_terminal_negative_payment_outranks_everything(self):
        from django.utils import timezone

        from management.services.ig_client_state import resolve_client_state

        client = self._client("arbiter-reversed")
        deal = IgDeal.objects.create(
            client=client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("990.00"),
            payment_truth=IgDeal.PaymentTruth.REVERSED,
        )
        IgDeal.objects.filter(pk=deal.pk).update(
            payment_truth_updated_at=timezone.now()
        )
        client.stage = IgClient.Stage.PAID
        client.save(update_fields=["stage", "updated_at"])

        state = resolve_client_state(client)

        self.assertTrue(state.payment_reversed)
        self.assertFalse(state.is_buyer)


class PaymentReversalStageTests(StateArbiterMixin, TestCase):
    """F-STATE-003: возврат денег должен откатывать настоящую стадию."""

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "reversal-manager", password="x", is_staff=True
        )

    def test_reversal_moves_the_stage_back_to_checkout(self):
        from django.utils import timezone

        from management.services.bot_payments import apply_payment_reversal_to_stage

        client = self._client("reversal-stage")
        client.stage = IgClient.Stage.PAID
        client.save(update_fields=["stage", "updated_at"])
        deal = IgDeal.objects.create(
            client=client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("990.00"),
            payment_truth=IgDeal.PaymentTruth.REVERSED,
        )

        apply_payment_reversal_to_stage(deal)

        client.refresh_from_db()
        self.assertEqual(client.stage, IgClient.Stage.CHECKOUT)

    def test_reversal_cancels_the_deal(self):
        from django.utils import timezone

        from management.services.bot_payments import apply_payment_reversal_to_stage

        client = self._client("reversal-deal")
        deal = IgDeal.objects.create(
            client=client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("990.00"),
            payment_truth=IgDeal.PaymentTruth.REFUNDED,
        )

        apply_payment_reversal_to_stage(deal)

        deal.refresh_from_db()
        self.assertEqual(deal.status, IgDeal.Status.CANCELLED)

    def test_confirmed_payment_is_not_rolled_back(self):
        from django.utils import timezone

        from management.services.bot_payments import apply_payment_reversal_to_stage

        client = self._client("reversal-confirmed")
        client.stage = IgClient.Stage.PAID
        client.save(update_fields=["stage", "updated_at"])
        deal = IgDeal.objects.create(
            client=client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("990.00"),
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
        )

        apply_payment_reversal_to_stage(deal)

        client.refresh_from_db()
        self.assertEqual(client.stage, IgClient.Stage.PAID)
        deal.refresh_from_db()
        self.assertEqual(deal.status, IgDeal.Status.PAID)

    def test_partial_refund_keeps_the_purchase(self):
        """Частичный возврат — не отмена покупки."""
        from django.utils import timezone

        from management.services.bot_payments import apply_payment_reversal_to_stage

        client = self._client("reversal-partial")
        client.stage = IgClient.Stage.PAID
        client.save(update_fields=["stage", "updated_at"])
        deal = IgDeal.objects.create(
            client=client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("990.00"),
            payment_truth=IgDeal.PaymentTruth.PARTIALLY_REFUNDED,
        )

        apply_payment_reversal_to_stage(deal)

        client.refresh_from_db()
        self.assertEqual(client.stage, IgClient.Stage.PAID)


class FunnelBranchTests(StateArbiterMixin, TestCase):
    """F-SCORE-011 / F-STATE-005: воронка с ветвями вместо погашенного бара."""

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "funnel-branch-manager", password="x", is_staff=True
        )

    def test_funnel_marks_the_side_flow_instead_of_zeroing_progress(self):
        from management.bot_views import _funnel_progress_for_stage

        client = self._buyer("funnel-side-flow")
        client.stage = IgClient.Stage.ORDER_CREATED
        client.save(update_fields=["stage", "updated_at"])
        self._case(client)

        steps = _funnel_progress_for_stage(client, IgClient.Stage.ORDER_CREATED)

        self.assertTrue(any(step["done"] for step in steps))
        self.assertTrue(any(step.get("side_flow") for step in steps))

    def test_plain_client_funnel_has_no_side_flow_marker(self):
        from management.bot_views import _funnel_progress_for_stage

        client = self._client("funnel-plain")

        steps = _funnel_progress_for_stage(client, IgClient.Stage.NEW)

        self.assertFalse(any(step.get("side_flow") for step in steps))

    def test_done_stage_is_reachable_in_the_funnel(self):
        """`stage=DONE` не записывалась никогда — последний шаг был мёртвым."""
        from management.bot_views import _funnel_progress_for_stage

        client = self._client("funnel-done")

        steps = _funnel_progress_for_stage(client, IgClient.Stage.DONE)

        self.assertTrue(steps[-1]["done"])
        self.assertTrue(steps[-1]["current"])
