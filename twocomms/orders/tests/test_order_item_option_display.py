from django.test import SimpleTestCase

from orders.models import DropshipperOrderItem, OrderItem


class OrderItemOptionDisplayTests(SimpleTestCase):
    def test_order_item_hides_fit_axis_duplicate(self):
        item = OrderItem(
            fit_option_label="Класична",
            option_labels={"fit": "Класична", "Посадка": "Класична", "color": "Кайот"},
        )
        self.assertEqual(item.generic_option_labels, ["color: Кайот"])

    def test_dropshipper_order_item_hides_fit_axis_duplicate(self):
        item = DropshipperOrderItem(
            fit_option_label="Класична",
            option_labels={"fit": "Класична", "посадка": "Класична", "color": "Кайот"},
        )
        self.assertEqual(item.generic_option_labels, ["color: Кайот"])
