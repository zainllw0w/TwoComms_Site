"""
Color utility functions for storefront app.

Centralized color handling to avoid code duplication across views.
"""

from typing import Optional


def hex_to_ukrainian_name(hex_value: str) -> Optional[str]:
    """
    Converts hex color code to Ukrainian color name.
    
    Args:
        hex_value: Hex color code (e.g., '#FF0000', 'FF0000')
        
    Returns:
        Ukrainian color name or None if not found
    """
    if not hex_value:
        return None
    
    h = hex_value.strip().lstrip('#').upper()
    
    COLOR_MAP = {
        '000000': 'чорний',
        'FFFFFF': 'білий',
        'FAFAFA': 'білий',
        'F5F5F5': 'білий',
        'FF0000': 'червоний',
        'C1382F': 'бордовий',
        'FFA500': 'помаранчевий',
        'FFFF00': 'жовтий',
        '00FF00': 'зелений',
        '0000FF': 'синій',
        '808080': 'сірий',
        'A52A2A': 'коричневий',
        '800080': 'фіолетовий',
    }
    
    return COLOR_MAP.get(h)


def translate_color_to_ukrainian(color_name: str) -> str:
    """
    Translates English color name to Ukrainian.
    
    Args:
        color_name: English color name
        
    Returns:
        Ukrainian color name
    """
    if not color_name:
        return color_name
    
    TRANSLATIONS = {
        'black': 'чорний',
        'white': 'білий',
        'red': 'червоний',
        'blue': 'синій',
        'green': 'зелений',
        'yellow': 'жовтий',
        'orange': 'помаранчевий',
        'purple': 'фіолетовий',
        'pink': 'рожевий',
        'gray': 'сірий',
        'grey': 'сірий',
        'brown': 'коричневий',
    }
    
    return TRANSLATIONS.get(color_name.lower(), color_name)


def normalize_color_name(raw_color: Optional[str]) -> str:
    """Normalizes color name (trims, lowercase)."""
    if not raw_color:
        return ''
    return raw_color.strip().lower()


def get_color_label_from_variant(color_variant) -> Optional[str]:
    """Returns Ukrainian text label for color variant."""
    if not color_variant:
        return None
    
    color = getattr(color_variant, 'color', None)
    if not color:
        return None
    
    name = (getattr(color, 'name', '') or '').strip()
    if name:
        return translate_color_to_ukrainian(name)
    
    primary = (getattr(color, 'primary_hex', '') or '').strip()
    secondary = (getattr(color, 'secondary_hex', '') or '').strip()
    
    if secondary:
        primary_name = hex_to_ukrainian_name(primary)
        secondary_name = hex_to_ukrainian_name(secondary)
        if primary_name and secondary_name:
            return f'{primary_name}/{secondary_name}'
        return f'{primary}+{secondary}'
    
    if primary:
        label = hex_to_ukrainian_name(primary)
        if label:
            return label
        return primary
    
    return None


def normalize_color_variant_id(raw) -> Optional[int]:
    """Normalizes color variant ID to int or None."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    try:
        value = str(raw).strip()
    except Exception:
        return None
    if not value:
        return None
    lowered = value.lower()
    if lowered in {'default', 'none', 'null', 'false', 'undefined'}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_color_variant_safe(color_variant_id):
    """Safely retrieves ProductColorVariant by ID."""
    from productcolors.models import ProductColorVariant
    
    normalized_id = normalize_color_variant_id(color_variant_id)
    if not normalized_id:
        return None
    
    try:
        return ProductColorVariant.objects.get(id=normalized_id)
    except (ProductColorVariant.DoesNotExist, ValueError, TypeError):
        return None
