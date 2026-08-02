"""Build a deterministic, verified catalog snapshot for commerce reasoning."""

from __future__ import annotations

import hashlib
import json

from storefront.models import Product, ProductStatus
from storefront.services.product_sales_semantics import get_effective_verified_revision

from .ig_commerce_types import CatalogGraph, CatalogProduct


def _aliases(value) -> dict[str, tuple[str, ...]]:
    return {
        str(locale): tuple(str(alias) for alias in aliases)
        for locale, aliases in sorted((value or {}).items())
        if isinstance(aliases, list)
    }


def _build_product(product) -> CatalogProduct:
    try:
        profile = product.sales_semantic_profile
    except Product.sales_semantic_profile.RelatedObjectDoesNotExist:
        profile = None
    revision = get_effective_verified_revision(profile) if profile else None
    variants = tuple(
        {
            "id": int(variant.pk),
            "slug": str(variant.slug or ""),
            "color": str(getattr(variant.color, "name", "") or ""),
            "stock": int(variant.stock or 0),
            "sku": str(variant.sku or ""),
        }
        for variant in product.color_variants.select_related("color").all()
    )
    fits = tuple(
        {
            "code": str(option.code),
            "label": str(option.label),
            "active": bool(option.is_active),
        }
        for option in product.fit_options.filter(is_active=True).all()
    )
    return CatalogProduct(
        product_id=int(product.pk),
        slug=str(product.slug),
        title=str(product.title),
        price=int(product.final_price),
        category=str(getattr(product.category, "name", "") or ""),
        aliases=_aliases(revision.aliases) if revision else {},
        traits=dict(sorted((revision.traits or {}).items())) if revision else {},
        semantic_revision_id=int(revision.pk) if revision else None,
        variants=variants,
        fits=fits,
    )


def build_catalog_graph() -> CatalogGraph:
    products = tuple(
        _build_product(product)
        for product in Product.objects.filter(status=ProductStatus.PUBLISHED)
        .select_related("category", "sales_semantic_profile__effective_revision")
        .prefetch_related("color_variants__color", "fit_options")
        .order_by("pk")
    )
    payload = [
        {
            "product_id": item.product_id,
            "slug": item.slug,
            "title": item.title,
            "price": item.price,
            "category": item.category,
            "aliases": {key: list(value) for key, value in item.aliases.items()},
            "traits": dict(item.traits),
            "semantic_revision_id": item.semantic_revision_id,
            "variants": [dict(value) for value in item.variants],
            "fits": [dict(value) for value in item.fits],
        }
        for item in products
    ]
    canonical_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CatalogGraph(products=products, digest=digest, canonical_json=canonical_json)
