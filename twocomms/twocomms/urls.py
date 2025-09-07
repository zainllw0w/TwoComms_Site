from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.views.generic.base import RedirectView
from django.contrib.sitemaps.views import sitemap
from storefront.sitemaps import StaticViewSitemap, ProductSitemap, CategorySitemap

# Sitemap configuration
sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
}

urlpatterns = [
    path("", include("storefront.urls")),
    path("admin/", admin.site.urls),
    
    # Sitemap
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    
    # Явный маршрут для /favicon.ico → статический файл
    path("favicon.ico", RedirectView.as_view(
        url=staticfiles_storage.url("img/favicon.ico"), permanent=False
    )),
]

# Добавляем обработку медиа-файлов для разработки и продакшена
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Для продакшена на PythonAnywhere
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)