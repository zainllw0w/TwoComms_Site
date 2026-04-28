"""
Product views - Детальная информация о товарах.

Содержит views для:
- Детальной страницы товара
- Получения изображений
- Цветовых вариантов
- Отзывов (в будущем)
"""

import re

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse

from ..models import Product
from ..services.catalog_helpers import get_detailed_color_variants, get_public_product_order_version
from ..services.image_variants import build_optimized_image_payload
from ..services.size_guides import resolve_product_size_context
from ..recommendations import ProductRecommendationEngine
from ..utm_tracking import record_product_view


# ==================== PRODUCT VIEWS ====================

def _is_tshirt_product(product):
    candidates = [
        getattr(product, 'title', ''),
        getattr(getattr(product, 'category', None), 'name', ''),
        getattr(getattr(product, 'category', None), 'slug', ''),
        getattr(getattr(product, 'catalog', None), 'name', ''),
        getattr(getattr(product, 'catalog', None), 'slug', ''),
    ]
    normalized = ' '.join(str(item or '').lower() for item in candidates)
    tshirt_pattern = re.compile(r'(^|[^a-z0-9а-яіїєґ])(?:футбол\w*|t-?shirts?|tees?)(?=$|[^a-z0-9а-яіїєґ])')
    return bool(tshirt_pattern.search(normalized))


def _resolve_fit_options(product):
    if not _is_tshirt_product(product):
        return []

    options = list(product.fit_options.filter(is_active=True).order_by('order', 'id'))
    if not options:
        return []

    has_default = any(option.is_default for option in options)
    if not has_default:
        options[0].is_default = True
    return options


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
    product = get_object_or_404(
        Product.objects.select_related('category', 'catalog', 'size_grid', 'size_grid__catalog').prefetch_related(
            'images',
            'catalog__size_grids',
            'catalog__options__values',
            'fit_options',
        ),
        slug=slug,
        status='published',
    )
    record_product_view(request, product.id, product.title)
    images = product.images.all()

    # Читаем параметры из URL (?size=M&color=123)
    preselected_size = request.GET.get('size', '').upper()
    preselected_color_id = request.GET.get('color', '')  # ID цветового варианта

    size_context = resolve_product_size_context(product, preselected_size)
    available_sizes = size_context["sizes"]
    preselected_size = size_context["selected_size"]

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
    extra_image_urls = [
        build_optimized_image_payload(image.image)
        for image in images
        if getattr(image, 'image', None)
    ]

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
    recommended_products = list(recommendation_engine.get_recommendations(product=product, limit=8))
    recommended_product_ids = ':'.join(str(rec_product.id) for rec_product in recommended_products)

    # Обрабатываем цветовые превью для рекомендаций
    if recommended_products:
        from ..services.catalog_helpers import build_color_preview_map
        preview_map = build_color_preview_map(list(recommended_products))
        for rec_product in recommended_products:
            rec_product.colors_preview = preview_map.get(rec_product.id, [])

    public_product_order_version = get_public_product_order_version()
    fit_options = _resolve_fit_options(product)
    requested_fit_code = str(request.GET.get('fit', '') or '').strip().lower()
    if fit_options:
        selected_fit = next((option for option in fit_options if option.code == requested_fit_code), None)
        if selected_fit is None:
            selected_fit = next((option for option in fit_options if option.is_default), fit_options[0])
        preselected_fit_code = selected_fit.code
        for option in fit_options:
            option.is_default = option.code == preselected_fit_code
    else:
        preselected_fit_code = ''

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
            'recommended_product_ids': recommended_product_ids,
            'preselected_size': preselected_size,
            'preselected_color': preselected_color,  # ID предвыбранного цвета из ?color=123
            'offer_id_map': offer_id_map_json,
            'default_offer_id': default_offer_id,
            'offer_id_map_data': offer_id_map,
            'extra_image_urls': extra_image_urls,
            'available_sizes': available_sizes,
            'size_display_labels': size_context["display_labels"],
            'resolved_size_guide': size_context["guide"],
            'resolved_size_profile': size_context["profile"],
            'public_product_order_version': public_product_order_version,
            'fit_options': fit_options,
            'show_fit_selector': bool(fit_options),
            'preselected_fit_code': preselected_fit_code,
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
        product = Product.objects.prefetch_related('images').get(id=product_id, status='published')
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
