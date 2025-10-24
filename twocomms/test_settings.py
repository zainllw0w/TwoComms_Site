"""
Django Test Settings для запуска тестов с SQLite вместо MySQL.

Использование:
    python manage.py test --settings=test_settings
    coverage run --source=storefront manage.py test --settings=test_settings
"""

from twocomms.settings import *

# Используем SQLite для тестов (быстрее и не требует MySQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # Хранить БД в памяти для скорости
    }
}

# Отключаем миграции для ускорения тестов (не обязательно)
# class DisableMigrations:
#     def __contains__(self, item):
#         return True
#     def __getitem__(self, item):
#         return None
# MIGRATION_MODULES = DisableMigrations()

# Отключаем DEBUG в тестах
DEBUG = False

# Простой пароль хэшер для ускорения тестов
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Отключаем кэширование в тестах
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Минимальное логирование
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'ERROR',
    },
}

# Отключаем CSRF для тестов
CSRF_USE_SESSIONS = False

