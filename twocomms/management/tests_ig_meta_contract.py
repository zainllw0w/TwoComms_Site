from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from management.services import instagram_bot as bot


class _MemoryCache:
    def __init__(self):
        self.values = {}

    def add(self, key, value, timeout=None):
        if key in self.values:
            return False
        self.values[key] = value
        return True

    def incr(self, key):
        self.values[key] += 1
        return self.values[key]

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value, timeout=None):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


class InstagramMetaContractTests(SimpleTestCase):
    def test_graph_url_builder_is_versioned_and_rejects_external_paths(self):
        self.assertEqual(
            bot._graph_url("/me/accounts", {"fields": "name"}),
            "https://graph.facebook.com/v25.0/me/accounts?fields=name",
        )
        for path in (
            "https://evil.example/v25.0/me",
            "/v24.0/me",
            "/me#fragment",
            "/me?client_secret=leak",
        ):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    bot._graph_url(path)

    @patch("management.services.instagram_bot._http", return_value=(200, "{}"))
    def test_graph_transport_moves_access_token_out_of_url(self, http):
        code, body = bot._graph_http(
            "https://graph.facebook.com/v25.0/me?fields=id&access_token=secret-token",
        )

        self.assertEqual((code, body), (200, "{}"))
        called_url = http.call_args.args[0]
        self.assertNotIn("access_token", called_url)
        self.assertEqual(http.call_args.kwargs["headers"]["Authorization"], "Bearer secret-token")

    @patch("management.services.instagram_bot._http", return_value=(200, "{}"))
    def test_graph_transport_strips_paging_access_token_with_header_token(self, http):
        code, body = bot._graph_http(
            "https://graph.facebook.com/v25.0/page/conversations?after=cursor&access_token=page-secret",
            token="current-page-token",
        )

        self.assertEqual((code, body), (200, "{}"))
        called_url = http.call_args.args[0]
        self.assertIn("after=cursor", called_url)
        self.assertNotIn("access_token", called_url)
        self.assertEqual(
            http.call_args.kwargs["headers"]["Authorization"],
            "Bearer current-page-token",
        )

    @patch("management.services.instagram_bot._http")
    def test_graph_transport_rejects_non_access_token_credentials(self, http):
        code, body = bot._graph_http(
            "https://graph.facebook.com/v25.0/page?client_secret=leak",
            token="current-page-token",
        )

        self.assertEqual((code, body), (-1, "graph_url_policy"))
        http.assert_not_called()

    def test_conversation_paging_accepts_meta_access_token_but_not_other_secrets(self):
        self.assertTrue(
            bot._valid_conversation_page_url(
                f"{bot.GRAPH}/page/conversations?after=cursor&access_token=provider-token"
            )
        )
        self.assertFalse(
            bot._valid_conversation_page_url(
                f"{bot.GRAPH}/page/conversations?after=cursor&client_secret=leak"
            )
        )

    def test_long_lived_token_cache_is_namespaced_by_raw_credential(self):
        fake_cache = _MemoryCache()
        settings = SimpleNamespace()
        with patch.object(bot, "cache", fake_cache), \
             patch.object(bot, "app_secret", return_value="app-secret"), \
             patch.object(
                 bot,
                 "resolve_direct_token",
                 side_effect=["raw-token-a", "raw-token-b"],
             ), \
             patch.object(
                 bot,
                 "_exchange_long_lived",
                 side_effect=["long-lived-a", "long-lived-b"],
             ) as exchange:
            self.assertEqual(bot._effective_user_token(settings), "long-lived-a")
            self.assertEqual(bot._effective_user_token(settings), "long-lived-b")

        self.assertEqual(exchange.call_count, 2)

    def test_page_token_cache_is_namespaced_by_effective_credential(self):
        fake_cache = _MemoryCache()
        settings = SimpleNamespace(page_id="page")
        responses = [
            (200, '{"data":[{"id":"page","access_token":"page-token-a"}]}'),
            (200, '{"data":[{"id":"page","access_token":"page-token-b"}]}'),
        ]
        with patch.object(bot, "cache", fake_cache), \
             patch.object(bot, "app_secret", return_value="app-secret"), \
             patch.object(
                 bot,
                 "_effective_user_token",
                 side_effect=["effective-a", "effective-b"],
             ), \
             patch.object(bot, "_graph_http", side_effect=responses) as graph_http:
            self.assertEqual(bot.get_page_token(settings), "page-token-a")
            self.assertEqual(bot.get_page_token(settings), "page-token-b")

        self.assertEqual(graph_http.call_count, 2)

    @patch("management.services.instagram_bot._graph_http", return_value=(200, '{"access_token":"ll"}'))
    @patch("management.services.instagram_bot.app_secret", return_value="app-secret")
    def test_long_lived_exchange_keeps_credentials_out_of_graph_query(self, _secret, graph_http):
        self.assertEqual(bot._exchange_long_lived("short-token"), "ll")
        called_url = graph_http.call_args.args[0]
        self.assertEqual(called_url, "https://graph.facebook.com/v25.0/oauth/access_token")
        self.assertNotIn("client_secret", called_url)
        self.assertNotIn("fb_exchange_token", called_url)
        body = graph_http.call_args.kwargs["data"].decode("utf-8")
        self.assertIn("client_secret=app-secret", body)
        self.assertIn("fb_exchange_token=short-token", body)

    def test_capability_status_keeps_allowlist_permission_and_delivery_separate(self):
        settings = SimpleNamespace(allowed_senders="123,456", direct_source="env")
        with patch.object(bot, "resolve_direct_token", return_value="token"):
            status = bot.meta_capability_status(settings)

        self.assertEqual(status["local_allowlist"], "restricted")
        self.assertTrue(status["token_configured"])
        self.assertEqual(status["token_permission"], "unknown")
        self.assertEqual(status["account_access"], "unknown")
        self.assertEqual(status["recipient_delivery"], "per_recipient")

    def test_rate_observability_counts_endpoint_classes_without_quota_claims(self):
        self.assertEqual(bot._meta_endpoint_class(f"{bot.GRAPH}/page/conversations"), "conversations")
        self.assertEqual(bot._meta_endpoint_class(f"{bot.GRAPH}/page/messages"), "send")
        self.assertEqual(bot._meta_endpoint_class(f"{bot.GRAPH}/oauth/access_token"), "oauth")
        fake_cache = _MemoryCache()
        with patch.object(bot, "cache", fake_cache):
            bot._record_meta_http_observation("send", 429)
            bot._record_meta_http_observation("conversations", 200, '{"error":{"code":4}}')
            status = bot.meta_rate_limit_status()

        self.assertEqual(status["endpoints"]["send"]["requests"], 1)
        self.assertEqual(status["endpoints"]["send"]["rate_limited"], 1)
        self.assertEqual(status["endpoints"]["conversations"]["requests"], 1)
        self.assertEqual(status["endpoints"]["conversations"]["rate_limited"], 1)
        self.assertTrue(status["degraded"])
        self.assertNotIn("remaining", status)
