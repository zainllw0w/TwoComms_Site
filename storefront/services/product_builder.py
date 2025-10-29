"""Service helpers for the product builder experience."""
from __future__ import annotations

from typing import Dict, Any, List, Optional

from django.db.models import Prefetch

try:
    from storefront.models import (
        Product,
        Catalog,
        CatalogOption,
        CatalogOptionValue,
        SizeGrid,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback for local package structure
    from twocomms.storefront.models import (  # type: ignore
        Product,
        Catalog,
        CatalogOption,
        CatalogOptionValue,
        SizeGrid,
    )
from productcolors.models import ProductColorVariant, ProductColorImage, Color


def _serialize_option_value(value: CatalogOptionValue) -> Dict[str, Any]:
    return {
        "id": value.id,
        "value": value.value,
        "display_name": value.display_name,
        "image": value.image.url if value.image else None,
        "order": value.order,
        "is_default": value.is_default,
        "metadata": value.metadata or {},
    }


def _serialize_option(option: CatalogOption) -> Dict[str, Any]:
    values = option.values.all().order_by("order", "id")
    return {
        "id": option.id,
        "name": option.name,
        "option_type": option.option_type,
        "is_required": option.is_required,
        "is_additional_cost": option.is_additional_cost,
        "additional_cost": option.additional_cost,
        "help_text": option.help_text,
        "order": option.order,
        "values": [_serialize_option_value(value) for value in values],
    }


def _serialize_size_grid(grid: SizeGrid) -> Dict[str, Any]:
    return {
        "id": grid.id,
        "name": grid.name,
        "image": grid.image.url if grid.image else None,
        "description": grid.description,
        "is_active": grid.is_active,
        "order": grid.order,
    }


def serialize_catalog(catalog: Catalog, *, include_options: bool = True) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": catalog.id,
        "name": catalog.name,
        "slug": catalog.slug,
        "description": catalog.description,
        "order": catalog.order,
        "is_active": catalog.is_active,
    }
    if include_options:
        options = catalog.options.all().prefetch_related("values").order_by("order", "id")
        payload["options"] = [_serialize_option(option) for option in options]
    payload["size_grids"] = [
        _serialize_size_grid(grid) for grid in catalog.size_grids.all().order_by("order", "name")
    ]
    return payload


def list_catalog_payloads(*, active_only: bool = True) -> List[Dict[str, Any]]:
    queryset = Catalog.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)
    queryset = queryset.prefetch_related(
        Prefetch("options", queryset=CatalogOption.objects.all().prefetch_related("values")),
        "size_grids",
    ).order_by("order", "name")
    return [serialize_catalog(catalog) for catalog in queryset]


def _serialize_color_variant(variant: ProductColorVariant) -> Dict[str, Any]:
    color: Color = variant.color
    images = variant.images.all().order_by("order", "id")
    return {
        "id": variant.id,
        "color_id": color.id,
        "name": color.name,
        "primary_hex": color.primary_hex,
        "secondary_hex": color.secondary_hex,
        "is_default": variant.is_default,
        "order": variant.order,
        "sku": variant.sku,
        "barcode": variant.barcode,
        "stock": variant.stock,
        "price_override": variant.price_override,
        "metadata": variant.metadata or {},
        "images": [
            {
                "id": image.id,
                "image": image.image.url if image.image else None,
                "alt_text": image.alt_text,
                "order": image.order,
            }
            for image in images
        ],
    }


def serialize_product(product: Product) -> Dict[str, Any]:
    catalog_data = serialize_catalog(product.catalog) if product.catalog else None
    size_grid_data = _serialize_size_grid(product.size_grid) if product.size_grid else None

    variants = product.color_variants.select_related("color").prefetch_related("images").order_by("order", "id")

    return {
        "id": product.id,
        "title": product.title,
        "slug": product.slug,
        "category_id": product.category_id,
        "catalog_id": product.catalog_id,
        "catalog": catalog_data,
        "size_grid_id": product.size_grid_id,
        "size_grid": size_grid_data,
        "price": product.price,
        "discount_percent": product.discount_percent,
        "featured": product.featured,
        "short_description": product.short_description,
        "full_description": product.full_description,
        "main_image": product.main_image.url if product.main_image else None,
        "main_image_alt": product.main_image_alt,
        "points_reward": product.points_reward,
        "status": product.status,
        "priority": product.priority,
        "published_at": product.published_at,
        "unpublished_reason": product.unpublished_reason,
        "last_reviewed_at": product.last_reviewed_at,
        "seo": {
            "title": product.seo_title,
            "description": product.seo_description,
            "keywords": product.seo_keywords,
            "schema": product.seo_schema,
        },
        "ai": {
            "keywords": product.ai_keywords,
            "description": product.ai_description,
            "content_generated": product.ai_content_generated,
        },
        "color_variants": [_serialize_color_variant(variant) for variant in variants],
        "recommendation_tags": product.recommendation_tags or [],
    }


def get_product_builder_payload(
    *,
    product: Optional[Product] = None,
    catalog: Optional[Catalog] = None,
) -> Dict[str, Any]:
    """Return data required for the product builder interface."""
    payload: Dict[str, Any] = {
        "catalogs": list_catalog_payloads(active_only=True),
    }

    if product:
        payload["product"] = serialize_product(product)
    elif catalog:
        payload["catalog"] = serialize_catalog(catalog)

    return payload
