import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

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


class TypingWindowTests(SimpleTestCase):
    def setUp(self):
        self.settings = SimpleNamespace(pk=17, is_enabled=True)
        self.row = SimpleNamespace(client_id=23, sender_id="customer-23")
        self.permission = SimpleNamespace(settings_epoch=4, client_epoch=9)

    def test_reply_length_maps_to_small_bounded_target(self):
        short = bot._typing_target_seconds("Hi")
        long = bot._typing_target_seconds("x" * 1000)

        self.assertGreaterEqual(short, bot.TYPING_MIN_VISIBLE_SECONDS)
        self.assertLessEqual(short, bot.TYPING_MAX_VISIBLE_SECONDS)
        self.assertEqual(long, bot.TYPING_MAX_VISIBLE_SECONDS)
        self.assertLess(
            bot._typing_target_seconds("Short answer"),
            bot._typing_target_seconds("A" * 240),
        )

    @patch("management.services.instagram_bot._reply_permission_is_current", return_value=True)
    @patch("management.services.instagram_bot._renew_client_automation_lease", return_value=True)
    @patch("management.services.instagram_bot.time.sleep")
    def test_fast_generation_waits_only_for_remaining_target(
        self, sleep, _renew, _permission
    ):
        target = bot._typing_target_seconds("A concise answer")

        allowed = bot._wait_for_typing_window(
            self.settings,
            self.row,
            "lease-token",
            self.permission,
            "A concise answer",
            typing_started_at=100.0,
            now=100.2,
        )

        self.assertEqual(allowed, "allowed")
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], target - 0.2, places=6)

    @patch("management.services.instagram_bot._reply_permission_is_current", return_value=True)
    @patch("management.services.instagram_bot._renew_client_automation_lease", return_value=True)
    @patch("management.services.instagram_bot.time.sleep")
    def test_slow_generation_does_not_add_wait(
        self, sleep, _renew, _permission
    ):
        allowed = bot._wait_for_typing_window(
            self.settings,
            self.row,
            "lease-token",
            self.permission,
            "A short answer",
            typing_started_at=100.0,
            now=100.0 + bot.TYPING_MAX_VISIBLE_SECONDS + 0.1,
        )

        self.assertEqual(allowed, "allowed")
        sleep.assert_not_called()

    @patch("management.services.instagram_bot.time.sleep")
    def test_failed_typing_on_does_not_add_wait(self, sleep):
        allowed = bot._wait_for_typing_window(
            self.settings,
            self.row,
            "lease-token",
            self.permission,
            "A reply",
            typing_started_at=None,
            now=100.0,
        )

        self.assertEqual(allowed, "allowed")
        sleep.assert_not_called()

    @patch("management.services.instagram_bot._stop_typing_indicator")
    @patch("management.services.instagram_bot.time.sleep")
    @patch("management.services.instagram_bot._renew_client_automation_lease", return_value=False)
    def test_stale_lease_skips_wait_and_stops_typing(
        self, _renew, sleep, stop_typing
    ):
        allowed = bot._wait_for_typing_window(
            self.settings,
            self.row,
            "lease-token",
            self.permission,
            "A reply",
            typing_started_at=100.0,
            now=100.1,
            typing_active=True,
        )

        self.assertEqual(allowed, "lease_lost")
        sleep.assert_not_called()
        stop_typing.assert_called_once_with(self.settings, self.row, True)

    @patch("management.services.instagram_bot._stop_typing_indicator")
    @patch("management.services.instagram_bot.time.sleep")
    @patch(
        "management.services.instagram_bot._reply_permission_is_current",
        side_effect=[True, False],
    )
    @patch("management.services.instagram_bot._renew_client_automation_lease", return_value=True)
    def test_permission_change_during_wait_stops_typing_and_blocks_send(
        self, _renew, _permission, sleep, stop_typing
    ):
        allowed = bot._wait_for_typing_window(
            self.settings,
            self.row,
            "lease-token",
            self.permission,
            "A reply",
            typing_started_at=100.0,
            now=100.1,
            typing_active=True,
        )

        self.assertEqual(allowed, "permission_denied")
        sleep.assert_called_once()
        stop_typing.assert_called_once_with(self.settings, self.row, True)

    def test_typing_off_happens_before_send_callable(self):
        events = []

        def stop_typing(*_args):
            events.append("typing_off")

        def send():
            events.append("send_text")
            return "sent"

        with patch.object(bot, "_stop_typing_indicator", side_effect=stop_typing):
            result = bot._send_with_typing_off(
                self.settings,
                self.row,
                True,
                send,
            )

        self.assertEqual(result, "sent")
        self.assertEqual(events, ["typing_off", "send_text"])

    def test_typing_off_precedes_durable_sending_marker_even_when_action_fails(self):
        events = []

        def stop_typing(_settings, _row, typing_active):
            if typing_active:
                events.append("typing_off")
            return bot.SenderActionResult(False, 503, "provider", "typing_off")

        def mark_sending():
            events.append("send_state_sending")
            return 1

        def send():
            events.append("send_text")
            return "sent"

        with patch.object(bot, "_stop_typing_indicator", side_effect=stop_typing):
            marker = bot._mark_sending_after_typing_off(
                self.settings,
                self.row,
                True,
                mark_sending,
            )
            result = bot._send_with_typing_off(
                self.settings,
                self.row,
                False,
                send,
            )

        self.assertEqual(marker, 1)
        self.assertEqual(result, "sent")
        self.assertEqual(events, ["typing_off", "send_state_sending", "send_text"])


class TypingPermissionTransitionTests(TestCase):
    def setUp(self):
        from django.utils import timezone

        self.settings = bot.InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.ai_enabled = False
        self.settings.trigger_text = "hello"
        self.settings.reply_text = "A reply"
        self.settings.save(update_fields=[
            "is_enabled", "ai_enabled", "trigger_text", "reply_text",
        ])
        self.row = bot.InstagramBotMessage.objects.create(
            sender_id="permission-transition-customer",
            role=bot.InstagramBotMessage.Role.USER,
            text="hello",
            status=bot.InstagramBotMessage.Status.PROCESSING,
            processing_started_at=timezone.now(),
        )

    @patch(
        "management.services.instagram_bot.send_text",
    )
    @patch(
        "management.services.instagram_bot.gemini_generate",
        return_value="A reply",
    )
    @patch(
        "management.services.instagram_bot._reply_permission_is_current",
        side_effect=[True, False],
    )
    @patch("management.services.instagram_bot.time.sleep")
    @patch("management.services.instagram_bot.send_sender_action")
    def test_permission_change_during_typing_wait_finishes_claim_without_send(
        self, sender_action, _sleep, _permission, _gemini, send_text
    ):
        sender_action.side_effect = lambda _settings, _sender_id, action: (
            bot.SenderActionResult(True, 200, "delivered", action)
        )
        self.settings.ai_enabled = True
        self.settings.save(update_fields=["ai_enabled"])

        result = bot._process_one_inside_reply_boundary(
            self.settings,
            self.row,
            lease_token="",
            permission=SimpleNamespace(settings_epoch=1, client_epoch=None),
        )

        self.assertFalse(result)
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, bot.InstagramBotMessage.Status.DONE)
        self.assertIsNotNone(self.row.processed_at)
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    @patch("management.services.instagram_bot._wait_for_typing_window")
    def test_lease_loss_keeps_lease_helpers_requeue_result(self, wait, send_text):
        def lose_lease(*_args, **_kwargs):
            bot._requeue_for_active_lease(self.row)
            return "lease_lost"

        wait.side_effect = lose_lease

        result = bot._process_one_inside_reply_boundary(
            self.settings,
            self.row,
            lease_token="",
            permission=None,
        )

        self.assertFalse(result)
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, bot.InstagramBotMessage.Status.PENDING)
        self.assertIsNone(self.row.processing_started_at)
        send_text.assert_not_called()
