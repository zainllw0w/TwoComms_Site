"""
Оптимизированные модели с улучшенными запросами и кэшированием
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Sum, Q, Prefetch
from django.utils.functional import cached_property

class ProductManager(models.Manager):
    """Менеджер для оптимизированных запросов товаров"""
    
    def active(self):
        """Активные товары"""
        return self.all()  # Убираем фильтр is_active, так как поле не существует
    
    def featured(self):
        """Рекомендуемые товары"""
        return self.filter(featured=True)
    
    def with_category(self):
        """Товары с категорией"""
        return self.select_related('category')
    
    def optimized_list(self):
        """Оптимизированный список товаров"""
        return self.with_category().order_by('-id')
    
    def get_featured(self):
        """Получить рекомендуемый товар"""
        return self.featured().with_category().order_by('-id').first()
    
    def get_latest(self, limit=8):
        """Получить последние товары"""
        return list(self.with_category().order_by('-id')[:limit])

class CategoryManager(models.Manager):
    """Менеджер для оптимизированных запросов категорий"""
    
    def active(self):
        """Активные категории"""
        return self.filter(is_active=True)
    
    def with_products_count(self):
        """Категории с количеством товаров"""
        return self.annotate(products_count=Count('products'))
    
    def optimized_list(self):
        """Оптимизированный список категорий"""
        return self.active().with_products_count().order_by('order', 'name')

class OrderManager(models.Manager):
    """Менеджер для оптимизированных запросов заказов"""
    
    def with_user(self):
        """Заказы с пользователем"""
        return self.select_related('user', 'promo_code')
    
    def with_items(self):
        """Заказы с элементами"""
        from orders.models import OrderItem
        return self.prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('product'))
        )
    
    def optimized_list(self):
        """Оптимизированный список заказов"""
        return self.with_user().with_items().order_by('-created')
    
    def get_stats(self):
        """Получить статистику заказов"""
        stats = {}
        
        # Один запрос для всех статусов
        status_counts = self.values('status').annotate(count=Count('id'))
        for item in status_counts:
            stats[f"{item['status']}_count"] = item['count']
        
        # Один запрос для всех статусов оплаты
        payment_counts = self.values('payment_status').annotate(count=Count('id'))
        for item in payment_counts:
            stats[f"payment_{item['payment_status']}_count"] = item['count']
        
        return stats

class UserManager(models.Manager):
    """Менеджер для оптимизированных запросов пользователей"""
    
    def with_profile(self):
        """Пользователи с профилем"""
        return self.select_related('userprofile')
    
    def with_orders(self):
        """Пользователи с заказами"""
        from orders.models import Order
        return self.prefetch_related(
            Prefetch('orders', queryset=Order.objects.select_related('promo_code'))
        )
    
    def with_points(self):
        """Пользователи с баллами"""
        from accounts.models import UserPoints
        return self.prefetch_related(
            Prefetch('points', queryset=UserPoints.objects.all())
        )
    
    def optimized_list(self):
        """Оптимизированный список пользователей"""
        return self.with_profile().with_orders().with_points().order_by('username')
    
    def get_stats(self):
        """Получить статистику пользователей"""
        from orders.models import Order
        from accounts.models import UserPoints
        
        return self.annotate(
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
        )

# Применяем менеджеры к моделям
from .models import Product, Category
from orders.models import Order

Product.add_to_class('objects', ProductManager())
Category.add_to_class('objects', CategoryManager())
Order.add_to_class('objects', OrderManager())
User.add_to_class('objects', UserManager())
