"""
Оптимизированные модели с улучшенными запросами и кэшированием
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Sum, Q, Prefetch
from django.utils.functional import cached_property

class CategoryOptimized(models.Model):
    """Оптимизированная модель категории"""
    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(unique=True, db_index=True)
    icon = models.ImageField(upload_to='category_icons/', blank=True, null=True)
    cover = models.ImageField(upload_to='category_covers/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['is_active', 'order']),
            models.Index(fields=['is_featured', 'is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    @cached_property
    def products_count(self):
        """Кэшированное количество товаров в категории"""
        cache_key = f'category_{self.id}_products_count'
        count = cache.get(cache_key)
        if count is None:
            count = self.products.filter(is_active=True).count()
            cache.set(cache_key, count, 300)  # Кэшируем на 5 минут
        return count
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Инвалидируем кэш при изменении
        cache.delete(f'category_{self.id}_products_count')
        cache.delete('categories_list')

class ProductOptimized(models.Model):
    """Оптимизированная модель товара"""
    title = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(unique=True, db_index=True)
    category = models.ForeignKey(
        CategoryOptimized, 
        on_delete=models.PROTECT, 
        related_name='products',
        db_index=True
    )
    price = models.PositiveIntegerField(db_index=True)
    has_discount = models.BooleanField(default=False, db_index=True)
    discount_percent = models.PositiveIntegerField(blank=True, null=True)
    featured = models.BooleanField(default=False, db_index=True)
    description = models.TextField(blank=True)
    main_image = models.ImageField(upload_to='products/', blank=True, null=True)
    points_reward = models.PositiveIntegerField(default=0, verbose_name='Бали за покупку')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'featured']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['price', 'is_active']),
            models.Index(fields=['created_at', 'is_active']),
        ]
    
    def __str__(self):
        return self.title
    
    @cached_property
    def final_price(self):
        """Кэшированная финальная цена"""
        if self.has_discount and self.discount_percent:
            return int(self.price * (100 - self.discount_percent) / 100)
        return self.price
    
    @cached_property
    def display_image(self):
        """Кэшированное главное изображение"""
        if self.main_image:
            return self.main_image
        
        # Если нет главного изображения, ищем в цветах
        first_color_variant = self.color_variants.first()
        if first_color_variant:
            first_image = first_color_variant.images.first()
            if first_image:
                return first_image.image
        
        return None
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Инвалидируем кэш при изменении
        cache.delete(f'product_{self.id}_final_price')
        cache.delete(f'product_{self.id}_display_image')
        cache.delete('products_count')
        cache.delete('home_data')

class ProductImageOptimized(models.Model):
    """Оптимизированная модель изображения товара"""
    product = models.ForeignKey(
        ProductOptimized, 
        on_delete=models.CASCADE, 
        related_name='images',
        db_index=True
    )
    image = models.ImageField(upload_to='products/extra/')
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_main = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['product', 'order']),
            models.Index(fields=['product', 'is_main']),
        ]
    
    def __str__(self):
        return f'Image for {self.product_id}'

class PromoCodeOptimized(models.Model):
    """Оптимизированная модель промокода"""
    DISCOUNT_TYPES = [
        ('percentage', 'Відсоток'),
        ('fixed', 'Фіксована сума'),
    ]
    
    code = models.CharField(max_length=20, unique=True, blank=True, db_index=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True, db_index=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0, db_index=True)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'expires_at']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['code', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.code} ({self.discount_value}%)"
    
    @cached_property
    def is_valid(self):
        """Проверка валидности промокода"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
        return True
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Инвалидируем кэш при изменении
        cache.delete(f'promocode_{self.id}_is_valid')

# Менеджеры для оптимизированных запросов
class ProductManager(models.Manager):
    """Менеджер для оптимизированных запросов товаров"""
    
    def active(self):
        """Активные товары"""
        return self.filter(is_active=True)
    
    def featured(self):
        """Рекомендуемые товары"""
        return self.filter(featured=True, is_active=True)
    
    def with_colors(self):
        """Товары с цветами"""
        return self.prefetch_related(
            Prefetch(
                'color_variants',
                queryset=ProductColorVariant.objects.select_related('color').order_by('order', 'id')
            )
        )
    
    def with_category(self):
        """Товары с категорией"""
        return self.select_related('category')
    
    def optimized_list(self):
        """Оптимизированный список товаров"""
        return self.active().with_category().with_colors()

class CategoryManager(models.Manager):
    """Менеджер для оптимизированных запросов категорий"""
    
    def active(self):
        """Активные категории"""
        return self.filter(is_active=True)
    
    def with_products_count(self):
        """Категории с количеством товаров"""
        return self.annotate(products_count=Count('products', filter=Q(products__is_active=True)))
    
    def optimized_list(self):
        """Оптимизированный список категорий"""
        return self.active().with_products_count().order_by('order', 'name')

# Применяем менеджеры к моделям
ProductOptimized.add_to_class('objects', ProductManager())
CategoryOptimized.add_to_class('objects', CategoryManager())
