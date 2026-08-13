import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from management.models import GeminiKeyState, LeadCheckerSettings


class GeminiKeyStateModelTests(TestCase):
    def test_get_creates_row(self):
        st = GeminiKeyState.get("GEMINI_API")
        self.assertEqual(st.key_name, "GEMINI_API")
        self.assertIsNone(st.cooldown_until)
        self.assertEqual(st.requests_today, 0)

    def test_get_is_idempotent(self):
        a = GeminiKeyState.get("GEMINI_API2")
        a.requests_today = 5
        a.save()
        b = GeminiKeyState.get("GEMINI_API2")
        self.assertEqual(b.requests_today, 5)
        self.assertEqual(GeminiKeyState.objects.filter(key_name="GEMINI_API2").count(), 1)


class LeadCheckerSettingsAutoRecheckTests(TestCase):
    def test_auto_recheck_defaults(self):
        s = LeadCheckerSettings.load()
        self.assertFalse(s.auto_recheck)
        self.assertEqual(s.auto_recheck_batch, 25)


ENV6 = {f"GEMINI_API{n}": f"key-val-{n}" for n in ("", "2", "3", "4", "5", "6")}


class NextMidnightPTTests(SimpleTestCase):
    def test_returns_future_utc_midnight_pt(self):
        from management.services import gemini_keys as gk
        now = timezone.now()
        nm = gk.next_midnight_pt(now)
        self.assertGreater(nm, now)
        nm_pt = nm.astimezone(gk.PT)
        self.assertEqual((nm_pt.hour, nm_pt.minute, nm_pt.second), (0, 0, 0))


class Parse429Tests(SimpleTestCase):
    def test_topup(self):
        from management.services import gemini_keys as gk
        scope, secs = gk.parse_429('{"error":{"message":"Your prepayment credits are depleted."}}')
        self.assertEqual(scope, "topup")
        self.assertGreater(secs, 0)

    def test_retry_delay_wins_over_perday(self):
        """Реальне free-tier тіло: quotaId PerDay + retryDelay 48s → беремо retryDelay
        (короткий кулдаун), а НЕ до півночі."""
        from management.services import gemini_keys as gk
        body = ('{"error":{"code":429,"message":"You exceeded your current quota... limit: 20",'
                '"details":[{"@type":"...QuotaFailure","violations":[{"quotaId":'
                '"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},'
                '{"@type":"...RetryInfo","retryDelay":"48s"}]}}')
        scope, secs = gk.parse_429(body)
        self.assertEqual(scope, "minute")
        self.assertGreaterEqual(secs, 48)
        self.assertLessEqual(secs, 60)

    def test_long_retry_delay_is_day(self):
        from management.services import gemini_keys as gk
        scope, secs = gk.parse_429('{"error":{"details":[{"@type":"RetryInfo","retryDelay":"40000s"}]}}')
        self.assertEqual(scope, "day")
        self.assertGreater(secs, 3600)

    def test_perday_without_retry_delay_is_midnight(self):
        from management.services import gemini_keys as gk
        body = '{"error":{"message":"quota","details":[{"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}}'
        scope, secs = gk.parse_429(body)
        self.assertEqual(scope, "day")
        self.assertEqual(secs, 0)

    def test_ambiguous_defaults_to_minute_not_day(self):
        from management.services import gemini_keys as gk
        scope, secs = gk.parse_429('{"error":{"message":"check your plan and billing details"}}')
        self.assertEqual(scope, "minute")


class MarkAndAvailabilityTests(TestCase):
    def test_mark_429_day_cooldown_until_midnight_pt(self):
        from management.services import gemini_keys as gk
        now = timezone.now()
        st = gk.mark_429("GEMINI_API", "day", 0, now=now, error="quota")
        self.assertEqual(st.cooldown_scope, "day")
        self.assertEqual(st.cooldown_until, gk.next_midnight_pt(now))
        self.assertFalse(gk.is_available("GEMINI_API", now))

    def test_mark_429_minute_short_cooldown(self):
        from management.services import gemini_keys as gk
        now = timezone.now()
        gk.mark_429("GEMINI_API2", "minute", 40, now=now)
        self.assertFalse(gk.is_available("GEMINI_API2", now))
        self.assertTrue(gk.is_available("GEMINI_API2", now + datetime.timedelta(seconds=41)))

    def test_mark_success_clears_and_counts(self):
        from management.services import gemini_keys as gk
        now = timezone.now()
        gk.mark_429("GEMINI_API3", "day", 0, now=now)
        st = gk.mark_success("GEMINI_API3", now=now)
        self.assertIsNone(st.cooldown_until)
        self.assertEqual(st.requests_today, 1)
        self.assertTrue(gk.is_available("GEMINI_API3", now))

    @override_settings(GEMINI_KEY_PROJECT_GROUPS={
        "GEMINI_API": "project-chat",
        "GEMINI_API2": "project-chat",
        "GEMINI_API3": "project-management",
    })
    def test_429_cools_every_alias_in_the_same_known_project(self):
        from management.services import gemini_keys as gk
        now = timezone.now()

        gk.mark_429("GEMINI_API", "minute", 40, now=now)

        self.assertFalse(gk.is_available("GEMINI_API", now))
        self.assertFalse(gk.is_available("GEMINI_API2", now))
        self.assertTrue(gk.is_available("GEMINI_API3", now))

    @override_settings(GEMINI_KEY_PROJECT_GROUPS={})
    def test_unknown_project_identity_does_not_guess_alias_relationship(self):
        from management.services import gemini_keys as gk
        now = timezone.now()

        gk.mark_429("GEMINI_API", "minute", 40, now=now)

        self.assertFalse(gk.is_available("GEMINI_API", now))
        self.assertTrue(gk.is_available("GEMINI_API2", now))

    @override_settings(GEMINI_KEY_PROJECT_GROUPS={
        "GEMINI_API": "project-chat",
        "GEMINI_API2": "project-chat",
    })
    def test_success_cannot_clear_active_sibling_project_cooldown(self):
        from management.services import gemini_keys as gk

        now = timezone.now()
        gk.mark_429("GEMINI_API", "minute", 60, now=now)

        state = gk.mark_success(
            "GEMINI_API2",
            now=now + datetime.timedelta(seconds=1),
        )

        self.assertEqual(state.last_status, "ok:project_cooldown")
        self.assertFalse(gk.is_available("GEMINI_API", now + datetime.timedelta(seconds=1)))
        self.assertFalse(gk.is_available("GEMINI_API2", now + datetime.timedelta(seconds=1)))


class ModelOverloadTests(SimpleTestCase):
    def test_overload_cache(self):
        from management.services import gemini_keys as gk
        gk.clear_model_overload()
        now = timezone.now()
        self.assertFalse(gk.is_model_overloaded("gemini-3.5-flash", now))
        gk.mark_model_overloaded("gemini-3.5-flash", seconds=300, now=now)
        self.assertTrue(gk.is_model_overloaded("gemini-3.5-flash", now))
        self.assertFalse(gk.is_model_overloaded("gemini-3.5-flash", now + datetime.timedelta(seconds=301)))
        gk.clear_model_overload()


class IterAttemptsTests(TestCase):
    def setUp(self):
        from management.services import gemini_keys as gk
        gk.clear_model_overload()

    def test_chat_starts_with_primary_key_and_newest_model(self):
        from management.services import gemini_keys as gk
        with patch.dict("os.environ", ENV6, clear=False):
            first = next(gk.iter_attempts("chat"))
        self.assertEqual(first[0], "GEMINI_API")
        self.assertEqual(first[2], "gemini-3.7-flash")

    def test_checker_manual_key_cannot_reuse_reserved_chat_secret(self):
        from management.services import gemini_keys as gk

        env = dict(ENV6)
        env["GEMINI_API"] = "shared-chat-secret"
        with patch.dict("os.environ", env, clear=False):
            self.assertFalse(
                gk.manual_key_allowed("checker", "shared-chat-secret")
            )
            self.assertTrue(
                gk.manual_key_allowed("chat", "shared-chat-secret")
            )

    def test_chat_falls_to_borrow_when_own_in_cooldown(self):
        from management.services import gemini_keys as gk
        now = timezone.now()
        gk.mark_429("GEMINI_API", "day", 0, now=now)
        gk.mark_429("GEMINI_API2", "day", 0, now=now)
        with patch.dict("os.environ", ENV6, clear=False):
            keys = [a[0] for a in gk.iter_attempts("chat")]
        self.assertNotIn("GEMINI_API", keys)
        self.assertNotIn("GEMINI_API2", keys)
        self.assertEqual(keys[0], "GEMINI_API3")

    def test_cooldown_only_removes_affected_key_from_all_six_pool(self):
        from management.services import gemini_keys as gk
        now = timezone.now()
        gk.mark_429("GEMINI_API3", "minute", 120, now=now)
        with patch.dict("os.environ", ENV6, clear=False):
            keys = [a[0] for a in gk.iter_attempts("chat")]
        self.assertNotIn("GEMINI_API3", keys)
        self.assertIn("GEMINI_API4", keys)
        self.assertIn("GEMINI_API5", keys)
        self.assertIn("GEMINI_API6", keys)

    def test_overloaded_model_skipped(self):
        from management.services import gemini_keys as gk
        gk.mark_model_overloaded("gemini-3.5-flash", seconds=300)
        with patch.dict("os.environ", ENV6, clear=False):
            models_for_first_key = [a[2] for a in gk.iter_attempts("chat") if a[0] == "GEMINI_API"]
        self.assertNotIn("gemini-3.5-flash", models_for_first_key)
        self.assertIn("gemini-3.5-flash-lite", models_for_first_key)
        gk.clear_model_overload()

    def test_model_chain_override_is_used_for_pooled_attempts(self):
        from management.services import gemini_keys as gk

        with patch.dict("os.environ", ENV6, clear=False):
            combos = list(
                gk.iter_attempts(
                    "chat",
                    model_chain_override=["gemini-3.5-flash-lite", "gemini-3.6-flash"],
                )
            )
        self.assertTrue(combos)
        self.assertEqual(combos[0][2], "gemini-3.5-flash-lite")

    def test_checker_chain_uses_25_flash(self):
        from management.services import gemini_keys as gk
        with patch.dict("os.environ", ENV6, clear=False):
            combos = list(gk.iter_attempts("checker"))
        self.assertTrue(all(k in set(ENV6) for k, _, _ in combos))
        key_order = []
        for key_name, _, _ in combos:
            if key_name not in key_order:
                key_order.append(key_name)
        self.assertEqual(key_order[:2], ["GEMINI_API5", "GEMINI_API6"])
        self.assertEqual(
            set(key_order),
            {"GEMINI_API3", "GEMINI_API4", "GEMINI_API5", "GEMINI_API6"},
        )
        self.assertIn("gemini-2.5-flash", [m for _, _, m in combos])

    def test_management_pool_uses_own_then_non_chat_borrowed_keys(self):
        from management.services import gemini_keys as gk
        with patch.dict("os.environ", ENV6, clear=False):
            combos = list(gk.iter_attempts("management"))
        key_order = []
        for key_name, _, _ in combos:
            if key_name not in key_order:
                key_order.append(key_name)
        self.assertEqual(key_order[:2], ["GEMINI_API3", "GEMINI_API4"])
        self.assertEqual(
            set(key_order),
            {"GEMINI_API3", "GEMINI_API4", "GEMINI_API5", "GEMINI_API6"},
        )

    def test_chat_pool_uses_all_six_keys_with_own_priority(self):
        from management.services import gemini_keys as gk
        with patch.dict("os.environ", ENV6, clear=False):
            combos = list(gk.iter_attempts("chat"))
        key_order = []
        for key_name, _, _ in combos:
            if key_name not in key_order:
                key_order.append(key_name)
        self.assertEqual(key_order[:2], ["GEMINI_API", "GEMINI_API2"])
        self.assertEqual(set(key_order), set(ENV6))

    def test_chat_preserves_hot_shared_and_last_reserve_tiers(self):
        """Sticky success may reorder a tier, but never promote API5/6 over API3/4."""
        from management.services import gemini_keys as gk

        gk.mark_success("GEMINI_API5", now=timezone.now())
        with patch.dict("os.environ", ENV6, clear=False):
            primary = [
                key_name
                for key_name, _, model in gk.iter_attempts("chat")
                if model == "gemini-3.7-flash"
            ]

        self.assertEqual(set(primary[:2]), {"GEMINI_API", "GEMINI_API2"})
        self.assertEqual(set(primary[2:4]), {"GEMINI_API3", "GEMINI_API4"})
        self.assertEqual(set(primary[4:6]), {"GEMINI_API5", "GEMINI_API6"})

    def test_primary_model_tried_on_all_keys_before_lower(self):
        """Model-major: gemini-3.7-flash перебирається на ВСІХ ключах раніше за
        будь-яку резервну модель."""
        from management.services import gemini_keys as gk
        with patch.dict("os.environ", ENV6, clear=False):
            combos = list(gk.iter_attempts("chat"))
        models_seq = [m for _, _, m in combos]
        last_primary = max(i for i, m in enumerate(models_seq) if m == "gemini-3.7-flash")
        first_lower = min(i for i, m in enumerate(models_seq) if m != "gemini-3.7-flash")
        self.assertLess(last_primary, first_lower)
        keys_with_primary = {k for k, _, m in combos if m == "gemini-3.7-flash"}
        self.assertEqual(
            keys_with_primary,
            set(ENV6),
        )

    def test_primary_kept_for_other_keys_after_midpass_overload(self):
        """Frozen snapshot: 503 на 3.7 під час проходу не виключає 3.7 з решти
        ключів — спершу вичерпуємо пріоритетну модель на всіх ключах."""
        from management.services import gemini_keys as gk
        gk.clear_model_overload()
        with patch.dict("os.environ", ENV6, clear=False):
            gen = gk.iter_attempts("chat")
            first = next(gen)
            gk.mark_model_overloaded("gemini-3.7-flash", seconds=300)
            rest = list(gen)
        combos = [first] + rest
        keys_with_primary = {k for k, _, m in combos if m == "gemini-3.7-flash"}
        self.assertEqual(
            keys_with_primary,
            set(ENV6),
        )
        gk.clear_model_overload()


class PoolStatusTests(TestCase):
    def test_pool_status_shape(self):
        from management.services import gemini_keys as gk
        now = timezone.now()
        gk.mark_429("GEMINI_API", "day", 0, now=now)
        with patch.dict("os.environ", ENV6, clear=False):
            rows = gk.pool_status(now=now)
        by_name = {r["key_name"]: r for r in rows}
        self.assertEqual(len(rows), 6)
        self.assertFalse(by_name["GEMINI_API"]["available"])
        self.assertGreater(by_name["GEMINI_API"]["seconds_remaining"], 0)
        self.assertTrue(by_name["GEMINI_API2"]["available"])
        self.assertEqual(by_name["GEMINI_API"]["role"], "chat")
        self.assertIn("project_identity_known", by_name["GEMINI_API"])


class KeyLevel429Tests(SimpleTestCase):
    def test_free_model_429_is_key_level(self):
        from management.services import gemini_keys as gk
        self.assertTrue(gk.is_key_level_429("gemini-3.5-flash", grounded=False))
        self.assertTrue(gk.is_key_level_429("gemini-3.1-flash-lite", grounded=False))

    def test_paid_model_429_is_model_level(self):
        from management.services import gemini_keys as gk
        self.assertFalse(gk.is_key_level_429("gemini-3.1-pro-preview", grounded=False))

    def test_grounding_429_key_level_only_on_25(self):
        from management.services import gemini_keys as gk
        self.assertTrue(gk.is_key_level_429("gemini-2.5-flash", grounded=True))
        self.assertFalse(gk.is_key_level_429("gemini-3.5-flash", grounded=True))


class ModelChainPolicyTests(SimpleTestCase):
    @override_settings(GEMINI_ROLE_MODEL_CHAINS={
        "chat": ["gemini-3-flash-preview", "gemini-3.5-flash-lite", "gemini-3.6-flash"],
    })
    def test_chat_override_filters_obsolete_models_through_allowlist(self):
        from management.services import gemini_keys as gk

        chain = gk.model_chain("chat")

        self.assertEqual(
            chain,
            ["gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"],
        )

    @override_settings(GEMINI_ROLE_MODEL_CHAINS={
        "management": ["gemini-3.6-flash", "gemini-3.5-flash"],
    })
    def test_management_override_cannot_demote_gemini_37(self):
        from management.services import gemini_keys as gk

        self.assertEqual(
            gk.model_chain("management"),
            ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"],
        )

    @override_settings(GEMINI_ROLE_MODEL_CHAINS={
        "chat": ["gemini-3.6-flash", "gemini-3.5-flash"],
    })
    def test_partial_chat_override_preserves_management_default_chain(self):
        from management.services import gemini_keys as gk

        self.assertEqual(gk.model_chain("management")[0], "gemini-3.7-flash")

    def test_management_chain_uses_gemini_37_flash_first(self):
        from management.services import gemini_keys as gk

        chain = gk.model_chain("management")

        self.assertEqual(chain[0], "gemini-3.7-flash")
        self.assertEqual(len(chain), len(set(chain)))


class ProjectCooldownPolicyTests(SimpleTestCase):
    def test_success_preserves_strongest_active_project_cooldown(self):
        from management.services import gemini_keys as gk

        now = timezone.now()
        sibling_until = now + datetime.timedelta(minutes=5)
        states = [
            SimpleNamespace(cooldown_until=None, cooldown_scope=""),
            SimpleNamespace(
                cooldown_until=sibling_until,
                cooldown_scope="minute",
            ),
        ]

        active = gk._active_project_cooldown(states, now=now)

        self.assertEqual(active, (sibling_until, "minute"))

    def test_shorter_429_does_not_shorten_existing_project_cooldown(self):
        from management.services import gemini_keys as gk

        now = timezone.now()
        longer_until = now + datetime.timedelta(hours=6)
        state = SimpleNamespace(
            day_date=now.astimezone(gk.PT).date(),
            requests_today=0,
            cooldown_until=longer_until,
            cooldown_scope="topup",
            last_status="429:topup",
            last_429_at=now,
            last_error="",
            save=Mock(),
        )

        gk._apply_429_state(state, "minute", 30, now, error="short limit")

        self.assertEqual(state.cooldown_until, longer_until)
        self.assertEqual(state.cooldown_scope, "topup")
        state.save.assert_called_once()


class ModelChainDegradationTests(SimpleTestCase):
    """Фаза 1: цепочки моделей — лише безкоштовні, з деградацією до меншої моделі.
    Платні моделі (pro) НЕ в цепочці (free-tier ключі не можуть їх юзати → марна трата)."""

    def test_management_degrades_to_smaller_free_models_without_paid(self):
        from management.services import gemini_keys as gk
        chain = gk.role_model_chains()["management"]
        self.assertEqual(chain[0], "gemini-3.7-flash")
        self.assertIn("gemini-2.5-flash", chain)
        self.assertIn("gemini-2.5-flash-lite", chain)
        self.assertNotIn("gemini-3.1-pro-preview", chain)
        self.assertNotIn("gemini-3-pro-preview", chain)
        self.assertNotIn("gemini-2.5-pro", chain)
        for m in chain:
            self.assertIn(m, gk.FREE_QUOTA_MODELS)

    def test_live_chat_chain_contains_only_approved_models_in_quality_order(self):
        from management.services import gemini_keys as gk

        chain = gk.role_model_chains()["chat"]

        self.assertEqual(
            chain,
            [
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
            ],
        )

    def test_chat_model_allowlist_normalizes_legacy_or_arbitrary_values(self):
        from management.services import gemini_keys as gk

        self.assertTrue(gk.is_allowed_chat_model("gemini-3.7-flash"))
        self.assertTrue(gk.is_allowed_chat_model("gemini-3.6-flash"))
        self.assertTrue(gk.is_allowed_chat_model("gemini-3.5-flash-lite"))
        self.assertFalse(gk.is_allowed_chat_model("gemini-2.5-flash"))
        self.assertFalse(gk.is_allowed_chat_model("https://attacker.invalid/model"))
        self.assertEqual(gk.normalize_chat_model("gemini-3-flash-preview"), "gemini-3.7-flash")
        self.assertEqual(
            gk.model_chain("chat", "gemini-2.5-flash")[0],
            "gemini-3.7-flash",
        )
        self.assertNotIn("gemini-2.5-flash", gk.model_chain("chat", "gemini-2.5-flash"))

    def test_checker_chain_uses_only_free_grounding_models(self):
        from management.services import gemini_keys as gk
        chain = gk.role_model_chains()["checker"]
        self.assertTrue(chain)
        for m in chain:
            self.assertIn(m, gk.FREE_GROUNDING_MODELS)
        self.assertNotIn("gemini-3.5-flash", chain)


class DurableGeminiStateTests(TestCase):
    def setUp(self):
        from management.services import gemini_keys as gk

        self.gk = gk
        self.env = {
            "GEMINI_API": "chat-key-1",
            "GEMINI_API2": "chat-key-2",
            "GEMINI_API3": "analysis-key-1",
        }

    def test_project_siblings_cannot_hold_the_same_lease(self):
        acquire = getattr(self.gk, "acquire_key_lease", None)
        release = getattr(self.gk, "release_key_lease", None)
        self.assertTrue(callable(acquire), "missing durable key lease acquisition")
        self.assertTrue(callable(release), "missing durable key lease release")

        with patch.dict("os.environ", self.env, clear=False), override_settings(
            GEMINI_KEY_PROJECT_GROUPS="GEMINI_API=chat-project,GEMINI_API2=chat-project,GEMINI_API3=analysis-project"
        ):
            token = acquire("GEMINI_API", role="chat")
            self.assertTrue(token)
            self.assertIsNone(acquire("GEMINI_API2", role="chat"))
            self.assertFalse(release("GEMINI_API", "wrong-token"))
            self.assertTrue(release("GEMINI_API", token))
            self.assertTrue(acquire("GEMINI_API2", role="chat"))

    def test_model_circuit_is_cross_process_state(self):
        opener = getattr(self.gk, "open_model_circuit", None)
        is_open = getattr(self.gk, "model_circuit_open", None)
        self.assertTrue(callable(opener), "missing durable model circuit")
        self.assertTrue(callable(is_open), "missing durable circuit check")

        opener("gemini-3.6-flash", reason="http_404")
        self.assertTrue(is_open("gemini-3.6-flash"))

    def test_attempt_telemetry_is_redacted_and_keyed_by_request(self):
        recorder = getattr(self.gk, "record_attempt", None)
        self.assertTrue(callable(recorder), "missing Gemini request telemetry")

        row = recorder(
            request_id="request-redacted-1",
            role="chat",
            key_name="GEMINI_API",
            model="gemini-3.6-flash",
            outcome="failed",
            failure_kind="read_timeout",
            error_detail="api_key=chat-key-1 customer text must not persist",
            latency_ms=123,
            remaining_deadline_ms=456,
        )
        self.assertEqual(row.request_id, "request-redacted-1")
        self.assertEqual(row.failure_kind, "read_timeout")
        self.assertNotIn("chat-key-1", row.error_detail)
        self.assertNotIn("customer text", row.error_detail)


class ModelUnavailableSkipTests(TestCase):
    """Фаза 1: модель, що повернула 429-платно / 404 — позначається недоступною й
    одразу пропускається (не б'ємо її на решті ключів / у наступних викликах)."""

    def setUp(self):
        from management.services import gemini_keys as gk
        gk.clear_model_unavailable()

    def tearDown(self):
        from management.services import gemini_keys as gk
        gk.clear_model_unavailable()

    def test_mark_and_is_unavailable_with_ttl(self):
        from management.services import gemini_keys as gk
        now = timezone.now()
        self.assertFalse(gk.is_model_unavailable("gemini-3.1-pro-preview", now))
        gk.mark_model_unavailable("gemini-3.1-pro-preview", seconds=600, now=now)
        self.assertTrue(gk.is_model_unavailable("gemini-3.1-pro-preview", now))
        self.assertFalse(
            gk.is_model_unavailable("gemini-3.1-pro-preview", now + datetime.timedelta(seconds=601))
        )

    def test_iter_attempts_skips_unavailable_model_entirely(self):
        from management.services import gemini_keys as gk
        gk.mark_model_unavailable("gemini-3.5-flash", seconds=600)
        with patch.dict("os.environ", ENV6, clear=False):
            combos = list(gk.iter_attempts("chat"))
        self.assertNotIn("gemini-3.5-flash", [m for _, _, m in combos])
        # нижча модель усе ще доступна
        self.assertIn("gemini-3.5-flash-lite", [m for _, _, m in combos])

    def test_iter_attempts_stops_model_when_marked_unavailable_midpass(self):
        from management.services import gemini_keys as gk
        with patch.dict("os.environ", ENV6, clear=False):
            gen = gk.iter_attempts("chat")
            first = next(gen)
            self.assertEqual(first[2], "gemini-3.7-flash")
            # імітуємо: на 1-му ключі модель виявилась платною → позначили
            gk.mark_model_unavailable("gemini-3.7-flash", seconds=600)
            rest = list(gen)
        # після позначення 3.7-flash вона більше не пробується на інших ключах
        self.assertEqual([(k, m) for k, _, m in rest if m == "gemini-3.7-flash"], [])
