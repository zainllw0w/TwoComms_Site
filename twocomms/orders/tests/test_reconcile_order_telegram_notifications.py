from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from orders.models import Order


class ReconcileOrderTelegramNotificationsTests(TestCase):
    def _paid_attempt_order(self, *, number='TWC30072026N01'):
        return Order.objects.create(
            order_number=number,
            full_name='Paid Buyer',
            phone='+380501112233',
            city='Kyiv',
            np_office='Branch 1',
            pay_type='online_full',
            total_sum=Decimal('900.00'),
            discount_amount=Decimal('0.00'),
            payment_status='paid',
            payment_provider='monobank_pay',
            payment_payload={
                'attempt_id': 99,
                'telegram_notifications': {
                    'order_notification_pending': True,
                },
            },
        )

    def test_retries_missing_paid_order_card_once_and_persists_delivery(self):
        order = self._paid_attempt_order()

        with patch(
            'orders.telegram_notifications.TelegramNotifier.send_admin_payment_status_update',
            return_value=True,
        ) as payment_update, patch(
            'orders.telegram_notifications.TelegramNotifier.send_new_order_notification',
            return_value=True,
        ) as order_card:
            call_command(
                'reconcile_order_telegram_notifications',
                max_age_hours=168,
                min_age_seconds=0,
                limit=10,
            )
            call_command(
                'reconcile_order_telegram_notifications',
                max_age_hours=168,
                min_age_seconds=0,
                limit=10,
            )

        payment_update.assert_called_once()
        order_card.assert_called_once()
        order.refresh_from_db()
        notifications = order.payment_payload['telegram_notifications']
        self.assertTrue(notifications['payment_status_update_sent'])
        self.assertTrue(notifications['order_notification_sent'])
        self.assertFalse(notifications['order_notification_pending'])

    def test_failed_delivery_remains_retryable_without_repeating_paid_update(self):
        order = self._paid_attempt_order(number='TWC30072026N02')

        with patch(
            'orders.telegram_notifications.TelegramNotifier.send_admin_payment_status_update',
            return_value=True,
        ) as payment_update, patch(
            'orders.telegram_notifications.TelegramNotifier.send_new_order_notification',
            side_effect=[False, True],
        ) as order_card:
            call_command(
                'reconcile_order_telegram_notifications',
                max_age_hours=168,
                min_age_seconds=0,
                limit=10,
            )
            call_command(
                'reconcile_order_telegram_notifications',
                max_age_hours=168,
                min_age_seconds=0,
                limit=10,
            )

        payment_update.assert_called_once()
        self.assertEqual(order_card.call_count, 2)
        order.refresh_from_db()
        notifications = order.payment_payload['telegram_notifications']
        self.assertEqual(notifications['delivery_attempt_count'], 2)
        self.assertTrue(notifications['order_notification_sent'])

    def test_ignores_paid_orders_not_materialized_from_payment_attempt(self):
        order = self._paid_attempt_order(number='TWC30072026N03')
        order.payment_payload = {}
        order.save(update_fields=['payment_payload'])

        with patch(
            'orders.telegram_notifications.TelegramNotifier.send_new_order_notification',
            return_value=True,
        ) as order_card:
            call_command(
                'reconcile_order_telegram_notifications',
                max_age_hours=168,
                min_age_seconds=0,
                limit=10,
            )

        order_card.assert_not_called()
