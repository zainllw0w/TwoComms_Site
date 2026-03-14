import math
from decimal import Decimal, ROUND_HALF_UP


FOUR_PLACES = Decimal("0.0001")
TWO_PLACES = Decimal("0.01")


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def compute_working_factor(capacity_factors: list[float], nominal_workdays: int = 5) -> Decimal:
    usable = sum(max(0.0, min(1.0, float(item))) for item in capacity_factors)
    value = Decimal(str(usable / max(1, nominal_workdays)))
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def compute_onboarding_floor_score(tenure_days: int) -> Decimal:
    if tenure_days <= 14:
        return Decimal("40.00")
    if tenure_days >= 28:
        return Decimal("0.00")
    remaining = Decimal("1") - (Decimal(str(tenure_days - 14)) / Decimal("14"))
    return (Decimal("40.00") * remaining).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def effective_phase0_dmt(capacity_factor: float) -> tuple[int, int]:
    clamped = max(0.0, min(1.0, float(capacity_factor or 0.0)))
    effective_dmt_contacts = max(1, int(math.ceil(5 * clamped)))
    effective_dmt_updates = 1 if clamped >= 0.5 else 0
    return effective_dmt_contacts, effective_dmt_updates


def compute_repeat_commission(
    *,
    repeat_revenue,
    new_clients_this_week: int,
    target_new_clients: int = 1,
    cap_amount=Decimal("120000"),
) -> Decimal:
    repeat_revenue_dec = _to_decimal(repeat_revenue)
    cap_amount_dec = _to_decimal(cap_amount)
    base_rate = Decimal("0.05")
    shortfall = max(0, target_new_clients - int(new_clients_this_week or 0))

    if shortfall == 0:
        return (repeat_revenue_dec * base_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    penalty_rate = Decimal("0.045") if shortfall == 1 else Decimal("0.035")
    penalized = min(repeat_revenue_dec, cap_amount_dec)
    regular = max(Decimal("0"), repeat_revenue_dec - cap_amount_dec)
    value = penalized * penalty_rate + regular * base_rate
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_rescue_spiff(
    rescued_revenue,
    *,
    spiff_floor=Decimal("500"),
    spiff_rate=Decimal("0.01"),
    spiff_cap=Decimal("2000"),
) -> Decimal:
    rescued_revenue_dec = _to_decimal(rescued_revenue)
    raw = rescued_revenue_dec * _to_decimal(spiff_rate)
    bounded = max(_to_decimal(spiff_floor), min(_to_decimal(spiff_cap), raw))
    if rescued_revenue_dec <= 0:
        return Decimal("0.00")
    return bounded.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_earned_day_state(
    *,
    crm_contacts: int,
    crm_updates: int,
    report_submitted: bool,
    capacity_factor: float,
    telephony_ready: bool = False,
    meaningful_calls: int = 0,
    meaningful_call_seconds_threshold: int = 30,
) -> dict:
    clamped_capacity = max(0.0, min(1.0, float(capacity_factor or 0.0)))
    minimum_contacts, minimum_updates = effective_phase0_dmt(clamped_capacity)
    target_contacts = max(minimum_contacts, int(math.ceil(10 * clamped_capacity)))
    required_calls = int(math.ceil(2 * clamped_capacity)) if telephony_ready else 0

    minimum_achieved = (
        int(crm_contacts or 0) >= minimum_contacts
        and int(crm_updates or 0) >= minimum_updates
        and bool(report_submitted)
        and int(meaningful_calls or 0) >= required_calls
    )
    target_pace_achieved = minimum_achieved and int(crm_contacts or 0) >= target_contacts

    gap_category = ""
    if not report_submitted:
        gap_category = "reporting_gap"
    elif telephony_ready and int(meaningful_calls or 0) < required_calls:
        gap_category = "system_gap"
    elif not minimum_achieved:
        gap_category = "performance_gap"

    return {
        "minimum_achieved": minimum_achieved,
        "target_pace_achieved": target_pace_achieved,
        "recovery_needed": not target_pace_achieved,
        "meaningful_calls": int(meaningful_calls or 0),
        "meaningful_call_seconds_threshold": int(meaningful_call_seconds_threshold or 30),
        "gap_category": gap_category,
        "minimum_contacts_required": minimum_contacts,
        "minimum_updates_required": minimum_updates,
        "target_contacts_required": target_contacts,
        "required_calls": required_calls,
    }
