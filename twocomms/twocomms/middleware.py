"""
Дополнительные middleware для TwoComms
"""

from django.http import HttpResponsePermanentRedirect, HttpResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
import time


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


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware для установки Content-Security-Policy и связанных security-заголовков.
    """

    def process_response(self, request, response):
        csp = getattr(settings, "CONTENT_SECURITY_POLICY", None)
        if csp and not response.has_header("Content-Security-Policy"):
            response["Content-Security-Policy"] = csp

        x_xss = getattr(settings, "X_XSS_PROTECTION", None)
        if x_xss and not response.has_header("X-XSS-Protection"):
            response["X-XSS-Protection"] = x_xss

        referrer_policy = getattr(settings, "SECURE_REFERRER_POLICY", None)
        if referrer_policy and not response.has_header("Referrer-Policy"):
            response["Referrer-Policy"] = referrer_policy

        return response


class SimpleRateLimitMiddleware(MiddlewareMixin):
    """
    Simple rate limiting middleware to prevent abuse.
    Limits requests per IP address.
    """
    
    def process_request(self, request):
        # Skip rate limiting in DEBUG mode
        if settings.DEBUG:
            return None
            
        # Skip static and media files (double check, though WhiteNoise handles them first now)
        path = request.path
        if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
            return None
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        
        # Skip if no IP
        if not ip:
            return None
        
        # Rate limit: 100 requests per minute per IP
        cache_key = f'ratelimit:ip:{ip}'
        current_time = int(time.time())
        window_key = f'{cache_key}:{current_time // 60}'  # 1-minute window
        
        try:
            request_count = cache.get(window_key, 0)
            
            # Check if limit exceeded
            if request_count >= 100:
                response = HttpResponse(
                    'Rate limit exceeded. Please try again later.',
                    status=429
                )
                response['Retry-After'] = '60'
                return response
            
            # Increment counter
            cache.set(window_key, request_count + 1, 120)  # Store for 2 minutes
            
        except Exception:
            # If cache fails, allow the request
            pass
        
        return None
