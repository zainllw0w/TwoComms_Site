"""
Views для эффективного кеширования API ответов
"""

import functools


def cache_api_response(timeout=300):
    """
    Декоратор для кеширования API ответов
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Добавляем заголовки кеширования
            response = view_func(request, *args, **kwargs)
            response['Cache-Control'] = f'public, max-age={timeout}'
            response['ETag'] = f'"{hash(str(response.content))}"'
            response['Vary'] = 'Accept-Encoding'
            return response
        return wrapper
    return decorator


def cache_static_content(timeout=86400):
    """
    Декоратор для кеширования статического контента
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            response['Cache-Control'] = f'public, max-age={timeout}, immutable'
            response['ETag'] = f'"{hash(str(response.content))}"'
            response['Vary'] = 'Accept-Encoding'
            return response
        return wrapper
    return decorator


def cache_dynamic_content(timeout=3600):
    """
    Декоратор для кеширования динамического контента
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            response['Cache-Control'] = f'public, max-age={timeout}'
            response['ETag'] = f'"{hash(str(response.content))}"'
            response['Vary'] = 'Accept-Encoding, Accept-Language'
            return response
        return wrapper
    return decorator
