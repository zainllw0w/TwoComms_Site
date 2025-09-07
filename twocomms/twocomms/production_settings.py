"""
Production settings for TwoComms project on PythonAnywhere.
"""

from .settings import *
import os
import pymysql

# Настройка PyMySQL для работы с MySQL
pymysql.install_as_MySQLdb()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# SECURITY WARNING: keep the secret key used in production secret!
# В продакшене используйте переменную окружения
import os
SECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)

# ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS читаем из переменных окружения
# ALLOWED_HOSTS="*" допустимо (только временно на время настройки!)
_allowed_hosts_env = os.environ.get('ALLOWED_HOSTS')
if _allowed_hosts_env:
    _allowed_hosts_env = _allowed_hosts_env.strip()
    if _allowed_hosts_env == '*':
        ALLOWED_HOSTS = ['*']
    else:
        ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]
else:
    # Значения по умолчанию: pythonanywhere и ваш домен
    ALLOWED_HOSTS = [
        'twocomms.pythonanywhere.com',
        'twocomms.shop',
        'www.twocomms.shop',
        'test.com',
        'www.test.com',
        'localhost',
        '127.0.0.1',
        'testserver',  # Для Django тестового клиента
    ]

_csrf_origins_env = os.environ.get('CSRF_TRUSTED_ORIGINS')
if _csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins_env.split(',') if o.strip()]
else:
    # Если явно не задано, формируем из ALLOWED_HOSTS (для доменных имён)
    CSRF_TRUSTED_ORIGINS = []
    for h in ALLOWED_HOSTS:
        if h not in ('localhost', '127.0.0.1') and not h.startswith('*'):
            CSRF_TRUSTED_ORIGINS.extend([f"http://{h}", f"https://{h}"])

# База данных: выбираем по DB_ENGINE (mysql | postgresql), иначе SQLite как фолбэк
DB_ENGINE = os.environ.get('DB_ENGINE', '').lower()
if os.environ.get('DB_NAME') and os.environ.get('DB_USER'):
    if DB_ENGINE.startswith('mysql'):
        # Базовые опции подключения к MySQL
        _options = {
            'charset': 'utf8mb4',
            'use_unicode': True,
            'init_command': "SET NAMES 'utf8mb4' COLLATE 'utf8mb4_unicode_ci'",
        }

        # Поддержка SSL через переменные окружения (опционально)
        _ssl = {}
        if os.environ.get('DB_SSL_CA'):
            _ssl['ca'] = os.environ['DB_SSL_CA']
        if os.environ.get('DB_SSL_CERT'):
            _ssl['cert'] = os.environ['DB_SSL_CERT']
        if os.environ.get('DB_SSL_KEY'):
            _ssl['key'] = os.environ['DB_SSL_KEY']
        if _ssl:
            _options['ssl'] = _ssl

        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': os.environ['DB_NAME'],
                'USER': os.environ['DB_USER'],
                'PASSWORD': os.environ.get('DB_PASSWORD', ''),
                'HOST': os.environ.get('DB_HOST', 'localhost'),
                'PORT': os.environ.get('DB_PORT', '3306'),
                'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '60')),
                'OPTIONS': _options,
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': os.environ['DB_NAME'],
                'USER': os.environ['DB_USER'],
                'PASSWORD': os.environ.get('DB_PASSWORD', ''),
                'HOST': os.environ.get('DB_HOST', 'localhost'),
                'PORT': os.environ.get('DB_PORT', '5432'),
                'CONN_MAX_AGE': 60,
                'OPTIONS': {
                    'sslmode': os.environ.get('DB_SSLMODE', 'require')
                }
            }
        }

# Настройки статических файлов для продакшена
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Настройки медиа файлов
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ===== ОПТИМИЗАЦИИ ДЛЯ ПРОДАКШЕНА =====

# Кэширование
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 300,  # 5 минут
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    }
}

# Кэширование сессий
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'

# Кэширование шаблонов
TEMPLATES[0]['OPTIONS']['loaders'] = [
    ('django.template.loaders.cached.Loader', [
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    ]),
]
TEMPLATES[0]['APP_DIRS'] = False

# Настройки сжатия статических файлов
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
]

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

# Настройки для правильной работы медиа-файлов на PythonAnywhere
MEDIAFILES_DIRS = [
    BASE_DIR / 'media',
]

# Настройки для загрузки файлов
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# Убедимся, что STATICFILES_DIRS настроен правильно
STATICFILES_DIRS = [
    BASE_DIR / "twocomms_django_theme" / "static",
]

# Настройки безопасности
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Настройки сессий (временно смягчены для диагностики)
SESSION_COOKIE_SECURE = False  # Временно отключено для диагностики
CSRF_COOKIE_SECURE = False     # Временно отключено для диагностики

# Дополнительные настройки безопасности для HTTPS (временно отключены)
SECURE_SSL_REDIRECT = False    # Временно отключено для диагностики
# SECURE_HSTS_SECONDS = 31536000 # Временно отключено
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True # Временно отключено
# SECURE_HSTS_PRELOAD = True # Временно отключено
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') # Временно отключено

# Настройки логирования
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Sites framework
SITE_ID = 1

# URL для входа в систему
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Настройки для отправки email (опционально)
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-email@gmail.com'
# EMAIL_HOST_PASSWORD = 'your-app-password'
