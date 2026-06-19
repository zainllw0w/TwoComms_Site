from django.test import TestCase

from management.models import (
    LeadAICheck,
    LeadCheckJob,
    LeadCheckRuntimeLock,
    LeadCheckerSettings,
    ManagementLead,
)


class LeadCheckerSettingsTests(TestCase):
    def test_load_creates_singleton(self):
        obj = LeadCheckerSettings.load()
        self.assertEqual(obj.pk, 1)
        self.assertEqual(obj.gemini_api_key, "")
        self.assertEqual(obj.requests_per_minute, 8)

    def test_load_is_idempotent(self):
        a = LeadCheckerSettings.load()
        a.gemini_api_key = "secret-key"
        a.save()
        b = LeadCheckerSettings.load()
        self.assertEqual(b.gemini_api_key, "secret-key")
        self.assertEqual(LeadCheckerSettings.objects.count(), 1)


class LeadCheckJobModelTests(TestCase):
    def test_create_defaults(self):
        job = LeadCheckJob.objects.create(scope=LeadCheckJob.Scope.UNCHECKED)
        self.assertEqual(job.status, LeadCheckJob.Status.RUNNING)
        self.assertEqual(job.processed, 0)
        self.assertEqual(job.scored, 0)
        self.assertEqual(job.errors, 0)
        self.assertEqual(job.cursor_id, 0)
        self.assertEqual(job.requests_per_minute, 8)

    def test_runtime_lock_singleton(self):
        lock, _ = LeadCheckRuntimeLock.objects.get_or_create(singleton_key=1)
        self.assertEqual(lock.pk, 1)
        self.assertIsNone(lock.active_job_id)


class LeadAICheckModelTests(TestCase):
    def test_create_check_linked_to_lead(self):
        lead = ManagementLead.objects.create(shop_name="Shop", phone="0501112233")
        check = LeadAICheck.objects.create(
            lead=lead, status=LeadAICheck.Status.DONE, overall_score=75,
            criteria=[{"key": "product", "title": "Товар", "score": 8, "comment": "ok"}],
            verdict_category="brand", partnership_fit=["wholesale", "collab"],
            confidence="medium", sources=[{"title": "IG", "url": "https://instagram.com/x"}],
        )
        self.assertEqual(lead.ai_checks.count(), 1)
        self.assertEqual(check.partnership_fit, ["wholesale", "collab"])
        self.assertEqual(check.criteria[0]["score"], 8)


from unittest.mock import patch

from django.utils import timezone

from management.services import lead_check_job as ljob


class CandidateQuerysetTests(TestCase):
    def _lead(self, **kw):
        defaults = dict(shop_name="S", phone="050" + str(1000000 + ManagementLead.objects.count()),
                        lead_source=ManagementLead.LeadSource.PARSER)
        defaults.update(kw)
        return ManagementLead.objects.create(**defaults)

    def test_unchecked_scope_excludes_checked(self):
        a = self._lead()
        b = self._lead(ai_checked_at=timezone.now(), ai_verdict="fit")
        qs = ljob.candidate_queryset(scope="unchecked", city="", band="")
        self.assertIn(a, qs)
        self.assertNotIn(b, qs)

    def test_all_scope_includes_everything_parser(self):
        a = self._lead()
        b = self._lead(ai_checked_at=timezone.now())
        qs = ljob.candidate_queryset(scope="all", city="", band="")
        self.assertIn(a, qs)
        self.assertIn(b, qs)

    def test_by_city_scope(self):
        a = self._lead(city="Харків")
        b = self._lead(city="Київ")
        qs = ljob.candidate_queryset(scope="by_city", city="Харків", band="")
        self.assertIn(a, qs)
        self.assertNotIn(b, qs)

    def test_by_band_scope(self):
        a = self._lead(ai_checked_at=timezone.now(), ai_verdict="maybe")
        b = self._lead(ai_checked_at=timezone.now(), ai_verdict="fit")
        qs = ljob.candidate_queryset(scope="by_band", city="", band="maybe")
        self.assertIn(a, qs)
        self.assertNotIn(b, qs)

    def test_excludes_manual_leads(self):
        manual = self._lead(lead_source=ManagementLead.LeadSource.MANUAL)
        qs = ljob.candidate_queryset(scope="all", city="", band="")
        self.assertNotIn(manual, qs)


class ResolveKeyTests(TestCase):
    def test_returns_settings_key_when_set(self):
        s = LeadCheckerSettings.load()
        s.gemini_api_key = "settings-key"
        s.save()
        self.assertEqual(ljob.resolve_checker_api_key(), "settings-key")

    def test_returns_empty_when_unset(self):
        self.assertEqual(ljob.resolve_checker_api_key(), "")


class JobLifecycleTests(TestCase):
    def setUp(self):
        for i in range(3):
            ManagementLead.objects.create(
                shop_name=f"S{i}", phone=f"05010000{i}",
                lead_source=ManagementLead.LeadSource.PARSER,
            )

    def test_create_sets_total_and_lock(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=10)
        self.assertEqual(job.status, LeadCheckJob.Status.RUNNING)
        self.assertEqual(job.total_selected, 3)
        lock = LeadCheckRuntimeLock.objects.get(singleton_key=1)
        self.assertEqual(lock.active_job_id, job.id)

    def test_second_active_job_rejected(self):
        ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=10)
        with self.assertRaises(ljob.CheckerServiceError):
            ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=10)

    def test_pause_resume_stop(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=10)
        job = ljob.pause_job(job.id)
        self.assertEqual(job.status, LeadCheckJob.Status.PAUSED)
        job = ljob.resume_job(job.id)
        self.assertEqual(job.status, LeadCheckJob.Status.RUNNING)
        job = ljob.stop_job(job.id)
        self.assertEqual(job.status, LeadCheckJob.Status.STOPPED)
        lock = LeadCheckRuntimeLock.objects.get(singleton_key=1)
        self.assertIsNone(lock.active_job_id)

    def test_stop_allows_new_job(self):
        j1 = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=10)
        ljob.stop_job(j1.id)
        j2 = ljob.create_check_job(user=None, scope="all", city="", band="", target_limit=0, requests_per_minute=10)
        self.assertEqual(j2.status, LeadCheckJob.Status.RUNNING)


class RunStepTests(TestCase):
    def setUp(self):
        self.leads = [
            ManagementLead.objects.create(shop_name=f"S{i}", phone=f"05011100{i}",
                                          lead_source=ManagementLead.LeadSource.PARSER)
            for i in range(3)
        ]
        # У тестовому середовищі ключів пулу немає — імітуємо доступний ключ.
        p = patch.object(ljob, "checker_can_run", return_value=True)
        p.start()
        self.addCleanup(p.stop)

    def _fake_check(self, lead, **kw):
        check = LeadAICheck.objects.create(lead=lead, status=LeadAICheck.Status.DONE, overall_score=75)
        check._duration_seconds = 1.5
        lead.ai_score = 75
        lead.ai_verdict = "fit"
        lead.ai_checked_at = timezone.now()
        lead.save(update_fields=["ai_score", "ai_verdict", "ai_checked_at"])
        return check

    def test_step_processes_one_lead_and_advances(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=60)
        with patch.object(ljob.lead_checker, "score_lead", side_effect=self._fake_check):
            job = ljob.run_step(job)
        self.assertEqual(job.processed, 1)
        self.assertEqual(job.scored, 1)
        self.assertEqual(job.fit_count, 1)
        self.assertGreater(job.cursor_id, 0)

    def test_step_completes_when_no_more_leads(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=60)
        with patch.object(ljob.lead_checker, "score_lead", side_effect=self._fake_check):
            for _ in range(5):
                LeadCheckJob.objects.filter(id=job.id).update(next_step_not_before=None)
                job = ljob.run_step(job)
        self.assertEqual(job.processed, 3)
        self.assertEqual(job.status, LeadCheckJob.Status.COMPLETED)

    def test_step_respects_target_limit(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=2, requests_per_minute=60)
        with patch.object(ljob.lead_checker, "score_lead", side_effect=self._fake_check):
            for _ in range(5):
                LeadCheckJob.objects.filter(id=job.id).update(next_step_not_before=None)
                job = ljob.run_step(job)
        self.assertEqual(job.processed, 2)
        self.assertEqual(job.status, LeadCheckJob.Status.COMPLETED)

    def test_step_counts_errors(self):
        def err_check(lead, **kw):
            check = LeadAICheck.objects.create(lead=lead, status=LeadAICheck.Status.ERROR, error="x")
            check._duration_seconds = 0.5
            lead.ai_verdict = "error"
            lead.ai_checked_at = timezone.now()
            lead.save(update_fields=["ai_verdict", "ai_checked_at"])
            return check
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=60)
        with patch.object(ljob.lead_checker, "score_lead", side_effect=err_check):
            job = ljob.run_step(job)
        self.assertEqual(job.errors, 1)
        self.assertEqual(job.scored, 0)


class StatusPayloadTests(TestCase):
    def setUp(self):
        ManagementLead.objects.create(shop_name="S0", phone="0501230000",
                                      lead_source=ManagementLead.LeadSource.PARSER)

    def test_payload_shape(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=12)
        payload = ljob.job_status_payload(job)
        self.assertEqual(payload["id"], job.id)
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["total_selected"], 1)
        self.assertEqual(payload["processed"], 0)
        self.assertIn("fit_count", payload)
        self.assertIn("maybe_count", payload)
        self.assertIn("unfit_count", payload)
        self.assertIn("errors", payload)
        self.assertIn("avg_seconds", payload)
        self.assertIn("next_step_eta_ms", payload)
        self.assertIn("elapsed_seconds", payload)

    def test_payload_none_job(self):
        self.assertIsNone(ljob.job_status_payload(None))


from unittest.mock import patch

from management.services import lead_check_job as ljob
from management.services import gemini_keys as gk


class CheckerKeysCooldownTests(TestCase):
    def _make_lead(self):
        return ManagementLead.objects.create(
            shop_name="S", phone="0501110000",
            lead_source=ManagementLead.LeadSource.PARSER,
        )

    def test_run_step_pauses_when_no_key(self):
        self._make_lead()
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="",
                                    target_limit=0, requests_per_minute=60)
        with patch.object(ljob, "resolve_checker_api_key", return_value=""), \
             patch.object(gk, "has_available_key", return_value=False), \
             patch.object(gk, "soonest_cooldown", return_value=None):
            job = ljob.run_step(job)
        self.assertEqual(job.status, LeadCheckJob.Status.PAUSED)
        self.assertEqual(job.stop_reason_code, "keys_cooldown")
        self.assertEqual(job.processed, 0)  # лід НЕ спалено в error

    def test_run_step_runs_when_key_available(self):
        self._make_lead()
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="",
                                    target_limit=0, requests_per_minute=60)
        fake = {"parsed": {"overall_score": 75, "criteria": []}, "usage": {}, "model": "gemini-2.5-flash"}
        with patch.object(ljob, "resolve_checker_api_key", return_value=""), \
             patch.object(gk, "has_available_key", return_value=True), \
             patch("management.services.lead_checker.gemini_generate_grounded", return_value=fake), \
             patch("management.services.lead_checker.fetch_website_text", return_value=("", False)):
            job = ljob.run_step(job)
        self.assertEqual(job.processed, 1)


class AutoRecheckTickTests(TestCase):
    def setUp(self):
        for i in range(3):
            ManagementLead.objects.create(
                shop_name=f"S{i}", phone=f"050111000{i}",
                lead_source=ManagementLead.LeadSource.PARSER,
            )

    def test_disabled_noop(self):
        s = LeadCheckerSettings.load()
        s.auto_recheck = False
        s.save()
        out = ljob.auto_recheck_tick(sleeper=lambda *_: None)
        self.assertFalse(out["ran"])
        self.assertEqual(out["reason"], "disabled")

    def test_keys_cooldown_noop(self):
        s = LeadCheckerSettings.load()
        s.auto_recheck = True
        s.save()
        with patch.object(ljob, "checker_can_run", return_value=False):
            out = ljob.auto_recheck_tick(sleeper=lambda *_: None)
        self.assertFalse(out["ran"])
        self.assertEqual(out["reason"], "keys_cooldown")

    def test_processes_batch_when_enabled(self):
        s = LeadCheckerSettings.load()
        s.auto_recheck = True
        s.auto_recheck_batch = 2
        s.save()
        fake = {"parsed": {"overall_score": 80, "criteria": []}, "usage": {}, "model": "gemini-2.5-flash"}
        with patch.object(ljob, "checker_can_run", return_value=True), \
             patch("management.services.lead_checker.gemini_generate_grounded", return_value=fake), \
             patch("management.services.lead_checker.fetch_website_text", return_value=("", False)):
            out = ljob.auto_recheck_tick(max_seconds=30, sleeper=lambda *_: None)
        self.assertTrue(out["ran"])
        self.assertEqual(out["processed"], 2)
        job = LeadCheckJob.objects.get(id=out["job_id"])
        self.assertTrue(job.is_auto)

    def test_skips_when_manual_active(self):
        s = LeadCheckerSettings.load()
        s.auto_recheck = True
        s.save()
        # ручна активна сесія
        ljob.create_check_job(user=None, scope="unchecked", city="", band="",
                              target_limit=0, requests_per_minute=8)
        with patch.object(ljob, "checker_can_run", return_value=True):
            out = ljob.auto_recheck_tick(sleeper=lambda *_: None)
        self.assertFalse(out["ran"])
        self.assertEqual(out["reason"], "manual_active_or_empty")


class RunStepKeysExhaustedMidCallTests(TestCase):
    def test_pauses_without_consuming_lead(self):
        from management.services import lead_checker
        ManagementLead.objects.create(shop_name="X", phone="0507770000",
                                      lead_source=ManagementLead.LeadSource.PARSER)
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="",
                                    target_limit=0, requests_per_minute=60)
        with patch.object(ljob, "checker_can_run", return_value=True), \
             patch.object(lead_checker, "score_lead",
                          side_effect=lead_checker.CheckerKeysExhausted("quota")), \
             patch.object(gk, "soonest_cooldown", return_value=None):
            job = ljob.run_step(job)
        self.assertEqual(job.status, LeadCheckJob.Status.PAUSED)
        self.assertEqual(job.stop_reason_code, "keys_cooldown")
        self.assertEqual(job.processed, 0)   # лід НЕ спожито
        self.assertEqual(job.errors, 0)
        self.assertEqual(job.cursor_id, 0)   # курсор НЕ зрушено


class CheckerTokenTrackingTests(TestCase):
    """Фаза 2: облік витрачених токенів сесії + ETA до завершення у статусі."""

    def test_job_status_payload_includes_tokens_and_eta(self):
        from management.services import lead_check_job as ljob
        job = LeadCheckJob.objects.create(
            scope=LeadCheckJob.Scope.UNCHECKED, total_selected=10, processed=2,
            avg_seconds=4.0, tokens_total=1234,
        )
        payload = ljob.job_status_payload(job)
        self.assertEqual(payload["tokens_total"], 1234)
        # remaining = 10 - 2 = 8; eta = round(4.0 * 8) = 32
        self.assertEqual(payload["eta_finish_seconds"], 32)

    def test_tokens_total_defaults_zero(self):
        job = LeadCheckJob.objects.create(scope=LeadCheckJob.Scope.UNCHECKED)
        self.assertEqual(job.tokens_total, 0)
