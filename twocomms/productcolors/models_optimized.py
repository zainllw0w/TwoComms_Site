"""
Оптимизированные модели для productcolors приложения
"""

from django.db import models
from storefront.models import Product
from django.core.cache import cache
from django.db.models import Count, Prefetch

class ColorManager(models.Manager):
    """Оптимизированный менеджер для Color"""
    
    def popular_colors(self, limit=20):
        """Популярные цвета"""
        cache_key = f'popular_colors_{limit}'
        colors = cache.get(cache_key)
        
        if colors is None:
            colors = list(
                self.annotate(
                    variants_count=Count('variants'),
                    products_count=Count('variants__product', distinct=True)
                )
                .order_by('-variants_count')[:limit]
            )
            cache.set(cache_key, colors, 1800)  # Кэшируем на 30 минут
        
        return colors
    
    def get_all_colors_cached(self):
        """Все цвета из кэша"""
        cache_key = 'all_colors'
        colors = cache.get(cache_key)
        
        if colors is None:
            colors = list(self.all().order_by('name', 'primary_hex'))
            cache.set(cache_key, colors, 3600)  # Кэшируем на час
        
        return colors

class ProductColorVariantManager(models.Manager):
    """Оптимизированный менеджер для ProductColorVariant"""
    
    def with_product_data(self):
        """Варианты с данными товара"""
        return self.select_related('product', 'product__category', 'color')
    
    def with_images(self):
        """Варианты с изображениями"""
        return self.prefetch_related('images')
    
    def get_product_variants(self, product):
        """Варианты цвета для товара"""
        cache_key = f'product_variants_{product.id}'
        variants = cache.get(cache_key)
        
        if variants is None:
            variants = list(
                self.filter(product=product)
                .with_product_data()
                .with_images()
                .order_by('order', 'id')
            )
            cache.set(cache_key, variants, 1800)  # Кэшируем на 30 минут
        
        return variants
    
    def get_default_variant(self, product):
        """Вариант по умолчанию для товара"""
        cache_key = f'product_default_variant_{product.id}'
        variant = cache.get(cache_key)
        
        if variant is None:
            try:
                variant = self.filter(product=product, is_default=True).with_product_data().with_images().first()
                if not variant:
                    variant = self.filter(product=product).with_product_data().with_images().first()
                cache.set(cache_key, variant, 1800)  # Кэшируем на 30 минут
            except:
                variant = None
        
        return variant
    
    def get_variants_with_colors(self, product_ids):
        """Варианты для списка товаров"""
        cache_key = f'variants_with_colors_{hash(tuple(sorted(product_ids)))}'
        variants = cache.get(cache_key)
        
        if variants is None:
            variants = list(
                self.filter(product_id__in=product_ids)
                .with_product_data()
                .with_images()
                .order_by('product_id', 'order', 'id')
            )
            cache.set(cache_key, variants, 1800)  # Кэшируем на 30 минут
        
        return variants
    
    def get_color_statistics(self):
        """Статистика по цветам"""
        cache_key = 'color_statistics'
        stats = cache.get(cache_key)
        
        if stats is None:
            stats = list(
                self.values('color')
                .annotate(
                    variants_count=Count('id'),
                    products_count=Count('product', distinct=True)
                )
                .order_by('-variants_count')
            )
            cache.set(cache_key, stats, 3600)  # Кэшируем на час
        
        return stats

class ProductColorImageManager(models.Manager):
    """Оптимизированный менеджер для ProductColorImage"""
    
    def get_variant_images(self, variant):
        """Изображения для варианта"""
        cache_key = f'variant_images_{variant.id}'
        images = cache.get(cache_key)
        
        if images is None:
            images = list(self.filter(variant=variant).order_by('order', 'id'))
            cache.set(cache_key, images, 3600)  # Кэшируем на час
        
        return images
    
    def get_main_image(self, variant):
        """Главное изображение варианта"""
        cache_key = f'variant_main_image_{variant.id}'
        image = cache.get(cache_key)
        
        if image is None:
            image = self.filter(variant=variant).order_by('order', 'id').first()
            cache.set(cache_key, image, 3600)  # Кэшируем на час
        
        return image

class Color(models.Model):
    """
    Универсальная сущность цвета: один или составной (два цвета).
    """
    name = models.CharField(max_length=100, blank=True)
    primary_hex = models.CharField(max_length=7, help_text='#RRGGBB')
    secondary_hex = models.CharField(max_length=7, blank=True, null=True, help_text='#RRGGBB (опционально)')

    objects = ColorManager()

    class Meta:
        unique_together = (('primary_hex', 'secondary_hex'),)
        indexes = [
            models.Index(fields=['primary_hex']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        if self.secondary_hex:
            return f'{self.primary_hex}+{self.secondary_hex}'
        return self.primary_hex

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invalidate_cache()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.invalidate_cache()

    def invalidate_cache(self):
        """Инвалидация кэша цветов"""
        cache_keys = [
            'all_colors',
            'popular_colors_20',
            'color_statistics',
        ]
        cache.delete_many(cache_keys)

class ProductColorVariant(models.Model):
    """
    Вариант цвета для конкретного товара.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='color_variants')
    color = models.ForeignKey(Color, on_delete=models.PROTECT, related_name='variants')
    is_default = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    objects = ProductColorVariantManager()

    class Meta:
        ordering = ['order', 'id']
        unique_together = (('product', 'color'),)
        indexes = [
            models.Index(fields=['product', 'order']),
            models.Index(fields=['color']),
            models.Index(fields=['is_default']),
        ]

    def __str__(self):
        return f'{self.product.title} [{self.color}]'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invalidate_cache()

    def delete(self, *args, **kwargs):
        product_id = self.product.id
        super().delete(*args, **kwargs)
        self.invalidate_cache(product_id)

    def invalidate_cache(self, product_id=None):
        """Инвалидация кэша вариантов"""
        if product_id is None:
            product_id = self.product.id
        
        cache_keys = [
            f'product_variants_{product_id}',
            f'product_default_variant_{product_id}',
            'color_statistics',
        ]
        cache.delete_many(cache_keys)

class ProductColorImage(models.Model):
    """
    Изображения, привязанные к цветовому варианту товара.
    """
    variant = models.ForeignKey(ProductColorVariant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_colors/')
    order = models.PositiveIntegerField(default=0)

    objects = ProductColorImageManager()

    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['variant', 'order']),
        ]

    def __str__(self):
        return f'Image for {self.variant}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invalidate_cache()

    def delete(self, *args, **kwargs):
        variant_id = self.variant.id
        super().delete(*args, **kwargs)
        self.invalidate_cache(variant_id)

    def invalidate_cache(self, variant_id=None):
        """Инвалидация кэша изображений"""
        if variant_id is None:
            variant_id = self.variant.id
        
        cache_keys = [
            f'variant_images_{variant_id}',
            f'variant_main_image_{variant_id}',
        ]
        cache.delete_many(cache_keys)
