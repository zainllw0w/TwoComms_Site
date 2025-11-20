"""
Production settings for TwoComms project on PythonAnywhere.
"""

from pathlib import Path
import os
try:
    from dotenv import load_dotenv
except Exception:
    # Если python-dotenv не установлен в окружении — тихо пропускаем
    def load_dotenv(*args, **kwargs):
        return False

# Загрузим переменные окружения из файла репозитория ДО импортирования базовых настроек.
# Приоритет: DJANGO_ENV_FILE -> .env.production -> .env
BASE_DIR = Path(__file__).resolve().parent.parent
_explicit_env_file = os.environ.get('DJANGO_ENV_FILE')
if _explicit_env_file:
    load_dotenv(_explicit_env_file)

from .settings import *

# Возможность отключить аналитическую мидлварь через переменную окружения
if os.environ.get('DISABLE_ANALYTICS', 'false').lower() in ('1', 'true', 'yes'):
    MIDDLEWARE = [m for m in MIDDLEWARE if m != "storefront.tracking.SimpleAnalyticsMiddleware"]
    # Добавляем HTTPS middleware в продакшене
    if "twocomms.middleware.ForceHTTPSMiddleware" not in MIDDLEWARE:
        MIDDLEWARE.insert(0, "twocomms.middleware.ForceHTTPSMiddleware")
    if "twocomms.middleware.WWWRedirectMiddleware" not in MIDDLEWARE:
        MIDDLEWARE.insert(1, "twocomms.middleware.WWWRedirectMiddleware")

# Добавляем middleware для кеширования медиа файлов
if "twocomms.media_cache_middleware.MediaCacheMiddleware" not in MIDDLEWARE:
    MIDDLEWARE.append("twocomms.media_cache_middleware.MediaCacheMiddleware")
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
        # Принудительно добавляем www-версию для основного домена
        if 'twocomms.shop' in ALLOWED_HOSTS and 'www.twocomms.shop' not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append('www.twocomms.shop')
else:
    # Значения по умолчанию: ваш домен(ы)
    ALLOWED_HOSTS = [
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

# Принудительно добавляем www-версию в CSRF_TRUSTED_ORIGINS если есть основной домен
if 'https://twocomms.shop' in CSRF_TRUSTED_ORIGINS and 'https://www.twocomms.shop' not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.extend(['https://www.twocomms.shop'])
if 'http://twocomms.shop' in CSRF_TRUSTED_ORIGINS and 'http://www.twocomms.shop' not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.extend(['http://www.twocomms.shop'])

# Social Auth: приложения и контекст-процессоры уже подключены из base settings
if 'social_django' not in INSTALLED_APPS:
    INSTALLED_APPS.append('social_django')
if 'social_django.context_processors.backends' not in TEMPLATES[0]['OPTIONS']['context_processors']:
    TEMPLATES[0]['OPTIONS']['context_processors'].append('social_django.context_processors.backends')
if 'social_django.context_processors.login_redirect' not in TEMPLATES[0]['OPTIONS']['context_processors']:
    TEMPLATES[0]['OPTIONS']['context_processors'].append('social_django.context_processors.login_redirect')

# Telegram Bot настройки
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
TELEGRAM_ADMIN_ID = os.environ.get('TELEGRAM_ADMIN_ID', '')

# Nova Poshta API настройки
NOVA_POSHTA_API_KEY = os.environ.get('NOVA_POSHTA_API_KEY', '')

AUTHENTICATION_BACKENDS = (
    'social_core.backends.google.GoogleOAuth2',
    'django.contrib.auth.backends.ModelBackend',
)
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get('GOOGLE_CLIENT_ID', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
SOCIAL_AUTH_REDIRECT_IS_HTTPS = os.environ.get('SOCIAL_AUTH_REDIRECT_IS_HTTPS', 'True').lower() in ('1','true','yes')
SOCIAL_AUTH_URL_NAMESPACE = 'social'
SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/'
SOCIAL_AUTH_LOGIN_ERROR_URL = '/login/'

# Pipeline для обработки данных из Google
SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'storefront.social_pipeline.require_email',
    'social_core.pipeline.social_auth.associate_by_email',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
    'storefront.social_pipeline.get_avatar_url',
    'storefront.social_pipeline.create_or_update_profile',
)

# Дополнительные настройки для Google OAuth
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
]

# Логирование наследуем из базовых настроек и используем ротацию файлов

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
        # Включаем строгий режим MariaDB/MySQL: задаём через отдельный параметр
        _sql_mode = os.environ.get('DB_SQL_MODE')
        if _sql_mode:
            _options['sql_mode'] = _sql_mode
        else:
            _options['sql_mode'] = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION'
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

# Кэширование: Redis для продакшена
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
REDIS_DB = os.environ.get('REDIS_DB', '0')
REDIS_STATIC_DB = os.environ.get('REDIS_STATIC_DB', '1')
REDIS_FRAGMENT_DB = os.environ.get('REDIS_FRAGMENT_DB', '2')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', '')
REDIS_USE_SSL = os.environ.get('REDIS_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
REDIS_SCHEME = 'rediss' if REDIS_USE_SSL else 'redis'
REDIS_CACHE_URL = os.environ.get('REDIS_CACHE_URL')
REDIS_STATIC_URL = os.environ.get('REDIS_STATIC_URL')
REDIS_FRAGMENT_URL = os.environ.get('REDIS_FRAGMENT_URL')
REDIS_MAX_CONNECTIONS = int(os.environ.get('REDIS_MAX_CONNECTIONS', '100'))
REDIS_FRAGMENT_MAX_CONNECTIONS = int(os.environ.get('REDIS_FRAGMENT_MAX_CONNECTIONS', '40'))


def _build_redis_location(db_name: str, explicit_url: str | None = None) -> str:
    """
    Собирает Redis URI, учитывая пароль и протокол.
    При переданном explicit_url возвращает его (используется для кастомных URL).
    """
    if explicit_url:
        return explicit_url
    auth_part = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ''
    return f"{REDIS_SCHEME}://{auth_part}{REDIS_HOST}:{REDIS_PORT}/{db_name}"


COMMON_REDIS_OPTIONS = {
    'CLIENT_CLASS': 'django_redis.client.HerdClient',
    'SERIALIZER': 'django_redis.serializers.pickle.PickleSerializer',
    'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
    'COMPRESS_MIN_LEN': 1024,
    'IGNORE_EXCEPTIONS': True,  # Не падаем, если Redis недоступен
    'SOCKET_CONNECT_TIMEOUT': 5,
    'SOCKET_TIMEOUT': 5,
    'SOCKET_KEEPALIVE': True,
    'HEALTH_CHECK_INTERVAL': 30,
    'PICKLE_VERSION': -1,
}


CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': _build_redis_location(REDIS_DB, REDIS_CACHE_URL),
        'OPTIONS': {
            **COMMON_REDIS_OPTIONS,
            'PASSWORD': REDIS_PASSWORD or None,
            'CONNECTION_POOL_KWARGS': {
                'max_connections': REDIS_MAX_CONNECTIONS,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'twocomms',
        'TIMEOUT': int(os.environ.get('CACHE_DEFAULT_TIMEOUT', '600')),
    },
    'staticfiles': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': _build_redis_location(REDIS_STATIC_DB, REDIS_STATIC_URL),
        'OPTIONS': {
            **COMMON_REDIS_OPTIONS,
            'PASSWORD': REDIS_PASSWORD or None,
            'CONNECTION_POOL_KWARGS': {
                'max_connections': max(REDIS_FRAGMENT_MAX_CONNECTIONS // 2, 10),
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'staticfiles',
        'TIMEOUT': int(os.environ.get('CACHE_STATIC_TIMEOUT', str(60 * 60 * 24))),  # 24 часа
    },
    'fragments': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': _build_redis_location(REDIS_FRAGMENT_DB, REDIS_FRAGMENT_URL),
        'OPTIONS': {
            **COMMON_REDIS_OPTIONS,
            'PASSWORD': REDIS_PASSWORD or None,
            'CONNECTION_POOL_KWARGS': {
                'max_connections': REDIS_FRAGMENT_MAX_CONNECTIONS,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'twocomms:frag',
        'TIMEOUT': int(os.environ.get('CACHE_FRAGMENT_TIMEOUT', '900')),  # 15 минут
    },
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'

# Кэширование шаблонов (включено для продакшена)
TEMPLATES[0]['OPTIONS']['loaders'] = [
    ('django.template.loaders.cached.Loader', [
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    ]),
]
TEMPLATES[0]['APP_DIRS'] = False  # Отключаем APP_DIRS при использовании loaders

# Настройки сжатия статических файлов
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
]

# WhiteNoise: включаем сжатие и манифест с агрессивным кешированием
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_MAX_AGE = int(os.environ.get('WHITENOISE_MAX_AGE', str(60*60*24*365)))  # 1 год для статических файлов
WHITENOISE_IMMUTABLE_FILE_TEST = lambda path, url: True

# Дополнительные настройки WhiteNoise для лучшего кеширования
WHITENOISE_USE_FINDERS = True

# Эффективные настройки кеширования для разных типов ресурсов
WHITENOISE_ADD_HEADERS_FUNCTION = 'twocomms.cache_headers.add_cache_headers'

# Настройки кеширования для медиа файлов
MEDIA_CACHE_MAX_AGE = 60 * 60 * 24 * 30  # 30 дней для медиа файлов
WHITENOISE_AUTOREFRESH = False  # Отключаем автообновление в продакшене
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'ico', 'woff', 'woff2', 'ttf', 'eot']

# Настройки кеширования статических файлов
def add_cache_headers(headers, path, url):
    """Добавляет заголовки кеширования для статических файлов"""
    if any(path.endswith(ext) for ext in ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot']):
        headers['Cache-Control'] = 'public, max-age=15552000, immutable'  # 180 дней
        headers['Vary'] = 'Accept-Encoding'

WHITENOISE_ADD_HEADERS_FUNCTION = add_cache_headers

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
COMPRESS_OFFLINE = _ensure_compress_offline(COMPRESS_OFFLINE)

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
    BASE_DIR / "static",
]

# Настройки безопасности
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Отключаем COOP/COEP в продакшене, чтобы не блокировать сторонние виджеты/пиксели
SECURE_CROSS_ORIGIN_OPENER_POLICY = None
SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = None

# Принудительный HTTPS и доверие заголовку прокси
# Разрешим переключать редирект через переменную окружения, чтобы избежать возможных циклов редиректа
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in ('1', 'true', 'yes')
SECURE_REDIRECT_EXEMPT = []  # Принудительный редирект для всех URL
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMАINS = True
SECURE_HSTS_PRELOAD = True

# Куки
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_HTTPONLY = True

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
