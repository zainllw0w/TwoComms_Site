"""
Utility helpers for catalog-related views: cached categories and colour variants.
"""
from __future__ import annotations

import logging
import hashlib
from collections import defaultdict
from typing import Iterable, List, Dict, Any

from django.apps import apps
from django.core.cache import BaseCache
from django.db import DatabaseError
from django.db.models import QuerySet

from cache_utils import get_cache
from .image_variants import build_optimized_image_payload

logger = logging.getLogger(__name__)

PUBLIC_PRODUCT_ORDER_VERSION_CACHE_KEY = "products:public_order_version"
PUBLIC_CATEGORY_VERSION_CACHE_KEY = "categories:public_version"

_COLOR_LABELS_BY_HEX = {
    "000000": "Чорний",
    "050505": "Чорний",
    "111111": "Чорний",
    "151515": "Чорний",
    "FFFFFF": "Білий",
    "F5F5F5": "Білий",
    "7A5A3A": "Койот",
    "8B6B45": "Койот",
    "A47A4D": "Койот",
    "59604A": "Олива",
    "5C6449": "Олива",
    "6B6F45": "Олива",
    "4F5A3A": "Олива",
}

_COLOR_LABELS_BY_NAME = {
    "black": "Чорний",
    "white": "Білий",
    "olive": "Олива",
    "coyote": "Койот",
    "khaki": "Хакі",
}


def _display_color_name(color) -> str:
    name = (getattr(color, 'name', '') or '').strip()
    if name:
        return _COLOR_LABELS_BY_NAME.get(name.lower(), name)

    primary = (getattr(color, 'primary_hex', '') or '').strip().lstrip('#').upper()
    secondary = (getattr(color, 'secondary_hex', '') or '').strip().lstrip('#').upper()
    primary_name = _COLOR_LABELS_BY_HEX.get(primary)
    secondary_name = _COLOR_LABELS_BY_HEX.get(secondary)

    if primary_name and secondary_name and primary_name != secondary_name:
        return f'{primary_name}/{secondary_name}'
    if primary_name:
        return primary_name
    if primary:
        return f'#{primary}'
    return ''


def build_product_image_alt(product, stored_alt: str | None = None, *, color_name: str = '', index: int | None = None, main: bool = False) -> str:
    """
    Return stored ALT text or a stable Ukrainian fallback for product images.
    """
    value = (stored_alt or '').strip()
    if value:
        return value

    title = (getattr(product, 'title', '') or 'Товар TwoComms').strip()
    color = (color_name or '').strip()
    number = f' {index}' if index else ''

    if main:
        return f'{title} — головне фото товару TwoComms'
    if color:
        return f'{title} — {color} — фото{number} TwoComms'
    return f'{title} — фото{number} TwoComms'


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


def apply_public_product_order(queryset: QuerySet) -> QuerySet:
    """
    Central source of truth for public product ordering.

    Admin drag-and-drop writes to Product.priority, so every public product list
    that should reflect admin order must use this helper.
    """
    return queryset.order_by("-priority", "-id")


def get_public_product_order_version(cache_backend: BaseCache | None = None) -> int:
    """
    Version marker for public product list cache keys.

    When admin reorder changes product priority, bumping this version invalidates
    cached anonymous listing pages without clearing unrelated cache entries.
    """
    cache_backend = cache_backend or get_cache()
    version = cache_backend.get(PUBLIC_PRODUCT_ORDER_VERSION_CACHE_KEY)
    if version is None:
        cache_backend.add(PUBLIC_PRODUCT_ORDER_VERSION_CACHE_KEY, 1, timeout=None)
        version = cache_backend.get(PUBLIC_PRODUCT_ORDER_VERSION_CACHE_KEY)

    try:
        return max(int(version), 1)
    except (TypeError, ValueError):
        cache_backend.set(PUBLIC_PRODUCT_ORDER_VERSION_CACHE_KEY, 1, timeout=None)
        return 1


def bump_public_product_order_version(cache_backend: BaseCache | None = None) -> int:
    """
    Bump the public product order cache version after admin reorder commits.
    """
    cache_backend = cache_backend or get_cache()
    current_version = get_public_product_order_version(cache_backend)
    try:
        next_version = cache_backend.incr(PUBLIC_PRODUCT_ORDER_VERSION_CACHE_KEY)
    except Exception:
        next_version = current_version + 1
        cache_backend.set(PUBLIC_PRODUCT_ORDER_VERSION_CACHE_KEY, next_version, timeout=None)

    try:
        return max(int(next_version), current_version + 1)
    except (TypeError, ValueError):
        fallback_version = current_version + 1
        cache_backend.set(PUBLIC_PRODUCT_ORDER_VERSION_CACHE_KEY, fallback_version, timeout=None)
        return fallback_version


def get_public_category_version(cache_backend: BaseCache | None = None) -> int:
    """
    Version marker for public category fragments and listing pages.
    """
    cache_backend = cache_backend or get_cache()
    version = cache_backend.get(PUBLIC_CATEGORY_VERSION_CACHE_KEY)
    if version is None:
        cache_backend.add(PUBLIC_CATEGORY_VERSION_CACHE_KEY, 1, timeout=None)
        version = cache_backend.get(PUBLIC_CATEGORY_VERSION_CACHE_KEY)

    try:
        return max(int(version), 1)
    except (TypeError, ValueError):
        cache_backend.set(PUBLIC_CATEGORY_VERSION_CACHE_KEY, 1, timeout=None)
        return 1


def bump_public_category_version(cache_backend: BaseCache | None = None) -> int:
    """
    Bump the public category cache version after category mutations commit.
    """
    cache_backend = cache_backend or get_cache()
    current_version = get_public_category_version(cache_backend)
    try:
        next_version = cache_backend.incr(PUBLIC_CATEGORY_VERSION_CACHE_KEY)
    except Exception:
        next_version = current_version + 1
        cache_backend.set(PUBLIC_CATEGORY_VERSION_CACHE_KEY, next_version, timeout=None)

    try:
        return max(int(next_version), current_version + 1)
    except (TypeError, ValueError):
        fallback_version = current_version + 1
        cache_backend.set(PUBLIC_CATEGORY_VERSION_CACHE_KEY, fallback_version, timeout=None)
        return fallback_version


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
        # Use the prefetched images directly without calling .all() again
        # This prevents N+1 queries
        images = getattr(variant, '_prefetched_objects_cache', {}).get('images', [])
        if not images:
            # Fallback if prefetch didn't work
            images = list(variant.images.all()) if hasattr(variant, 'images') else []

        first_image = ''
        if images:
            first_payload = build_optimized_image_payload(images[0].image, display_width=320)
            first_image = first_payload.get('thumbnail_url') or first_payload.get('url') or ''
        preview_map[variant.product_id].append(
            {
                'id': variant.id,
                'name': _display_color_name(color),
                'primary_hex': getattr(color, 'primary_hex', '') or '',
                'secondary_hex': getattr(color, 'secondary_hex', '') or '',
                'first_image_url': first_image,
                'is_default': bool(getattr(variant, 'is_default', False)),
            }
        )

    return preview_map


def build_color_preview_key(variants: Iterable[Dict[str, Any]]) -> str:
    """
    Compact fragment-cache key for rendered colour controls.
    """
    variants = list(variants or [])
    if not variants:
        return "colors:0"

    digest = hashlib.blake2s(digest_size=8)
    for variant in variants:
        for field in ("id", "name", "primary_hex", "secondary_hex", "first_image_url", "is_default"):
            digest.update(str(variant.get(field, "")).encode("utf-8"))
            digest.update(b"\0")

    return f"colors:{len(variants)}:{digest.hexdigest()}"


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
        # Явно сортируем по order/id, чтобы порядок соответствовал админскому драг-н-дропу
        images = sorted(
            images,
            key=lambda image: (getattr(image, "order", 0), getattr(image, "id", 0)),
        )

        image_urls = []
        color_name = _display_color_name(color)
        for index, image in enumerate(images, start=1):
            if not getattr(image, "image", None):
                continue
            payload = build_optimized_image_payload(image.image)
            payload["alt"] = build_product_image_alt(
                product,
                getattr(image, "alt_text", ""),
                color_name=color_name,
                index=index,
            )
            image_urls.append(payload)

        variants.append(
            {
                'id': variant.id,
                'name': color_name,
                'primary_hex': getattr(color, 'primary_hex', '') or '',
                'secondary_hex': getattr(color, 'secondary_hex', '') or '',
                'is_default': bool(getattr(variant, 'is_default', False)),
                'images': image_urls,
            }
        )
    return variants
