from decimal import Decimal
from http.client import RemoteDisconnected
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, TestCase

from orders.models import Order
from orders.telegram_notifications import TelegramNotifier, _parse_chat_ids


class TelegramResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class TelegramSendMessageRetryTests(SimpleTestCase):
    def make_notifier(self, admin_id="admin-one"):
        return TelegramNotifier(
            bot_token="bot-token-secret",
            admin_id=admin_id,
            chat_id="",
        )

    def test_remote_disconnect_then_success_retries_and_reports_recovery(self):
        post = Mock(
            side_effect=[
                requests.ConnectionError(RemoteDisconnected("remote closed")),
                TelegramResponse(200, {"ok": True, "result": {"message_id": 17}}),
            ]
        )

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ) as sleep, self.assertLogs("orders.telegram_notifications", level="INFO") as logs:
            delivered = self.make_notifier().send_message("private-message")

        self.assertTrue(delivered)
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once()
        self.assertIn("retry_recovered", "\n".join(logs.output))

    def test_tls_disconnect_then_success_retries(self):
        post = Mock(
            side_effect=[
                requests.exceptions.SSLError("tls details must stay private"),
                TelegramResponse(200, {"ok": True, "result": {"message_id": 18}}),
            ]
        )

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ) as sleep:
            delivered = self.make_notifier().send_message("private-message")

        self.assertTrue(delivered)
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once()

    def test_timeout_exhaustion_is_bounded_to_three_attempts(self):
        post = Mock(side_effect=requests.Timeout("timeout details must stay private"))

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ) as sleep, self.assertLogs("orders.telegram_notifications", level="WARNING") as logs:
            delivered = self.make_notifier().send_message("private-message")

        self.assertFalse(delivered)
        self.assertEqual(post.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertIn("retry_exhausted", "\n".join(logs.output))

    def test_http_500_and_429_are_retried(self):
        for retry_status in (500, 429):
            with self.subTest(status=retry_status):
                post = Mock(
                    side_effect=[
                        TelegramResponse(retry_status, {"ok": False}),
                        TelegramResponse(200, {"ok": True, "result": {"message_id": 19}}),
                    ]
                )
                with patch("orders.telegram_notifications.requests.post", post), patch(
                    "time.sleep"
                ) as sleep:
                    delivered = self.make_notifier().send_message("private-message")

                self.assertTrue(delivered)
                self.assertEqual(post.call_count, 2)
                sleep.assert_called_once()

    def test_at_most_once_policy_does_not_retry_ambiguous_transport_failure(self):
        post = Mock(
            side_effect=[
                requests.ConnectionError(RemoteDisconnected("response lost")),
                TelegramResponse(200, {"ok": True, "result": {"message_id": 117}}),
            ]
        )

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ) as sleep, self.assertLogs("orders.telegram_notifications", level="WARNING") as logs:
            report = self.make_notifier().send_message(
                "private-message",
                retry_ambiguous=False,
                return_report=True,
            )

        self.assertEqual(report.outcome, "ambiguous")
        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()
        self.assertIn("ambiguous_delivery", "\n".join(logs.output))

    def test_at_most_once_policy_does_not_retry_http_500(self):
        post = Mock(
            side_effect=[
                TelegramResponse(500, {"ok": False}),
                TelegramResponse(200, {"ok": True, "result": {"message_id": 118}}),
            ]
        )

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ) as sleep, self.assertLogs("orders.telegram_notifications", level="WARNING"):
            report = self.make_notifier().send_message(
                "private-message",
                retry_ambiguous=False,
                return_report=True,
            )

        self.assertEqual(report.outcome, "ambiguous")
        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()

    def test_at_most_once_policy_treats_other_request_errors_as_ambiguous(self):
        post = Mock(
            side_effect=requests.exceptions.ChunkedEncodingError("response body lost")
        )

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ) as sleep, self.assertLogs("orders.telegram_notifications", level="WARNING"):
            report = self.make_notifier().send_message(
                "private-message",
                retry_ambiguous=False,
                return_report=True,
            )

        self.assertEqual(report.outcome, "ambiguous")
        post.assert_called_once()
        sleep.assert_not_called()

    def test_at_most_once_policy_still_retries_explicit_rate_limit(self):
        post = Mock(
            side_effect=[
                TelegramResponse(429, {"ok": False}),
                TelegramResponse(200, {"ok": True, "result": {"message_id": 119}}),
            ]
        )

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ) as sleep:
            report = self.make_notifier().send_message(
                "private-message",
                retry_ambiguous=False,
                return_report=True,
            )

        self.assertEqual(report.outcome, "sent")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once()

    def test_parse_chat_ids_deduplicates_targets_without_reordering(self):
        self.assertEqual(
            _parse_chat_ids("111, 222;111 333,222"),
            ["111", "222", "333"],
        )

    def test_at_most_once_partial_delivery_is_terminally_ambiguous(self):
        post = Mock(
            side_effect=[
                TelegramResponse(
                    200,
                    {"ok": True, "result": {"chat": {"id": 111}, "message_id": 120}},
                ),
                TelegramResponse(400, {"ok": False, "description": "rejected"}),
            ]
        )

        with patch("orders.telegram_notifications.requests.post", post), self.assertLogs(
            "orders.telegram_notifications", level="WARNING"
        ):
            report = self.make_notifier("111,222").send_message(
                "private-message",
                retry_ambiguous=False,
                return_report=True,
            )

        self.assertEqual(report.outcome, "ambiguous")
        self.assertEqual(
            list(report.results),
            [{"chat": {"id": 111}, "message_id": 120}],
        )
        self.assertEqual(post.call_count, 2)

    def test_order_card_outcome_uses_at_most_once_transport_policy(self):
        notifier = self.make_notifier()
        report = SimpleNamespace(outcome="ambiguous", results=())

        with patch.object(notifier, "format_order_message", return_value="order"), patch.object(
            notifier,
            "_build_order_management_reply_markup",
            return_value=None,
        ), patch.object(notifier, "send_message", return_value=report) as send_message:
            outcome = notifier.send_new_order_notification(
                SimpleNamespace(pk=None),
                return_outcome=True,
            )

        self.assertEqual(outcome, "ambiguous")
        send_message.assert_called_once_with(
            "order",
            reply_markup=None,
            retry_ambiguous=False,
            return_report=True,
        )

    def test_order_card_default_path_also_uses_at_most_once_transport_policy(self):
        notifier = self.make_notifier()
        report = SimpleNamespace(
            outcome="sent",
            results=({"chat": {"id": 111}, "message_id": 121},),
        )

        with patch.object(notifier, "format_order_message", return_value="order"), patch.object(
            notifier,
            "_build_order_management_reply_markup",
            return_value=None,
        ), patch.object(notifier, "send_message", return_value=report) as send_message:
            delivered = notifier.send_new_order_notification(SimpleNamespace(pk=None))

        self.assertTrue(delivered)
        send_message.assert_called_once_with(
            "order",
            reply_markup=None,
            retry_ambiguous=False,
            return_report=True,
        )

    def test_payment_alert_outcome_uses_at_most_once_transport_policy(self):
        notifier = self.make_notifier()
        report = SimpleNamespace(outcome="ambiguous", results=())

        with patch.object(
            notifier,
            "format_admin_payment_status_update",
            return_value="payment",
        ), patch.object(notifier, "send_message", return_value=report) as send_message:
            outcome = notifier.send_admin_payment_status_update(
                SimpleNamespace(),
                "unpaid",
                "paid",
                return_outcome=True,
            )

        self.assertEqual(outcome, "ambiguous")
        send_message.assert_called_once_with(
            "payment",
            retry_ambiguous=False,
            return_report=True,
        )

    def test_http_200_ok_false_and_non_429_4xx_are_not_retried(self):
        cases = (
            TelegramResponse(200, {"ok": False, "description": "rejected"}),
            TelegramResponse(400, {"ok": False, "description": "bad request"}),
        )
        for response in cases:
            with self.subTest(status=response.status_code):
                post = Mock(return_value=response)
                with patch("orders.telegram_notifications.requests.post", post), patch(
                    "time.sleep"
                ) as sleep:
                    delivered = self.make_notifier().send_message("private-message")

                self.assertFalse(delivered)
                post.assert_called_once()
                sleep.assert_not_called()
    def test_one_exhausted_target_does_not_block_later_target_success(self):
        post = Mock(
            side_effect=[
                requests.ConnectionError("first target failure"),
                requests.ConnectionError("first target failure"),
                requests.ConnectionError("first target failure"),
                TelegramResponse(200, {"ok": True, "result": {"message_id": 21}}),
            ]
        )

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ), self.assertLogs("orders.telegram_notifications", level="WARNING") as logs:
            delivered = self.make_notifier(
                "admin-one-secret,admin-two-secret"
            ).send_message(
                "private-message-secret",
                reply_markup={"private": "markup-secret"},
            )

        output = "\n".join(logs.output)
        self.assertTrue(delivered)
        self.assertEqual(post.call_count, 4)
        self.assertIn("partial_delivery", output)
        for secret in (
            "bot-token-secret",
            "admin-one-secret",
            "admin-two-secret",
            "private-message-secret",
            "markup-secret",
            "first target failure",
        ):
            self.assertNotIn(secret, output)

    def test_return_results_contains_only_successful_targets(self):
        post = Mock(
            side_effect=[
                TelegramResponse(400, {"ok": False}),
                TelegramResponse(200, {"ok": True, "result": {"message_id": 22}}),
            ]
        )

        with patch("orders.telegram_notifications.requests.post", post), self.assertLogs(
            "orders.telegram_notifications", level="WARNING"
        ):
            results = self.make_notifier("admin-one,admin-two").send_message(
                "private-message", return_results=True
            )

        self.assertEqual(results, [{"message_id": 22}])
        self.assertEqual(post.call_count, 2)

    def test_generic_post_json_remains_single_attempt(self):
        post = Mock(side_effect=requests.ConnectionError("document failure"))

        with patch("orders.telegram_notifications.requests.post", post):
            with self.assertRaises(requests.ConnectionError):
                self.make_notifier()._post_json("sendDocument", data={})

        post.assert_called_once()

    def test_document_tls_disconnect_then_success_retries(self):
        post = Mock(
            side_effect=[
                requests.exceptions.SSLError("document tls details stay private"),
                TelegramResponse(200, {"ok": True, "result": {"message_id": 24}}),
            ]
        )
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.xlsx"
            path.write_bytes(b"xlsx")
            with patch("orders.telegram_notifications.requests.post", post), patch(
                "time.sleep"
            ) as sleep, self.assertLogs("orders.telegram_notifications", level="INFO") as logs:
                delivered = self.make_notifier().send_admin_document(str(path), "report")

        self.assertTrue(delivered)
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once()
        self.assertIn("telegram_send_document retry_recovered", "\n".join(logs.output))

    def test_document_http_rejection_is_not_retried(self):
        post = Mock(return_value=TelegramResponse(400, {"ok": False, "description": "private"}))
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.xlsx"
            path.write_bytes(b"xlsx")
            with patch("orders.telegram_notifications.requests.post", post), patch(
                "time.sleep"
            ) as sleep, self.assertLogs("orders.telegram_notifications", level="WARNING"):
                delivered = self.make_notifier().send_admin_document(str(path), "report")

        self.assertFalse(delivered)
        post.assert_called_once()
        sleep.assert_not_called()

    def test_document_timeout_exhaustion_is_bounded_and_sanitized(self):
        post = Mock(side_effect=requests.Timeout("document timeout secret"))
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "private-report-name.xlsx"
            path.write_bytes(b"xlsx")
            with patch("orders.telegram_notifications.requests.post", post), patch(
                "time.sleep"
            ) as sleep, patch("builtins.print") as print_mock, self.assertLogs(
                "orders.telegram_notifications", level="WARNING"
            ) as logs:
                delivered = self.make_notifier().send_admin_document(
                    str(path), "private report caption"
                )

        output = "\n".join(logs.output)
        self.assertFalse(delivered)
        self.assertEqual(post.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        print_mock.assert_not_called()
        self.assertIn("telegram_send_document retry_exhausted", output)
        for secret in (
            "document timeout secret",
            "private-report-name.xlsx",
            "private report caption",
            "bot-token-secret",
        ):
            self.assertNotIn(secret, output)

    def test_personal_remote_disconnect_then_success_uses_shared_retry(self):
        post = Mock(
            side_effect=[
                requests.ConnectionError(
                    RemoteDisconnected("personal raw exception secret")
                ),
                TelegramResponse(200, {"ok": True, "result": {"message_id": 23}}),
            ]
        )

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ) as sleep, patch("builtins.print") as print_mock, self.assertLogs(
            "orders.telegram_notifications", level="INFO"
        ) as logs:
            delivered = self.make_notifier().send_personal_message(
                "personal-id-secret", "personal-message-secret"
            )

        output = "\n".join(logs.output)
        self.assertTrue(delivered)
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once()
        print_mock.assert_not_called()
        self.assertIn("retry_recovered", output)
        for secret in (
            "personal-id-secret",
            "bot-token-secret",
            "personal-message-secret",
            "personal raw exception secret",
            "api.telegram.org/bot",
        ):
            self.assertNotIn(secret, output)

    def test_personal_http_200_ok_false_is_not_success_or_retried(self):
        post = Mock(
            return_value=TelegramResponse(
                200, {"ok": False, "description": "personal rejection secret"}
            )
        )

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ) as sleep, patch("builtins.print") as print_mock, self.assertLogs(
            "orders.telegram_notifications", level="WARNING"
        ) as logs:
            delivered = self.make_notifier().send_personal_message(
                "personal-id-secret", "personal-message-secret"
            )

        self.assertFalse(delivered)
        post.assert_called_once()
        sleep.assert_not_called()
        print_mock.assert_not_called()
        self.assertNotIn("personal rejection secret", "\n".join(logs.output))

    def test_personal_transient_exhaustion_returns_false_after_three_attempts(self):
        post = Mock(side_effect=requests.Timeout("personal timeout secret"))

        with patch("orders.telegram_notifications.requests.post", post), patch(
            "time.sleep"
        ) as sleep, patch("builtins.print") as print_mock, self.assertLogs(
            "orders.telegram_notifications", level="WARNING"
        ) as logs:
            delivered = self.make_notifier().send_personal_message(
                "personal-id-secret", "personal-message-secret"
            )

        output = "\n".join(logs.output)
        self.assertFalse(delivered)
        self.assertEqual(post.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        print_mock.assert_not_called()
        self.assertIn("retry_exhausted", output)
        self.assertNotIn("personal timeout secret", output)

    def test_personal_missing_configuration_or_target_uses_sanitized_logs(self):
        with patch("builtins.print") as print_mock, self.assertLogs(
            "orders.telegram_notifications", level="WARNING"
        ) as logs:
            without_token = TelegramNotifier(bot_token="", admin_id="admin")
            self.assertFalse(without_token.send_personal_message("personal-id", "message"))
            self.assertFalse(self.make_notifier().send_personal_message("", "message"))

        output = "\n".join(logs.output)
        print_mock.assert_not_called()
        self.assertIn("not_configured", output)
        self.assertIn("invalid_target", output)
        self.assertNotIn("personal-id", output)


class OrderCardDeliveryClaimTests(TestCase):
    def make_notifier(self):
        return TelegramNotifier(
            bot_token="bot-token-secret",
            admin_id="111",
            chat_id="",
        )

    def make_order(self, number):
        return Order.objects.create(
            order_number=number,
            full_name="Direct Buyer",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type="online_full",
            total_sum=Decimal("900.00"),
            discount_amount=Decimal("0.00"),
            payment_status="checking",
            payment_provider="monobank_pay",
            payment_payload={"attempt_id": 101},
        )

    def test_direct_order_card_is_claimed_before_io_and_not_sent_twice(self):
        order = self.make_order("TWC16082026N91")
        notifier = self.make_notifier()

        def assert_claim_before_send(*args, **kwargs):
            order.refresh_from_db()
            notifications = order.payment_payload["telegram_notifications"]
            self.assertTrue(notifications["order_notification_send_started_at"])
            self.assertFalse(notifications["payment_status_update_sent"])
            return SimpleNamespace(outcome="sent", results=())

        with patch.object(notifier, "format_order_message", return_value="order"), patch.object(
            notifier,
            "_build_order_management_reply_markup",
            return_value=None,
        ), patch.object(
            notifier,
            "send_message",
            side_effect=assert_claim_before_send,
        ) as send_message:
            self.assertTrue(notifier.send_new_order_notification(order))
            self.assertTrue(notifier.send_new_order_notification(order))

        send_message.assert_called_once()
        order.refresh_from_db()
        notifications = order.payment_payload["telegram_notifications"]
        self.assertTrue(notifications["order_notification_sent"])
        self.assertIsNone(notifications["order_notification_send_started_at"])

    def test_ambiguous_direct_order_card_is_not_retried(self):
        order = self.make_order("TWC16082026N92")
        notifier = self.make_notifier()
        report = SimpleNamespace(outcome="ambiguous", results=())

        with patch.object(notifier, "format_order_message", return_value="order"), patch.object(
            notifier,
            "_build_order_management_reply_markup",
            return_value=None,
        ), patch.object(notifier, "send_message", return_value=report) as send_message:
            self.assertFalse(notifier.send_new_order_notification(order))
            self.assertFalse(notifier.send_new_order_notification(order))

        send_message.assert_called_once()
        order.refresh_from_db()
        notifications = order.payment_payload["telegram_notifications"]
        self.assertTrue(notifications["order_notification_ambiguous"])
        self.assertFalse(notifications["order_notification_pending"])
