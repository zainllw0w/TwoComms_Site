"""Стійкість IG-бота: реклейм зависань у processing, дедлайн пулу Gemini,
логування перебору ключів/моделей у консоль бота.
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

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
        self.assertTrue(any("gemini-3.5-flash" in ln for ln in lines), lines)


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
            if model == "gemini-3.6-flash":
                clock["now"] += float(timeout[1])
                raise ai._GeminiTransient("timeout: simulated incident")
            if aliases[key] != "GEMINI_API4":
                raise ai._GeminiFatal("HTTP 401: API_KEY_INVALID")
            return ("3.5/API4 recovered", {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(ai.time, "monotonic", side_effect=lambda: clock["now"]), \
             patch.object(ai.time, "sleep") as sleep, \
             patch.object(ai, "_gemini_call_once", side_effect=fake_once):
            out = runner({"contents": []}, reasoning_task=reasoning_task)

        primary = [call for call in calls if call[1] == "gemini-3.6-flash"]
        self.assertEqual(out["parsed"], "3.5/API4 recovered")
        self.assertEqual((calls[-1][1], calls[-1][2]), ("gemini-3.5-flash", "GEMINI_API4"))
        self.assertEqual(len(primary), 2)
        self.assertLess(primary[1][3][1], primary[0][3][1])
        self.assertLessEqual(clock["now"], budget)
        for started_at, _, _, timeout in calls:
            self.assertLessEqual(timeout[1], budget - started_at)
        sleep.assert_not_called()

    def test_ordinary_incident_recovers_within_35_seconds(self):
        self._assert_incident_fallback(
            "customer_chat", 35.0, "CHAT_ORDINARY_DEADLINE_SECONDS"
        )

    def test_complex_incident_recovers_within_45_seconds(self):
        self._assert_incident_fallback(
            "payment_decision", 45.0, "CHAT_COMPLEX_DEADLINE_SECONDS"
        )
