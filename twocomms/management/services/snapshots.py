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
from management.services.score import compute_ewr, compute_mosaic, compute_score_confidence
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
    required = max(0, int(reports.get("required") or 0))
    missing_reports_ratio = Decimal(str((reports.get("missing") or 0) / max(1, required or 1))) if required else Decimal("0")
    return _clamp01(Decimal("1.0") - (missing_plan_ratio * Decimal("0.7")) - (missing_reports_ratio * Decimal("0.3")))


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


def _portfolio_health(summary: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    shops = summary.get("shops") or {}
    stale_list = shops.get("stale_shops_list") or []
    overdue_tests = shops.get("test_overdue_list") or []
    rescue_cases = []
    for row in overdue_tests[:5]:
        overdue_days = int(row.get("overdue_days") or 0)
        rescue_cases.append(
            {
                "id": row.get("id"),
                "name": row.get("name") or "Test shop",
                "value_at_risk": max(4000, 12000 - overdue_days * 180),
                "urgency": f"{overdue_days}d overdue",
                "confidence_badge": "MEDIUM",
                "churn_basis": "logistic",
            }
        )
    for row in stale_list[: max(0, 5 - len(rescue_cases))]:
        days_since = int(row.get("days_since") or 0)
        rescue_cases.append(
            {
                "id": row.get("id"),
                "name": row.get("name") or "Stale shop",
                "value_at_risk": max(2500, 8000 - days_since * 90),
                "urgency": f"{days_since}d stale",
                "confidence_badge": "LOW" if days_since < 14 else "MEDIUM",
                "churn_basis": "interim",
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

    axes = {
        "result": compute_ewr(orders=orders, contacts_processed=processed, revenue=revenue),
        "source_fairness": _compute_source_fairness(summary, sources),
        "process": _compute_process_axis(summary),
        "follow_up": _compute_follow_up_axis(summary),
        "data_quality": _compute_data_quality_axis(summary),
        "verified_communication": _compute_verified_communication_axis(summary, readiness),
    }
    mosaic_score = compute_mosaic(axes=axes, readiness=readiness)

    freshness_seconds = max(0, int((timezone.now() - stats_range.end).total_seconds()))
    confidence_inputs = _compute_confidence_inputs(
        owner=owner,
        snapshot_date=snapshot_date,
        processed=processed,
        readiness=readiness,
        freshness_seconds=freshness_seconds,
        provisional_mosaic=mosaic_score,
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
    )
    dampener_value = compute_dampener(axes=axes, readiness=readiness)
    portfolio_health_state, rescue_top5 = _portfolio_health(summary)
    incidents = _incident_keys(
        summary=summary,
        freshness_seconds=freshness_seconds,
        duplicate_backlog=duplicate_backlog,
        telephony_status=telephony_health["status"],
    )

    return {
        "formula_version": (cfg.shadow_mosaic_formula_version if cfg else None) or "mosaic-v1",
        "defaults_version": cfg.defaults_version if cfg else "2026-03-13",
        "snapshot_schema_version": cfg.snapshot_schema_version if cfg else "v1",
        "payload_version": cfg.payload_version if cfg else "v2",
        "rollout_state": cfg.rollout_state if cfg else "shadow",
        "feature_flags": cfg.feature_flags if cfg else {},
        "formula_defaults": cfg.formula_defaults if cfg else {},
        "kpd_value": _to_decimal((summary.get("kpd") or {}).get("value") or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "mosaic_score": _to_decimal(mosaic_score).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "score_confidence": _to_decimal(score_confidence).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "working_day_factor": working_day_factor,
        "freshness_seconds": freshness_seconds,
        "payload": {
            "stats_range": {
                "period": stats_range.period,
                "from": snapshot_date.isoformat(),
                "to": snapshot_date.isoformat(),
                "label": stats_range.label,
            },
            "summary": {
                "processed": processed,
                "points": int(summary.get("points") or 0),
                "active_seconds": int(summary.get("active_seconds") or 0),
                "success_rate_pct": float(summary.get("success_rate_pct") or 0),
                "kpd": summary.get("kpd") or {},
                "followups": summary.get("followups") or {},
                "pipeline": summary.get("pipeline") or {},
                "reports": summary.get("reports") or {},
                "invoices": summary.get("invoices") or {},
                "shops": summary.get("shops") or {},
            },
            "axes": {key: str(value) for key, value in axes.items()},
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
                "dampener_value": str(dampener_value),
                "confidence_band": classify_confidence_band(score_confidence),
            },
            "incidents": incidents,
            "portfolio": {
                "health_state": portfolio_health_state,
                "assignment_fairness": str(axes["source_fairness"]),
                "self_selected_mix": round(max([float(item.get("pct") or 0) for item in sources[:1]] or [0.0]), 1),
                "rescue_top5": rescue_top5,
            },
            "config_versions": versioned,
            "telephony_health": telephony_health,
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
