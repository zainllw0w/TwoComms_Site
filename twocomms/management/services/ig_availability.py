"""Authoritative, exact availability decisions for Instagram commerce."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AvailabilityStatus(StrEnum):
    CONFIGURABLE = "configurable"
    ALLOCATABLE = "allocatable"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AllocationSpec:
    product_id: int
    color_variant_id: int | None = None
    size: str = ""
    fit_code: str = ""
    quantity: int = 1


@dataclass(frozen=True)
class StockAllocation:
    source: str
    stock_item_id: int | None = None
    color_variant_id: int | None = None
    quantity: int = 0


@dataclass(frozen=True)
class AvailabilityDecision:
    status: AvailabilityStatus
    reason: str
    allocation: StockAllocation | None = None

    @classmethod
    def unknown(cls, reason: str) -> "AvailabilityDecision":
        return cls(AvailabilityStatus.UNKNOWN, reason)

    @classmethod
    def unavailable(cls, reason: str) -> "AvailabilityDecision":
        return cls(AvailabilityStatus.UNAVAILABLE, reason)


def _quantity(value) -> int:
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return 0
    return quantity


def _policy(product_id: int):
    from fable5.models import ProductInventoryPolicy

    return ProductInventoryPolicy.objects.filter(product_id=product_id).first()


def _variant(spec: AllocationSpec):
    from productcolors.models import ProductColorVariant

    if spec.color_variant_id is not None:
        return ProductColorVariant.objects.filter(
            pk=spec.color_variant_id,
            product_id=spec.product_id,
        ).select_related("color").first()
    return None


def _resolve_catalog_variant(spec: AllocationSpec, *, lock: bool) -> AvailabilityDecision:
    from fable5.models import VariantSizeRule

    variant = _variant(spec)
    if variant is None:
        return AvailabilityDecision.unknown("color_variant_required")
    if _quantity(spec.quantity) <= 0:
        return AvailabilityDecision.unavailable("invalid_quantity")
    if spec.fit_code and not variant.product.fit_options.filter(
        code=spec.fit_code, is_active=True
    ).exists():
        return AvailabilityDecision.unavailable("fit_not_supported")
    rule_qs = VariantSizeRule.objects.filter(
        variant_id=variant.pk,
        size__iexact=str(spec.size or ""),
    )
    if spec.fit_code:
        rule_qs = rule_qs.filter(fit_code__in=["", spec.fit_code])
    rule = rule_qs.order_by("-fit_code", "pk").first()
    if rule is not None and not rule.is_enabled:
        return AvailabilityDecision.unavailable("size_disabled")
    available = int(variant.stock or 0)
    if rule is not None and rule.stock is not None:
        available = int(rule.stock)
    if available < int(spec.quantity):
        return AvailabilityDecision.unavailable("insufficient_catalog_variant_stock")
    return AvailabilityDecision(
        AvailabilityStatus.ALLOCATABLE,
        "catalog_variant_stock",
        StockAllocation(
            source="catalog_variant",
            color_variant_id=variant.pk,
            quantity=int(spec.quantity),
        ),
    )


def _resolve_warehouse(spec: AllocationSpec, *, lock: bool) -> AvailabilityDecision:
    from fable5.models import VariantBlankLink
    from warehouse.models import StockItem

    variant = _variant(spec)
    if variant is None:
        return AvailabilityDecision.unknown("color_variant_required")
    if _quantity(spec.quantity) <= 0:
        return AvailabilityDecision.unavailable("invalid_quantity")
    option_key = f"fit={str(spec.fit_code or '').strip().lower()}" if spec.fit_code else ""
    links = VariantBlankLink.objects.filter(variant_id=variant.pk)
    if option_key:
        links = links.filter(option_key=option_key)
    link = links.order_by("pk").first()
    if link is None:
        return AvailabilityDecision.unknown("inventory_mapping_missing")
    items = StockItem.objects.filter(
        subcategory_id=link.storage_subcategory_id,
        size__iexact=str(spec.size or ""),
    )
    if variant.color_id is None:
        items = items.filter(color__isnull=True)
    else:
        items = items.filter(color_id=variant.color_id)
    if lock:
        items = items.select_for_update()
    stock_item = items.order_by("pk").first()
    if stock_item is None or int(stock_item.quantity or 0) < int(spec.quantity):
        return AvailabilityDecision.unavailable("insufficient_warehouse_stock")
    return AvailabilityDecision(
        AvailabilityStatus.ALLOCATABLE,
        "warehouse_stock",
        StockAllocation(
            source="warehouse",
            stock_item_id=stock_item.pk,
            color_variant_id=variant.pk,
            quantity=int(spec.quantity),
        ),
    )


def resolve_allocation(spec: AllocationSpec, *, lock: bool = False) -> AvailabilityDecision:
    """Resolve one exact line using explicit MariaDB-backed inventory policy."""
    policy = _policy(spec.product_id)
    if policy is None:
        return AvailabilityDecision.unknown("inventory_policy_missing")
    if policy.source == "warehouse":
        return _resolve_warehouse(spec, lock=lock)
    if policy.source == "catalog_variant":
        return _resolve_catalog_variant(spec, lock=lock)
    return AvailabilityDecision.unknown("inventory_untracked")


def resolve_basket_allocations(
    specs: tuple[AllocationSpec, ...] | list[AllocationSpec], *, lock: bool = False
) -> AvailabilityDecision:
    """Validate a basket as one aggregate allocation operation."""
    grouped: dict[tuple, int] = {}
    first: dict[tuple, AllocationSpec] = {}
    for spec in specs or ():
        key = (spec.product_id, spec.color_variant_id, str(spec.size).casefold(), str(spec.fit_code).casefold())
        grouped[key] = grouped.get(key, 0) + _quantity(spec.quantity)
        first[key] = spec
    if not grouped:
        return AvailabilityDecision.unknown("empty_basket")
    decisions = []
    for key, quantity in grouped.items():
        base = first[key]
        decision = resolve_allocation(
            AllocationSpec(
                product_id=base.product_id,
                color_variant_id=base.color_variant_id,
                size=base.size,
                fit_code=base.fit_code,
                quantity=quantity,
            ),
            lock=lock,
        )
        decisions.append(decision)
        if decision.status != AvailabilityStatus.ALLOCATABLE:
            return decision
    first_allocation = decisions[0].allocation
    return AvailabilityDecision(
        AvailabilityStatus.ALLOCATABLE,
        "basket_allocatable",
        first_allocation,
    )
