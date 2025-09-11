"""
Middleware для эффективного кеширования медиа файлов
"""

import os
from django.http import HttpResponse
from django.conf import settings
from .cache_headers import get_media_cache_headers


class MediaCacheMiddleware:
    """
    Middleware для добавления заголовков кеширования к медиа файлам
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Проверяем, является ли запрос к медиа файлу
        if request.path.startswith(settings.MEDIA_URL):
            try:
                # Получаем путь к файлу
                media_path = request.path[len(settings.MEDIA_URL):]
                full_path = os.path.join(settings.MEDIA_ROOT, media_path)
                
                if os.path.exists(full_path):
                    # Добавляем заголовки кеширования
                    cache_headers = get_media_cache_headers(full_path)
                    for header, value in cache_headers.items():
                        response[header] = value
                    
                    # Добавляем заголовки для оптимизации
                    response['Vary'] = 'Accept-Encoding'
                    response['X-Content-Type-Options'] = 'nosniff'
                    
            except Exception:
                # В случае ошибки просто пропускаем
                pass
        
        return response
