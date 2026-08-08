"""Task 3: Nova Poshta delivery truth gates for Instagram fulfillment."""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.ig_bot_models import IgClient, IgDeal, IgDealItem
from management.models import IgFollowUpTask
from management.services import bot_orders
from management.services.ig_delivery import apply_directory_selection
from orders.nova_poshta_checkout import NovaPoshtaDeliverySelection


def _paid_deal(*, delivery_status="unverified", with_refs=False):
    client = IgClient.get_or_create_for_sender("fulfillment-truth-client")
    values = {
        "client": client,
        "pay_type": IgDeal.PayType.ONLINE_FULL,
        "status": IgDeal.Status.PAID,
        "payment_status": "paid",
        "paid_at": timezone.now(),
        "np_full_name": "Іван Іванов",
        "np_phone": "0931112233",
        "np_city": "Київ",
        "np_office": "Відділення №1",
        "delivery_status": delivery_status,
    }
    if with_refs:
        values.update(
            np_settlement_ref="settlement-ref-1",
            np_city_ref="city-ref-1",
            np_warehouse_ref="warehouse-ref-1",
            np_warehouse_kind="branch",
            delivery_source="nova_poshta_directory",
        )
    deal = IgDeal.objects.create(**values)
    IgDealItem.objects.create(
        deal=deal,
        title="Футболка Харків",
        qty=1,
        unit_price=Decimal("950.00"),
        line_total=Decimal("950.00"),
    )
    deal.recalc_total()
    return deal


class InstagramFulfillmentTruthTests(TestCase):
    def test_text_only_delivery_never_materializes_and_creates_manager_work(self):
        deal = _paid_deal()

        self.assertFalse(bot_orders.fulfill_if_ready(deal))
        self.assertIsNone(deal.order_id)
        task = IgFollowUpTask.objects.get(
            deal=deal,
            kind=IgFollowUpTask.Kind.MANAGER_TASK,
            reason="delivery_validation_review",
        )
        self.assertIn("Ref", task.last_error)

    def test_validated_refs_materialize_and_survive_on_order(self):
        deal = _paid_deal(delivery_status="validated", with_refs=True)

        self.assertTrue(bot_orders.fulfill_if_ready(deal))
        deal.refresh_from_db()
        order = deal.order
        self.assertIsNotNone(order)
        self.assertEqual(order.np_settlement_ref, "settlement-ref-1")
        self.assertEqual(order.np_city_ref, "city-ref-1")
        self.assertEqual(order.np_warehouse_ref, "warehouse-ref-1")

    def test_validated_status_without_refs_fails_closed(self):
        deal = _paid_deal(delivery_status="validated", with_refs=False)

        self.assertFalse(bot_orders.fulfill_if_ready(deal))
        self.assertIsNone(deal.order_id)
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                deal=deal,
                reason="delivery_validation_review",
            ).exists()
        )

    def test_delivery_review_alert_keeps_pii_and_raw_reason_in_crm_only(self):
        deal = _paid_deal()

        with patch("management.services.bot_orders.notify_manager") as notify:
            self.assertFalse(bot_orders.fulfill_if_ready(deal))

        text = notify.call_args.args[0]
        for private_value in (
            deal.np_full_name,
            deal.np_phone,
            deal.np_city,
            deal.np_office,
            "Ref Нової Пошти",
        ):
            self.assertNotIn(private_value, text)
        self.assertIn(f"Клієнт ID: {deal.client_id}", text)
        self.assertIn(f"Угода ID: {deal.pk}", text)
        self.assertIn(f"?deal={deal.pk}", text)

    def test_order_created_alert_omits_delivery_identity(self):
        deal = _paid_deal(delivery_status="validated", with_refs=True)

        with patch("management.services.bot_orders.notify_manager") as notify:
            self.assertTrue(bot_orders.fulfill_if_ready(deal))

        text = notify.call_args.args[0]
        for private_value in (
            deal.np_full_name,
            deal.np_phone,
            deal.np_city,
            deal.np_office,
        ):
            self.assertNotIn(private_value, text)
        self.assertIn(f"Клієнт ID: {deal.client_id}", text)
        self.assertIn(f"Угода ID: {deal.pk}", text)
        self.assertIn(f"?deal={deal.pk}", text)

    def test_signed_directory_selection_sets_source_qualified_truth(self):
        deal = _paid_deal()
        selection = NovaPoshtaDeliverySelection(
            city="Київ",
            np_office="Відділення №1",
            settlement_ref="settlement-ref-1",
            city_ref="city-ref-1",
            warehouse_ref="warehouse-ref-1",
            warehouse_kind="branch",
            city_token="signed-city-token",
            warehouse_token="signed-warehouse-token",
        )

        apply_directory_selection(deal, selection)
        deal.save()
        deal.refresh_from_db()

        self.assertEqual(deal.delivery_status, IgDeal.DeliveryStatus.VALIDATED)
        self.assertEqual(deal.delivery_source, "nova_poshta_directory")
        self.assertEqual(deal.np_warehouse_ref, "warehouse-ref-1")
