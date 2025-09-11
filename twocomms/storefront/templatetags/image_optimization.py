"""
Template tags для оптимизации изображений
Автоматически выбирает лучший формат (WebP/AVIF) с fallback
"""

from django import template
from django.template import Context, Template
from django.utils.safestring import mark_safe
import os
from pathlib import Path

register = template.Library()

@register.simple_tag
def optimized_image(image_path, alt_text="", width=None, height=None, loading="lazy", class_name=""):
    """
    Создает оптимизированную версию изображения с поддержкой WebP/AVIF
    """
    if not image_path:
        return ""
    
    # Получаем путь к статическим файлам
    static_path = Path("static") / image_path.lstrip("/")
    image_path_clean = image_path.lstrip("/")
    
    # Проверяем существование файлов
    webp_path = f"{image_path_clean.rsplit('.', 1)[0]}.webp"
    avif_path = f"{image_path_clean.rsplit('.', 1)[0]}.avif"
    
    # Создаем атрибуты
    attrs = []
    if alt_text:
        attrs.append(f'alt="{alt_text}"')
    if width:
        attrs.append(f'width="{width}"')
    if height:
        attrs.append(f'height="{height}"')
    if loading:
        attrs.append(f'loading="{loading}"')
    if class_name:
        attrs.append(f'class="{class_name}"')
    
    attrs_str = " ".join(attrs)
    
    # Создаем HTML с поддержкой современных форматов
    html = f'<picture>'
    
    # AVIF (лучший сжатие)
    if os.path.exists(static_path.parent / avif_path):
        html += f'<source srcset="/static/{avif_path}" type="image/avif">'
    
    # WebP (хорошее сжатие, широкая поддержка)
    if os.path.exists(static_path.parent / webp_path):
        html += f'<source srcset="/static/{webp_path}" type="image/webp">'
    
    # Fallback на оригинальный формат
    html += f'<img src="/static/{image_path_clean}" {attrs_str}>'
    html += '</picture>'
    
    return mark_safe(html)

@register.simple_tag
def responsive_image(image_path, alt_text="", sizes="(max-width: 768px) 100vw, 50vw", loading="lazy", class_name=""):
    """
    Создает адаптивное изображение с разными размерами
    """
    if not image_path:
        return ""
    
    image_path_clean = image_path.lstrip("/")
    base_name = image_path_clean.rsplit('.', 1)[0]
    extension = image_path_clean.rsplit('.', 1)[1]
    
    # Создаем атрибуты
    attrs = []
    if alt_text:
        attrs.append(f'alt="{alt_text}"')
    if loading:
        attrs.append(f'loading="{loading}"')
    if class_name:
        attrs.append(f'class="{class_name}"')
    if sizes:
        attrs.append(f'sizes="{sizes}"')
    
    attrs_str = " ".join(attrs)
    
    # Создаем srcset для разных размеров
    srcset_webp = []
    srcset_original = []
    
    # Размеры для адаптивных изображений
    responsive_sizes = [320, 640, 768, 1024, 1280, 1920]
    
    for size in responsive_sizes:
        # Проверяем существование файлов разных размеров
        webp_responsive = f"{base_name}_{size}w.webp"
        original_responsive = f"{base_name}_{size}w.{extension}"
        
        if os.path.exists(Path("static") / webp_responsive):
            srcset_webp.append(f"/static/{webp_responsive} {size}w")
        
        if os.path.exists(Path("static") / original_responsive):
            srcset_original.append(f"/static/{original_responsive} {size}w")
    
    # Если нет адаптивных версий, используем оригинал
    if not srcset_webp and not srcset_original:
        return optimized_image(image_path, alt_text, loading=loading, class_name=class_name)
    
    html = '<picture>'
    
    # WebP srcset
    if srcset_webp:
        html += f'<source srcset="{", ".join(srcset_webp)}" type="image/webp" sizes="{sizes}">'
    
    # Original srcset
    if srcset_original:
        html += f'<source srcset="{", ".join(srcset_original)}" sizes="{sizes}">'
    
    # Fallback
    html += f'<img src="/static/{image_path_clean}" {attrs_str}>'
    html += '</picture>'
    
    return mark_safe(html)

@register.simple_tag
def icon_image(icon_path, size=24, alt_text="", class_name=""):
    """
    Создает оптимизированную иконку с правильным размером
    """
    if not icon_path:
        return ""
    
    icon_path_clean = icon_path.lstrip("/")
    base_name = icon_path_clean.rsplit('.', 1)[0]
    extension = icon_path_clean.rsplit('.', 1)[1]
    
    # Проверяем существование иконки нужного размера
    icon_size_path = f"{base_name}_{size}x{size}.{extension}"
    icon_webp_path = f"{base_name}_{size}x{size}.webp"
    
    attrs = []
    if alt_text:
        attrs.append(f'alt="{alt_text}"')
    attrs.append(f'width="{size}"')
    attrs.append(f'height="{size}"')
    if class_name:
        attrs.append(f'class="{class_name}"')
    
    attrs_str = " ".join(attrs)
    
    html = '<picture>'
    
    # WebP версия иконки
    if os.path.exists(Path("static") / icon_webp_path):
        html += f'<source srcset="/static/{icon_webp_path}" type="image/webp">'
    
    # Fallback на оригинальную иконку нужного размера или оригинал
    if os.path.exists(Path("static") / icon_size_path):
        html += f'<img src="/static/{icon_size_path}" {attrs_str}>'
    else:
        html += f'<img src="/static/{icon_path_clean}" {attrs_str}>'
    
    html += '</picture>'
    
    return mark_safe(html)

@register.filter
def image_optimization_info(image_path):
    """
    Возвращает информацию об оптимизации изображения
    """
    if not image_path:
        return {}
    
    image_path_clean = image_path.lstrip("/")
    base_name = image_path_clean.rsplit('.', 1)[0]
    
    info = {
        'original': image_path_clean,
        'webp': f"{base_name}.webp",
        'avif': f"{base_name}.avif",
        'has_webp': os.path.exists(Path("static") / f"{base_name}.webp"),
        'has_avif': os.path.exists(Path("static") / f"{base_name}.avif"),
    }
    
    return info
