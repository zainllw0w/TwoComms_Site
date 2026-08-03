from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from orders.models import Order
from orders.status_management import apply_order_status_update


class StatusManagementTrackingTests(TestCase):
    def _order(self, **kwargs):
        values = {
            "full_name": "Buyer",
            "phone": "+380501112233",
            "city": "Kyiv",
            "np_office": "Branch 1",
            "status": "prep",
            "tracking_number": "20451234123456",
            "shipment_status": "Відправлено - старий статус",
            "tracking_status_code": 9,
            "tracking_checked_at": timezone.now(),
            "tracking_provider_event_at": timezone.now(),
            "tracking_next_check_at": timezone.now(),
            "tracking_failure_count": 3,
            "tracking_terminal_at": timezone.now(),
        }
        values.update(kwargs)
        return Order.objects.create(**values)

    @patch("orders.nova_poshta_service.NovaPoshtaService.update_order_tracking_status")
    def test_replacing_tracking_number_resets_lifecycle_and_syncs_after_commit(self, sync):
        order = self._order()

        with self.captureOnCommitCallbacks(execute=True):
            result = apply_order_status_update(
                order.pk,
                status="ship",
                tracking_number="20451234999999",
                require_tracking_number=True,
            )

        order.refresh_from_db()
        self.assertTrue(result["tracking_changed"])
        self.assertEqual(order.tracking_number, "20451234999999")
        self.assertIsNone(order.tracking_status_code)
        self.assertIsNone(order.tracking_checked_at)
        self.assertIsNone(order.tracking_provider_event_at)
        self.assertIsNone(order.tracking_next_check_at)
        self.assertEqual(order.tracking_failure_count, 0)
        self.assertIsNone(order.tracking_terminal_at)
        self.assertIsNone(order.shipment_status)
        sync.assert_called_once()

    @patch("orders.nova_poshta_service.NovaPoshtaService.update_order_tracking_status", side_effect=RuntimeError("lookup failed"))
    def test_immediate_sync_failure_does_not_rollback_new_tracking_number(self, sync):
        order = self._order()

        with self.captureOnCommitCallbacks(execute=True):
            apply_order_status_update(
                order.pk,
                status="ship",
                tracking_number="20451234999999",
                require_tracking_number=True,
            )

        order.refresh_from_db()
        self.assertEqual(order.tracking_number, "20451234999999")
        sync.assert_called_once()
