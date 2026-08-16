from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.test import TestCase
from django.utils import timezone

from orders import dropshipper_views
from orders.models import DropshipperOrder, DropshipperPayout


class DropshipperPaginationOrderingTests(TestCase):
    def setUp(self):
        self.dropshipper = get_user_model().objects.create_user(
            username="pagination-dropshipper"
        )
        self.tie_at = timezone.now().replace(microsecond=0)

    def assert_tie_boundary(self, queryset, expected_ids):
        self.assertTrue(queryset.totally_ordered)
        paginator = Paginator(queryset, 2)
        actual_ids = [
            obj.pk
            for page_number in paginator.page_range
            for obj in paginator.page(page_number).object_list
        ]
        self.assertEqual(actual_ids, expected_ids)
        self.assertEqual(len(actual_ids), len(set(actual_ids)))

    def test_orders_are_totally_ordered_across_tie_boundary(self):
        orders = [
            DropshipperOrder.objects.create(
                dropshipper=self.dropshipper,
                client_name=f"Client {index}",
                client_phone=f"+380222222{index:03d}",
                client_np_address="Kyiv, branch 1",
            )
            for index in range(3)
        ]
        DropshipperOrder.objects.filter(pk__in=[order.pk for order in orders]).update(
            created_at=self.tie_at
        )
        builder = getattr(dropshipper_views, "_dropshipper_orders_queryset", None)

        self.assertIsNotNone(builder)
        queryset = builder(self.dropshipper)
        self.assertEqual(queryset.query.order_by, ("-created_at", "-id"))
        self.assert_tie_boundary(queryset, [order.pk for order in reversed(orders)])

    def test_payouts_are_totally_ordered_across_tie_boundary(self):
        payouts = [
            DropshipperPayout.objects.create(
                dropshipper=self.dropshipper,
                amount=Decimal("100.00"),
            )
            for _ in range(3)
        ]
        DropshipperPayout.objects.filter(pk__in=[payout.pk for payout in payouts]).update(
            requested_at=self.tie_at
        )
        builder = getattr(dropshipper_views, "_dropshipper_payouts_queryset", None)

        self.assertIsNotNone(builder)
        queryset = builder(self.dropshipper)
        self.assertEqual(queryset.query.order_by, ("-requested_at", "-id"))
        self.assert_tie_boundary(queryset, [payout.pk for payout in reversed(payouts)])
