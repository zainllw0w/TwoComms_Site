from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin

urlpatterns = [
    path("", include("storefront.urls")),
]

# Добавляем обработку медиа-файлов для разработки и продакшена
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Для продакшена на PythonAnywhere
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)