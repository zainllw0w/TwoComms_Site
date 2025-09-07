"""
Настройки производительности для разработки
"""

from .settings import *
from .performance_settings import *

# Настройки для разработки
DEBUG = True

# Настройки кэширования для разработки
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 500,
            'CULL_FREQUENCY': 3,
        },
        'TIMEOUT': 300,
    }
}

# Настройки сессий для разработки
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 часа
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Настройки кэширования шаблонов для разработки
TEMPLATES[0]['APP_DIRS'] = True  # Для разработки используем стандартные загрузчики

# Настройки сжатия статических файлов для разработки
COMPRESS_ENABLED = False  # Отключаем сжатие для разработки
COMPRESS_OFFLINE = False

# Настройки производительности базы данных для разработки
if 'default' in DATABASES:
    DATABASES['default']['CONN_MAX_AGE'] = 0  # Отключаем пул соединений для разработки

# Настройки логирования для разработки
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'development.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'storefront': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
