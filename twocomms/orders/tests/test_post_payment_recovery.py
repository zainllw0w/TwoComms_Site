from datetime import timedelta
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from orders.models import Order
from orders.email_receipt import (
    build_order_receipt_context,
    build_order_receipt_email,
    send_order_receipt_email,
)
from storefront.views.utils import _send_post_payment_events


class PostPaymentRecoveryTests(TestCase):
    def _paid_order(self, **kwargs):
        payload = {
            "full_name": "Buyer",
            "phone": "+380501112233",
            "city": "Київ",
            "np_office": "Відділення №1",
            "pay_type": "online_full",
            "payment_status": "paid",
            "payment_provider": "monobank_pay",
            "total_sum": Decimal("950.00"),
            "payment_payload": {"attempt_id": 42},
        }
        payload.update(kwargs)
        return Order.objects.create(**payload)

    def test_storefront_without_instagram_event_is_marked_skipped(self):
        order = self._paid_order(source="web")
        with patch(
            "storefront.views.utils.deliver_pending_order_telegram_notifications",
            return_value="sent",
        ), patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=SimpleNamespace(enabled=False),
        ), patch(
            "orders.tiktok_events_service.get_tiktok_events_service",
            return_value=SimpleNamespace(enabled=False),
        ), patch("orders.email_receipt.send_order_receipt_email", return_value=(False, "no_valid_email")), patch(
            "storefront.utm_tracking.ensure_order_purchase_action"
        ):
            _send_post_payment_events(order.pk, "unpaid", order.pay_type)

        order.refresh_from_db()
        self.assertEqual(order.payment_payload["post_payment_channels"]["instagram_lifecycle"]["state"], "skipped")

    def test_telegram_already_sent_is_a_sent_channel(self):
        order = self._paid_order(payment_payload={"telegram_notifications": {"order_notification_sent": True}})
        with patch(
            "storefront.views.utils.deliver_pending_order_telegram_notifications",
            return_value="already_sent",
        ), patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=SimpleNamespace(enabled=False),
        ), patch(
            "orders.tiktok_events_service.get_tiktok_events_service",
            return_value=SimpleNamespace(enabled=False),
        ), patch("orders.email_receipt.send_order_receipt_email", return_value=(False, "no_valid_email")), patch(
            "storefront.utm_tracking.ensure_order_purchase_action"
        ):
            _send_post_payment_events(order.pk, "unpaid", order.pay_type)

        order.refresh_from_db()
        self.assertEqual(order.payment_payload["post_payment_channels"]["telegram"]["state"], "sent")

    def test_meta_ledger_uses_persisted_capi_event_id(self):
        order = self._paid_order(payment_payload={"fb_conversions_api": {"event_id": "capi-event-42"}})
        with patch(
            "storefront.views.utils.deliver_pending_order_telegram_notifications", return_value="sent"
        ), patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=SimpleNamespace(enabled=True, send_purchase_event=Mock(return_value=True)),
        ), patch(
            "orders.tiktok_events_service.get_tiktok_events_service",
            return_value=SimpleNamespace(enabled=False),
        ), patch("orders.email_receipt.send_order_receipt_email", return_value=(False, "no_valid_email")), patch(
            "storefront.utm_tracking.ensure_order_purchase_action"
        ):
            _send_post_payment_events(order.pk, "unpaid", order.pay_type)

        order.refresh_from_db()
        self.assertEqual(
            order.payment_payload["post_payment_channels"]["meta_purchase"]["event_id"],
            "capi-event-42",
        )

    def test_already_sent_meta_ledger_rehydrates_persisted_capi_event_id(self):
        order = self._paid_order(
            payment_payload={
                "fb_conversions_api": {"event_id": "capi-event-already-42"},
                "facebook_events": {"purchase_sent": True},
            }
        )
        with patch(
            "storefront.views.utils.deliver_pending_order_telegram_notifications", return_value="already_sent"
        ), patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=SimpleNamespace(enabled=True, send_purchase_event=Mock()),
        ), patch(
            "orders.tiktok_events_service.get_tiktok_events_service",
            return_value=SimpleNamespace(enabled=False),
        ), patch("orders.email_receipt.send_order_receipt_email", return_value=(False, "no_valid_email")), patch(
            "storefront.utm_tracking.ensure_order_purchase_action"
        ):
            _send_post_payment_events(order.pk, "unpaid", order.pay_type)

        order.refresh_from_db()
        self.assertEqual(
            order.payment_payload["post_payment_channels"]["meta_purchase"]["event_id"],
            "capi-event-already-42",
        )

    def test_purchase_event_time_is_saved_before_failed_provider_attempt(self):
        order = self._paid_order()
        with patch(
            "storefront.views.utils.deliver_pending_order_telegram_notifications", return_value="sent"
        ), patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=SimpleNamespace(enabled=True, send_purchase_event=Mock(return_value=False)),
        ), patch(
            "orders.tiktok_events_service.get_tiktok_events_service",
            return_value=SimpleNamespace(enabled=False),
        ), patch("orders.email_receipt.send_order_receipt_email", return_value=(False, "no_valid_email")), patch(
            "storefront.utm_tracking.ensure_order_purchase_action"
        ):
            _send_post_payment_events(order.pk, "unpaid", order.pay_type)

        order.refresh_from_db()
        self.assertIsInstance(order.payment_payload["facebook_events"].get("purchase_event_time"), int)

    def test_dispatcher_records_blank_receipt_email_as_skipped_without_smtp(self):
        order = Order.objects.create(
            full_name="Buyer",
            email="",
            phone="+380501112233",
            city="Київ",
            np_office="Відділення №1",
            pay_type="online_full",
            payment_status="paid",
            payment_provider="monobank_pay",
            total_sum=Decimal("950.00"),
            payment_payload={"attempt_id": 42},
        )

        with patch(
            "storefront.views.utils.deliver_pending_order_telegram_notifications",
            return_value="sent",
        ), patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service",
            return_value=SimpleNamespace(enabled=False),
        ), patch(
            "orders.tiktok_events_service.get_tiktok_events_service",
            return_value=SimpleNamespace(enabled=False),
        ), patch("orders.email_receipt.EmailMultiAlternatives") as email_cls, patch(
            "storefront.utm_tracking.ensure_order_purchase_action"
        ):
            _send_post_payment_events(order.pk, "unpaid", order.pay_type)

        order.refresh_from_db()
        receipt = order.payment_payload["post_payment_channels"]["receipt_email"]
        self.assertEqual(receipt["state"], "skipped")
        self.assertEqual(receipt["error"], "no_valid_email")
        email_cls.assert_not_called()

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

    def test_valid_receipt_uses_canonical_html_template(self):
        order = Order.objects.create(
            full_name="Buyer", email="buyer@example.com", phone="+380501112233",
            city="Київ", np_office="Відділення №1", pay_type="online_full",
            payment_status="paid", total_sum=Decimal("950.00"), payment_payload={},
        )

        with patch(
            "orders.email_receipt.render_to_string",
            return_value="<html>receipt</html>",
        ) as render:
            built = build_order_receipt_email(order)

        self.assertEqual(render.call_args.args[0], "orders/emails/order_receipt.html")
        self.assertEqual(built["html"], "<html>receipt</html>")

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

    def test_recovery_limit_ignores_older_order_with_terminal_channel_ledger(self):
        now = timezone.now()
        older = Order.objects.create(
            order_number="TWC01082026N01",
            full_name="Completed Buyer",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type="online_full",
            payment_status="paid",
            payment_provider="monobank_pay",
            total_sum=Decimal("950.00"),
            payment_payload={
                "attempt_id": 41,
                "post_payment_channels": {
                    "telegram": {"state": "sent"},
                    "meta_purchase": {"state": "disabled"},
                    "tiktok_purchase": {"state": "unknown"},
                    "receipt_email": {"state": "skipped"},
                    "instagram_lifecycle": {"state": "ambiguous"},
                },
            },
        )
        newer = Order.objects.create(
            order_number="TWC01082026N02",
            full_name="Pending Buyer",
            phone="+380501112234",
            city="Kyiv",
            np_office="Branch 2",
            pay_type="online_full",
            payment_status="paid",
            payment_provider="monobank_pay",
            total_sum=Decimal("950.00"),
            payment_payload={
                "attempt_id": 42,
                "post_payment_channels": {
                    "telegram": {"state": "failed"},
                    "meta_purchase": {"state": "sent"},
                    "tiktok_purchase": {"state": "sent"},
                    "receipt_email": {"state": "skipped"},
                    "instagram_lifecycle": {"state": "sent"},
                },
            },
        )
        Order.objects.filter(pk=older.pk).update(created=now - timedelta(minutes=10))
        Order.objects.filter(pk=newer.pk).update(created=now - timedelta(minutes=5))

        with patch(
            "orders.management.commands.reconcile_order_telegram_notifications._send_post_payment_events"
        ) as dispatch:
            call_command(
                "reconcile_order_telegram_notifications",
                min_age_seconds=0,
                limit=1,
            )

        dispatch.assert_called_once_with(newer.pk, "unpaid", newer.pay_type)

    def test_ig_pending_alone_does_not_replay_post_payment_dispatch(self):
        order = self._paid_order(
            payment_payload={
                "attempt_id": 43,
                "post_payment_channels": {
                    "telegram": {"state": "unknown"},
                    "meta_purchase": {"state": "sent"},
                    "tiktok_purchase": {"state": "disabled"},
                    "receipt_email": {"state": "skipped"},
                    "instagram_lifecycle": {"state": "pending"},
                },
            }
        )

        with patch(
            "orders.management.commands.reconcile_order_telegram_notifications._send_post_payment_events"
        ) as dispatch:
            call_command(
                "reconcile_order_telegram_notifications",
                min_age_seconds=0,
            )

        dispatch.assert_not_called()

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

    def test_receipt_smtp_failure_marks_failed_and_uses_transactional_mailer(self):
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
            return_value={"subject": "Receipt", "text": "Receipt", "html": "<p>Receipt</p>"},
        ), patch("orders.email_receipt.EmailMultiAlternatives") as email_class:
            email_class.return_value.send.side_effect = OSError("SMTP unavailable")
            result = send_order_receipt_email(order)

        self.assertEqual(result, (False, "SMTP unavailable"))
        email_class.return_value.send.assert_called_once_with(using="transactional")
        order.refresh_from_db()
        self.assertEqual(order.payment_payload.get("receipt_email_status"), "failed")
        self.assertIn("SMTP unavailable", order.payment_payload.get("receipt_email_error", ""))
