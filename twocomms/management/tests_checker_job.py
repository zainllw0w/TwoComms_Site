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
