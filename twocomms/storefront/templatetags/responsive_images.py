# twocomms/storefront/templatetags/responsive_images.py

"""
Template tags для генерации responsive изображений с WebP поддержкой.
"""

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe
import os

register = template.Library()


@register.simple_tag
def responsive_image(image, alt='', sizes='100vw', lazy=True, css_class=''):
    """
    Генерирует responsive image с WebP fallback и srcset.
    
    Использование:
    {% load responsive_images %}
    {% responsive_image product.main_image alt=product.title sizes="(max-width: 640px) 100vw, 50vw" %}
    """
    if not image:
        return ''
    
    # Получаем URL изображения
    if hasattr(image, 'url'):
        image_url = image.url
    else:
        image_url = str(image)
    
    # Определяем базовый путь и расширение
    base_path, ext = os.path.splitext(image_url)
    
    # Генерируем loading атрибут
    loading_attr = 'loading="lazy"' if lazy else ''
    
    # Простая WebP версия (без srcset пока)
    webp_url = f"{base_path}.webp"
    
    # Генерируем HTML
    html = f'''<picture>
    <source type="image/webp" srcset="{webp_url}">
    <img src="{image_url}" alt="{alt}" {loading_attr} class="{css_class}" decoding="async">
</picture>'''
    
    return mark_safe(html)


@register.filter
def get_webp_url(image_url):
    """Получить WebP версию URL изображения"""
    if not image_url:
        return ''
    base_path, ext = os.path.splitext(str(image_url))
    return f"{base_path}.webp"


register.filter('get_webp_url', get_webp_url)
