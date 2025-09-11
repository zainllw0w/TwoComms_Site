"""
Middleware для кеширования API ответов
"""

import json
import hashlib
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings


class APICacheMiddleware(MiddlewareMixin):
    """
    Middleware для кеширования API ответов
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Проверяем кеш для GET запросов к API
        """
        if request.method == 'GET' and request.path.startswith('/api/'):
            cache_key = self.generate_cache_key(request)
            cached_response = cache.get(cache_key)
            
            if cached_response:
                return JsonResponse(cached_response)
        
        return None
    
    def process_response(self, request, response):
        """
        Кешируем успешные API ответы
        """
        if (request.method == 'GET' and 
            request.path.startswith('/api/') and 
            response.status_code == 200):
            
            try:
                # Парсим JSON ответ
                response_data = json.loads(response.content)
                
                # Определяем время кеширования в зависимости от типа API
                cache_timeout = self.get_cache_timeout(request.path)
                
                # Генерируем ключ кеша
                cache_key = self.generate_cache_key(request)
                
                # Кешируем ответ
                cache.set(cache_key, response_data, cache_timeout)
                
                # Добавляем заголовки кеширования
                response['Cache-Control'] = f'public, max-age={cache_timeout}'
                response['X-Cache-Status'] = 'MISS'
                
            except (json.JSONDecodeError, TypeError):
                # Если не JSON или ошибка, не кешируем
                pass
        
        return response
    
    def generate_cache_key(self, request):
        """
        Генерирует уникальный ключ кеша для запроса
        """
        # Получаем параметры запроса
        params = request.GET.dict()
        
        # Создаем строку для хеширования
        key_data = f"{request.path}:{json.dumps(params, sort_keys=True)}"
        
        # Генерируем MD5 хеш
        cache_key = hashlib.md5(key_data.encode()).hexdigest()
        
        return f"api_cache:{cache_key}"
    
    def get_cache_timeout(self, path):
        """
        Определяет время кеширования в зависимости от типа API
        """
        # Каталог товаров - 5 минут
        if '/api/products/' in path or '/api/catalog/' in path:
            return 300  # 5 минут
        
        # Информация о товаре - 10 минут
        elif '/api/product/' in path:
            return 600  # 10 минут
        
        # Категории - 30 минут
        elif '/api/categories/' in path:
            return 1800  # 30 минут
        
        # Пользовательские данные - 1 минута
        elif '/api/user/' in path or '/api/profile/' in path:
            return 60  # 1 минута
        
        # Корзина - 30 секунд
        elif '/api/cart/' in path:
            return 30  # 30 секунд
        
        # По умолчанию - 2 минуты
        else:
            return 120  # 2 минуты
