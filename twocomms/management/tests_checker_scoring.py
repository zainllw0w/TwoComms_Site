from django.test import TestCase

from management.models import ManagementLead


class ManagementLeadAICacheFieldsTests(TestCase):
    def test_ai_cache_fields_default_empty(self):
        lead = ManagementLead.objects.create(shop_name="Test Shop", phone="0501112233")
        self.assertIsNone(lead.ai_score)
        self.assertEqual(lead.ai_verdict, "")
        self.assertIsNone(lead.ai_checked_at)

    def test_ai_cache_fields_persist(self):
        from django.utils import timezone
        lead = ManagementLead.objects.create(shop_name="Test Shop", phone="0501112233")
        lead.ai_score = 82
        lead.ai_verdict = "fit"
        lead.ai_checked_at = timezone.now()
        lead.save(update_fields=["ai_score", "ai_verdict", "ai_checked_at"])
        lead.refresh_from_db()
        self.assertEqual(lead.ai_score, 82)
        self.assertEqual(lead.ai_verdict, "fit")
        self.assertIsNotNone(lead.ai_checked_at)
