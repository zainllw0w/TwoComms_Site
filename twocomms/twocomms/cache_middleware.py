"""
Эффективное кеширование для TwoComms
"""
import hashlib
import json
from django.core.cache import caches
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
from django.conf import settings


class EfficientCacheMiddleware(MiddlewareMixin):
    """
    Middleware для эффективного кеширования страниц и API запросов
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.cache = caches['default']
        self.static_cache = caches['staticfiles']
        self.api_cache = caches['api']
        super().__init__(get_response)
    
    def process_request(self, request):
        """Обработка входящих запросов для кеширования"""
        
        # Кешируем только GET запросы
        if request.method != 'GET':
            return None
            
        # Исключаем админку и API
        if request.path.startswith('/admin/') or request.path.startswith('/api/'):
            return None
            
        # Создаем ключ кеша
        cache_key = self._generate_cache_key(request)
        
        # Проверяем кеш
        cached_response = self.cache.get(cache_key)
        if cached_response:
            return HttpResponse(
                cached_response['content'],
                status=cached_response['status'],
                content_type=cached_response['content_type']
            )
        
        # Сохраняем ключ для использования в process_response
        request._cache_key = cache_key
        return None
    
    def process_response(self, request, response):
        """Обработка исходящих ответов для кеширования"""
        
        # Кешируем только успешные GET запросы
        if (hasattr(request, '_cache_key') and 
            request.method == 'GET' and 
            response.status_code == 200):
            
            # Кешируем на разное время в зависимости от типа страницы
            cache_timeout = self._get_cache_timeout(request.path)
            
            cache_data = {
                'content': response.content,
                'status': response.status_code,
                'content_type': response.get('Content-Type', 'text/html')
            }
            
            self.cache.set(request._cache_key, cache_data, cache_timeout)
        
        return response
    
    def _generate_cache_key(self, request):
        """Генерация уникального ключа кеша"""
        # Учитываем путь, параметры и язык
        key_data = {
            'path': request.path,
            'query': request.GET.urlencode(),
            'language': getattr(request, 'LANGUAGE_CODE', 'en'),
            'user_authenticated': request.user.is_authenticated,
        }
        
        # Добавляем версию для инвалидации кеша
        key_data['version'] = getattr(settings, 'CACHE_VERSION', '1.0')
        
        key_string = json.dumps(key_data, sort_keys=True)
        return f"page_cache:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    def _get_cache_timeout(self, path):
        """Определение времени кеширования в зависимости от страницы"""
        if path == '/':
            return 1800  # 30 минут для главной страницы
        elif path.startswith('/catalog/'):
            return 900   # 15 минут для каталога
        elif path.startswith('/product/'):
            return 3600  # 1 час для страниц товаров
        elif path.startswith('/category/'):
            return 1800  # 30 минут для категорий
        else:
            return 600   # 10 минут для остальных страниц


class StaticFilesCacheMiddleware(MiddlewareMixin):
    """
    Middleware для кеширования статических файлов
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.cache = caches['staticfiles']
        super().__init__(get_response)
    
    def process_request(self, request):
        """Кеширование статических файлов"""
        if request.path.startswith('/static/'):
            cache_key = f"static:{request.path}"
            cached_response = self.cache.get(cache_key)
            
            if cached_response:
                return HttpResponse(
                    cached_response['content'],
                    content_type=cached_response['content_type'],
                    headers=cached_response['headers']
                )
            
            request._static_cache_key = cache_key
        return None
    
    def process_response(self, request, response):
        """Сохранение статических файлов в кеш"""
        if (hasattr(request, '_static_cache_key') and 
            response.status_code == 200):
            
            cache_data = {
                'content': response.content,
                'content_type': response.get('Content-Type', ''),
                'headers': dict(response.headers)
            }
            
            # Кешируем статические файлы на 24 часа
            self.cache.set(request._static_cache_key, cache_data, 86400)
        
        return response


class DatabaseQueryCacheMiddleware(MiddlewareMixin):
    """
    Middleware для кеширования запросов к базе данных
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.cache = caches['database']
        super().__init__(get_response)
    
    def process_request(self, request):
        """Подготовка к кешированию запросов к БД"""
        request._db_queries = []
        return None
    
    def process_response(self, request, response):
        """Кеширование результатов запросов к БД"""
        # Здесь можно добавить логику кеширования запросов к БД
        # если нужно кешировать результаты на уровне middleware
        return response
