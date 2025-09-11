"""
Template tags для адаптивных изображений
"""

from django import template
from django.conf import settings
import os
from pathlib import Path

register = template.Library()

@register.inclusion_tag('responsive_image.html')
def responsive_image(image_path, alt_text="", class_name="", sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"):
    """
    Создает адаптивное изображение с поддержкой WebP/AVIF
    
    Args:
        image_path: Путь к изображению
        alt_text: Альтернативный текст
        class_name: CSS класс
        sizes: Атрибут sizes для srcset
    """
    if not image_path:
        return {
            'image_path': '',
            'alt_text': alt_text,
            'class_name': class_name,
            'sizes': sizes,
            'has_webp': False,
            'has_avif': False,
            'responsive_sources': []
        }
    
    # Определяем базовое имя файла
    base_path = Path(image_path)
    base_name = base_path.stem
    base_dir = base_path.parent
    
    # Проверяем наличие оптимизированных версий
    webp_path = base_dir / f"{base_name}.webp"
    avif_path = base_dir / f"{base_name}.avif"
    
    # Проверяем наличие адаптивных версий
    responsive_sources = []
    
    # Размеры для адаптивных изображений
    responsive_sizes = [320, 640, 768, 1024, 1920]
    
    for size in responsive_sizes:
        # WebP версии
        webp_responsive_path = base_dir / f"{base_name}_{size}w.webp"
        if webp_responsive_path.exists():
            responsive_sources.append({
                'url': str(webp_responsive_path),
                'size': f"{size}w",
                'format': 'webp'
            })
        
        # AVIF версии
        avif_responsive_path = base_dir / f"{base_name}_{size}w.avif"
        if avif_responsive_path.exists():
            responsive_sources.append({
                'url': str(avif_responsive_path),
                'size': f"{size}w",
                'format': 'avif'
            })
    
    return {
        'image_path': image_path,
        'alt_text': alt_text,
        'class_name': class_name,
        'sizes': sizes,
        'has_webp': webp_path.exists(),
        'has_avif': avif_path.exists(),
        'webp_path': str(webp_path) if webp_path.exists() else None,
        'avif_path': str(avif_path) if avif_path.exists() else None,
        'responsive_sources': responsive_sources
    }

@register.inclusion_tag('optimized_image.html')
def optimized_image(image_path, alt_text="", class_name="", width=None, height=None):
    """
    Создает оптимизированное изображение с автоматическим выбором формата
    
    Args:
        image_path: Путь к изображению
        alt_text: Альтернативный текст
        class_name: CSS класс
        width: Ширина изображения
        height: Высота изображения
    """
    if not image_path:
        return {
            'image_path': '',
            'alt_text': alt_text,
            'class_name': class_name,
            'width': width,
            'height': height,
            'has_webp': False,
            'has_avif': False
        }
    
    # Определяем базовое имя файла
    base_path = Path(image_path)
    base_name = base_path.stem
    base_dir = base_path.parent
    
    # Проверяем наличие оптимизированных версий
    webp_path = base_dir / f"{base_name}.webp"
    avif_path = base_dir / f"{base_name}.avif"
    
    return {
        'image_path': image_path,
        'alt_text': alt_text,
        'class_name': class_name,
        'width': width,
        'height': height,
        'has_webp': webp_path.exists(),
        'has_avif': avif_path.exists(),
        'webp_path': str(webp_path) if webp_path.exists() else None,
        'avif_path': str(avif_path) if avif_path.exists() else None
    }

@register.simple_tag
def image_srcset(image_path, sizes=None):
    """
    Создает srcset для адаптивного изображения
    
    Args:
        image_path: Путь к изображению
        sizes: Список размеров для srcset
    """
    if not image_path or not sizes:
        return ""
    
    base_path = Path(image_path)
    base_name = base_path.stem
    base_dir = base_path.parent
    
    srcset_items = []
    
    for size in sizes:
        # Проверяем наличие WebP версии
        webp_path = base_dir / f"{base_name}_{size}w.webp"
        if webp_path.exists():
            srcset_items.append(f"{webp_path} {size}w")
    
    return ", ".join(srcset_items)
