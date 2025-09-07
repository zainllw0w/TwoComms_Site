"""
Менеджер кэширования для оптимизации производительности
"""

from django.core.cache import cache
from django.db.models import Count, Sum, Q
from django.contrib.auth.models import User
from .models import Product, Category
from orders.models import Order
from accounts.models import UserPoints

class CacheManager:
    """Менеджер кэширования"""
    
    @staticmethod
    def invalidate_product_cache():
        """Инвалидация кэша товаров"""
        cache_keys = [
            'products_count',
            'home_data',
            'featured_product',
            'categories_list'
        ]
        cache.delete_many(cache_keys)
    
    @staticmethod
    def invalidate_orders_cache():
        """Инвалидация кэша заказов"""
        cache_keys = [
            'orders_stats',
            'admin_orders_data'
        ]
        cache.delete_many(cache_keys)
    
    @staticmethod
    def get_cached_home_data():
        """Кэшированные данные для главной страницы"""
        cache_key = 'home_data'
        data = cache.get(cache_key)
        
        if data is None:
            # Оптимизированные запросы
            featured = Product.objects.select_related('category').filter(
                featured=True
            ).order_by('-id').first()
            
            categories = Category.objects.filter(is_active=True).order_by('order', 'name')
            
            products = list(Product.objects.select_related('category').order_by('-id')[:8])
            
            # Подготавливаем данные
            data = {
                'featured': featured,
                'categories': categories,
                'products': products,
                'total_products': Product.objects.count()
            }
            
            cache.set(cache_key, data, 300)  # Кэшируем на 5 минут
        
        return data
    
    @staticmethod
    def get_products_count_cached():
        """Кэшированный подсчет товаров"""
        cache_key = 'products_count'
        count = cache.get(cache_key)
        
        if count is None:
            count = Product.objects.count()
            cache.set(cache_key, count, 300)  # Кэшируем на 5 минут
        
        return count
    
    @staticmethod
    def get_orders_stats_cached():
        """Кэшированная статистика заказов"""
        cache_key = 'orders_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            stats = {}
            
            # Один запрос для всех статусов
            status_counts = Order.objects.values('status').annotate(count=Count('id'))
            for item in status_counts:
                stats[f"{item['status']}_count"] = item['count']
            
            # Один запрос для всех статусов оплаты
            payment_counts = Order.objects.values('payment_status').annotate(count=Count('id'))
            for item in payment_counts:
                stats[f"payment_{item['payment_status']}_count"] = item['count']
            
            cache.set(cache_key, stats, 300)  # Кэшируем на 5 минут
        
        return stats
    
    @staticmethod
    def get_optimized_users_with_stats():
        """Оптимизированный запрос для получения пользователей со статистикой"""
        # Используем подзапросы для агрегации
        users = User.objects.select_related('userprofile').prefetch_related(
            Prefetch('orders', queryset=Order.objects.select_related('promo_code')),
            Prefetch('points', queryset=UserPoints.objects.all())
        ).annotate(
            total_orders_count=Count('orders'),
            total_spent=Sum('orders__total_sum', filter=Q(orders__payment_status__in=['paid', 'partial', 'checking'])),
            new_orders=Count('orders', filter=Q(orders__status='new')),
            prep_orders=Count('orders', filter=Q(orders__status='prep')),
            ship_orders=Count('orders', filter=Q(orders__status='ship')),
            done_orders=Count('orders', filter=Q(orders__status='done')),
            cancelled_orders=Count('orders', filter=Q(orders__status='cancelled')),
            unpaid_orders=Count('orders', filter=Q(orders__payment_status='unpaid')),
            checking_orders=Count('orders', filter=Q(orders__payment_status='checking')),
            partial_orders=Count('orders', filter=Q(orders__payment_status='partial')),
            paid_orders=Count('orders', filter=Q(orders__payment_status='paid'))
        ).order_by('username')
        
        return users
