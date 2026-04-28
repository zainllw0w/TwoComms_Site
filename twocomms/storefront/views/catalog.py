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
from django.db.models import Count, Q
from django.views.decorators.csrf import ensure_csrf_cookie
from django.template.loader import render_to_string
from django.urls import reverse

from ..models import Product, Category, SurveySession
from ..pagination import build_homepage_pagination_items
from ..services.catalog_helpers import (
    apply_public_product_order,
    build_color_preview_key,
    build_color_preview_map,
    get_categories_cached,
    get_public_category_version,
    get_public_product_order_version,
)
from ..services.survey_engine import load_survey_definition
from ..utm_tracking import record_search
from cache_utils import get_fragment_cache
from .utils import (
    cache_page_for_anon,
    HOME_PRODUCTS_PER_PAGE,
    PRODUCTS_PER_PAGE,
    public_product_listing_cache_prefix,
)


# ==================== CATALOG VIEWS ====================

CATALOG_SHOWCASE_CARD_CONFIG = (
    {
        'key': 'longsleeves',
        'number': '01',
        'title': 'Лонгсліви',
        'subtitle': 'Функціональність. Стиль. Характер.',
        'image': 'img/catalog/catalog-longsleeves.webp',
        'slugs': ('longslivy', 'longsleeves', 'longsleeve', 'longslivi'),
        'tokens': ('лонг', 'long'),
        'swatches': ('#050505', '#6a6b60', '#e7e1d3', '#8c8f79'),
    },
    {
        'key': 'tshirts',
        'number': '02',
        'title': 'Футболки',
        'subtitle': 'Графіка, що говорить гучніше за слова.',
        'image': 'img/catalog/catalog-tshirts.webp',
        'slugs': ('futbolki', 'futbolky', 'tshirts', 't-shirts', 'tshirt', 'tees'),
        'tokens': ('футбол', 'tshirt', 'shirt', 'tee'),
        'swatches': ('#050505', '#3a3d3f', '#62684a', '#ede8dc'),
    },
    {
        'key': 'hoodies',
        'number': '03',
        'title': 'Худі',
        'subtitle': 'Тепло. Захист. Нічого зайвого.',
        'image': 'img/catalog/catalog-hoodies.webp',
        'slugs': ('hudi', 'hoodie', 'hoodies', 'khudi'),
        'tokens': ('худі', 'hood'),
        'swatches': ('#050505', '#303436', '#6a6f48', '#efe9dc'),
    },
)


def _match_showcase_category(categories, config):
    slugs = {slug.lower() for slug in config['slugs']}
    tokens = tuple(token.lower() for token in config['tokens'])

    for category in categories:
        slug = (getattr(category, 'slug', '') or '').lower()
        name = (getattr(category, 'name', '') or '').lower()
        if slug in slugs or any(token in slug or token in name for token in tokens):
            return category

    return None


def _build_catalog_showcase_cards(categories):
    matched_categories = {}
    for config in CATALOG_SHOWCASE_CARD_CONFIG:
        category = _match_showcase_category(categories, config)
        if category and getattr(category, 'id', None):
            matched_categories[config['key']] = category

    category_ids = [category.id for category in matched_categories.values()]
    product_counts = {}
    if category_ids:
        product_counts = {
            item['category_id']: item['total']
            for item in Product.objects.filter(
                category_id__in=category_ids,
                status='published',
            ).values('category_id').annotate(total=Count('id'))
        }

    cards = []
    for config in CATALOG_SHOWCASE_CARD_CONFIG:
        category = matched_categories.get(config['key'])
        cards.append({
            **config,
            'category': category,
            'product_count': product_counts.get(category.id, 0) if category else None,
        })
    return cards

def _product_cards_queryset():
    return Product.objects.select_related('category').prefetch_related('images', 'color_variants__images').defer(
        'description', 'full_description', 'short_description', 'ai_description', 'ai_keywords',
        'seo_title', 'seo_description', 'seo_keywords', 'seo_schema', 'recommendation_tags',
        'dropship_note', 'unpublished_reason'
    )


@ensure_csrf_cookie
@cache_page_for_anon(
    300,
    key_prefix=public_product_listing_cache_prefix,
)  # Phase 4.1: 5-мин кэш для анонимов; cart/favs-бейджи идут AJAX, не в кэше
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
    featured = apply_public_product_order(
        _product_cards_queryset().filter(
            featured=True,
            status='published'
        )
    ).first()

    fragment_cache = get_fragment_cache()
    categories = get_categories_cached(fragment_cache)
    public_product_order_version = get_public_product_order_version(fragment_cache)
    public_category_version = get_public_category_version(fragment_cache)

    # Пагинация
    page_number = request.GET.get('page', '1')
    product_qs = apply_public_product_order(
        _product_cards_queryset().filter(status='published')
    )
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
        colors_preview = color_previews.get(product.id, [])
        setattr(product, 'colors_preview', colors_preview)
        setattr(product, 'colors_preview_key', build_color_preview_key(colors_preview))

    # Проверяем есть ли еще товары для пагинации
    total_products = paginator.count
    has_more = page_obj.has_next()
    homepage_pagination_items = build_homepage_pagination_items(
        current_page=page_obj.number,
        total_pages=paginator.num_pages,
        base_path=reverse("home"),
    )

    survey_def = load_survey_definition()
    survey_ui_home = survey_def.get('ui_copy', {}).get('homepage_block', {}) if survey_def else {}
    survey_ui_modal = survey_def.get('ui_copy', {}).get('modal', {}) if survey_def else {}
    survey_reward = survey_def.get('reward', {}) if survey_def else {}
    survey_key = survey_def.get('survey_key', 'print_feedback_v1') if survey_def else 'print_feedback_v1'
    survey_has_active = False
    if request.user.is_authenticated and survey_def:
        survey_has_active = SurveySession.objects.filter(
            user=request.user,
            survey_key=survey_key,
            status='in_progress',
        ).exists()
    survey_cta_text = survey_ui_home.get(
        'cta_continue_uk' if survey_has_active else 'cta_start_uk',
        'Пройти опитування',
    )

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
            'homepage_pagination_items': homepage_pagination_items,
            'total_products': total_products,
            'survey_ui_home': survey_ui_home,
            'survey_ui_modal': survey_ui_modal,
            'survey_reward': survey_reward,
            'survey_key': survey_key,
            'survey_cta_text': survey_cta_text,
            'survey_has_active': survey_has_active,
            'public_product_order_version': public_product_order_version,
            'public_category_version': public_category_version,
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
        page = request.GET.get('page', 1)
        per_page = HOME_PRODUCTS_PER_PAGE

        product_qs = apply_public_product_order(
            _product_cards_queryset().filter(status='published')
        )
        paginator = Paginator(product_qs, per_page)

        page_obj = paginator.get_page(page)

        products = list(page_obj.object_list)

        # Подготавливаем цвета для товаров
        color_previews = build_color_preview_map(products)
        for product in products:
            product.colors_preview = color_previews.get(product.id, [])
            product.colors_preview_key = build_color_preview_key(product.colors_preview)

        # Проверяем есть ли еще товары
        total_products = paginator.count
        has_more = page_obj.has_next()
        homepage_pagination_items = build_homepage_pagination_items(
            current_page=page_obj.number,
            total_pages=paginator.num_pages,
            base_path=reverse("home"),
        )

        # Рендерим HTML для товаров
        products_html = render_to_string('partials/products_list.html', {
            'products': products,
            'page': page_obj.number
        })
        pagination_html = render_to_string(
            'partials/home_pagination.html',
            {
                'homepage_pagination_items': homepage_pagination_items,
                'page_obj': page_obj,
                'paginator': paginator,
                'homepage_pagination_base_path': reverse("home"),
            },
            request=request,
        )

        return JsonResponse({
            'html': products_html,
            'has_more': has_more,
            'next_page': page_obj.next_page_number() if has_more else None,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'pagination_html': pagination_html,
            'total_products': total_products,
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)


@ensure_csrf_cookie
@cache_page_for_anon(600, key_prefix=public_product_listing_cache_prefix)  # Кэшируем каталог на 10 минут только для анонимов
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
    public_product_order_version = get_public_product_order_version(fragment_cache)
    public_category_version = get_public_category_version(fragment_cache)

    if cat_slug:
        category = get_object_or_404(Category, slug=cat_slug, is_active=True)
        product_qs = apply_public_product_order(
            _product_cards_queryset().filter(
                category=category,
                status='published',
            )
        )
        show_category_cards = False
    else:
        category = None
        product_qs = apply_public_product_order(
            _product_cards_queryset().filter(status='published')
        )
        show_category_cards = True

    # Pagination
    paginator = Paginator(product_qs, PRODUCTS_PER_PAGE)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page_number)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    products = list(page_obj.object_list)
    color_previews = build_color_preview_map(products)

    for product in products:
        colors_preview = color_previews.get(product.id, [])
        product.colors_preview = colors_preview
        product.colors_preview_key = build_color_preview_key(colors_preview)

    return render(
        request,
        'pages/catalog.html',
        {
            'categories': categories,
            'category': category,
            'products': products,
            'show_category_cards': show_category_cards,
            'catalog_showcase_cards': _build_catalog_showcase_cards(categories) if show_category_cards else [],
            'cat_slug': cat_slug or '',
            'page_obj': page_obj,
            'paginator': paginator,
            'public_product_order_version': public_product_order_version,
            'public_category_version': public_category_version,
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
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Search function called from catalog.py")

    try:
        query = (request.GET.get('q') or '').strip()
        category_slug = request.GET.get('category', '').strip()

        # Используем тот же подход, что и в рабочей версии из views.py
        product_qs = _product_cards_queryset().filter(status='published')

        if query:
            product_qs = product_qs.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(full_description__icontains=query)
                | Q(short_description__icontains=query)
            )
            record_search(request, query)

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
        public_product_order_version = get_public_product_order_version(fragment_cache)
        public_category_version = get_public_category_version(fragment_cache)

        product_list = list(apply_public_product_order(product_qs))
        color_previews = build_color_preview_map(product_list)

        for product in product_list:
            colors_preview = color_previews.get(product.id, [])
            product.colors_preview = colors_preview
            product.colors_preview_key = build_color_preview_key(colors_preview)

        return render(
            request,
            'pages/catalog.html',
            {
                'categories': categories,
                'products': product_list,
                'show_category_cards': False,
                'selected_category': selected_category,
                'query': query,
                'results_count': len(product_list),
                'is_search_page': True,
                'public_product_order_version': public_product_order_version,
                'public_category_version': public_category_version,
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
            public_product_order_version = get_public_product_order_version(fragment_cache)
            public_category_version = get_public_category_version(fragment_cache)
        except Exception:
            categories = []
            public_product_order_version = 1
            public_category_version = 1

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
                'is_search_page': True,
                'error': 'Произошла ошибка при поиске. Попробуйте еще раз.',
                'public_product_order_version': public_product_order_version,
                'public_category_version': public_category_version,
            }
        )
