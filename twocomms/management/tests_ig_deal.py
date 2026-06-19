"""Тести Phase 0 / Task 3 — угода IG-клієнта (IgDeal / IgDealItem).

Угода — це «кошик» діалогу: вибрані позиції, сума, тип оплати (повна/передоплата
200), invoice Monobank, статус оплати, дані НП текстом і посилання на створене
замовлення (замовлення створюється ТІЛЬКИ після оплати — рішення Q2).
"""
from decimal import Decimal

from django.test import TestCase

from management.models import IgClient, IgDeal, IgDealItem


class IgDealModelTests(TestCase):
    def setUp(self):
        self.buyer = IgClient.get_or_create_for_sender("buyer1")

    def test_defaults(self):
        d = IgDeal.objects.create(client=self.buyer)
        self.assertEqual(d.status, IgDeal.Status.DRAFT)
        self.assertEqual(d.pay_type, IgDeal.PayType.ONLINE_FULL)
        self.assertEqual(d.currency, "UAH")
        self.assertEqual(d.payment_status, "unpaid")
        self.assertIsNone(d.order_id)

    def test_item_line_total_autocomputed_on_save(self):
        d = IgDeal.objects.create(client=self.buyer)
        it = IgDealItem.objects.create(
            deal=d, title="Худі Kharkiv", size="M", qty=2, unit_price=Decimal("950.00")
        )
        self.assertEqual(it.line_total, Decimal("1900.00"))

    def test_recalc_total_sums_items(self):
        d = IgDeal.objects.create(client=self.buyer)
        IgDealItem.objects.create(deal=d, title="A", qty=1, unit_price=Decimal("500"))
        IgDealItem.objects.create(deal=d, title="B", qty=2, unit_price=Decimal("300"))
        d.recalc_total()
        self.assertEqual(d.amount, Decimal("1100"))

    def test_payable_amount_full_vs_prepay(self):
        d = IgDeal.objects.create(client=self.buyer, amount=Decimal("1500"))
        self.assertEqual(d.payable_amount(), Decimal("1500"))
        d.pay_type = IgDeal.PayType.PREPAY_200
        self.assertEqual(d.payable_amount(), Decimal("200.00"))

    def test_items_related_name(self):
        d = IgDeal.objects.create(client=self.buyer)
        IgDealItem.objects.create(deal=d, title="A", qty=1, unit_price=Decimal("500"))
        self.assertEqual(d.items.count(), 1)
        self.assertEqual(self.buyer.deals.count(), 1)
