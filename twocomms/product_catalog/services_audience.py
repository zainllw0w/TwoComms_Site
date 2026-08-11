"""Structured product-audience helpers for Product Catalog and the public catalog."""

from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction

from .models import AudienceTag, ProductAudience


def _normalized_codes(codes: Iterable[str] | None) -> list[str]:
    values = {
        str(code or "").strip().lower()
        for code in (codes or ())
        if str(code or "").strip()
    }
    if "unisex" in values:
        values.difference_update({"men", "women"})
    return sorted(values)


def get_product_audience_codes(product) -> list[str]:
    """Return active audience codes in the canonical tag order."""
    rows = (
        ProductAudience.objects
        .filter(product=product, tag__is_active=True)
        .select_related("tag")
        .order_by("tag__order", "tag__code")
    )
    return [row.tag.code for row in rows]


def get_effective_audience_codes(product) -> list[str]:
    """Return audience facets after expanding the canonical ``unisex`` tag."""
    explicit = get_product_audience_codes(product)
    effective = []
    for code in explicit:
        implied = ("unisex", "women", "men") if code == "unisex" else (code,)
        for candidate in implied:
            if candidate not in effective:
                effective.append(candidate)
    return effective


@transaction.atomic
def set_product_audience_codes(product, codes: Iterable[str] | None) -> list[str]:
    """Replace product assignments after validating every requested code."""
    normalized = _normalized_codes(codes)
    tags = list(AudienceTag.objects.filter(code__in=normalized, is_active=True))
    found = {tag.code for tag in tags}
    missing = [code for code in normalized if code not in found]
    if missing:
        raise ValueError(f"Unknown or inactive audience code(s): {', '.join(missing)}")

    ProductAudience.objects.filter(product=product).exclude(tag__code__in=normalized).delete()
    existing = set(
        ProductAudience.objects.filter(product=product, tag__code__in=normalized)
        .values_list("tag__code", flat=True)
    )
    ProductAudience.objects.bulk_create(
        [ProductAudience(product=product, tag=tag) for tag in tags if tag.code not in existing],
        ignore_conflicts=True,
    )
    return get_product_audience_codes(product)


def validate_published_apparel_audience(product) -> None:
    """Require an explicit audience assignment for published products."""
    if str(getattr(product, "status", "")).lower() != "published":
        return
    category = getattr(product, "category", None)
    category_text = " ".join(
        (
            str(getattr(category, "slug", "") or ""),
            str(getattr(category, "name", "") or ""),
        )
    ).lower()
    apparel_tokens = (
        "tshirt", "t-shirt", "shirt", "футбол",
        "hoodie", "hoodies", "худі", "худи",
        "long-sleeve", "longsleeve", "лонг",
    )
    if not any(token in category_text for token in apparel_tokens):
        return
    if not get_product_audience_codes(product):
        raise ValueError("Для публікації одягу виберіть хоча б одну аудиторію")
