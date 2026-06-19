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
