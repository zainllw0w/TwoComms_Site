"""
Настройки производительности для тестирования
"""

from .settings import *
from .performance_settings import *

# Настройки для тестирования
DEBUG = False

# Настройки кэширования для тестирования
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 100,
            'CULL_FREQUENCY': 3,
        },
        'TIMEOUT': 300,
    }
}

# Настройки сессий для тестирования
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 часа
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Настройки кэширования шаблонов для тестирования
TEMPLATES[0]['APP_DIRS'] = True  # Для тестирования используем стандартные загрузчики

# Настройки сжатия статических файлов для тестирования
COMPRESS_ENABLED = False  # Отключаем сжатие для тестирования
COMPRESS_OFFLINE = False

# Настройки производительности базы данных для тестирования
if 'default' in DATABASES:
    DATABASES['default']['CONN_MAX_AGE'] = 0  # Отключаем пул соединений для тестирования

# Настройки логирования для тестирования
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
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': 'testing.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'storefront': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
    },
}
