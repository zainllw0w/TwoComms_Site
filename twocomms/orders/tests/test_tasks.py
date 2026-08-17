from django.test import TestCase

from orders.models import Order, PaymentSideEffectJob
from orders.tasks import send_telegram_notification_task


class TelegramNotificationTaskTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            full_name="Task Buyer",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
        )

    def test_compatibility_entrypoint_persists_without_delivery(self):
        job, created = send_telegram_notification_task.delay(
            self.order.pk,
            "status_update",
            transition_version="v1",
            old_status="В обробці",
            new_status="Готується до відправлення",
        )

        self.assertTrue(created)
        self.assertEqual(job.state, PaymentSideEffectJob.State.PENDING)
        self.assertEqual(job.order_id, self.order.pk)

    def test_compatibility_entrypoint_is_idempotent(self):
        kwargs = {
            "transition_version": "v1",
            "old_status": "В обробці",
            "new_status": "Готується до відправлення",
        }
        first, created = send_telegram_notification_task.apply_async(
            args=(self.order.pk, "status_update"),
            kwargs=kwargs,
        )
        second, created_again = send_telegram_notification_task.apply_async(
            args=(self.order.pk, "status_update"),
            kwargs=kwargs,
        )

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
