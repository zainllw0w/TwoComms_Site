"""
Catalog views - Каталог товаров и категорий.

Содержит views для:
- Главной страницы (home)
- Каталога товаров (catalog)
- Поиска
- Фильтрации
- AJAX подгрузки товаров
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage
from django.urls import reverse
from django.template.loader import render_to_string
from django.db.models import Q

from ..models import Product, Category
from ..services.catalog_helpers import (
    build_color_preview_map,
    get_categories_cached,
)
from cache_utils import get_fragment_cache
from .utils import cache_page_for_anon, HOME_PRODUCTS_PER_PAGE


# ==================== CATALOG VIEWS ====================

def home(request):
    """
    Главная страница сайта.
    
    Features:
    - Показывает featured товар
    - Список последних товаров с пагинацией
    - Категории товаров
    - Предпросмотр цветовых вариантов
    """
    # Оптимизированные запросы с select_related и prefetch_related
    featured = Product.objects.select_related('category').filter(
        featured=True
    ).order_by('-id').first()
    
    fragment_cache = get_fragment_cache()
    categories = get_categories_cached(fragment_cache)
    
    # Пагинация
    page_number = request.GET.get('page', '1')
    product_qs = Product.objects.select_related('category').order_by('-id')
    paginator = Paginator(product_qs, HOME_PRODUCTS_PER_PAGE)

    try:
        page_obj = paginator.get_page(page_number)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    products = list(page_obj.object_list)
    
    # Подготавливаем цветовые превью
    preview_products = list(products)
    if featured:
        preview_products.append(featured)
    
    color_previews = build_color_preview_map(preview_products)
    featured_variants = color_previews.get(featured.id, []) if featured else []
    
    for product in products:
        setattr(product, 'colors_preview', color_previews.get(product.id, []))
    
    # Проверяем есть ли еще товары для пагинации
    total_products = paginator.count
    has_more = page_obj.has_next()

    return render(
        request,
        'pages/index.html',
        {
            'featured': featured,
            'categories': categories,
            'products': products,
            'featured_variants': featured_variants,
            'has_more_products': has_more,
            'current_page': page_obj.number,
            'paginator': paginator,
            'page_obj': page_obj,
            'total_products': total_products
        }
    )


def load_more_products(request):
    """
    AJAX view для загрузки дополнительных товаров.
    
    Используется для бесконечной прокрутки на главной странице.
    
    Returns:
        JsonResponse: HTML фрагмент с товарами + метаданные пагинации
    """
    if request.method == 'GET':
        page = int(request.GET.get('page', 1))
        per_page = HOME_PRODUCTS_PER_PAGE

        product_qs = Product.objects.select_related('category').order_by('-id')
        paginator = Paginator(product_qs, per_page)

        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        products = list(page_obj.object_list)

        # Подготавливаем цвета для товаров
        color_previews = build_color_preview_map(products)
        for product in products:
            product.colors_preview = color_previews.get(product.id, [])
        
        # Проверяем есть ли еще товары
        total_products = paginator.count
        has_more = page_obj.has_next()

        # Рендерим HTML для товаров
        products_html = render_to_string('partials/products_list.html', {
            'products': products,
            'page': page
        })

        return JsonResponse({
            'html': products_html,
            'has_more': has_more,
            'next_page': page_obj.next_page_number() if has_more else None,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@cache_page_for_anon(600)  # Кэшируем каталог на 10 минут только для анонимов
def catalog(request, cat_slug=None):
    """
    Страница каталога товаров.
    
    Args:
        cat_slug (str, optional): Slug категории для фильтрации
        
    Features:
    - Показывает все товары или фильтрует по категории
    - Цветовые варианты товаров
    - Карточки категорий (если не выбрана конкретная категория)
    """
    fragment_cache = get_fragment_cache()
    categories = get_categories_cached(fragment_cache)
    
    if cat_slug:
        category = get_object_or_404(Category, slug=cat_slug)
        product_qs = Product.objects.select_related('category').filter(
            category=category
        ).order_by('-id')
        show_category_cards = False
    else:
        category = None
        product_qs = Product.objects.select_related('category').order_by('-id')
        show_category_cards = True
    
    products = list(product_qs)
    color_previews = build_color_preview_map(products)
    
    for product in products:
        product.colors_preview = color_previews.get(product.id, [])
    
    return render(
        request,
        'pages/catalog.html',
        {
            'categories': categories,
            'category': category,
            'products': products,
            'show_category_cards': show_category_cards,
            'cat_slug': cat_slug or ''
        }
    )


def search(request):
    """
    Поиск товаров.
    
    Query params:
        q (str): Поисковый запрос
        category (str, optional): Фильтр по категории
        
    Features:
    - Поиск по названию и описанию
    - Фильтрация по категории
    - Выделение результатов
    """
    try:
        query = (request.GET.get('q') or '').strip()
        category_slug = request.GET.get('category', '').strip()
        
        # Используем тот же подход, что и в рабочей версии из views.py
        product_qs = Product.objects.select_related('category').prefetch_related('images', 'color_variants__images')
        
        if query:
            # Поиск по названию (базовый поиск, как в рабочей версии из views.py)
            # Сначала пробуем простой поиск по title, как в рабочей версии
            product_qs = product_qs.filter(title__icontains=query)
        
        # Фильтрация по категории
        selected_category = None
        if category_slug:
            try:
                selected_category = Category.objects.get(slug=category_slug, is_active=True)
                product_qs = product_qs.filter(category=selected_category)
            except Category.DoesNotExist:
                selected_category = None
        
        fragment_cache = get_fragment_cache()
        categories = get_categories_cached(fragment_cache)
        
        product_list = list(product_qs.order_by('-id'))
        color_previews = build_color_preview_map(product_list)
        
        for product in product_list:
            product.colors_preview = color_previews.get(product.id, [])
        
        return render(
            request,
            'pages/catalog.html',
            {
                'categories': categories,
                'products': product_list,
                'show_category_cards': False,
                'selected_category': selected_category,
                'query': query,
                'results_count': len(product_list)
            }
        )
    except Exception as e:
        # Логируем ошибку для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in search view: {e}", exc_info=True)
        
        # Возвращаем пустую страницу с ошибкой
        try:
            fragment_cache = get_fragment_cache()
            categories = get_categories_cached(fragment_cache) if fragment_cache else []
        except Exception:
            categories = []
        
        return render(
            request,
            'pages/catalog.html',
            {
                'query': request.GET.get('q', ''),
                'products': [],
                'categories': categories,
                'selected_category': None,
                'show_category_cards': False,
                'results_count': 0,
                'error': 'Произошла ошибка при поиске. Попробуйте еще раз.'
            }
        )















