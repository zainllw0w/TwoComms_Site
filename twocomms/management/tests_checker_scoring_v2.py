"""Блок C (scoring v2): collaboration-гейт + стан «під питанням» (verdict_band)."""
from django.test import TestCase

from management.models import ManagementLead, LeadAICheck


class LeadAICheckScoringV2FieldsTests(TestCase):
    def test_new_fields_default_empty(self):
        lead = ManagementLead.objects.create(shop_name="Shop", phone="0501112233")
        c = LeadAICheck.objects.create(lead=lead)
        self.assertEqual(c.verdict_band, "")
        self.assertEqual(c.collaboration_evidence, "")
        self.assertEqual(c.signals, {})

    def test_new_fields_persist(self):
        lead = ManagementLead.objects.create(shop_name="Shop", phone="0501112233")
        c = LeadAICheck.objects.create(
            lead=lead, verdict_band="question", collaboration_evidence="unknown",
            signals={"own_production": "yes"},
        )
        c.refresh_from_db()
        self.assertEqual(c.verdict_band, "question")
        self.assertEqual(c.collaboration_evidence, "unknown")
        self.assertEqual(c.signals["own_production"], "yes")
