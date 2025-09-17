"""
Template tags для адаптивных изображений
"""

from django import template
from django.conf import settings
import os
from pathlib import Path
from urllib.parse import urljoin

register = template.Library()

@register.inclusion_tag('responsive_image.html')
def responsive_image(image_path, alt_text="", class_name="", sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"):
    """
    Создает адаптивное изображение с поддержкой WebP/AVIF
    
    Args:
        image_path: Путь к изображению (URL)
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
    
    # Преобразуем URL в файловый путь для проверки существования
    if image_path.startswith('/media/'):
        relative_path = image_path[7:]  # убираем '/media/'
        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        base_url = os.path.dirname(image_path)
    else:
        file_path = image_path
        base_url = os.path.dirname(image_path)
    
    # Определяем базовое имя файла
    base_path = Path(file_path)
    base_name = base_path.stem
    base_dir = base_path.parent
    
    # Проверяем наличие оптимизированных версий в папке optimized
    optimized_dir = base_dir / "optimized"
    webp_file_path = optimized_dir / f"{base_name}.webp"
    avif_file_path = optimized_dir / f"{base_name}.avif"
    
    # Формируем URL для оптимизированных изображений
    if image_path.startswith('/media/'):
        webp_url = f"{base_url}/optimized/{base_name}.webp"
        avif_url = f"{base_url}/optimized/{base_name}.avif"
    else:
        webp_url = str(webp_file_path)
        avif_url = str(avif_file_path)
    
    # Проверяем наличие адаптивных версий
    responsive_sources = []
    
    # Размеры для адаптивных изображений (увеличиваем минимальные размеры)
    responsive_sizes = [480, 640, 768, 1024, 1200, 1920]
    
    for size in responsive_sizes:
        # WebP версии
        webp_responsive_file = optimized_dir / f"{base_name}_{size}w.webp"
        if webp_responsive_file.exists():
            if image_path.startswith('/media/'):
                webp_responsive_url = f"{base_url}/optimized/{base_name}_{size}w.webp"
            else:
                webp_responsive_url = str(webp_responsive_file)
            responsive_sources.append({
                'url': webp_responsive_url,
                'size': f"{size}w",
                'format': 'webp'
            })
        
        # AVIF версии
        avif_responsive_file = optimized_dir / f"{base_name}_{size}w.avif"
        if avif_responsive_file.exists():
            if image_path.startswith('/media/'):
                avif_responsive_url = f"{base_url}/optimized/{base_name}_{size}w.avif"
            else:
                avif_responsive_url = str(avif_responsive_file)
            responsive_sources.append({
                'url': avif_responsive_url,
                'size': f"{size}w",
                'format': 'avif'
            })
    
    return {
        'image_path': image_path,
        'alt_text': alt_text,
        'class_name': class_name,
        'sizes': sizes,
        'has_webp': webp_file_path.exists(),
        'has_avif': avif_file_path.exists(),
        'webp_path': webp_url if webp_file_path.exists() else None,
        'avif_path': avif_url if avif_file_path.exists() else None,
        'responsive_sources': responsive_sources
    }

@register.inclusion_tag('optimized_image.html')
def optimized_image(
    image_path,
    alt_text="",
    class_name="",
    width=None,
    height=None,
    loading="lazy",
    fetchpriority=None,
    sizes=None,
):
    """
    Создает оптимизированное изображение с автоматическим выбором формата
    
    Args:
        image_path: Путь к изображению (URL)
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
            'has_avif': False,
            'loading': loading,
            'fetchpriority': fetchpriority
        }
    
    # Преобразуем URL в файловый путь для проверки существования
    if image_path.startswith('/media/'):
        relative_path = image_path[7:]  # убираем '/media/'
        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        base_url = os.path.dirname(image_path)
    else:
        file_path = image_path
        base_url = os.path.dirname(image_path)
    
    # Определяем базовое имя файла
    base_path = Path(file_path)
    base_name = base_path.stem
    base_dir = base_path.parent
    
    # Проверяем наличие оптимизированных версий в папке optimized
    optimized_dir = base_dir / "optimized"
    webp_file_path = optimized_dir / f"{base_name}.webp"
    avif_file_path = optimized_dir / f"{base_name}.avif"
    
    # Формируем URL для оптимизированных изображений
    if image_path.startswith('/media/'):
        webp_url = f"{base_url}/optimized/{base_name}.webp"
        avif_url = f"{base_url}/optimized/{base_name}.avif"
    else:
        webp_url = str(webp_file_path)
        avif_url = str(avif_file_path)
    
    responsive_sources = []
    max_target_width = None
    try:
        max_target_width = int(width) if width else None
    except (TypeError, ValueError):
        max_target_width = None

    responsive_sizes = [320, 480, 640, 768, 960, 1280, 1600, 1920]
    if max_target_width:
        responsive_sizes = [s for s in responsive_sizes if s <= max_target_width]

    for size in responsive_sizes:
        webp_responsive_file = optimized_dir / f"{base_name}_{size}w.webp"
        if webp_responsive_file.exists():
            if image_path.startswith('/media/'):
                webp_responsive_url = f"{base_url}/optimized/{base_name}_{size}w.webp"
            else:
                webp_responsive_url = str(webp_responsive_file)
            responsive_sources.append({
                'url': webp_responsive_url,
                'size': f"{size}w",
                'format': 'webp'
            })

        avif_responsive_file = optimized_dir / f"{base_name}_{size}w.avif"
        if avif_responsive_file.exists():
            if image_path.startswith('/media/'):
                avif_responsive_url = f"{base_url}/optimized/{base_name}_{size}w.avif"
            else:
                avif_responsive_url = str(avif_responsive_file)
            responsive_sources.append({
                'url': avif_responsive_url,
                'size': f"{size}w",
                'format': 'avif'
            })

    responsive_srcsets = {'webp': '', 'avif': ''}
    if responsive_sources:
        by_format = {'webp': [], 'avif': []}
        for source in responsive_sources:
            by_format[source['format']].append(f"{source['url']} {source['size']}")
        for fmt, entries in by_format.items():
            if entries:
                responsive_srcsets[fmt] = ", ".join(sorted(entries, key=lambda item: int(item.split()[-1][:-1])))

    fallback_format = base_path.suffix.lstrip('.').lower()
    img_srcset = responsive_srcsets.get(fallback_format, '') if responsive_srcsets else ''
    default_src = image_path
    if img_srcset:
        first_entry = img_srcset.split(',')[0].strip()
        first_url = first_entry.split(' ')[0]
        if first_url:
            default_src = first_url

    return {
        'image_path': default_src,
        'alt_text': alt_text,
        'class_name': class_name,
        'width': width,
        'height': height,
        'has_webp': webp_file_path.exists(),
        'has_avif': avif_file_path.exists(),
        'webp_path': webp_url if webp_file_path.exists() else None,
        'avif_path': avif_url if avif_file_path.exists() else None,
        'responsive_sources': responsive_sources,
        'loading': loading,
        'fetchpriority': fetchpriority,
        'sizes': sizes,
        'responsive_srcsets': responsive_srcsets,
        'img_srcset': img_srcset
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
        # Проверяем наличие WebP версии в папке optimized
        optimized_dir = base_dir / "optimized"
        webp_path = optimized_dir / f"{base_name}_{size}w.webp"
        if webp_path.exists():
            srcset_items.append(f"{webp_path} {size}w")
    
    return ", ".join(srcset_items)
