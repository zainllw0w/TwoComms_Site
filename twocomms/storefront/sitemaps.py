"""
Динамический sitemap для SEO
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Product, Category
from django.utils import timezone

class StaticViewSitemap(Sitemap):
    """
    Sitemap для статических страниц
    """
    priority = 0.8
    changefreq = 'weekly'
    protocol = 'https'
    domain = 'twocomms.shop'
    
    def items(self):
        return [
            'home',
            'catalog',
        ]
    
    def location(self, item):
        return reverse(item)
    
    def lastmod(self, item):
        return timezone.now()

class ProductSitemap(Sitemap):
    """
    Sitemap для товаров
    """
    changefreq = 'weekly'
    priority = 0.9
    protocol = 'https'
    domain = 'twocomms.shop'
    
    def items(self):
        # Возвращаем все товары, так как у Product нет поля is_active
        return Product.objects.all()
    
    def lastmod(self, obj):
        # У Product нет полей времени, возвращаем None
        return None
    
    def location(self, obj):
        return reverse('product', kwargs={'slug': obj.slug})

class CategorySitemap(Sitemap):
    """
    Sitemap для категорий
    """
    changefreq = 'monthly'
    priority = 0.7
    protocol = 'https'
    domain = 'twocomms.shop'
    
    def items(self):
        return Category.objects.filter(is_active=True)
    
    def lastmod(self, obj):
        # Можно использовать реальное время изменения, если поле появится в модели
        return timezone.now()
    
    def location(self, obj):
        return reverse('catalog_by_cat', kwargs={'cat_slug': obj.slug})
