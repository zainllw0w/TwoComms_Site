from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from management.models import ComponentReadiness


FOUR_PLACES = Decimal("0.0001")

EVIDENCE_GATE_SCORES = {
    "Paid": 100,
    "Admin-confirmed": 78,
    "CRM-timestamped": 60,
    "Self-reported only": 45,
}


def _to_decimal(value, default: str = "0") -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal(default)
    return Decimal(str(value))


def compute_gate_level(*, paid_orders: int, approved_orders: int, crm_events: int) -> tuple[str, int]:
    if paid_orders > 0:
        return "Paid", EVIDENCE_GATE_SCORES["Paid"]
    if approved_orders > 0:
        return "Admin-confirmed", EVIDENCE_GATE_SCORES["Admin-confirmed"]
    if crm_events > 0:
        return "CRM-timestamped", EVIDENCE_GATE_SCORES["CRM-timestamped"]
    return "Self-reported only", EVIDENCE_GATE_SCORES["Self-reported only"]


def compute_production_trust(
    *,
    duplicate_backlog: int,
    overdue_followups: int,
    telephony_healthy: bool,
    reason_quality: Decimal | float = Decimal("1.00"),
) -> Decimal:
    report_integrity = Decimal("1.00") if overdue_followups == 0 else max(
        Decimal("0.00"),
        Decimal("1.00") - (Decimal(str(min(10, overdue_followups))) / Decimal("10")),
    )
    reason_quality_value = max(Decimal("0.00"), min(Decimal("1.00"), _to_decimal(reason_quality)))
    duplicate_abuse = min(Decimal("1.00"), _to_decimal(duplicate_backlog) / Decimal("5"))
    anomaly = max(
        duplicate_abuse,
        min(Decimal("1.00"), _to_decimal(overdue_followups) / Decimal("10")),
    )

    trust = (
        Decimal("0.97")
        + Decimal("0.04") * report_integrity
        + Decimal("0.02") * reason_quality_value
        - Decimal("0.05") * duplicate_abuse
        - Decimal("0.05") * anomaly
    )
    if not telephony_healthy:
        trust = max(Decimal("0.85"), trust)
    trust = max(Decimal("0.85"), min(Decimal("1.05"), trust))
    return trust.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def compute_dampener(*, axes: dict[str, Decimal], readiness: dict[str, str], weak_axis_threshold: Decimal = Decimal("0.45")) -> Decimal:
    weak_axes = 0
    for key, value in axes.items():
        if key == "verified_communication" and readiness.get(key) == ComponentReadiness.Status.DORMANT:
            continue
        if _to_decimal(value) < weak_axis_threshold:
            weak_axes += 1
    if weak_axes <= 0:
        return Decimal("1.0000")
    if weak_axes == 1:
        return Decimal("0.9400")
    if weak_axes == 2:
        return Decimal("0.8800")
    return Decimal("0.8200")


def classify_confidence_band(score_confidence) -> str:
    value = _to_decimal(score_confidence)
    if value >= Decimal("0.80"):
        return "HIGH"
    if value >= Decimal("0.50"):
        return "MEDIUM"
    return "LOW"
