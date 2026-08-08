"""Presentation-safe merchandising facts shared by PDP, schema, and analytics."""

from __future__ import annotations

from fable5.models import ProductAudience
from fable5.services_collections import product_collection_context


LANGUAGES = {"uk", "ru", "en"}


def _language(value: str) -> str:
    code = str(value or "uk").lower().replace("_", "-").split("-", 1)[0]
    return code if code in LANGUAGES else "uk"


def _audience_rows(product, language: str) -> list[dict]:
    cached = getattr(product, "_prefetched_objects_cache", {}).get(
        "audience_assignments"
    )
    assignments = (
        cached
        if cached is not None
        else ProductAudience.objects.filter(
            product=product,
            tag__is_active=True,
        ).select_related("tag").order_by("tag__order", "tag__code")
    )
    rows = []
    for assignment in assignments:
        tag = assignment.tag
        if not tag.is_active:
            continue
        label = (
            getattr(tag, f"label_{language}", "")
            or tag.label_uk
            or tag.label_ru
            or tag.label_en
            or tag.code
        )
        rows.append({"code": tag.code, "label": label})
    return rows


def build_product_merchandising_context(
    product,
    *,
    language: str = "uk",
    selected_variant_context: dict | None = None,
) -> dict:
    """Return normalized facts without inferring from product prose or slugs."""
    language = _language(language)
    audiences = _audience_rows(product, language)
    collections = product_collection_context(product, language=language)
    selected_variant_context = selected_variant_context or {}
    variant = {
        "is_thermo": bool(selected_variant_context.get("is_thermo")),
        "thermo_note": str(selected_variant_context.get("thermo_note") or "").strip(),
        "thermo_description": str(
            selected_variant_context.get("thermo_description") or ""
        ).strip(),
        "material_story": selected_variant_context.get("material_story") or None,
        "price_difference": selected_variant_context.get("price_difference") or 0,
        "price_reason": str(
            selected_variant_context.get("price_delta_reason")
            or selected_variant_context.get("price_reason")
            or ""
        ).strip(),
    }
    audience_codes = [row["code"] for row in audiences]
    collection_codes = [row["slug"] for row in collections]
    return {
        "audiences": audiences,
        "collections": collections,
        "variant": variant,
        "analytics": {
            "audience_codes": audience_codes,
            "collection_codes": collection_codes,
            "is_thermo": variant["is_thermo"],
        },
    }
