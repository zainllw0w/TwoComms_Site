"""
Rate Limiting Middleware for TwoComms
Protects against brute force attacks and API abuse
"""
import time
from django.core.cache import cache
from django.http import HttpResponse
from django.conf import settings


class RateLimitMiddleware:
    """
    Simple rate limiting middleware using Django cache
    
    Limits:
    - 100 requests per minute per IP for anonymous users
    - 1000 requests per minute per IP for authenticated users
    - 10 requests per minute for login attempts
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Rate limits (requests per minute)
        self.anon_limit = getattr(settings, 'RATELIMIT_ANON', 100)
        self.user_limit = getattr(settings, 'RATELIMIT_USER', 1000)
        self.login_limit = getattr(settings, 'RATELIMIT_LOGIN', 10)
        
        # Paths that require stricter rate limiting
        self.strict_paths = [
            '/login/',
            '/accounts/login/',
            '/api/auth/',
            '/password_reset/',
        ]
    
    def __call__(self, request):
        # Skip rate limiting for static files and media
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)
        
        # Get client IP
        ip = self.get_client_ip(request)
        
        # Determine rate limit based on path and user
        if any(request.path.startswith(path) for path in self.strict_paths):
            limit = self.login_limit
            window = 60  # 1 minute
            cache_key = f'ratelimit:strict:{ip}:{request.path}'
        elif hasattr(request, 'user') and request.user.is_authenticated:
            limit = self.user_limit
            window = 60
            cache_key = f'ratelimit:user:{ip}'
        else:
            limit = self.anon_limit
            window = 60
            cache_key = f'ratelimit:anon:{ip}'
        
        # Check rate limit
        current_requests = cache.get(cache_key, 0)
        
        if current_requests >= limit:
            # Rate limit exceeded
            retry_after = cache.ttl(cache_key) or window
            response = HttpResponse(
                'Rate limit exceeded. Please try again later.',
                status=429,
                content_type='text/plain'
            )
            response['Retry-After'] = str(retry_after)
            response['X-RateLimit-Limit'] = str(limit)
            response['X-RateLimit-Remaining'] = '0'
            response['X-RateLimit-Reset'] = str(int(time.time()) + retry_after)
            return response
        
        # Increment counter
        try:
        if current_requests == 0:
            # First request in this window
            cache.set(cache_key, 1, window)
        else:
                # Use set instead of incr for redis-herd compatibility  
                cache.set(cache_key, current_requests + 1, window)
        except Exception:
            # Gracefully handle cache failures
            pass
        
        # Add rate limit headers to response
        response = self.get_response(request)
        response['X-RateLimit-Limit'] = str(limit)
        response['X-RateLimit-Remaining'] = str(limit - current_requests - 1)
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

