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
from ..recommendations import ProductRecommendationEngine
from .utils import cache_page_for_anon


# ==================== PRODUCT VIEWS ====================

# ВАЖНО: Не кэшируем страницу товара, так как нужен предвыбор размера/цвета из URL параметров
# @cache_page_for_anon(600)  # Отключено для поддержки ?size=M и ?color=X
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
    - Поддержка URL параметра ?size=X для предвыбора размера
    - Генерация offer_ids для синхронизации с пикселями
    
    Context:
        product: Объект товара
        images: Дополнительные изображения товара
        color_variants: Список цветовых вариантов с изображениями
        auto_select_first_color: Флаг автовыбора первого цвета
        breadcrumbs: Хлебные крошки для SEO
        preselected_size: Предвыбранный размер из URL параметра
        offer_id_map: JSON mapping (color_variant_id, size) -> offer_id для JS
        default_offer_id: Offer ID для текущего выбора (default цвет + размер)
    """
    product = get_object_or_404(Product.objects.select_related('category').prefetch_related('images'), slug=slug, status='published')
    images = product.images.all()
    
    # Читаем параметры из URL (?size=M&color=123)
    preselected_size = request.GET.get('size', '').upper()
    preselected_color_id = request.GET.get('color', '')  # ID цветового варианта
    
    available_sizes = ['S', 'M', 'L', 'XL', 'XXL']
    
    # Валидируем размер
    if preselected_size not in available_sizes:
        preselected_size = None  # Будет выбран default размер в JS
    
    # Варианты цветов с изображениями (если есть приложение и данные)
    color_variants = get_detailed_color_variants(product)
    auto_select_first_color = False
    preselected_color = None  # Будем хранить выбранный цвет для шаблона

    if color_variants:
        # Валидируем и ищем предвыбранный цвет
        if preselected_color_id:
            try:
                preselected_color_id_int = int(preselected_color_id)
                # Ищем вариант с таким ID
                preselected_index = next(
                    (idx for idx, variant in enumerate(color_variants) 
                     if variant.get('id') == preselected_color_id_int),
                    None
                )
                if preselected_index is not None:
                    preselected_color = preselected_color_id_int
                    # Перемещаем предвыбранный вариант на первое место
                    if preselected_index != 0:
                        preselected_variant = color_variants.pop(preselected_index)
                        color_variants.insert(0, preselected_variant)
            except (ValueError, TypeError):
                pass  # Невалидный ID цвета
        
        # Если цвет не был предвыбран, находим default вариант
        if preselected_color is None:
            default_index = next(
                (idx for idx, variant in enumerate(color_variants) 
                 if variant.get('is_default')),
                0
        )
        
            if default_index != 0:
                default_variant = color_variants.pop(default_index)
                color_variants.insert(0, default_variant)
        
        # Устанавливаем первый вариант как default (теперь это либо предвыбранный, либо default)
        for idx, variant in enumerate(color_variants):
            variant['is_default'] = (idx == 0)
        
        # Если нет главного изображения, автоматически выбираем первый цвет
        if not product.main_image:
            auto_select_first_color = True
    
    # Генерируем offer_id mapping для всех комбинаций (цвет × размер)
    # Формат: { "variant_id:size": "offer_id" } или { "default:size": "offer_id" }
    import json
    offer_id_map = {}
    default_offer_id = None
    
    if color_variants:
        # Есть цветовые варианты
        for variant in color_variants:
            variant_id = variant.get('id')
            for size in available_sizes:
                offer_id = product.get_offer_id(variant_id, size)
                key = f"{variant_id}:{size}"
                offer_id_map[key] = offer_id
                
                # Определяем default offer_id (первый вариант + первый/предвыбранный размер)
                if variant.get('is_default') and default_offer_id is None:
                    if preselected_size and size == preselected_size:
                        default_offer_id = offer_id
                    elif not preselected_size and size == available_sizes[0]:
                        default_offer_id = offer_id
    else:
        # Нет цветовых вариантов - используем default
        for size in available_sizes:
            offer_id = product.get_offer_id(None, size)
            key = f"default:{size}"
            offer_id_map[key] = offer_id
            
            # Определяем default offer_id
            if default_offer_id is None:
                if preselected_size and size == preselected_size:
                    default_offer_id = offer_id
                elif not preselected_size and size == available_sizes[0]:
                    default_offer_id = offer_id
    
    # Если default_offer_id не установлен, берем самый первый
    if not default_offer_id and offer_id_map:
        default_offer_id = list(offer_id_map.values())[0]
    
    offer_id_map_json = json.dumps(offer_id_map)
    
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
    
    # Получаем рекомендации товаров
    recommendation_engine = ProductRecommendationEngine(user=request.user if hasattr(request, 'user') else None)
    recommended_products = recommendation_engine.get_recommendations(product=product, limit=8)
    
    # Обрабатываем цветовые превью для рекомендаций
    if recommended_products:
        from ..services.catalog_helpers import build_color_preview_map
        preview_map = build_color_preview_map(list(recommended_products))
        for rec_product in recommended_products:
            rec_product.colors_preview = preview_map.get(rec_product.id, [])
    
    return render(
        request,
        'pages/product_detail.html',
        {
            'product': product,
            'images': images,
            'color_variants': color_variants,
            'auto_select_first_color': auto_select_first_color,
            'breadcrumbs': breadcrumbs,
            'recommended_products': recommended_products,
            'preselected_size': preselected_size,
            'preselected_color': preselected_color,  # ID предвыбранного цвета из ?color=123
            'offer_id_map': offer_id_map_json,
            'default_offer_id': default_offer_id,
            'available_sizes': available_sizes,
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
        product = Product.objects.get(id=product_id, status='published')
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
        product = Product.objects.get(id=product_id, status='published')
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
        product = Product.objects.select_related('category').get(id=product_id, status='published')
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
















