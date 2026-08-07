"""Validated, deterministic catalog facet parsing and queryset constraints."""

from __future__ import annotations

from collections.abc import Mapping

from django.db.models import QuerySet


FACET_ORDER = ("theme", "collection", "audience", "availability", "fit", "size", "color", "thermo")
FACET_ALLOWED = {
    "theme": {"military", "brigades", "streetwear", "kharkiv"},
    "collection": set(),
    "audience": {"unisex", "women", "men"},
    "availability": {"in_stock"},
    "fit": {"classic", "oversize", "standard"},
    "size": {"XS", "S", "M", "L", "XL", "2XL", "3XL"},
    "color": set(),
    "thermo": {"thermo"},
}


def _values(query, key: str) -> list[str]:
    if hasattr(query, "getlist"):
        raw = query.getlist(key)
    else:
        raw = query.get(key, []) if isinstance(query, Mapping) else []
        if isinstance(raw, str):
            raw = [raw]
    return [str(value or "").strip() for value in raw if str(value or "").strip()]


def normalize_catalog_facet_state(query) -> dict[str, tuple[str, ...]]:
    """Normalize repeated query keys and drop unknown values."""
    state: dict[str, tuple[str, ...]] = {}
    for facet in FACET_ORDER:
        values = _values(query, facet)
        allowed = FACET_ALLOWED[facet]
        normalized = []
        for value in values:
            candidate = value.lower() if facet != "size" else value.upper()
            if allowed and candidate not in allowed:
                continue
            if candidate not in normalized:
                normalized.append(candidate)
        if normalized:
            state[facet] = tuple(sorted(normalized))
    return state


def filter_products_by_facets(products: QuerySet, state: Mapping[str, tuple[str, ...]]) -> QuerySet:
    """Apply the strict product-level audience AND constraint."""
    result = products
    for code in state.get("audience", ()):
        result = result.filter(
            audience_assignments__tag__code=code,
            audience_assignments__tag__is_active=True,
        )
    return result.distinct()
