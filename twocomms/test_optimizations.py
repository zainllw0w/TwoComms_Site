#!/usr/bin/env python
"""
Скрипт для тестирования оптимизаций производительности
"""

import os
import sys
import django
from django.conf import settings

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

def test_optimizations():
    """Тестирование оптимизаций"""
    print("=== Тестирование оптимизаций производительности ===")
    
    # Тест 1: Проверка доступности оптимизаций
    try:
        from storefront.cache_manager import CacheManager
        from storefront.query_optimizer import QueryOptimizer
        from storefront.models_performance import ProductManager, CategoryManager
        print("✓ Оптимизированные модули загружены успешно")
    except ImportError as e:
        print(f"✗ Ошибка загрузки оптимизаций: {e}")
        return False
    
    # Тест 2: Тестирование кэширования
    try:
        from django.core.cache import cache
        cache.set('test_key', 'test_value', 30)
        value = cache.get('test_key')
        if value == 'test_value':
            print("✓ Кэширование работает корректно")
        else:
            print("✗ Ошибка кэширования")
            return False
    except Exception as e:
        print(f"✗ Ошибка тестирования кэша: {e}")
        return False
    
    # Тест 3: Тестирование оптимизированных запросов
    try:
        from storefront.models import Product, Category
        from storefront.query_optimizer import QueryOptimizer
        
        # Тест получения товаров
        products = QueryOptimizer.get_optimized_products_list(5)
        print(f"✓ Оптимизированный запрос товаров: получено {len(products)} товаров")
        
        # Тест получения категорий
        categories = QueryOptimizer.get_optimized_categories()
        print(f"✓ Оптимизированный запрос категорий: получено {len(categories)} категорий")
        
        # Тест получения статистики
        stats = QueryOptimizer.get_optimized_orders_stats()
        print(f"✓ Оптимизированный запрос статистики: получено {len(stats)} метрик")
        
    except Exception as e:
        print(f"✗ Ошибка тестирования оптимизированных запросов: {e}")
        return False
    
    # Тест 4: Тестирование кэш-менеджера
    try:
        from storefront.cache_manager import CacheManager
        
        # Тест кэширования данных главной страницы
        home_data = CacheManager.get_cached_home_data()
        print(f"✓ Кэширование данных главной страницы: {len(home_data)} элементов")
        
        # Тест кэширования количества товаров
        products_count = CacheManager.get_products_count_cached()
        print(f"✓ Кэширование количества товаров: {products_count}")
        
        # Тест кэширования статистики заказов
        orders_stats = CacheManager.get_orders_stats_cached()
        print(f"✓ Кэширование статистики заказов: {len(orders_stats)} метрик")
        
    except Exception as e:
        print(f"✗ Ошибка тестирования кэш-менеджера: {e}")
        return False
    
    print("\n=== Все тесты пройдены успешно! ===")
    return True

def test_performance():
    """Тестирование производительности"""
    print("\n=== Тестирование производительности ===")
    
    import time
    from storefront.models import Product, Category
    from storefront.query_optimizer import QueryOptimizer
    
    # Тест производительности обычных запросов
    start_time = time.time()
    products_normal = list(Product.objects.select_related('category').order_by('-id')[:10])
    normal_time = time.time() - start_time
    
    # Тест производительности оптимизированных запросов
    start_time = time.time()
    products_optimized = QueryOptimizer.get_optimized_products_list(10)
    optimized_time = time.time() - start_time
    
    print(f"Обычные запросы: {normal_time:.4f} секунд")
    print(f"Оптимизированные запросы: {optimized_time:.4f} секунд")
    
    if optimized_time < normal_time:
        improvement = ((normal_time - optimized_time) / normal_time) * 100
        print(f"✓ Улучшение производительности: {improvement:.1f}%")
    else:
        print("⚠ Оптимизированные запросы не показали улучшения")
    
    return True

if __name__ == '__main__':
    success = test_optimizations()
    if success:
        test_performance()
    else:
        print("Тестирование завершено с ошибками")
        sys.exit(1)
