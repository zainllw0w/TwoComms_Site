"""Фаза 4: виправлення підтверджених багів формул MOSAIC (тільки рейтинг, не гроші)."""
from decimal import Decimal

from django.test import SimpleTestCase

from management.services.trust import compute_production_trust


class ProductionTrustFormulaTests(SimpleTestCase):
    def _t(self, **kw):
        base = dict(duplicate_backlog=0, overdue_followups=0,
                    telephony_healthy=True, reason_quality=Decimal("1.00"))
        base.update(kw)
        return compute_production_trust(**base)

    def test_clean_manager_gets_max(self):
        self.assertEqual(self._t(), Decimal("1.0300"))

    def test_overdue_penalized_once_not_twice(self):
        # overdue=5 → report_integrity=0.5; раніше overdue штрафувався ще й через anomaly.
        # Тепер лише через report_integrity: 0.97 + 0.04*0.5 + 0.02 = 1.01.
        self.assertEqual(self._t(overdue_followups=5), Decimal("1.0100"))

    def test_duplicates_penalized_consolidated(self):
        # dup>=5 → duplicate_abuse=1 → 0.97 + 0.04 + 0.02 - 0.10 = 0.93.
        self.assertEqual(self._t(duplicate_backlog=5), Decimal("0.9300"))

    def test_telephony_flag_no_longer_changes_trust(self):
        a = self._t(duplicate_backlog=2, overdue_followups=3, telephony_healthy=True)
        b = self._t(duplicate_backlog=2, overdue_followups=3, telephony_healthy=False)
        self.assertEqual(a, b)

    def test_floor_085(self):
        self.assertGreaterEqual(
            self._t(duplicate_backlog=100, overdue_followups=100, reason_quality=Decimal("0")),
            Decimal("0.85"),
        )


from management.services import snapshots as snap
from management.services import score as score_svc


class IdleAxisBaselineTests(SimpleTestCase):
    """Фаза 4B: бездіяльність більше НЕ дорівнює «ідеалу» осей (інверсія стимулів).
    Пустий день (processed==0) → низька база, а не 1.0 → дозволяє рейтингу осідати
    нижче 14 при тривалому простої. Активного менеджера (processed>0) не чіпаємо."""

    def test_follow_up_idle_day_not_perfect(self):
        v = snap._compute_follow_up_axis({"processed": 0, "followups": {}, "pipeline": {}})
        self.assertLessEqual(v, Decimal("0.5"))

    def test_follow_up_active_no_followups_stays_high(self):
        v = snap._compute_follow_up_axis({"processed": 30, "followups": {}, "pipeline": {}})
        self.assertEqual(v, Decimal("1.0"))

    def test_data_quality_idle_day_not_perfect(self):
        v = snap._compute_data_quality_axis({"processed": 0, "pipeline": {}, "reports": {}})
        self.assertLessEqual(v, Decimal("0.5"))

    def test_data_quality_active_high_when_clean(self):
        v = snap._compute_data_quality_axis({"processed": 30, "pipeline": {}, "reports": {}})
        self.assertGreaterEqual(v, Decimal("0.9"))


class VerifiedSliceTests(SimpleTestCase):
    """Фаза 4B: verified_slice рахується від вкладу осі result (а не 40% усього balla)."""

    def _readiness(self):
        return {k: "shadow" for k in score_svc.MOSAIC_WEIGHTS}

    def _run(self, **over):
        kw = dict(base_mosaic=Decimal("70"), gate_score=100, trust_multiplier=Decimal("1.0"),
                  dampener=Decimal("1.0"), readiness=self._readiness(), gate_level="Paid",
                  onboarding_floor=Decimal("0"), result_axis=Decimal("0.9"))
        kw.update(over)
        return score_svc.apply_shadow_score_pipeline(**kw)

    def test_verified_slice_scales_with_result_axis(self):
        low = self._run(result_axis=Decimal("0.2"))
        high = self._run(result_axis=Decimal("0.9"))
        self.assertLess(low["verified_slice"], high["verified_slice"])

    def test_verified_slice_zero_without_paid(self):
        out = self._run(gate_level="Self-reported only", gate_score=45)
        self.assertEqual(out["verified_slice"], Decimal("0.00"))

    def test_verified_slice_not_exceed_base(self):
        out = self._run(base_mosaic=Decimal("10"), result_axis=Decimal("1.0"))
        self.assertLessEqual(out["verified_slice"], out["base_mosaic"])
