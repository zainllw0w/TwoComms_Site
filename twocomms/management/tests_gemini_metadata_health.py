import datetime
import json
import time
from io import StringIO
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings

from management.models import GeminiKeyState, GeminiRequestAttempt
from management.services import gemini_metadata_health


UTC = datetime.timezone.utc


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class GeminiMetadataHealthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.now = datetime.datetime(2026, 8, 18, 12, 5, tzinfo=UTC)

    @patch.dict("os.environ", {"GEMINI_API": "secret-value"}, clear=False)
    @patch("management.services.gemini_metadata_health.urlopen")
    def test_primary_metadata_success_skips_secondary_without_post_or_body(self, urlopen):
        response = Mock()
        response.status = 200
        response.read.return_value = json.dumps({
            "supportedGenerationMethods": ["generateContent"],
        }).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response

        result = gemini_metadata_health.check_alias("GEMINI_API", now=self.now)

        self.assertEqual([row["status"] for row in result], ["metadata_ok", "not_needed"])
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertNotIn("secret-value", request.full_url)
        self.assertEqual(request.headers["X-goog-api-key"], "secret-value")
        attempts = list(GeminiRequestAttempt.objects.order_by("id"))
        self.assertEqual([row.role for row in attempts], ["health_metadata", "health_metadata"])
        self.assertEqual([row.outcome for row in attempts], ["succeeded", "skipped"])
        self.assertEqual(attempts[1].failure_kind, "not_needed")
        self.assertEqual(attempts[1].decision, "skipped_primary_ok")

    @patch.dict("os.environ", {"GEMINI_API": "secret-value"}, clear=False)
    @patch("management.services.gemini_metadata_health.urlopen")
    def test_primary_failure_checks_secondary_and_redacts_provider_response(self, urlopen):
        from urllib.error import HTTPError

        error = HTTPError("https://provider.invalid", 429, "secret provider text", {}, None)
        response = Mock()
        response.status = 200
        response.read.return_value = json.dumps({
            "supportedGenerationMethods": ["generateContent"],
        }).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.side_effect = [error, response]

        result = gemini_metadata_health.check_alias("GEMINI_API", now=self.now)

        self.assertEqual([row["status"] for row in result], ["rate_limited", "metadata_ok"])
        self.assertEqual(urlopen.call_count, 2)
        serialized = str(result) + str(list(GeminiRequestAttempt.objects.values()))
        self.assertNotIn("secret-value", serialized)
        self.assertNotIn("secret provider text", serialized)

    @patch.dict("os.environ", {"GEMINI_API": "secret-value"}, clear=False)
    @patch("management.services.gemini_metadata_health.urlopen")
    def test_http_200_without_generate_content_checks_fallback_model(self, urlopen):
        unsupported = Mock()
        unsupported.status = 200
        unsupported.read.return_value = json.dumps({
            "supportedGenerationMethods": ["countTokens"],
        }).encode()
        unsupported.__enter__ = Mock(return_value=unsupported)
        unsupported.__exit__ = Mock(return_value=False)
        supported = Mock()
        supported.status = 200
        supported.read.return_value = json.dumps({
            "supportedGenerationMethods": ["generateContent"],
        }).encode()
        supported.__enter__ = Mock(return_value=supported)
        supported.__exit__ = Mock(return_value=False)
        urlopen.side_effect = [unsupported, supported]

        result = gemini_metadata_health.check_alias("GEMINI_API", now=self.now)

        self.assertEqual(
            [row["status"] for row in result],
            ["unsupported_generation", "metadata_ok"],
        )
        self.assertEqual(urlopen.call_count, 2)

    @patch("management.services.gemini_metadata_health.urlopen")
    def test_provider_http_503_is_distinct_from_transport_failure(self, urlopen):
        import socket
        from urllib.error import HTTPError, URLError

        urlopen.side_effect = HTTPError(
            "https://provider.invalid", 503, "provider unavailable", {}, None
        )
        provider = gemini_metadata_health._check_model(
            "GEMINI_API",
            "secret-value",
            "gemini-3.7-flash",
            "metadata-provider-503",
        )
        urlopen.side_effect = URLError("dns unavailable")
        transport = gemini_metadata_health._check_model(
            "GEMINI_API",
            "secret-value",
            "gemini-3.7-flash",
            "metadata-transport",
        )

        self.assertEqual(provider["status"], "http_5xx")
        self.assertEqual(transport["status"], "transport_error")

        urlopen.side_effect = HTTPError(
            "https://provider.invalid", 408, "request timeout", {}, None
        )
        http_timeout = gemini_metadata_health._check_model(
            "GEMINI_API",
            "secret-value",
            "gemini-3.7-flash",
            "metadata-http-408",
        )
        self.assertEqual(http_timeout["status"], "http_408")

        urlopen.side_effect = URLError(socket.timeout("read timed out"))
        wrapped_timeout = gemini_metadata_health._check_model(
            "GEMINI_API",
            "secret-value",
            "gemini-3.7-flash",
            "metadata-wrapped-timeout",
        )
        self.assertEqual(wrapped_timeout["status"], "timeout")
        self.assertEqual(
            list(
                GeminiRequestAttempt.objects.order_by("id").values_list(
                    "failure_kind", "http_code"
                )
            ),
            [
                ("http_5xx", 503),
                ("transport_error", None),
                ("http_408", 408),
                ("timeout", None),
            ],
        )

    @patch.dict("os.environ", {"GEMINI_API": ""}, clear=True)
    @patch("management.services.gemini_metadata_health.urlopen")
    def test_unconfigured_alias_does_not_call_provider(self, urlopen):
        result = gemini_metadata_health.check_alias("GEMINI_API", now=self.now)
        self.assertEqual([row["status"] for row in result], ["unconfigured", "unconfigured"])
        urlopen.assert_not_called()
        self.assertFalse(GeminiRequestAttempt.objects.exists())

    @patch("management.management.commands.check_ig_gemini_metadata_health.gemini_metadata_health.run_hour")
    def test_hourly_command_is_idempotent_and_heartbeat_supervised(self, run_hour):
        run_hour.return_value = {
            "request_id": "metadata-20260818T12",
            "checked_aliases": 6,
            "configured_aliases": 6,
            "provider_requests": 6,
            "deadline_skipped_models": 0,
        }
        output = StringIO()
        with patch("management.management.commands.check_ig_gemini_metadata_health.task_heartbeat") as heartbeat:
            heartbeat.return_value.__enter__.return_value = None
            call_command("check_ig_gemini_metadata_health", stdout=output)
            call_command("check_ig_gemini_metadata_health", stdout=output)
        self.assertEqual(run_hour.call_count, 1)
        heartbeat.assert_called_once_with("ig_gemini_metadata_health")
        self.assertIn("6 provider requests", output.getvalue())
        self.assertIn("0 deadline skips", output.getvalue())

    def test_read_only_pool_status_does_not_create_state_rows(self):
        from management.services import gemini_keys

        self.assertEqual(GeminiKeyState.objects.count(), 0)
        rows = gemini_keys.pool_status(now=self.now, read_only=True)
        self.assertEqual(len(rows), 6)
        self.assertEqual(GeminiKeyState.objects.count(), 0)

    @patch("management.services.gemini_metadata_health.urlopen")
    def test_deadline_skip_is_not_recorded_as_provider_failure(self, urlopen):
        result = gemini_metadata_health._check_model(
            "GEMINI_API",
            "secret-value",
            "gemini-3.7-flash",
            "metadata-deadline",
            deadline=time.monotonic() - 1,
        )

        self.assertEqual(result["status"], "deadline_skipped")
        urlopen.assert_not_called()
        self.assertFalse(GeminiRequestAttempt.objects.exists())

    @patch("management.services.gemini_metadata_health.check_alias")
    def test_hourly_aliases_use_distinct_request_ids_and_shared_deadline(self, check_alias):
        check_alias.side_effect = [
            [{"status": "metadata_ok"}, {"status": "not_needed"}],
            [{"status": "deadline_skipped"}, {"status": "deadline_skipped"}],
            [{"status": "unconfigured"}, {"status": "unconfigured"}],
            [{"status": "metadata_ok"}, {"status": "not_needed"}],
            [{"status": "metadata_ok"}, {"status": "not_needed"}],
            [{"status": "metadata_ok"}, {"status": "not_needed"}],
        ]
        result = gemini_metadata_health.run_hour(now=self.now)

        self.assertEqual(result["checked_aliases"], 6)
        self.assertEqual(result["configured_aliases"], 5)
        self.assertEqual(result["provider_requests"], 4)
        self.assertEqual(result["deadline_skipped_models"], 2)
        self.assertEqual(check_alias.call_count, 6)
        request_ids = [call.kwargs["request_id"] for call in check_alias.call_args_list]
        self.assertEqual(len(set(request_ids)), 6)
        self.assertTrue(all(call.kwargs["deadline"] > time.monotonic() for call in check_alias.call_args_list))

    def test_hourly_timeout_budget_reserves_headroom_for_every_model_route(self):
        worst_case_seconds = (
            len(gemini_metadata_health.MODELS)
            * len(gemini_metadata_health.gemini_keys.ALL_KEYS)
            * gemini_metadata_health.TIMEOUT_SECONDS
        )

        self.assertLessEqual(
            worst_case_seconds,
            gemini_metadata_health.CHECK_DEADLINE_SECONDS - 5,
        )
