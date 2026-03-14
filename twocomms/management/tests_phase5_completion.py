from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from management.models import (
    Client,
    DtfBridgeSnapshot,
    ManagementDailyActivity,
    ManagerCommissionAccrual,
    ManagerDayStatus,
    NightlyScoreSnapshot,
)
from management.services.payroll import (
    compute_onboarding_floor_score,
    compute_rescue_spiff,
    compute_working_factor,
)
from management.services.score import compute_ewr, compute_score_confidence
from management.services.snapshots import build_daily_stats_range, persist_nightly_snapshot
from management.stats_service import get_stats_payload


class CanonicalGoldenFormulaTests(SimpleTestCase):
    def test_ewr_matches_canonical_goldens(self):
        self.assertEqual(compute_ewr(orders=3, contacts_processed=120, revenue=40_000), Decimal("0.7516"))
        self.assertEqual(compute_ewr(orders=0, contacts_processed=5, revenue=0), Decimal("0.1219"))
        self.assertEqual(compute_ewr(orders=1, contacts_processed=80, revenue=50_000), Decimal("0.7008"))

    def test_score_confidence_matches_canonical_goldens(self):
        self.assertEqual(
            compute_score_confidence(
                verified_coverage=Decimal("0.90"),
                sample_sufficiency=Decimal("0.70"),
                stability=Decimal("0.60"),
                recency=Decimal("0.80"),
            ),
            Decimal("0.7700"),
        )
        self.assertEqual(
            compute_score_confidence(
                verified_coverage=Decimal("0.30"),
                sample_sufficiency=Decimal("0.20"),
                stability=Decimal("0.40"),
                recency=Decimal("0.60"),
            ),
            Decimal("0.3550"),
        )
        self.assertEqual(
            compute_score_confidence(
                verified_coverage=Decimal("0.60"),
                sample_sufficiency=Decimal("0.50"),
                stability=Decimal("0.55"),
                recency=Decimal("0.70"),
            ),
            Decimal("0.5850"),
        )

    def test_working_factor_and_onboarding_floor_match_canonical_goldens(self):
        self.assertEqual(compute_working_factor([1.0, 1.0, 0.0, 1.0, 0.5]), Decimal("0.7000"))
        self.assertEqual(compute_working_factor([0.0, 0.0, 0.0, 0.0, 0.0]), Decimal("0.0000"))
        self.assertEqual(compute_working_factor([1.0, 1.0, 1.0, 1.0, 1.0]), Decimal("1.0000"))
        self.assertEqual(compute_onboarding_floor_score(7), Decimal("40.00"))
        self.assertEqual(compute_onboarding_floor_score(21), Decimal("20.00"))
        self.assertEqual(compute_onboarding_floor_score(28), Decimal("0.00"))

    def test_rescue_spiff_obeys_floor_rate_and_cap(self):
        self.assertEqual(compute_rescue_spiff(Decimal("20_000")), Decimal("500.00"))
        self.assertEqual(compute_rescue_spiff(Decimal("100_000")), Decimal("1000.00"))
        self.assertEqual(compute_rescue_spiff(Decimal("300_000")), Decimal("2000.00"))


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class SnapshotAggregationExplainabilityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="phase5_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)
        call_command("seed_management_defaults")

    def _create_real_snapshot(self, target_date: date) -> NightlyScoreSnapshot:
        created_at = timezone.make_aware(datetime.combine(target_date, time(hour=11, minute=15)))
        Client.objects.create(
            shop_name=f"Shop {target_date.isoformat()}",
            phone=f"+38067111{target_date.day:04d}",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            points_override=180,
            source="Instagram",
        )
        Client.objects.filter(owner=self.user, created_at__isnull=False).update(created_at=created_at)
        ManagementDailyActivity.objects.create(
            user=self.user,
            date=target_date,
            active_seconds=7_200,
            last_seen_at=created_at,
        )
        ManagerDayStatus.objects.create(
            owner=self.user,
            day=target_date,
            status=ManagerDayStatus.Status.WORKING,
            capacity_factor=Decimal("1.00"),
            source_reason="manual",
        )
        return persist_nightly_snapshot(owner=self.user, snapshot_date=target_date)

    def test_snapshot_payload_contains_canonical_sections(self):
        snapshot = self._create_real_snapshot(date(2026, 3, 10))

        self.assertIn("versions", snapshot.payload)
        self.assertIn("score", snapshot.payload)
        self.assertIn("confidence", snapshot.payload)
        self.assertIn("axes", snapshot.payload)
        self.assertIn("working_context", snapshot.payload)
        self.assertIn("dmt_earned_day", snapshot.payload)
        self.assertIn("portfolio", snapshot.payload)
        self.assertIn("ops", snapshot.payload)
        self.assertIn("advice_context", snapshot.payload)

    def test_shadow_payload_aggregates_multiple_daily_snapshots_and_marks_partial_ranges(self):
        first = date(2026, 3, 10)
        third = date(2026, 3, 12)
        NightlyScoreSnapshot.objects.create(
            owner=self.user,
            snapshot_date=first,
            formula_version="mosaic-v1",
            defaults_version="2026-03-13",
            snapshot_schema_version="v2",
            payload_version="v2",
            kpd_value=Decimal("40.00"),
            mosaic_score=Decimal("60.00"),
            score_confidence=Decimal("0.77"),
            working_day_factor=Decimal("1.00"),
            freshness_seconds=1200,
            payload={
                "versions": {"formula_version": "mosaic-v1", "defaults_version": "2026-03-13", "payload_version": "v2", "snapshot_schema_version": "v2"},
                "score": {"legacy_kpd": "40.00", "shadow_mosaic": "60.00", "ewr": "0.70", "score_confidence": "0.77", "gate_level": "CRM-timestamped", "gate_value": 60, "dampener_value": "0.94", "trust_multiplier": "0.98"},
                "confidence": {"verified_coverage": "0.70", "sample_sufficiency": "0.80", "stability": "0.75", "recency": "0.80"},
                "axes": {"result": "0.70", "source_fairness": "0.65", "process": "0.60", "follow_up": "0.55", "data_quality": "0.75", "verified_communication": "0.25"},
                "working_context": {"day_status": "working", "capacity_factor": "1.00", "reintegration_flag": False, "working_day_factor": "1.00"},
                "dmt_earned_day": {"minimum_achieved": True, "target_pace_achieved": False, "recovery_needed": True, "meaningful_calls": 0, "meaningful_call_seconds_threshold": 30, "gap_category": "performance_gap"},
                "portfolio": {"portfolio_health_state": "Watch", "rescue_candidates": [], "rescue_top5": [], "churn_basis": "logistic", "self_selected_mix": 32.0, "assignment_fairness": "0.65"},
                "ops": {"snapshot_freshness_seconds": 1200, "incident_keys": [], "stale_reason": ""},
                "advice_context": {"top_drivers": ["fresh follow-ups"], "top_recovery_actions": ["close overdue calls"], "explainability_tokens": ["gate:60"]},
                "summary": {"invoices": {"amount": "15000", "paid": 1}, "followups": {"missed_effective": 2}, "shops": {}, "pipeline": {}, "reports": {}},
                "readiness": {"result": "shadow", "source_fairness": "shadow", "process": "shadow", "follow_up": "shadow", "data_quality": "shadow", "verified_communication": "dormant"},
            },
        )
        NightlyScoreSnapshot.objects.create(
            owner=self.user,
            snapshot_date=third,
            formula_version="mosaic-v1",
            defaults_version="2026-03-13",
            snapshot_schema_version="v2",
            payload_version="v2",
            kpd_value=Decimal("80.00"),
            mosaic_score=Decimal("90.00"),
            score_confidence=Decimal("0.55"),
            working_day_factor=Decimal("0.80"),
            freshness_seconds=3000,
            payload={
                "versions": {"formula_version": "mosaic-v1", "defaults_version": "2026-03-13", "payload_version": "v2", "snapshot_schema_version": "v2"},
                "score": {"legacy_kpd": "80.00", "shadow_mosaic": "90.00", "ewr": "0.95", "score_confidence": "0.55", "gate_level": "Paid", "gate_value": 100, "dampener_value": "0.88", "trust_multiplier": "1.00"},
                "confidence": {"verified_coverage": "0.80", "sample_sufficiency": "0.60", "stability": "0.50", "recency": "0.65"},
                "axes": {"result": "0.95", "source_fairness": "0.75", "process": "0.85", "follow_up": "0.80", "data_quality": "0.90", "verified_communication": "0.25"},
                "working_context": {"day_status": "working", "capacity_factor": "0.80", "reintegration_flag": True, "working_day_factor": "0.80"},
                "dmt_earned_day": {"minimum_achieved": True, "target_pace_achieved": True, "recovery_needed": False, "meaningful_calls": 3, "meaningful_call_seconds_threshold": 30, "gap_category": ""},
                "portfolio": {"portfolio_health_state": "Risk", "rescue_candidates": [{"name": "Risk Shop"}], "rescue_top5": [{"name": "Risk Shop", "value_at_risk": 4200, "urgency": "72h", "confidence_badge": "MEDIUM", "churn_basis": "weibull"}], "churn_basis": "weibull", "self_selected_mix": 51.0, "assignment_fairness": "0.75"},
                "ops": {"snapshot_freshness_seconds": 3000, "incident_keys": ["DUPLICATE_QUEUE_BACKLOG"], "stale_reason": "missing_middle_day"},
                "advice_context": {"top_drivers": ["paid orders"], "top_recovery_actions": ["protect rescue queue"], "explainability_tokens": ["gate:100"]},
                "summary": {"invoices": {"amount": "45000", "paid": 2}, "followups": {"missed_effective": 1}, "shops": {}, "pipeline": {}, "reports": {}},
                "readiness": {"result": "shadow", "source_fairness": "shadow", "process": "shadow", "follow_up": "shadow", "data_quality": "shadow", "verified_communication": "dormant"},
            },
        )

        range_current = build_daily_stats_range(first)
        range_current = range_current.__class__(
            period="range",
            start=range_current.start,
            end=timezone.make_aware(datetime.combine(date(2026, 3, 12), time.min)) + timezone.timedelta(days=1),
            start_date=first,
            end_date=third,
            label="10.03 — 12.03",
        )
        payload = get_stats_payload(user=self.user, range_current=range_current)
        shadow = payload["shadow_score"]

        self.assertTrue(shadow["flags"]["has_snapshot"])
        self.assertTrue(shadow["flags"]["is_partial"])
        self.assertEqual(shadow["aggregation"]["expected_days"], 3)
        self.assertEqual(shadow["aggregation"]["available_days"], 2)
        self.assertEqual(shadow["aggregation"]["missing_days"], ["2026-03-11"])
        self.assertEqual(shadow["mosaic_score"], 75.0)
        self.assertEqual(shadow["state_label"], "ЧАСТКОВО")

    def test_shadow_explain_and_rescue_endpoints_return_contract_payloads(self):
        target_date = date(2026, 3, 10)
        snapshot = self._create_real_snapshot(target_date)

        shadow_response = self.client.get(f"/stats/mosaic/shadow/?period=range&from={target_date.isoformat()}&to={target_date.isoformat()}", secure=True)
        explain_response = self.client.get(f"/stats/score/explain/?period=range&from={target_date.isoformat()}&to={target_date.isoformat()}", secure=True)
        rescue_response = self.client.get(f"/stats/rescue-top/?period=range&from={target_date.isoformat()}&to={target_date.isoformat()}", secure=True)

        self.assertEqual(shadow_response.status_code, 200)
        self.assertEqual(explain_response.status_code, 200)
        self.assertEqual(rescue_response.status_code, 200)
        self.assertEqual(shadow_response.json()["snapshot_date"], snapshot.snapshot_date.isoformat())
        self.assertIn("base_mosaic", explain_response.json())
        self.assertIn("axes", explain_response.json())
        self.assertIn("items", rescue_response.json())


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class AdminAndPayoutSurfaceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="surface_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)
        call_command("seed_management_defaults")

    def test_admin_dtf_tab_renders_snapshot_payload(self):
        DtfBridgeSnapshot.objects.create(
            source_key="default",
            snapshot_date=date(2026, 3, 14),
            status=DtfBridgeSnapshot.Status.DEGRADED,
            freshness_seconds=3600,
            payload={"reason": "dtf_bridge_not_configured", "items": [{"title": "Живий потік", "value": "fallback"}], "links": [{"title": "Відкрити DTF", "url": "https://dtf.twocomms.shop/"}]},
        )

        response = self.client.get("/admin-panel/?tab=dtf", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DTF-міст")
        self.assertContains(response, "Живий потік")

    def test_admin_surfaces_keep_excluded_manager_history_visible(self):
        excluded = get_user_model().objects.create_user(username="excluded_mgr", password="x")
        excluded.userprofile.is_manager = False
        excluded.userprofile.save(update_fields=["is_manager"])
        ManagementDailyActivity.objects.create(
            user=excluded,
            date=date(2026, 3, 14),
            active_seconds=600,
        )

        stats_response = self.client.get("/stats/admin/", secure=True)
        admin_response = self.client.get("/admin-panel/?tab=managers", secure=True)
        detail_response = self.client.get(f"/stats/admin/{excluded.id}/?period=today", secure=True)

        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(stats_response, "excluded_mgr")
        self.assertContains(stats_response, "Виключений менеджер")
        self.assertContains(admin_response, "excluded_mgr")
        self.assertContains(admin_response, "Виключений менеджер")

    def test_payouts_page_renders_freeze_reasons_and_shadow_hold_harmless(self):
        snapshot = NightlyScoreSnapshot.objects.create(
            owner=self.user,
            snapshot_date=date(2026, 3, 14),
            formula_version="mosaic-v1",
            defaults_version="2026-03-13",
            snapshot_schema_version="v2",
            payload_version="v2",
            kpd_value=Decimal("55.00"),
            mosaic_score=Decimal("72.00"),
            score_confidence=Decimal("0.58"),
            working_day_factor=Decimal("1.00"),
            freshness_seconds=600,
            payload={
                "versions": {"formula_version": "mosaic-v1", "defaults_version": "2026-03-13", "payload_version": "v2", "snapshot_schema_version": "v2"},
                "score": {"legacy_kpd": "55.00", "shadow_mosaic": "72.00", "ewr": "0.72", "score_confidence": "0.58", "gate_level": "CRM-timestamped", "gate_value": 60, "dampener_value": "0.94", "trust_multiplier": "0.98"},
                "confidence": {"verified_coverage": "0.55", "sample_sufficiency": "0.60", "stability": "0.55", "recency": "0.60"},
                "axes": {},
                "working_context": {"day_status": "working", "capacity_factor": "1.00", "reintegration_flag": False, "working_day_factor": "1.00"},
                "dmt_earned_day": {"minimum_achieved": True, "target_pace_achieved": False, "recovery_needed": True, "meaningful_calls": 1, "meaningful_call_seconds_threshold": 30, "gap_category": "reporting_gap"},
                "portfolio": {"portfolio_health_state": "Watch", "rescue_candidates": [], "rescue_top5": [], "churn_basis": "logistic"},
                "ops": {"snapshot_freshness_seconds": 600, "incident_keys": [], "stale_reason": ""},
                "advice_context": {"top_drivers": [], "top_recovery_actions": [], "explainability_tokens": []},
                "summary": {"invoices": {"amount": "35000", "paid": 2}, "followups": {"missed_effective": 0}, "shops": {}, "pipeline": {}, "reports": {}},
                "readiness": {"result": "shadow", "source_fairness": "shadow", "process": "shadow", "follow_up": "shadow", "data_quality": "shadow", "verified_communication": "dormant"},
            },
        )
        ManagerCommissionAccrual.objects.create(
            owner=self.user,
            source_snapshot=snapshot,
            accrual_type=ManagerCommissionAccrual.AccrualType.REPEAT,
            base_amount=Decimal("10000.00"),
            percent=Decimal("5.00"),
            amount=Decimal("500.00"),
            note="Manual note",
            freeze_reason_code="return_window",
            freeze_reason_text="Очікуємо завершення вікна повернення",
            working_factor_applied=Decimal("1.00"),
            evidence_payload={"invoice_number": "W-123"},
            frozen_until=timezone.now() + timezone.timedelta(days=7),
        )

        response = self.client.get("/payouts/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Очікуємо завершення вікна повернення")
        self.assertContains(response, "Тіньовий захист")

    def test_payouts_tab_keeps_excluded_manager_with_history_visible(self):
        excluded = get_user_model().objects.create_user(username="former_payout_mgr", password="x")
        excluded.userprofile.is_manager = False
        excluded.userprofile.save(update_fields=["is_manager"])
        ManagementDailyActivity.objects.create(
            user=excluded,
            date=date(2026, 3, 14),
            active_seconds=900,
        )

        response = self.client.get("/admin-panel/?tab=payouts", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "former_payout_mgr")
