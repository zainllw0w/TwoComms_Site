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


from management.services import lead_checker as lc


class CollaborationGateTests(TestCase):
    def test_positive_no_cap(self):
        cap, ev = lc.compute_collaboration_gate(sells_third_party="yes", own_production="no")
        self.assertEqual(ev, "positive")
        self.assertEqual(cap, 100)

    def test_negative_own_production_blocks_resale(self):
        cap, ev = lc.compute_collaboration_gate(sells_third_party="no", own_production="yes")
        self.assertEqual(ev, "negative")
        self.assertLessEqual(cap, lc.COLLAB_GATE_NEGATIVE_MAX)

    def test_negative_no_own_production_allows_custom_print(self):
        cap, ev = lc.compute_collaboration_gate(sells_third_party="no", own_production="no")
        self.assertEqual(ev, "negative")
        self.assertGreater(cap, lc.COLLAB_GATE_NEGATIVE_MAX)
        self.assertLessEqual(cap, lc.COLLAB_GATE_MAYBE_MAX)

    def test_unknown_caps_below_fit(self):
        cap, ev = lc.compute_collaboration_gate(sells_third_party="unknown", own_production="unknown")
        self.assertEqual(ev, "unknown")
        self.assertLess(cap, lc.FIT_THRESHOLD)


class VerdictBandTests(TestCase):
    def test_fit_requires_positive_collab_and_confidence(self):
        self.assertEqual(lc.compute_verdict_band(score=82, apparel=8, collab_evidence="positive", confidence="high"), "fit")

    def test_high_score_unknown_collab_becomes_question(self):
        self.assertEqual(lc.compute_verdict_band(score=82, apparel=8, collab_evidence="unknown", confidence="high"), "question")

    def test_low_confidence_blocks_fit(self):
        self.assertIn(lc.compute_verdict_band(score=80, apparel=8, collab_evidence="positive", confidence="low"), ("question", "maybe"))

    def test_negative_collab_unfit(self):
        self.assertEqual(lc.compute_verdict_band(score=70, apparel=8, collab_evidence="negative", confidence="high"), "unfit")

    def test_apparel_gate_unfit(self):
        self.assertEqual(lc.compute_verdict_band(score=20, apparel=1, collab_evidence="positive", confidence="high"), "unfit")

    def test_mid_is_maybe(self):
        self.assertEqual(lc.compute_verdict_band(score=55, apparel=6, collab_evidence="positive", confidence="medium"), "maybe")
