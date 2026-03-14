from decimal import Decimal

from django.test import SimpleTestCase

from management.services.churn import compute_churn_weibull
from management.services.payroll import compute_repeat_commission, compute_working_factor
from management.services.score import compute_ewr, compute_mosaic, compute_score_confidence


class ScoreServiceTests(SimpleTestCase):
    def test_compute_ewr_matches_canonical_reference_case(self):
        value = compute_ewr(orders=2, contacts_processed=80, revenue=50_000)
        self.assertEqual(value, Decimal("0.8016"))

    def test_compute_ewr_keeps_low_sample_no_order_window_neutral(self):
        value = compute_ewr(orders=0, contacts_processed=10, revenue=0)
        self.assertEqual(value, Decimal("0.1438"))

    def test_compute_score_confidence_matches_weighted_formula(self):
        value = compute_score_confidence(
            verified_coverage=Decimal("0.90"),
            sample_sufficiency=Decimal("0.80"),
            stability=Decimal("0.70"),
            recency=Decimal("0.60"),
        )
        self.assertEqual(value, Decimal("0.7750"))

    def test_compute_mosaic_redistributes_dormant_axis_weight(self):
        value = compute_mosaic(
            axes={
                "result": Decimal("0.80"),
                "source_fairness": Decimal("0.60"),
                "process": Decimal("0.70"),
                "follow_up": Decimal("0.50"),
                "data_quality": Decimal("0.90"),
                "verified_communication": Decimal("1.00"),
            },
            readiness={
                "result": "shadow",
                "source_fairness": "shadow",
                "process": "shadow",
                "follow_up": "shadow",
                "data_quality": "shadow",
                "verified_communication": "dormant",
            },
        )
        self.assertEqual(value, Decimal("73.33"))


class ChurnServiceTests(SimpleTestCase):
    def test_planned_gap_returns_neutral_churn(self):
        value = compute_churn_weibull(
            days_since_last_order=10,
            avg_interval=30,
            std_interval=8,
            order_count=9,
            expected_next_order=20,
        )
        self.assertEqual(value, Decimal("0.0500"))

    def test_logistic_fallback_used_for_low_history(self):
        value = compute_churn_weibull(
            days_since_last_order=20,
            avg_interval=20,
            std_interval=5,
            order_count=3,
        )
        self.assertEqual(value, Decimal("0.5000"))


class PayrollServiceTests(SimpleTestCase):
    def test_compute_working_factor_prorates_capacity(self):
        value = compute_working_factor([1.0, 0.5, 0.0, 1.0, 0.8])
        self.assertEqual(value, Decimal("0.6600"))

    def test_repeat_commission_uses_soft_floor_penalty_band(self):
        value = compute_repeat_commission(
            repeat_revenue=Decimal("150000"),
            new_clients_this_week=0,
        )
        self.assertEqual(value, Decimal("6900.00"))
