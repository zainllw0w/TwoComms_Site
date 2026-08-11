"""Shared catalog compatibility resolution for graph and prompt consumers."""

from __future__ import annotations

from copy import deepcopy

from django.core.exceptions import ValidationError

from product_catalog.size_grid_services import (
    normalize_size_grid_payload,
    normalize_size_value,
)


def _prefetched(obj, relation):
    cache = getattr(obj, "_prefetched_objects_cache", {})
    return list(cache.get(relation, ()))


def _usable_grid(grid):
    if grid is None or not grid.is_active:
        return None
    try:
        profile = grid.product_catalog_profile
    except Exception:
        profile = None
    return grid if profile is None or profile.is_active else None


def _grid_sizes(grid) -> list[str]:
    grid = _usable_grid(grid)
    if grid is None:
        return []
    try:
        guide = normalize_size_grid_payload(deepcopy(grid.guide_data or {}))
    except ValidationError:
        return []
    return list(dict.fromkeys(
        normalized
        for row in guide.get("rows", ())
        if (normalized := normalize_size_value(row.get("size")))
    ))


def _catalog_sizes(product) -> list[str]:
    catalog = getattr(product, "catalog", None)
    if catalog is None:
        return []
    size_options = sorted(
        (
            option for option in _prefetched(catalog, "options")
            if option.option_type == "size"
        ),
        key=lambda option: (option.order, option.id),
    )
    if not size_options:
        return []
    values = sorted(
        _prefetched(size_options[0], "values"),
        key=lambda value: (value.order, value.id),
    )
    return list(dict.fromkeys(
        normalized
        for value in values
        if (normalized := normalize_size_value(value.value))
    ))


def _fallback_grid(product, option_key):
    direct = _usable_grid(getattr(product, "size_grid", None))
    if direct is not None:
        return direct
    catalog = getattr(product, "catalog", None)
    if catalog is None:
        return None
    grids = sorted(
        (
            grid for grid in _prefetched(catalog, "size_grids")
            if _usable_grid(grid) is not None
        ),
        key=lambda grid: (grid.order, grid.name, grid.id),
    )
    if not grids:
        return None
    exact = []
    neutral = []
    for grid in grids:
        try:
            profile_key = str(grid.product_catalog_profile.option_key or "")
        except Exception:
            profile_key = ""
        if profile_key == option_key:
            exact.append(grid)
        elif not profile_key:
            neutral.append(grid)
    return (exact or neutral or grids)[0]


def resolve_configuration_size_contract(
    product,
    variant,
    row,
) -> tuple[tuple[str, ...], bool]:
    """Return exact sizes and whether an authoritative size source exists."""

    option_key = str(row.get("option_key") or "")
    fit_code = str(row.get("fit_code") or "")
    product_assignments = {
        assignment.option_key: assignment
        for assignment in _prefetched(product, "product_catalog_size_grid_assignments")
    }
    variant_assignments = {
        assignment.option_key: assignment
        for assignment in _prefetched(variant, "product_catalog_size_grid_assignments")
    }
    variant_assignment = variant_assignments.get(option_key)
    product_assignment = product_assignments.get(option_key)
    explicit_variant_grid = variant_assignment is not None
    catalog = getattr(product, "catalog", None)
    declared_catalog_grids = _prefetched(catalog, "size_grids") if catalog else []
    has_declared_grid = bool(
        variant_assignment is not None
        or product_assignment is not None
        or getattr(product, "size_grid_id", None)
        or declared_catalog_grids
    )
    grid = _usable_grid(
        variant_assignment.size_grid
        if variant_assignment is not None
        else product_assignment.size_grid
        if product_assignment is not None
        else _fallback_grid(product, option_key)
    )
    sizes = _grid_sizes(grid)
    catalog_sizes = _catalog_sizes(product)
    if sizes and catalog_sizes and not explicit_variant_grid:
        sizes = [size for size in catalog_sizes if size in sizes]
    elif not sizes:
        sizes = catalog_sizes

    product_rules = {
        (rule.option_key, normalize_size_value(rule.size)): rule
        for rule in _prefetched(product, "product_catalog_size_rules")
    }
    variant_rules = {
        (rule.fit_code, normalize_size_value(rule.size)): rule
        for rule in _prefetched(variant, "product_catalog_size_rules")
    }
    has_contract = bool(
        has_declared_grid
        or catalog_sizes
        or product_rules
        or variant_rules
    )
    resolved = []
    for size in sizes:
        product_rule = product_rules.get((option_key, size))
        if product_rule is not None and not product_rule.is_enabled:
            continue
        variant_rule = (
            variant_rules.get((fit_code, size))
            or variant_rules.get(("", size))
        )
        if variant_rule is not None and not variant_rule.is_enabled:
            continue
        resolved.append(size)
    return tuple(resolved), has_contract


def resolve_configuration_sizes(product, variant, row) -> tuple[str, ...]:
    """Return enabled sizes for one exact variant/option configuration."""

    sizes, _has_contract = resolve_configuration_size_contract(
        product,
        variant,
        row,
    )
    return sizes
