import math
from decimal import Decimal, ROUND_HALF_UP


FOUR_PLACES = Decimal("0.0001")


def compute_churn_weibull(
    *,
    days_since_last_order: int,
    avg_interval: float,
    std_interval: float,
    order_count: int,
    expected_next_order: int | None = None,
) -> Decimal:
    if expected_next_order is not None and days_since_last_order < expected_next_order:
        return Decimal("0.0500")

    if order_count < 5:
        if avg_interval <= 0:
            return Decimal("0.5000")
        logistic = 1 / (1 + math.exp(-3.0 * (days_since_last_order - avg_interval) / avg_interval))
        return Decimal(str(min(1.0, max(0.0, logistic)))).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)

    lambda_param = avg_interval + 0.5 * max(1.0, std_interval)
    k_param = min(10.0, max(1.0, avg_interval / max(1.0, std_interval)))
    churn = 1 - math.exp(-pow(days_since_last_order / max(1.0, lambda_param), k_param))
    return Decimal(str(min(1.0, max(0.0, churn)))).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
