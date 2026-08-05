import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from management.services import instagram_bot as bot


class SenderActionTests(SimpleTestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            page_id="legacy-page",
            ig_user_id="17841400000000001",
        )

    @patch("management.services.instagram_bot.log")
    @patch(
        "management.services.instagram_bot.get_page_token",
        return_value="provider-token",
    )
    @patch(
        "management.services.instagram_bot._provider_account_id",
        return_value="17841400000000001",
    )
    @patch(
        "management.services.instagram_bot.provider_transport",
        return_value=bot.INSTAGRAM_LOGIN_TRANSPORT,
    )
    @patch(
        "management.services.instagram_bot._provider_http",
        return_value=(200, '{"ok":true}'),
    )
    def test_success_uses_active_provider_url_and_returns_typed_result(
        self, provider_http, _transport, _account, _token, action_log
    ):
        result = bot.send_sender_action(self.settings, "customer-123", "typing_on")

        self.assertIsInstance(result, bot.SenderActionResult)
        self.assertTrue(result.ok)
        self.assertEqual(result.http_status, 200)
        self.assertEqual(result.kind, "delivered")
        self.assertEqual(result.action, "typing_on")
        self.assertEqual(
            provider_http.call_args.args[1],
            "https://graph.instagram.com/v25.0/17841400000000001/messages",
        )
        action_log.assert_not_called()

    @patch("management.services.instagram_bot.log")
    @patch(
        "management.services.instagram_bot.get_page_token",
        return_value="provider-token",
    )
    @patch(
        "management.services.instagram_bot._provider_account_id",
        return_value="page-123",
    )
    @patch(
        "management.services.instagram_bot.provider_transport",
        return_value=bot.LEGACY_PAGE_TRANSPORT,
    )
    @patch(
        "management.services.instagram_bot._provider_http",
        return_value=(
            400,
            json.dumps(
                {"error": {"message": "raw-provider-body customer-123"}}
            ),
        ),
    )
    def test_provider_failure_returns_typed_result_and_redacts_diagnostics(
        self, provider_http, _transport, _account, _token, action_log
    ):
        result = bot.send_sender_action(self.settings, "customer-123", "typing_off")

        self.assertIsInstance(result, bot.SenderActionResult)
        self.assertFalse(result.ok)
        self.assertEqual(result.http_status, 400)
        self.assertEqual(result.kind, "provider")
        self.assertEqual(result.action, "typing_off")
        self.assertEqual(provider_http.call_count, 1)
        diagnostics = " ".join(str(call) for call in action_log.call_args_list)
        self.assertIn("typing_off", diagnostics)
        self.assertNotIn("customer-123", diagnostics)
        self.assertNotIn("raw-provider-body", diagnostics)
        self.assertNotIn("provider-token", diagnostics)

    @patch("management.services.instagram_bot.log")
    @patch(
        "management.services.instagram_bot.get_page_token",
        return_value="provider-token",
    )
    @patch(
        "management.services.instagram_bot._provider_account_id",
        return_value="page-123",
    )
    @patch(
        "management.services.instagram_bot._provider_http",
        return_value=(-1, "timeout customer-123"),
    )
    def test_transport_failure_is_best_effort_and_redacted(
        self, provider_http, _account, _token, action_log
    ):
        result = bot.send_sender_action(self.settings, "customer-123", "mark_seen")

        self.assertIsInstance(result, bot.SenderActionResult)
        self.assertFalse(result.ok)
        self.assertEqual(result.http_status, -1)
        self.assertEqual(result.kind, "transport")
        self.assertEqual(result.action, "mark_seen")
        self.assertEqual(provider_http.call_count, 1)
        diagnostics = " ".join(str(call) for call in action_log.call_args_list)
        self.assertNotIn("customer-123", diagnostics)
        self.assertNotIn("timeout", diagnostics)
