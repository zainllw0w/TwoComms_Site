"""
Utility helpers for catalog-related views: cached categories and colour variants.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable, List, Dict, Any

from django.apps import apps
from django.core.cache import BaseCache
from django.db import DatabaseError

logger = logging.getLogger(__name__)


def get_categories_cached(cache_backend: BaseCache, timeout: int = 600):
    """
    Retrieve ordered categories with caching.
    """
    if cache_backend is None:
        logger.warning("No cache backend passed to get_categories_cached; querying DB directly.")
        Category = apps.get_model('storefront', 'Category')
        return list(Category.objects.filter(is_active=True).order_by('order', 'name'))

    categories = cache_backend.get('categories:ordered')
    if categories is not None:
        return categories

    Category = apps.get_model('storefront', 'Category')
    categories = list(Category.objects.filter(is_active=True).order_by('order', 'name'))
    cache_backend.set('categories:ordered', categories, timeout)
    return categories


def _load_product_color_variant_queryset(product_ids: Iterable[int]):
    """
    Internal helper that fetches ProductColorVariant queryset safely.
    """
    try:
        ProductColorVariant = apps.get_model('productcolors', 'ProductColorVariant')
    except LookupError:
        logger.debug("productcolors.ProductColorVariant is not available; skipping colour enrichment.")
        return None

    try:
        return (
            ProductColorVariant.objects.select_related('color')
            .prefetch_related('images')
            .filter(product_id__in=product_ids)
            .order_by('product_id', 'order', 'id')
        )
    except DatabaseError as exc:
        logger.warning("Failed to load ProductColorVariant rows: %s", exc, exc_info=exc)
        return None


def build_color_preview_map(products: Iterable[Any]) -> Dict[int, List[Dict[str, Any]]]:
    """
    Returns mapping {product_id: [colour preview dicts]} suitable for product cards / featured.
    """
    product_ids = [p.id for p in products if getattr(p, 'id', None)]
    if not product_ids:
        return {}

    queryset = _load_product_color_variant_queryset(product_ids)
    if queryset is None:
        return {}

    preview_map: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for variant in queryset:
        color = getattr(variant, 'color', None)
        # Используем prefetched данные для избежания N+1 запросов
        images = getattr(variant, '_prefetched_objects_cache', {}).get('images', [])
        if not images and hasattr(variant, 'images'):
            # Fallback если prefetch не сработал
            images = list(variant.images.all())
        first_image = images[0].image.url if images else ''
        preview_map[variant.product_id].append(
            {
                'id': variant.id,
                'primary_hex': getattr(color, 'primary_hex', '') or '',
                'secondary_hex': getattr(color, 'secondary_hex', '') or '',
                'first_image_url': first_image,
                'is_default': bool(getattr(variant, 'is_default', False)),
            }
        )

    return preview_map


def get_detailed_color_variants(product) -> List[Dict[str, Any]]:
    """
    Returns list of colour variants with full image sets for product detail page.
    """
    if not getattr(product, 'id', None):
        return []

    queryset = _load_product_color_variant_queryset([product.id])
    if queryset is None:
        return []

    variants: List[Dict[str, Any]] = []
    for variant in queryset:
        color = getattr(variant, 'color', None)
        # Use the prefetched images directly without calling .all() again
        # This prevents N+1 queries
        images = getattr(variant, '_prefetched_objects_cache', {}).get('images', [])
        if not images:
            # Fallback if prefetch didn't work
            images = list(variant.images.all()) if hasattr(variant, 'images') else []
        
        image_urls = [image.image.url for image in images]
        
        variants.append(
            {
                'id': variant.id,
                'primary_hex': getattr(color, 'primary_hex', '') or '',
                'secondary_hex': getattr(color, 'secondary_hex', '') or '',
                'is_default': bool(getattr(variant, 'is_default', False)),
                'images': image_urls,
            }
        )
    return variants
