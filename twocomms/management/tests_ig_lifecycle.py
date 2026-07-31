import hashlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.ig_bot_models import IgLifecycleEvent
from management.models import (
    IgCheckoutProposal,
    IgClient,
    IgDeal,
    IgFollowUpTask,
    IgOrderAttribution,
    InstagramBotSettings,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from management.services.ig_lifecycle import (
    _message,
    dispatch_due_lifecycle_events,
    dispatch_lifecycle_event,
    ensure_lifecycle_event,
)
from orders.models import Order, PaymentAttempt


class InstagramLifecycleTests(TestCase):
    def setUp(self):
        self.client = IgClient.get_or_create_for_sender(
            "ig-lifecycle-test",
            defaults={"language": "uk"},
        )
        self.client.language = "uk"
        self.client.last_message_at = timezone.now()
        self.client.save(update_fields=["language", "last_message_at", "updated_at"])
        self.deal = IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("950.00"),
        )
        self.episode = ensure_episode_for_deal(self.deal)
        self.order = Order.objects.create(
            full_name="Іван Іванов",
            phone="+380501112233",
            email="buyer@example.com",
            city="Київ",
            np_office="Відділення №1",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("950.00"),
        )
        self.attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"ig-lifecycle-attempt").hexdigest(),
            full_name=self.order.full_name,
            phone=self.order.phone,
            email=self.order.email,
            city=self.order.city,
            np_office=self.order.np_office,
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.CONVERTED,
            cart_snapshot={"checkout_surface": "instagram_proposal", "items": []},
            gross_amount=self.order.total_sum,
            payable_amount=self.order.total_sum,
            payment_amount=self.order.total_sum,
            order=self.order,
        )
        self.proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            catalog_total=self.order.total_sum,
            quoted_total=self.order.total_sum,
            requested_payment_amount=self.order.total_sum,
            items_digest="a" * 64,
        )
        self.proposal.payment_attempt = self.attempt
        self.proposal.save(update_fields=["payment_attempt", "updated_at"])
        self.attribution = IgOrderAttribution.objects.create(
            order=self.order,
            client=self.client,
            deal=self.deal,
            creation_mode="provider_auto",
            payment_source="provider_attempt",
        )
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled", "updated_at"])

    def _event(self, kind=IgLifecycleEvent.Kind.PAYMENT_VERIFIED, payload=None):
        event, created = ensure_lifecycle_event(
            self.order,
            kind,
            payload=payload or {"attempt_id": self.attempt.pk, "amount": "950.00"},
        )
        self.assertTrue(created)
        return event

    def test_payment_copy_contains_phone_city_office_and_order_number(self):
        event = self._event()
        message = _message(event)

        for value in (
            self.order.full_name,
            self.order.phone,
            self.order.city,
            self.order.np_office,
            self.order.order_number,
        ):
            self.assertIn(value, message)

    @patch("management.services.instagram_bot.send_text")
    def test_opted_out_client_cancels_event_before_provider_call(self, send_text):
        self.client.bot_paused = True
        self.client.paused_reason = "opt_out"
        self.client.save(update_fields=["bot_paused", "paused_reason", "updated_at"])
        event = self._event()

        self.assertEqual(dispatch_lifecycle_event(event.pk), IgLifecycleEvent.State.CANCELLED)
        send_text.assert_not_called()
        event.refresh_from_db()
        self.assertEqual(event.last_error, "client_paused")
        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"]["instagram_lifecycle"]
        self.assertEqual(channel["state"], "disabled")
        self.assertEqual(channel["error"], "client_paused")

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_text")
    def test_closed_window_creates_one_prepared_manager_task(self, send_text, notify_manager):
        self.client.last_message_at = None
        self.client.save(update_fields=["last_message_at", "updated_at"])
        event = self._event()

        self.assertEqual(
            dispatch_lifecycle_event(event.pk),
            IgLifecycleEvent.State.WAITING_WINDOW,
        )
        task = IgFollowUpTask.objects.get(
            client=self.client,
            deal=self.deal,
            kind=IgFollowUpTask.Kind.MANAGER_TASK,
            reason=f"ig_lifecycle:{event.event_key}",
        )
        self.assertEqual(task.status, IgFollowUpTask.Status.PENDING)
        self.assertIn(self.order.order_number, task.message_text)
        self.assertEqual(IgFollowUpTask.objects.filter(reason=task.reason).count(), 1)
        send_text.assert_not_called()
        notify_manager.assert_called_once()
        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"]["instagram_lifecycle"]
        self.assertEqual(channel["state"], "pending")
        self.assertEqual(channel["error"], "standard_response_window_closed")

    @patch("management.services.instagram_bot.send_text", return_value=(True, "", "", "meta-lifecycle-1"))
    def test_expired_processing_lease_is_reclaimed(self, send_text):
        event = self._event()
        event.state = IgLifecycleEvent.State.PROCESSING
        event.lease_token = "dead-worker"
        event.lease_expires_at = timezone.now() - timedelta(minutes=1)
        event.due_at = timezone.now() - timedelta(minutes=1)
        event.save(update_fields=["state", "lease_token", "lease_expires_at", "due_at", "updated_at"])

        result = dispatch_due_lifecycle_events(limit=1)
        event.refresh_from_db()
        self.assertEqual((result, event.state, event.last_error), (1, IgLifecycleEvent.State.SENT, ""))
        self.assertEqual(event.state, IgLifecycleEvent.State.SENT)
        send_text.assert_called_once()

    @patch("management.services.instagram_bot.send_text", return_value=(True, "", "", "meta-channel-1"))
    def test_direct_delivery_updates_independent_order_channel_state(self, send_text):
        event = self._event()

        self.assertEqual(dispatch_lifecycle_event(event.pk), IgLifecycleEvent.State.SENT)

        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"]["instagram_lifecycle"]
        self.assertEqual(channel["state"], "sent")
        self.assertEqual(channel["provider_message_id"], "meta-channel-1")
        send_text.assert_called_once()

    @patch("management.services.instagram_bot.send_text", return_value=(False, "permanent", "blocked"))
    def test_permanent_failure_is_operator_only_and_not_replayed(self, send_text):
        event = self._event()

        self.assertEqual(dispatch_lifecycle_event(event.pk), IgLifecycleEvent.State.FAILED)
        self.assertEqual(dispatch_lifecycle_event(event.pk), IgLifecycleEvent.State.FAILED)
        self.assertEqual(send_text.call_count, 1)
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ig_lifecycle:{event.event_key}",
            ).exists()
        )

    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="page-token")
    @patch(
        "management.services.instagram_bot._provider_http",
        return_value=(200, '{"recipient_id":"ig-lifecycle-test","message_id":"mid-123"}'),
    )
    def test_send_text_can_return_structured_provider_receipt(
        self, provider_http, _page_token, _account_id
    ):
        from management.services.instagram_bot import ProviderDeliveryReceipt, send_text

        receipt = send_text(
            self.settings,
            self.client.igsid,
            "Тестове повідомлення",
            return_receipt=True,
        )

        self.assertIsInstance(receipt, ProviderDeliveryReceipt)
        self.assertTrue(receipt.ok)
        self.assertEqual(receipt.provider_message_id, "mid-123")
        self.assertEqual(receipt.as_legacy_tuple(), (True, "", ""))
        provider_http.assert_called_once()
