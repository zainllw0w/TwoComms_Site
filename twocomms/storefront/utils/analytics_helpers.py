"""
Утилиты для аналитики и пикселей.
Генерация offer_id и полезные структурные функции.
"""
from __future__ import annotations

from typing import Optional

from django.utils.text import slugify

FEED_DEFAULT_COLOR = "Черный"


def _normalize_feed_color(raw_color: Optional[str]) -> str:
    """
    Нормализует цвет к формату, который используется в товарном фиде.
    """
    if not raw_color:
        return FEED_DEFAULT_COLOR
    trimmed = raw_color.strip()
    if not trimmed:
        return FEED_DEFAULT_COLOR
    return trimmed[0].upper() + trimmed[1:]


def _build_color_slug(raw_color: Optional[str]) -> str:
    """
    Преобразует название цвета в slug, идентичный slug в товарном фиде.
    """
    normalized = _normalize_feed_color(raw_color)
    slug = slugify(normalized, allow_unicode=True).replace("-", "")
    slug_upper = slug.upper()
    return slug_upper or "COLOR"


def get_offer_id(product_id: int, color_variant_id: Optional[int] = None, size: str = 'S') -> str:
    """
    Генерирует offer_id в том же формате, что и товарный фид.
    
    Args:
        product_id: ID товара
        color_variant_id: ID цветового варианта (может быть None)
        size: Размер (S, M, L, XL, XXL)
    
    Returns:
        str: offer_id в формате TC-{product_id:04d}-{COLOR}-{SIZE}
    """
    try:
        product_id_int = int(product_id)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid product_id for offer_id: {product_id}")

    normalized_size = (size or "S").upper()

    color_name = None
    if color_variant_id:
        try:
            from productcolors.models import ProductColorVariant  # локальный импорт, чтобы избежать циклов

            variant = (
                ProductColorVariant.objects
                .select_related("color")
                .only("id", "color__name")
                .get(id=color_variant_id)
            )
            color_name = variant.color.name if getattr(variant, "color", None) else None
        except (ValueError, TypeError):
            color_name = None
        except ProductColorVariant.DoesNotExist:
            color_name = None

    color_slug = _build_color_slug(color_name)
    return f"TC-{product_id_int:04d}-{color_slug}-{normalized_size}"


def normalize_feed_color(raw_color: Optional[str]) -> str:
    """Публичный доступ к нормализации цвета (для фидов и сервисов)."""
    return _normalize_feed_color(raw_color)


def build_feed_color_slug(raw_color: Optional[str]) -> str:
    """Публичный доступ к slug цвета, совпадающему с фидом."""
    return _build_color_slug(raw_color)


def get_item_group_id(product_id: int) -> str:
    """
    Генерирует item_group_id для группировки вариантов товара.
    
    Args:
        product_id: ID товара
    
    Returns:
        str: item_group_id в формате фида
    
    Example:
        >>> get_item_group_id(1)
        'TC-GROUP-1'
    """
    return f"TC-GROUP-{product_id}"


def parse_offer_id(offer_id: str) -> dict:
    """
    Парсит offer_id обратно в компоненты.
    
    Args:
        offer_id: offer_id в формате TC-{id}-{variant}-{SIZE}
    
    Returns:
        dict: {'product_id': int, 'variant_key': str, 'size': str}
    
    Example:
        >>> parse_offer_id('TC-4-cv2-M')
        {'product_id': 4, 'variant_key': 'cv2', 'size': 'M', 'variant_id': 2}
        >>> parse_offer_id('TC-1-default-S')
        {'product_id': 1, 'variant_key': 'default', 'size': 'S', 'variant_id': None}
    """
    parts = offer_id.split('-')
    
    if len(parts) < 4:
        raise ValueError(f"Invalid offer_id format: {offer_id}")
    
    # TC-{id}-{variant}-{SIZE}
    product_id = int(parts[1])
    variant_key = parts[2]
    size = parts[3]
    
    # Извлекаем variant_id если это cv{id}
    variant_id = None
    if variant_key.startswith('cv') and len(variant_key) > 2:
        try:
            variant_id = int(variant_key[2:])
        except ValueError:
            pass
    
    return {
        'product_id': product_id,
        'variant_key': variant_key,
        'size': size,
        'variant_id': variant_id
    }


def build_ecommerce_payload(
    offer_ids: list,
    product_name: str,
    product_category: Optional[str] = None,
    price: Optional[float] = None,
    currency: str = 'UAH',
    quantity: int = 1,
    brand: str = 'TwoComms'
) -> dict:
    """
    Создает унифицированный payload для e-commerce событий пикселей.
    
    Поддерживает Meta Pixel, TikTok Pixel и GA4.
    
    Args:
        offer_ids: Список offer_id товаров
        product_name: Название товара
        product_category: Категория товара
        price: Цена товара
        currency: Валюта (по умолчанию UAH)
        quantity: Количество
        brand: Бренд (по умолчанию TwoComms)
    
    Returns:
        dict: Унифицированный payload для всех платформ
    """
    payload = {
        # Общие поля для Meta/TikTok
        'content_ids': offer_ids,
        'content_type': 'product',
        'content_name': product_name,
        'currency': currency.upper(),
        
        # Meta Pixel contents array
        'contents': [
            {
                'id': offer_id,
                'quantity': quantity,
                'item_price': price
            }
            for offer_id in offer_ids
        ],
        
        # GA4 items array
        'items': [
            {
                'item_id': offer_id,
                'item_name': product_name,
                'item_category': product_category,
                'item_brand': brand,
                'price': price,
                'quantity': quantity
            }
            for offer_id in offer_ids
        ]
    }
    
    # Добавляем value только если цена указана
    if price is not None:
        payload['value'] = float(price) * quantity
    
    # Добавляем категорию если указана (для TikTok)
    if product_category:
        payload['content_category'] = product_category
    
    # Количество товаров
    payload['num_items'] = len(offer_ids) * quantity
    
    return payload
