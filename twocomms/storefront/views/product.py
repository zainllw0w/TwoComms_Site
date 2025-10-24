"""
Product views - Детальная информация о товарах.

Содержит views для:
- Детальной страницы товара
- Получения изображений
- Цветовых вариантов
- Отзывов (в будущем)
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse

from ..models import Product
from ..services.catalog_helpers import get_detailed_color_variants
from .utils import cache_page_for_anon


# ==================== PRODUCT VIEWS ====================

@cache_page_for_anon(600)  # Кэшируем карточку товара на 10 минут для анонимов
def product_detail(request, slug):
    """
    Детальная страница товара.
    
    Args:
        slug (str): Уникальный slug товара
        
    Features:
    - Основная информация о товаре
    - Галерея изображений
    - Цветовые варианты с изображениями
    - Автоматический выбор первого цвета (если нет main_image)
    - SEO breadcrumbs
    - Рекомендованные товары (опционально)
    
    Context:
        product: Объект товара
        images: Дополнительные изображения товара
        color_variants: Список цветовых вариантов с изображениями
        auto_select_first_color: Флаг автовыбора первого цвета
        breadcrumbs: Хлебные крошки для SEO
    """
    product = get_object_or_404(Product.objects.select_related('category'), slug=slug)
    images = product.images.all()
    
    # Варианты цветов с изображениями (если есть приложение и данные)
    color_variants = get_detailed_color_variants(product)
    auto_select_first_color = False

    if color_variants:
        # Находим default вариант и перемещаем его на первое место
        default_index = next(
            (idx for idx, variant in enumerate(color_variants) 
             if variant.get('is_default')),
            0
        )
        
        if default_index != 0:
            default_variant = color_variants.pop(default_index)
            color_variants.insert(0, default_variant)
        
        # Устанавливаем первый вариант как default
        for idx, variant in enumerate(color_variants):
            variant['is_default'] = (idx == 0)
        
        # Если нет главного изображения, автоматически выбираем первый цвет
        if not product.main_image:
            auto_select_first_color = True
    
    # Генерируем breadcrumbs для SEO
    breadcrumbs = [
        {'name': 'Головна', 'url': reverse('home')},
        {'name': 'Каталог', 'url': reverse('catalog')},
    ]
    
    if product.category:
        breadcrumbs.append({
            'name': product.category.name,
            'url': reverse('catalog_by_cat', kwargs={'cat_slug': product.category.slug})
        })
    
    breadcrumbs.append({
        'name': product.title,
        'url': reverse('product', kwargs={'slug': product.slug})
    })
    
    return render(
        request,
        'pages/product_detail.html',
        {
            'product': product,
            'images': images,
            'color_variants': color_variants,
            'auto_select_first_color': auto_select_first_color,
            'breadcrumbs': breadcrumbs
        }
    )


def get_product_images(request, product_id):
    """
    AJAX endpoint для получения изображений товара.
    
    Args:
        product_id (int): ID товара
        
    Returns:
        JsonResponse: Список URL изображений
    """
    try:
        product = Product.objects.get(id=product_id)
        images = product.images.all()
        
        image_urls = []
        
        # Главное изображение
        if product.main_image:
            image_urls.append({
                'url': product.main_image.url,
                'is_main': True
            })
        
        # Дополнительные изображения
        for img in images:
            image_urls.append({
                'url': img.image.url,
                'is_main': False
            })
        
        return JsonResponse({
            'success': True,
            'images': image_urls,
            'count': len(image_urls)
        })
    
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)


def get_product_variants(request, product_id):
    """
    AJAX endpoint для получения цветовых вариантов товара.
    
    Args:
        product_id (int): ID товара
        
    Returns:
        JsonResponse: Список вариантов с изображениями
    """
    try:
        product = Product.objects.get(id=product_id)
        color_variants = get_detailed_color_variants(product)
        
        return JsonResponse({
            'success': True,
            'variants': color_variants,
            'count': len(color_variants)
        })
    
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)


def quick_view(request, product_id):
    """
    Quick view модал для товара (AJAX).
    
    Args:
        product_id (int): ID товара
        
    Returns:
        JsonResponse или rendered HTML fragment
    """
    try:
        product = Product.objects.select_related('category').get(id=product_id)
        color_variants = get_detailed_color_variants(product)
        
        from django.template.loader import render_to_string
        
        html = render_to_string('partials/product_quick_view.html', {
            'product': product,
            'color_variants': color_variants
        })
        
        return JsonResponse({
            'success': True,
            'html': html
        })
    
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)
















