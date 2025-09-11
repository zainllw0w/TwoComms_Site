"""
Template tags для оптимизации CLS (Cumulative Layout Shift)
"""

from django import template
from django.conf import settings
from django.utils.html import format_html
import os
from pathlib import Path

register = template.Library()

@register.simple_tag
def optimized_image(image_path, alt_text="", width=None, height=None, class_name="", lazy=True):
    """
    Создает оптимизированное изображение с фиксированными размерами для предотвращения CLS
    
    Args:
        image_path: Путь к изображению
        alt_text: Альтернативный текст
        width: Ширина изображения
        height: Высота изображения
        class_name: CSS класс
        lazy: Lazy loading
    """
    if not image_path:
        return ""
    
    attributes = []
    
    # Добавляем размеры для предотвращения CLS
    if width and height:
        attributes.append(f'width="{width}"')
        attributes.append(f'height="{height}"')
        # Добавляем aspect-ratio для предотвращения CLS
        aspect_ratio = width / height
        style = f'aspect-ratio: {aspect_ratio};'
    else:
        # По умолчанию квадратное изображение
        style = 'aspect-ratio: 1;'
    
    if class_name:
        attributes.append(f'class="{class_name}"')
    
    if lazy:
        attributes.append('loading="lazy"')
        attributes.append('decoding="async"')
    
    attributes.append(f'style="{style}"')
    attributes.append(f'alt="{alt_text}"')
    attributes.append(f'src="{image_path}"')
    
    return format_html('<img {}>', ' '.join(attributes))

@register.simple_tag
def product_image(product, size="medium", class_name="product-image", lazy=True):
    """
    Создает оптимизированное изображение товара с фиксированными размерами
    
    Args:
        product: Объект товара
        size: Размер изображения (small, medium, large)
        class_name: CSS класс
        lazy: Lazy loading
    """
    if not product or not product.main_image:
        return format_html('<div class="{} image-skeleton" style="aspect-ratio: 1;"></div>', class_name)
    
    # Определяем размеры в зависимости от размера
    size_map = {
        'small': (150, 150),
        'medium': (300, 300),
        'large': (600, 600)
    }
    
    width, height = size_map.get(size, (300, 300))
    
    return optimized_image(
        product.main_image.url,
        product.name,
        width=width,
        height=height,
        class_name=class_name,
        lazy=lazy
    )

@register.simple_tag
def category_icon(category, size="medium", class_name="category-icon", lazy=True):
    """
    Создает оптимизированную иконку категории с фиксированными размерами
    
    Args:
        category: Объект категории
        size: Размер иконки (small, medium, large)
        class_name: CSS класс
        lazy: Lazy loading
    """
    if not category or not category.icon:
        return format_html('<div class="{} image-skeleton" style="aspect-ratio: 1; width: 48px; height: 48px;"></div>', class_name)
    
    # Определяем размеры в зависимости от размера
    size_map = {
        'small': (24, 24),
        'medium': (48, 48),
        'large': (96, 96)
    }
    
    width, height = size_map.get(size, (48, 48))
    
    return optimized_image(
        category.icon.url,
        category.name,
        width=width,
        height=height,
        class_name=class_name,
        lazy=lazy
    )

@register.simple_tag
def avatar_image(user, size="medium", class_name="avatar", lazy=True):
    """
    Создает оптимизированный аватар пользователя с фиксированными размерами
    
    Args:
        user: Объект пользователя
        size: Размер аватара (small, medium, large)
        class_name: CSS класс
        lazy: Lazy loading
    """
    if not user or not hasattr(user, 'userprofile') or not user.userprofile.avatar:
        return format_html('<div class="{} image-skeleton" style="aspect-ratio: 1; border-radius: 50%;"></div>', class_name)
    
    # Определяем размеры в зависимости от размера
    size_map = {
        'small': (32, 32),
        'medium': (40, 40),
        'large': (80, 80)
    }
    
    width, height = size_map.get(size, (40, 40))
    
    return optimized_image(
        user.userprofile.avatar.url,
        user.get_full_name() or user.username,
        width=width,
        height=height,
        class_name=class_name,
        lazy=lazy
    )

@register.simple_tag
def logo_image(size="medium", class_name="logo", lazy=False):
    """
    Создает оптимизированный логотип с фиксированными размерами
    
    Args:
        size: Размер логотипа (small, medium, large)
        class_name: CSS класс
        lazy: Lazy loading (по умолчанию False для логотипа)
    """
    # Определяем размеры в зависимости от размера
    size_map = {
        'small': (120, 40),
        'medium': (180, 60),
        'large': (240, 80)
    }
    
    width, height = size_map.get(size, (180, 60))
    
    return optimized_image(
        '/static/img/logo.svg',
        'TwoComms Logo',
        width=width,
        height=height,
        class_name=class_name,
        lazy=lazy
    )

@register.simple_tag
def hero_image(image_path, alt_text="", class_name="hero-image", lazy=False):
    """
    Создает оптимизированное изображение для hero секции с фиксированными размерами
    
    Args:
        image_path: Путь к изображению
        alt_text: Альтернативный текст
        class_name: CSS класс
        lazy: Lazy loading (по умолчанию False для hero изображений)
    """
    if not image_path:
        return format_html('<div class="{} image-skeleton" style="aspect-ratio: 16/9; width: 100%;"></div>', class_name)
    
    return optimized_image(
        image_path,
        alt_text,
        width=1920,
        height=1080,
        class_name=class_name,
        lazy=lazy
    )

@register.simple_tag
def product_card(product, class_name="product-card"):
    """
    Создает оптимизированную карточку товара с фиксированными размерами
    
    Args:
        product: Объект товара
        class_name: CSS класс
    """
    if not product:
        return format_html('<div class="{}"><div class="image-skeleton" style="aspect-ratio: 1;"></div></div>', class_name)
    
    image_html = product_image(product, size="medium", class_name="product-image")
    
    return format_html("""
    <div class="{}">
        {}
        <div class="product-info">
            <h3 class="product-title">{}</h3>
            <div class="product-price">{} грн</div>
        </div>
    </div>
    """,
    class_name,
    image_html,
    product.name,
    product.price
    )

@register.simple_tag
def category_card(category, class_name="category-card"):
    """
    Создает оптимизированную карточку категории с фиксированными размерами
    
    Args:
        category: Объект категории
        class_name: CSS класс
    """
    if not category:
        return format_html('<div class="{}"><div class="image-skeleton" style="aspect-ratio: 1;"></div></div>', class_name)
    
    icon_html = category_icon(category, size="medium", class_name="category-icon")
    
    return format_html("""
    <a href="/category/{}/" class="{}">
        {}
        <span class="category-name">{}</span>
    </a>
    """,
    category.slug,
    class_name,
    icon_html,
    category.name
    )

@register.simple_tag
def skeleton_loader(width=None, height=None, class_name="skeleton"):
    """
    Создает skeleton loader с фиксированными размерами
    
    Args:
        width: Ширина
        height: Высота
        class_name: CSS класс
    """
    style = "background: linear-gradient(90deg, #1a1a1a 25%, #2a2a2a 50%, #1a1a1a 75%); background-size: 200% 100%; animation: loading 1.5s infinite;"
    
    if width and height:
        style += f" width: {width}px; height: {height}px;"
    else:
        style += " aspect-ratio: 1;"
    
    return format_html('<div class="{}" style="{}"></div>', class_name, style)
