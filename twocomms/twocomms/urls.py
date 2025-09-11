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
    
    # Sitemap
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    
    # Явный маршрут для /favicon.ico → статический файл
    path("favicon.ico", RedirectView.as_view(
        url=staticfiles_storage.url("img/favicon.ico"), permanent=False
    )),
    # Явный маршрут для /robots.txt → прямая отдача, без статики
    path("robots.txt", storefront_views.robots_txt, name="robots_txt"),
    # Fallback на случай, если где-то закешировался старый редирект на /static/robots.txt
    path("static/robots.txt", storefront_views.robots_txt),
]

# Добавляем обработку медиа-файлов для разработки и продакшена
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Для продакшена на PythonAnywhere
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)