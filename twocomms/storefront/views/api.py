"""
API views - AJAX и JSON endpoints.

Содержит views для:
- AJAX запросов от фронтенда
- JSON API endpoints
- Реал-тайм данные
- Аналитика и трекинг
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from ..models import Product, Category
from ..services.catalog_helpers import get_categories_cached
from cache_utils import get_fragment_cache


# ==================== API ENDPOINTS ====================


def _public_product_queryset(request):
    """
    Возвращает queryset товаров c учетом статуса публикации.
    """
    qs = Product.objects.select_related('category')
    if not (request.user.is_authenticated and request.user.is_staff):
        qs = qs.filter(status='published')
    return qs

@require_http_methods(["GET"])
def get_product_json(request, product_id):
    """
    Получить данные товара в формате JSON.
    
    Args:
        product_id (int): ID товара
        
    Returns:
        JsonResponse: Полные данные товара
    """
    try:
        product = _public_product_queryset(request).get(id=product_id)
        
        data = {
            'id': product.id,
            'title': product.title,
            'slug': product.slug,
            'price': product.price,
            'final_price': product.final_price,
            'has_discount': product.has_discount,
            'discount_percent': product.discount_percent,
            'description': product.description,
            'category': {
                'id': product.category.id if product.category else None,
                'name': product.category.name if product.category else None,
                'slug': product.category.slug if product.category else None
            },
            'main_image': product.main_image.url if product.main_image else None,
            'featured': product.featured
        }
        
        return JsonResponse({
            'success': True,
            'product': data
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)


@require_http_methods(["GET"])
def get_categories_json(request):
    """
    Получить список всех категорий в формате JSON.
    
    Returns:
        JsonResponse: Список категорий
    """
    fragment_cache = get_fragment_cache()
    categories = get_categories_cached(fragment_cache)
    
    categories_data = [
        {
            'id': cat.id,
            'name': cat.name,
            'slug': cat.slug,
            'order': cat.order,
            'icon': cat.icon.url if cat.icon else None,
            'cover': cat.cover.url if cat.cover else None,
            'is_active': cat.is_active,
            'is_featured': cat.is_featured
        }
        for cat in categories
    ]
    
    return JsonResponse({
        'success': True,
        'categories': categories_data,
        'count': len(categories_data)
    })


@require_http_methods(["POST"])
@csrf_exempt  # Для внешних интеграций
def track_event(request):
    """
    Трекинг событий для аналитики.
    
    POST params:
        event_type: Тип события (view, click, add_to_cart, etc.)
        product_id: ID товара (опционально)
        category_id: ID категории (опционально)
        metadata: Дополнительные данные (JSON)
        
    Returns:
        JsonResponse: success
    """
    import json
    
    try:
        data = json.loads(request.body)
        event_type = data.get('event_type')
        product_id = data.get('product_id')
        category_id = data.get('category_id')
        metadata = data.get('metadata', {})
        
        # TODO: Сохранить событие в БД или отправить в аналитику
        # Например: Google Analytics, Mixpanel, etc.
        
        # Пока просто логируем
        import logging
        logger = logging.getLogger('storefront.analytics')
        logger.info(f"Event: {event_type}, Product: {product_id}, Category: {category_id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Event tracked'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["GET"])
def search_suggestions(request):
    """
    Автодополнение для поиска (AJAX).
    
    Query params:
        q: Поисковый запрос
        limit: Количество результатов (по умолчанию 5)
        
    Returns:
        JsonResponse: Список предложений
    """
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 5))
    
    if not query or len(query) < 2:
        return JsonResponse({
            'success': True,
            'suggestions': []
        })
    
    # Ищем по началу названия (быстрее чем contains)
    products = _public_product_queryset(request).filter(
        title__istartswith=query
    ).values('id', 'title', 'slug')[:limit]
    
    suggestions = [
        {
            'id': p['id'],
            'title': p['title'],
            'slug': p['slug']
        }
        for p in products
    ]
    
    return JsonResponse({
        'success': True,
        'suggestions': suggestions,
        'count': len(suggestions)
    })


@require_http_methods(["GET"])
def product_availability(request, product_id):
    """
    Проверка доступности товара.
    
    Args:
        product_id (int): ID товара
        
    Returns:
        JsonResponse: available, in_stock
    """
    try:
        qs = _public_product_queryset(request)
        product = qs.get(id=product_id)
        
        # TODO: Добавить реальную проверку наличия на складе
        # Пока просто возвращаем True
        
        return JsonResponse({
            'success': True,
            'available': True,
            'in_stock': True,
            'message': 'Товар доступний'
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)


@require_http_methods(["GET"])
def get_related_products(request, product_id):
    """
    Получить похожие товары.
    
    Args:
        product_id (int): ID товара
        
    Returns:
        JsonResponse: Список похожих товаров
    """
    try:
        qs = _public_product_queryset(request)
        product = qs.get(id=product_id)
        
        # Ищем товары из той же категории
        related = qs.filter(
            category=product.category
        ).exclude(
            id=product_id
        ).select_related('category')[:6]
        
        related_data = [
            {
                'id': p.id,
                'title': p.title,
                'slug': p.slug,
                'price': p.price,
                'final_price': p.final_price,
                'main_image': p.main_image.url if p.main_image else None
            }
            for p in related
        ]
        
        return JsonResponse({
            'success': True,
            'products': related_data,
            'count': len(related_data)
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)


@require_http_methods(["POST"])
def newsletter_subscribe(request):
    """
    Подписка на рассылку.
    
    POST params:
        email: Email адрес
        
    Returns:
        JsonResponse: success, message
    """
    import json
    
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        
        if not email:
            return JsonResponse({
                'success': False,
                'error': 'Email обов\'язковий'
            }, status=400)
        
        # TODO: Сохранить email в БД или отправить в сервис рассылок
        # Например: MailChimp, SendGrid, etc.
        
        return JsonResponse({
            'success': True,
            'message': 'Дякуємо за підписку!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["POST"])
def contact_form(request):
    """
    Форма обратной связи.
    
    POST params:
        name: Имя
        email: Email
        phone: Телефон
        message: Сообщение
        
    Returns:
        JsonResponse: success, message
    """
    import json
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        message = data.get('message', '').strip()
        
        if not all([name, email, message]):
            return JsonResponse({
                'success': False,
                'error': 'Всі поля обов\'язкові'
            }, status=400)
        
        # TODO: Отправить email администратору или сохранить в БД
        
        return JsonResponse({
            'success': True,
            'message': 'Ваше повідомлення надіслано!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)














