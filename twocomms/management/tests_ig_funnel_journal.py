# -*- coding: utf-8 -*-
"""Журнал вибору товару і FSM стадій.

Прямий запит заказника: воронка має пам'ятати не лише «який товар зараз», а й
«як ми до нього дійшли» — з якого товару людина пішла і **чому**. Два переходи
через відсутність вимагають іншої реакції, ніж два переходи за смаком, і бот має
цю різницю бачити.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, IgDeal
from storefront.models import Category, Product, ProductStatus


def _client(igsid="funnel-journal"):
    return IgClient.get_or_create_for_sender(igsid)


class ProductSwitchJournalTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="journal-shirts")
        self.first = Product.objects.create(
            title="Футболка «Reality Bends»", slug="journal-first",
            category=self.category, price=880, status=ProductStatus.PUBLISHED,
        )
        self.second = Product.objects.create(
            title="Футболка класична", slug="journal-second",
            category=self.category, price=788, status=ProductStatus.PUBLISHED,
        )
        self.third = Product.objects.create(
            title="Худі класичне", slug="journal-third",
            category=self.category, price=1912, status=ProductStatus.PUBLISHED,
        )
        self.client_row = _client()

    def test_switch_records_source_target_and_reason(self):
        from management.services.ig_funnel_journal import SwitchReason, record_product_switch

        entry = record_product_switch(
            self.client_row,
            from_product_id=self.first.pk,
            to_product_id=self.second.pk,
            reason=SwitchReason.OUT_OF_STOCK,
            from_title=self.first.title,
            to_title=self.second.title,
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry["from_product_id"], self.first.pk)
        self.assertEqual(entry["to_product_id"], self.second.pk)
        self.assertEqual(entry["reason"], SwitchReason.OUT_OF_STOCK)

    def test_repeated_identical_switch_is_not_duplicated(self):
        """Ретрай webhook не має роздувати журнал."""
        from management.services.ig_funnel_journal import SwitchReason, record_product_switch

        kwargs = dict(
            from_product_id=self.first.pk,
            to_product_id=self.second.pk,
            reason=SwitchReason.CUSTOMER_CHOICE,
        )
        self.assertIsNotNone(record_product_switch(self.client_row, **kwargs))
        self.assertIsNone(record_product_switch(self.client_row, **kwargs))

    def test_switch_to_the_same_product_is_not_an_event(self):
        from management.services.ig_funnel_journal import SwitchReason, record_product_switch

        self.assertIsNone(record_product_switch(
            self.client_row,
            from_product_id=self.first.pk,
            to_product_id=self.first.pk,
            reason=SwitchReason.CUSTOMER_CHOICE,
        ))

    def test_two_stock_failures_in_a_row_ask_for_escalation(self):
        from management.services.ig_funnel_journal import (
            SwitchReason, friction_summary, record_product_switch,
        )

        record_product_switch(
            self.client_row, from_product_id=self.first.pk, to_product_id=self.second.pk,
            reason=SwitchReason.OUT_OF_STOCK,
        )
        record_product_switch(
            self.client_row, from_product_id=self.second.pk, to_product_id=self.third.pk,
            reason=SwitchReason.OUT_OF_STOCK,
        )

        summary = friction_summary(self.client_row)
        self.assertEqual(summary.consecutive_friction, 2)
        self.assertTrue(summary.escalate)

    def test_a_normal_choice_resets_the_friction_streak(self):
        """Клієнт, який спокійно обрав інше, більше не «проблемний»."""
        from management.services.ig_funnel_journal import (
            SwitchReason, friction_summary, record_product_switch,
        )

        record_product_switch(
            self.client_row, from_product_id=self.first.pk, to_product_id=self.second.pk,
            reason=SwitchReason.OUT_OF_STOCK,
        )
        record_product_switch(
            self.client_row, from_product_id=self.second.pk, to_product_id=self.third.pk,
            reason=SwitchReason.CUSTOMER_CHOICE,
        )

        summary = friction_summary(self.client_row)
        self.assertEqual(summary.consecutive_friction, 0)
        self.assertEqual(summary.friction_switches, 1)
        self.assertFalse(summary.escalate)

    def test_prompt_note_demands_apology_and_manager_after_two_failures(self):
        from management.services.ig_funnel_journal import (
            SwitchReason, journal_prompt_note, record_product_switch,
        )

        record_product_switch(
            self.client_row, from_product_id=self.first.pk, to_product_id=self.second.pk,
            reason=SwitchReason.OUT_OF_STOCK, from_title=self.first.title,
        )
        record_product_switch(
            self.client_row, from_product_id=self.second.pk, to_product_id=self.third.pk,
            reason=SwitchReason.OUT_OF_STOCK, from_title=self.second.title,
        )

        note = journal_prompt_note(self.client_row)
        self.assertIn("[ІСТОРІЯ ВИБОРУ ТОВАРУ", note)
        self.assertIn("вибачся", note)
        self.assertIn("[MANAGER]", note)

    def test_empty_journal_takes_no_prompt_budget(self):
        from management.services.ig_funnel_journal import journal_prompt_note

        self.assertEqual(journal_prompt_note(self.client_row), "")

    def test_stock_gap_mark_becomes_the_switch_reason(self):
        """Причина береться з факту, а не з тексту повідомлення."""
        from management.services.ig_funnel_journal import (
            SwitchReason, remember_stock_gap, resolve_switch_reason,
        )

        remember_stock_gap(self.client_row, product_id=self.first.pk, size="M")

        self.assertEqual(
            resolve_switch_reason(self.client_row, self.first.pk),
            SwitchReason.OUT_OF_STOCK,
        )
        # Мітка стосується конкретного товару, а не клієнта взагалі.
        self.assertEqual(resolve_switch_reason(self.client_row, self.third.pk), "")

    def test_unpublished_product_gap_is_a_separate_reason(self):
        from management.services.ig_funnel_journal import (
            SwitchReason, remember_stock_gap, resolve_switch_reason,
        )

        remember_stock_gap(self.client_row, product_id=self.first.pk, published=False)

        self.assertEqual(
            resolve_switch_reason(self.client_row, self.first.pk),
            SwitchReason.NOT_PUBLISHED,
        )

    def test_pin_product_writes_the_journal(self):
        from management.services import bot_orders
        from management.services.ig_funnel_journal import SwitchReason

        self.client_row.current_product = self.first
        self.client_row.save(update_fields=["current_product", "updated_at"])

        bot_orders.pin_product(
            self.client_row, self.second.pk, switch_reason=SwitchReason.CUSTOMER_LINK
        )

        self.client_row.refresh_from_db()
        journal = self.client_row.sales_context["product_journal"]
        self.assertEqual(journal[-1]["to_product_id"], self.second.pk)
        self.assertEqual(journal[-1]["reason"], SwitchReason.CUSTOMER_LINK)

    def test_journal_is_capped(self):
        from management.services.ig_funnel_journal import (
            JOURNAL_LIMIT, SwitchReason, record_product_switch,
        )

        products = [self.first.pk, self.second.pk, self.third.pk]
        for index in range(JOURNAL_LIMIT + 6):
            record_product_switch(
                self.client_row,
                from_product_id=products[index % 3],
                to_product_id=products[(index + 1) % 3],
                reason=SwitchReason.CUSTOMER_CHOICE,
            )
        self.client_row.refresh_from_db()
        self.assertLessEqual(
            len(self.client_row.sales_context["product_journal"]), JOURNAL_LIMIT
        )


class StageFsmTests(TestCase):
    def setUp(self):
        self.client_row = _client("stage-fsm")

    def test_reason_is_mandatory(self):
        from management.services.ig_funnel_fsm import apply_stage

        result = apply_stage(self.client_row, IgClient.Stage.QUALIFYING, reason="")
        self.assertFalse(result.changed)
        self.assertEqual(result.refused, "reason_required")

    def test_forward_transition_is_allowed(self):
        from management.services.ig_funnel_fsm import apply_stage

        result = apply_stage(self.client_row, IgClient.Stage.QUALIFYING, reason="asked_need")
        self.assertTrue(result.changed)
        self.assertEqual(result.direction, "forward")

    def test_regress_requires_explicit_permission(self):
        from management.services.ig_funnel_fsm import apply_stage

        self.client_row.stage = IgClient.Stage.CHECKOUT
        self.client_row.save(update_fields=["stage", "updated_at"])

        refused = apply_stage(self.client_row, IgClient.Stage.QUALIFYING, reason="recalc")
        self.assertFalse(refused.changed)
        self.assertEqual(refused.refused, "regress_not_allowed")

        allowed = apply_stage(
            self.client_row, IgClient.Stage.QUALIFYING,
            reason="customer_changed_mind", allow_regress=True,
        )
        self.assertTrue(allowed.changed)
        self.assertEqual(allowed.direction, "regress")

    def test_payment_stages_require_a_verified_fact(self):
        """Стадію «оплачено» не може поставити модель — лише перевірений факт."""
        from management.services.ig_funnel_fsm import apply_stage

        refused = apply_stage(self.client_row, IgClient.Stage.PAID, reason="model_said_so")
        self.assertFalse(refused.changed)
        self.assertEqual(refused.refused, "fact_required")

        allowed = apply_stage(
            self.client_row, IgClient.Stage.PAID,
            reason="provider_confirmed", fact_verified=True,
        )
        self.assertTrue(allowed.changed)

    def test_unknown_stage_is_refused(self):
        from management.services.ig_funnel_fsm import apply_stage

        result = apply_stage(self.client_row, "teleported", reason="whatever")
        self.assertFalse(result.changed)
        self.assertEqual(result.refused, "unknown_stage")

    def test_transition_is_written_to_the_timeline(self):
        from management.models import IgClientStageEvent
        from management.services.ig_funnel_fsm import apply_stage

        apply_stage(
            self.client_row, IgClient.Stage.PRODUCT_MATCHED,
            reason="product_pinned", actor="bot",
        )

        event = IgClientStageEvent.objects.filter(client=self.client_row).order_by("-id").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.to_stage, IgClient.Stage.PRODUCT_MATCHED)
        self.assertIn("product_pinned", event.reason)
        self.assertIn("bot", event.reason)

    def test_return_from_a_side_stage_is_not_a_regress(self):
        """`cold` — це пауза воронки, а не її кінець."""
        from management.services.ig_funnel_fsm import apply_stage, direction_of

        self.client_row.stage = IgClient.Stage.COLD
        self.client_row.save(update_fields=["stage", "updated_at"])

        self.assertEqual(direction_of(IgClient.Stage.COLD, IgClient.Stage.CHECKOUT), "lateral")
        result = apply_stage(self.client_row, IgClient.Stage.CHECKOUT, reason="client_returned")
        self.assertTrue(result.changed)


class PaymentReversalFunnelTests(TestCase):
    def setUp(self):
        self.client_row = _client("reversal-funnel")

    def _deal(self, truth):
        return IgDeal.objects.create(
            client=self.client_row,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("880.00"),
            payment_truth=truth,
        )

    def test_failed_payment_does_not_cancel_the_deal(self):
        """Невдала спроба оплати — не скасування: людина заплатить із другого разу."""
        from management.services.bot_payments import apply_payment_reversal_to_stage

        deal = self._deal(IgDeal.PaymentTruth.FAILED)
        self.assertFalse(apply_payment_reversal_to_stage(deal))
        deal.refresh_from_db()
        self.assertEqual(deal.status, IgDeal.Status.PAID)

    def test_reversal_regresses_stage_and_cancels_deal(self):
        from management.services.bot_payments import apply_payment_reversal_to_stage

        self.client_row.stage = IgClient.Stage.ORDER_CREATED
        self.client_row.save(update_fields=["stage", "updated_at"])
        deal = self._deal(IgDeal.PaymentTruth.REVERSED)

        self.assertTrue(apply_payment_reversal_to_stage(deal))
        self.client_row.refresh_from_db()
        deal.refresh_from_db()
        self.assertEqual(self.client_row.stage, IgClient.Stage.CHECKOUT)
        self.assertEqual(deal.status, IgDeal.Status.CANCELLED)

    def test_stage_is_not_pushed_below_checkout(self):
        from management.services.bot_payments import apply_payment_reversal_to_stage

        self.client_row.stage = IgClient.Stage.QUALIFYING
        self.client_row.save(update_fields=["stage", "updated_at"])
        deal = self._deal(IgDeal.PaymentTruth.REFUNDED)

        apply_payment_reversal_to_stage(deal)
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.stage, IgClient.Stage.QUALIFYING)


class FunnelStateInPromptTests(TestCase):
    """Воронка має впливати на те, що бот говорить, а не лише на картинку."""

    def setUp(self):
        self.client_row = _client("funnel-prompt")

    def test_reversed_payment_forbids_thanking_for_the_purchase(self):
        from management.services import instagram_bot as bot

        with patch(
            "management.services.ig_client_state.resolve_client_state"
        ) as resolve:
            from management.services.ig_client_state import CoherentState

            resolve.return_value = CoherentState(
                payment_reversed=True, stage="paid", stage_label="Оплачено",
                funnel_progress=75,
            )
            lines = "\n".join(bot._coherent_state_lines(self.client_row))

        self.assertIn("оплату повернено", lines.lower())
        self.assertIn("[MANAGER]", lines)

    def test_open_side_flow_is_described_as_service_not_sale(self):
        from management.services import instagram_bot as bot
        from management.services.ig_client_state import CoherentState

        with patch("management.services.ig_client_state.resolve_client_state") as resolve:
            resolve.return_value = CoherentState(
                is_buyer=True, payment_source="provider", stage="order_created",
                stage_label="Замовлення створено", funnel_progress=88,
                side_flow="exchange", side_flow_label="обмін",
                side_flow_status="В дорозі", requested_size="XL",
            )
            lines = "\n".join(bot._coherent_state_lines(self.client_row))

        self.assertIn("паралельна гілка", lines)
        self.assertIn("XL", lines)
        self.assertIn("не продаж", lines)

    def test_repeat_buyer_is_named_with_the_source_of_truth(self):
        from management.services import instagram_bot as bot
        from management.services.ig_client_state import CoherentState

        with patch("management.services.ig_client_state.resolve_client_state") as resolve:
            resolve.return_value = CoherentState(
                is_buyer=True, payment_source="provider", purchases=2,
                stage="done", stage_label="Завершено", funnel_progress=100,
            )
            lines = "\n".join(bot._coherent_state_lines(self.client_row))

        self.assertIn("уже купував", lines)
        self.assertIn("2", lines)
