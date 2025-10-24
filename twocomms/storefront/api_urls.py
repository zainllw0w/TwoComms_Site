"""
Django REST Framework API URLs with Router.

Автоматически генерирует URL patterns для ViewSets.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    CategoryViewSet,
    ProductViewSet,
    CartViewSet,
    AnalyticsViewSet,
    CommunicationViewSet
)


# Создаем Router
router = DefaultRouter()

# Регистрируем ViewSets
router.register(r'categories', CategoryViewSet, basename='api-category')
router.register(r'products', ProductViewSet, basename='api-product')
router.register(r'cart', CartViewSet, basename='api-cart')
router.register(r'analytics', AnalyticsViewSet, basename='api-analytics')
router.register(r'communication', CommunicationViewSet, basename='api-communication')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]

# Автоматически созданные URLs:
# GET    /api/categories/                    - Список категорий
# GET    /api/categories/{slug}/             - Детали категории
# GET    /api/products/                      - Список товаров
# GET    /api/products/{slug}/               - Детали товара
# GET    /api/products/search/               - Поиск товаров
# GET    /api/products/by-category/{slug}/   - Товары по категории
# GET    /api/cart/                          - Содержимое корзины
# POST   /api/cart/add/                      - Добавить в корзину
# POST   /api/cart/remove/                   - Удалить из корзины
# POST   /api/cart/clear/                    - Очистить корзину

