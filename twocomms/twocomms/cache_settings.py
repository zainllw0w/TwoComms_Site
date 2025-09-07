"""
Настройки кэширования для оптимизации производительности
"""

import os
from django.core.cache.backends.redis import RedisCache
from django.core.cache.backends.locmem import LocMemCache

# Настройки кэширования
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'KEY_PREFIX': 'twocomms',
        'TIMEOUT': 300,  # 5 минут по умолчанию
        'VERSION': 1,
    },
    'sessions': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'twocomms_sessions',
        'TIMEOUT': 86400,  # 24 часа
    },
    'static': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/3'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'twocomms_static',
        'TIMEOUT': 86400,  # 24 часа
    },
    'database': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/4'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'twocomms_db',
        'TIMEOUT': 600,  # 10 минут
    }
}

# Fallback для локальной разработки
if not os.environ.get('REDIS_URL'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
            'OPTIONS': {
                'MAX_ENTRIES': 1000,
                'CULL_FREQUENCY': 3,
            },
            'TIMEOUT': 300,
        },
        'sessions': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'sessions-cache',
            'OPTIONS': {
                'MAX_ENTRIES': 500,
                'CULL_FREQUENCY': 3,
            },
            'TIMEOUT': 86400,
        },
        'static': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'static-cache',
            'OPTIONS': {
                'MAX_ENTRIES': 200,
                'CULL_FREQUENCY': 3,
            },
            'TIMEOUT': 86400,
        },
        'database': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'database-cache',
            'OPTIONS': {
                'MAX_ENTRIES': 300,
                'CULL_FREQUENCY': 3,
            },
            'TIMEOUT': 600,
        }
    }

# Настройки сессий
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'sessions'
SESSION_COOKIE_AGE = 86400  # 24 часа
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Настройки кэширования шаблонов
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "twocomms_django_theme" / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'storefront.context_processors.orders_processing_count',
            ],
            'loaders': [
                ('django.template.loaders.cached.Loader', [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                ]),
            ],
        },
    },
]

# Настройки кэширования статических файлов
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Настройки сжатия
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.rCSSMinFilter',
]
COMPRESS_JS_FILTERS = [
    'compressor.filters.jsmin.rJSMinFilter',
]
COMPRESS_CSS_HASHING_METHOD = 'content'
COMPRESS_JS_HASHING_METHOD = 'content'

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
