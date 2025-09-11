"""
Декораторы для эффективного кеширования
"""
import hashlib
import json
import functools
from django.core.cache import caches
from django.conf import settings


def cache_page(timeout=300, cache_alias='default', key_prefix=''):
    """
    Декоратор для кеширования страниц
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            cache = caches[cache_alias]
            
            # Генерируем ключ кеша
            cache_key = _generate_page_cache_key(
                request, view_func.__name__, key_prefix, *args, **kwargs
            )
            
            # Проверяем кеш
            cached_response = cache.get(cache_key)
            if cached_response:
                return cached_response
            
            # Выполняем view и кешируем результат
            response = view_func(request, *args, **kwargs)
            if response.status_code == 200:
                cache.set(cache_key, response, timeout)
            
            return response
        return wrapper
    return decorator


def cache_api(timeout=600, cache_alias='api', key_prefix=''):
    """
    Декоратор для кеширования API запросов
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            cache = caches[cache_alias]
            
            # Генерируем ключ кеша
            cache_key = _generate_api_cache_key(
                request, view_func.__name__, key_prefix, *args, **kwargs
            )
            
            # Проверяем кеш
            cached_data = cache.get(cache_key)
            if cached_data:
                from django.http import JsonResponse
                return JsonResponse(cached_data)
            
            # Выполняем view и кешируем результат
            response = view_func(request, *args, **kwargs)
            if response.status_code == 200:
                try:
                    data = json.loads(response.content)
                    cache.set(cache_key, data, timeout)
                except (json.JSONDecodeError, AttributeError):
                    pass  # Не кешируем если не JSON
            
            return response
        return wrapper
    return decorator


def cache_database_query(timeout=1800, cache_alias='database', key_prefix=''):
    """
    Декоратор для кеширования результатов запросов к БД
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = caches[cache_alias]
            
            # Генерируем ключ кеша
            cache_key = _generate_db_cache_key(
                func.__name__, key_prefix, *args, **kwargs
            )
            
            # Проверяем кеш
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Выполняем функцию и кешируем результат
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def cache_template_fragment(timeout=3600, cache_alias='templates', key_prefix=''):
    """
    Декоратор для кеширования фрагментов шаблонов
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = caches[cache_alias]
            
            # Генерируем ключ кеша
            cache_key = _generate_template_cache_key(
                func.__name__, key_prefix, *args, **kwargs
            )
            
            # Проверяем кеш
            cached_content = cache.get(cache_key)
            if cached_content:
                return cached_content
            
            # Выполняем функцию и кешируем результат
            content = func(*args, **kwargs)
            cache.set(cache_key, content, timeout)
            
            return content
        return wrapper
    return decorator


def _generate_page_cache_key(request, view_name, key_prefix, *args, **kwargs):
    """Генерация ключа кеша для страниц"""
    key_data = {
        'view': view_name,
        'path': request.path,
        'query': request.GET.urlencode(),
        'language': getattr(request, 'LANGUAGE_CODE', 'en'),
        'user_authenticated': request.user.is_authenticated,
        'args': str(args),
        'kwargs': str(kwargs),
        'prefix': key_prefix,
        'version': getattr(settings, 'CACHE_VERSION', '1.0'),
    }
    
    key_string = json.dumps(key_data, sort_keys=True)
    return f"page:{hashlib.md5(key_string.encode()).hexdigest()}"


def _generate_api_cache_key(request, view_name, key_prefix, *args, **kwargs):
    """Генерация ключа кеша для API"""
    key_data = {
        'api': view_name,
        'path': request.path,
        'method': request.method,
        'query': request.GET.urlencode(),
        'body': request.body.decode('utf-8', errors='ignore')[:100],
        'args': str(args),
        'kwargs': str(kwargs),
        'prefix': key_prefix,
        'version': getattr(settings, 'CACHE_VERSION', '1.0'),
    }
    
    key_string = json.dumps(key_data, sort_keys=True)
    return f"api:{hashlib.md5(key_string.encode()).hexdigest()}"


def _generate_db_cache_key(func_name, key_prefix, *args, **kwargs):
    """Генерация ключа кеша для запросов к БД"""
    key_data = {
        'function': func_name,
        'args': str(args),
        'kwargs': str(kwargs),
        'prefix': key_prefix,
        'version': getattr(settings, 'CACHE_VERSION', '1.0'),
    }
    
    key_string = json.dumps(key_data, sort_keys=True)
    return f"db:{hashlib.md5(key_string.encode()).hexdigest()}"


def _generate_template_cache_key(func_name, key_prefix, *args, **kwargs):
    """Генерация ключа кеша для шаблонов"""
    key_data = {
        'template': func_name,
        'args': str(args),
        'kwargs': str(kwargs),
        'prefix': key_prefix,
        'version': getattr(settings, 'CACHE_VERSION', '1.0'),
    }
    
    key_string = json.dumps(key_data, sort_keys=True)
    return f"template:{hashlib.md5(key_string.encode()).hexdigest()}"


# Утилиты для управления кешем
def invalidate_cache_pattern(pattern, cache_alias='default'):
    """Инвалидация кеша по паттерну"""
    cache = caches[cache_alias]
    # В LocMemCache нет возможности поиска по паттерну
    # Но можно добавить логику для других бэкендов
    pass


def clear_all_caches():
    """Очистка всех кешей"""
    for cache_name in ['default', 'staticfiles', 'templates', 'database', 'api']:
        try:
            caches[cache_name].clear()
        except Exception:
            pass


def get_cache_stats():
    """Получение статистики кеша"""
    stats = {}
    for cache_name in ['default', 'staticfiles', 'templates', 'database', 'api']:
        try:
            cache = caches[cache_name]
            # LocMemCache не предоставляет статистику
            # Но можно добавить счетчики
            stats[cache_name] = {
                'backend': cache.__class__.__name__,
                'location': getattr(cache, '_cache', {}).get('_location', 'unknown')
            }
        except Exception as e:
            stats[cache_name] = {'error': str(e)}
    
    return stats
