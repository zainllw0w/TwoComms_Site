"""Validated, deterministic catalog facet parsing and queryset constraints."""

from __future__ import annotations

from collections.abc import Mapping
import re

from django.core.cache import cache
from django.db.models import Case, IntegerField, QuerySet, Value, When


FACET_ORDER = ("theme", "collection", "audience", "availability", "fit", "size", "color", "thermo")
FACET_ALLOWED = {
    "theme": {"military", "brigades", "streetwear", "kharkiv"},
    "collection": set(),
    "audience": {"unisex", "women", "men"},
    "availability": {"in_stock"},
    "fit": {"classic", "oversize", "standard"},
    # XXXL/3XL can exist in an informational guide, but is not a public
    # sellable facet until a persisted inventory rule makes it purchasable.
    "size": {"XS", "S", "M", "L", "XL", "2XL"},
    "color": set(),
    "thermo": {"thermo"},
}
SELLABLE_SIZE_ORDER = ("XS", "S", "M", "L", "XL", "2XL")
FIT_ALIASES = {
    "classic": "classic",
    "класичний": "classic",
    "oversize": "oversize",
    "оверсайз": "oversize",
    "regular": "standard",
    "standard": "standard",
    "стандартний": "standard",
}
_COLOR_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_COLLECTION_FACET_CONTRACT_CACHE_KEY = "catalog:facet-taxonomy-contract:v1"
_COLLECTION_FACET_CONTRACT_CACHE_TIMEOUT = 300


def _active_collection_rows():
    from product_catalog.models import MerchCollection

    return list(
        MerchCollection.objects.filter(is_active=True)
        .only("id", "slug", "kind", "parent_id", "order")
        .order_by("order", "slug")
    )


def _collection_facet_contract():
    from product_catalog.models import MerchCollection

    cached = cache.get(_COLLECTION_FACET_CONTRACT_CACHE_KEY)
    if cached is not None:
        themes, collections, parent_by_child = cached
        return set(themes), set(collections), dict(parent_by_child)

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
    cache.set(
        _COLLECTION_FACET_CONTRACT_CACHE_KEY,
        (tuple(sorted(themes)), tuple(sorted(collections)), parent_by_child),
        _COLLECTION_FACET_CONTRACT_CACHE_TIMEOUT,
    )
    return themes, collections, parent_by_child


def invalidate_collection_facet_contract():
    cache.delete(_COLLECTION_FACET_CONTRACT_CACHE_KEY)


def redundant_parent_theme_slugs(query) -> set[str]:
    """Return selected themes already implied by selected leaf collections."""
    selected_themes = {value.lower() for value in _values(query, "theme")}
    selected_collections = {value.lower() for value in _values(query, "collection")}
    if not selected_themes or not selected_collections:
        return set()

    themes, collections, parent_by_child = _collection_facet_contract()
    redundant = set()
    for child_slug in selected_collections:
        if child_slug not in collections:
            continue
        seen = {child_slug}
        parent_slug = parent_by_child.get(child_slug)
        while parent_slug and parent_slug not in seen:
            seen.add(parent_slug)
            if parent_slug in themes and parent_slug in selected_themes:
                redundant.add(parent_slug)
            parent_slug = parent_by_child.get(parent_slug)
    return redundant


def _values(query, key: str) -> list[str]:
    if hasattr(query, "getlist"):
        raw = query.getlist(key)
    else:
        raw = query.get(key, []) if isinstance(query, Mapping) else []
        if isinstance(raw, str):
            raw = [raw]
    return [str(value or "").strip() for value in raw if str(value or "").strip()]


def normalize_catalog_facet_state(
    query,
    *,
    allowed_colors: set[str] | None = None,
) -> dict[str, tuple[str, ...]]:
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
        if facet == "color" and allowed_colors is not None:
            allowed = {str(value).strip().lower() for value in allowed_colors}
        normalized = []
        for value in values:
            candidate = value.lower() if facet != "size" else value.upper()
            if facet == "fit":
                candidate = FIT_ALIASES.get(candidate, candidate)
            is_dynamic_collection_facet = facet in {"theme", "collection"}
            if facet == "color" and not _COLOR_SLUG_RE.fullmatch(candidate):
                continue
            if facet == "color" and allowed_colors is None and not candidate:
                continue
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


def active_collection_descendant_slugs(root_slug: str) -> set[str]:
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


def _prefetched(product, relation):
    return getattr(product, "_prefetched_objects_cache", {}).get(relation)


def _variant_rows(product):
    cached = _prefetched(product, "color_variants")
    if cached is not None:
        return list(cached)
    from productcolors.models import ProductColorVariant

    return list(
        ProductColorVariant.objects.filter(product=product)
        .select_related("color__product_catalog_profile")
        .prefetch_related("product_catalog_fit_rules", "product_catalog_size_rules")
        .order_by("order", "id")
    )


def _rules_for(variant, relation):
    cached = _prefetched(variant, relation)
    if cached is not None:
        return list(cached)
    return list(getattr(variant, relation).all())


def _normal_size(value):
    from product_catalog.size_grid_services import normalize_size_value

    return normalize_size_value(value)


def _rule_allows_size(variant, size, fit_code=""):
    wanted = _normal_size(size)
    if wanted not in SELLABLE_SIZE_ORDER:
        return False
    rules = [
        rule for rule in _rules_for(variant, "product_catalog_size_rules")
        if _normal_size(rule.size) == wanted and str(rule.fit_code or "").strip().lower() in {"", str(fit_code or "").strip().lower()}
    ]
    if not rules:
        # A missing rule preserves the legacy made-to-order size surface; the
        # informational 3XL row is excluded above and never becomes sellable.
        return True
    specific_fit = str(fit_code or "").strip().lower()
    specific = next((rule for rule in reversed(rules) if str(rule.fit_code or "").strip().lower() == specific_fit and specific_fit), None)
    general = next((rule for rule in reversed(rules) if not str(rule.fit_code or "").strip()), None)
    rule = specific or general or rules[-1]
    return bool(rule.is_enabled and (rule.stock is None or rule.stock > 0))


def _rule_allows_fit(variant, fit_code=""):
    wanted = str(fit_code or "").strip().lower()
    if not wanted:
        return True
    rules = [
        rule for rule in _rules_for(variant, "product_catalog_fit_rules")
        if str(rule.fit_code or "").strip().lower() == wanted
    ]
    return not rules or bool(rules[-1].is_enabled)


def _product_fit_codes(product):
    cached = _prefetched(product, "fit_options")
    if cached is None:
        try:
            cached = list(product.fit_options.filter(is_active=True).order_by("order", "id"))
        except Exception:
            cached = []
    return {
        FIT_ALIASES.get(
            str(option.code or "").strip().lower(),
            str(option.code or "").strip().lower(),
        )
        for option in cached
        if getattr(option, "is_active", True) and str(option.code or "").strip()
    }


def _product_matches_inventory_facets(product, state):
    if state.get("availability") and not getattr(product, "is_dropship_available", True):
        return False

    variants = _variant_rows(product)
    if state.get("thermo"):
        variants = [
            variant for variant in variants
            if bool(getattr(getattr(variant.color, "product_catalog_profile", None), "is_thermo", False))
        ]
        if not variants:
            return False

    selected_fits = tuple(state.get("fit", ()))
    if selected_fits:
        product_fits = _product_fit_codes(product)
        inventory_requires_variant = bool(
            state.get("availability")
            or state.get("size")
            or state.get("color")
            or state.get("thermo")
        )
        if product_fits:
            if any(code not in product_fits for code in selected_fits):
                return False
        elif not variants and selected_fits != ("standard",):
            return False
        if not variants and not inventory_requires_variant:
            return True
        variants = [
            variant for variant in variants
            if all(_rule_allows_fit(variant, fit) for fit in selected_fits)
        ]
        if not variants:
            return False

    selected_colors = tuple(state.get("color", ()))
    if selected_colors:
        selected_color_set = set(selected_colors)
        variants = [
            variant
            for variant in variants
            if str(getattr(variant, "slug", "") or "").strip().lower()
            in selected_color_set
        ]
        if not variants:
            return False

    selected_sizes = tuple(state.get("size", ()))
    if selected_sizes:
        # Multiple sizes are strict AND constraints: each requested size must
        # be purchasable for the selected fit/variant surface.
        for size in selected_sizes:
            if not any(
                all(_rule_allows_fit(variant, fit) for fit in selected_fits)
                and _rule_allows_size(variant, size, selected_fits[0] if selected_fits else "")
                for variant in variants
            ):
                return False

    if state.get("availability"):
        if not variants:
            return False
        if selected_sizes:
            return True
        if not any(
            all(_rule_allows_fit(variant, fit) for fit in selected_fits)
            and any(_rule_allows_size(variant, size, selected_fits[0] if selected_fits else "") for size in SELLABLE_SIZE_ORDER)
            for variant in variants
        ):
            return False
    return True


def filter_products_by_facets(products: QuerySet, state: Mapping[str, tuple[str, ...]]) -> QuerySet:
    """Apply strict normalized merchandising and inventory constraints."""
    result = products
    audience_codes = tuple(state.get("audience", ()))
    for code in audience_codes:
        effective_codes = {code}
        if len(audience_codes) == 1 and code in {"men", "women"}:
            effective_codes.add("unisex")
        result = result.filter(
            audience_assignments__tag__code__in=effective_codes,
            audience_assignments__tag__is_active=True,
        )
    for slug in state.get("theme", ()):
        result = result.filter(
            merch_collection_assignments__collection__slug__in=active_collection_descendant_slugs(slug),
            merch_collection_assignments__collection__is_active=True,
        )
    for slug in state.get("collection", ()):
        result = result.filter(
            merch_collection_assignments__collection__slug__in=active_collection_descendant_slugs(slug),
            merch_collection_assignments__collection__is_active=True,
        )
    result = result.distinct()
    inventory_facets = {"availability", "fit", "size", "color", "thermo"}
    if not inventory_facets.intersection(state):
        return result

    candidates = list(
        result.select_related("category")
        .prefetch_related(
            "color_variants__color__product_catalog_profile",
            "color_variants__product_catalog_fit_rules",
            "color_variants__product_catalog_size_rules",
            "fit_options",
        )
    )
    matched_ids = [product.pk for product in candidates if _product_matches_inventory_facets(product, state)]
    if not matched_ids:
        return result.none()
    ordering = Case(
        *[When(pk=pk, then=Value(index)) for index, pk in enumerate(matched_ids)],
        output_field=IntegerField(),
    )
    return result.filter(pk__in=matched_ids).order_by(ordering)
