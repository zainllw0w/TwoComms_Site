"""Normalized product collection helpers shared by Product Catalog and storefront."""

from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction

from .models import MerchCollection, ProductMerchCollection


LANGUAGES = ("uk", "ru", "en")


def _normalized_slugs(slugs: Iterable[str] | None) -> list[str]:
    return sorted(
        {
            str(slug or "").strip().lower()
            for slug in (slugs or ())
            if str(slug or "").strip()
        }
    )


def _localized(collection, field: str, language: str) -> str:
    language = language if language in LANGUAGES else "uk"
    values = (
        getattr(collection, f"{field}_{language}", ""),
        getattr(collection, f"{field}_uk", ""),
        getattr(collection, f"{field}_ru", ""),
        getattr(collection, f"{field}_en", ""),
    )
    return next((str(value).strip() for value in values if str(value).strip()), collection.slug)


def _without_implied_parents(
    collections: Iterable[MerchCollection],
    *,
    by_id: dict[int, MerchCollection] | None = None,
) -> list[MerchCollection]:
    """Keep the most specific selected nodes and suppress their ancestors."""
    rows = list(collections)
    if by_id is None:
        taxonomy = MerchCollection.objects.only("id", "parent_id")
        by_id = {collection.pk: collection for collection in taxonomy}
    selected_ids = {row.pk for row in rows}
    implied_parent_ids = set()
    for row in rows:
        seen = {row.pk}
        parent_id = row.parent_id
        while parent_id and parent_id not in seen:
            seen.add(parent_id)
            if parent_id in selected_ids:
                implied_parent_ids.add(parent_id)
            parent = by_id.get(parent_id)
            parent_id = parent.parent_id if parent is not None else None
    return [row for row in rows if row.pk not in implied_parent_ids]


def _ancestor_rows(collection, by_id, language: str) -> list[dict]:
    rows = []
    seen = {collection.pk}
    parent_id = collection.parent_id
    while parent_id and parent_id not in seen:
        seen.add(parent_id)
        parent = by_id.get(parent_id)
        if parent is None:
            break
        rows.append(
            {
                "slug": parent.slug,
                "kind": parent.kind,
                "label": _localized(parent, "name", language),
            }
        )
        parent_id = parent.parent_id
    rows.reverse()
    return rows


def get_product_collection_slugs(product) -> list[str]:
    """Return active assignments in their canonical collection order."""
    rows = (
        ProductMerchCollection.objects
        .filter(product=product, collection__is_active=True)
        .select_related("collection")
        .order_by("order", "collection__order", "collection__slug")
    )
    assignments = list(rows)
    collections = _without_implied_parents(row.collection for row in assignments)
    return [collection.slug for collection in collections]


@transaction.atomic
def set_product_collection_slugs(product, slugs: Iterable[str] | None) -> list[str]:
    """Atomically replace assignments after validating the complete requested set."""
    normalized = _normalized_slugs(slugs)
    collections = list(
        MerchCollection.objects
        .filter(slug__in=normalized, is_active=True)
        .order_by("order", "slug")
    )
    found = {collection.slug for collection in collections}
    missing = [slug for slug in normalized if slug not in found]
    if missing:
        raise ValueError(f"Unknown or inactive collection slug(s): {', '.join(missing)}")
    collections = _without_implied_parents(collections)
    normalized = [collection.slug for collection in collections]

    ProductMerchCollection.objects.select_for_update().filter(product=product).exists()
    # A collection can be deactivated after products were assigned to it.
    # Preserve that historical fact when an editor saves unrelated active tags;
    # inactive assignments remain available to admin/PDP context but are never
    # returned by public facet or link helpers.
    ProductMerchCollection.objects.filter(
        product=product, collection__is_active=True
    ).exclude(collection__slug__in=normalized).delete()
    for index, collection in enumerate(collections):
        ProductMerchCollection.objects.update_or_create(
            product=product,
            collection=collection,
            defaults={"order": index},
        )
    return get_product_collection_slugs(product)


def product_collection_context(
    product,
    *,
    language: str = "uk",
    include_inactive: bool = False,
) -> list[dict]:
    """Return presentation-safe assignments with localized ancestry and URLs."""
    language = language if language in LANGUAGES else "uk"
    all_collections = list(MerchCollection.objects.all())
    by_id = {collection.pk: collection for collection in all_collections}
    assignments = ProductMerchCollection.objects.filter(product=product).select_related(
        "collection"
    )
    if not include_inactive:
        assignments = assignments.filter(collection__is_active=True)
    assignments = list(
        assignments.order_by("order", "collection__order", "collection__slug")
    )
    visible_ids = {
        collection.pk
        for collection in _without_implied_parents(
            (assignment.collection for assignment in assignments),
            by_id=by_id,
        )
    }

    rows = []
    for assignment in assignments:
        collection = assignment.collection
        if collection.pk not in visible_ids:
            continue
        ancestors = _ancestor_rows(collection, by_id, language)
        label = assignment.display_label.strip() or _localized(collection, "name", language)
        rows.append(
            {
                "slug": collection.slug,
                "kind": collection.kind,
                "label": label,
                "description": _localized(collection, "description", language),
                "ancestors": ancestors,
                "path_label": " / ".join(
                    [ancestor["label"] for ancestor in ancestors] + [label]
                ),
                "public_path": (
                    f"/merch/{collection.slug}/"
                    if collection.is_active and collection.indexable
                    else ""
                ),
                "accent_token": collection.accent_token,
                "indexable": collection.indexable,
                "is_active": collection.is_active,
            }
        )
    return rows


def active_collection_dictionary(*, language: str = "uk") -> list[dict]:
    """Return the searchable hierarchy used by the Product Catalog picker."""
    collections = list(MerchCollection.objects.filter(is_active=True).order_by("order", "slug"))
    by_id = {collection.pk: collection for collection in collections}
    rows = []
    for collection in collections:
        ancestors = _ancestor_rows(collection, by_id, language)
        label = _localized(collection, "name", language)
        rows.append(
            {
                "slug": collection.slug,
                "kind": collection.kind,
                "label": label,
                "label_uk": _localized(collection, "name", "uk"),
                "label_ru": _localized(collection, "name", "ru"),
                "label_en": _localized(collection, "name", "en"),
                "parent_slug": by_id.get(collection.parent_id).slug
                if collection.parent_id in by_id
                else "",
                "path_label": " / ".join(
                    [ancestor["label"] for ancestor in ancestors] + [label]
                ),
                "indexable": collection.indexable,
            }
        )
    return rows


def collection_picker_state(
    rows: Iterable[dict],
    selected_slugs: Iterable[str] | None,
) -> list[dict]:
    """Decorate collection rows for an ancestor-aware editor picker."""
    rows = [dict(row) for row in rows]
    selected = set(_normalized_slugs(selected_slugs))
    by_slug = {str(row.get("slug") or ""): row for row in rows}
    derived = set()
    for slug in selected:
        current = by_slug.get(slug)
        seen = set()
        while current and current.get("parent_slug") and current["parent_slug"] not in seen:
            parent_slug = str(current["parent_slug"])
            seen.add(parent_slug)
            if parent_slug not in selected:
                derived.add(parent_slug)
            current = by_slug.get(parent_slug)
    for row in rows:
        slug = str(row.get("slug") or "")
        if slug in selected:
            row.update(selection_state="selected", is_selected=True, is_locked=False)
        elif slug in derived:
            row.update(selection_state="derived", is_selected=True, is_locked=True)
        else:
            row.update(selection_state="available", is_selected=False, is_locked=False)
    return rows
