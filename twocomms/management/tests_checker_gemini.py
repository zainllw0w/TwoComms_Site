from unittest.mock import patch

from django.test import TestCase

from management.models import GeminiRequestAttempt
from management.services import call_ai_analysis as caa
from management.services import gemini_hedge
from management.services import gemini_keys as gk

ENV6 = {f"GEMINI_API{n}": f"key-val-{n or '1'}" for n in ("", "2", "3", "4", "5", "6")}


class GeminiGroundedPoolTests(TestCase):
    def setUp(self):
        gk.clear_model_overload()

    def test_grounded_skips_gen3_and_uses_25_flash(self):
        """grounded на gen-3 → 429 (не free) → model_skip, успіх на 2.5-flash, ключ НЕ в кулдауні."""
        def fake(model, payload, key, *, parse=True, timeout=None):
            if model == "gemini-2.5-flash":
                return ({"overall_score": 80}, {"totalTokenCount": 50})
            raise caa._Gemini429("quota plan and billing")

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            out = caa.gemini_generate_grounded("SYS", "USER")

        self.assertEqual(out["parsed"], {"overall_score": 80})
        self.assertEqual(out["model"], "gemini-2.5-flash")
        # Ключ checker-пулу НЕ повинен піти в кулдаун через grounding-429 на gen-3.
        self.assertTrue(gk.is_available("GEMINI_API5"))

    def test_grounded_payload_has_google_search_no_json_mime(self):
        captured = {}

        def fake(model, payload, key, *, parse=True, timeout=None):
            captured["payload"] = payload
            return ({"ok": True}, {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            caa.gemini_generate_grounded("SYS", "USER")

        self.assertEqual(captured["payload"]["tools"], [{"google_search": {}}])
        self.assertNotIn("responseMimeType", captured["payload"]["generationConfig"])

    def test_manual_key_tried_first(self):
        seen_keys = []

        def fake(model, payload, key, *, parse=True, timeout=None):
            seen_keys.append(key)
            if model == "gemini-2.5-flash":
                return ({"x": 1}, {})
            raise caa._Gemini429("billing")

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            out = caa.gemini_generate_grounded("S", "U", api_key="manual-key")

        self.assertEqual(out["parsed"], {"x": 1})
        self.assertEqual(seen_keys[0], "manual-key")
        self.assertEqual(out["meta"]["key"], "(manual)")

    def test_400_raises(self):
        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=caa._GeminiFatal("HTTP 400")):
            with self.assertRaises(caa.CallAIAnalysisError):
                caa.gemini_generate_grounded("S", "U")


class GeminiJsonPoolTests(TestCase):
    def setUp(self):
        gk.clear_model_overload()

    def test_free_model_429_cools_the_pair_key_model_not_the_whole_key(self):
        """ЭБ.2: 429 по дневной квоте закрывает пару (ключ, модель), а не ключ.

        Прежняя формулировка теста — «429 на free-модели = исчерпана квота
        ПРОЕКТА → кулдаун ключа» — была неверна: у Google лимиты free-tier
        объявлены на модель в проекте. Из-за кулдауна ключа целиком 429 по самой
        дефицитной модели (3.7-flash) выбивал ключ вместе с 3.6, 3.5 и lite, у
        которых лимит в разы больше. Шесть ключей исчерпывались за день по
        худшей модели, и живой ответ оставался без ключа.
        """
        # Первый ключ фонового пула после ЭБ.2 — API6 (фон идёт навстречу чату).
        def fake(model, payload, key, *, parse=True, timeout=None):
            if key == "key-val-6":
                raise caa._Gemini429("PerDay quota exceeded, check your plan and billing")
            return ({"ok": True}, {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            out = caa.gemini_generate_json("SYS", "USER", role="management")

        self.assertEqual(out["parsed"], {"ok": True})
        self.assertEqual(out["meta"]["key"], "GEMINI_API5")
        exhausted_model = gk.task_model_chain("management", "reporting_summary")[0]
        self.assertFalse(
            gk.is_available("GEMINI_API6", model=exhausted_model),
            "пара (ключ, исчерпанная модель) должна быть в кулдауне",
        )
        self.assertTrue(
            gk.is_available("GEMINI_API6"),
            "сам ключ остаётся рабочим: у младших моделей своя квота",
        )
        self.assertTrue(
            gk.is_available(
                "GEMINI_API6",
                model=gk.task_model_chain("management", "reporting_summary")[-1],
            ),
            "младшая модель на том же ключе обязана остаться доступной",
        )
        self.assertTrue(gk.is_available("GEMINI_API5", model=exhausted_model))

    def test_503_falls_back_to_next_model_same_key(self):
        failed_model = gk.task_model_chain("management", "reporting_summary")[0]

        def fake(model, payload, key, *, parse=True, timeout=None):
            if model == failed_model:
                raise caa._GeminiTransient("HTTP 503")
            return ({"ok": True}, {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake), \
             patch("management.services.call_ai_analysis.time.sleep", return_value=None):
            out = caa.gemini_generate_json("S", "U", role="management")

        self.assertEqual(out["parsed"], {"ok": True})
        self.assertNotEqual(out["model"], failed_model)
        self.assertTrue(gk.is_model_overloaded(failed_model))
        gk.clear_model_overload()

    def test_all_exhausted_raises(self):
        def fake(model, payload, key, *, parse=True, timeout=None):
            raise caa._Gemini429("PerDay quota plan and billing")

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            with self.assertRaises(caa.CallAIAnalysisError):
                caa.gemini_generate_json("S", "U", role="management")


class GeminiTextPoolTests(TestCase):
    def setUp(self):
        gk.clear_model_overload()

    def test_text_mode_returns_raw_text(self):
        def fake(model, payload, key, *, parse=True, timeout=None):
            assert parse is False
            return ("Привіт! Чим допомогти?", {"totalTokenCount": 12})

        payload = {"contents": [{"role": "user", "parts": [{"text": "хай"}]}],
                   "generationConfig": {"temperature": 0.6, "maxOutputTokens": 700}}
        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            out = caa.gemini_generate_text(payload, role="chat")
        self.assertEqual(out["parsed"], "Привіт! Чим допомогти?")

    def test_chat_role_starts_with_chat_keys(self):
        seen = []

        def fake(model, payload, key, *, parse=True, timeout=None):
            seen.append((key, model))
            return ("ok-text", {})

        payload = {"contents": [{"role": "user", "parts": [{"text": "хай"}]}]}
        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            caa.gemini_generate_text(payload, role="chat")
        # ЭБ.4: первый ключ chat-пула тот же, а модель — модель тира задачи.
        # Обычный ответ живёт на lite (500 запросов в сутки на ключ), потому что
        # на 3.7 их всего 20 и они нужны решениям, а не каждой реплике.
        self.assertEqual(
            seen[0], ("key-val-1", gk.task_model_chain("chat", "customer_chat")[0])
        )

    def test_chat_manual_key_first(self):
        seen = []

        def fake(model, payload, key, *, parse=True, timeout=None):
            seen.append(key)
            return ("ok", {})

        payload = {"contents": [{"role": "user", "parts": [{"text": "хай"}]}]}
        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            caa.gemini_generate_text(payload, role="chat", manual_key="bot-custom")
        self.assertEqual(seen[0], "bot-custom")

    def test_chat_borrows_reserve_on_37_when_own_exhausted(self):
        """Коли own-ключі чату (API, API2) у денному кулдауні — чат бере резерв
        усіх доступних ключів (починаючи з API3) на тій самій моделі 3.7-flash. Це пріоритет спілкування."""
        from django.utils import timezone
        now = timezone.now()
        gk.mark_429("GEMINI_API", "day", 0, now=now)
        gk.mark_429("GEMINI_API2", "day", 0, now=now)
        seen = []

        def fake(model, payload, key, *, parse=True, timeout=None):
            seen.append((key, model))
            return ("ok-text", {})

        payload = {"contents": [{"role": "user", "parts": [{"text": "хай"}]}]}
        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake):
            out = caa.gemini_generate_text(payload, role="chat")
        self.assertEqual(out["parsed"], "ok-text")
        # перший доступний — позичений management-ключ; модель — з тира задачі
        self.assertEqual(
            seen[0], ("key-val-3", gk.task_model_chain("chat", "customer_chat")[0])
        )


class GeminiEmptyResponseTests(TestCase):
    def setUp(self):
        gk.clear_model_overload()

    def test_empty_retries_and_does_not_mark_overloaded(self):
        """Порожня відповідь ретраїться, але НЕ метить модель глобально overloaded."""
        calls = {"n": 0}

        def fake(model, payload, key, *, parse=True, timeout=None):
            calls["n"] += 1
            raise caa._GeminiEmpty("порожня відповідь (finishReason=STOP)")

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake), \
             patch("management.services.call_ai_analysis.time.sleep", return_value=None):
            with self.assertRaises(caa.CallAIAnalysisError):
                caa.gemini_generate_grounded("S", "U")
        # checker attempts=2 → кожна 2.5-flash комбінація пробується двічі.
        self.assertFalse(gk.is_model_overloaded("gemini-2.5-flash"))
        self.assertGreater(calls["n"], 2)  # було кілька ретраїв

    def test_empty_then_success_on_retry(self):
        seq = iter([caa._GeminiEmpty("empty"), ({"overall_score": 70}, {})])

        def fake(model, payload, key, *, parse=True, timeout=None):
            if model != "gemini-2.5-flash":
                raise caa._Gemini429("billing")  # gen-3 grounded не free
            item = next(seq)
            if isinstance(item, Exception):
                raise item
            return item

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake), \
             patch("management.services.call_ai_analysis.time.sleep", return_value=None):
            out = caa.gemini_generate_grounded("S", "U")
        self.assertEqual(out["parsed"], {"overall_score": 70})
        self.assertEqual(out["model"], "gemini-2.5-flash")


class ParseModelJsonTests(TestCase):
    def test_handles_fences_and_trailing_commas(self):
        txt = '```json\n{"a": 1, "b": [1, 2,], "c": {"x": 3,},}\n```'
        out = caa._parse_model_json(txt)
        self.assertEqual(out["a"], 1)
        self.assertEqual(out["b"], [1, 2])
        self.assertEqual(out["c"], {"x": 3})

    def test_extracts_json_with_surrounding_text(self):
        txt = 'Ось результат:\n{"overall_score": 70}\nДжерела: [1] example.com'
        out = caa._parse_model_json(txt)
        self.assertEqual(out["overall_score"], 70)

    def test_unparseable_raises(self):
        with self.assertRaises(caa.CallAIAnalysisError):
            caa._parse_model_json("зовсім не json")


class ChatTimeoutTests(TestCase):
    def setUp(self):
        gk.clear_model_overload()

    def test_chat_uses_short_timeout(self):
        """Чат не повинен висіти на завислій моделі — короткий read-таймаут."""
        captured = {}

        class FakeResp:
            status_code = 200
            text = "ok"

            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": "привіт"}]}}]}

        def fake_post(url, **kw):
            captured["timeout"] = kw.get("timeout")
            return FakeResp()

        with patch.dict("os.environ", ENV6, clear=False), \
             patch("management.services.call_ai_analysis.requests.post", side_effect=fake_post):
            out = caa.gemini_generate_text({"contents": []}, role="chat")
        self.assertEqual(out["parsed"], "привіт")
        self.assertLessEqual(sum(captured["timeout"]), sum(caa.CHAT_TIMEOUT))
        self.assertLess(sum(captured["timeout"]), caa.CHAT_DEADLINE_SECONDS)
        gk.clear_model_overload()

    def test_audio_management_keeps_long_timeout(self):
        """Audio analysis, unlike CRM text analysis, may use the long timeout."""
    def test_management_json_uses_bounded_text_timeout(self):
        """JSON re-analysis must not hold the IG worker on a stalled model."""
        captured = {}

        class FakeResp:
            status_code = 200
            text = "ok"

            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": '{"a":1}'}]}}]}

        def fake_post(url, **kw):
            captured["timeout"] = kw.get("timeout")
            return FakeResp()

        with patch.dict("os.environ", ENV6, clear=False), \
             patch("management.services.call_ai_analysis.requests.post", side_effect=fake_post):
            caa.gemini_generate_json("S", "U", role="management")
        self.assertEqual(captured["timeout"], caa.MANAGEMENT_TEXT_TIMEOUT)
        gk.clear_model_overload()

    def test_audio_management_keeps_long_timeout(self):
        """Audio analysis, unlike CRM text analysis, may use the long timeout."""
        captured = {}

        class FakeResp:
            status_code = 200
            text = "ok"

            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": '{"a":1}'}]}}]}

        def fake_post(url, **kw):
            captured["timeout"] = kw.get("timeout")
            return FakeResp()

        with patch.dict("os.environ", ENV6, clear=False), \
             patch("management.services.call_ai_analysis.requests.post", side_effect=fake_post):
            caa._gemini_analyze(b"audio", "audio/mpeg", "context")
        self.assertEqual(captured["timeout"], caa.GEMINI_TIMEOUT)
        gk.clear_model_overload()

    @patch.object(caa, "_run_with_pool")
    def test_management_text_calls_are_bounded_for_bot_automation(self, mock_pool):
        mock_pool.return_value = {"parsed": "ok"}

        caa.gemini_generate_text({"contents": []}, role="management")

        self.assertEqual(
            mock_pool.call_args.kwargs.get("timeout"),
            caa.MANAGEMENT_TEXT_TIMEOUT,
        )
        self.assertEqual(
            mock_pool.call_args.kwargs.get("deadline_seconds"),
            caa.MANAGEMENT_TEXT_DEADLINE_SECONDS,
        )


class AdaptiveChatPlannerTests(TestCase):
    def setUp(self):
        gk.clear_model_overload()
        gk.clear_model_unavailable()

    def _runner(self):
        runner = getattr(caa, "_run_chat_with_pool", None)
        self.assertTrue(callable(runner), "missing adaptive _run_chat_with_pool")
        return runner

    def test_public_chat_text_api_routes_only_to_adaptive_runner(self):
        with patch.object(caa, "_run_chat_with_pool", create=True) as adaptive, \
             patch.object(caa, "_run_with_pool") as legacy:
            adaptive.return_value = {"parsed": "adaptive"}
            legacy.return_value = {"parsed": "legacy"}

            out = caa.gemini_generate_text(
                {"contents": []}, role="chat", reasoning_task="customer_chat"
            )

        self.assertEqual(out["parsed"], "adaptive")
        adaptive.assert_called_once()
        legacy.assert_not_called()

    def test_fast_auth_failures_rotate_all_six_aliases_on_37(self):
        seen = []
        aliases = {value: name for name, value in ENV6.items()}

        def fake(model, payload, key, *, parse=True, timeout=None):
            seen.append((aliases[key], model))
            raise caa._GeminiFatal("HTTP 401: API_KEY_INVALID")

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake), \
             patch.object(caa.time, "sleep") as sleep:
            with self.assertRaises(caa.CallAIAnalysisError):
                self._runner()({"contents": []}, reasoning_task="customer_chat")

        # ЭБ.4: модель обычного ответа определяет тир задачи, а не константа в
        # тесте. Проверяемое свойство прежнее: все шесть ключей ПЕРВОЙ модели.
        primary_model = gk.task_model_chain("chat", "customer_chat")[0]
        primary = [alias for alias, model in seen if model == primary_model]
        self.assertEqual(primary, list(ENV6))
        sleep.assert_not_called()

    def test_slow_transients_are_bounded_before_degrading_the_model(self):
        """A slow model gets two calls; unstarted projects stay durable."""
        seen = []

        chain = gk.task_model_chain("chat", "customer_chat")
        primary_model, fallback_model = chain[0], chain[1]

        def fake(model, payload, key, *, parse=True, timeout=None):
            seen.append(model)
            if model == primary_model:
                raise caa._GeminiTransient("timeout/transport/HTTP 503")
            return ("fallback", {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake), \
             patch.object(caa.gemini_hedge, "HEDGE_STAGGER_SECONDS", 0.01), \
             patch.object(caa.time, "sleep") as sleep:
            out = self._runner()({"contents": []}, reasoning_task="customer_chat")

        first_fallback = seen.index(fallback_model)
        primary_calls = seen[:first_fallback].count(primary_model)
        self.assertEqual(out["parsed"], "fallback")
        self.assertEqual(primary_calls, 2)
        self.assertEqual(
            GeminiRequestAttempt.objects.filter(
                model=primary_model,
                outcome="not_attempted",
                not_attempted_reason="sla_model_budget",
            ).count(),
            4,
        )
        sleep.assert_not_called()


class StickyKeyOrderTests(TestCase):
    def test_recent_ok_key_goes_first_within_tier(self):
        from django.utils import timezone
        # API2 успішно відповів нещодавно → у тирі own він має йти першим
        gk.mark_success("GEMINI_API2", now=timezone.now())
        with patch.dict("os.environ", ENV6, clear=False):
            order = [k for k, _, _ in gk.iter_attempts("chat")]
        # перший own-ключ — GEMINI_API2 (sticky), borrow-ключі — після own
        own_keys = [k for k in order if k in ("GEMINI_API", "GEMINI_API2")]
        self.assertEqual(own_keys[0], "GEMINI_API2")


class ChatHedgeDisciplineTests(TestCase):
    """ЭБ.2 — hedging лечит разброс латентности, а не исчерпанную квоту.

    Под квотой волна вредна: 429 приходит за доли секунды, следующий ключ волны
    стартует через 1.5 с и получает тот же отказ. Один ход остужает несколько
    ключей, и следующий клиент начинает с меньшим пулом — ровно тот эффект,
    из-за которого «улучшение» ухудшало доступность.
    """

    def setUp(self):
        gk.clear_model_overload()

    def _payload(self):
        return {
            "contents": [{"role": "user", "parts": [{"text": "хай"}]}],
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": 700},
        }

    def test_quota_pressure_skips_the_hedged_wave(self):
        primary = gk.task_model_chain("chat", "customer_chat")[0]
        gk.mark_429("GEMINI_API", "minute", 60, model=primary)

        def fake(model, payload, key, *, parse=True, timeout=None):
            return ("ok-text", {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake), \
             patch.object(
                 caa.gemini_hedge, "run_hedged", side_effect=AssertionError("волна не должна открываться")
             ):
            out = caa.gemini_generate_text(self._payload(), role="chat")
        self.assertEqual(out["parsed"], "ok-text")

    def test_healthy_pool_does_not_open_the_legacy_wave(self):
        def fake(model, payload, key, *, parse=True, timeout=None):
            return ("ok-text", {})

        with patch.dict("os.environ", ENV6, clear=False), \
             patch.object(caa, "_gemini_call_once", side_effect=fake), \
             patch.object(caa.gemini_hedge, "run_hedged") as run_hedged:
            run_hedged.return_value = gemini_hedge.HedgeWave(
                winner=None, outcomes=[], elapsed_seconds=0.0
            )
            caa.gemini_generate_text(self._payload(), role="chat")

        run_hedged.assert_not_called()
