"""
Оптимизированные контекстные процессоры для storefront приложения
"""

from django.core.cache import cache
from django.conf import settings

def orders_processing_count(request):
    """
    Оптимизированный контекстный процессор для добавления счетчика заказов в обработке
    """
    if request.user.is_authenticated and request.user.is_staff:
        try:
            from orders.models import Order
            processing_count = Order.objects.get_processing_count_cached()
        except Exception:
            processing_count = 0
    else:
        processing_count = 0
    
    return {
        'orders_processing_count': processing_count
    }

def site_settings(request):
    """
    Контекстный процессор для общих настроек сайта
    """
    cache_key = 'site_settings'
    settings_data = cache.get(cache_key)
    
    if settings_data is None:
        settings_data = {
            'site_name': getattr(settings, 'SITE_NAME', 'TwoComms'),
            'site_description': getattr(settings, 'SITE_DESCRIPTION', 'Магазин стріт & мілітарі одягу'),
            'contact_phone': getattr(settings, 'CONTACT_PHONE', ''),
            'contact_email': getattr(settings, 'CONTACT_EMAIL', ''),
            'social_telegram': getattr(settings, 'SOCIAL_TELEGRAM', ''),
            'social_instagram': getattr(settings, 'SOCIAL_INSTAGRAM', ''),
        }
        cache.set(cache_key, settings_data, 3600)  # Кэшируем на час
    
    return {
        'site_settings': settings_data
    }

def user_stats(request):
    """
    Контекстный процессор для статистики пользователя
    """
    if not request.user.is_authenticated:
        return {}
    
    cache_key = f'user_stats_{request.user.id}'
    user_stats_data = cache.get(cache_key)
    
    if user_stats_data is None:
        try:
            from accounts.models import UserPoints, FavoriteProduct
            from orders.models import Order
            
            # Получаем баллы пользователя
            try:
                points = UserPoints.objects.get(user=request.user)
                user_points = points.points
                total_earned = points.total_earned
                total_spent = points.total_spent
            except UserPoints.DoesNotExist:
                user_points = 0
                total_earned = 0
                total_spent = 0
            
            # Получаем количество избранных товаров
            favorites_count = FavoriteProduct.objects.filter(user=request.user).count()
            
            # Получаем количество заказов
            orders_count = Order.objects.filter(user=request.user).count()
            
            user_stats_data = {
                'user_points': user_points,
                'total_earned': total_earned,
                'total_spent': total_spent,
                'favorites_count': favorites_count,
                'orders_count': orders_count,
            }
            
            cache.set(cache_key, user_stats_data, 300)  # Кэшируем на 5 минут
            
        except Exception:
            user_stats_data = {
                'user_points': 0,
                'total_earned': 0,
                'total_spent': 0,
                'favorites_count': 0,
                'orders_count': 0,
            }
    
    return {
        'user_stats': user_stats_data
    }

def categories_menu(request):
    """
    Контекстный процессор для меню категорий
    """
    cache_key = 'categories_menu'
    categories = cache.get(cache_key)
    
    if categories is None:
        try:
            from .models import Category
            categories = list(Category.objects.filter(is_active=True).order_by('order', 'name'))
            cache.set(cache_key, categories, 1800)  # Кэшируем на 30 минут
        except Exception:
            categories = []
    
    return {
        'categories_menu': categories
    }

def featured_products(request):
    """
    Контекстный процессор для рекомендуемых товаров
    """
    cache_key = 'featured_products_context'
    featured = cache.get(cache_key)
    
    if featured is None:
        try:
            from .models import Product
            featured = Product.objects.select_related('category').filter(featured=True).order_by('-id').first()
            cache.set(cache_key, featured, 1800)  # Кэшируем на 30 минут
        except Exception:
            featured = None
    
    return {
        'featured_product': featured
    }

def cart_info(request):
    """
    Контекстный процессор для информации о корзине
    """
    if not request.user.is_authenticated:
        return {'cart_items_count': 0, 'cart_total': 0}
    
    cache_key = f'cart_info_{request.user.id}'
    cart_data = cache.get(cache_key)
    
    if cart_data is None:
        try:
            # Здесь можно добавить логику для работы с корзиной
            # Пока возвращаем пустые значения
            cart_data = {
                'cart_items_count': 0,
                'cart_total': 0,
            }
            cache.set(cache_key, cart_data, 300)  # Кэшируем на 5 минут
        except Exception:
            cart_data = {
                'cart_items_count': 0,
                'cart_total': 0,
            }
    
    return cart_data

def notifications(request):
    """
    Контекстный процессор для уведомлений
    """
    if not request.user.is_authenticated:
        return {'notifications': []}
    
    cache_key = f'notifications_{request.user.id}'
    notifications_data = cache.get(cache_key)
    
    if notifications_data is None:
        try:
            # Здесь можно добавить логику для получения уведомлений
            # Пока возвращаем пустой список
            notifications_data = []
            cache.set(cache_key, notifications_data, 300)  # Кэшируем на 5 минут
        except Exception:
            notifications_data = []
    
    return {
        'notifications': notifications_data
    }

def performance_info(request):
    """
    Контекстный процессор для информации о производительности (только для staff)
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}
    
    cache_key = 'performance_info'
    perf_info = cache.get(cache_key)
    
    if perf_info is None:
        try:
            from .models import Product, Category
            from orders.models import Order
            from accounts.models import User
            
            perf_info = {
                'total_products': Product.objects.count(),
                'total_categories': Category.objects.count(),
                'total_orders': Order.objects.count(),
                'total_users': User.objects.count(),
                'cache_status': 'active',
            }
            cache.set(cache_key, perf_info, 600)  # Кэшируем на 10 минут
        except Exception:
            perf_info = {
                'total_products': 0,
                'total_categories': 0,
                'total_orders': 0,
                'total_users': 0,
                'cache_status': 'error',
            }
    
    return {
        'performance_info': perf_info
    }

# Функция для инвалидации кэша контекстных процессоров
def invalidate_context_cache(user_id=None):
    """
    Инвалидация кэша контекстных процессоров
    """
    cache_keys = [
        'site_settings',
        'categories_menu',
        'featured_products_context',
        'performance_info',
    ]
    
    if user_id:
        user_cache_keys = [
            f'user_stats_{user_id}',
            f'cart_info_{user_id}',
            f'notifications_{user_id}',
        ]
        cache_keys.extend(user_cache_keys)
    
    cache.delete_many(cache_keys)
