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
    active_weights = {
        key: weight
        for key, weight in MOSAIC_WEIGHTS.items()
        if readiness.get(key, "shadow") != "dormant"
    }
    total_weight = sum(active_weights.values()) or Decimal("1")
    score = Decimal("0")
    for key, weight in active_weights.items():
        axis_value = max(Decimal("0"), min(Decimal("1"), _to_decimal(axes.get(key, 0))))
        score += (weight / total_weight) * axis_value
    return (score * Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
