from decimal import Decimal

from django.test import TestCase, Client

from .models import DtfOrder
from .utils import calculate_pricing


class DtfOrderTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="dtf.twocomms.shop")

    def test_order_number_unique(self):
        o1 = DtfOrder.objects.create(
            name="Test",
            phone="+380501112233",
            city="Kyiv",
            np_branch="1",
        )
        o2 = DtfOrder.objects.create(
            name="Test2",
            phone="+380501112234",
            city="Kyiv",
            np_branch="1",
        )
        self.assertNotEqual(o1.order_number, o2.order_number)

    def test_pricing_calc(self):
        result = calculate_pricing(Decimal("2.5"), 10)
        self.assertEqual(result["meters_total"], Decimal("25.00"))
        self.assertGreater(result["price_total"], 0)

    def test_status_lookup(self):
        order = DtfOrder.objects.create(
            name="Client",
            phone="+380501112233",
            city="Kyiv",
            np_branch="1",
        )
        resp = self.client.post("/status/", {
            "order_number": order.order_number,
            "phone": "+380501112233",
        }, secure=True)
        self.assertContains(resp, order.order_number)
