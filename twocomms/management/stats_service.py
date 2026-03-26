from __future__ import annotations

import hashlib

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.core.cache import cache
from django.db.models import Count, F, Max, Q, Sum
from django.db.models.functions import Abs, TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import (
    CallRecord,
    Client,
    ClientFollowUp,
    CommercialOfferEmailLog,
    ManagementDailyActivity,
    ManagementStatsAdviceDismissal,
    ManagementStatsConfig,
    NightlyScoreSnapshot,
    OwnershipChangeLog,
    Report,
    ScoreAppeal,
    Shop,
    ShopCommunication,
    ShopInventoryMovement,
    ShopShipment,
)
from .services.advice import build_action_stack, build_why_changed_today
from .services.appeals import summarize_appeals
from .services.config_versions import get_management_config
from .services.forecast import build_forecast_band, build_salary_simulator
from .services.outcomes import RESULTS_REQUIRING_REASON, summarize_reason_quality
from .services.telephony import build_telephony_health_summary
from .services.trust import classify_confidence_band
from .services.ui_labels import (
    normalize_shadow_phrase,
    normalize_shadow_urgency,
    translate_churn_basis,
    translate_confidence_band,
    translate_gate_level,
    translate_incident_key,
    translate_readiness_key,
    translate_readiness_state,
    translate_surface_state,
)
from .services.visible_points import visible_points_sum_expr


@dataclass(frozen=True)
class StatsRange:
    period: str
    start: datetime  # inclusive, aware
    end: datetime  # exclusive, aware
    start_date: date
    end_date: date
    label: str

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


FOLLOWUP_PLAN_CALL_RESULTS = {
    Client.CallResult.SENT_EMAIL,
    Client.CallResult.SENT_MESSENGER,
    Client.CallResult.WROTE_IG,
    Client.CallResult.THINKING,
    Client.CallResult.WAITING_PAYMENT,
    Client.CallResult.WAITING_PREPAYMENT,
}

SHADOW_ON_DEMAND_MIN_CLIENTS = 20
SHADOW_ON_DEMAND_MAX_DAYS = 366


def _start_of_local_day(d: date) -> datetime:
    tz = timezone.get_current_timezone()
    naive = datetime(d.year, d.month, d.day, 0, 0, 0)
    return timezone.make_aware(naive, tz)


def _build_range(period: str, from_date: date, to_date: date, *, label: str) -> StatsRange:
    start = _start_of_local_day(from_date)
    end = _start_of_local_day(to_date) + timedelta(days=1)
    return StatsRange(period=period, start=start, end=end, start_date=from_date, end_date=to_date, label=label)


def parse_stats_range(params: dict[str, Any], *, now: datetime | None = None) -> StatsRange:
    now_local = timezone.localtime(now or timezone.now())
    today = now_local.date()

    period = (params.get("period") or "today").strip().lower()
    if period not in {"today", "yesterday", "week", "month", "range"}:
        period = "today"

    if period == "today":
        return _build_range("today", today, today, label="Сьогодні")
    if period == "yesterday":
        d = today - timedelta(days=1)
        return _build_range("yesterday", d, d, label="Вчора")
    if period == "week":
        start = today - timedelta(days=6)
        return _build_range("week", start, today, label="Останні 7 днів")
    if period == "month":
        start = today - timedelta(days=29)
        return _build_range("month", start, today, label="Останні 30 днів")

    from_raw = (params.get("from") or "").strip()
    to_raw = (params.get("to") or "").strip()
    from_d = parse_date(from_raw) if from_raw else None
    to_d = parse_date(to_raw) if to_raw else None
    if not from_d or not to_d:
        start = today - timedelta(days=6)
        return _build_range("week", start, today, label="Останні 7 днів")

    if to_d < from_d:
        from_d, to_d = to_d, from_d

    # Safety cap to avoid pathological ranges in UI.
    if (to_d - from_d).days > 366:
        to_d = from_d + timedelta(days=366)

    label = f"{from_d.strftime('%d.%m.%Y')} — {to_d.strftime('%d.%m.%Y')}"
    return _build_range("range", from_d, to_d, label=label)


def previous_range(r: StatsRange) -> StatsRange:
    prev_to = r.start_date - timedelta(days=1)
    prev_from = prev_to - timedelta(days=(r.days - 1))
    return _build_range(f"prev_{r.period}", prev_from, prev_to, label="Попередній період")


def _points_sum_expr() -> Sum:
    return visible_points_sum_expr()


def _safe_pct(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return float(n) / float(d) * 100.0


def _format_hhmm(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}:{m:02d}"


def _get_or_build_config() -> dict[str, Any]:
    cache_key = "mgmt:stats:config:v2"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    cfg = ManagementStatsConfig.objects.filter(pk=1).first()
    versioned = get_management_config(cfg)
    kpd_weights = cfg.kpd_weights if cfg else {}
    thresholds = cfg.advice_thresholds if cfg else {}

    merged = {
        "kpd": {
            "active_norm_minutes": 240,
            "points_norm": 85,
            "max_effort": 2.2,
            "max_quality": 1.6,
            "max_ops": 1.2,
            "max_penalty": 0.6,
            **(kpd_weights or {}),
        },
        "advice": {
            "min_n_sources": 15,
            "min_n_strong": 20,
            "min_n_source_compare": 25,
            "min_source_diff": 0.25,
            "missed_followups_warn_pct": 8.0,
            "followup_plan_missing_warn": 3,
            "report_deadline_hour": 19,
            "report_late_grace_minutes": 60,
            "report_warn_late_days": 1,
            "report_warn_missing_days": 1,
            "stale_shop_days": 14,
            "stale_shop_warn": 2,
            "shops_next_contact_due_warn": 2,
            "test_overdue_warn": 1,
            **(thresholds or {}),
        },
        **versioned,
    }
    cache.set(cache_key, merged, 600)
    return merged


def _nested_get(payload: dict[str, Any], *path: str, default=None):
    node = payload
    for key in path:
        if not isinstance(node, dict):
            return default
        node = node.get(key)
        if node is None:
            return default
    return node


def _snapshot_decimal(snapshot_payload: dict[str, Any], *paths: tuple[str, ...], default: str = "0") -> Decimal:
    for path in paths:
        value = _nested_get(snapshot_payload, *path)
        if value not in (None, ""):
            try:
                return Decimal(str(value))
            except Exception:
                continue
    return Decimal(default)


def _average_decimal(values: list[Decimal], default: str = "0") -> Decimal:
    if not values:
        return Decimal(default)
    return (sum(values, Decimal("0")) / Decimal(str(len(values)))).quantize(Decimal("0.01"))


def _normalize_rescue_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item or {})
    confidence_code = str(normalized.get("confidence_badge") or "").upper()
    confidence_label = str(normalized.get("confidence_badge_label") or "").strip()
    if not confidence_label or confidence_label.upper() == confidence_code:
        normalized["confidence_badge_label"] = translate_confidence_band(confidence_code or confidence_label)

    normalized["urgency"] = normalize_shadow_urgency(normalized.get("urgency"))

    churn_basis = str(normalized.get("churn_basis") or "").strip()
    churn_label = str(normalized.get("churn_basis_label") or "").strip()
    if not churn_label or churn_label.lower() == churn_basis.lower():
        normalized["churn_basis_label"] = translate_churn_basis(churn_basis or churn_label)
    return normalized


def _aggregate_rescue_items(snapshots: list[NightlyScoreSnapshot]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        payload = snapshot.payload or {}
        rescue_items = (
            _nested_get(payload, "portfolio", "rescue_top5")
            or _nested_get(payload, "portfolio_legacy", "rescue_top5")
            or []
        )
        for item in rescue_items:
            name = str(item.get("name") or item.get("title") or "").strip()
            if not name:
                continue
            normalized_item = _normalize_rescue_item(item)
            current = by_name.get(name)
            if current is None or float(normalized_item.get("value_at_risk") or 0) > float(current.get("value_at_risk") or 0):
                by_name[name] = normalized_item
    return sorted(by_name.values(), key=lambda item: float(item.get("value_at_risk") or 0), reverse=True)[:5]


def _build_shadow_explain_payload(
    *,
    user,
    range_current: StatsRange,
    cfg: ManagementStatsConfig | None,
    score_payload: dict[str, Any],
    latest_payload: dict[str, Any],
) -> dict[str, Any]:
    readiness = latest_payload.get("readiness") or {}
    axes = latest_payload.get("axes") or {}
    weight_config = ((_get_or_build_config().get("mosaic_config") or {}).get("weights") or {})
    explain_axes = {}
    for key, value in axes.items():
        explain_axes[key] = {
            "key_label": translate_readiness_key(key),
            "value": float(Decimal(str(value))),
            "weight": float(weight_config.get(key, 0)),
            "status": str(readiness.get(key) or "shadow").upper(),
            "status_label": translate_readiness_state(readiness.get(key) or "shadow"),
        }
    explainability_tokens = _nested_get(latest_payload, "advice_context", "explainability_tokens", default=[]) or []
    return {
        "manager_id": user.id,
        "period": range_current.period,
        "formula_version": (cfg.shadow_mosaic_formula_version if cfg else None) or "mosaic-v1",
        "defaults_version": (cfg.defaults_version if cfg else None) or "2026-03-13",
        "readiness_state": score_payload["surface_state"],
        "readiness_state_label": translate_surface_state(score_payload["surface_state"]),
        "base_mosaic": float(score_payload.get("base_mosaic") or 0),
        "final_mosaic": float(score_payload.get("mosaic_score") or 0),
        "score_confidence": {
            "value": float(score_payload.get("score_confidence") or 0),
            "band": score_payload.get("confidence_band") or "LOW",
            "band_label": translate_confidence_band(score_payload.get("confidence_band") or "LOW"),
        },
        "gate": {
            "level": score_payload.get("gate_level") or "Self-reported only",
            "level_label": translate_gate_level(score_payload.get("gate_level") or "Self-reported only"),
            "value": int(score_payload.get("gate_score") or 45),
        },
        "axes": explain_axes,
        "freshness": {
            "seconds": int(score_payload.get("freshness_seconds") or 0),
            "stale": bool(score_payload["flags"]["is_stale"]),
        },
        "top_drivers": explainability_tokens or (score_payload.get("top_drivers") or []),
    }


def _build_recent_timeline(*, user, range_current: StatsRange, limit: int = 12) -> list[dict[str, Any]]:
    from orders.models import WholesaleInvoice

    events: list[dict[str, Any]] = []

    for row in (
        CommercialOfferEmailLog.objects.filter(owner=user, created_at__gte=range_current.start, created_at__lt=range_current.end)
        .order_by("-created_at")[: limit]
    ):
        events.append(
            {
                "kind": "email",
                "when": timezone.localtime(row.created_at),
                "title": row.recipient_name or row.recipient_email or "Комерційна пропозиція",
                "detail": row.subject or "КП надіслано",
                "badge": "КП email",
            }
        )

    for row in (
        ShopCommunication.objects.filter(created_by=user, created_at__gte=range_current.start, created_at__lt=range_current.end)
        .select_related("shop")
        .order_by("-created_at")[: limit]
    ):
        events.append(
            {
                "kind": "shop_comm",
                "when": timezone.localtime(row.created_at),
                "title": getattr(row.shop, "name", "") or "Комунікація по магазину",
                "detail": row.note or row.contact_person or "Комунікацію зафіксовано",
                "badge": "Нотатка",
            }
        )

    for row in (
        ClientFollowUp.objects.filter(owner=user)
        .filter(Q(scheduled_at__gte=range_current.start, scheduled_at__lt=range_current.end) | Q(closed_at__gte=range_current.start, closed_at__lt=range_current.end))
        .select_related("client")
        .order_by("-scheduled_at", "-closed_at")[: limit]
    ):
        event_dt = row.closed_at or row.scheduled_at or row.due_at
        if not event_dt:
            continue
        events.append(
            {
                "kind": "followup",
                "when": timezone.localtime(event_dt),
                "title": getattr(row.client, "shop_name", "") or "Передзвон",
                "detail": row.get_status_display(),
                "badge": "Передзвон",
            }
        )

    for row in (
        CallRecord.objects.filter(manager=user, created_at__gte=range_current.start, created_at__lt=range_current.end)
        .order_by("-created_at")[: limit]
    ):
        event_dt = row.started_at or row.created_at
        events.append(
            {
                "kind": "call",
                "when": timezone.localtime(event_dt),
                "title": row.phone or "Дзвінок",
                "detail": f"{row.duration_seconds}s • {row.direction}",
                "badge": "Дзвінок",
            }
        )

    for row in (
        WholesaleInvoice.objects.filter(created_by=user, created_at__gte=range_current.start, created_at__lt=range_current.end)
        .order_by("-created_at")[: limit]
    ):
        events.append(
            {
                "kind": "invoice",
                "when": timezone.localtime(row.created_at),
                "title": f"Накладна #{row.invoice_number}",
                "detail": f"{row.total_amount} грн • {row.payment_status}",
                "badge": "Накладна",
            }
        )

    for row in (
        OwnershipChangeLog.objects.filter(Q(previous_owner=user) | Q(new_owner=user), created_at__gte=range_current.start, created_at__lt=range_current.end)
        .order_by("-created_at")[: limit]
    ):
        events.append(
            {
                "kind": "ownership",
                "when": timezone.localtime(row.created_at),
                "title": f"Зміна відповідального #{row.entity_id}",
                "detail": row.reason or row.entity_type,
                "badge": "Передача",
            }
        )

    events.sort(key=lambda item: item["when"], reverse=True)
    timeline = []
    for item in events[:limit]:
        timeline.append(
            {
                **item,
                "when_label": item["when"].strftime("%d.%m %H:%M"),
            }
        )
    return timeline


def _shadow_score_payload(*, user, range_current: StatsRange) -> dict[str, Any]:
    snapshots = list(
        NightlyScoreSnapshot.objects.filter(
            owner=user,
            snapshot_date__gte=range_current.start_date,
            snapshot_date__lte=range_current.end_date,
        ).order_by("snapshot_date")
    )
    cfg = ManagementStatsConfig.objects.filter(pk=1).first()
    rollout_state = (cfg.rollout_state if cfg else "shadow") or "shadow"
    feature_flags = cfg.feature_flags if cfg else {}

    if not snapshots:
        return {
            "snapshot_id": None,
            "state": rollout_state,
            "state_label": translate_surface_state(rollout_state),
            "surface_state": "STALE",
            "snapshot_date": "",
            "mosaic_score": None,
            "base_mosaic": None,
            "score_confidence": None,
            "working_day_factor": None,
            "freshness_seconds": None,
            "kpd_value": None,
            "ewr": None,
            "gate_level": "Self-reported only",
            "gate_level_label": translate_gate_level("Self-reported only"),
            "gate_score": 45,
            "dampener_value": 1.0,
            "confidence_band": "LOW",
            "confidence_band_label": translate_confidence_band("LOW"),
            "incident_keys": ["SNAPSHOT_STALE"],
            "incident_labels": [translate_incident_key("SNAPSHOT_STALE")],
            "portfolio_health_state": "Unknown",
            "rescue_top5": [],
            "must_do_today": [],
            "best_opportunities": [],
            "why_changed_today": [],
            "salary_simulator": {},
            "readiness": {},
            "readiness_items": [],
            "aggregation": {
                "expected_days": range_current.days,
                "available_days": 0,
                "missing_days": [],
            },
            "explain": {},
            "flags": {
                "is_stale": True,
                "is_low_confidence": False,
                "is_partial": False,
                "has_snapshot": False,
            },
            "appeals": {"total": 0, "open": 0, "latest_status": "", "nearest_due_at": ""},
            "pace_state": "recovery",
            "pace_label": "Потрібне відновлення",
            "rollout_state": rollout_state,
            "feature_flags": feature_flags,
            "previous_period": {},
            "delta_vs_prev": None,
        }

    snapshot = snapshots[-1]
    snapshot_payload = snapshot.payload or {}
    latest_payload = snapshot_payload
    expected_days = range_current.days
    available_days = len(snapshots)
    available_dates = {item.snapshot_date for item in snapshots}
    missing_days = [
        (range_current.start_date + timedelta(days=offset)).isoformat()
        for offset in range(expected_days)
        if (range_current.start_date + timedelta(days=offset)) not in available_dates
    ]
    is_partial = bool(missing_days)
    is_stale = snapshot.snapshot_date < range_current.end_date or int(snapshot.freshness_seconds or 0) > 172800
    mosaic_score = _average_decimal([Decimal(str(item.mosaic_score or 0)) for item in snapshots])
    base_mosaic = _average_decimal(
        [
            _snapshot_decimal(item.payload or {}, ("score", "base_mosaic"), default=str(item.mosaic_score or 0))
            for item in snapshots
        ]
    )
    score_confidence = float(_average_decimal([Decimal(str(item.score_confidence or 0)) for item in snapshots]))
    working_day_factor = float(_average_decimal([Decimal(str(item.working_day_factor or 0)) for item in snapshots]))
    freshness_seconds = max(int(item.freshness_seconds or 0) for item in snapshots)
    kpd_value = float(_average_decimal([Decimal(str(item.kpd_value or 0)) for item in snapshots]))
    is_low_confidence = score_confidence < 0.65
    readiness = latest_payload.get("readiness") or {}
    result_block = latest_payload.get("result") or {}
    trust_block = latest_payload.get("trust") or {}
    portfolio = _nested_get(latest_payload, "portfolio", default={}) or {}
    incidents = sorted(
        {
            incident
            for item in snapshots
            for incident in ((_nested_get(item.payload or {}, "ops", "incident_keys") or item.payload.get("incidents") or []))
        }
    )
    incident_labels = [translate_incident_key(incident) for incident in incidents]
    rescue_top5 = _aggregate_rescue_items(snapshots)
    appeals_summary = summarize_appeals(snapshot)
    surface_state = "PARTIAL" if is_partial else ("STALE" if is_stale else rollout_state.upper())
    top_drivers = [normalize_shadow_phrase(item) for item in (_nested_get(latest_payload, "advice_context", "top_drivers", default=[]) or [])]
    v7_payload = latest_payload.get("v7") or {}

    payload = {
        "snapshot_id": snapshot.id,
        "state": rollout_state,
        "state_label": translate_surface_state(surface_state),
        "surface_state": surface_state,
        "snapshot_date": snapshot.snapshot_date.isoformat(),
        "mosaic_score": float(mosaic_score),
        "base_mosaic": float(base_mosaic),
        "score_confidence": score_confidence,
        "working_day_factor": working_day_factor,
        "freshness_seconds": freshness_seconds,
        "kpd_value": kpd_value,
        "ewr": float(result_block.get("ewr") or 0),
        "gate_level": trust_block.get("gate_level") or "Self-reported only",
        "gate_level_label": translate_gate_level(trust_block.get("gate_level") or "Self-reported only"),
        "gate_score": int(trust_block.get("gate_score") or 45),
        "dampener_value": float(trust_block.get("dampener_value") or 1),
        "trust_multiplier": float(trust_block.get("trust_multiplier") or 1),
        "confidence_band": trust_block.get("confidence_band") or classify_confidence_band(score_confidence),
        "confidence_band_label": translate_confidence_band(
            trust_block.get("confidence_band") or classify_confidence_band(score_confidence)
        ),
        "incident_keys": incidents,
        "incident_labels": incident_labels,
        "portfolio_health_state": portfolio.get("portfolio_health_state") or portfolio.get("health_state") or "Watch",
        "rescue_top5": rescue_top5 or [_normalize_rescue_item(item) for item in (portfolio.get("rescue_top5") or [])],
        "readiness": readiness,
        "readiness_items": [
            {
                "key": key,
                "key_label": translate_readiness_key(key),
                "state": state,
                "state_label": translate_readiness_state(state),
            }
            for key, state in readiness.items()
        ],
        "aggregation": {
            "expected_days": expected_days,
            "available_days": available_days,
            "missing_days": missing_days,
        },
        "dmt_earned_day": _nested_get(latest_payload, "dmt_earned_day", default={}) or {},
        "telephony_health": _nested_get(latest_payload, "telephony_health", default={}) or {},
        "top_drivers": top_drivers,
        "flags": {
            "is_stale": is_stale,
            "is_low_confidence": is_low_confidence,
            "is_partial": is_partial,
            "has_snapshot": True,
        },
        "appeals": appeals_summary,
        "rollout_state": rollout_state,
        "feature_flags": feature_flags,
        "v7": v7_payload,
    }
    earned_day = payload.get("dmt_earned_day") or {}
    if earned_day.get("target_pace_achieved"):
        payload["pace_state"] = "target"
        payload["pace_label"] = "Цільовий темп виконано"
    elif earned_day.get("minimum_achieved"):
        payload["pace_state"] = "minimum"
        payload["pace_label"] = "Мінімум дня виконано"
    else:
        payload["pace_state"] = "recovery"
        payload["pace_label"] = "Потрібне відновлення"
    payload["explain"] = _build_shadow_explain_payload(
        user=user,
        range_current=range_current,
        cfg=cfg,
        score_payload=payload,
        latest_payload=latest_payload,
    )
    return payload


def _compute_report_status(report_dt_local: datetime, *, deadline_hour: int, grace_minutes: int) -> str:
    """
    Returns: on_time | late
    Late is defined as sending more than grace_minutes after deadline_hour.
    """
    deadline = report_dt_local.replace(hour=int(deadline_hour), minute=0, second=0, microsecond=0)
    late_after = deadline + timedelta(minutes=int(grace_minutes))
    return "late" if report_dt_local > late_after else "on_time"


def compute_kpd(metrics: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    kcfg = (config.get("kpd") or {}) if isinstance(config, dict) else {}

    active_minutes = float(metrics.get("active_seconds", 0) or 0) / 60.0
    points = float(metrics.get("points", 0) or 0)
    processed = float(metrics.get("processed", 0) or 0)

    # Effort (0..~2.2)
    active_norm = float(kcfg.get("active_norm_minutes", 240) or 240)
    points_norm = float(kcfg.get("points_norm", 85) or 85)
    effort_active = 0.0 if active_minutes <= 0 else min(1.0, (active_minutes / max(1.0, active_norm)) ** 0.6)
    effort_points = 0.0 if points <= 0 else min(1.2, (points / max(1.0, points_norm)) ** 0.55 * 1.2)
    effort = min(float(kcfg.get("max_effort", 2.2) or 2.2), effort_active + effort_points)

    # Quality (0..~1.6) with smoothing
    success_weighted = float(metrics.get("success_weighted", 0) or 0)
    quality_smoothed = (success_weighted + 1.0) / (processed + 5.0) if processed >= 0 else 0.0
    quality = min(float(kcfg.get("max_quality", 1.6) or 1.6), quality_smoothed * 2.0)

    # Ops (0..~1.2)
    cp_sent = float(metrics.get("cp_email_sent", 0) or 0)
    shops_created = float(metrics.get("shops_created", 0) or 0)
    invoices_created = float(metrics.get("invoices_created", 0) or 0)
    ops = min(float(kcfg.get("max_ops", 1.2) or 1.2), min(0.4, cp_sent / 5.0 * 0.4) + min(0.4, shops_created / 2.0 * 0.4) + min(0.4, invoices_created / 2.0 * 0.4))

    # Discipline penalty (0..~0.6)
    followups_total = float(metrics.get("followups_total", 0) or 0)
    followups_missed = float(metrics.get("followups_missed", 0) or 0)
    missed_rate = (followups_missed / followups_total) if followups_total > 0 else 0.0
    missed_rate *= min(1.0, followups_total / 5.0)  # low-volume protection

    report_days_required = float(metrics.get("report_days_required", 0) or 0)
    report_days_late = float(metrics.get("report_days_late", 0) or 0)
    report_days_missing = float(metrics.get("report_days_missing", 0) or 0)
    report_late_rate = (report_days_late / report_days_required) if report_days_required > 0 else 0.0
    report_late_rate *= min(1.0, report_days_required / 3.0)

    report_missing_rate = (report_days_missing / report_days_required) if report_days_required > 0 else 0.0
    report_missing_rate *= min(1.0, report_days_required / 3.0)

    followup_plan_missing = float(metrics.get("followup_plan_missing", 0) or 0)
    followup_plan_missing_rate = (followup_plan_missing / processed) if processed > 0 else 0.0
    followup_plan_missing_rate *= min(1.0, processed / 5.0)  # low-volume protection
    followup_plan_penalty = min(0.2, followup_plan_missing_rate * 0.3)

    penalty = min(
        float(kcfg.get("max_penalty", 0.6) or 0.6),
        missed_rate * 0.8 + report_late_rate * 0.25 + report_missing_rate * 0.5 + followup_plan_penalty,
    )

    raw = effort + quality + ops
    value = max(0.0, round(raw * (1.0 - penalty), 2))

    return {
        "value": value,
        "raw": round(raw, 2),
        "effort": round(effort, 2),
        "quality": round(quality, 2),
        "ops": round(ops, 2),
        "penalty": round(penalty, 3),
        "breakdown": {
            "effort_active": round(effort_active, 3),
            "effort_points": round(effort_points, 3),
            "quality_smoothed": round(quality_smoothed, 3),
            "missed_rate": round(missed_rate, 3),
            "report_late_rate": round(report_late_rate, 3),
            "report_missing_rate": round(report_missing_rate, 3),
            "followup_plan_missing_rate": round(followup_plan_missing_rate, 3),
        },
    }


def _dismissed_keys(user_id: int) -> set[str]:
    now = timezone.now()
    qs = ManagementStatsAdviceDismissal.objects.filter(user_id=user_id).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return set(qs.values_list("key", flat=True))


def generate_advice(
    *,
    user_id: int,
    range_current: StatsRange,
    range_prev: StatsRange,
    metrics_now: dict[str, Any],
    metrics_prev: dict[str, Any],
    sources_now: list[dict[str, Any]],
    series: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    acfg = config.get("advice") if isinstance(config, dict) else {}
    min_n_strong = int(acfg.get("min_n_strong", 20) or 20)
    min_n_sources = int(acfg.get("min_n_sources", 15) or 15)
    min_n_source_compare = int(acfg.get("min_n_source_compare", 25) or 25)
    min_source_diff = float(acfg.get("min_source_diff", 0.25) or 0.25)
    warn_pct = float(acfg.get("missed_followups_warn_pct", 8.0) or 8.0)
    followup_plan_missing_warn = int(acfg.get("followup_plan_missing_warn", 3) or 3)
    report_warn_late_days = int(acfg.get("report_warn_late_days", 1) or 1)
    report_warn_missing_days = int(acfg.get("report_warn_missing_days", 1) or 1)
    stale_shop_warn = int(acfg.get("stale_shop_warn", 2) or 2)
    shops_next_contact_due_warn = int(acfg.get("shops_next_contact_due_warn", 2) or 2)
    test_overdue_warn = int(acfg.get("test_overdue_warn", 1) or 1)

    dismissed = _dismissed_keys(user_id)
    items: list[dict[str, Any]] = []

    def add(item: dict[str, Any]):
        key = str(item.get("key") or "").strip()
        if not key or key in dismissed:
            return
        items.append(item)

    # 1) Productivity trend (points per active hour)
    active_h_now = float(metrics_now.get("active_seconds", 0) or 0) / 3600.0
    active_h_prev = float(metrics_prev.get("active_seconds", 0) or 0) / 3600.0
    pph_now = (float(metrics_now.get("points", 0) or 0) / active_h_now) if active_h_now > 0 else 0.0
    pph_prev = (float(metrics_prev.get("points", 0) or 0) / active_h_prev) if active_h_prev > 0 else 0.0

    processed_now = int(metrics_now.get("processed", 0) or 0)
    processed_prev = int(metrics_prev.get("processed", 0) or 0)

    if processed_now >= min_n_strong and processed_prev >= min_n_strong and pph_prev > 0:
        delta = (pph_now - pph_prev) / pph_prev
        if delta >= 0.2:
            add(
                {
                    "key": f"prod_pph_up:{range_current.start_date}:{range_current.end_date}",
                    "tone": "good",
                    "title": "Продуктивність зросла",
                    "text": "Схоже, ви робите більше результату за годину активної роботи.",
                    "evidence": f"{pph_prev:.1f} → {pph_now:.1f} бал/год, період: {range_current.label}",
                    "assumption": True,
                    "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1)).isoformat(),
                }
            )
        elif delta <= -0.2:
            add(
                {
                    "key": f"prod_pph_down:{range_current.start_date}:{range_current.end_date}",
                    "tone": "bad",
                    "title": "Продуктивність просіла",
                    "text": "Може бути, що стало більше «низьковартісних» дій або менше фокусу на конверсію.",
                    "evidence": f"{pph_prev:.1f} → {pph_now:.1f} бал/год, період: {range_current.label}",
                    "assumption": True,
                    "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1)).isoformat(),
                }
            )

    # 2) Follow-ups discipline
    fu_total = int(metrics_now.get("followups_total", 0) or 0)
    fu_missed = int(metrics_now.get("followups_missed", 0) or 0)
    fu_rate = _safe_pct(fu_missed, fu_total)
    if fu_total >= min_n_strong and fu_rate > warn_pct:
        add(
            {
                "key": f"followups_missed:{range_current.start_date}:{range_current.end_date}",
                "tone": "bad",
                "title": "Увага: багато пропущених передзвонів",
                "text": "Увага: ви не обробляєте клієнтів, з якими домовляєтесь про передзвон — це знижує конверсію.",
                "evidence": f"Пропущено: {fu_missed}/{fu_total} ({fu_rate:.1f}%)",
                "assumption": True,
                "cta": {"label": "Підключити Telegram-нагадування", "action": "open_profile_bot"},
                "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1)).isoformat(),
            }
        )
    elif fu_total >= min_n_strong and fu_missed == 0:
        add(
            {
                "key": f"followups_good:{range_current.start_date}:{range_current.end_date}",
                "tone": "good",
                "title": "Дисципліна передзвонів ок",
                "text": "За цей період немає пропущених передзвонів у статистиці — гарний сигнал для конверсії.",
                "evidence": f"Передзвони: {fu_total}, пропущено: 0, період: {range_current.label}",
                "assumption": True,
                "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=2)).isoformat(),
            }
        )

    # 3) Sources: suggest testing low-usage sources (no strong claims)
    for s in sources_now[:6]:
        code = str(s.get("code") or "")
        cnt = int(s.get("count") or 0)
        if code in {"google_maps", "forums"} and cnt < max(1, min_n_sources // 3):
            add(
                {
                    "key": f"source_test:{code}:{range_current.start_date}:{range_current.end_date}",
                    "tone": "neutral",
                    "title": "Можна протестувати джерело",
                    "text": f"За період мало лідів з «{s.get('label')}». Можливо, варто дати цьому джерелу невеликий тест (без сильних висновків).",
                    "evidence": f"{s.get('label')}: {cnt} лідів за період {range_current.label}",
                    "assumption": True,
                    "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=2)).isoformat(),
                }
            )

    # 4) Active time vs results (last 3 days)
    if isinstance(series, list) and len(series) >= 3:
        last3 = series[-3:]
        active_avg = sum(int(d.get("active_seconds") or 0) for d in last3) / 3.0
        success_sum = sum(float(d.get("success_weighted") or 0.0) for d in last3)
        processed_sum = sum(int(d.get("clients") or 0) for d in last3)
        if processed_sum >= min_n_sources and success_sum <= 0.0 and active_avg < 3 * 3600:
            add(
                {
                    "key": f"active_low_no_success:last3:{range_current.end_date}",
                    "tone": "neutral",
                    "title": "Мало активного часу + немає результатів",
                    "text": "За останні 3 дні активний час низький, і немає результативних переходів (замовлення/тест/XML). Можливо, варто збільшити фокус-час або переглянути сценарій обробки.",
                    "evidence": f"Середня активність: {_format_hhmm(int(active_avg))}/день, клієнтів: {processed_sum} за 3 дні",
                    "assumption": True,
                    "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1)).isoformat(),
                }
            )

    # 5) Report discipline (late/missing)
    rep_required = int(metrics_now.get("report_days_required", 0) or 0)
    rep_late = int(metrics_now.get("report_days_late", 0) or 0)
    rep_missing = int(metrics_now.get("report_days_missing", 0) or 0)
    if rep_required > 0:
        if rep_missing >= report_warn_missing_days:
            add(
                {
                    "key": f"reports_missing:{range_current.start_date}:{range_current.end_date}",
                    "tone": "bad",
                    "title": "Звітність: є пропуски",
                    "text": "Схоже, у частині робочих днів звіт не був відправлений. Це ускладнює контроль прогресу та планування.",
                    "evidence": f"Пропущено: {rep_missing}/{rep_required} дн, період: {range_current.label}",
                    "assumption": True,
                    "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1)).isoformat(),
                }
            )
        elif rep_late >= report_warn_late_days:
            add(
                {
                    "key": f"reports_late:{range_current.start_date}:{range_current.end_date}",
                    "tone": "neutral",
                    "title": "Звітність: є запізнення",
                    "text": "Частина звітів була відправлена із запізненням. Можливо, варто закріпити рутину закриття дня.",
                    "evidence": f"Запізнення: {rep_late}/{rep_required} дн, період: {range_current.label}",
                    "assumption": True,
                    "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1)).isoformat(),
                }
            )
        elif rep_required >= 3:
            add(
                {
                    "key": f"reports_good:{range_current.start_date}:{range_current.end_date}",
                    "tone": "good",
                    "title": "Звітність стабільна",
                    "text": "За період звіти виглядають стабільно (без пропусків і запізнень у робочі дні з активністю).",
                    "evidence": f"Вчасно: {rep_required}/{rep_required}, період: {range_current.label}",
                    "assumption": True,
                    "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=2)).isoformat(),
                }
            )

    # 6) Follow-up planning after key stages (CP / thinking / payment)
    plan_missing = int(metrics_now.get("followup_plan_missing", 0) or 0)
    if plan_missing >= followup_plan_missing_warn and processed_now >= max(1, min_n_sources // 2):
        add(
            {
                "key": f"followup_plan_missing:{range_current.start_date}:{range_current.end_date}",
                "tone": "neutral",
                "title": "Після етапів потрібен план передзвону",
                "text": "Є клієнти на етапах «КП / подумає / оплата», але без запланованого наступного контакту. Це може знижувати конверсію.",
                "evidence": f"Без плану: {plan_missing} клієнтів, період: {range_current.label}",
                "assumption": True,
                "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1)).isoformat(),
            }
        )

    # 7) Shops: stale contacts / next contact overdue / overdue tests
    stale_shops = int(metrics_now.get("stale_shops_count", 0) or 0)
    next_due = int(metrics_now.get("shops_next_contact_due_count", 0) or 0)
    overdue_tests = int(metrics_now.get("overdue_tests", 0) or 0)

    if stale_shops >= stale_shop_warn:
        add(
            {
                "key": f"shops_stale:{range_current.end_date}",
                "tone": "neutral",
                "title": "Є магазини без контакту давно",
                "text": "Є магазини, з якими давно не було комунікації. Можливо, варто зробити короткий повторний контакт (продажі/потреби/товар).",
                "evidence": f"Без контакту давно: {stale_shops} магазин(и)",
                "assumption": True,
                "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=2)).isoformat(),
            }
        )

    if next_due >= shops_next_contact_due_warn:
        add(
            {
                "key": f"shops_next_contact_due:{range_current.end_date}",
                "tone": "bad",
                "title": "Наступний контакт по магазинах прострочено",
                "text": "Є заплановані контакти по магазинах, але час вже настав. Це може впливати на утримання та повторні продажі.",
                "evidence": f"Прострочено контактів: {next_due}",
                "assumption": True,
                "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1)).isoformat(),
            }
        )

    if overdue_tests >= test_overdue_warn:
        add(
            {
                "key": f"tests_overdue:{range_current.end_date}",
                "tone": "neutral",
                "title": "Є прострочені тестові партії",
                "text": "У частини тестових магазинів минув період тесту. Можливо, варто уточнити результат і запропонувати перехід у повний магазин.",
                "evidence": f"Прострочених тестів: {overdue_tests}",
                "assumption": True,
                "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=2)).isoformat(),
            }
        )

    # 8) Sources: compare only with enough volume and material difference
    eligible = []
    for s in sources_now:
        try:
            cnt = int(s.get("count") or 0)
        except Exception:
            cnt = 0
        if cnt >= min_n_source_compare:
            eligible.append(s)
    if len(eligible) >= 2:
        eligible.sort(key=lambda x: float(x.get("success_rate") or 0.0))
        worst = eligible[0]
        best = eligible[-1]
        worst_rate = float(worst.get("success_rate") or 0.0)
        best_rate = float(best.get("success_rate") or 0.0)
        diff = best_rate - worst_rate
        if diff >= min_source_diff:
            add(
                {
                    "key": f"sources_compare:{range_current.start_date}:{range_current.end_date}",
                    "tone": "neutral",
                    "title": "Джерела відрізняються за «успішністю»",
                    "text": "Можливо, є сенс тимчасово змістити фокус у бік джерел із вищим індексом. Висновки робимо обережно — це припущення.",
                    "evidence": (
                        f"{worst.get('label')} ≈ {worst_rate * 100:.0f}% (n={int(worst.get('count') or 0)})"
                        f" → {best.get('label')} ≈ {best_rate * 100:.0f}% (n={int(best.get('count') or 0)}), "
                        f"мін. вибірка: {min_n_source_compare}"
                    ),
                    "assumption": True,
                    "expires_at": (timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=2)).isoformat(),
                }
            )

    # Sort by severity/tone (bad first, then neutral, then good)
    tone_rank = {"bad": 0, "neutral": 1, "good": 2}
    items.sort(key=lambda x: tone_rank.get(str(x.get("tone")), 9))
    return items[:8]


def _normalize_source(raw: str) -> tuple[str, str]:
    s = (raw or "").strip()
    if not s:
        return "unknown", "Не вказано"
    sl = s.lower()
    if "instagram" in sl:
        return "instagram", "Instagram"
    if "prom" in sl:
        return "prom_ua", "Prom.ua"
    if "google" in sl or "карти" in sl:
        return "google_maps", "Google Карти"
    if "форум" in sl or "сайт" in sl:
        return "forums", "Сайти / форуми"
    # stable per-raw bucket for custom sources
    digest = hashlib.md5(s.encode("utf-8")).hexdigest()[:10]
    return f"custom_{digest}", s


def _success_weight_for_call_result(code: str) -> float:
    code = (code or "").strip()
    return {
        Client.CallResult.ORDER: 1.0,
        Client.CallResult.TEST_BATCH: 0.8,
        Client.CallResult.WAITING_PAYMENT: 0.6,
        Client.CallResult.WAITING_PREPAYMENT: 0.5,
        Client.CallResult.XML_CONNECTED: 0.4,
    }.get(code, 0.0)


def _shadow_backfill_dates(*, user, range_current: StatsRange) -> list[date]:
    if range_current.days <= 0 or range_current.days > SHADOW_ON_DEMAND_MAX_DAYS:
        return []

    profile = getattr(user, "userprofile", None)
    is_management_subject = bool(
        getattr(profile, "is_manager", False) or user.is_staff or user.is_superuser
    )
    has_shadow_history = NightlyScoreSnapshot.objects.filter(owner=user).exists()
    total_processed = Client.objects.filter(owner=user).count()
    has_management_history = (
        has_shadow_history
        or total_processed >= SHADOW_ON_DEMAND_MIN_CLIENTS
        or ManagementDailyActivity.objects.filter(user=user).exists()
        or Report.objects.filter(owner=user).exists()
    )
    if not is_management_subject and not has_management_history:
        return []

    today = timezone.localdate()
    existing = {
        item.snapshot_date: item
        for item in NightlyScoreSnapshot.objects.filter(
            owner=user,
            snapshot_date__gte=range_current.start_date,
            snapshot_date__lte=range_current.end_date,
        )
    }

    refresh_dates: list[date] = []
    for offset in range(range_current.days):
        snapshot_date = range_current.start_date + timedelta(days=offset)
        snapshot = existing.get(snapshot_date)
        if snapshot is None:
            refresh_dates.append(snapshot_date)
            continue
        if snapshot_date < today and int(snapshot.freshness_seconds or 0) > 172800:
            refresh_dates.append(snapshot_date)
    return refresh_dates


def _ensure_shadow_snapshots_for_range(*, user, range_current: StatsRange) -> None:
    refresh_dates = _shadow_backfill_dates(user=user, range_current=range_current)
    if not refresh_dates:
        return

    from .services.snapshots import persist_nightly_snapshot

    for snapshot_date in refresh_dates:
        persist_nightly_snapshot(owner=user, snapshot_date=snapshot_date)


def get_stats_payload(*, user, range_current: StatsRange, include_shadow: bool = True) -> dict[str, Any]:
    cfg = _get_or_build_config()
    tz = timezone.get_current_timezone()
    prev_r = previous_range(range_current)

    if include_shadow:
        _ensure_shadow_snapshots_for_range(user=user, range_current=range_current)
        _ensure_shadow_snapshots_for_range(user=user, range_current=prev_r)

    cache_key = f"mgmt:stats:v6:{user.id}:{range_current.start_date}:{range_current.end_date}:{int(include_shadow)}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    now_dt = timezone.now()

    # Core clients (new in period)
    clients_qs = Client.objects.filter(owner=user, created_at__gte=range_current.start, created_at__lt=range_current.end)

    first_client_ts = (
        Client.objects.filter(owner=user)
        .order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    first_activity_date = timezone.localtime(first_client_ts).date() if first_client_ts else None
    days_working = (timezone.localdate() - first_activity_date).days + 1 if first_activity_date else 0

    processed = clients_qs.count()
    points = clients_qs.aggregate(points=_points_sum_expr()).get("points") or 0
    points_per_client = round((float(points) / float(processed)), 2) if processed > 0 else 0.0

    call_result_counts = (
        clients_qs.values("call_result")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    call_result_label = {k: str(v) for k, v in Client.CallResult.choices}
    role_label = {k: str(v) for k, v in Client.Role.choices}
    reason_capture = summarize_reason_quality(
        list(
            clients_qs.filter(call_result__in=RESULTS_REQUIRING_REASON).values(
                "call_result",
                "call_result_reason_code",
                "call_result_reason_note",
                "call_result_context",
            )
        )
    )
    reason_breakdown_map = {
        item["call_result"]: item["items"][:4]
        for item in reason_capture["breakdown"]
    }

    segments = []
    for row in call_result_counts:
        code = row.get("call_result") or ""
        cnt = int(row.get("count") or 0)
        if cnt <= 0:
            continue
        segments.append(
            {
                "code": code,
                "label": call_result_label.get(code, code),
                "count": cnt,
                "pct": round(_safe_pct(cnt, processed), 1),
                "success_weight": _success_weight_for_call_result(code),
            }
        )

    # Optional subtypes (only when details exist) — limited to avoid UI spam.
    seg_map = {s.get("code"): s for s in segments if s.get("code")}
    for code in ("other", "not_interested", "expensive", "no_answer", "invalid_number"):
        if code not in seg_map:
            continue
        sub = list(reason_breakdown_map.get(code) or [])
        if not sub:
            rows = (
                clients_qs.filter(call_result=code)
                .exclude(call_result_details__isnull=True)
                .exclude(call_result_details__exact="")
                .values("call_result_details")
                .annotate(count=Count("id"))
                .order_by("-count")[:4]
            )
            for rrow in rows:
                raw = str(rrow.get("call_result_details") or "").strip()
                if not raw:
                    continue
                label = raw.splitlines()[0].strip()
                if len(label) > 72:
                    label = label[:72].rstrip() + "…"
                sub.append({"label": label, "count": int(rrow.get("count") or 0)})
        if sub:
            seg_map[code]["subtypes"] = sub

    # Roles
    role_counts = clients_qs.values("role").annotate(count=Count("id")).order_by("-count")
    roles = []
    for row in role_counts:
        code = row.get("role") or ""
        cnt = int(row.get("count") or 0)
        if cnt <= 0:
            continue
        roles.append({"code": code, "label": role_label.get(code, code), "count": cnt, "pct": round(_safe_pct(cnt, processed), 1)})

    # Sources (with best-effort "quality" index from call_result weights)
    src_rows = clients_qs.values("source", "call_result").annotate(count=Count("id"))
    src_map: dict[str, dict[str, Any]] = {}
    for row in src_rows:
        raw = str(row.get("source") or "").strip()
        code, label = _normalize_source(raw)
        cnt = int(row.get("count") or 0)
        if cnt <= 0:
            continue
        bucket = src_map.setdefault(
            code,
            {"code": code, "label": label, "count": 0, "success_weighted": 0.0, "raw_set": set()},
        )
        bucket["count"] += cnt
        bucket["success_weighted"] += float(cnt) * _success_weight_for_call_result(str(row.get("call_result") or ""))
        if raw:
            bucket["raw_set"].add(raw)

    sources = []
    for b in src_map.values():
        cnt = int(b.get("count") or 0)
        sw = float(b.get("success_weighted") or 0.0)
        sources.append(
            {
                "code": b.get("code") or "",
                "label": b.get("label") or "",
                "count": cnt,
                "pct": round(_safe_pct(cnt, processed), 1),
                "success_weighted": round(sw, 2),
                "success_rate": round((sw + 1.0) / (cnt + 5.0), 3),  # smoothed
                "raw": sorted(list(b.get("raw_set") or []))[:6],
            }
        )
    sources.sort(key=lambda x: int(x.get("count") or 0), reverse=True)

    # Pipeline: missing follow-up plan for stages that typically require it
    plan_missing_qs = clients_qs.filter(call_result__in=FOLLOWUP_PLAN_CALL_RESULTS, next_call_at__isnull=True)
    followup_plan_missing = plan_missing_qs.count()
    followup_plan_missing_by = []
    for row in plan_missing_qs.values("call_result").annotate(count=Count("id")).order_by("-count"):
        code = row.get("call_result") or ""
        cnt = int(row.get("count") or 0)
        if cnt <= 0:
            continue
        followup_plan_missing_by.append({"code": code, "label": call_result_label.get(code, code), "count": cnt})
    followup_plan_missing_examples = []
    for row in plan_missing_qs.order_by("-created_at").values("id", "shop_name", "phone", "call_result", "created_at")[:8]:
        ts = row.get("created_at")
        followup_plan_missing_examples.append(
            {
                "id": int(row.get("id") or 0),
                "shop": row.get("shop_name") or "",
                "phone": row.get("phone") or "",
                "stage": call_result_label.get(row.get("call_result") or "", row.get("call_result") or ""),
                "created_at": timezone.localtime(ts).isoformat() if ts else "",
            }
        )
    plan_missing_by_day = {
        row["day"]: int(row.get("count") or 0)
        for row in plan_missing_qs.annotate(day=TruncDate("created_at", tzinfo=tz)).values("day").annotate(count=Count("id"))
        if row.get("day")
    }

    # Follow-ups
    today_local = timezone.localdate()
    fu_qs = ClientFollowUp.objects.filter(owner=user, due_date__gte=range_current.start_date, due_date__lte=range_current.end_date)
    fu_total = fu_qs.count()
    fu_missed = fu_qs.filter(status=ClientFollowUp.Status.MISSED).count()
    fu_done = fu_qs.filter(status=ClientFollowUp.Status.DONE).count()
    fu_rescheduled = fu_qs.filter(status=ClientFollowUp.Status.RESCHEDULED).count()
    fu_cancelled = fu_qs.filter(status=ClientFollowUp.Status.CANCELLED).count()
    fu_open = fu_qs.filter(status=ClientFollowUp.Status.OPEN).count()
    fu_overdue_open = fu_qs.filter(status=ClientFollowUp.Status.OPEN).filter(
        Q(grace_until__lt=timezone.now()) | Q(grace_until__isnull=True, due_at__lt=timezone.now())
    ).count()

    missed_effective = fu_missed + fu_overdue_open
    missed_rate = _safe_pct(missed_effective, fu_total)

    # Follow-ups: small "problem list" for on-demand details (missed + overdue open)
    fu_problem_list = []
    fu_problem_qs = (
        fu_qs.filter(
            Q(status=ClientFollowUp.Status.MISSED)
            | Q(status=ClientFollowUp.Status.OPEN, grace_until__lt=timezone.now())
            | Q(status=ClientFollowUp.Status.OPEN, grace_until__isnull=True, due_at__lt=timezone.now())
        )
        .select_related("client")
        .order_by("due_at")
    )
    for fu in fu_problem_qs[:10]:
        due_local = timezone.localtime(fu.due_at) if fu.due_at else None
        fu_problem_list.append(
            {
                "id": fu.id,
                "status": fu.status,
                "due_at": due_local.isoformat() if due_local else "",
                "due_label": due_local.strftime("%d.%m %H:%M") if due_local else "",
                "client_id": fu.client_id,
                "shop": getattr(fu.client, "shop_name", "") or "",
                "phone": getattr(fu.client, "phone", "") or "",
            }
        )

    # Activity (daily)
    act_qs = ManagementDailyActivity.objects.filter(user=user, date__gte=range_current.start_date, date__lte=range_current.end_date)
    active_seconds = int(act_qs.aggregate(s=Sum("active_seconds")).get("s") or 0)
    points_per_active_hour = round((float(points) / (float(active_seconds) / 3600.0)), 2) if active_seconds > 0 else 0.0

    # Reports discipline (per day)
    acfg = cfg.get("advice") or {}
    deadline_hour = int(acfg.get("report_deadline_hour", 19) or 19)
    grace = int(acfg.get("report_late_grace_minutes", 60) or 60)

    # Earliest report per day (portable): fetch ordered list and pick first per day.
    reports_list = list(Report.objects.filter(owner=user, created_at__gte=range_current.start, created_at__lt=range_current.end).order_by("created_at").values("created_at"))
    report_by_day: dict[date, datetime] = {}
    for r in reports_list:
        ts = r.get("created_at")
        if not ts:
            continue
        d = timezone.localtime(ts).date()
        if d not in report_by_day:
            report_by_day[d] = timezone.localtime(ts)

    # CP email logs
    cp_qs = CommercialOfferEmailLog.objects.filter(owner=user, created_at__gte=range_current.start, created_at__lt=range_current.end)
    cp_total = cp_qs.count()
    cp_sent = cp_qs.filter(status=CommercialOfferEmailLog.Status.SENT).count()
    cp_failed = cp_qs.filter(status=CommercialOfferEmailLog.Status.FAILED).count()
    cp_modes = list(cp_qs.values("mode").annotate(count=Count("id")).order_by("-count"))
    cp_segments = list(cp_qs.values("segment_mode").annotate(count=Count("id")).order_by("-count"))

    # Wholesale invoices (orders app)
    try:
        from orders.models import WholesaleInvoice
    except Exception:
        WholesaleInvoice = None

    invoices_qs = None
    invoices_created = 0
    invoices_amount = 0
    invoices_review = []
    invoices_payment = []
    invoices_paid = 0
    invoices_approved = 0

    if WholesaleInvoice is not None:
        invoices_qs = WholesaleInvoice.objects.filter(created_by=user, created_at__gte=range_current.start, created_at__lt=range_current.end)
        invoices_created = invoices_qs.count()
        invoices_amount = invoices_qs.aggregate(s=Sum("total_amount")).get("s") or 0
        invoices_review = list(invoices_qs.values("review_status").annotate(count=Count("id")).order_by("-count"))
        invoices_payment = list(invoices_qs.values("payment_status").annotate(count=Count("id")).order_by("-count"))
        invoices_paid = invoices_qs.filter(payment_status="paid").count()
        invoices_approved = invoices_qs.filter(is_approved=True).count()

    # Shops
    shops_qs = Shop.objects.filter(created_by=user, created_at__gte=range_current.start, created_at__lt=range_current.end)
    shops_created = shops_qs.count()
    shops_test = shops_qs.filter(shop_type=Shop.ShopType.TEST).count()
    shops_full = shops_qs.filter(shop_type=Shop.ShopType.FULL).count()

    clients_by_day = (
        clients_qs.annotate(day=TruncDate("created_at", tzinfo=tz))
        .values("day")
        .annotate(count=Count("id"), points=_points_sum_expr())
    )
    day_map: dict[date, dict[str, Any]] = {}
    for row in clients_by_day:
        d = row.get("day")
        if not d:
            continue
        day_map[d] = {
            "date": d.isoformat(),
            "clients": int(row.get("count") or 0),
            "points": int(row.get("points") or 0),
        }

    # Success weighted by day (best-effort via current call_result)
    success_by_day: dict[date, float] = {}
    cr_by_day = (
        clients_qs.annotate(day=TruncDate("created_at", tzinfo=tz))
        .values("day", "call_result")
        .annotate(count=Count("id"))
    )
    for row in cr_by_day:
        d = row.get("day")
        if not d:
            continue
        success_by_day[d] = float(success_by_day.get(d, 0.0)) + float(row.get("count") or 0) * _success_weight_for_call_result(row.get("call_result") or "")

    # Activity by day
    act_by_day = {a["date"]: int(a["active_seconds"] or 0) for a in act_qs.values("date", "active_seconds")}

    # Follow-ups by day
    fu_by_day: dict[date, dict[str, int]] = {}
    for row in fu_qs.values("due_date", "status").annotate(count=Count("id")):
        d = row.get("due_date")
        st = str(row.get("status") or "")
        cnt = int(row.get("count") or 0)
        if not d:
            continue
        bucket = fu_by_day.setdefault(d, {})
        bucket[st] = bucket.get(st, 0) + cnt
    expired_open_by_day = {
        row["due_date"]: int(row.get("count") or 0)
        for row in fu_qs.filter(status=ClientFollowUp.Status.OPEN)
        .filter(Q(grace_until__lt=timezone.now()) | Q(grace_until__isnull=True, due_at__lt=timezone.now()))
        .values("due_date")
        .annotate(count=Count("id"))
        if row.get("due_date")
    }

    # CP sent by day
    cp_by_day = {row["day"]: int(row["count"] or 0) for row in cp_qs.filter(status=CommercialOfferEmailLog.Status.SENT).annotate(day=TruncDate("created_at", tzinfo=tz)).values("day").annotate(count=Count("id"))}

    # Shops created by day
    shops_by_day = {row["day"]: int(row["count"] or 0) for row in shops_qs.annotate(day=TruncDate("created_at", tzinfo=tz)).values("day").annotate(count=Count("id"))}

    # Invoices created by day
    invoices_by_day: dict[date, int] = {}
    if invoices_qs is not None:
        invoices_by_day = {row["day"]: int(row["count"] or 0) for row in invoices_qs.annotate(day=TruncDate("created_at", tzinfo=tz)).values("day").annotate(count=Count("id"))}

    # Build full series days
    series: list[dict[str, Any]] = []
    report_days_required = 0
    report_days_late = 0
    report_days_missing = 0
    for i in range(range_current.days):
        d = range_current.start_date + timedelta(days=i)
        base = day_map.get(d, {"date": d.isoformat(), "clients": 0, "points": 0})
        act_sec = int(act_by_day.get(d) or 0)
        base["active_seconds"] = act_sec
        base["active_hhmm"] = _format_hhmm(act_sec)
        base["success_weighted"] = float(success_by_day.get(d, 0.0))

        rep_local = report_by_day.get(d)
        rep_status = "none"
        if rep_local:
            rep_status = _compute_report_status(rep_local, deadline_hour=deadline_hour, grace_minutes=grace)
        else:
            # Consider "missing" only on weekdays where there was work (clients>0).
            if d.weekday() < 5 and int(base.get("clients") or 0) > 0:
                rep_status = "missing"

        base["report_status"] = rep_status

        if d.weekday() < 5 and int(base.get("clients") or 0) > 0:
            report_days_required += 1
            if rep_status == "late":
                report_days_late += 1
            elif rep_status == "missing":
                report_days_missing += 1

        fu_bucket = fu_by_day.get(d, {})
        fu_total_d = int(sum(fu_bucket.values()))
        fu_missed_d = int(fu_bucket.get(ClientFollowUp.Status.MISSED, 0))
        fu_overdue_open_d = int(expired_open_by_day.get(d) or 0)

        metrics_day = {
            "processed": int(base.get("clients") or 0),
            "points": int(base.get("points") or 0),
            "active_seconds": act_sec,
            "followups_total": fu_total_d,
            "followups_missed": fu_missed_d + fu_overdue_open_d,
            "cp_email_sent": int(cp_by_day.get(d) or 0),
            "shops_created": int(shops_by_day.get(d) or 0),
            "invoices_created": int(invoices_by_day.get(d) or 0),
            "success_weighted": float(success_by_day.get(d, 0.0)),
            "report_days_required": 1 if (d.weekday() < 5 and int(base.get("clients") or 0) > 0) else 0,
            "report_days_late": 1 if rep_status == "late" else 0,
            "report_days_missing": 1 if rep_status == "missing" else 0,
            "followup_plan_missing": int(plan_missing_by_day.get(d) or 0),
        }
        base["kpd"] = compute_kpd(metrics_day, cfg).get("value")

        series.append(base)

    # Shops backlog signals (stale contacts / next-contact due) + overdue tests
    stale_days = int(acfg.get("stale_shop_days", 14) or 14)
    stale_cutoff = now_dt - timedelta(days=stale_days)

    shops_all_qs = Shop.objects.filter(created_by=user)

    stale_qs = (
        shops_all_qs.annotate(last_contacted=Max("communications__contacted_at", filter=Q(communications__created_by=user)))
        .filter(Q(last_contacted__lt=stale_cutoff) | Q(last_contacted__isnull=True, created_at__lt=stale_cutoff))
        .order_by(F("last_contacted").asc(nulls_first=True), "created_at")
    )
    stale_shops_count = stale_qs.count()
    stale_shops_list = []
    for row in stale_qs.values("id", "name", "shop_type", "created_at", "next_contact_at", "last_contacted")[:10]:
        last_ts = row.get("last_contacted") or row.get("created_at")
        last_local = timezone.localtime(last_ts) if last_ts else None
        days_ago = (today_local - last_local.date()).days if last_local else 0
        next_ts = row.get("next_contact_at")
        next_local = timezone.localtime(next_ts) if next_ts else None
        stale_shops_list.append(
            {
                "id": int(row.get("id") or 0),
                "name": row.get("name") or "",
                "type": row.get("shop_type") or "",
                "last_contacted_at": timezone.localtime(row["last_contacted"]).isoformat() if row.get("last_contacted") else "",
                "days_since": int(days_ago),
                "next_contact_at": next_local.isoformat() if next_local else "",
                "next_contact_label": next_local.strftime("%d.%m %H:%M") if next_local else "",
            }
        )

    next_due_qs = shops_all_qs.filter(next_contact_at__isnull=False, next_contact_at__lte=now_dt).order_by("next_contact_at")
    shops_next_contact_due_count = next_due_qs.count()
    shops_next_contact_due_list = []
    for row in next_due_qs.values("id", "name", "next_contact_at")[:10]:
        ts = row.get("next_contact_at")
        dt_local = timezone.localtime(ts) if ts else None
        shops_next_contact_due_list.append(
            {
                "id": int(row.get("id") or 0),
                "name": row.get("name") or "",
                "next_contact_at": dt_local.isoformat() if dt_local else "",
                "next_contact_label": dt_local.strftime("%d.%m %H:%M") if dt_local else "",
            }
        )

    tests_converted_total = shops_all_qs.filter(shop_type=Shop.ShopType.FULL).exclude(test_connected_at__isnull=True).count()

    overdue_tests = 0
    overdue_tests_list = []
    tests_raw = list(
        shops_all_qs.filter(shop_type=Shop.ShopType.TEST)
        .exclude(test_connected_at__isnull=True)
        .values("id", "name", "test_connected_at", "test_period_days", "next_contact_at")
    )
    for s in tests_raw:
        try:
            start_d = s.get("test_connected_at")
            days = int(s.get("test_period_days") or 14)
            if not start_d:
                continue
            end_d = start_d + timedelta(days=days)
            if end_d < today_local:
                overdue_tests += 1
                overdue_days = (today_local - end_d).days
                next_ts = s.get("next_contact_at")
                next_local = timezone.localtime(next_ts) if next_ts else None
                overdue_tests_list.append(
                    {
                        "id": int(s.get("id") or 0),
                        "name": s.get("name") or "",
                        "test_end": end_d.isoformat(),
                        "overdue_days": int(overdue_days),
                        "next_contact_at": next_local.isoformat() if next_local else "",
                        "next_contact_label": next_local.strftime("%d.%m %H:%M") if next_local else "",
                    }
                )
        except Exception:
            continue
    overdue_tests_list.sort(key=lambda x: int(x.get("overdue_days") or 0), reverse=True)
    overdue_tests_list = overdue_tests_list[:10]

    # Shipments + inventory movements inside period (only for manager's shops)
    shipments_qs = ShopShipment.objects.filter(created_by=user, created_at__gte=range_current.start, created_at__lt=range_current.end)
    shipments_count = shipments_qs.count()
    shipments_amount = shipments_qs.aggregate(s=Sum("invoice_total_amount")).get("s") or 0

    inv_qs = ShopInventoryMovement.objects.filter(created_by=user, created_at__gte=range_current.start, created_at__lt=range_current.end)
    inv_sales_qty = inv_qs.filter(kind=ShopInventoryMovement.Kind.SALE).aggregate(s=Sum(Abs("delta_qty"))).get("s") or 0
    inv_receipts_qty = inv_qs.filter(kind=ShopInventoryMovement.Kind.RECEIPT).aggregate(s=Sum("delta_qty")).get("s") or 0
    inv_adjust_count = inv_qs.filter(kind=ShopInventoryMovement.Kind.ADJUST).count()

    comms_qs = ShopCommunication.objects.filter(created_by=user, created_at__gte=range_current.start, created_at__lt=range_current.end)
    comms_count = comms_qs.count()

    # Success weighted (from segments)
    success_weighted = 0.0
    for seg in segments:
        success_weighted += float(seg.get("count") or 0) * float(seg.get("success_weight") or 0.0)

    metrics_now = {
        "processed": processed,
        "points": int(points or 0),
        "active_seconds": active_seconds,
        "followups_total": fu_total,
        "followups_missed": missed_effective,
        "cp_email_sent": cp_sent,
        "shops_created": shops_created,
        "invoices_created": invoices_created,
        "success_weighted": round(success_weighted, 2),
        "report_days_required": report_days_required,
        "report_days_late": report_days_late,
        "report_days_missing": report_days_missing,
        "followup_plan_missing": followup_plan_missing,
        "stale_shops_count": stale_shops_count,
        "shops_next_contact_due_count": shops_next_contact_due_count,
        "overdue_tests": overdue_tests,
    }

    kpd = compute_kpd(metrics_now, cfg)

    # Prev period for advice & kpd mini insight
    metrics_prev = _build_metrics_for_prev(user=user, r=prev_r, cfg=cfg)
    kpd_prev = compute_kpd(metrics_prev, cfg)
    kpd_delta = round(float(kpd.get("value") or 0) - float(kpd_prev.get("value") or 0), 2)

    def _kpd_insight() -> str:
        pts_now = int(metrics_now.get("points") or 0)
        pts_prev = int(metrics_prev.get("points") or 0)
        act_now = int(metrics_now.get("active_seconds") or 0)
        act_prev = int(metrics_prev.get("active_seconds") or 0)
        fu_now = int(metrics_now.get("followups_missed") or 0)
        fu_prev = int(metrics_prev.get("followups_missed") or 0)
        plan_now = int(metrics_now.get("followup_plan_missing") or 0)
        plan_prev = int(metrics_prev.get("followup_plan_missing") or 0)

        parts = []
        if pts_now != pts_prev:
            parts.append(f"бали: {pts_prev} → {pts_now}")
        if act_now != act_prev:
            parts.append(f"активність: {_format_hhmm(act_prev)} → {_format_hhmm(act_now)}")
        if fu_now != fu_prev:
            parts.append(f"пропущені передзвони: {fu_prev} → {fu_now}")
        if plan_now != plan_prev:
            parts.append(f"без плану передзвону: {plan_prev} → {plan_now}")
        if not parts:
            return "Зміни мінімальні — КПД стабільний."
        return " / ".join(parts[:3])

    advice = generate_advice(
        user_id=user.id,
        range_current=range_current,
        range_prev=prev_r,
        metrics_now=metrics_now,
        metrics_prev=metrics_prev,
        sources_now=sources,
        series=series,
        config=cfg,
    )

    payload = {
        "range": {
            "period": range_current.period,
            "label": range_current.label,
            "from": range_current.start_date.isoformat(),
            "to": range_current.end_date.isoformat(),
            "days": range_current.days,
        },
        "summary": {
            "first_activity_date": first_activity_date.isoformat() if first_activity_date else "",
            "first_activity_label": first_activity_date.strftime("%d.%m.%Y") if first_activity_date else "",
            "days_working": days_working,
            "processed": processed,
            "points": int(points or 0),
            "points_per_client": points_per_client,
            "active_seconds": active_seconds,
            "active_hhmm": _format_hhmm(active_seconds),
            "points_per_active_hour": points_per_active_hour,
            "kpd": kpd,
            "kpd_prev": kpd_prev,
            "kpd_delta": kpd_delta,
            "kpd_insight": _kpd_insight(),
            "success_weighted": round(success_weighted, 2),
            "success_rate": round((success_weighted + 1.0) / (float(processed) + 5.0), 3) if processed > 0 else 0.0,
            "success_rate_pct": round(((success_weighted + 1.0) / (float(processed) + 5.0)) * 100.0, 1) if processed > 0 else 0.0,
            "followups": {
                "total": fu_total,
                "missed": fu_missed,
                "overdue_open": fu_overdue_open,
                "missed_effective": missed_effective,
                "done": fu_done,
                "rescheduled": fu_rescheduled,
                "cancelled": fu_cancelled,
                "open": fu_open,
                "missed_rate": round(missed_rate, 2),
                "problem_list": fu_problem_list,
            },
            "pipeline": {
                "followup_plan_missing": followup_plan_missing,
                "followup_plan_missing_by": followup_plan_missing_by,
                "followup_plan_missing_examples": followup_plan_missing_examples,
                "negative_outcomes_total": reason_capture["required_total"],
                "required_reason_missing": reason_capture["missing_reason"],
                "reason_detail_missing": reason_capture["missing_detail"],
                "reason_quality": reason_capture["reason_quality"],
                "reason_breakdown": reason_capture["breakdown"],
                "reason_issue_examples": reason_capture["issue_examples"],
            },
            "reports": {
                "required": report_days_required,
                "late": report_days_late,
                "missing": report_days_missing,
                "on_time": max(0, report_days_required - report_days_late - report_days_missing),
            },
            "cp": {
                "total": cp_total,
                "sent": cp_sent,
                "failed": cp_failed,
                "modes": cp_modes,
                "segments": cp_segments,
            },
            "invoices": {
                "created": invoices_created,
                "amount": str(invoices_amount),
                "approved": invoices_approved,
                "paid": invoices_paid,
                "review": invoices_review,
                "payment": invoices_payment,
            },
            "shops": {
                "created": shops_created,
                "test": shops_test,
                "full": shops_full,
                "test_overdue_total": overdue_tests,
                "test_overdue_list": overdue_tests_list,
                "tests_converted_total": tests_converted_total,
                "stale_shops_count": stale_shops_count,
                "stale_shops_list": stale_shops_list,
                "next_contact_due_count": shops_next_contact_due_count,
                "next_contact_due_list": shops_next_contact_due_list,
                "shipments_count": shipments_count,
                "shipments_amount": str(shipments_amount),
                "inventory_sales_delta": int(inv_sales_qty or 0),
                "inventory_receipts_delta": int(inv_receipts_qty or 0),
                "inventory_adjust_count": inv_adjust_count,
                "communications_count": comms_count,
            },
        },
        "segments": segments,
        "roles": roles,
        "sources": sources[:12],
        "series": series,
        "advice": advice,
        "shadow_score": _shadow_score_payload(user=user, range_current=range_current) if include_shadow else {},
        "meta": {
            "report_deadline_hour": deadline_hour,
            "report_late_grace_minutes": grace,
        },
    }

    if not include_shadow:
        cache.set(cache_key, payload, 60)
        return payload

    shadow_score = payload["shadow_score"]
    previous_shadow = _shadow_score_payload(user=user, range_current=prev_r)
    prev_mosaic = previous_shadow.get("mosaic_score")
    curr_mosaic = shadow_score.get("mosaic_score")
    delta_vs_prev = None
    if prev_mosaic is not None and curr_mosaic is not None:
        delta_vs_prev = round(float(curr_mosaic) - float(prev_mosaic), 2)
    shadow_score["previous_period"] = {
        "label": prev_r.label,
        "snapshot_date": previous_shadow.get("snapshot_date"),
        "mosaic_score": prev_mosaic,
        "state_label": previous_shadow.get("state_label"),
        "explain": previous_shadow.get("explain") or {},
        "flags": previous_shadow.get("flags") or {},
    }
    shadow_score["delta_vs_prev"] = delta_vs_prev
    shadow_score["telephony_health"] = build_telephony_health_summary(owner=user)
    shadow_score["salary_simulator"] = build_salary_simulator(
        user=user,
        summary=payload["summary"],
        shadow_score=shadow_score,
    )
    shadow_score["forecast_band"] = build_forecast_band(
        summary=payload["summary"],
        shadow_score=shadow_score,
        config=cfg,
    )
    shadow_score["why_changed_today"] = build_why_changed_today(
        summary=payload["summary"],
        shadow_score=shadow_score,
    )
    shadow_score["timeline"] = _build_recent_timeline(user=user, range_current=range_current)
    shadow_score.update(
        build_action_stack(
            summary=payload["summary"],
            shops=payload["summary"].get("shops") or {},
            pipeline=payload["summary"].get("pipeline") or {},
            shadow_score=shadow_score,
        )
    )

    cache.set(cache_key, payload, 60)  # short cache for near-realtime feel
    return payload


def _build_metrics_for_prev(*, user, r: StatsRange, cfg: dict[str, Any]) -> dict[str, Any]:
    clients_qs = Client.objects.filter(owner=user, created_at__gte=r.start, created_at__lt=r.end)
    processed = clients_qs.count()
    points = clients_qs.aggregate(points=_points_sum_expr()).get("points") or 0
    act = ManagementDailyActivity.objects.filter(user=user, date__gte=r.start_date, date__lte=r.end_date).aggregate(s=Sum("active_seconds")).get("s") or 0

    fu_qs = ClientFollowUp.objects.filter(owner=user, due_date__gte=r.start_date, due_date__lte=r.end_date)
    today_local = timezone.localdate()
    fu_total = fu_qs.count()
    fu_missed = fu_qs.filter(status=ClientFollowUp.Status.MISSED).count()
    fu_overdue_open = fu_qs.filter(status=ClientFollowUp.Status.OPEN).filter(
        Q(grace_until__lt=timezone.now()) | Q(grace_until__isnull=True, due_at__lt=timezone.now())
    ).count()

    # Reports required/late
    acfg = cfg.get("advice") or {}
    deadline_hour = int(acfg.get("report_deadline_hour", 19) or 19)
    grace = int(acfg.get("report_late_grace_minutes", 60) or 60)
    report_days_required = 0
    report_days_late = 0
    report_days_missing = 0

    reports_list = list(Report.objects.filter(owner=user, created_at__gte=r.start, created_at__lt=r.end).order_by("created_at").values("created_at"))
    report_by_day: dict[date, datetime] = {}
    for row in reports_list:
        ts = row.get("created_at")
        if not ts:
            continue
        d = timezone.localtime(ts).date()
        if d not in report_by_day:
            report_by_day[d] = timezone.localtime(ts)

    tz = timezone.get_current_timezone()
    clients_by_day = clients_qs.annotate(day=TruncDate("created_at", tzinfo=tz)).values("day").annotate(count=Count("id"))
    worked_days = {row["day"] for row in clients_by_day if row.get("day") and int(row.get("count") or 0) > 0}

    for i in range(r.days):
        d = r.start_date + timedelta(days=i)
        if d.weekday() < 5 and d in worked_days:
            report_days_required += 1
            rep = report_by_day.get(d)
            if rep:
                if _compute_report_status(rep, deadline_hour=deadline_hour, grace_minutes=grace) == "late":
                    report_days_late += 1
            else:
                report_days_missing += 1

    # Success weighted (best-effort using current call_result)
    call_result_counts = clients_qs.values("call_result").annotate(count=Count("id"))
    success_weighted = 0.0
    for row in call_result_counts:
        success_weighted += float(row.get("count") or 0) * _success_weight_for_call_result(row.get("call_result") or "")

    followup_plan_missing = clients_qs.filter(call_result__in=FOLLOWUP_PLAN_CALL_RESULTS, next_call_at__isnull=True).count()

    cp_email_sent = CommercialOfferEmailLog.objects.filter(
        owner=user,
        created_at__gte=r.start,
        created_at__lt=r.end,
        status=CommercialOfferEmailLog.Status.SENT,
    ).count()

    shops_created = Shop.objects.filter(created_by=user, created_at__gte=r.start, created_at__lt=r.end).count()

    invoices_created = 0
    try:
        from orders.models import WholesaleInvoice
    except Exception:
        WholesaleInvoice = None
    if WholesaleInvoice is not None:
        invoices_created = WholesaleInvoice.objects.filter(created_by=user, created_at__gte=r.start, created_at__lt=r.end).count()

    return {
        "processed": processed,
        "points": int(points or 0),
        "active_seconds": int(act or 0),
        "followups_total": fu_total,
        "followups_missed": int(fu_missed + fu_overdue_open),
        "cp_email_sent": int(cp_email_sent or 0),
        "shops_created": int(shops_created or 0),
        "invoices_created": int(invoices_created or 0),
        "success_weighted": round(success_weighted, 2),
        "report_days_required": report_days_required,
        "report_days_late": report_days_late,
        "report_days_missing": report_days_missing,
        "followup_plan_missing": int(followup_plan_missing or 0),
    }
