from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from orders.models import Order, PaymentSideEffectJob
from orders.signals import track_order_changes
from orders import tasks as order_tasks


class OrderTelegramSideEffectTests(TransactionTestCase):
    reset_sequences = True

    def _order(self, **overrides):
        telegram_id = overrides.pop("telegram_id", None)
        if telegram_id is not None:
            user = User.objects.create_user(
                username=f"durable-buyer-{User.objects.count() + 1}"
            )
            user.userprofile.telegram_id = telegram_id
            user.userprofile.save(update_fields=["telegram_id"])
            overrides["user"] = user
        values = {
            "full_name": "Durable buyer",
            "phone": "+380501112299",
            "city": "Kyiv",
            "np_office": "Branch 9",
            "status": "new",
        }
        values.update(overrides)
        return Order.objects.create(**values)

    def _lifecycle_jobs(self):
        return PaymentSideEffectJob.objects.filter(
            kind=PaymentSideEffectJob.Kind.ORDER_TELEGRAM_NOTIFICATION
        )

    def test_save_in_outer_atomic_persists_intent_without_provider_or_thread(self):
        order = self._order()

        with patch(
            "orders.telegram_notifications.TelegramNotifier.send_order_status_update"
        ) as provider:
            with transaction.atomic():
                order.status = "prep"
                order.save()
                job = self._lifecycle_jobs().get()
                self.assertEqual(job.state, PaymentSideEffectJob.State.PENDING)
                self.assertEqual(
                    job.payload,
                    {
                        "notification_type": "status_update",
                        "old_status": "В обробці",
                        "new_status": "Готується до відправлення",
                    },
                )
                provider.assert_not_called()
                self.assertFalse(hasattr(order_tasks, "Thread"))

        self.assertEqual(self._lifecycle_jobs().count(), 1)

    def test_outer_rollback_removes_order_change_and_intent(self):
        order = self._order()

        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with transaction.atomic():
                order.status = "prep"
                order.save()
                self.assertEqual(self._lifecycle_jobs().count(), 1)
                raise RuntimeError("rollback")

        order.refresh_from_db()
        self.assertEqual(order.status, "new")
        self.assertFalse(self._lifecycle_jobs().exists())

    def test_save_failure_rolls_back_intent_with_order_update(self):
        order = self._order()
        order.status = "prep"
        self.assertFalse(connection.in_atomic_block)

        def fail_update(*args, **kwargs):
            self.assertTrue(connection.in_atomic_block)
            raise RuntimeError("order update failed")

        with patch(
            "django.db.models.sql.compiler.SQLUpdateCompiler.execute_sql",
            side_effect=fail_update,
        ), self.assertRaisesRegex(RuntimeError, "order update failed"):
            order.save()

        order.refresh_from_db()
        self.assertEqual(order.status, "new")
        self.assertFalse(self._lifecycle_jobs().exists())

    def test_duplicate_receiver_for_same_row_transition_creates_one_job(self):
        order = self._order()
        order.status = "prep"

        track_order_changes(Order, order)
        track_order_changes(Order, order)

        self.assertEqual(self._lifecycle_jobs().count(), 1)

    def test_future_repeated_transition_after_intervening_save_gets_new_job(self):
        order = self._order()
        order.status = "prep"
        order.save()
        order.status = "new"
        order.save()
        order.status = "prep"
        order.save()

        self.assertEqual(
            self._lifecycle_jobs().filter(
                payload__old_status="В обробці",
                payload__new_status="Готується до відправлення",
            ).count(),
            2,
        )
        self.assertEqual(
            self._lifecycle_jobs().values("event_key").distinct().count(),
            3,
        )

    def test_repeated_transition_with_update_fields_gets_new_job(self):
        order = self._order()
        order.status = "prep"
        order.save(update_fields=["status"])
        order.status = "new"
        order.save(update_fields=["status"])
        order.status = "prep"
        order.save(update_fields=["status"])

        self.assertEqual(
            self._lifecycle_jobs().filter(
                payload__old_status="В обробці",
                payload__new_status="Готується до відправлення",
            ).count(),
            2,
        )

    def test_unrelated_partial_save_does_not_mutate_updated(self):
        order = self._order()
        original_updated = order.updated
        order.manager_comment = "internal note"

        with patch(
            "django.db.models.fields.timezone.now",
            return_value=original_updated + timedelta(minutes=1),
        ):
            order.save(update_fields=["manager_comment"])

        order.refresh_from_db()
        self.assertEqual(order.updated, original_updated)
        self.assertFalse(self._lifecycle_jobs().exists())

    def test_ttn_intent_payload_does_not_persist_tracking_number(self):
        order = self._order()
        order.tracking_number = "20450012345678"
        order.save()

        job = self._lifecycle_jobs().get()
        self.assertEqual(job.payload, {"notification_type": "ttn_added"})
        self.assertNotIn("20450012345678", str(job.payload))

    def test_command_delivers_due_intent_exactly_once(self):
        order = self._order(telegram_id=10001)
        order.status = "prep"
        order.save()

        with patch(
            "orders.telegram_notifications.TelegramNotifier.send_order_status_update",
            return_value="sent",
        ) as provider:
            call_command("reconcile_order_telegram_notifications", limit=10)
            call_command("reconcile_order_telegram_notifications", limit=10)

        provider.assert_called_once_with(
            order,
            "В обробці",
            "Готується до відправлення",
            return_outcome=True,
        )
        job = self._lifecycle_jobs().get()
        self.assertEqual(job.state, PaymentSideEffectJob.State.DONE)
        self.assertEqual(job.attempts, 1)

    def test_command_delivers_ttn_intent_exactly_once(self):
        order = self._order(telegram_id=10002)
        order.tracking_number = "20450012345678"
        order.save()

        with patch(
            "orders.telegram_notifications.TelegramNotifier.send_ttn_added_notification",
            return_value="sent",
        ) as provider:
            call_command("reconcile_order_telegram_notifications", limit=10)
            call_command("reconcile_order_telegram_notifications", limit=10)

        provider.assert_called_once_with(order, return_outcome=True)
        self.assertEqual(
            self._lifecycle_jobs().get().state,
            PaymentSideEffectJob.State.DONE,
        )

    def test_missing_telegram_recipient_is_terminal_without_provider_io(self):
        order = self._order()
        order.status = "prep"
        order.save()

        with patch(
            "orders.telegram_notifications.TelegramNotifier.send_personal_message"
        ) as provider:
            call_command("reconcile_order_telegram_notifications", limit=10)
            call_command("reconcile_order_telegram_notifications", limit=10)

        provider.assert_not_called()
        job = self._lifecycle_jobs().get()
        self.assertEqual(job.state, PaymentSideEffectJob.State.DONE)
        self.assertEqual(job.attempts, 1)

    def test_exception_after_provider_boundary_is_ambiguous_and_not_replayed(self):
        order = self._order(telegram_id=10003)
        order.status = "prep"
        order.save()

        with patch(
            "orders.telegram_notifications.TelegramNotifier.send_order_status_update",
            side_effect=RuntimeError("connection dropped"),
        ) as provider:
            call_command("reconcile_order_telegram_notifications", limit=10)
            call_command("reconcile_order_telegram_notifications", limit=10)

        provider.assert_called_once()
        job = self._lifecycle_jobs().get()
        self.assertEqual(job.state, PaymentSideEffectJob.State.AMBIGUOUS)
        self.assertIsNotNone(job.provider_io_started_at)

    def test_definitive_failure_retries_but_ambiguous_outcome_does_not(self):
        failed_order = self._order(telegram_id=10004)
        failed_order.status = "prep"
        failed_order.save()
        failed_job = self._lifecycle_jobs().get(order=failed_order)

        with patch(
            "orders.telegram_notifications.TelegramNotifier.send_order_status_update",
            side_effect=["failed", "sent"],
        ) as provider:
            call_command("reconcile_order_telegram_notifications", limit=10)
            failed_job.refresh_from_db()
            self.assertEqual(failed_job.state, PaymentSideEffectJob.State.FAILED)
            PaymentSideEffectJob.objects.filter(pk=failed_job.pk).update(
                due_at=timezone.now() - timedelta(seconds=1)
            )
            call_command("reconcile_order_telegram_notifications", limit=10)

        self.assertEqual(provider.call_count, 2)
        failed_job.refresh_from_db()
        self.assertEqual(failed_job.state, PaymentSideEffectJob.State.DONE)

        ambiguous_order = self._order(
            phone="+380501112288",
            telegram_id=10005,
        )
        ambiguous_order.status = "prep"
        ambiguous_order.save()
        ambiguous_job = self._lifecycle_jobs().get(order=ambiguous_order)
        with patch(
            "orders.telegram_notifications.TelegramNotifier.send_order_status_update",
            return_value="ambiguous",
        ) as provider:
            call_command("reconcile_order_telegram_notifications", limit=10)
            call_command("reconcile_order_telegram_notifications", limit=10)

        provider.assert_called_once()
        ambiguous_job.refresh_from_db()
        self.assertEqual(ambiguous_job.state, PaymentSideEffectJob.State.AMBIGUOUS)
        self.assertIsNotNone(ambiguous_job.provider_io_started_at)
