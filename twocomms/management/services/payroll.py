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
