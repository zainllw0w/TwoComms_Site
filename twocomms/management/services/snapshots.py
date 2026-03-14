from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.utils import timezone

from management.models import (
    CommandRunLog,
    ComponentReadiness,
    DuplicateReview,
    ManagementStatsConfig,
    ManagerDayStatus,
    NightlyScoreSnapshot,
)
from management.services.config_versions import get_management_config
from management.services.payroll import (
    compute_earned_day_state,
    compute_onboarding_floor_score,
    compute_rescue_spiff,
)
from management.services.score import (
    apply_shadow_score_pipeline,
    compute_ewr,
    compute_mosaic,
    compute_score_confidence,
)
from management.services.telephony import build_telephony_health_summary
from management.services.trust import (
    classify_confidence_band,
    compute_dampener,
    compute_gate_level,
    compute_production_trust,
)
from management.stats_service import StatsRange, get_stats_payload


TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")
DEFAULT_COMPONENTS = (
    "result",
    "source_fairness",
    "process",
    "follow_up",
    "data_quality",
    "verified_communication",
)


def _to_decimal(value, default: str = "0") -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal(default)
    return Decimal(str(value))


def _quantize(value: Decimal, places: Decimal = FOUR_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_UP)


def _clamp01(value) -> Decimal:
    return _quantize(max(Decimal("0"), min(Decimal("1"), _to_decimal(value))))


def build_daily_stats_range(snapshot_date: date) -> StatsRange:
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(snapshot_date, time.min), tz)
    end = timezone.make_aware(datetime.combine(snapshot_date + timedelta(days=1), time.min), tz)
    return StatsRange(
        period="day",
        start=start,
        end=end,
        start_date=snapshot_date,
        end_date=snapshot_date,
        label=snapshot_date.strftime("%d.%m.%Y"),
    )


def get_component_readiness_map() -> dict[str, str]:
    readiness = {component: ComponentReadiness.Status.SHADOW for component in DEFAULT_COMPONENTS}
    readiness.update(dict(ComponentReadiness.objects.values_list("component", "status")))
    return readiness


def _readiness_weight(status: str) -> Decimal:
    return {
        ComponentReadiness.Status.ACTIVE: Decimal("1.00"),
        ComponentReadiness.Status.SHADOW: Decimal("0.70"),
        ComponentReadiness.Status.DORMANT: Decimal("0.35"),
    }.get(status, Decimal("0.70"))


def _compute_source_fairness(summary: dict[str, Any], sources: list[dict[str, Any]]) -> Decimal:
    processed = max(0, int(summary.get("processed") or 0))
    if processed <= 0 or not sources:
        return Decimal("0.5000")
    top_count = max(int(item.get("count") or 0) for item in sources)
    top_share = Decimal(str(top_count / max(1, processed)))
    return _clamp01(Decimal("1.0") - (top_share * Decimal("0.5")))


def _compute_process_axis(summary: dict[str, Any]) -> Decimal:
    kpd_value = _to_decimal((summary.get("kpd") or {}).get("value") or 0)
    report_block = summary.get("reports") or {}
    required = max(0, int(report_block.get("required") or 0))
    report_penalty = Decimal("0")
    if required > 0:
        late = int(report_block.get("late") or 0)
        missing = int(report_block.get("missing") or 0)
        report_penalty = Decimal(str((late + missing) / max(1, required))) * Decimal("0.3")
    normalized_kpd = min(Decimal("1"), kpd_value / Decimal("4.5"))
    return _clamp01(normalized_kpd - report_penalty)


def _compute_follow_up_axis(summary: dict[str, Any]) -> Decimal:
    followups = summary.get("followups") or {}
    pipeline = summary.get("pipeline") or {}
    missed_rate = Decimal(str((followups.get("missed_rate") or 0) / 100))
    total = max(0, int(followups.get("total") or 0))
    missing_plan = max(0, int(pipeline.get("followup_plan_missing") or 0))
    plan_penalty = Decimal(str(missing_plan / max(1, total or 1))) * Decimal("0.25")
    return _clamp01(Decimal("1.0") - missed_rate - plan_penalty)


def _compute_data_quality_axis(summary: dict[str, Any]) -> Decimal:
    processed = max(0, int(summary.get("processed") or 0))
    pipeline = summary.get("pipeline") or {}
    reports = summary.get("reports") or {}
    missing_plan_ratio = Decimal(str((pipeline.get("followup_plan_missing") or 0) / max(1, processed or 1)))
    reason_quality = _clamp01(Decimal(str(pipeline.get("reason_quality") or 1)))
    reason_penalty = Decimal("1.0") - reason_quality
    required = max(0, int(reports.get("required") or 0))
    missing_reports_ratio = Decimal(str((reports.get("missing") or 0) / max(1, required or 1))) if required else Decimal("0")
    return _clamp01(
        Decimal("1.0")
        - (missing_plan_ratio * Decimal("0.55"))
        - (missing_reports_ratio * Decimal("0.25"))
        - (reason_penalty * Decimal("0.20"))
    )


def _compute_verified_communication_axis(summary: dict[str, Any], readiness: dict[str, str]) -> Decimal:
    success_rate = Decimal(str((summary.get("success_rate_pct") or 0) / 100))
    readiness_factor = _readiness_weight(readiness.get("verified_communication", ComponentReadiness.Status.SHADOW))
    floor = Decimal("0.25") if readiness_factor < Decimal("1.0") else Decimal("0.0")
    return _clamp01((success_rate * readiness_factor) + floor)


def _compute_confidence_inputs(
    *,
    owner,
    snapshot_date: date,
    processed: int,
    readiness: dict[str, str],
    freshness_seconds: int,
    provisional_mosaic: Decimal,
) -> dict[str, Decimal]:
    prev_snapshot = (
        NightlyScoreSnapshot.objects.filter(owner=owner, snapshot_date__lt=snapshot_date)
        .order_by("-snapshot_date")
        .first()
    )
    if prev_snapshot:
        delta = abs(_to_decimal(prev_snapshot.mosaic_score) - provisional_mosaic)
        stability = _clamp01(Decimal("1.0") - (delta / Decimal("100")))
    else:
        stability = Decimal("0.5000")

    verified_coverage = _readiness_weight(readiness.get("verified_communication", ComponentReadiness.Status.SHADOW))
    sample_sufficiency = _clamp01(Decimal(str(processed / 20))) if processed > 0 else Decimal("0.0000")
    recency = _clamp01(Decimal("1.0") - (Decimal(str(freshness_seconds)) / Decimal("604800")))
    return {
        "verified_coverage": verified_coverage,
        "sample_sufficiency": sample_sufficiency,
        "stability": stability,
        "recency": recency,
    }


def _working_day_factor(owner, snapshot_date: date) -> Decimal:
    status = ManagerDayStatus.objects.filter(owner=owner, day=snapshot_date).first()
    if not status:
        return Decimal("1.00")
    return _to_decimal(status.capacity_factor, default="1.00").quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _manager_day_status(owner, snapshot_date: date) -> ManagerDayStatus | None:
    return ManagerDayStatus.objects.filter(owner=owner, day=snapshot_date).first()


def _manager_tenure_days(owner, snapshot_date: date) -> int:
    started_at = getattr(getattr(owner, "userprofile", None), "manager_started_at", None)
    if not started_at:
        try:
            started_at = timezone.localtime(owner.date_joined).date() if owner.date_joined else None
        except Exception:
            started_at = None
    if not started_at:
        return 0
    return max(0, (snapshot_date - started_at).days)


def _crm_updates(summary: dict[str, Any]) -> int:
    followups = summary.get("followups") or {}
    shops = summary.get("shops") or {}
    cp = summary.get("cp") or {}
    invoices = summary.get("invoices") or {}
    touches = (
        int(followups.get("done") or 0)
        + int(followups.get("rescheduled") or 0)
        + int(shops.get("communications_count") or 0)
        + int(cp.get("sent") or 0)
        + int(invoices.get("created") or 0)
    )
    return 1 if touches > 0 else 0


def _portfolio_health(summary: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    shops = summary.get("shops") or {}
    stale_list = shops.get("stale_shops_list") or []
    overdue_tests = shops.get("test_overdue_list") or []
    rescue_cases = []
    for row in overdue_tests[:5]:
        overdue_days = int(row.get("overdue_days") or 0)
        value_at_risk = max(4000, 12000 - overdue_days * 180)
        rescue_cases.append(
            {
                "id": row.get("id"),
                "name": row.get("name") or "Test shop",
                "value_at_risk": value_at_risk,
                "urgency": f"{overdue_days}d overdue",
                "confidence_badge": "MEDIUM",
                "churn_basis": "logistic",
                "potential_spiff": float(compute_rescue_spiff(value_at_risk)),
                "planned_gap": row.get("next_contact_label") or "",
            }
        )
    for row in stale_list[: max(0, 5 - len(rescue_cases))]:
        days_since = int(row.get("days_since") or 0)
        value_at_risk = max(2500, 8000 - days_since * 90)
        rescue_cases.append(
            {
                "id": row.get("id"),
                "name": row.get("name") or "Stale shop",
                "value_at_risk": value_at_risk,
                "urgency": f"{days_since}d stale",
                "confidence_badge": "LOW" if days_since < 14 else "MEDIUM",
                "churn_basis": "interim",
                "potential_spiff": float(compute_rescue_spiff(value_at_risk)),
                "planned_gap": row.get("next_contact_label") or "",
            }
        )
    if overdue_tests:
        state = "Rescue"
    elif stale_list:
        state = "Risk"
    elif int(shops.get("next_contact_due_count") or 0) > 0:
        state = "Watch"
    else:
        state = "Healthy"
    rescue_cases.sort(key=lambda item: item["value_at_risk"], reverse=True)
    return state, rescue_cases[:5]


def _incident_keys(*, summary: dict[str, Any], freshness_seconds: int, duplicate_backlog: int, telephony_status: str) -> list[str]:
    incidents = []
    if freshness_seconds > 172800:
        incidents.append("SNAPSHOT_STALE")
    if duplicate_backlog >= 5:
        incidents.append("DUPLICATE_QUEUE_BACKLOG")
    if int((summary.get("followups") or {}).get("missed_effective") or 0) > 25:
        incidents.append("REMINDER_STORM")
    if telephony_status != "healthy":
        incidents.append("TELEPHONY_OUTAGE")
    return incidents


def build_shadow_score_payload(*, owner, snapshot_date: date) -> dict[str, Any]:
    cfg = ManagementStatsConfig.objects.filter(pk=1).first()
    versioned = get_management_config(cfg)
    stats_range = build_daily_stats_range(snapshot_date)
    stats_payload = get_stats_payload(user=owner, range_current=stats_range)
    summary = stats_payload.get("summary") or {}
    sources = stats_payload.get("sources") or []
    readiness = get_component_readiness_map()

    processed = max(0, int(summary.get("processed") or 0))
    orders = max(0, int((summary.get("shops") or {}).get("full") or 0))
    revenue = _to_decimal((summary.get("invoices") or {}).get("amount") or "0")
    day_status = _manager_day_status(owner, snapshot_date)

    axes = {
        "result": compute_ewr(orders=orders, contacts_processed=processed, revenue=revenue),
        "source_fairness": _compute_source_fairness(summary, sources),
        "process": _compute_process_axis(summary),
        "follow_up": _compute_follow_up_axis(summary),
        "data_quality": _compute_data_quality_axis(summary),
        "verified_communication": _compute_verified_communication_axis(summary, readiness),
    }
    base_mosaic = compute_mosaic(axes=axes, readiness=readiness)

    freshness_seconds = max(0, int((timezone.now() - stats_range.end).total_seconds()))
    confidence_inputs = _compute_confidence_inputs(
        owner=owner,
        snapshot_date=snapshot_date,
        processed=processed,
        readiness=readiness,
        freshness_seconds=freshness_seconds,
        provisional_mosaic=base_mosaic,
    )
    score_confidence = compute_score_confidence(**confidence_inputs)
    working_day_factor = _working_day_factor(owner, snapshot_date)
    duplicate_backlog = DuplicateReview.objects.filter(owner=owner, status=DuplicateReview.Status.OPEN).count()
    telephony_health = build_telephony_health_summary(owner=owner)
    gate_level, gate_score = compute_gate_level(
        paid_orders=int((summary.get("invoices") or {}).get("paid") or 0),
        approved_orders=int((summary.get("invoices") or {}).get("approved") or 0),
        crm_events=processed,
    )
    trust_multiplier = compute_production_trust(
        duplicate_backlog=duplicate_backlog,
        overdue_followups=int((summary.get("followups") or {}).get("missed_effective") or 0),
        telephony_healthy=telephony_health["status"] == "healthy",
        reason_quality=summary.get("pipeline", {}).get("reason_quality") or 1,
    )
    dampener_value = compute_dampener(axes=axes, readiness=readiness)
    onboarding_floor = compute_onboarding_floor_score(_manager_tenure_days(owner, snapshot_date))
    score_pipeline = apply_shadow_score_pipeline(
        base_mosaic=base_mosaic,
        gate_score=gate_score,
        trust_multiplier=trust_multiplier,
        dampener=dampener_value,
        readiness=readiness,
        gate_level=gate_level,
        onboarding_floor=onboarding_floor,
    )
    portfolio_health_state, rescue_top5 = _portfolio_health(summary)
    incidents = _incident_keys(
        summary=summary,
        freshness_seconds=freshness_seconds,
        duplicate_backlog=duplicate_backlog,
        telephony_status=telephony_health["status"],
    )
    report_block = summary.get("reports") or {}
    report_submitted = int(report_block.get("required") or 0) == 0 or int(report_block.get("missing") or 0) == 0
    earned_day = compute_earned_day_state(
        crm_contacts=processed,
        crm_updates=_crm_updates(summary),
        report_submitted=report_submitted,
        capacity_factor=float(working_day_factor),
        telephony_ready=bool(telephony_health.get("punitively_available")),
        meaningful_calls=int(telephony_health.get("meaningful_calls") or 0),
        meaningful_call_seconds_threshold=int(telephony_health.get("meaningful_call_seconds") or 30),
    )
    score_confidence_band = classify_confidence_band(score_confidence)
    top_drivers = [
        f"EWR {axes['result']}",
        f"Gate {gate_level}",
        f"Dampener {dampener_value}",
        f"Portfolio {portfolio_health_state}",
    ]
    top_recovery_actions = []
    if rescue_top5:
        top_recovery_actions.append("Review rescue top-5 before end of day")
    if int((summary.get("followups") or {}).get("missed_effective") or 0) > 0:
        top_recovery_actions.append("Close overdue follow-ups to reduce discipline drag")
    if earned_day["recovery_needed"]:
        top_recovery_actions.append("Recover minimum-vs-pace gap before report cutoff")

    payload_version = (cfg.payload_version if cfg else None) or versioned["formula_defaults"]["payload_version"]
    snapshot_schema_version = (cfg.snapshot_schema_version if cfg else None) or versioned["formula_defaults"]["snapshot_schema_version"]
    formula_version = (cfg.shadow_mosaic_formula_version if cfg else None) or "mosaic-v1"
    defaults_version = (cfg.defaults_version if cfg else None) or "2026-03-13"
    summary_block = {
        "processed": processed,
        "points": int(summary.get("points") or 0),
        "active_seconds": int(summary.get("active_seconds") or 0),
        "success_rate_pct": float(summary.get("success_rate_pct") or 0),
        "kpd": summary.get("kpd") or {},
        "followups": summary.get("followups") or {},
        "pipeline": summary.get("pipeline") or {},
        "reports": report_block,
        "invoices": summary.get("invoices") or {},
        "shops": summary.get("shops") or {},
    }

    return {
        "formula_version": formula_version,
        "defaults_version": defaults_version,
        "snapshot_schema_version": snapshot_schema_version,
        "payload_version": payload_version,
        "rollout_state": cfg.rollout_state if cfg else "shadow",
        "feature_flags": cfg.feature_flags if cfg else {},
        "formula_defaults": cfg.formula_defaults if cfg else {},
        "kpd_value": _to_decimal((summary.get("kpd") or {}).get("value") or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "mosaic_score": score_pipeline["final_mosaic"],
        "score_confidence": _to_decimal(score_confidence).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "working_day_factor": working_day_factor,
        "freshness_seconds": freshness_seconds,
        "payload": {
            "versions": {
                "formula_version": formula_version,
                "defaults_version": defaults_version,
                "payload_version": payload_version,
                "snapshot_schema_version": snapshot_schema_version,
            },
            "stats_range": {
                "period": stats_range.period,
                "from": snapshot_date.isoformat(),
                "to": snapshot_date.isoformat(),
                "label": stats_range.label,
            },
            "score": {
                "legacy_kpd": str(_to_decimal((summary.get("kpd") or {}).get("value") or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)),
                "shadow_mosaic": str(score_pipeline["final_mosaic"]),
                "base_mosaic": str(score_pipeline["base_mosaic"]),
                "ewr": str(axes["result"]),
                "score_confidence": str(_to_decimal(score_confidence).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)),
                "gate_level": gate_level,
                "gate_value": gate_score,
                "dampener_value": str(dampener_value),
                "trust_multiplier": str(trust_multiplier),
                "verified_slice": str(score_pipeline["verified_slice"]),
                "evidence_sensitive_slice": str(score_pipeline["evidence_sensitive_slice"]),
                "onboarding_floor": str(score_pipeline["onboarding_floor"]),
            },
            "confidence": {
                "verified_coverage": str(confidence_inputs["verified_coverage"]),
                "sample_sufficiency": str(confidence_inputs["sample_sufficiency"]),
                "stability": str(confidence_inputs["stability"]),
                "recency": str(confidence_inputs["recency"]),
            },
            "axes": {key: str(value) for key, value in axes.items()},
            "working_context": {
                "day_status": getattr(day_status, "status", ManagerDayStatus.Status.WORKING),
                "capacity_factor": str(getattr(day_status, "capacity_factor", working_day_factor)),
                "reintegration_flag": bool(getattr(day_status, "reintegration_flag", False)),
                "working_day_factor": str(working_day_factor),
                "source_reason": getattr(day_status, "source_reason", "") or "",
            },
            "dmt_earned_day": earned_day,
            "portfolio": {
                "portfolio_health_state": portfolio_health_state,
                "rescue_candidates": rescue_top5,
                "rescue_top5": rescue_top5,
                "churn_basis": rescue_top5[0]["churn_basis"] if rescue_top5 else "interim",
                "assignment_fairness": str(axes["source_fairness"]),
                "self_selected_mix": round(max([float(item.get("pct") or 0) for item in sources[:1]] or [0.0]), 1),
            },
            "ops": {
                "snapshot_freshness_seconds": freshness_seconds,
                "incident_keys": incidents,
                "stale_reason": "snapshot_stale" if freshness_seconds > 172800 else "",
            },
            "advice_context": {
                "top_drivers": top_drivers,
                "top_recovery_actions": top_recovery_actions,
                "explainability_tokens": [
                    f"gate:{gate_score}",
                    f"trust:{trust_multiplier}",
                    f"dampener:{dampener_value}",
                    f"confidence:{score_confidence_band}",
                ],
            },
            "summary": summary_block,
            "readiness": readiness,
            "confidence_inputs": {key: str(value) for key, value in confidence_inputs.items()},
            "result": {
                "ewr": str(axes["result"]),
                "orders": orders,
                "contacts_processed": processed,
                "revenue": str(revenue),
            },
            "trust": {
                "gate_level": gate_level,
                "gate_score": gate_score,
                "trust_multiplier": str(trust_multiplier),
                "reason_quality": str(_to_decimal(summary.get("pipeline", {}).get("reason_quality") or 1).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)),
                "dampener_value": str(dampener_value),
                "confidence_band": score_confidence_band,
                "pipeline": {key: str(value) for key, value in score_pipeline.items()},
            },
            "incidents": incidents,
            "portfolio_legacy": {
                "health_state": portfolio_health_state,
                "assignment_fairness": str(axes["source_fairness"]),
                "self_selected_mix": round(max([float(item.get("pct") or 0) for item in sources[:1]] or [0.0]), 1),
                "rescue_top5": rescue_top5,
            },
            "config_versions": versioned,
            "telephony_health": telephony_health,
            "meta": {
                "top_drivers": top_drivers,
                "confidence_band": score_confidence_band,
                "report_submitted": report_submitted,
                "tenure_days": _manager_tenure_days(owner, snapshot_date),
                "onboarding_floor": str(onboarding_floor),
                "telephony_suppressed": not bool(telephony_health.get("punitively_available")),
            },
        },
    }


def persist_nightly_snapshot(*, owner, snapshot_date: date, job_run: CommandRunLog | None = None) -> NightlyScoreSnapshot:
    shadow_payload = build_shadow_score_payload(owner=owner, snapshot_date=snapshot_date)
    snapshot, _ = NightlyScoreSnapshot.objects.update_or_create(
        owner=owner,
        snapshot_date=snapshot_date,
        defaults={
            "formula_version": shadow_payload["formula_version"],
            "defaults_version": shadow_payload["defaults_version"],
            "snapshot_schema_version": shadow_payload["snapshot_schema_version"],
            "payload_version": shadow_payload["payload_version"],
            "kpd_value": shadow_payload["kpd_value"],
            "mosaic_score": shadow_payload["mosaic_score"],
            "score_confidence": shadow_payload["score_confidence"],
            "working_day_factor": shadow_payload["working_day_factor"],
            "freshness_seconds": shadow_payload["freshness_seconds"],
            "payload": shadow_payload["payload"],
            "job_run": job_run,
        },
    )
    return snapshot
