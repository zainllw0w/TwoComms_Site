from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from django.utils import timezone

from .models import DtfPricingConfig
from .utils import get_pricing_config


MONEY_Q = Decimal("0.01")


def _to_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def get_active_pricing_config() -> dict[str, Any]:
    today = timezone.localdate()
    db_config = (
        DtfPricingConfig.objects.filter(is_active=True, effective_from__lte=today)
        .order_by("-effective_from", "-id")
        .first()
    )
    if db_config:
        tiers = []
        for item in db_config.tiers_json or []:
            min_m = _to_decimal(item.get("min_m"), Decimal("0"))
            rate = _to_decimal(item.get("rate"), db_config.base_price_per_meter)
            if min_m <= 0 or rate <= 0:
                continue
            tiers.append({
                "min_m": min_m,
                "rate": rate,
            })
        tiers.sort(key=lambda item: item["min_m"])
        return {
            "version": f"cfg-{db_config.id}-v{db_config.version}",
            "width_cm": _to_decimal(db_config.width_cm, Decimal("60")),
            "min_order_m": _to_decimal(db_config.min_order_m, Decimal("1")),
            "base_rate": _to_decimal(db_config.base_price_per_meter, Decimal("350")),
            "tiers": tiers,
            "urgency": db_config.urgency_multipliers_json or {"standard": 1},
            "layout_help_fee": _to_decimal(db_config.layout_help_fee, Decimal("0")),
            "shipping_fee": _to_decimal(db_config.shipping_estimate_fee, Decimal("0")),
            "validity_days": int(db_config.validity_days or 7),
        }

    fallback = get_pricing_config()
    fallback_tiers = []
    for item in fallback.get("tiers", []):
        min_value = _to_decimal(item.get("min"), Decimal("0"))
        rate = _to_decimal(item.get("rate"), fallback.get("base_rate", Decimal("350")))
        if min_value <= 0 or rate <= 0:
            continue
        fallback_tiers.append({
            "min_m": min_value,
            "rate": rate,
        })

    return {
        "version": "legacy-settings",
        "width_cm": Decimal("60"),
        "min_order_m": Decimal("1"),
        "base_rate": _to_decimal(fallback.get("base_rate", Decimal("350")), Decimal("350")),
        "tiers": fallback_tiers,
        "urgency": {"standard": 1, "rush": Decimal("1.15")},
        "layout_help_fee": Decimal("100"),
        "shipping_fee": Decimal("0"),
        "validity_days": 7,
    }


def calculate_quote(payload: dict[str, Any]) -> dict[str, Any]:
    config = get_active_pricing_config()
    width_cm = _to_decimal(payload.get("width_cm"), config["width_cm"])
    length_m = _to_decimal(payload.get("length_m"), Decimal("0"))
    if width_cm <= 0:
        raise ValueError("width_cm must be positive")
    if length_m <= 0:
        raise ValueError("length_m must be positive")

    urgency = str(payload.get("urgency") or "standard").strip().lower()
    urgency_map = config.get("urgency", {})
    urgency_multiplier = _to_decimal(urgency_map.get(urgency, urgency_map.get("standard", 1)), Decimal("1"))
    if urgency_multiplier <= 0:
        urgency_multiplier = Decimal("1")

    help_layout = _to_bool(payload.get("help_layout"))
    with_shipping = _to_bool(payload.get("with_shipping"))

    width_ratio = width_cm / config["width_cm"] if config["width_cm"] else Decimal("1")
    effective_length_m = max(length_m, config["min_order_m"])
    min_order_applied = effective_length_m > length_m

    base_rate = _to_decimal(config["base_rate"], Decimal("350")) * width_ratio
    tier_rate = base_rate
    tier_label = "base"
    for tier in config.get("tiers", []):
        if effective_length_m >= tier["min_m"]:
            tier_rate = _to_decimal(tier["rate"], tier_rate) * width_ratio
            tier_label = f">={tier['min_m']}"

    base_total_without_discount = _money(effective_length_m * base_rate)
    discounted_subtotal = _money(effective_length_m * tier_rate)
    discount_total = _money(max(Decimal("0"), base_total_without_discount - discounted_subtotal))
    urgency_extra = _money(max(Decimal("0"), discounted_subtotal * (urgency_multiplier - Decimal("1"))))
    services_total = _money(config["layout_help_fee"] if help_layout else Decimal("0"))
    shipping_total = _money(config["shipping_fee"] if with_shipping else Decimal("0"))
    total = _money(discounted_subtotal + urgency_extra + services_total + shipping_total)

    valid_until = timezone.localdate() + timedelta(days=max(1, int(config["validity_days"])))
    disclaimer = "Орієнтовна вартість. Остаточну суму підтверджує менеджер після preflight."

    return {
        "config_version": config["version"],
        "width_cm": _money(width_cm),
        "length_m": _money(length_m),
        "effective_length_m": _money(effective_length_m),
        "min_order_applied": min_order_applied,
        "urgency": urgency,
        "urgency_multiplier": _money(urgency_multiplier),
        "pricing_tier": tier_label,
        "unit_price": _money(tier_rate),
        "breakdown": {
            "base_total": discounted_subtotal,
            "discount_total": discount_total,
            "urgency_extra": urgency_extra,
            "services_total": services_total,
            "shipping_total": shipping_total,
            "total": total,
        },
        "services": {
            "help_layout": help_layout,
            "with_shipping": with_shipping,
        },
        "currency": "UAH",
        "valid_until": valid_until.isoformat(),
        "disclaimer": disclaimer,
    }
