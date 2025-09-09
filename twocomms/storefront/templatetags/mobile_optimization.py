from django import template
from django.conf import settings
import os

register = template.Library()

@register.simple_tag
def mobile_image_url(image_url, size='medium'):
    """
    Возвращает оптимизированный URL изображения для мобильных устройств
    """
    if not image_url:
        return ''
    
    # Определяем размеры для мобильных
    mobile_sizes = {
        'small': '200x200',
        'medium': '400x400', 
        'large': '600x600',
        'thumbnail': '150x150'
    }
    
    # Если это внешний URL (например, Google аватар), возвращаем как есть
    if image_url.startswith('http'):
        return image_url
    
    # Для локальных изображений добавляем параметры оптимизации
    if hasattr(settings, 'MEDIA_URL') and image_url.startswith(settings.MEDIA_URL):
        # Здесь можно добавить логику для создания WebP версий
        # или использования CDN с параметрами сжатия
        return image_url
    
    return image_url

@register.simple_tag
def mobile_image_srcset(image_url, sizes=None):
    """
    Создает srcset для адаптивных изображений на мобильных
    """
    if not image_url or not sizes:
        return ''
    
    if sizes is None:
        sizes = ['200w', '400w', '600w']
    
    srcset_parts = []
    for size in sizes:
        # Здесь можно добавить логику для создания разных размеров
        srcset_parts.append(f"{image_url} {size}")
    
    return ', '.join(srcset_parts)

@register.simple_tag
def is_mobile_device(request):
    """
    Определяет, является ли устройство мобильным
    """
    if not request:
        return False
    
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'tablet']
    
    return any(keyword in user_agent for keyword in mobile_keywords)

@register.simple_tag
def mobile_viewport_meta():
    """
    Возвращает оптимизированный viewport meta тег для мобильных
    """
    return '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes, viewport-fit=cover">'

@register.simple_tag
def mobile_preload_critical():
    """
    Возвращает preload теги для критических ресурсов на мобильных
    """
    critical_resources = [
        'css/mobile-critical.css',
        'fonts/inter-var.woff2',
        'img/logo.svg'
    ]
    
    preload_tags = []
    for resource in critical_resources:
        resource_type = 'style' if resource.endswith('.css') else 'font' if resource.endswith(('.woff2', '.woff')) else 'image'
        preload_tags.append(f'<link rel="preload" href="/static/{resource}" as="{resource_type}">')
    
    return '\n'.join(preload_tags)

@register.simple_tag
def mobile_touch_optimization():
    """
    Возвращает CSS для оптимизации touch взаимодействий
    """
    return '''
    <style>
    /* Оптимизация touch для мобильных */
    * {
        -webkit-tap-highlight-color: transparent;
        -webkit-touch-callout: none;
        -webkit-user-select: none;
        -khtml-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }
    
    input, textarea, [contenteditable] {
        -webkit-user-select: text;
        -khtml-user-select: text;
        -moz-user-select: text;
        -ms-user-select: text;
        user-select: text;
    }
    
    /* Улучшение прокрутки */
    .scroll-container {
        -webkit-overflow-scrolling: touch;
        overscroll-behavior: contain;
    }
    
    /* Оптимизация анимаций */
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
            scroll-behavior: auto !important;
        }
    }
    </style>
    '''
