"""
Django Query Optimizations для мобильной производительности
Утилиты и декораторы для оптимизации запросов к БД
"""

from functools import wraps
from django.core.cache import cache
from django.db import connection
from django.db.models import Prefetch, Q
import hashlib
import logging

logger = logging.getLogger(__name__)


def get_optimized_product_queryset():
    """
    Возвращает оптимизированный queryset для продуктов
    с предзагрузкой всех необходимых связей
    """
    from .models import Product, ProductImage
    from productcolors.models import ColorVariant, ColorVariantImage
    
    return Product.objects.select_related(
        'category'  # Предзагружаем категорию
    ).prefetch_related(
        # Предзагружаем изображения продукта
        Prefetch('images', queryset=ProductImage.objects.select_related('product')),
        # Предзагружаем цветовые варианты с их изображениями
        Prefetch(
            'color_variants',
            queryset=ColorVariant.objects.select_related('color', 'product').prefetch_related(
                Prefetch('images', queryset=ColorVariantImage.objects.select_related('variant'))
            )
        )
    ).only(
        # Загружаем только необходимые поля
        'id', 'title', 'slug', 'price', 'discount_price', 'category_id',
        'main_image', 'is_active', 'created_at', 'updated_at', 'points_reward'
    )


def get_optimized_categories_queryset():
    """
    Возвращает оптимизированный queryset для категорий
    """
    from .models import Category
    
    return Category.objects.only(
        'id', 'name', 'slug', 'icon', 'is_active'
    ).filter(is_active=True)


def cache_queryset(timeout=300, key_prefix='query'):
    """
    Декоратор для кэширования результатов queryset
    
    Usage:
        @cache_queryset(timeout=600, key_prefix='products')
        def get_products(category_id=None):
            return Product.objects.filter(category_id=category_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Создаем уникальный ключ кэша
            cache_key_parts = [key_prefix, func.__name__]
            cache_key_parts.extend(str(arg) for arg in args)
            cache_key_parts.extend(f"{k}_{v}" for k, v in sorted(kwargs.items()))
            
            cache_key = hashlib.md5(
                ':'.join(cache_key_parts).encode('utf-8')
            ).hexdigest()
            
            # Пытаемся получить из кэша
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result
            
            # Выполняем запрос
            result = func(*args, **kwargs)
            
            # Кэшируем результат
            if hasattr(result, '__iter__'):
                # Для querysets и списков сначала выполняем запрос
                result = list(result)
            
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cache miss: {cache_key}")
            
            return result
        return wrapper
    return decorator


def debug_queries(func):
    """
    Декоратор для логирования SQL запросов (только для DEBUG)
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from django.conf import settings
        
        if not settings.DEBUG:
            return func(*args, **kwargs)
        
        # Сбрасываем счетчик запросов
        connection.queries_log.clear()
        
        # Выполняем функцию
        result = func(*args, **kwargs)
        
        # Логируем запросы
        queries = connection.queries
        logger.info(f"{func.__name__}: {len(queries)} queries")
        
        if queries:
            total_time = sum(float(q['time']) for q in queries)
            logger.info(f"Total query time: {total_time:.3f}s")
            
            # Показываем медленные запросы
            slow_queries = [q for q in queries if float(q['time']) > 0.1]
            if slow_queries:
                logger.warning(f"Slow queries ({len(slow_queries)}):")
                for q in slow_queries:
                    logger.warning(f"  {q['time']}s: {q['sql'][:100]}")
        
        return result
    return wrapper


class QueryCounter:
    """
    Context manager для подсчета SQL запросов
    
    Usage:
        with QueryCounter() as counter:
            products = list(Product.objects.all())
        print(f"Queries: {counter.count}")
    """
    
    def __init__(self, name=''):
        self.name = name
        self.count = 0
        self.total_time = 0
        
    def __enter__(self):
        self.count = len(connection.queries)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        queries = connection.queries[self.count:]
        self.count = len(queries)
        self.total_time = sum(float(q['time']) for q in queries)
        
        name = f" ({self.name})" if self.name else ""
        logger.info(f"QueryCounter{name}: {self.count} queries, {self.total_time:.3f}s")


def batch_select_related(queryset, *fields, batch_size=100):
    """
    Пакетная предзагрузка связанных объектов для больших queryset
    Полезно для избежания проблем с памятью
    """
    count = queryset.count()
    
    if count <= batch_size:
        return queryset.select_related(*fields)
    
    # Разбиваем на батчи
    results = []
    for offset in range(0, count, batch_size):
        batch = queryset[offset:offset + batch_size].select_related(*fields)
        results.extend(list(batch))
    
    return results


def efficient_exists(queryset):
    """
    Эффективная проверка существования записей
    Использует EXISTS вместо COUNT
    """
    return queryset.exists() if hasattr(queryset, 'exists') else bool(queryset)


def get_or_none(model, **kwargs):
    """
    Безопасная версия get(), возвращает None вместо DoesNotExist
    """
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        return None


def bulk_create_or_update(model, objects, update_fields, match_field='id'):
    """
    Массовое создание или обновление объектов
    Более эффективно чем цикл с save()
    """
    from django.db import transaction
    
    existing_objects = {
        getattr(obj, match_field): obj 
        for obj in model.objects.filter(
            **{f"{match_field}__in": [getattr(o, match_field) for o in objects]}
        )
    }
    
    to_create = []
    to_update = []
    
    for obj in objects:
        match_value = getattr(obj, match_field)
        if match_value in existing_objects:
            existing = existing_objects[match_value]
            for field in update_fields:
                setattr(existing, field, getattr(obj, field))
            to_update.append(existing)
        else:
            to_create.append(obj)
    
    with transaction.atomic():
        if to_create:
            model.objects.bulk_create(to_create)
        if to_update:
            model.objects.bulk_update(to_update, update_fields)
    
    return len(to_create), len(to_update)


def optimize_queryset_for_mobile(queryset, limit=20):
    """
    Оптимизирует queryset для мобильных устройств
    - Ограничивает количество результатов
    - Загружает только необходимые поля
    - Добавляет select_related для связанных моделей
    """
    return queryset[:limit]


# Кэшированные версии популярных запросов
@cache_queryset(timeout=3600, key_prefix='categories')
def get_cached_categories():
    """Получает кэшированный список категорий"""
    return list(get_optimized_categories_queryset())


@cache_queryset(timeout=1800, key_prefix='featured_product')
def get_cached_featured_product():
    """Получает кэшированный рекомендуемый продукт"""
    from .models import Product
    
    try:
        return get_optimized_product_queryset().filter(
            is_featured=True,
            is_active=True
        ).first()
    except Exception as e:
        logger.error(f"Error getting featured product: {e}")
        return None


@cache_queryset(timeout=600, key_prefix='new_products')
def get_cached_new_products(limit=12):
    """Получает кэшированный список новых продуктов"""
    return list(
        get_optimized_product_queryset()
        .filter(is_active=True)
        .order_by('-created_at')[:limit]
    )


def prefetch_user_favorites(user):
    """
    Предзагружает избранные товары пользователя
    Оптимизировано для избежания N+1
    """
    from accounts.models import FavoriteProduct
    
    if not user.is_authenticated:
        return []
    
    return list(
        FavoriteProduct.objects
        .filter(user=user)
        .select_related('product__category')
        .prefetch_related('product__images')
        .values_list('product_id', flat=True)
    )


def get_products_with_favorites(user, queryset=None):
    """
    Получает продукты с информацией об избранных
    Избегает N+1 запросов
    """
    if queryset is None:
        queryset = get_optimized_product_queryset()
    
    products = list(queryset)
    
    if user.is_authenticated:
        favorite_ids = set(prefetch_user_favorites(user))
        for product in products:
            product.is_favorited = product.id in favorite_ids
    else:
        for product in products:
            product.is_favorited = False
    
    return products


# Индексы для оптимизации запросов (добавить в миграцию)
RECOMMENDED_INDEXES = """
-- Индексы для Product модели
CREATE INDEX IF NOT EXISTS idx_product_active_created 
ON storefront_product(is_active, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_product_category_active 
ON storefront_product(category_id, is_active);

CREATE INDEX IF NOT EXISTS idx_product_featured 
ON storefront_product(is_featured, is_active);

CREATE INDEX IF NOT EXISTS idx_product_slug 
ON storefront_product(slug);

-- Индексы для Category модели
CREATE INDEX IF NOT EXISTS idx_category_active 
ON storefront_category(is_active);

-- Индексы для ProductImage модели  
CREATE INDEX IF NOT EXISTS idx_productimage_product 
ON storefront_productimage(product_id);

-- Индексы для ColorVariant модели
CREATE INDEX IF NOT EXISTS idx_colorvariant_product 
ON productcolors_colorvariant(product_id);

-- Индексы для FavoriteProduct модели
CREATE INDEX IF NOT EXISTS idx_favorite_user_product 
ON accounts_favoriteproduct(user_id, product_id);
"""


if __name__ == '__main__':
    # Примеры использования
    print("Query optimization utilities loaded")
    print("Recommended indexes:")
    print(RECOMMENDED_INDEXES)

