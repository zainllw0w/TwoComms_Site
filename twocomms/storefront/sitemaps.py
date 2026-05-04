"""
Динамический sitemap для SEO.

Использует стандартный Django Sitemap framework.
Конфигурация подключена в twocomms/urls.py через crawler-safe wrapper.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Product, Category


# Static routes that should appear in sitemap.
# IMPORTANT: 'search' intentionally excluded (noindex policy).
PUBLIC_STATIC_ROUTE_NAMES = [
    'home',
    'catalog',
    'delivery',
    'about',
    'contacts',
    'cooperation',
    'custom_print',
    'wholesale_page',        # B2B hub — must be indexed
    'help_center',
    'faq',
    'size_guide',
    'care_guide',
    'order_tracking',
    'site_map_page',
    'news',
    'returns',
    'privacy_policy',
    'terms_of_service',
]

# Priority tiers for static pages
_HIGH_PRIORITY_ROUTES = {'home', 'catalog', 'custom_print', 'wholesale_page'}
_MID_PRIORITY_ROUTES = {'delivery', 'about', 'contacts', 'cooperation', 'faq', 'size_guide'}


class StaticViewSitemap(Sitemap):
    """
    Sitemap для статических страниц.
    - search исключён (noindex policy)
    - wholesale добавлен (B2B hub)
    - lastmod = None для статических страниц (честнее чем timezone.now())
    """
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return PUBLIC_STATIC_ROUTE_NAMES

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        if item in _HIGH_PRIORITY_ROUTES:
            return 1.0
        if item in _MID_PRIORITY_ROUTES:
            return 0.7
        return 0.5

    def lastmod(self, item):
        # Static pages don't have meaningful lastmod.
        # Returning None is more honest than timezone.now() — Google
        # penalises sites that always return "now" for lastmod.
        return None


class ProductSitemap(Sitemap):
    """
    Sitemap для товаров.
    - lastmod использует updated_at (если доступно) или published_at
    """
    changefreq = 'weekly'
    priority = 0.9
    protocol = 'https'

    def items(self):
        return (
            Product.objects
            .filter(status='published')
            .exclude(slug='')
            .only('slug', 'updated_at', 'published_at')
            .order_by('id')
        )

    def lastmod(self, obj):
        # Prefer updated_at (auto_now), fall back to published_at
        return getattr(obj, 'updated_at', None) or getattr(obj, 'published_at', None)

    def location(self, obj):
        return reverse('product', kwargs={'slug': obj.slug})


class CategorySitemap(Sitemap):
    """
    Sitemap для категорий.
    - lastmod использует updated_at (если доступно)
    """
    changefreq = 'monthly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        return (
            Category.objects
            .filter(is_active=True)
            .only('slug', 'updated_at')
        )

    def lastmod(self, obj):
        return getattr(obj, 'updated_at', None)

    def location(self, obj):
        return reverse('catalog_by_cat', kwargs={'cat_slug': obj.slug})
