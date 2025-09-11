"""
Дополнительные middleware для TwoComms
"""

from django.http import HttpResponsePermanentRedirect
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class ForceHTTPSMiddleware(MiddlewareMixin):
    """
    Middleware для принудительного редиректа на HTTPS
    """
    
    def process_request(self, request):
        # Проверяем, что мы не в режиме отладки
        if settings.DEBUG:
            return None
            
        # Проверяем, что запрос идет по HTTP
        if not request.is_secure():
            # Создаем HTTPS URL
            https_url = request.build_absolute_uri().replace('http://', 'https://', 1)
            
            # Выполняем постоянный редирект (301)
            return HttpResponsePermanentRedirect(https_url)
        
        return None


class WWWRedirectMiddleware(MiddlewareMixin):
    """
    Middleware для редиректа с www на основной домен
    """
    
    def process_request(self, request):
        # Проверяем, что мы не в режиме отладки
        if settings.DEBUG:
            return None
            
        # Проверяем, что запрос идет с www
        if request.get_host().startswith('www.'):
            # Создаем URL без www
            non_www_url = request.build_absolute_uri().replace('://www.', '://', 1)
            
            # Выполняем постоянный редирект (301)
            return HttpResponsePermanentRedirect(non_www_url)
        
        return None
