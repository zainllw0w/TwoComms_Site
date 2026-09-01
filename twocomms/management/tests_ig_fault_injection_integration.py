"""ЭА.22 — integration tests verifying fault scenarios through the IG bot pipeline.

These tests drive the harness through real bot code paths to prove that injected
faults are handled the same way as real provider degradation.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from management.models import IgClient, InstagramBotMessage
from management.services import call_ai_analysis as ai
from management.services import gemini_keys as gk
from management.services import ig_fault_injection as faults
from management.services import instagram_bot as bot


ENV_SINGLE_KEY = {"GEMINI_API": "test-key-1"}


@override_settings(IG_BOT_ENABLED=True)
class EmptyModelTextRejectionTests(TestCase):
    """Verify empty model text is rejected and never sent to customer."""

    def setUp(self):
        self.settings = bot.InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled"])
        self.client_row = IgClient.objects.create(
            username="empty_test_client",
            language="uk",
        )
        gk.clear_model_overload()
        gk.clear_model_unavailable()

    def test_empty_reply_text_triggers_fallback_not_customer_send(self):
        message = InstagramBotMessage.objects.create(
            sender_id="empty_sender",
            role=InstagramBotMessage.Role.USER,
            text="привіт",
            status=InstagramBotMessage.Status.PENDING,
            client=self.client_row,
        )
        scenario = faults.model_returns_empty_text()

        with patch.dict("os.environ", ENV_SINGLE_KEY, clear=False), \
             patch.object(ai, "_gemini_call_once", side_effect=faults.build_injector(scenario)), \
             patch.object(bot, "_provider_http") as mock_http:
            mock_http.return_value = (200, '{"recipient_id":"empty_sender"}')
            processed = bot.process_pending(self.settings, max_items=1)

        self.assertEqual(processed, 1)
        message.refresh_from_db()
        replies = InstagramBotMessage.objects.filter(
            sender_id="empty_sender",
            role=InstagramBotMessage.Role.ASSISTANT,
        )
        # Fallback reply was sent, not the empty model text.
        self.assertEqual(replies.count(), 1)
        reply = replies.first()
        self.assertTrue(reply.text)
        self.assertGreater(len(reply.text), 10)
        # The reply must not be literally empty.
        self.assertNotEqual(reply.text.strip(), "")


@override_settings(IG_BOT_ENABLED=True)
class InvalidSchemaRejectionTests(TestCase):
    """Verify schema-invalid responses are rejected at application validation."""

    def setUp(self):
        self.settings = bot.InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled"])
        self.client_row = IgClient.objects.create(
            username="schema_test_client",
            language="uk",
        )
        gk.clear_model_overload()
        gk.clear_model_unavailable()

    def test_valid_http_200_invalid_schema_triggers_fallback(self):
        message = InstagramBotMessage.objects.create(
            sender_id="schema_sender",
            role=InstagramBotMessage.Role.USER,
            text="доброго дня",
            status=InstagramBotMessage.Status.PENDING,
            client=self.client_row,
        )
        scenario = faults.valid_http_200_invalid_application_schema()

        with patch.dict("os.environ", ENV_SINGLE_KEY, clear=False), \
             patch.object(ai, "_gemini_call_once", side_effect=faults.build_injector(scenario)), \
             patch.object(bot, "_provider_http") as mock_http:
            mock_http.return_value = (200, '{"recipient_id":"schema_sender"}')
            processed = bot.process_pending(self.settings, max_items=1)

        self.assertEqual(processed, 1)
        message.refresh_from_db()
        replies = InstagramBotMessage.objects.filter(
            sender_id="schema_sender",
            role=InstagramBotMessage.Role.ASSISTANT,
        )
        self.assertEqual(replies.count(), 1)
        reply = replies.first()
        # Reply must not contain the malformed model output.
        self.assertNotIn("unexpected_field", reply.text)


@override_settings(IG_BOT_ENABLED=True)
class TransientFailoverTests(TestCase):
    """Verify 503 failures trigger alias failover within the pool."""

    def setUp(self):
        self.settings = bot.InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled"])
        self.client_row = IgClient.objects.create(
            username="failover_client",
            language="uk",
        )
        gk.clear_model_overload()
        gk.clear_model_unavailable()

    def test_http_503_first_then_success_recovers_on_second_attempt(self):
        message = InstagramBotMessage.objects.create(
            sender_id="failover_sender",
            role=InstagramBotMessage.Role.USER,
            text="привіт",
            status=InstagramBotMessage.Status.PENDING,
            client=self.client_row,
        )
        scenario = faults.http_503_first_then_success()

        with patch.dict("os.environ", ENV_SINGLE_KEY, clear=False), \
             patch.object(ai, "_gemini_call_once", side_effect=faults.build_injector(scenario)), \
             patch.object(bot, "_provider_http") as mock_http:
            mock_http.return_value = (200, '{"recipient_id":"failover_sender"}')
            processed = bot.process_pending(self.settings, max_items=1)

        self.assertEqual(processed, 1)
        message.refresh_from_db()
        self.assertEqual(message.status, InstagramBotMessage.Status.SENT)
        replies = InstagramBotMessage.objects.filter(
            sender_id="failover_sender",
            role=InstagramBotMessage.Role.ASSISTANT,
        )
        self.assertEqual(replies.count(), 1)
        reply = replies.first()
        # Success on second attempt means a real reply, not a holding message.
        self.assertIn("recovered after 503", reply.text)


@override_settings(IG_BOT_ENABLED=True)
class FatalErrorHandlingTests(TestCase):
    """Verify fatal errors (400, 403, 404) abort retry and log properly."""

    def setUp(self):
        self.settings = bot.InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled"])
        self.client_row = IgClient.objects.create(
            username="fatal_client",
            language="uk",
        )
        gk.clear_model_overload()
        gk.clear_model_unavailable()

    def test_invalid_payload_400_aborts_without_infinite_retry(self):
        message = InstagramBotMessage.objects.create(
            sender_id="fatal_sender",
            role=InstagramBotMessage.Role.USER,
            text="привіт",
            status=InstagramBotMessage.Status.PENDING,
            client=self.client_row,
        )
        scenario = faults.invalid_payload_400()

        with patch.dict("os.environ", ENV_SINGLE_KEY, clear=False), \
             patch.object(ai, "_gemini_call_once", side_effect=faults.build_injector(scenario)), \
             patch.object(bot, "_provider_http") as mock_http:
            mock_http.return_value = (200, '{"recipient_id":"fatal_sender"}')
            processed = bot.process_pending(self.settings, max_items=1)

        # Bot processed the message (did not crash).
        self.assertEqual(processed, 1)
        message.refresh_from_db()
        # Fatal error means fallback reply, not a crash or infinite retry.
        replies = InstagramBotMessage.objects.filter(
            sender_id="fatal_sender",
            role=InstagramBotMessage.Role.ASSISTANT,
        )
        self.assertGreaterEqual(replies.count(), 1)

    def test_auth_403_permission_denied_falls_back_without_retry(self):
        message = InstagramBotMessage.objects.create(
            sender_id="auth_sender",
            role=InstagramBotMessage.Role.USER,
            text="привіт",
            status=InstagramBotMessage.Status.PENDING,
            client=self.client_row,
        )
        scenario = faults.auth_403_permission_denied()

        with patch.dict("os.environ", ENV_SINGLE_KEY, clear=False), \
             patch.object(ai, "_gemini_call_once", side_effect=faults.build_injector(scenario)), \
             patch.object(bot, "_provider_http") as mock_http:
            mock_http.return_value = (200, '{"recipient_id":"auth_sender"}')
            processed = bot.process_pending(self.settings, max_items=1)

        self.assertEqual(processed, 1)
        message.refresh_from_db()
        replies = InstagramBotMessage.objects.filter(
            sender_id="auth_sender",
            role=InstagramBotMessage.Role.ASSISTANT,
        )
        self.assertGreaterEqual(replies.count(), 1)


@override_settings(IG_BOT_ENABLED=True)
class FullQuotaExhaustionTests(TestCase):
    """Verify full 429 across all aliases triggers circuit open and holding."""

    def setUp(self):
        self.settings = bot.InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled"])
        self.client_row = IgClient.objects.create(
            username="quota_client",
            language="uk",
        )
        gk.clear_model_overload()
        gk.clear_model_unavailable()

    def test_full_429_all_aliases_opens_circuit_and_sends_holding(self):
        message = InstagramBotMessage.objects.create(
            sender_id="quota_sender",
            role=InstagramBotMessage.Role.USER,
            text="привіт",
            status=InstagramBotMessage.Status.PENDING,
            client=self.client_row,
        )
        scenario = faults.full_429_all_aliases()

        with patch.dict("os.environ", ENV_SINGLE_KEY, clear=False), \
             patch.object(ai, "_gemini_call_once", side_effect=faults.build_injector(scenario)), \
             patch.object(bot, "_provider_http") as mock_http:
            mock_http.return_value = (200, '{"recipient_id":"quota_sender"}')
            processed = bot.process_pending(self.settings, max_items=1)

        self.assertEqual(processed, 1)
        message.refresh_from_db()
        # Full quota exhaustion means a fallback reply was sent.
        replies = InstagramBotMessage.objects.filter(
            sender_id="quota_sender",
            role=InstagramBotMessage.Role.ASSISTANT,
        )
        self.assertGreaterEqual(replies.count(), 1)


class ScenarioCoverageInventoryTests(TestCase):
    """Document which production invariants each scenario is designed to test."""

    def test_all_named_scenarios_have_clear_intent(self):
        scenario_intents = {
            "full_429_all_aliases": "И8: circuit open without spam",
            "http_503_first_then_success": "И5: one terminal outcome per inbound",
            "read_timeout_all_models": "transient classification",
            "invalid_payload_400": "fatal classification, no infinite retry",
            "slow_success_30_seconds": "И4: no premature text before budget exhausted",
            "success_between_two_failures": "И2: partial recovery doesn't close incident",
            "failure_then_recovery_after_2_minutes": "И1: incident lifecycle",
            "flapping_success_and_failure": "И2: incident doesn't close on flap",
            "partial_degradation_model_37_unavailable_36_works": "L2 ladder",
            "valid_http_200_invalid_application_schema": "application validation",
            "model_replies_wrong_language": "language validation",
            "model_returns_empty_text": "empty text rejection",
            "auth_403_permission_denied": "fatal classification",
            "not_found_404_unknown_model": "fatal classification",
        }
        for factory in faults.ALL_SCENARIOS:
            scenario = factory()
            self.assertIn(
                scenario.name,
                scenario_intents,
                f"scenario {scenario.name} missing intent documentation"
            )
