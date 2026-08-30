"""Э-HEDGE: усі ключі найкращої моделі, а не два — і без витрати квоти на перевірки."""
import threading
import time
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from management.models import GeminiRequestAttempt
from management.services import gemini_hedge, gemini_scoreboard


class HedgedWaveTests(TestCase):
    """Перший успіх виграє; решта хвилі не стартує."""

    def _candidates(self, count):
        return [(f"K{index}", f"v{index}", "gemini-3.7-flash") for index in range(1, count + 1)]

    def test_fast_first_key_never_starts_the_second(self):
        """Головна властивість: у нормальному режимі квота не витрачається зайво."""
        called = []

        def call_one(key_name, key_value, model, timeout):
            called.append(key_name)
            return ("ok", {})

        wave = gemini_hedge.run_hedged(
            self._candidates(6),
            call_one=call_one,
            deadline_monotonic=time.monotonic() + 30,
        )

        self.assertIsNotNone(wave.winner)
        self.assertEqual(wave.winner.key_name, "K1")
        self.assertEqual(called, ["K1"], "швидкий ключ мусить виграти сам")
        skipped = [item for item in wave.outcomes if item.skipped_reason]
        self.assertEqual(len(skipped), 5)
        self.assertTrue(all(item.skipped_reason == "winner_found" for item in skipped))

    def test_fast_first_boundary_is_stable_across_fifty_scheduler_runs(self):
        for run in range(50):
            called = []

            def call_one(key_name, key_value, model, timeout):
                called.append(key_name)
                return ("ok", {})

            wave = gemini_hedge.run_hedged(
                self._candidates(6),
                call_one=call_one,
                deadline_monotonic=time.monotonic() + 5,
            )

            self.assertEqual(called, ["K1"], f"scheduler run {run}")
            self.assertEqual(wave.winner.key_name, "K1")
            self.assertTrue(all(
                item.candidate_index == 1
                or item.skipped_reason == "winner_found"
                for item in wave.outcomes
            ))

    def test_recorded_success_wins_if_first_worker_is_preempted_before_publication(self):
        success_recorded = threading.Event()
        allow_first_publish = threading.Event()
        second_gate_blocked = threading.Event()
        called = []
        result = {}

        def call_one(key_name, key_value, model, timeout):
            called.append(key_name)
            return ("ok", {})

        def after_recorded(outcome):
            if outcome.candidate_index == 1 and outcome.succeeded:
                success_recorded.set()
                allow_first_publish.wait(timeout=5)

        def after_gate(index, started):
            if index == 2 and not started:
                second_gate_blocked.set()

        def run():
            result["wave"] = gemini_hedge.run_hedged(
                self._candidates(3),
                call_one=call_one,
                deadline_monotonic=time.monotonic() + 10,
                after_outcome_recorded=after_recorded,
                after_provider_gate=after_gate,
            )

        with patch.object(gemini_hedge, "HEDGE_STAGGER_SECONDS", 0.01):
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            self.assertTrue(success_recorded.wait(timeout=5))
            self.assertTrue(second_gate_blocked.wait(timeout=5))
            self.assertEqual(called, ["K1"])
            allow_first_publish.set()
            thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(result["wave"].winner.key_name, "K1")
        self.assertEqual(called, ["K1"])

    def test_slow_first_key_lets_a_later_key_win(self):
        """Production-сценарій: 3.7 повільна на першому ключі, швидка на іншому."""

        def call_one(key_name, key_value, model, timeout):
            if key_name == "K1":
                time.sleep(2.0)
                raise TimeoutError("read timeout")
            return (f"ok-{key_name}", {})

        with patch.object(gemini_hedge, "HEDGE_STAGGER_SECONDS", 0.2):
            wave = gemini_hedge.run_hedged(
                self._candidates(3),
                call_one=call_one,
                deadline_monotonic=time.monotonic() + 30,
            )

        self.assertIsNotNone(wave.winner)
        self.assertNotEqual(
            wave.winner.key_name, "K1", "переможцем мусить стати інший ключ"
        )
        self.assertLess(wave.elapsed_seconds, 2.0, "не чекаємо повільний ключ до кінця")

    def test_all_keys_are_attempted_when_every_one_fails(self):
        """Саме цього не сталось у production: 4 ключі не пробувались взагалі."""
        called = []

        def call_one(key_name, key_value, model, timeout):
            called.append(key_name)
            raise TimeoutError("read timeout")

        with patch.object(gemini_hedge, "HEDGE_STAGGER_SECONDS", 0.05):
            wave = gemini_hedge.run_hedged(
                self._candidates(6),
                call_one=call_one,
                deadline_monotonic=time.monotonic() + 30,
            )

        self.assertIsNone(wave.winner)
        self.assertEqual(len(called), 6, "усі шість ключів мусять бути спробовані")
        self.assertEqual(len([o for o in wave.outcomes if o.error]), 6)

    def test_model_terminal_failure_aborts_the_whole_wave(self):
        """404 по моделі не зникне від іншого ключа — палити квоту немає сенсу."""
        called = []

        class _ModelGone(Exception):
            pass

        def call_one(key_name, key_value, model, timeout):
            called.append(key_name)
            raise _ModelGone("HTTP 404")

        with patch.object(gemini_hedge, "HEDGE_STAGGER_SECONDS", 0.05):
            wave = gemini_hedge.run_hedged(
                self._candidates(6),
                call_one=call_one,
                deadline_monotonic=time.monotonic() + 30,
                aborts_wave=lambda exc: isinstance(exc, _ModelGone),
            )

        self.assertIsNone(wave.winner)
        self.assertLess(len(called), 6, "хвиля мусить згаснути після термінального відказу")
        self.assertTrue(
            any(o.skipped_reason == "model_terminal" for o in wave.outcomes)
        )

    def test_exhausted_deadline_skips_remaining_candidates(self):
        def call_one(key_name, key_value, model, timeout):
            raise TimeoutError("read timeout")

        wave = gemini_hedge.run_hedged(
            self._candidates(4),
            call_one=call_one,
            deadline_monotonic=time.monotonic() + 1.0,
        )

        self.assertIsNone(wave.winner)
        self.assertTrue(any(o.skipped_reason == "deadline" for o in wave.outcomes))

    def test_empty_candidate_list_is_safe(self):
        wave = gemini_hedge.run_hedged(
            [], call_one=lambda *a: None, deadline_monotonic=time.monotonic() + 5
        )
        self.assertIsNone(wave.winner)
        self.assertEqual(wave.outcomes, [])

    def test_adaptive_stagger_waits_for_a_known_fast_key(self):
        """Якщо ключ зазвичай відповідає за 2 с, другий не стартує через 1.5 с."""
        delay = gemini_hedge._stagger_for("K1", "gemini-3.7-flash", 2000)
        self.assertGreater(delay, gemini_hedge.HEDGE_STAGGER_SECONDS)
        self.assertLessEqual(delay, gemini_hedge.MAX_ADAPTIVE_STAGGER_SECONDS)

    def test_unknown_latency_falls_back_to_the_fixed_stagger(self):
        self.assertEqual(
            gemini_hedge._stagger_for("K1", "gemini-3.7-flash", 0),
            gemini_hedge.HEDGE_STAGGER_SECONDS,
        )


class ScoreboardTests(TestCase):
    """Знання з уже існуючої телеметрії — без жодного тестового запиту."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _attempt(self, key_name, model, outcome, *, failure_kind="", latency_ms=1000):
        return GeminiRequestAttempt.objects.create(
            request_id="r", role="chat", key_name=key_name, model=model,
            outcome=outcome, failure_kind=failure_kind, latency_ms=latency_ms,
        )

    def test_scoreboard_makes_no_provider_call(self):
        """Скорборд не має права витрачати квоту: він тільки читає факти."""
        import management.services.call_ai_analysis as ai

        self._attempt("K1", "gemini-3.7-flash", "succeeded", latency_ms=2000)
        with patch.object(ai, "_gemini_call_once") as call:
            gemini_scoreboard.snapshot("chat", force=True)
        call.assert_not_called()

    def test_successful_key_is_ordered_first(self):
        self._attempt("K1", "gemini-3.7-flash", "failed", failure_kind="quota_429")
        self._attempt("K2", "gemini-3.7-flash", "succeeded", latency_ms=1500)

        ordered = gemini_scoreboard.order_candidates(
            [("K1", "v", "gemini-3.7-flash"), ("K2", "v", "gemini-3.7-flash")]
        )
        self.assertEqual([item[0] for item in ordered], ["K2", "K1"])

    def test_slow_model_does_not_demote_the_key_below_a_quota_failure(self):
        """read_timeout — це повільна МОДЕЛЬ, а не зламаний ключ."""
        self._attempt("K1", "gemini-3.7-flash", "failed", failure_kind="read_timeout")
        self._attempt("K2", "gemini-3.7-flash", "failed", failure_kind="quota_429")

        ordered = gemini_scoreboard.order_candidates(
            [("K2", "v", "gemini-3.7-flash"), ("K1", "v", "gemini-3.7-flash")]
        )
        self.assertEqual(
            [item[0] for item in ordered], ["K1", "K2"],
            "ключ із quota_429 мусить бути нижче за ключ із таймаутом моделі",
        )

    def test_no_candidate_is_ever_dropped(self):
        self._attempt("K1", "gemini-3.7-flash", "failed", failure_kind="quota_429")
        candidates = [
            ("K1", "v", "gemini-3.7-flash"),
            ("K2", "v", "gemini-3.7-flash"),
            ("K3", "v", "gemini-3.7-flash"),
        ]
        ordered = gemini_scoreboard.order_candidates(candidates)
        self.assertEqual(len(ordered), 3)
        self.assertEqual({item[0] for item in ordered}, {"K1", "K2", "K3"})

    def test_faster_key_wins_between_two_healthy_keys(self):
        self._attempt("K1", "gemini-3.7-flash", "succeeded", latency_ms=9000)
        self._attempt("K2", "gemini-3.7-flash", "succeeded", latency_ms=1200)

        ordered = gemini_scoreboard.order_candidates(
            [("K1", "v", "gemini-3.7-flash"), ("K2", "v", "gemini-3.7-flash")]
        )
        self.assertEqual([item[0] for item in ordered], ["K2", "K1"])

    def test_no_telemetry_keeps_the_base_order(self):
        candidates = [("K1", "v", "m"), ("K2", "v", "m")]
        self.assertEqual(
            gemini_scoreboard.order_candidates(candidates), candidates
        )

    def test_model_is_answering_returns_none_without_facts(self):
        self.assertIsNone(gemini_scoreboard.model_is_answering("gemini-3.7-flash"))

    def test_model_is_answering_is_true_after_a_success(self):
        self._attempt("K1", "gemini-3.7-flash", "succeeded", latency_ms=2000)
        gemini_scoreboard.invalidate("chat")
        self.assertTrue(gemini_scoreboard.model_is_answering("gemini-3.7-flash"))

    def test_model_is_answering_is_false_when_every_attempt_failed(self):
        self._attempt("K1", "gemini-3.7-flash", "failed", failure_kind="read_timeout")
        gemini_scoreboard.invalidate("chat")
        self.assertFalse(gemini_scoreboard.model_is_answering("gemini-3.7-flash"))

    def test_healthy_key_count_reflects_distinct_keys(self):
        self._attempt("K1", "gemini-3.7-flash", "succeeded", latency_ms=1000)
        self._attempt("K2", "gemini-3.7-flash", "succeeded", latency_ms=1000)
        self._attempt("K3", "gemini-3.7-flash", "failed", failure_kind="quota_429")
        gemini_scoreboard.invalidate("chat")
        self.assertEqual(gemini_scoreboard.healthy_key_count("gemini-3.7-flash"), 2)

    def test_not_attempted_rows_are_ignored(self):
        self._attempt("K1", "gemini-3.7-flash", "not_attempted")
        gemini_scoreboard.invalidate("chat")
        self.assertIsNone(gemini_scoreboard.model_is_answering("gemini-3.7-flash"))

    def test_snapshot_is_cached_between_calls(self):
        self._attempt("K1", "gemini-3.7-flash", "succeeded", latency_ms=2000)
        gemini_scoreboard.invalidate("chat")
        first = gemini_scoreboard.snapshot("chat")
        self._attempt("K2", "gemini-3.7-flash", "succeeded", latency_ms=2000)
        second = gemini_scoreboard.snapshot("chat")
        self.assertEqual(
            set(first), set(second), "гарячий хід не має платити за новий запит"
        )

    def test_expected_latency_is_reported_for_a_known_pair(self):
        self._attempt("K1", "gemini-3.7-flash", "succeeded", latency_ms=3400)
        gemini_scoreboard.invalidate("chat")
        self.assertEqual(
            gemini_scoreboard.expected_latency_ms("K1", "gemini-3.7-flash"), 3400
        )

    def test_expected_latency_is_zero_for_an_unknown_pair(self):
        self.assertEqual(
            gemini_scoreboard.expected_latency_ms("NOPE", "gemini-3.7-flash"), 0
        )
