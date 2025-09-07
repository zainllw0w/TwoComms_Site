"""
Оптимизатор запросов для улучшения производительности
"""

from django.db.models import Count, Sum, Q, Prefetch
from django.core.cache import cache
from django.contrib.auth.models import User
from .models import Product, Category
from orders.models import Order
from accounts.models import UserPoints

class QueryOptimizer:
    """Класс для оптимизации запросов к базе данных"""
    
    @staticmethod
    def get_optimized_products_with_colors(limit=None, offset=0):
        """Оптимизированный запрос для получения товаров с цветами"""
        queryset = Product.objects.select_related('category').order_by('-id')
        
        if limit:
            queryset = queryset[offset:offset + limit]
        
        return queryset
    
    @staticmethod
    def get_optimized_categories():
        """Оптимизированный запрос для получения категорий"""
        return Category.objects.filter(is_active=True).order_by('order', 'name')
    
    @staticmethod
    def get_optimized_featured_product():
        """Оптимизированный запрос для получения рекомендуемого товара"""
        return Product.objects.select_related('category').filter(
            featured=True
        ).order_by('-id').first()
    
    @staticmethod
    def get_optimized_products_list(limit=8, offset=0):
        """Оптимизированный запрос для получения списка товаров"""
        return list(Product.objects.select_related('category').order_by('-id')[offset:offset + limit])
    
    @staticmethod
    def get_optimized_orders_with_filters(status_filter='all', payment_filter='all', user_id_filter=None):
        """Оптимизированный запрос для получения заказов с фильтрами"""
        from orders.models import OrderItem
        
        # Базовый queryset с оптимизацией
        orders = Order.objects.select_related('user', 'promo_code').prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('product'))
        )
        
        # Применяем фильтры
        if status_filter != 'all':
            orders = orders.filter(status=status_filter)
        if payment_filter != 'all':
            orders = orders.filter(payment_status=payment_filter)
        if user_id_filter:
            orders = orders.filter(user_id=user_id_filter)
        
        return orders.order_by('-created')[:100]  # Ограничиваем для производительности
    
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
    
    @staticmethod
    def get_optimized_orders_stats():
        """Оптимизированный запрос для получения статистики заказов"""
        stats = {}
        
        # Один запрос для всех статусов
        status_counts = Order.objects.values('status').annotate(count=Count('id'))
        for item in status_counts:
            stats[f"{item['status']}_count"] = item['count']
        
        # Один запрос для всех статусов оплаты
        payment_counts = Order.objects.values('payment_status').annotate(count=Count('id'))
        for item in payment_counts:
            stats[f"payment_{item['payment_status']}_count"] = item['count']
        
        return stats
    
    @staticmethod
    def get_optimized_products_count():
        """Оптимизированный запрос для получения количества товаров"""
        return Product.objects.count()
    
    @staticmethod
    def get_optimized_categories_count():
        """Оптимизированный запрос для получения количества категорий"""
        return Category.objects.count()
    
    @staticmethod
    def get_optimized_users_count():
        """Оптимизированный запрос для получения количества пользователей"""
        return User.objects.count()
    
    @staticmethod
    def get_optimized_points_total():
        """Оптимизированный запрос для получения общего количества баллов"""
        result = UserPoints.objects.aggregate(total=Sum('points'))
        return result['total'] or 0
