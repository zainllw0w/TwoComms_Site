"""
Утилиты для аналитики и пикселей.
Генерация offer_id для синхронизации событий с фидом товаров.
"""
from typing import Optional


def get_offer_id(product_id: int, color_variant_id: Optional[int] = None, size: str = 'S') -> str:
    """
    Генерирует offer_id в формате Google Merchant Feed для синхронизации с пикселями.
    
    Формат:
    - С цветовым вариантом: TC-{product_id}-cv{variant_id}-{SIZE}
    - Без цвета (default): TC-{product_id}-default-{SIZE}
    
    Args:
        product_id: ID товара
        color_variant_id: ID цветового варианта (опционально)
        size: Размер (S, M, L, XL, XXL)
    
    Returns:
        str: offer_id в формате фида
    
    Examples:
        >>> get_offer_id(1, None, 'S')
        'TC-1-default-S'
        >>> get_offer_id(4, 2, 'M')
        'TC-4-cv2-M'
    """
    size = size.upper()  # Нормализуем размер к верхнему регистру
    
    if color_variant_id:
        return f"TC-{product_id}-cv{color_variant_id}-{size}"
    else:
        return f"TC-{product_id}-default-{size}"


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

