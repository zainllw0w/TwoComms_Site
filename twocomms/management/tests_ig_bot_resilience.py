"""Стійкість IG-бота: реклейм зависань у processing, дедлайн пулу Gemini,
логування перебору ключів/моделей у консоль бота.
"""
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from management.models import IgClient, InstagramBotMessage
from management.services import instagram_bot as bot
from management.services import call_ai_analysis as ai
from management.services import gemini_keys as gk


ENV6 = {
    f"GEMINI_API{suffix}": f"key-{suffix or '1'}"
    for suffix in ("", "2", "3", "4", "5", "6")
}


def _msg(status, attempts, age_seconds, *, processing_age_seconds=None, client=None):
    m = InstagramBotMessage.objects.create(
        sender_id="rs1", role=InstagramBotMessage.Role.USER, text="привіт",
        status=status, attempts=attempts, client=client,
    )
    updates = {"created_at": timezone.now() - timedelta(seconds=age_seconds)}
    if processing_age_seconds is not None:
        updates["processing_started_at"] = timezone.now() - timedelta(
            seconds=processing_age_seconds
        )
    InstagramBotMessage.objects.filter(id=m.id).update(**updates)
    return m


class ReclaimStaleProcessingTests(TestCase):
    def test_reclaim_uses_strict_processing_age_boundary(self):
        now = timezone.now()
        threshold = bot.STALE_PROCESSING_SECONDS
        at_boundary = _msg(
            InstagramBotMessage.Status.PROCESSING,
            attempts=1,
            age_seconds=threshold,
            processing_age_seconds=threshold,
        )
        past_boundary = _msg(
            InstagramBotMessage.Status.PROCESSING,
            attempts=1,
            age_seconds=threshold + 1,
            processing_age_seconds=threshold + 1,
        )
        InstagramBotMessage.objects.filter(pk=at_boundary.pk).update(
            processing_started_at=now - timedelta(seconds=threshold),
        )
        InstagramBotMessage.objects.filter(pk=past_boundary.pk).update(
            processing_started_at=(
                now - timedelta(seconds=threshold, microseconds=1)
            ),
        )

        with patch.object(bot.timezone, "now", return_value=now):
            self.assertEqual(bot.reclaim_stale_processing(), 1)

        at_boundary.refresh_from_db()
        past_boundary.refresh_from_db()
        self.assertEqual(
            at_boundary.status,
            InstagramBotMessage.Status.PROCESSING,
        )
        self.assertEqual(
            past_boundary.status,
            InstagramBotMessage.Status.PENDING,
        )

    def test_stale_row_after_send_boundary_is_never_requeued(self):
        m = _msg(
            InstagramBotMessage.Status.PROCESSING,
            attempts=1,
            age_seconds=10,
            processing_age_seconds=600,
        )
        InstagramBotMessage.objects.filter(pk=m.pk).update(send_state="sending")

        self.assertEqual(bot.reclaim_stale_processing(), 0)
        m.refresh_from_db()
        self.assertEqual(m.status, InstagramBotMessage.Status.FAILED)
        self.assertEqual(m.send_state, "unknown")

    def test_requeues_stale_processing(self):
        m = _msg(
            InstagramBotMessage.Status.PROCESSING,
            attempts=1,
            age_seconds=10,
            processing_age_seconds=600,
        )
        n = bot.reclaim_stale_processing()
        self.assertEqual(n, 1)
        m.refresh_from_db()
        self.assertEqual(m.status, InstagramBotMessage.Status.PENDING)

    def test_fails_when_attempts_exhausted(self):
        m = _msg(
            InstagramBotMessage.Status.PROCESSING,
            attempts=3,
            age_seconds=10,
            processing_age_seconds=600,
        )
        bot.reclaim_stale_processing()
        m.refresh_from_db()
        self.assertEqual(m.status, InstagramBotMessage.Status.FAILED)

    def test_ignores_fresh_processing(self):
        m = _msg(
            InstagramBotMessage.Status.PROCESSING,
            attempts=1,
            age_seconds=600,
            processing_age_seconds=10,
        )
        bot.reclaim_stale_processing()
        m.refresh_from_db()
        self.assertEqual(m.status, InstagramBotMessage.Status.PROCESSING)

    def test_claim_stamps_processing_start_independently_of_queue_age(self):
        message = InstagramBotMessage.objects.create(
            sender_id="claimed-old-message",
            role=InstagramBotMessage.Role.USER,
            text="привіт",
            status=InstagramBotMessage.Status.PENDING,
        )
        InstagramBotMessage.objects.filter(pk=message.pk).update(
            created_at=timezone.now() - timedelta(minutes=20)
        )

        claimed = bot._claim_next()

        self.assertEqual(claimed.pk, message.pk)
        self.assertIsNotNone(claimed.processing_started_at)
        self.assertEqual(bot.reclaim_stale_processing(), 0)
        message.refresh_from_db()
        self.assertEqual(message.status, InstagramBotMessage.Status.PROCESSING)

    def test_does_not_reclaim_stale_row_while_client_lease_is_active(self):
        client = IgClient.get_or_create_for_sender("stale-with-active-lease")
        client.automation_lease_token = "working"
        client.automation_lease_until = timezone.now() + timedelta(minutes=2)
        client.save(update_fields=[
            "automation_lease_token", "automation_lease_until", "updated_at",
        ])
        message = _msg(
            InstagramBotMessage.Status.PROCESSING,
            attempts=3,
            age_seconds=600,
            processing_age_seconds=600,
            client=client,
        )

        self.assertEqual(bot.reclaim_stale_processing(), 0)
        message.refresh_from_db()
        self.assertEqual(message.status, InstagramBotMessage.Status.PROCESSING)


class ProcessingTimeoutInvariantTests(SimpleTestCase):
    def test_automation_lease_strictly_outlives_reclaim_threshold(self):
        self.assertGreater(
            bot.AUTOMATION_LEASE_TTL.total_seconds(),
            bot.STALE_PROCESSING_SECONDS,
        )

    def test_unsafe_config_is_normalized_to_a_safe_lease(self):
        stale_seconds, lease_seconds = bot._coherent_processing_timeouts(
            stale_seconds=300,
            lease_seconds=300,
        )

        self.assertEqual(stale_seconds, 300)
        self.assertGreater(lease_seconds, stale_seconds)

        stale_seconds, lease_seconds = bot._coherent_processing_timeouts(
            stale_seconds=0,
            lease_seconds=-1,
        )

        self.assertEqual(stale_seconds, 300)
        self.assertEqual(lease_seconds, 360)

        stale_seconds, lease_seconds = bot._coherent_processing_timeouts(
            stale_seconds=10**100,
            lease_seconds=10**100,
        )

        self.assertEqual(stale_seconds, bot.MAX_STALE_PROCESSING_SECONDS)
        self.assertEqual(
            lease_seconds,
            bot.MAX_STALE_PROCESSING_SECONDS
            + bot.AUTOMATION_LEASE_RECLAIM_MARGIN_SECONDS,
        )


class ProcessingClaimOwnershipTests(TestCase):
    def test_stale_worker_cannot_requeue_a_newer_processing_claim(self):
        message = _msg(
            InstagramBotMessage.Status.PROCESSING,
            attempts=1,
            age_seconds=600,
            processing_age_seconds=600,
        )
        stale_worker_row = InstagramBotMessage.objects.get(pk=message.pk)
        newer_claim_at = timezone.now()
        InstagramBotMessage.objects.filter(pk=message.pk).update(
            processing_started_at=newer_claim_at
        )

        self.assertFalse(bot._requeue_for_active_lease(stale_worker_row))

        message.refresh_from_db()
        self.assertEqual(message.status, InstagramBotMessage.Status.PROCESSING)
        self.assertEqual(message.processing_started_at, newer_claim_at)

    def test_process_exception_cannot_requeue_a_newer_processing_claim(self):
        settings = bot.InstagramBotSettings.load()
        settings.is_enabled = True
        settings.save(update_fields=["is_enabled"])
        message = InstagramBotMessage.objects.create(
            sender_id="exception-ownership",
            role=InstagramBotMessage.Role.USER,
            text="привіт",
            status=InstagramBotMessage.Status.PENDING,
        )
        newer_claim_at = timezone.now() + timedelta(seconds=1)

        def lose_claim_then_fail(_settings, claimed_row):
            InstagramBotMessage.objects.filter(pk=claimed_row.pk).update(
                status=InstagramBotMessage.Status.PROCESSING,
                processing_started_at=newer_claim_at,
            )
            raise RuntimeError("simulated stale worker failure")

        with patch.object(bot, "_process_one", side_effect=lose_claim_then_fail):
            self.assertEqual(bot.process_pending(settings, max_items=1), 0)

        message.refresh_from_db()
        self.assertEqual(message.status, InstagramBotMessage.Status.PROCESSING)
        self.assertEqual(message.processing_started_at, newer_claim_at)


class PoolLoggingTests(TestCase):
    @patch("management.services.call_ai_analysis._gemini_call_once")
    def test_log_cb_called_on_success(self, mock_once):
        mock_once.return_value = ("привіт", {})
        lines = []
        out = ai.gemini_generate_text(
            {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
            role="chat", manual_key="K", log_cb=lines.append,
        )
        self.assertEqual(out.get("parsed"), "привіт")
        self.assertTrue(
            any(gk.role_model_chains()["chat"][0] in line for line in lines),
            lines,
        )


class PoolDeadlineTests(SimpleTestCase):
    @patch("management.services.call_ai_analysis._gemini_call_once")
    def test_deadline_zero_aborts_without_calling(self, mock_once):
        mock_once.side_effect = AssertionError("must not be called past deadline")
        with self.assertRaises(ai.CallAIAnalysisError):
            ai._run_with_pool(
                "chat",
                {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
                manual_key="K", deadline_seconds=0,
            )
        mock_once.assert_not_called()


class BackgroundPoolLeaseTests(SimpleTestCase):
    def test_busy_key_is_skipped_and_provider_exception_releases_bounded_lease(self):
        with patch.object(gk, "model_chain", return_value=["gemini-test"]), \
             patch.object(gk, "iter_attempts", return_value=iter([
                 ("GEMINI_API3", "busy-key", "gemini-test"),
                 ("GEMINI_API4", "available-key", "gemini-test"),
             ])), \
             patch.object(gk, "attempts_per_model", return_value=1), \
             patch.object(gk, "max_rounds", return_value=1), \
             patch.object(
                 gk, "acquire_key_lease", side_effect=[None, "lease-token"]
             ) as acquire, \
             patch.object(gk, "release_key_lease", return_value=True) as release, \
             patch.object(ai.time, "monotonic", return_value=10.0), \
             patch.object(
                 ai, "_gemini_call_once",
                 side_effect=ai._GeminiFatal("HTTP 400 INVALID_ARGUMENT"),
             ) as invoke:
            with self.assertRaises(ai.CallAIAnalysisError):
                ai._run_with_pool(
                    "management",
                    {"contents": []},
                    deadline_seconds=5,
                    reasoning_task="conversation_reanalysis",
                )

        self.assertEqual(
            acquire.call_args_list,
            [
                call("GEMINI_API3", role="management"),
                call("GEMINI_API4", role="management"),
            ],
        )
        invoke.assert_called_once()
        self.assertEqual(invoke.call_args.args[2], "available-key")
        effective_timeout = invoke.call_args.kwargs["timeout"]
        self.assertLessEqual(sum(effective_timeout), 5)
        self.assertLess(sum(effective_timeout), gk.KEY_LEASE_SECONDS)
        release.assert_called_once_with("GEMINI_API4", "lease-token")

    def test_retry_releases_lease_before_deadline_clipped_backoff(self):
        events = []
        clock = {"now": 10.0}

        def monotonic():
            return clock["now"]

        def release(key_name, token):
            events.append(("release", key_name, token))
            return True

        def sleep(seconds):
            events.append(("sleep", seconds))
            clock["now"] += seconds

        with patch.object(gk, "model_chain", return_value=["gemini-test"]), \
             patch.object(gk, "iter_attempts", return_value=iter([
                 ("GEMINI_API3", "available-key", "gemini-test"),
             ])), \
             patch.object(gk, "attempts_per_model", return_value=2), \
             patch.object(gk, "max_rounds", return_value=1), \
             patch.object(
                 gk, "acquire_key_lease", return_value="lease-1"
             ), \
             patch.object(gk, "release_key_lease", side_effect=release), \
             patch.object(ai.time, "monotonic", side_effect=monotonic), \
             patch.object(ai.time, "sleep", side_effect=sleep), \
             patch.object(
                 ai, "_gemini_call_once",
                 side_effect=ai._GeminiTransient("timeout: simulated"),
             ) as invoke:
            with self.assertRaisesRegex(ai.CallAIAnalysisError, "дедлайн"):
                ai._run_with_pool(
                    "management",
                    {"contents": []},
                    deadline_seconds=1,
                    reasoning_task="conversation_reanalysis",
                )

        invoke.assert_called_once()
        self.assertEqual(
            events,
            [
                ("release", "GEMINI_API3", "lease-1"),
                ("sleep", 1.0),
            ],
        )


class AdaptiveChatIncidentRegressionTests(TestCase):
    def setUp(self):
        gk.clear_model_overload()
        gk.clear_model_unavailable()

    def _assert_incident_fallback(self, reasoning_task, budget, constant_name):
        runner = getattr(ai, "_run_chat_with_pool", None)
        self.assertTrue(callable(runner), "missing adaptive _run_chat_with_pool")
        self.assertEqual(getattr(ai, constant_name, None), budget)
        aliases = {value: name for name, value in ENV6.items()}
        clock = {"now": 0.0}
        calls = []

        def fake_once(model, payload, key, *, parse=True, timeout=None):
            calls.append((clock["now"], model, aliases[key], timeout))
            if model == "gemini-3.7-flash":
                # ``requests`` may spend the connect timeout and then the read
                # timeout. Model that worst case so the planner cannot protect
                # the fallback reserve by clipping only one tuple component.
                clock["now"] += float(timeout[0]) + float(timeout[1])
                raise ai._GeminiTransient("timeout: simulated incident")
            if aliases[key] != "GEMINI_API4":
                raise ai._GeminiFatal("HTTP 401: API_KEY_INVALID")
            clock["now"] += 1.0
            return ("3.6/API4 recovered", {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(ai.time, "monotonic", side_effect=lambda: clock["now"]), \
             patch.object(ai.time, "sleep") as sleep, \
             patch.object(ai, "_gemini_call_once", side_effect=fake_once):
            out = runner({"contents": []}, reasoning_task=reasoning_task)

        primary = [call for call in calls if call[1] == "gemini-3.7-flash"]
        self.assertEqual(out["parsed"], "3.6/API4 recovered")
        self.assertEqual((calls[-1][1], calls[-1][2]), ("gemini-3.6-flash", "GEMINI_API4"))
        self.assertEqual(len(primary), 2)
        self.assertLess(sum(primary[1][3]), sum(primary[0][3]))
        self.assertLessEqual(clock["now"], budget)
        for started_at, model, _, timeout in calls:
            remaining = budget - started_at
            self.assertGreaterEqual(remaining, 2.0)
            self.assertGreater(timeout[0], 0)
            self.assertGreater(timeout[1], 0)
            self.assertLessEqual(sum(timeout), remaining)
            if model == "gemini-3.7-flash":
                self.assertLessEqual(sum(timeout), remaining - 2.0)
        fallback_started_at = calls[-1][0]
        self.assertGreaterEqual(budget - fallback_started_at, 2.0)
        self.assertEqual(clock["now"] - fallback_started_at, 1.0)
        sleep.assert_not_called()

    def test_ordinary_incident_recovers_within_35_seconds(self):
        self._assert_incident_fallback(
            "customer_chat", 35.0, "CHAT_ORDINARY_DEADLINE_SECONDS"
        )

    def test_complex_incident_recovers_within_45_seconds(self):
        self._assert_incident_fallback(
            "payment_decision", 45.0, "CHAT_COMPLEX_DEADLINE_SECONDS"
        )
