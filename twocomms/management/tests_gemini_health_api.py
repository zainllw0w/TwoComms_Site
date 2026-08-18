import datetime
import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from management.bot_access import META_REVIEWER_GROUP_NAME
from management.models import GeminiKeyState, GeminiRequestAttempt
from management.services import gemini_keys


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class GeminiHealthApiTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="gemini-health-admin", password="secret", is_staff=True
        )
        self.user = get_user_model().objects.create_user(
            username="gemini-health-user", password="secret"
        )
        self.reviewer = get_user_model().objects.create_user(
            username="gemini-health-reviewer", password="secret"
        )
        reviewer_group, _created = Group.objects.get_or_create(
            name=META_REVIEWER_GROUP_NAME
        )
        self.reviewer.groups.add(reviewer_group)
        self.client.force_login(self.staff)

        self.secret_value = "test-gemini-provider-key-never-return"
        self.env_patcher = patch.dict(
            os.environ,
            {key_name: "" for key_name in gemini_keys.ALL_KEYS},
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)
        cache.clear()
        self.addCleanup(cache.clear)

    def _health_url(self):
        return reverse("management_bot_gemini_health_api")

    def _probe_url(self):
        return reverse("management_bot_gemini_health_probe_api")

    def _configure(self, key_name="GEMINI_API"):
        os.environ[key_name] = self.secret_value
        return GeminiKeyState.get(key_name)

    def _post_probe(self, *, key_name="GEMINI_API", model="gemini-3.7-flash"):
        return self.client.post(
            self._probe_url(), {"key_name": key_name, "model": model}
        )

    def test_get_returns_snapshot_and_never_calls_provider(self):
        snapshot = {
            "schema_version": 1,
            "generated_at": "2026-08-18T12:00:00+00:00",
            "window": {"hours": 24},
            "summary": {"configured": 0},
            "fallback": None,
            "keys": [],
        }
        with (
            patch(
                "management.services.gemini_health.build_snapshot",
                return_value=snapshot,
            ) as build_snapshot,
            patch("management.services.gemini_probe.probe_key") as probe_key,
        ):
            response = self.client.get(self._health_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), snapshot)
        build_snapshot.assert_called_once_with()
        probe_key.assert_not_called()

    def test_get_uses_redacted_snapshot_without_configured_key(self):
        self._configure()
        with patch("management.services.gemini_probe.probe_key") as probe_key:
            response = self.client.get(self._health_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["keys"]), 6)
        self.assertNotIn(self.secret_value, response.content.decode())
        probe_key.assert_not_called()

    def test_non_admin_and_meta_reviewer_cannot_read_or_probe(self):
        self._configure()
        with (
            patch("management.services.gemini_health.build_snapshot") as build_snapshot,
            patch("management.services.gemini_probe.probe_key") as probe_key,
        ):
            for user in (self.user, self.reviewer):
                with self.subTest(username=user.username):
                    self.client.force_login(user)
                    self.assertEqual(self.client.get(self._health_url()).status_code, 403)
                    self.assertEqual(self._post_probe().status_code, 403)
        build_snapshot.assert_not_called()
        probe_key.assert_not_called()

    def test_endpoint_http_methods_are_enforced(self):
        self.assertEqual(self.client.post(self._health_url()).status_code, 405)
        self.assertEqual(self.client.get(self._probe_url()).status_code, 405)

    def test_probe_rejects_unknown_values_before_provider_io(self):
        self._configure()
        invalid_requests = (
            {"key_name": "", "model": "gemini-3.7-flash"},
            {"key_name": "GEMINI_API7", "model": "gemini-3.7-flash"},
            {"key_name": " GEMINI_API", "model": "gemini-3.7-flash"},
            {"key_name": "GEMINI_API", "model": ""},
            {"key_name": "GEMINI_API", "model": "gemini-3.5-flash"},
            {"key_name": "GEMINI_API", "model": "gemini-3.7-flash "},
        )
        with patch("management.services.gemini_probe.probe_key") as probe_key:
            for payload in invalid_requests:
                with self.subTest(payload=payload):
                    self.assertEqual(self.client.post(self._probe_url(), payload).status_code, 400)
        probe_key.assert_not_called()
        self.assertFalse(GeminiRequestAttempt.objects.exists())

    def test_probe_rejects_unconfigured_cooldown_and_busy_key(self):
        with patch("management.services.gemini_probe.probe_key") as probe_key:
            self.assertEqual(self._post_probe().status_code, 409)
            state = self._configure()
            state.cooldown_until = timezone.now() + datetime.timedelta(minutes=5)
            state.cooldown_scope = "minute"
            state.save(update_fields=["cooldown_until", "cooldown_scope", "updated_at"])
            self.assertEqual(self._post_probe().status_code, 409)
            state.cooldown_until = None
            state.cooldown_scope = ""
            state.lease_token = "active-customer-lease"
            state.lease_until = timezone.now() + datetime.timedelta(minutes=1)
            state.lease_role = "chat"
            state.save(update_fields=[
                "cooldown_until", "cooldown_scope", "lease_token",
                "lease_until", "lease_role", "updated_at",
            ])
            self.assertEqual(self._post_probe().status_code, 409)
        probe_key.assert_not_called()
        self.assertFalse(GeminiRequestAttempt.objects.exists())

    def test_probe_rejects_cache_lock_contention_before_provider_io(self):
        self._configure()
        with (
            patch("management.bot_views.cache.add", return_value=False),
            patch("management.services.gemini_probe.probe_key") as probe_key,
        ):
            response = self._post_probe()
        self.assertEqual(response.status_code, 409)
        probe_key.assert_not_called()
        self.assertFalse(GeminiRequestAttempt.objects.exists())

    def test_probe_rejects_lease_race_without_provider_io(self):
        self._configure()
        with (
            patch("management.services.gemini_keys.acquire_key_lease", return_value=None),
            patch("management.services.gemini_probe.probe_key") as probe_key,
        ):
            response = self._post_probe()
        self.assertEqual(response.status_code, 409)
        probe_key.assert_not_called()

    def test_probe_rate_limit_is_scoped_to_alias_and_model(self):
        self._configure()
        result = {
            "status": "ok", "http_code": 200, "finish_reason": "STOP",
            "latency_ms": 12, "model": "gemini-3.7-flash",
        }
        with patch("management.services.gemini_probe.probe_key", return_value=result) as probe_key:
            first = self._post_probe()
            repeated = self._post_probe()
            other_model = self._post_probe(model="gemini-3.6-flash")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 429)
        self.assertEqual(other_model.status_code, 200)
        self.assertEqual(probe_key.call_count, 2)

    def test_successful_probe_is_single_bounded_redacted_audit(self):
        state = self._configure()
        state.last_status = "existing-status"
        state.last_error = "existing-error"
        state.requests_today = 7
        state.save(update_fields=["last_status", "last_error", "requests_today", "updated_at"])
        provider_result = {
            "status": "ok", "http_code": 200, "finish_reason": "STOP",
            "thoughts_tokens": 987, "candidates_tokens": 3, "latency_ms": 27,
            "model": "provider-controlled-model", "provider_body": self.secret_value,
            "error": self.secret_value,
        }
        with patch(
            "management.services.gemini_probe.probe_key", return_value=provider_result
        ) as probe_key:
            response = self._post_probe()
        self.assertEqual(response.status_code, 200)
        probe_key.assert_called_once_with("gemini-3.7-flash", self.secret_value, timeout=(5, 20))
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["probe"]["alias"], "API key 1")
        self.assertEqual(payload["probe"]["model"], "gemini-3.7-flash")
        self.assertEqual(payload["probe"]["status"], "ok")
        self.assertEqual(payload["probe"]["http_code"], 200)
        self.assertEqual(payload["probe"]["finish_reason"], "STOP")
        self.assertEqual(payload["probe"]["latency_ms"], 27)
        serialized = json.dumps(payload, sort_keys=True)
        self.assertNotIn(self.secret_value, serialized)
        self.assertNotIn("provider_body", serialized)
        self.assertNotIn("tokens", serialized)

        attempt = GeminiRequestAttempt.objects.get()
        self.assertTrue(attempt.request_id.startswith("health-probe-"))
        self.assertEqual(
            {
                "role": attempt.role, "key_name": attempt.key_name,
                "model": attempt.model, "outcome": attempt.outcome,
                "failure_kind": attempt.failure_kind, "http_code": attempt.http_code,
                "decision": attempt.decision, "error_detail": attempt.error_detail,
                "prompt_tokens": attempt.prompt_tokens,
                "thoughts_tokens": attempt.thoughts_tokens,
                "candidates_tokens": attempt.candidates_tokens,
            },
            {
                "role": "health_probe", "key_name": "GEMINI_API",
                "model": "gemini-3.7-flash", "outcome": "succeeded",
                "failure_kind": "", "http_code": 200,
                "decision": "manual_probe", "error_detail": "",
                "prompt_tokens": 0, "thoughts_tokens": 0, "candidates_tokens": 0,
            },
        )
        state.refresh_from_db()
        self.assertIsNotNone(state.last_probe_at)
        self.assertEqual(state.last_probe_status, "ok")
        self.assertEqual(state.last_probe_model, "gemini-3.7-flash")
        self.assertEqual(state.last_probe_latency_ms, 27)
        self.assertEqual(state.last_probe_finish_reason, "STOP")
        self.assertEqual(state.last_probe_http_code, 200)
        self.assertEqual(state.last_probe_error, "")
        self.assertEqual(state.last_status, "existing-status")
        self.assertEqual(state.last_error, "existing-error")
        self.assertEqual(state.requests_today, 7)
        self.assertEqual(state.lease_token, "")
        self.assertIsNone(state.lease_until)
        self.assertEqual(state.lease_role, "")

    def test_failed_probe_normalizes_untrusted_result_and_does_not_cooldown(self):
        state = self._configure()
        provider_result = {
            "status": self.secret_value, "http_code": 99999,
            "finish_reason": self.secret_value, "latency_ms": 999999999,
            "thoughts_tokens": 123, "raw_error": self.secret_value,
        }
        with patch("management.services.gemini_probe.probe_key", return_value=provider_result):
            response = self._post_probe()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["probe"]["status"], "provider_error")
        self.assertEqual(payload["probe"]["http_code"], 0)
        self.assertEqual(payload["probe"]["finish_reason"], "")
        self.assertEqual(payload["probe"]["latency_ms"], 120000)
        self.assertNotIn(self.secret_value, json.dumps(payload, sort_keys=True))
        attempt = GeminiRequestAttempt.objects.get()
        self.assertEqual(attempt.outcome, "failed")
        self.assertEqual(attempt.failure_kind, "provider_error")
        self.assertEqual(attempt.error_detail, "provider_error")
        self.assertIsNone(attempt.http_code)
        self.assertEqual(attempt.prompt_tokens, 0)
        self.assertEqual(attempt.thoughts_tokens, 0)
        self.assertEqual(attempt.candidates_tokens, 0)
        state.refresh_from_db()
        self.assertEqual(state.last_probe_status, "provider_error")
        self.assertEqual(state.last_probe_error, "provider_error")
        self.assertEqual(state.last_probe_finish_reason, "")
        self.assertEqual(state.last_probe_latency_ms, 120000)
        self.assertIsNone(state.cooldown_until)
        self.assertEqual(state.requests_today, 0)

    def test_unexpected_probe_exception_is_redacted_and_rate_limited(self):
        self._configure()
        with patch(
            "management.services.gemini_probe.probe_key",
            side_effect=RuntimeError(self.secret_value),
        ) as probe_key:
            first = self._post_probe()
            repeated = self._post_probe()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["probe"]["status"], "provider_error")
        self.assertNotIn(self.secret_value, first.content.decode())
        self.assertEqual(repeated.status_code, 429)
        probe_key.assert_called_once()
        self.assertEqual(GeminiRequestAttempt.objects.get().failure_kind, "provider_error")
        state = GeminiKeyState.get("GEMINI_API")
        self.assertEqual(state.lease_token, "")
        self.assertIsNone(state.lease_until)
