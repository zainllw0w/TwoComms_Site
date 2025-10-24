"""
Утилиты для работы с кешем, абстрагируют получение alias-ов Redis.
"""
from django.core.cache import cache, caches
from django.core.cache.backends.base import InvalidCacheBackendError


def get_cache(alias='default'):
    """
    Возвращает кэш по алиасу, подстраховываясь fallback-ом на default.
    """
    if alias in ('default', None):
        return cache
    try:
        return caches[alias]
    except InvalidCacheBackendError:
        return cache


def get_fragment_cache():
    """
    Кэш для фрагментов (Redis alias 'fragments'), резервируется на default.
    """
    return get_cache('fragments')
