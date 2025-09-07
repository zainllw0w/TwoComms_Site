"""
Оптимизированная админка для storefront приложения
"""

from django.contrib import admin
from django.core.cache import cache
from django.db.models import Count, Sum
from django.utils.html import format_html
from .models import Category, Product, ProductImage, PrintProposal

class OptimizedCategoryAdmin(admin.ModelAdmin):
    """Оптимизированная админка для категорий"""
    
    list_display = ('name', 'slug', 'order', 'is_active', 'is_featured', 'products_count')
    list_filter = ('is_active', 'is_featured', 'created_at')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'slug', 'description', 'order')
        }),
        ('Изображения', {
            'fields': ('icon', 'cover'),
            'classes': ('collapse',)
        }),
        ('Настройки', {
            'fields': ('is_active', 'is_featured'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Оптимизированный queryset с подсчетом товаров"""
        return super().get_queryset(request).annotate(
            products_count=Count('product')
        )
    
    def products_count(self, obj):
        """Количество товаров в категории"""
        return obj.products_count
    products_count.short_description = 'Товаров'
    products_count.admin_order_field = 'products_count'
    
    def save_model(self, request, obj, form, change):
        """Сохранение с инвалидацией кэша"""
        super().save_model(request, obj, form, change)
        self.invalidate_cache()
    
    def delete_model(self, request, obj):
        """Удаление с инвалидацией кэша"""
        super().delete_model(request, obj)
        self.invalidate_cache()
    
    def invalidate_cache(self):
        """Инвалидация кэша"""
        cache_keys = [
            'categories_list',
            'categories_menu',
            'form_categories',
            'home_data',
        ]
        cache.delete_many(cache_keys)

class OptimizedProductAdmin(admin.ModelAdmin):
    """Оптимизированная админка для товаров"""
    
    list_display = ('title', 'category', 'price', 'discount_percent', 'points_reward', 'featured', 'created_at')
    list_filter = ('category', 'featured', 'created_at', 'updated_at')
    search_fields = ('title', 'slug', 'description')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'category', 'description')
        }),
        ('Цена и скидки', {
            'fields': ('price', 'discount_percent', 'points_reward'),
            'classes': ('collapse',)
        }),
        ('Изображения', {
            'fields': ('main_image',),
            'classes': ('collapse',)
        }),
        ('Настройки', {
            'fields': ('featured',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Оптимизированный queryset"""
        return super().get_queryset(request).select_related('category')
    
    def save_model(self, request, obj, form, change):
        """Сохранение с инвалидацией кэша"""
        super().save_model(request, obj, form, change)
        self.invalidate_cache()
    
    def delete_model(self, request, obj):
        """Удаление с инвалидацией кэша"""
        super().delete_model(request, obj)
        self.invalidate_cache()
    
    def invalidate_cache(self):
        """Инвалидация кэша"""
        cache_keys = [
            'home_data',
            'products_count',
            'featured_products',
            'catalog_data',
        ]
        cache.delete_many(cache_keys)

class OptimizedProductImageAdmin(admin.ModelAdmin):
    """Оптимизированная админка для изображений товаров"""
    
    list_display = ('product', 'image_preview', 'order')
    list_filter = ('product__category',)
    search_fields = ('product__title',)
    ordering = ('product', 'order')
    
    def get_queryset(self, request):
        """Оптимизированный queryset"""
        return super().get_queryset(request).select_related('product', 'product__category')
    
    def image_preview(self, obj):
        """Превью изображения"""
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover;" />',
                obj.image.url
            )
        return "Нет изображения"
    image_preview.short_description = 'Превью'
    
    def save_model(self, request, obj, form, change):
        """Сохранение с инвалидацией кэша"""
        super().save_model(request, obj, form, change)
        self.invalidate_cache()
    
    def delete_model(self, request, obj):
        """Удаление с инвалидацией кэша"""
        super().delete_model(request, obj)
        self.invalidate_cache()
    
    def invalidate_cache(self):
        """Инвалидация кэша"""
        cache_keys = [
            'home_data',
            'catalog_data',
        ]
        cache.delete_many(cache_keys)

class OptimizedPrintProposalAdmin(admin.ModelAdmin):
    """Оптимизированная админка для предложений принтов"""
    
    list_display = ('user', 'status', 'awarded_points', 'awarded_promocode', 'created_at', 'image_preview')
    list_filter = ('status', 'created_at', 'awarded_points', 'awarded_promocode')
    search_fields = ('user__username', 'description', 'link_url')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'status', 'description')
        }),
        ('Изображение', {
            'fields': ('image', 'link_url'),
            'classes': ('collapse',)
        }),
        ('Награды', {
            'fields': ('awarded_points', 'awarded_promocode'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Оптимизированный queryset"""
        return super().get_queryset(request).select_related('user')
    
    def image_preview(self, obj):
        """Превью изображения"""
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover;" />',
                obj.image.url
            )
        elif obj.link_url:
            return format_html('<a href="{}" target="_blank">Ссылка</a>', obj.link_url)
        return "Нет изображения"
    image_preview.short_description = 'Превью'
    
    def save_model(self, request, obj, form, change):
        """Сохранение с инвалидацией кэша"""
        super().save_model(request, obj, form, change)
        self.invalidate_cache()
    
    def delete_model(self, request, obj):
        """Удаление с инвалидацией кэша"""
        super().delete_model(request, obj)
        self.invalidate_cache()
    
    def invalidate_cache(self):
        """Инвалидация кэша"""
        cache_keys = [
            'print_proposals_pending',
            'admin_orders_data',
        ]
        cache.delete_many(cache_keys)

# Регистрация оптимизированных админок
admin.site.register(Category, OptimizedCategoryAdmin)
admin.site.register(Product, OptimizedProductAdmin)
admin.site.register(ProductImage, OptimizedProductImageAdmin)
admin.site.register(PrintProposal, OptimizedPrintProposalAdmin)

# Настройки админки
admin.site.site_header = "TwoComms Админка"
admin.site.site_title = "TwoComms Admin"
admin.site.index_title = "Управление сайтом"
