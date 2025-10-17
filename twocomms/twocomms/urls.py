from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.views.generic.base import RedirectView
from storefront import views as storefront_views
from django.contrib.sitemaps.views import sitemap
from storefront.sitemaps import StaticViewSitemap, ProductSitemap, CategorySitemap

# Sitemap configuration
sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
}

urlpatterns = [
    # Core - главная страница должна быть первой!
    path("", include("storefront.urls")),
    # Social auth - только для OAuth путей
    path('oauth/', include('social_django.urls', namespace='social')),
    path('social/', include('social_django.urls')),  # fallback для старых ссылок
    path("admin/", admin.site.urls),
    
    # Accounts
    path("accounts/", include("accounts.urls")),
    
    # Orders (включая дропшип)
    path("orders/", include("orders.urls")),
    
    # Sitemap
    path('sitemap.xml', storefront_views.static_sitemap, name='django.contrib.sitemaps.views.sitemap'),
    
    # Явный маршрут для /favicon.ico → статический файл
    path("favicon.ico", RedirectView.as_view(
        url=staticfiles_storage.url("img/favicon.ico"), permanent=False
    )),
    # Явный маршрут для /robots.txt → прямая отдача, без статики
    path("robots.txt", storefront_views.robots_txt, name="robots_txt"),
    # Fallback на случай, если где-то закешировался старый редирект на /static/robots.txt
    path("static/robots.txt", storefront_views.robots_txt),
    # Verification файл в корне сайта
    path("494cb80b2da94b4395dbbed566ab540d.txt", storefront_views.static_verification_file,
         name="static_verification_file"),

    # Google Merchant feed
    path('google_merchant_feed.xml', storefront_views.google_merchant_feed, name='google_merchant_feed'),
    path('google-merchant-feed-v2.xml', storefront_views.google_merchant_feed, name='google_merchant_feed_v2_root'),
    path('merchant/product-feed', storefront_views.google_merchant_feed, name='google_merchant_feed_plain'),
]

# Добавляем обработку медиа-файлов для разработки и продакшена
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Для продакшена на PythonAnywhere
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
