import importlib
import importlib.util
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from orders import models as order_models


class PaymentSideEffectJobModelTests(TestCase):
    def setUp(self):
        self.attempt = order_models.PaymentAttempt.objects.create(
            fingerprint="job-attempt-fingerprint",
            full_name="Job buyer",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=order_models.PaymentAttempt.PayType.ONLINE_FULL,
            gross_amount=Decimal("900.00"),
            payable_amount=Decimal("900.00"),
            payment_amount=Decimal("900.00"),
        )

    def _job_model(self):
        model = getattr(order_models, "PaymentSideEffectJob", None)
        self.assertIsNotNone(model, "PaymentSideEffectJob model is not defined")
        return model

    def test_attempt_job_has_pending_state_and_durable_lease_fields(self):
        model = self._job_model()
        now = timezone.now()
        job = model.objects.create(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:1:add-payment-info",
            payment_attempt=self.attempt,
            payload={"source_url": "https://twocomms.shop/cart/"},
            due_at=now,
        )

        self.assertEqual(job.state, model.State.PENDING)
        self.assertEqual(job.attempts, 0)
        self.assertEqual(job.lease_token, "")
        self.assertIsNone(job.lease_expires_at)
        self.assertIsNone(job.provider_io_started_at)
        self.assertIsNone(job.completed_at)

    def test_event_key_is_unique(self):
        model = self._job_model()
        model.objects.create(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:2:add-payment-info",
            payment_attempt=self.attempt,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                model.objects.create(
                    kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
                    event_key="attempt:2:add-payment-info",
                    payment_attempt=self.attempt,
                )

    def test_job_requires_exactly_one_subject(self):
        model = self._job_model()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                model.objects.create(
                    kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
                    event_key="attempt:3:no-subject",
                )

        order = order_models.Order.objects.create(
            full_name="Order buyer",
            phone="+380501112244",
            city="Kyiv",
            np_office="Branch 2",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                model.objects.create(
                    kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
                    event_key="attempt:3:two-subjects",
                    payment_attempt=self.attempt,
                    order=order,
                )

    def test_due_index_contract_is_present(self):
        model = self._job_model()
        index_fields = {
            tuple(index.fields)
            for index in model._meta.indexes
        }
        self.assertIn(("state", "due_at", "id"), index_fields)
        self.assertIn(("lease_expires_at", "id"), index_fields)


class PaymentSideEffectJobServiceTests(TestCase):
    def setUp(self):
        self.attempt = order_models.PaymentAttempt.objects.create(
            fingerprint="job-service-attempt",
            full_name="Service buyer",
            phone="+380501112255",
            city="Kyiv",
            np_office="Branch 3",
            pay_type=order_models.PaymentAttempt.PayType.ONLINE_FULL,
            gross_amount=Decimal("1200.00"),
            payable_amount=Decimal("1200.00"),
            payment_amount=Decimal("1200.00"),
        )

    def _service(self):
        spec = importlib.util.find_spec("orders.payment_side_effects")
        self.assertIsNotNone(spec, "orders.payment_side_effects is not defined")
        return importlib.import_module("orders.payment_side_effects")

    def _order(self, *, payment_payload=None):
        return order_models.Order.objects.create(
            full_name="Paid buyer",
            phone="+380501112277",
            city="Kyiv",
            np_office="Branch 5",
            pay_type="online_full",
            payment_status="paid",
            payment_provider="monobank_pay",
            payment_payload=payment_payload or {},
        )

    def test_enqueue_is_idempotent_by_event_key(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        first, created = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:add-payment-info",
            payment_attempt_id=self.attempt.pk,
            payload={"source_url": "https://twocomms.shop/cart/"},
        )
        second, created_again = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:add-payment-info",
            payment_attempt_id=self.attempt.pk,
            payload={"source_url": "https://twocomms.shop/other/"},
        )

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(model.objects.count(), 1)
        self.assertEqual(first.payload["source_url"], "https://twocomms.shop/cart/")

    def test_attempt_invoice_intents_are_idempotent_and_transactional(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob

        service.enqueue_attempt_invoice_side_effects(
            self.attempt.pk,
            source_url="https://twocomms.shop/cart/",
        )
        service.enqueue_attempt_invoice_side_effects(
            self.attempt.pk,
            source_url="https://twocomms.shop/cart/?retry=1",
        )

        jobs = list(model.objects.order_by("kind"))
        self.assertEqual(len(jobs), 2)
        self.assertEqual(
            {job.kind for job in jobs},
            {
                model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
                model.Kind.ATTEMPT_TELEGRAM_STARTED,
            },
        )
        add_payment = model.objects.get(kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO)
        self.assertEqual(
            add_payment.payload["source_url"],
            "https://twocomms.shop/cart/",
        )

    def test_attempt_invoice_intents_roll_back_with_transaction(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                service.enqueue_attempt_invoice_side_effects(self.attempt.pk)
                raise RuntimeError("rollback")

        self.assertFalse(model.objects.exists())

    def test_enqueue_rejects_pii_and_wrong_subject_kind(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        with self.assertRaisesRegex(ValueError, "payload"):
            service.enqueue_payment_side_effect(
                kind=model.Kind.ATTEMPT_TELEGRAM_STARTED,
                event_key="attempt:service:telegram-pii",
                payment_attempt_id=self.attempt.pk,
                payload={"phone": self.attempt.phone},
            )
        with self.assertRaisesRegex(ValueError, "payment_attempt"):
            service.enqueue_payment_side_effect(
                kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
                event_key="attempt:service:no-attempt",
                order_id=order_models.Order.objects.create(
                    full_name="Order buyer",
                    phone="+380501112266",
                    city="Kyiv",
                    np_office="Branch 4",
                ).pk,
            )

    def test_claim_has_one_active_lease_and_reclaims_before_provider_io(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        now = timezone.now()
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:claim",
            payment_attempt_id=self.attempt.pk,
            due_at=now,
        )

        first = service.claim_payment_side_effect(job.pk, now=now)
        blocked = service.claim_payment_side_effect(job.pk, now=now + timedelta(seconds=1))
        self.assertEqual(first.outcome, "claimed")
        self.assertTrue(first.lease_token)
        self.assertEqual(blocked.outcome, "leased")

        reclaimed = service.claim_payment_side_effect(
            job.pk,
            now=now + service.DEFAULT_LEASE_DURATION + timedelta(seconds=1),
        )
        self.assertEqual(reclaimed.outcome, "claimed")
        self.assertNotEqual(reclaimed.lease_token, first.lease_token)
        job.refresh_from_db()
        self.assertEqual(job.attempts, 2)

    def test_expired_lease_after_provider_boundary_becomes_ambiguous(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        now = timezone.now()
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_TELEGRAM_STARTED,
            event_key="attempt:service:telegram-boundary",
            payment_attempt_id=self.attempt.pk,
            due_at=now,
        )
        claim = service.claim_payment_side_effect(job.pk, now=now)
        self.assertTrue(
            service.mark_payment_side_effect_provider_io_started(
                job.pk,
                claim.lease_token,
                now=now + timedelta(seconds=1),
            )
        )

        result = service.claim_payment_side_effect(
            job.pk,
            now=now + service.DEFAULT_LEASE_DURATION + timedelta(seconds=1),
        )
        self.assertEqual(result.outcome, "ambiguous")
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.AMBIGUOUS)
        self.assertEqual(job.lease_token, "")
        self.assertIsNone(job.lease_expires_at)

    def test_active_lease_after_provider_boundary_remains_leased(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        now = timezone.now()
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:active-provider-boundary",
            payment_attempt_id=self.attempt.pk,
            due_at=now,
        )
        claim = service.claim_payment_side_effect(job.pk, now=now)
        self.assertTrue(
            service.mark_payment_side_effect_provider_io_started(
                job.pk,
                claim.lease_token,
                now=now + timedelta(seconds=1),
            )
        )

        result = service.claim_payment_side_effect(
            job.pk,
            now=now + timedelta(seconds=2),
        )

        self.assertEqual(result.outcome, "leased")
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.PROCESSING)
        self.assertEqual(job.lease_token, claim.lease_token)

    def test_only_current_lease_can_complete_job(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        now = timezone.now()
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:complete",
            payment_attempt_id=self.attempt.pk,
            due_at=now,
        )
        claim = service.claim_payment_side_effect(job.pk, now=now)

        self.assertFalse(
            service.complete_payment_side_effect(
                job.pk,
                "stale-worker",
                now=now + timedelta(seconds=1),
            )
        )
        self.assertTrue(
            service.complete_payment_side_effect(
                job.pk,
                claim.lease_token,
                now=now + timedelta(seconds=2),
            )
        )
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.DONE)
        self.assertEqual(job.lease_token, "")
        self.assertIsNotNone(job.completed_at)

    def test_failed_provider_delivery_is_retried_only_after_backoff(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        now = timezone.now()
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:add-payment-retry",
            payment_attempt_id=self.attempt.pk,
            due_at=now,
        )
        facebook = Mock(enabled=True)
        facebook.send_add_payment_info_event.return_value = False

        with patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=facebook,
        ):
            first = service.process_payment_side_effect_job(job.pk, now=now)
            before_due = service.process_payment_side_effect_job(
                job.pk,
                now=now + timedelta(seconds=1),
            )

        self.assertEqual(first, "failed")
        self.assertEqual(before_due, "not_due")
        self.assertEqual(facebook.send_add_payment_info_event.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.FAILED)
        self.assertGreater(job.due_at, now + timedelta(seconds=1))
        self.assertIsNone(job.provider_io_started_at)

    def test_add_payment_transport_timeout_is_ambiguous_and_not_replayed(self):
        from orders.provider_delivery import ProviderDeliveryAmbiguous

        service = self._service()
        model = order_models.PaymentSideEffectJob
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:add-payment-timeout",
            payment_attempt_id=self.attempt.pk,
        )
        facebook = Mock(enabled=True)
        facebook.send_add_payment_info_event.side_effect = (
            ProviderDeliveryAmbiguous("transport outcome unknown")
        )

        with patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=facebook,
        ):
            first = service.process_payment_side_effect_job(job.pk)
            second = service.process_payment_side_effect_job(job.pk)

        self.assertEqual((first, second), ("ambiguous", "ambiguous"))
        facebook.send_add_payment_info_event.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.AMBIGUOUS)

    def _post_payment_provider_job(self):
        service = self._service()
        order = self._order()
        job, _ = service.enqueue_order_post_payment_side_effect(
            order.pk,
            previous_status="unpaid",
            pay_type="online_full",
        )
        return service, order, job

    def test_meta_purchase_transport_reset_is_ambiguous_and_not_replayed(self):
        from orders.provider_delivery import ProviderDeliveryAmbiguous

        service, _order, job = self._post_payment_provider_job()
        facebook = SimpleNamespace(
            enabled=True,
            send_purchase_event=Mock(
                side_effect=ProviderDeliveryAmbiguous("connection reset")
            ),
        )
        tiktok = SimpleNamespace(enabled=False)
        with patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=facebook,
        ), patch(
            "orders.tiktok_events_service.get_tiktok_events_service",
            return_value=tiktok,
        ), patch(
            "storefront.utm_tracking.ensure_order_purchase_action"
        ):
            first = service.process_payment_side_effect_job(job.pk)
            second = service.process_payment_side_effect_job(job.pk)

        self.assertEqual((first, second), ("ambiguous", "ambiguous"))
        facebook.send_purchase_event.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.state, order_models.PaymentSideEffectJob.State.AMBIGUOUS)

    def test_tiktok_purchase_transport_timeout_is_ambiguous_and_not_replayed(self):
        from orders.provider_delivery import ProviderDeliveryAmbiguous

        service, _order, job = self._post_payment_provider_job()
        facebook = SimpleNamespace(enabled=False)
        tiktok = SimpleNamespace(
            enabled=True,
            send_purchase_event=Mock(
                side_effect=ProviderDeliveryAmbiguous("transport timeout")
            ),
        )
        with patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=facebook,
        ), patch(
            "orders.tiktok_events_service.get_tiktok_events_service",
            return_value=tiktok,
        ), patch(
            "storefront.utm_tracking.ensure_order_purchase_action"
        ):
            first = service.process_payment_side_effect_job(job.pk)
            second = service.process_payment_side_effect_job(job.pk)

        self.assertEqual((first, second), ("ambiguous", "ambiguous"))
        tiktok.send_purchase_event.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.state, order_models.PaymentSideEffectJob.State.AMBIGUOUS)

    def test_failure_before_provider_boundary_remains_retryable(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:pre-provider-failure",
            payment_attempt_id=self.attempt.pk,
        )

        with patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            side_effect=RuntimeError("configuration unavailable"),
        ):
            outcome = service.process_payment_side_effect_job(job.pk)

        self.assertEqual(outcome, "failed")
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.FAILED)
        self.assertIsNone(job.provider_io_started_at)

    def test_add_payment_info_replay_uses_durable_marker_without_resend(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:add-payment-once",
            payment_attempt_id=self.attempt.pk,
        )
        facebook = Mock(enabled=True)
        facebook.send_add_payment_info_event.return_value = True

        with patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=facebook,
        ):
            first = service.process_payment_side_effect_job(job.pk)
            second = service.process_payment_side_effect_job(job.pk)

        self.assertEqual(first, "done")
        self.assertEqual(second, "done")
        facebook.send_add_payment_info_event.assert_called_once_with(
            order=self.attempt,
            payment_amount=float(self.attempt.payment_amount),
            event_id=self.attempt.add_payment_event_id,
            source_url=None,
        )

    def test_crash_after_persisted_add_payment_marker_completes_without_resend(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        now = timezone.now()
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:add-payment-crash-marker",
            payment_attempt_id=self.attempt.pk,
            due_at=now,
        )
        claim = service.claim_payment_side_effect(job.pk, now=now)
        service.mark_payment_side_effect_provider_io_started(
            job.pk,
            claim.lease_token,
            now=now + timedelta(seconds=1),
        )
        self.attempt.event_state = {
            "fb_capi_add_payment_info": {"event_id": self.attempt.add_payment_event_id}
        }
        self.attempt.save(update_fields=["event_state"])

        facebook = Mock(enabled=True)
        with patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=facebook,
        ):
            outcome = service.process_payment_side_effect_job(
                job.pk,
                now=now + service.DEFAULT_LEASE_DURATION + timedelta(seconds=1),
            )

        self.assertEqual(outcome, "done")
        facebook.send_add_payment_info_event.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.DONE)

    def test_telegram_attempt_replay_sends_once_and_persists_marker(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_TELEGRAM_STARTED,
            event_key="attempt:service:telegram-once",
            payment_attempt_id=self.attempt.pk,
        )

        with patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value="sent",
        ) as send:
            first = service.process_payment_side_effect_job(job.pk)
            second = service.process_payment_side_effect_job(job.pk)

        self.assertEqual(first, "done")
        self.assertEqual(second, "done")
        send.assert_called_once()
        self.attempt.refresh_from_db()
        self.assertTrue(self.attempt.notification_state["started_sent"])

    def test_telegram_ambiguous_delivery_is_not_replayed(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_TELEGRAM_STARTED,
            event_key="attempt:service:telegram-ambiguous",
            payment_attempt_id=self.attempt.pk,
        )

        with patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value="ambiguous",
        ) as send:
            first = service.process_payment_side_effect_job(job.pk)
            second = service.process_payment_side_effect_job(job.pk)

        self.assertEqual(first, "ambiguous")
        self.assertEqual(second, "ambiguous")
        send.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.AMBIGUOUS)

    def test_telegram_attempt_notification_can_return_ambiguous_outcome(self):
        from orders.telegram_notifications import (
            TelegramDeliveryReport,
            TelegramNotifier,
        )

        notifier = TelegramNotifier()
        with patch.object(notifier, "is_configured", return_value=True), patch.object(
            notifier, "send_message", return_value=TelegramDeliveryReport("ambiguous")
        ):
            outcome = notifier.send_payment_attempt_notification(
                self.attempt,
                return_outcome=True,
            )

        self.assertEqual(outcome, "ambiguous")

    def test_unconfigured_telegram_attempt_returns_typed_failed_outcome(self):
        from orders.telegram_notifications import TelegramNotifier

        notifier = TelegramNotifier()
        with patch.object(notifier, "is_configured", return_value=False):
            outcome = notifier.send_payment_attempt_notification(
                self.attempt,
                return_outcome=True,
            )

        self.assertEqual(outcome, "failed")

    def test_order_post_payment_replay_uses_channel_ledger(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        order = self._order()
        job, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ORDER_POST_PAYMENT,
            event_key="order:service:post-payment-once",
            order_id=order.pk,
            payload={"previous_status": "unpaid", "pay_type": "online_full"},
        )

        def persist_terminal_channels(*_args, **_kwargs):
            order.refresh_from_db()
            payload = dict(order.payment_payload or {})
            payload["post_payment_channels"] = {
                "telegram": {"state": "sent"},
                "meta_purchase": {"state": "sent"},
                "tiktok_purchase": {"state": "disabled"},
                "receipt_email": {"state": "skipped"},
                "instagram_lifecycle": {"state": "skipped"},
            }
            order.payment_payload = payload
            order.save(update_fields=["payment_payload"])
            return "sent"

        with patch(
            "storefront.views.utils._send_post_payment_events",
            side_effect=persist_terminal_channels,
        ) as send:
            first = service.process_payment_side_effect_job(job.pk)
            second = service.process_payment_side_effect_job(job.pk)

        self.assertEqual(first, "done")
        self.assertEqual(second, "done")
        send.assert_called_once_with(
            order.pk,
            "unpaid",
            "online_full",
            only_channel="telegram",
        )

    def test_expired_cursor_after_telegram_resumes_remaining_channels(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        now = timezone.now()
        order = self._order(
            payment_payload={
                "post_payment_channels": {
                    "telegram": {"state": "sent"},
                    "meta_purchase": {"state": "pending"},
                    "tiktok_purchase": {"state": "pending"},
                    "receipt_email": {"state": "pending"},
                }
            }
        )
        job, _ = service.enqueue_order_post_payment_side_effect(
            order.pk,
            previous_status="unpaid",
            pay_type="online_full",
            due_at=now,
        )
        job.state = model.State.PROCESSING
        job.attempts = 1
        job.lease_token = "stopped-worker"
        job.lease_expires_at = now - timedelta(seconds=1)
        job.provider_io_started_at = now - timedelta(seconds=2)
        job.payload = {
            **job.payload,
            "channel_cursor": "telegram",
        }
        job.save(
            update_fields=[
                "state",
                "attempts",
                "lease_token",
                "lease_expires_at",
                "provider_io_started_at",
                "payload",
            ]
        )
        delivered = []

        def persist_channel(order_id, *_args, only_channel=None, **_kwargs):
            delivered.append(only_channel)
            current = order_models.Order.objects.get(pk=order_id)
            payload = dict(current.payment_payload or {})
            channels = dict(payload.get("post_payment_channels") or {})
            channels[only_channel] = {"state": "sent"}
            payload["post_payment_channels"] = channels
            current.payment_payload = payload
            current.save(update_fields=["payment_payload"])
            return "sent"

        with patch(
            "storefront.views.utils._send_post_payment_events",
            side_effect=persist_channel,
        ):
            first = service.process_payment_side_effect_job(job.pk, now=now)
            second = service.process_payment_side_effect_job(
                job.pk,
                now=now + timedelta(seconds=1),
            )

        self.assertEqual(first, "done")
        self.assertEqual(second, "done")
        self.assertEqual(
            delivered,
            ["meta_purchase", "tiktok_purchase", "receipt_email"],
        )
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.DONE)
        self.assertIsNone(job.provider_io_started_at)

    def test_terminal_ledger_reconciliation_clears_stale_channel_boundary(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        now = timezone.now()
        order = self._order(
            payment_payload={
                "post_payment_channels": {
                    "telegram": {"state": "sent"},
                    "meta_purchase": {"state": "sent"},
                    "tiktok_purchase": {"state": "disabled"},
                    "receipt_email": {"state": "sent"},
                }
            }
        )
        job, _ = service.enqueue_order_post_payment_side_effect(
            order.pk,
            previous_status="unpaid",
            pay_type="online_full",
            due_at=now,
        )
        job.state = model.State.PROCESSING
        job.attempts = 1
        job.lease_token = "stopped-after-receipt"
        job.lease_expires_at = now - timedelta(seconds=1)
        job.provider_io_started_at = now - timedelta(seconds=2)
        job.payload = {**job.payload, "channel_cursor": "receipt_email"}
        job.save(
            update_fields=[
                "state",
                "attempts",
                "lease_token",
                "lease_expires_at",
                "provider_io_started_at",
                "payload",
            ]
        )

        outcome = service.process_payment_side_effect_job(job.pk, now=now)

        self.assertEqual(outcome, "done")
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.DONE)
        self.assertEqual(job.lease_token, "")
        self.assertIsNone(job.lease_expires_at)
        self.assertIsNone(job.provider_io_started_at)
        self.assertNotIn("channel_cursor", job.payload)

    def test_failed_channel_does_not_block_later_channels_or_repeat_successes(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        now = timezone.now()
        order = self._order()
        job, _ = service.enqueue_order_post_payment_side_effect(
            order.pk,
            previous_status="unpaid",
            pay_type="online_full",
            due_at=now,
        )
        attempts = []
        meta_attempts = 0

        def persist_channel(order_id, *_args, only_channel=None, **_kwargs):
            nonlocal meta_attempts
            attempts.append(only_channel)
            state = "sent"
            if only_channel == "meta_purchase":
                meta_attempts += 1
                state = "failed" if meta_attempts == 1 else "sent"
            current = order_models.Order.objects.get(pk=order_id)
            payload = dict(current.payment_payload or {})
            channels = dict(payload.get("post_payment_channels") or {})
            channels[only_channel] = {"state": state}
            payload["post_payment_channels"] = channels
            current.payment_payload = payload
            current.save(update_fields=["payment_payload"])
            return "failed" if state == "failed" else "sent"

        with patch(
            "storefront.views.utils._send_post_payment_events",
            side_effect=persist_channel,
        ):
            first = service.process_payment_side_effect_job(job.pk, now=now)
            job.refresh_from_db()
            retry_at = job.due_at
            second = service.process_payment_side_effect_job(job.pk, now=retry_at)

        self.assertEqual(first, "failed")
        self.assertEqual(second, "done")
        self.assertEqual(
            attempts,
            [
                "telegram",
                "meta_purchase",
                "tiktok_purchase",
                "receipt_email",
                "meta_purchase",
            ],
        )

    def test_provider_success_without_durable_ledger_is_channel_ambiguous(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        order = self._order()
        job, _ = service.enqueue_order_post_payment_side_effect(
            order.pk,
            previous_status="unpaid",
            pay_type="online_full",
        )
        delivered = []

        def lose_first_ledger_write(order_id, *_args, only_channel=None, **_kwargs):
            delivered.append(only_channel)
            if only_channel == "telegram":
                return "sent"
            current = order_models.Order.objects.get(pk=order_id)
            payload = dict(current.payment_payload or {})
            channels = dict(payload.get("post_payment_channels") or {})
            channels[only_channel] = {"state": "sent"}
            payload["post_payment_channels"] = channels
            current.payment_payload = payload
            current.save(update_fields=["payment_payload"])
            return "sent"

        with patch(
            "storefront.views.utils._send_post_payment_events",
            side_effect=lose_first_ledger_write,
        ):
            outcome = service.process_payment_side_effect_job(job.pk)

        self.assertEqual(outcome, "ambiguous")
        self.assertEqual(
            delivered,
            ["telegram", "meta_purchase", "tiktok_purchase", "receipt_email"],
        )
        order.refresh_from_db()
        channels = order.payment_payload["post_payment_channels"]
        self.assertEqual(channels["telegram"]["state"], "ambiguous")
        self.assertEqual(channels["meta_purchase"]["state"], "sent")
        self.assertEqual(channels["tiktok_purchase"]["state"], "sent")
        self.assertEqual(channels["receipt_email"]["state"], "sent")
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.AMBIGUOUS)

    def test_unknown_channel_outcome_is_ambiguous_and_not_replayed(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        order = self._order()
        job, _ = service.enqueue_order_post_payment_side_effect(
            order.pk,
            previous_status="unpaid",
            pay_type="online_full",
        )
        delivered = []

        def persist_channel(order_id, *_args, only_channel=None, **_kwargs):
            delivered.append(only_channel)
            state = "unknown" if only_channel == "meta_purchase" else "sent"
            current = order_models.Order.objects.get(pk=order_id)
            payload = dict(current.payment_payload or {})
            channels = dict(payload.get("post_payment_channels") or {})
            channels[only_channel] = {"state": state}
            payload["post_payment_channels"] = channels
            current.payment_payload = payload
            current.save(update_fields=["payment_payload"])
            return state

        with patch(
            "storefront.views.utils._send_post_payment_events",
            side_effect=persist_channel,
        ):
            first = service.process_payment_side_effect_job(job.pk)
            second = service.process_payment_side_effect_job(job.pk)

        self.assertEqual((first, second), ("ambiguous", "ambiguous"))
        self.assertEqual(
            delivered,
            ["telegram", "meta_purchase", "tiktok_purchase", "receipt_email"],
        )
        job.refresh_from_db()
        self.assertEqual(job.state, model.State.AMBIGUOUS)

    def test_channel_cursor_and_provider_boundary_are_persisted_before_delivery(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        order = self._order()
        job, _ = service.enqueue_order_post_payment_side_effect(
            order.pk,
            previous_status="unpaid",
            pay_type="online_full",
        )
        observed = []

        def persist_channel(order_id, *_args, only_channel=None, **_kwargs):
            current_job = model.objects.get(pk=job.pk)
            observed.append(
                (
                    only_channel,
                    current_job.payload.get("channel_cursor"),
                    current_job.provider_io_started_at is not None,
                )
            )
            current = order_models.Order.objects.get(pk=order_id)
            payload = dict(current.payment_payload or {})
            channels = dict(payload.get("post_payment_channels") or {})
            channels[only_channel] = {"state": "sent"}
            payload["post_payment_channels"] = channels
            current.payment_payload = payload
            current.save(update_fields=["payment_payload"])
            return "sent"

        with patch(
            "storefront.views.utils._send_post_payment_events",
            side_effect=persist_channel,
        ):
            outcome = service.process_payment_side_effect_job(job.pk)

        self.assertEqual(outcome, "done")
        self.assertEqual(
            observed,
            [
                ("telegram", "telegram", True),
                ("meta_purchase", "meta_purchase", True),
                ("tiktok_purchase", "tiktok_purchase", True),
                ("receipt_email", "receipt_email", True),
            ],
        )
        job.refresh_from_db()
        self.assertIsNone(job.provider_io_started_at)

    def test_existing_reconcile_command_drains_bounded_due_job_batch(self):
        service = self._service()
        model = order_models.PaymentSideEffectJob
        first, _ = service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_ADD_PAYMENT_INFO,
            event_key="attempt:service:command-first",
            payment_attempt_id=self.attempt.pk,
        )
        service.enqueue_payment_side_effect(
            kind=model.Kind.ATTEMPT_TELEGRAM_STARTED,
            event_key="attempt:service:command-second",
            payment_attempt_id=self.attempt.pk,
        )
        output = StringIO()

        with patch(
            "orders.management.commands.reconcile_order_telegram_notifications."
            "process_payment_side_effect_job",
            return_value="done",
        ) as process:
            call_command(
                "reconcile_order_telegram_notifications",
                max_age_hours=168,
                min_age_seconds=0,
                limit=1,
                stdout=output,
            )

        process.assert_called_once_with(first.pk)
        self.assertIn("jobs_scanned=1", output.getvalue())


if __name__ == "__main__":
    import unittest

    unittest.main()
