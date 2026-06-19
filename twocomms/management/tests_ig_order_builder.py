"""Тести Phase 6 / Task 18 — створення замовлення з угоди IG-бота.

Замовлення створюється ТІЛЬКИ після оплати (Q2), source=manual, sale_source=
Instagram. Ідемпотентно (один заказ на угоду). Дані НП — текстом (Q3=a).
"""
from decimal import Decimal

from django.test import TestCase

from management.models import IgClient, IgDeal, IgDealItem
from orders.models import Order
from orders.services.order_builder import create_order_from_deal


class CreateOrderFromDealTests(TestCase):
    def setUp(self):
        self.c = IgClient.get_or_create_for_sender("ob1")
        self.deal = IgDeal.objects.create(
            client=self.c, pay_type=IgDeal.PayType.ONLINE_FULL,
            np_full_name="Іван Іванов", np_phone="0931112233",
            np_city="Київ", np_office="Відділення 1", invoice_id="inv_ob",
        )
        IgDealItem.objects.create(deal=self.deal, title="Худі Kharkiv", size="M", qty=1, unit_price=Decimal("950"))
        self.deal.recalc_total()
        self.deal.payment_status = "paid"
        self.deal.status = IgDeal.Status.PAID
        self.deal.save()

    def test_creates_order_with_items(self):
        order = create_order_from_deal(self.deal)
        self.assertIsNotNone(order.id)
        self.assertEqual(order.sale_source, "Instagram")
        self.assertEqual(order.source, "manual")
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.full_name, "Іван Іванов")
        self.assertEqual(order.phone, "0931112233")
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total_sum, Decimal("950"))
        self.assertEqual(order.payment_invoice_id, "inv_ob")
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.order_id, order.id)
        self.assertEqual(self.deal.status, IgDeal.Status.ORDER_CREATED)
        self.c.refresh_from_db()
        self.assertEqual(self.c.purchases_count, 1)
        self.assertEqual(self.c.stage, IgClient.Stage.ORDER_CREATED)

    def test_prepay_payment_status_and_full_total(self):
        self.deal.pay_type = IgDeal.PayType.PREPAY_200
        self.deal.save()
        order = create_order_from_deal(self.deal)
        self.assertEqual(order.payment_status, "prepaid")
        self.assertEqual(order.total_sum, Decimal("950"))

    def test_idempotent_one_order(self):
        o1 = create_order_from_deal(self.deal)
        o2 = create_order_from_deal(self.deal)
        self.assertEqual(o1.id, o2.id)
        self.assertEqual(Order.objects.count(), 1)
