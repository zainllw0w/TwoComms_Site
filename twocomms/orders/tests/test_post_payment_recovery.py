from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from orders.models import Order
from orders.email_receipt import build_order_receipt_context, send_order_receipt_email
from storefront.views.utils import _send_post_payment_events


class PostPaymentRecoveryTests(TestCase):
    def test_receipt_context_uses_net_payable_total_and_keeps_gross(self):
        order = Order.objects.create(
            full_name="Buyer", email="buyer@example.com", phone="+380501112233",
            city="Київ", np_office="Відділення №1", pay_type="online_full",
            payment_status="paid", total_sum=Decimal("1900.00"),
            discount_amount=Decimal("200.00"), payment_payload={},
        )
        context = build_order_receipt_context(order)
        self.assertEqual(context["gross_total_display"], "1 900")
        self.assertEqual(context["total_display"], "1 700")

    def test_post_payment_channel_states_are_independent(self):
        order = Order.objects.create(
            full_name="Buyer",
            email="buyer@example.com",
            phone="+380501112233",
            city="Київ",
            np_office="Відділення №1",
            pay_type="online_full",
            payment_status="paid",
            payment_provider="monobank_pay",
            total_sum=Decimal("950.00"),
            payment_payload={"attempt_id": 42},
        )
        facebook = patch("orders.facebook_conversions_service.get_facebook_conversions_service")
        tiktok = patch("orders.tiktok_events_service.get_tiktok_events_service")
        with patch(
            "storefront.views.utils.deliver_pending_order_telegram_notifications",
            return_value="failed",
        ), facebook as facebook_factory, tiktok as tiktok_factory, patch(
            "orders.email_receipt.send_order_receipt_email",
            return_value=(True, None),
        ), patch("storefront.utm_tracking.ensure_order_purchase_action"):
            facebook_service = facebook_factory.return_value
            facebook_service.enabled = True
            facebook_service.send_purchase_event.return_value = True
            tiktok_service = tiktok_factory.return_value
            tiktok_service.enabled = True
            tiktok_service.send_purchase_event.return_value = True

            _send_post_payment_events(order.pk, "unpaid", order.pay_type)

        order.refresh_from_db()
        channels = order.payment_payload["post_payment_channels"]
        self.assertEqual(channels["telegram"]["state"], "failed")
        self.assertEqual(channels["meta_purchase"]["state"], "sent")
        self.assertEqual(channels["tiktok_purchase"]["state"], "sent")
        self.assertEqual(channels["receipt_email"]["state"], "sent")

    def test_recovery_does_not_skip_order_when_telegram_is_already_sent(self):
        order = Order.objects.create(
            full_name="Buyer",
            phone="+380501112233",
            city="Київ",
            np_office="Відділення №1",
            pay_type="online_full",
            payment_status="paid",
            payment_provider="monobank_pay",
            created=timezone.now() - timedelta(minutes=10),
            payment_payload={
                "attempt_id": 42,
                "telegram_notifications": {"order_notification_sent": True},
                "facebook_events": {},
            },
        )
        output = StringIO()
        with patch(
            "orders.management.commands.reconcile_order_telegram_notifications._send_post_payment_events"
        ) as dispatch:
            call_command(
                "reconcile_order_telegram_notifications",
                min_age_seconds=0,
                stdout=output,
            )

        dispatch.assert_called_once_with(order.pk, "unpaid", order.pay_type)

    def test_receipt_send_marker_prevents_blind_duplicate_after_marker_write_failure(self):
        order = Order.objects.create(
            full_name="Buyer",
            email="buyer@example.com",
            phone="+380501112233",
            city="Київ",
            np_office="Відділення №1",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("950.00"),
            payment_payload={},
        )
        message = patch("orders.email_receipt.EmailMultiAlternatives")
        with message as email_cls, patch(
            "orders.email_receipt.build_order_receipt_email",
            return_value={"subject": "Receipt", "text": "Receipt", "html": "<p>Receipt</p>"},
        ):
            email_cls.return_value.send.return_value = 1
            original_save = Order.save
            save_calls = {"count": 0}

            def fail_after_claim(instance, *args, **kwargs):
                save_calls["count"] += 1
                if save_calls["count"] == 2:
                    raise RuntimeError("marker write failed")
                return original_save(instance, *args, **kwargs)

            with patch("orders.models.Order.save", autospec=True, side_effect=fail_after_claim):
                result = send_order_receipt_email(order)

        self.assertEqual(result[0], False)
        self.assertEqual(result[1], "delivery_unknown")
        order.refresh_from_db()
        self.assertEqual(order.payment_payload.get("receipt_email_status"), "sending")

        with patch("orders.email_receipt.EmailMultiAlternatives") as retry_email:
            retry_result = send_order_receipt_email(order)

        self.assertEqual(retry_result, (False, "delivery_unknown"))
        retry_email.assert_not_called()

    def test_receipt_build_failure_marks_failed_before_smtp(self):
        order = Order.objects.create(
            full_name="Buyer",
            email="buyer@example.com",
            phone="+380501112233",
            city="Київ",
            np_office="Відділення №1",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("950.00"),
            payment_payload={},
        )

        with patch(
            "orders.email_receipt.build_order_receipt_email",
            side_effect=RuntimeError("template render failed"),
        ), patch("orders.email_receipt.EmailMultiAlternatives") as email_cls:
            result = send_order_receipt_email(order)

        self.assertEqual(result, (False, "build_failed"))
        email_cls.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.payment_payload.get("receipt_email_status"), "failed")
        self.assertIn("template render failed", order.payment_payload.get("receipt_email_error", ""))
