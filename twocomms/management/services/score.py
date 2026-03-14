from decimal import Decimal, ROUND_HALF_UP


FOUR_PLACES = Decimal("0.0001")
TWO_PLACES = Decimal("0.01")
MOSAIC_WEIGHTS = {
    "result": Decimal("0.40"),
    "source_fairness": Decimal("0.10"),
    "process": Decimal("0.20"),
    "follow_up": Decimal("0.10"),
    "data_quality": Decimal("0.10"),
    "verified_communication": Decimal("0.10"),
}


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def compute_ewr(
    *,
    orders: int,
    contacts_processed: int,
    revenue,
    conversion_baseline=Decimal("0.0248"),
    target_weekly_revenue=Decimal("50000"),
    target_contacts: int = 80,
) -> Decimal:
    orders_dec = _to_decimal(orders)
    contacts_dec = _to_decimal(contacts_processed)
    revenue_dec = _to_decimal(revenue)
    expected_orders = contacts_dec * _to_decimal(conversion_baseline)

    if expected_orders >= Decimal("1"):
        outcome = min(Decimal("2"), orders_dec / expected_orders)
    elif orders_dec > 0:
        outcome = Decimal("2")
    else:
        outcome = Decimal("0.5")

    normalized_outcome = min(Decimal("1"), outcome / Decimal("2"))
    effort = min(Decimal("1"), contacts_dec / max(1, target_contacts))
    revenue_progress = min(Decimal("1"), revenue_dec / max(1, _to_decimal(target_weekly_revenue)))

    value = min(
        Decimal("1"),
        Decimal("0.40") * normalized_outcome
        + Decimal("0.35") * effort
        + Decimal("0.25") * revenue_progress,
    )
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def compute_score_confidence(
    *,
    verified_coverage,
    sample_sufficiency,
    stability,
    recency,
) -> Decimal:
    value = (
        Decimal("0.35") * _to_decimal(verified_coverage)
        + Decimal("0.25") * _to_decimal(sample_sufficiency)
        + Decimal("0.20") * _to_decimal(stability)
        + Decimal("0.20") * _to_decimal(recency)
    )
    value = max(Decimal("0"), min(Decimal("1"), value))
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def compute_mosaic(*, axes: dict[str, Decimal], readiness: dict[str, str]) -> Decimal:
    active_weights = get_active_weights(readiness)
    total_weight = sum(active_weights.values()) or Decimal("1")
    score = Decimal("0")
    for key, weight in active_weights.items():
        axis_value = max(Decimal("0"), min(Decimal("1"), _to_decimal(axes.get(key, 0))))
        score += (weight / total_weight) * axis_value
    return (score * Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def get_active_weights(readiness: dict[str, str]) -> dict[str, Decimal]:
    return {
        key: weight
        for key, weight in MOSAIC_WEIGHTS.items()
        if readiness.get(key, "shadow") != "dormant"
    }


def compute_verified_result_share(*, readiness: dict[str, str], gate_level: str) -> Decimal:
    active_weights = get_active_weights(readiness)
    total_weight = sum(active_weights.values()) or Decimal("1")
    result_share = active_weights.get("result", Decimal("0")) / total_weight
    if gate_level == "Paid":
        return result_share.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
    if gate_level == "Admin-confirmed":
        return (result_share * Decimal("0.60")).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
    return Decimal("0.0000")


def apply_shadow_score_pipeline(
    *,
    base_mosaic,
    gate_score,
    trust_multiplier,
    dampener,
    readiness: dict[str, str],
    gate_level: str,
    onboarding_floor=Decimal("0"),
) -> dict[str, Decimal]:
    base_value = _to_decimal(base_mosaic)
    verified_share = compute_verified_result_share(readiness=readiness, gate_level=gate_level)
    verified_slice = (base_value * verified_share).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    evidence_slice = max(Decimal("0"), base_value - verified_slice)
    trust_adjusted_evidence = (evidence_slice * _to_decimal(trust_multiplier)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    gated_evidence = (trust_adjusted_evidence * (_to_decimal(gate_score) / Decimal("100"))).quantize(
        TWO_PLACES,
        rounding=ROUND_HALF_UP,
    )
    dampened_evidence = (gated_evidence * _to_decimal(dampener)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    pre_floor = (verified_slice + dampened_evidence).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    final_score = max(pre_floor, _to_decimal(onboarding_floor)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return {
        "base_mosaic": base_value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "verified_slice": verified_slice,
        "evidence_sensitive_slice": evidence_slice.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "trust_adjusted_evidence": trust_adjusted_evidence,
        "gated_evidence": gated_evidence,
        "dampened_evidence": dampened_evidence,
        "pre_floor_score": pre_floor,
        "onboarding_floor": _to_decimal(onboarding_floor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "final_mosaic": final_score,
        "verified_share": verified_share,
    }
