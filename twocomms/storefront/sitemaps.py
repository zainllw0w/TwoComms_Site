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

    Phase 17e (2026-05-11) — ``i18n=True`` makes Django emit one
    ``<url>`` per active language, and ``alternates=True`` adds
    ``<xhtml:link rel="alternate" hreflang="...">`` entries pointing
    at every other language variant. ``x_default=True`` adds the
    canonical x-default fallback (defaults to LANGUAGE_CODE = uk).
    """
    changefreq = 'weekly'
    protocol = 'https'
    i18n = True
    alternates = True
    x_default = True

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
    Phase 17e — i18n alternates per language.
    """
    changefreq = 'weekly'
    priority = 0.9
    protocol = 'https'
    i18n = True
    alternates = True
    x_default = True

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


class ProductVariantSitemap(Sitemap):
    """
    Phase 7.4 — sitemap для ONE-segment path-style variant URLs.

    Phase 21 (2026-05-10) — size-only one-segment variants removed
    from this sitemap. ``/product/<slug>/m/`` is the same page with a
    selected size: the visible content barely changes, and 349 of 418
    pre-Phase-21 variant URLs were size-only — pure crawl waste. They
    remain reachable for users (the URL still resolves) but canonical
    on those pages now points to the base product (see
    ``services.variant_meta``). The sitemap therefore lists only the
    crawl-worthy 1-segment subset:

        * Base ``/product/<slug>/``                   — self-canonical (ProductSitemap).
        * 1-segment ``/product/<slug>/<color>/``      — self-canonical.
        * 1-segment ``/product/<slug>/<fit>/``        — self-canonical.
        * 1-segment ``/product/<slug>/<size>/``       — canonical→base, NOT in sitemap.
        * 2+ segments                                 — canonical→base, NOT in sitemap.
    Phase 17e — i18n alternates per language.
    """
    changefreq = 'weekly'
    priority = 0.7
    protocol = 'https'
    i18n = True
    alternates = True
    x_default = True

    def items(self):
        products = (
            Product.objects
            .filter(status='published')
            .exclude(slug='')
            .prefetch_related('color_variants', 'fit_options')
            .only('id', 'slug', 'title', 'updated_at', 'published_at',
                  'size_grid', 'catalog', 'category')
            .order_by('id')
        )

        entries = []
        for product in products:
            lastmod = getattr(product, 'updated_at', None) or getattr(product, 'published_at', None)
            base_path = f'/product/{product.slug}'

            # Colour variants. Each variant.slug was backfilled in
            # Phase 7.1 migrations — empty-slug rows should never exist
            # in production but we guard anyway.
            for cv in product.color_variants.all():
                if cv.slug:
                    entries.append({
                        'loc': f'{base_path}/{cv.slug}/',
                        'lastmod': lastmod,
                    })

            # Fit options — only active ones are user-facing.
            for fit in product.fit_options.all():
                if fit.is_active and fit.code:
                    entries.append({
                        'loc': f'{base_path}/{fit.code}/',
                        'lastmod': lastmod,
                    })

        return entries

    def lastmod(self, item):
        return item.get('lastmod')

    def location(self, item):
        return item['loc']


class CategorySitemap(Sitemap):
    """
    Sitemap для категорий.
    - lastmod использует updated_at (если доступно)
    Phase 17e — i18n alternates per language.
    """
    changefreq = 'monthly'
    priority = 0.8
    protocol = 'https'
    i18n = True
    alternates = True
    x_default = True

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
