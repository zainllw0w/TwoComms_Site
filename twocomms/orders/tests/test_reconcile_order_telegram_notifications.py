from decimal import Decimal
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

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

    def test_failed_payment_alert_retries_without_repeating_order_card(self):
        order = self._paid_attempt_order(number='TWC30072026N09')

        with patch(
            'orders.telegram_notifications.TelegramNotifier.send_admin_payment_status_update',
            side_effect=[False, True],
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

        self.assertEqual(payment_update.call_count, 2)
        order_card.assert_called_once()
        order.refresh_from_db()
        notifications = order.payment_payload['telegram_notifications']
        self.assertTrue(notifications['payment_status_update_sent'])
        self.assertTrue(notifications['order_notification_sent'])
        self.assertEqual(notifications['delivery_attempt_count'], 2)

    def test_ambiguous_delivery_is_not_retried_automatically(self):
        order = self._paid_attempt_order(number='TWC30072026N04')
        first_output = StringIO()

        with patch(
            'orders.telegram_notifications.TelegramNotifier.send_admin_payment_status_update',
            return_value=True,
        ) as payment_update, patch(
            'orders.telegram_notifications.TelegramNotifier.send_new_order_notification',
            return_value='ambiguous',
        ) as order_card:
            call_command(
                'reconcile_order_telegram_notifications',
                max_age_hours=168,
                min_age_seconds=0,
                limit=10,
                stdout=first_output,
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
        self.assertTrue(notifications['order_notification_ambiguous'])
        self.assertFalse(notifications['order_notification_pending'])
        self.assertFalse(notifications.get('order_notification_sent', False))
        self.assertEqual(
            order.payment_payload['post_payment_channels']['telegram']['state'],
            'ambiguous',
        )
        self.assertIn('ambiguous=1', first_output.getvalue())

    def test_expired_send_phase_lease_becomes_ambiguous_without_resend(self):
        order = self._paid_attempt_order(number='TWC30072026N05')
        payload = dict(order.payment_payload)
        notifications = dict(payload['telegram_notifications'])
        notifications.update({
            'delivery_attempt_count': 1,
            'delivery_retry_lease_until': (timezone.now() - timedelta(minutes=1)).isoformat(),
            'payment_status_update_sent': True,
            'order_notification_send_started_at': (timezone.now() - timedelta(minutes=6)).isoformat(),
        })
        payload['telegram_notifications'] = notifications
        order.payment_payload = payload
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
            call_command(
                'reconcile_order_telegram_notifications',
                max_age_hours=168,
                min_age_seconds=0,
                limit=10,
            )

        order_card.assert_not_called()
        order.refresh_from_db()
        notifications = order.payment_payload['telegram_notifications']
        self.assertTrue(notifications['order_notification_ambiguous'])
        self.assertFalse(notifications['order_notification_pending'])
        self.assertEqual(
            order.payment_payload['post_payment_channels']['telegram']['state'],
            'ambiguous',
        )

    def test_payment_alert_ambiguity_does_not_block_or_duplicate_order_card(self):
        order = self._paid_attempt_order(number='TWC30072026N06')

        with patch(
            'orders.telegram_notifications.TelegramNotifier.send_admin_payment_status_update',
            return_value='ambiguous',
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
        self.assertTrue(notifications['payment_status_update_ambiguous'])
        self.assertFalse(notifications['order_notification_pending'])
        self.assertTrue(notifications['order_notification_sent'])
        self.assertEqual(
            order.payment_payload['post_payment_channels']['telegram']['state'],
            'ambiguous',
        )

    def test_send_phase_markers_are_persisted_before_external_calls(self):
        order = self._paid_attempt_order(number='TWC30072026N07')

        def assert_payment_marker(*args, **kwargs):
            order.refresh_from_db()
            notifications = order.payment_payload['telegram_notifications']
            self.assertTrue(notifications['payment_status_update_send_started_at'])
            return True

        def assert_order_marker(*args, **kwargs):
            order.refresh_from_db()
            notifications = order.payment_payload['telegram_notifications']
            self.assertTrue(notifications['order_notification_send_started_at'])
            return True

        with patch(
            'orders.telegram_notifications.TelegramNotifier.send_admin_payment_status_update',
            side_effect=assert_payment_marker,
        ), patch(
            'orders.telegram_notifications.TelegramNotifier.send_new_order_notification',
            side_effect=assert_order_marker,
        ):
            call_command(
                'reconcile_order_telegram_notifications',
                max_age_hours=168,
                min_age_seconds=0,
                limit=10,
            )

        order.refresh_from_db()
        notifications = order.payment_payload['telegram_notifications']
        self.assertIsNone(notifications['payment_status_update_send_started_at'])
        self.assertIsNone(notifications['order_notification_send_started_at'])

    def test_expired_payment_send_phase_becomes_ambiguous_without_resend(self):
        order = self._paid_attempt_order(number='TWC30072026N08')
        payload = dict(order.payment_payload)
        notifications = dict(payload['telegram_notifications'])
        notifications.update({
            'delivery_attempt_count': 1,
            'delivery_retry_lease_until': (timezone.now() - timedelta(minutes=1)).isoformat(),
            'payment_status_update_send_started_at': (
                timezone.now() - timedelta(minutes=6)
            ).isoformat(),
        })
        payload['telegram_notifications'] = notifications
        order.payment_payload = payload
        order.save(update_fields=['payment_payload'])

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

        payment_update.assert_not_called()
        order_card.assert_called_once()
        order.refresh_from_db()
        notifications = order.payment_payload['telegram_notifications']
        self.assertTrue(notifications['payment_status_update_ambiguous'])
        self.assertFalse(notifications['order_notification_pending'])
        self.assertTrue(notifications['order_notification_sent'])

    def test_payment_ambiguity_with_card_failure_retries_only_the_card(self):
        order = self._paid_attempt_order(number='TWC30072026N10')

        with patch(
            'orders.telegram_notifications.TelegramNotifier.send_admin_payment_status_update',
            return_value='ambiguous',
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
        self.assertTrue(notifications['payment_status_update_ambiguous'])
        self.assertTrue(notifications['order_notification_sent'])
        self.assertFalse(notifications['order_notification_pending'])
        self.assertEqual(
            order.payment_payload['post_payment_channels']['telegram']['state'],
            'ambiguous',
        )

    def test_ambiguous_existing_card_still_allows_one_payment_alert(self):
        order = self._paid_attempt_order(number='TWC30072026N11')
        payload = dict(order.payment_payload)
        notifications = dict(payload['telegram_notifications'])
        notifications.update({
            'order_notification_pending': False,
            'order_notification_ambiguous': True,
            'payment_status_update_sent': False,
        })
        payload['telegram_notifications'] = notifications
        order.payment_payload = payload
        order.save(update_fields=['payment_payload'])

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
        order_card.assert_not_called()
        order.refresh_from_db()
        notifications = order.payment_payload['telegram_notifications']
        self.assertTrue(notifications['payment_status_update_sent'])
        self.assertTrue(notifications['order_notification_ambiguous'])
        self.assertFalse(notifications['order_notification_pending'])
        self.assertEqual(
            order.payment_payload['post_payment_channels']['telegram']['state'],
            'ambiguous',
        )

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
