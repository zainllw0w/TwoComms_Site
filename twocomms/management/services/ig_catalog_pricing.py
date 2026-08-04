"""Authoritative catalog pricing for Instagram prompt readers.

Orders already use ``fable5.services.effective_cart_unit_price``. This module
exposes the same variant/option truth to the model before it quotes a price.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from itertools import product as option_product

from django.db.models import prefetch_related_objects


logger = logging.getLogger(__name__)
MAX_OPTION_COMBINATIONS = 128

PRODUCT_PRICING_LOOKUPS = (
    "category__fable5_flows",
    "fit_options",
    "fable5_fit_notes",
    "fable5_option_profiles__i18n",
    "fable5_axis_presentations",
)
VARIANT_PRICING_LOOKUPS = (
    "color__fable5_profile",
    "fable5_details__i18n",
    "fable5_fit_rules",
    "fable5_size_rules",
    "fable5_faqs",
    "fable5_combinations__i18n",
)


def _money(value) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def money_text(value) -> str:
    amount = _money(value)
    if amount == amount.to_integral():
        return str(int(amount))
    return format(amount, "f")


def _variant_rows(product, variants=None):
    if variants is not None:
        return list(variants)
    prefetched = getattr(product, "_prefetched_objects_cache", {}).get("color_variants")
    if prefetched is not None:
        return list(prefetched)
    return list(
        product.color_variants.select_related("color").order_by("order", "id")
    )


def prepare_pricing_context(products, variants) -> None:
    """Batch-load the graph used by Fable5 pricing and content resolution."""

    product_rows = list(products)
    variant_rows = list(variants)
    product_by_id = {row.pk: row for row in product_rows}
    for variant in variant_rows:
        product = product_by_id.get(variant.product_id)
        if product is not None:
            variant.product = product
    if product_rows:
        prefetch_related_objects(product_rows, *PRODUCT_PRICING_LOOKUPS)
    if variant_rows:
        prefetch_related_objects(variant_rows, *VARIANT_PRICING_LOOKUPS)


def _variant_configurations(product, variant) -> list[dict]:
    from fable5.content_resolution import build_combination_key
    from fable5.services import (
        product_option_context,
        variant_public_context,
    )

    option_context = product_option_context(product, variant=variant)
    axes = option_context.get("axes") or []
    enabled_groups = [
        [choice for choice in (axis.get("choices") or []) if choice.get("is_enabled")]
        for axis in axes
    ]
    combinations = 1
    for group in enabled_groups:
        combinations *= len(group)
    if enabled_groups and (not all(enabled_groups) or combinations > MAX_OPTION_COMBINATIONS):
        logger.warning(
            "IG catalog option matrix unavailable for product=%s variant=%s combinations=%s",
            getattr(product, "pk", None),
            getattr(variant, "pk", None),
            combinations,
        )
        return []

    choices_iter = option_product(*enabled_groups) if enabled_groups else [()]
    rows = []
    combination_rows = {
        row.combination_key: row
        for row in variant.fable5_combinations.all()
    }
    for choices in choices_iter:
        values = {
            axis["code"]: choice["code"]
            for axis, choice in zip(axes, choices)
        }
        combination = combination_rows.get(build_combination_key(values))
        if combination is not None and not combination.is_active:
            continue
        resolved = variant_public_context(variant, option_values=values)
        price = _money(resolved.get("final_price"))
        if price <= 0:
            continue
        labels = {
            axis["code"]: str(choice.get("label") or choice.get("code") or "")
            for axis, choice in zip(axes, choices)
        }
        rows.append({
            "variant_id": variant.pk,
            "color_id": getattr(variant, "color_id", None),
            "color_slug": str(getattr(variant, "slug", "") or ""),
            "color": str(getattr(getattr(variant, "color", None), "name", "") or ""),
            "option_values": values,
            "option_labels": labels,
            "option_key": build_combination_key(values),
            "fit_code": str(values.get("fit") or ""),
            "price": price,
            "price_text": money_text(price),
            "price_reason": str(resolved.get("price_delta_reason") or "").strip(),
            "is_thermo": bool(resolved.get("is_thermo")),
            "stock": int(getattr(variant, "stock", 0) or 0),
        })
    return rows


def resolve_product_pricing(
    product,
    *,
    variants=None,
    selected_variant_id=None,
    option_values=None,
    context_prepared=False,
) -> dict:
    """Return exact/ranged prices for currently sellable product configurations."""

    variant_rows = _variant_rows(product, variants=variants)
    if not context_prepared:
        prepare_pricing_context([product], variant_rows)
    configurations = []
    for variant in variant_rows:
        if selected_variant_id and int(variant.pk) != int(selected_variant_id):
            continue
        configurations.extend(_variant_configurations(product, variant))

    selected_options = {
        str(key).strip().lower(): str(value).strip().lower()
        for key, value in (option_values or {}).items()
        if str(key).strip() and str(value).strip()
    }
    if selected_options:
        configurations = [
            row for row in configurations
            if all(row["option_values"].get(key) == value for key, value in selected_options.items())
        ]

    if not configurations and not variant_rows:
        price = _money(getattr(product, "final_price", getattr(product, "price", 0)))
        configurations = [{
            "variant_id": None,
            "color_id": None,
            "color_slug": "",
            "color": "",
            "option_values": selected_options,
            "option_labels": {},
            "option_key": "",
            "fit_code": str(selected_options.get("fit") or ""),
            "price": price,
            "price_text": money_text(price),
            "price_reason": "",
            "is_thermo": False,
        }] if price > 0 else []

    prices = sorted({row["price"] for row in configurations})
    minimum = prices[0] if prices else None
    maximum = prices[-1] if prices else None
    exact = bool(prices) and len(prices) == 1
    display = ""
    if exact:
        display = money_text(minimum)
    elif minimum is not None and maximum is not None:
        display = f"{money_text(minimum)}-{money_text(maximum)}"
    return {
        "configurations": configurations,
        "prices": prices,
        "minimum": minimum,
        "maximum": maximum,
        "exact": exact,
        "display": display,
    }


def format_variant_pricing(rows: list[dict]) -> str:
    """Compact variant matrix for the system prompt."""

    grouped: dict[int, list[dict]] = {}
    for row in rows:
        if row.get("variant_id"):
            grouped.setdefault(int(row["variant_id"]), []).append(row)
    rendered = []
    for variant_id, options in grouped.items():
        color = options[0].get("color") or "колір"
        distinct_prices = {row["price"] for row in options}
        reasons = list(dict.fromkeys(
            row["price_reason"] for row in options if row.get("price_reason")
        ))
        if len(distinct_prices) == 1:
            detail = f"ціна {options[0]['price_text']} грн"
            fits = list(dict.fromkeys(row.get("fit_code") for row in options if row.get("fit_code")))
            if fits:
                detail += f", фасони: {'/'.join(fits)}"
        else:
            parts = []
            for row in options:
                option_label = ",".join(
                    f"{key}={value}" for key, value in row["option_values"].items()
                ) or "базова"
                parts.append(f"{option_label}={row['price_text']} грн")
            detail = "ціни: " + ", ".join(dict.fromkeys(parts))
        if reasons:
            detail += ", причина: " + "; ".join(reasons)
        stock = int(options[0].get("stock") or 0)
        if stock > 0:
            detail += f", на складі {stock} шт"
        rendered.append(f"{color} (variant_id={variant_id}, {detail})")
    return ", ".join(rendered)
