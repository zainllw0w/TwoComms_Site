"""
Оптимизированные модели для orders приложения
"""

from django.conf import settings
from django.db import models
from storefront.models import Product, PromoCode
from productcolors.models import ProductColorVariant
from datetime import datetime
from django.core.cache import cache
from django.db.models import Sum, Count, Q, Avg, Max, Min
from django.utils import timezone

class OrderManager(models.Manager):
    """Оптимизированный менеджер для Order"""
    
    def with_user_data(self):
        """Заказы с данными пользователя"""
        return self.select_related('user', 'promo_code')
    
    def with_items(self):
        """Заказы с элементами"""
        return self.prefetch_related('items', 'items__product', 'items__color_variant')
    
    def recent_orders(self, days=30):
        """Недавние заказы"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created__gte=cutoff_date)
    
    def get_processing_count_cached(self):
        """Кэшированное количество заказов в обработке"""
        cache_key = 'orders_processing_count'
        count = cache.get(cache_key)
        
        if count is None:
            count = self.filter(status='new').count()
            cache.set(cache_key, count, 300)  # Кэшируем на 5 минут
        
        return count
    
    def get_orders_stats_cached(self):
        """Кэшированная статистика заказов"""
        cache_key = 'orders_detailed_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            stats = {
                'total_orders': self.count(),
                'new_orders': self.filter(status='new').count(),
                'prep_orders': self.filter(status='prep').count(),
                'ship_orders': self.filter(status='ship').count(),
                'done_orders': self.filter(status='done').count(),
                'cancelled_orders': self.filter(status='cancelled').count(),
                'unpaid_orders': self.filter(payment_status='unpaid').count(),
                'checking_orders': self.filter(payment_status='checking').count(),
                'partial_orders': self.filter(payment_status='partial').count(),
                'paid_orders': self.filter(payment_status='paid').count(),
                'total_revenue': self.filter(payment_status__in=['paid', 'partial']).aggregate(
                    total=Sum('total_sum')
                )['total'] or 0,
                'avg_order_value': self.filter(payment_status__in=['paid', 'partial']).aggregate(
                    avg=Avg('total_sum')
                )['avg'] or 0,
            }
            cache.set(cache_key, stats, 600)  # Кэшируем на 10 минут
        
        return stats
    
    def get_daily_stats(self, days=30):
        """Статистика по дням"""
        cache_key = f'orders_daily_stats_{days}'
        stats = cache.get(cache_key)
        
        if stats is None:
            from django.db.models.functions import TruncDate
            
            stats = list(
                self.filter(created__gte=timezone.now() - timezone.timedelta(days=days))
                .annotate(date=TruncDate('created'))
                .values('date')
                .annotate(
                    orders_count=Count('id'),
                    revenue=Sum('total_sum', filter=Q(payment_status__in=['paid', 'partial']))
                )
                .order_by('date')
            )
            cache.set(cache_key, stats, 1800)  # Кэшируем на 30 минут
        
        return stats
    
    def get_user_orders(self, user, limit=50):
        """Заказы пользователя"""
        cache_key = f'user_orders_{user.id}_{limit}'
        orders = cache.get(cache_key)
        
        if orders is None:
            orders = list(
                self.filter(user=user)
                .with_user_data()
                .with_items()
                .order_by('-created')[:limit]
            )
            cache.set(cache_key, orders, 300)  # Кэшируем на 5 минут
        
        return orders
    
    def get_recent_orders(self, limit=20):
        """Недавние заказы"""
        cache_key = f'recent_orders_{limit}'
        orders = cache.get(cache_key)
        
        if orders is None:
            orders = list(
                self.with_user_data()
                .with_items()
                .order_by('-created')[:limit]
            )
            cache.set(cache_key, orders, 300)  # Кэшируем на 5 минут
        
        return orders

class OrderItemManager(models.Manager):
    """Оптимизированный менеджер для OrderItem"""
    
    def with_product_data(self):
        """Элементы заказа с данными товара"""
        return self.select_related('product', 'product__category', 'color_variant', 'color_variant__color')
    
    def get_popular_products(self, limit=20):
        """Популярные товары"""
        cache_key = f'popular_products_{limit}'
        popular = cache.get(cache_key)
        
        if popular is None:
            popular = list(
                self.values('product')
                .annotate(
                    total_ordered=Sum('qty'),
                    orders_count=Count('order', distinct=True)
                )
                .order_by('-total_ordered')[:limit]
            )
            cache.set(cache_key, popular, 1800)  # Кэшируем на 30 минут
        
        return popular
    
    def get_sales_stats(self, days=30):
        """Статистика продаж"""
        cache_key = f'sales_stats_{days}'
        stats = cache.get(cache_key)
        
        if stats is None:
            cutoff_date = timezone.now() - timezone.timedelta(days=days)
            stats = self.filter(order__created__gte=cutoff_date).aggregate(
                total_items=Sum('qty'),
                total_revenue=Sum('line_total'),
                avg_item_price=Avg('unit_price'),
                unique_products=Count('product', distinct=True)
            )
            cache.set(cache_key, stats, 1800)  # Кэшируем на 30 минут
        
        return stats

class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'В обробці'),
        ('prep', 'Готується до відправлення'),
        ('ship', 'Відправлено'),
        ('done', 'Отримано'),
        ('cancelled', 'Скасовано'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32)
    city = models.CharField(max_length=100)
    np_office = models.CharField(max_length=200)
    pay_type = models.CharField(max_length=10, default='full')
    payment_status = models.CharField(max_length=20, choices=[
        ('unpaid', 'Не оплачено'),
        ('checking', 'На перевірці'),
        ('partial', 'Внесена передплата'),
        ('paid', 'Оплачено повністю'),
    ], default='unpaid')
    total_sum = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Сума знижки')
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Використаний промокод')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new')
    tracking_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='Номер ТТН')
    payment_screenshot = models.ImageField(upload_to='payment_screenshots/', blank=True, null=True, verbose_name='Скріншот оплати')
    points_awarded = models.BooleanField(default=False, verbose_name='Бали нараховані')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = OrderManager()

    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['user', 'created']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created']),
            models.Index(fields=['order_number']),
        ]

    def __str__(self):
        return f'Order {self.order_number} by {self.get_user_display()} — {self.get_status_display()}'
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
        self.invalidate_cache()
    
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.invalidate_cache()
    
    def invalidate_cache(self):
        """Инвалидация кэша заказов"""
        cache_keys = [
            'orders_processing_count',
            'orders_detailed_stats',
            'orders_daily_stats_30',
            'recent_orders_20',
        ]
        cache.delete_many(cache_keys)
        
        if self.user:
            cache_key = f'user_orders_{self.user.id}_50'
            cache.delete(cache_key)
    
    def generate_order_number(self):
        """Генерирует номер заказа в формате TWC+дата+N+номер"""
        today = datetime.now()
        date_str = today.strftime('%d%m%Y')
        
        # Получаем количество заказов за сегодня
        today_orders = Order.objects.filter(
            created__date=today.date()
        ).count()
        
        # Номер по счету (начиная с 01)
        order_count = today_orders + 1
        
        return f"TWC{date_str}N{order_count:02d}"
    
    def get_user_display(self):
        """Возвращает отображаемое имя пользователя"""
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
        return "Гість"
    
    def get_payment_status_display(self):
        """Возвращает отображаемое название статуса оплаты"""
        payment_status_choices = dict([
            ('unpaid', 'Не оплачено'),
            ('checking', 'На перевірці'),
            ('partial', 'Внесена передплата'),
            ('paid', 'Оплачено повністю'),
        ])
        return payment_status_choices.get(self.payment_status, self.payment_status)
    
    @classmethod
    def get_processing_count(cls):
        """Возвращает количество заказов в обработке"""
        return cls.objects.get_processing_count_cached()
    
    @property
    def subtotal(self):
        """Сумма без скидки"""
        return sum(item.line_total for item in self.items.all())
    
    @property
    def final_total(self):
        """Итоговая сумма с учетом скидки"""
        return self.total_sum
    
    @property
    def total_points(self):
        """Возвращает общее количество балов за заказ"""
        total = 0
        for item in self.items.all():
            if hasattr(item.product, 'points_reward') and item.product.points_reward:
                total += item.product.points_reward * item.qty
        return total
    
    def apply_promo_code(self, promo_code):
        """Применяет промокод к заказу"""
        if not promo_code or not promo_code.can_be_used():
            return False
        
        from decimal import Decimal
        
        subtotal = self.subtotal
        discount = promo_code.calculate_discount(subtotal)
        
        if discount > 0:
            # Преобразуем discount в Decimal для совместимости
            discount_decimal = Decimal(str(discount))
            self.discount_amount = discount_decimal
            self.total_sum = subtotal - discount_decimal
            self.promo_code = promo_code
            return True
        
        return False

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    color_variant = models.ForeignKey(ProductColorVariant, on_delete=models.PROTECT, null=True, blank=True)
    title = models.CharField(max_length=200)
    size = models.CharField(max_length=16, blank=True)
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    objects = OrderItemManager()

    class Meta:
        indexes = [
            models.Index(fields=['order', 'product']),
            models.Index(fields=['product']),
            models.Index(fields=['color_variant']),
        ]

    def __str__(self):
        return f'{self.title} × {self.qty}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invalidate_cache()
    
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.invalidate_cache()
    
    def invalidate_cache(self):
        """Инвалидация кэша элементов заказа"""
        cache_keys = [
            'popular_products_20',
            'sales_stats_30',
        ]
        cache.delete_many(cache_keys)
    
    @property
    def color_name(self):
        """Возвращает название цвета или None"""
        if self.color_variant:
            return str(self.color_variant.color)
        return None
    
    @property
    def product_image(self):
        """Возвращает изображение товара с учетом выбранного цвета"""
        if self.color_variant and self.color_variant.images.exists():
            return self.color_variant.images.first().image
        return self.product.main_image
