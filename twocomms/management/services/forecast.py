from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from management.models import (
    DuplicateReview,
    ManagerCommissionAccrual,
    NightlyScoreSnapshot,
    ScoreAppeal,
    TelephonyHealthSnapshot,
)
from management.services.config_versions import get_management_config
from management.services.dtf_bridge import build_dtf_bridge_payload
from management.services.roster import management_role_label, manager_roster_queryset
from management.services.ui_labels import (
    translate_confidence_band,
    translate_driver,
    translate_dtf_status,
    translate_payback_risk,
    translate_telephony_status,
)
from orders.models import WholesaleInvoice


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
    commission_percent = _to_decimal(getattr(profile, "manager_commission_percent", 0) if profile else 0) / Decimal("100")
    invoices_amount = _to_decimal((summary.get("invoices") or {}).get("amount") or 0)
    open_frozen_qs = ManagerCommissionAccrual.objects.filter(owner=user, frozen_until__gt=timezone.now()).order_by("frozen_until")
    frozen_total = sum((_to_decimal(item.amount) for item in open_frozen_qs), Decimal("0"))
    current_truth = base_salary + (invoices_amount * commission_percent)
    shadow_candidate = current_truth + (invoices_amount * (_to_decimal(shadow_score.get("mosaic_score") or 0) / Decimal("10000")))
    delta = shadow_candidate - current_truth
    return {
        "base_salary": float(_quantize(base_salary)),
        "current_truth": float(_quantize(current_truth)),
        "shadow_candidate": float(_quantize(shadow_candidate)),
        "shadow_hold_harmless_delta": float(_quantize(delta)),
        "confidence_band": shadow_score.get("confidence_band") or "LOW",
        "confidence_band_label": translate_confidence_band(shadow_score.get("confidence_band") or "LOW"),
        "freshness_seconds": int(shadow_score.get("freshness_seconds") or 0),
        "freeze_items": [
            {
                "amount": float(_quantize(_to_decimal(item.amount))),
                "until": timezone.localtime(item.frozen_until).strftime("%d.%m.%Y") if item.frozen_until else "—",
                "reason": item.freeze_reason_text or item.note or "Ручне замороження",
            }
            for item in open_frozen_qs[:5]
        ],
        "freeze_line": (
            f"Тіньовий захист діє до активації. Зараз заморожено: {float(_quantize(frozen_total))} грн."
            if frozen_total > 0
            else "Тіньовий захист діє до активації."
        ),
    }


def build_forecast_band(*, summary: dict, shadow_score: dict, config: dict | None = None) -> dict:
    cfg = config or get_management_config()
    aging = (cfg.get("forecast_config") or {}).get("aging_multipliers") or {}
    invoices_amount = _to_decimal((summary.get("invoices") or {}).get("amount") or 0)
    pipeline_missing = _to_decimal((summary.get("pipeline") or {}).get("followup_plan_missing") or 0)
    repeat_concentration = _to_decimal((summary.get("shops") or {}).get("stale_shops_count") or 0) / Decimal("10")
    confidence = _to_decimal(shadow_score.get("score_confidence") or 0)

    within_sla = _to_decimal(aging.get("within_sla", 1.0))
    double_sla = _to_decimal(aging.get("double_sla", 0.85))
    older = _to_decimal(aging.get("older", 0.65))
    base_weight = Decimal("0.55") + confidence * Decimal("0.45")
    freshness_penalty = min(Decimal("0.30"), pipeline_missing / Decimal("100"))
    concentration_penalty = min(Decimal("0.20"), repeat_concentration / Decimal("5"))

    optimistic = invoices_amount * base_weight * within_sla
    base = invoices_amount * base_weight * double_sla * (Decimal("1.0") - (freshness_penalty / Decimal("2")))
    pessimistic = invoices_amount * base_weight * older * (Decimal("1.0") - freshness_penalty - concentration_penalty)

    drivers = []
    if pipeline_missing > 0:
        drivers.append("pipeline_aging")
    if confidence < Decimal("0.65"):
        drivers.append("verified_coverage")
    if repeat_concentration > Decimal("0.30"):
        drivers.append("repeat_concentration")
    if not drivers:
        drivers.append("recent_conversion_trend")

    return {
        "optimistic": float(_quantize(optimistic)),
        "base": float(_quantize(base)),
        "pessimistic": float(_quantize(max(Decimal("0"), pessimistic))),
        "confidence_note": f"Довіра: {translate_confidence_band(shadow_score.get('confidence_band') or 'LOW')}",
        "drivers": drivers,
        "driver_labels": [translate_driver(item) for item in drivers],
    }


def _manager_retention_proxy(manager) -> dict:
    paid_dates = list(
        WholesaleInvoice.objects.filter(created_by=manager, payment_status="paid")
        .order_by("created_at")
        .values_list("created_at", flat=True)
    )
    if not paid_dates:
        return {"30d": 0, "60d": 0, "90d": 0, "180d": 0}
    first = timezone.localtime(paid_dates[0]) if hasattr(paid_dates[0], "tzinfo") else paid_dates[0]
    result = {}
    for days in (30, 60, 90, 180):
        cutoff = first + timedelta(days=days)
        result[f"{days}d"] = int(any((ts >= cutoff for ts in paid_dates)))
    return result


def build_admin_economics_summary() -> dict:
    cfg = get_management_config()
    appeal_sla_hours = int((((cfg.get("payroll_config") or {}).get("appeal_sla_hours") or {}).get("score") or 48))
    managers = manager_roster_queryset(include_staff=False)
    rows = []
    stale_count = 0
    low_confidence_count = 0
    total_optimistic = Decimal("0")
    total_base = Decimal("0")
    total_pessimistic = Decimal("0")
    cohort_counts = {"30d": 0, "60d": 0, "90d": 0, "180d": 0}
    latest_incidents: dict[int, set[str]] = {}

    for manager in managers:
        snapshot = NightlyScoreSnapshot.objects.filter(owner=manager).order_by("-snapshot_date").first()
        summary = (snapshot.payload or {}).get("summary") if snapshot else {}
        shadow_payload = (snapshot.payload or {}) if snapshot else {}
        revenue = _to_decimal((summary.get("invoices") or {}).get("amount") or 0)
        base_salary = _to_decimal(getattr(getattr(manager, "userprofile", None), "manager_base_salary_uah", 0))
        score_confidence = _to_decimal(snapshot.score_confidence if snapshot else 0)
        forecast_band = build_forecast_band(
            summary=summary or {},
            shadow_score={
                "score_confidence": score_confidence,
                "confidence_band": shadow_payload.get("trust", {}).get("confidence_band", "LOW"),
            },
        )
        cost = base_salary + (revenue * Decimal("0.025"))
        contribution = revenue
        payback = Decimal("0") if cost <= 0 else contribution / cost
        payback_risk = "high" if payback < Decimal("1.00") else "watch" if payback < Decimal("1.25") else "safe"
        if snapshot and int(snapshot.freshness_seconds or 0) > 172800:
            stale_count += 1
        if score_confidence < Decimal("0.50"):
            low_confidence_count += 1
        latest_incidents[manager.id] = set((shadow_payload.get("ops") or {}).get("incident_keys") or shadow_payload.get("incidents") or [])

        paid_invoices = list(
            WholesaleInvoice.objects.filter(created_by=manager, payment_status="paid")
            .order_by("-total_amount")
            .values_list("total_amount", flat=True)
        )
        total_paid_invoice_amount = sum((_to_decimal(item) for item in paid_invoices), Decimal("0"))
        top3_invoice_amount = sum((_to_decimal(item) for item in paid_invoices[:3]), Decimal("0"))
        concentration_top3 = Decimal("0") if total_paid_invoice_amount <= 0 else top3_invoice_amount / total_paid_invoice_amount

        rescue_spiff_paid = sum(
            (
                _to_decimal(amount)
                for amount in ManagerCommissionAccrual.objects.filter(
                    owner=manager,
                    accrual_type=ManagerCommissionAccrual.AccrualType.RESCUE_SPIFF,
                )
                .order_by("-created_at")
                .values_list("amount", flat=True)[:90]
            ),
            Decimal("0"),
        )
        estimated_rescue_time_cost = Decimal(str(len((shadow_payload.get("portfolio") or {}).get("rescue_top5") or []) * 250))
        rescued_revenue_90d = Decimal(str(sum((item.get("value_at_risk") or 0 for item in (shadow_payload.get("portfolio") or {}).get("rescue_top5") or []))))
        rescue_roi = Decimal("0") if rescued_revenue_90d <= 0 else rescued_revenue_90d / max(
            Decimal("1"),
            rescue_spiff_paid + estimated_rescue_time_cost,
        )

        retention_proxy = _manager_retention_proxy(manager)
        for key in cohort_counts:
            cohort_counts[key] += retention_proxy[key]

        total_optimistic += _to_decimal(forecast_band["optimistic"])
        total_base += _to_decimal(forecast_band["base"])
        total_pessimistic += _to_decimal(forecast_band["pessimistic"])

        rows.append(
            {
                "id": manager.id,
                "name": manager.get_full_name() or manager.username,
                "role": management_role_label(manager),
                "confidence": float(score_confidence),
                "contribution": float(_quantize(contribution)),
                "cost": float(_quantize(cost)),
                "break_even": float(_quantize(cost)),
                "payback": float(_quantize(payback)),
                "payback_risk": payback_risk,
                "payback_risk_label": translate_payback_risk(payback_risk),
                "concentration_top3": float(_quantize(concentration_top3)),
                "rescue_roi": float(_quantize(rescue_roi)),
                "forecast_band": forecast_band,
                "retention_proxy": retention_proxy,
                "open_appeals": ScoreAppeal.objects.filter(owner=manager, status=ScoreAppeal.Status.OPEN).count(),
                "duplicate_reviews": DuplicateReview.objects.filter(owner=manager, status=DuplicateReview.Status.OPEN).count(),
                "state": shadow_payload.get("rollout_state") or "shadow",
            }
        )

    dtf_payload = build_dtf_bridge_payload()
    telephony_status = (
        TelephonyHealthSnapshot.objects.order_by("-snapshot_at").values_list("status", flat=True).first() or "degraded"
    )
    now = timezone.now()
    frozen_queue = ManagerCommissionAccrual.objects.filter(frozen_until__gt=now).count()
    open_appeals_qs = ScoreAppeal.objects.filter(status=ScoreAppeal.Status.OPEN)
    appeals_nearing_sla = open_appeals_qs.filter(
        opened_at__lte=now - timedelta(hours=max(1, int(appeal_sla_hours * 0.75)))
    ).count()
    follow_up_overload = sum(1 for incidents in latest_incidents.values() if "REMINDER_STORM" in incidents)
    telephony_mismatch = (
        TelephonyHealthSnapshot.objects.filter(status__in=[TelephonyHealthSnapshot.Status.DEGRADED, TelephonyHealthSnapshot.Status.OUTAGE]).count()
    )
    forecast_confidence = "HIGH" if low_confidence_count == 0 and stale_count == 0 else "MEDIUM" if stale_count <= 1 else "LOW"
    forecast_drivers = []
    if stale_count:
        forecast_drivers.append("pipeline_freshness")
    if low_confidence_count:
        forecast_drivers.append("verified_coverage")
    if DuplicateReview.objects.filter(status=DuplicateReview.Status.OPEN).exists():
        forecast_drivers.append("follow_up_load")
    if not forecast_drivers:
        forecast_drivers.append("recent_conversion_trend")
    top_risk_managers = sorted(
        rows,
        key=lambda row: (
            0 if row["payback_risk"] == "high" else 1 if row["payback_risk"] == "watch" else 2,
            row["confidence"],
            -row["duplicate_reviews"],
            -row["open_appeals"],
        ),
    )[:5]

    return {
        "manager_count": len(rows),
        "stale_count": stale_count,
        "low_confidence_count": low_confidence_count,
        "open_appeals": open_appeals_qs.count(),
        "duplicate_queue": DuplicateReview.objects.filter(status=DuplicateReview.Status.OPEN).count(),
        "telephony_status": telephony_status,
        "telephony_status_label": translate_telephony_status(telephony_status),
        "dtf_status": dtf_payload["status"],
        "dtf_status_label": translate_dtf_status(dtf_payload["status"]),
        "dtf": dtf_payload,
        "queue_presets": [
            {"key": "duplicate_review", "label": "Черга дублів", "count": DuplicateReview.objects.filter(status=DuplicateReview.Status.OPEN).count(), "tone": "warn"},
            {"key": "payout_freeze", "label": "Заморожені виплати", "count": frozen_queue, "tone": "watch"},
            {"key": "appeals_sla", "label": "Апеляції біля SLA", "count": appeals_nearing_sla, "tone": "bad" if appeals_nearing_sla else "ok"},
            {"key": "low_confidence", "label": "Менеджери з низькою довірою", "count": low_confidence_count, "tone": "warn" if low_confidence_count else "ok"},
            {"key": "follow_up_overload", "label": "Перевантаження передзвонів", "count": follow_up_overload, "tone": "warn" if follow_up_overload else "ok"},
            {"key": "telephony_mismatch", "label": "Розбіжності телефонії", "count": telephony_mismatch, "tone": "bad" if telephony_mismatch else "ok"},
        ],
        "forecast": {
            "optimistic": float(_quantize(total_optimistic)),
            "base": float(_quantize(total_base)),
            "pessimistic": float(_quantize(total_pessimistic)),
            "confidence": forecast_confidence,
            "confidence_label": translate_confidence_band(forecast_confidence),
            "drivers": forecast_drivers,
            "driver_labels": [translate_driver(item) for item in forecast_drivers],
        },
        "cohorts": cohort_counts,
        "rows": rows,
        "top_risk_managers": top_risk_managers,
    }
