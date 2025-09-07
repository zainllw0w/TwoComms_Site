"""
Простые настройки кэширования для оптимизации производительности
"""

import os

# Настройки кэширования
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        },
        'TIMEOUT': 300,  # 5 минут по умолчанию
    }
}

# Fallback для Redis (если доступен)
if os.environ.get('REDIS_URL'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.environ.get('REDIS_URL'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {
                    'max_connections': 50,
                    'retry_on_timeout': True,
                },
            },
            'KEY_PREFIX': 'twocomms',
            'TIMEOUT': 300,
            'VERSION': 1,
        }
    }

# Настройки сессий
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 часа
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Настройки кэширования для разных типов данных
CACHE_TIMEOUTS = {
    'home_data': 300,  # 5 минут
    'products_count': 300,  # 5 минут
    'categories_list': 600,  # 10 минут
    'orders_stats': 300,  # 5 минут
    'user_data': 180,  # 3 минуты
    'product_detail': 600,  # 10 минут
    'catalog_data': 600,  # 10 минут
    'search_results': 300,  # 5 минут
    'static_content': 86400,  # 24 часа
}

# Middleware для кэширования
CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = 'twocomms'

# Настройки для мониторинга кэша
CACHE_MONITORING = {
    'ENABLED': True,
    'LOG_HITS': True,
    'LOG_MISSES': True,
    'LOG_TIMEOUTS': True,
}
