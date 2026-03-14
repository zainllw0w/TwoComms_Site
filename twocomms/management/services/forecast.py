from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model

from management.models import DtfBridgeSnapshot, DuplicateReview, NightlyScoreSnapshot, ScoreAppeal, TelephonyHealthSnapshot
from management.services.config_versions import get_management_config


TWO_PLACES = Decimal("0.01")


def _to_decimal(value, default: str = "0") -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal(default)
    return Decimal(str(value))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def build_salary_simulator(*, user, summary: dict, shadow_score: dict) -> dict:
    profile = getattr(user, "userprofile", None)
    base_salary = _to_decimal(getattr(profile, "manager_base_salary_uah", 0) if profile else 0)
    invoices_amount = _to_decimal((summary.get("invoices") or {}).get("amount") or 0)
    accrued_shadow_bonus = _quantize(invoices_amount * _to_decimal(shadow_score.get("mosaic_score") or 0) / Decimal("1000"))
    current_truth = base_salary + _to_decimal((summary.get("invoices") or {}).get("paid") or 0)
    shadow_candidate = current_truth + accrued_shadow_bonus
    delta = shadow_candidate - current_truth
    return {
        "base_salary": float(base_salary),
        "current_truth": float(_quantize(current_truth)),
        "shadow_candidate": float(_quantize(shadow_candidate)),
        "shadow_hold_harmless_delta": float(_quantize(delta)),
        "confidence_band": shadow_score.get("confidence_band") or "LOW",
        "freeze_line": "Shadow payroll remains hold-harmless until activation.",
    }


def build_forecast_band(*, summary: dict, shadow_score: dict, config: dict | None = None) -> dict:
    cfg = config or get_management_config()
    aging = (cfg.get("forecast_config") or {}).get("aging_multipliers") or {}
    invoices_amount = _to_decimal((summary.get("invoices") or {}).get("amount") or 0)
    pipeline_missing = _to_decimal((summary.get("pipeline") or {}).get("followup_plan_missing") or 0)
    active_multiplier = _to_decimal(aging.get("within_sla", 1.0))
    watch_multiplier = _to_decimal(aging.get("double_sla", 0.85))
    risk_multiplier = _to_decimal(aging.get("older", 0.65))
    confidence = _to_decimal(shadow_score.get("score_confidence") or 0)
    base = invoices_amount * (Decimal("0.65") + confidence * Decimal("0.55"))
    penalty = min(Decimal("0.30"), pipeline_missing / Decimal("100"))
    optimistic = base * active_multiplier
    pessimistic = base * risk_multiplier * (Decimal("1.0") - penalty)
    return {
        "optimistic": float(_quantize(optimistic)),
        "base": float(_quantize(base * watch_multiplier)),
        "pessimistic": float(_quantize(pessimistic)),
        "confidence_note": f"Confidence {shadow_score.get('confidence_band') or 'LOW'}",
    }


def build_admin_economics_summary() -> dict:
    User = get_user_model()
    managers = (
        User.objects.filter(is_active=True)
        .filter(userprofile__is_manager=True)
        .select_related("userprofile")
        .order_by("username")
    )
    rows = []
    stale_count = 0
    for manager in managers:
        snapshot = NightlyScoreSnapshot.objects.filter(owner=manager).order_by("-snapshot_date").first()
        summary = (snapshot.payload or {}).get("summary") if snapshot else {}
        shadow_payload = (snapshot.payload or {}) if snapshot else {}
        revenue = _to_decimal((summary.get("invoices") or {}).get("amount") or 0)
        base_salary = _to_decimal(getattr(getattr(manager, "userprofile", None), "manager_base_salary_uah", 0))
        score_confidence = _to_decimal(snapshot.score_confidence if snapshot else 0)
        cost = base_salary + (revenue * Decimal("0.025"))
        contribution = revenue
        payback = Decimal("0") if cost <= 0 else contribution / cost
        if snapshot and int(snapshot.freshness_seconds or 0) > 172800:
            stale_count += 1
        rows.append(
            {
                "id": manager.id,
                "name": manager.get_full_name() or manager.username,
                "confidence": float(score_confidence),
                "contribution": float(_quantize(contribution)),
                "cost": float(_quantize(cost)),
                "payback": float(_quantize(payback)),
                "open_appeals": ScoreAppeal.objects.filter(owner=manager, status=ScoreAppeal.Status.OPEN).count(),
                "duplicate_reviews": DuplicateReview.objects.filter(owner=manager, status=DuplicateReview.Status.OPEN).count(),
                "state": shadow_payload.get("rollout_state") or "shadow",
            }
        )

    return {
        "manager_count": len(rows),
        "stale_count": stale_count,
        "open_appeals": ScoreAppeal.objects.filter(status=ScoreAppeal.Status.OPEN).count(),
        "duplicate_queue": DuplicateReview.objects.filter(status=DuplicateReview.Status.OPEN).count(),
        "telephony_status": (
            TelephonyHealthSnapshot.objects.order_by("-snapshot_at").values_list("status", flat=True).first() or "degraded"
        ),
        "dtf_status": (
            DtfBridgeSnapshot.objects.order_by("-snapshot_date").values_list("status", flat=True).first() or "degraded"
        ),
        "rows": rows,
    }
