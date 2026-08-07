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


def _active_collection_rows():
    from fable5.models import MerchCollection

    return list(
        MerchCollection.objects.filter(is_active=True)
        .only("id", "slug", "kind", "parent_id", "order")
        .order_by("order", "slug")
    )


def _collection_facet_contract():
    from fable5.models import MerchCollection

    rows = _active_collection_rows()
    by_id = {row.pk: row for row in rows}
    themes = {
        row.slug
        for row in rows
        if row.parent_id is None
        and row.kind in {MerchCollection.Kind.THEME, MerchCollection.Kind.CITY}
    }
    collections = {row.slug for row in rows if row.parent_id is not None}
    parent_by_child = {
        row.slug: by_id[row.parent_id].slug
        for row in rows
        if row.parent_id in by_id
    }
    return themes, collections, parent_by_child


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
    theme_values, collection_values, parent_by_child = _collection_facet_contract()
    allowed_by_facet = {
        **FACET_ALLOWED,
        "theme": theme_values,
        "collection": collection_values,
    }
    state: dict[str, tuple[str, ...]] = {}
    for facet in FACET_ORDER:
        values = _values(query, facet)
        allowed = allowed_by_facet[facet]
        normalized = []
        for value in values:
            candidate = value.lower() if facet != "size" else value.upper()
            is_dynamic_collection_facet = facet in {"theme", "collection"}
            if (allowed or is_dynamic_collection_facet) and candidate not in allowed:
                continue
            if candidate not in normalized:
                normalized.append(candidate)
        if normalized:
            state[facet] = tuple(sorted(normalized))
    selected_themes = set(state.get("theme", ()))
    for child_slug in state.get("collection", ()):
        parent_slug = parent_by_child.get(child_slug)
        while parent_slug:
            selected_themes.discard(parent_slug)
            parent_slug = parent_by_child.get(parent_slug)
    if selected_themes:
        state["theme"] = tuple(sorted(selected_themes))
    else:
        state.pop("theme", None)
    return state


def _descendant_slugs(root_slug: str) -> set[str]:
    rows = _active_collection_rows()
    by_parent = {}
    for row in rows:
        by_parent.setdefault(row.parent_id, []).append(row)
    root = next((row for row in rows if row.slug == root_slug), None)
    if root is None:
        return set()
    slugs = {root.slug}
    pending = [root.pk]
    while pending:
        parent_id = pending.pop()
        for child in by_parent.get(parent_id, ()):
            if child.slug in slugs:
                continue
            slugs.add(child.slug)
            pending.append(child.pk)
    return slugs


def filter_products_by_facets(products: QuerySet, state: Mapping[str, tuple[str, ...]]) -> QuerySet:
    """Apply strict product-level identity constraints from normalized facts."""
    result = products
    for code in state.get("audience", ()):
        result = result.filter(
            audience_assignments__tag__code=code,
            audience_assignments__tag__is_active=True,
        )
    for slug in state.get("theme", ()):
        result = result.filter(
            merch_collection_assignments__collection__slug__in=_descendant_slugs(slug),
            merch_collection_assignments__collection__is_active=True,
        )
    for slug in state.get("collection", ()):
        result = result.filter(
            merch_collection_assignments__collection__slug=slug,
            merch_collection_assignments__collection__is_active=True,
        )
    return result.distinct()
