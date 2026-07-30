import hashlib
import hmac
import json
import os
import time
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.core.cache import cache

from management.services import instagram_bot as bot


class InstagramLoginTransportTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.settings = SimpleNamespace(
            page_id="legacy-page-id",
            ig_user_id="17841467101471112",
            direct_source=bot.InstagramBotSettings.CredSource.ENV,
            custom_direct_token="",
            last_error="",
        )

    def test_instagram_login_token_selects_new_transport_and_account(self):
        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": "instagram-user-token"},
            clear=True,
        ):
            self.assertEqual(
                bot.resolve_instagram_login_token(),
                "instagram-user-token",
            )
            self.assertEqual(bot.provider_transport(self.settings), "instagram_login")
            self.assertEqual(
                bot._provider_account_id(self.settings),
                "17841467101471112",
            )
            self.assertEqual(
                bot._provider_url(self.settings, "/me", {"fields": "user_id"}),
                "https://graph.instagram.com/v25.0/me?fields=user_id",
            )

    def test_instagram_login_token_never_uses_legacy_page_exchange(self):
        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": "instagram-user-token"},
            clear=True,
        ), patch.object(bot, "_graph_http") as legacy_http:
            self.assertEqual(
                bot.get_page_token(self.settings),
                "instagram-user-token",
            )

        legacy_http.assert_not_called()

    def test_instagram_login_token_refresh_is_cached(self):
        raw_token = "instagram-user-token-refresh-success"
        cache_key = bot._instagram_login_token_cache_key(raw_token)
        cache.delete(cache_key)
        cache.delete(f"{cache_key}:refresh_lock")
        self.addCleanup(cache.delete, cache_key)
        self.addCleanup(cache.delete, f"{cache_key}:refresh_lock")

        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": raw_token},
            clear=True,
        ), patch.object(
            bot,
            "_refresh_instagram_login_token",
            return_value="refreshed-instagram-token",
        ) as refresh:
            self.assertEqual(
                bot.get_page_token(self.settings),
                "refreshed-instagram-token",
            )
            self.assertEqual(
                bot.get_page_token(self.settings),
                "refreshed-instagram-token",
            )

        refresh.assert_called_once_with(raw_token)

    def test_instagram_login_refresh_failure_backs_off_on_raw_token(self):
        raw_token = "instagram-user-token-refresh-failure"
        cache_key = bot._instagram_login_token_cache_key(raw_token)
        cache.delete(cache_key)
        cache.delete(f"{cache_key}:refresh_lock")
        self.addCleanup(cache.delete, cache_key)
        self.addCleanup(cache.delete, f"{cache_key}:refresh_lock")

        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": raw_token},
            clear=True,
        ), patch.object(
            bot,
            "_refresh_instagram_login_token",
            return_value="",
        ) as refresh:
            self.assertEqual(bot.get_page_token(self.settings), raw_token)
            self.assertEqual(bot.get_page_token(self.settings), raw_token)

        refresh.assert_called_once_with(raw_token)

    def test_legacy_credentials_cannot_reactivate_when_new_token_is_missing(self):
        with patch.dict(
            os.environ,
            {"IG_MARKER": "legacy-system-user-token"},
            clear=True,
        ), patch.object(bot, "_graph_http") as legacy_http:
            self.assertEqual(
                bot.provider_transport(self.settings),
                bot.INSTAGRAM_LOGIN_TRANSPORT,
            )
            self.assertEqual(bot.get_page_token(self.settings), "")

        legacy_http.assert_not_called()

    @patch("management.services.instagram_bot._http", return_value=(200, "{}"))
    def test_missing_instagram_account_id_blocks_send_before_http(self, http):
        self.settings.ig_user_id = ""
        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": "instagram-user-token"},
            clear=True,
        ):
            result = bot.send_text(self.settings, "customer-igsid", "Привіт")

        self.assertEqual(
            result,
            (False, "permanent", "missing_provider_account_id"),
        )
        http.assert_not_called()

    def test_conversation_discovery_uses_instagram_account_metadata_without_platform(self):
        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": "instagram-user-token"},
            clear=True,
        ):
            url = bot._conversation_discovery_url(self.settings, "CURSOR")

        self.assertEqual(
            url,
            "https://graph.instagram.com/v25.0/17841467101471112/conversations"
            "?fields=id%2Cparticipants%2Cupdated_time&limit=50&after=CURSOR",
        )
        self.assertNotIn("platform=instagram", url)

    @patch("management.services.instagram_bot._mark_bot_sent")
    @patch("management.services.instagram_bot._clear_client_delivery_error")
    @patch("management.services.instagram_bot._clear_send_error")
    @patch("management.services.instagram_bot._http", return_value=(200, "{}"))
    def test_send_uses_instagram_graph_and_ig_account_id(
        self,
        http,
        _clear_send,
        _clear_client,
        _mark_sent,
    ):
        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": "instagram-user-token"},
            clear=True,
        ):
            result = bot.send_text(self.settings, "customer-igsid", "Привіт")

        self.assertEqual(result, (True, "", ""))
        self.assertEqual(
            http.call_args.args[0],
            "https://graph.instagram.com/v25.0/17841467101471112/messages",
        )
        self.assertEqual(
            http.call_args.kwargs["headers"]["Authorization"],
            "Bearer instagram-user-token",
        )
        payload = json.loads(http.call_args.kwargs["data"])
        self.assertEqual(payload["recipient"]["id"], "customer-igsid")
        self.assertEqual(payload["message"], {"text": "Привіт"})
        self.assertNotIn("messaging_type", payload)

    @patch(
        "management.services.instagram_bot._http",
        return_value=(
            200,
            '{"name":"Customer","username":"customer","profile_pic":"https://img.example/avatar.jpg"}',
        ),
    )
    def test_profile_uses_instagram_graph(self, http):
        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": "instagram-user-token"},
            clear=True,
        ):
            profile = bot.fetch_ig_profile(self.settings, "customer-igsid")

        self.assertEqual(profile["username"], "customer")
        self.assertEqual(
            http.call_args.args[0],
            "https://graph.instagram.com/v25.0/customer-igsid"
            "?fields=name%2Cusername%2Cprofile_pic",
        )

    @patch(
        "management.services.instagram_bot._http",
        return_value=(200, '{"messages":{"data":[]}}'),
    )
    def test_polling_reads_conversation_from_instagram_graph(self, http):
        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": "instagram-user-token"},
            clear=True,
        ):
            result = bot._fetch_polled_conversation(
                self.settings,
                "conversation-id",
                "instagram-user-token",
                cursor_at=None,
                cursor_id="",
                deadline=time.monotonic() + 10,
                request_limit=1,
            )

        self.assertTrue(result["complete"])
        self.assertTrue(
            http.call_args.args[0].startswith(
                "https://graph.instagram.com/v25.0/conversation-id?fields="
            )
        )

    @patch(
        "management.services.instagram_bot._http",
        return_value=(200, '{"success":true}'),
    )
    def test_account_subscription_uses_instagram_graph(self, http):
        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": "instagram-user-token"},
            clear=True,
        ):
            result = bot.ensure_instagram_subscription(self.settings)

        self.assertEqual(result, {"ok": True, "http": 200})
        self.assertEqual(
            http.call_args.args[0],
            "https://graph.instagram.com/v25.0/17841467101471112/subscribed_apps",
        )
        self.assertIn(b"subscribed_fields=messages", http.call_args.kwargs["data"])

    def test_paging_url_must_match_active_instagram_transport(self):
        with patch.dict(
            os.environ,
            {"IG_INSTAGRAM_BOT": "instagram-user-token"},
            clear=True,
        ):
            self.assertTrue(
                bot._valid_provider_conversation_page_url(
                    self.settings,
                    "https://graph.instagram.com/v25.0/conversation-id"
                    "?after=cursor&access_token=provider-token",
                )
            )
            self.assertFalse(
                bot._valid_provider_conversation_page_url(
                    self.settings,
                    "https://graph.facebook.com/v25.0/conversation-id?after=cursor",
                )
            )

    @patch("management.services.instagram_bot._http", return_value=(200, "{}"))
    def test_instagram_graph_strips_paging_token_and_keeps_header_token(self, http):
        code, body = bot._instagram_graph_http(
            "https://graph.instagram.com/v25.0/conversation-id"
            "?after=cursor&access_token=provider-token",
            token="current-instagram-token",
        )

        self.assertEqual((code, body), (200, "{}"))
        called_url = http.call_args.args[0]
        self.assertIn("after=cursor", called_url)
        self.assertNotIn("access_token", called_url)
        self.assertEqual(
            http.call_args.kwargs["headers"]["Authorization"],
            "Bearer current-instagram-token",
        )

    @patch("management.services.instagram_bot._http")
    def test_instagram_graph_rejects_non_token_credentials(self, http):
        code, body = bot._instagram_graph_http(
            "https://graph.instagram.com/v25.0/conversation-id?client_secret=leak",
            token="current-instagram-token",
        )

        self.assertEqual((code, body), (-1, "graph_url_policy"))
        http.assert_not_called()


class InstagramLoginWebhookSecretTests(SimpleTestCase):
    def test_signature_uses_app_secret(self):
        raw = b'{"object":"instagram","entry":[]}'
        digest = hmac.new(b"meta-app-secret", raw, hashlib.sha256).hexdigest()

        with patch.dict(
            os.environ,
            {
                "IG_INSTAGRAM_BOT": "instagram-user-token",
                "IG_APP_SECRET": "meta-app-secret",
            },
            clear=True,
        ):
            self.assertTrue(bot.verify_signature(raw, f"sha256={digest}"))

    def test_access_token_is_never_accepted_as_webhook_secret(self):
        raw = b'{"object":"instagram","entry":[]}'
        digest = hmac.new(b"instagram-user-token", raw, hashlib.sha256).hexdigest()

        with patch.dict(
            os.environ,
            {
                "IG_INSTAGRAM_BOT": "instagram-user-token",
                "IG_APP_SECRET": "meta-app-secret",
            },
            clear=True,
        ):
            self.assertFalse(bot.verify_signature(raw, f"sha256={digest}"))

    def test_instagram_webhook_ignores_parent_and_legacy_secrets(self):
        raw = b'{"object":"instagram","entry":[]}'
        instagram_digest = hmac.new(
            b"instagram-app-secret", raw, hashlib.sha256
        ).hexdigest()
        parent_digest = hmac.new(b"parent-meta-secret", raw, hashlib.sha256).hexdigest()
        legacy_digest = hmac.new(b"legacy-meta-secret", raw, hashlib.sha256).hexdigest()

        with patch.dict(
            os.environ,
            {
                "IG_INSTAGRAM_BOT": "instagram-user-token",
                "IG_APP_SECRET": "instagram-app-secret",
                "META_APP_SECRET": "parent-meta-secret",
                "FACEBOOK_APP_SECRET": "legacy-meta-secret",
            },
            clear=True,
        ):
            self.assertTrue(bot.verify_signature(raw, f"sha256={instagram_digest}"))
            self.assertFalse(bot.verify_signature(raw, f"sha256={parent_digest}"))
            self.assertFalse(bot.verify_signature(raw, f"sha256={legacy_digest}"))

    def test_webhook_secret_does_not_switch_when_access_token_is_missing(self):
        raw = b'{"object":"instagram","entry":[]}'
        instagram_digest = hmac.new(
            b"instagram-app-secret", raw, hashlib.sha256
        ).hexdigest()
        parent_digest = hmac.new(
            b"parent-meta-secret", raw, hashlib.sha256
        ).hexdigest()

        with patch.dict(
            os.environ,
            {
                "IG_APP_SECRET": "instagram-app-secret",
                "META_APP_SECRET": "parent-meta-secret",
            },
            clear=True,
        ):
            self.assertTrue(bot.verify_signature(raw, f"sha256={instagram_digest}"))
            self.assertFalse(bot.verify_signature(raw, f"sha256={parent_digest}"))

    def test_legacy_oauth_uses_parent_meta_secret(self):
        with patch.dict(
            os.environ,
            {
                "IG_PROVIDER_TRANSPORT": "legacy_page",
                "IG_APP_SECRET": "instagram-app-secret",
                "META_APP_SECRET": "parent-meta-secret",
                "FACEBOOK_APP_SECRET": "legacy-meta-secret",
            },
            clear=True,
        ):
            self.assertEqual(bot.facebook_app_secret(), "parent-meta-secret")
