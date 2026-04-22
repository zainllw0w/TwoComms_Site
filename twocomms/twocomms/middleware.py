"""
Дополнительные middleware для TwoComms
"""

from django.http import HttpResponsePermanentRedirect, HttpResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.core.exceptions import DisallowedHost
from django.contrib.redirects.middleware import RedirectFallbackMiddleware
import os
import time


class ForceHTTPSMiddleware(MiddlewareMixin):
    """
    Middleware для принудительного редиректа на HTTPS
    """

    def process_request(self, request):
        # Проверяем, что мы не в режиме отладки
        if settings.DEBUG:
            return None

        # Service worker registration on some production frontends can reach Django
        # without the usual proxy HTTPS markers, which creates a self-redirect loop.
        # The worker still requires a secure browser context, so skip middleware
        # canonicalization here and let the dedicated view answer directly.
        if request.path == '/sw.js':
            return None

        if request.path.startswith('/tg-manager/webhook/'):
            return None

        # Проверяем, что запрос идет по HTTP
        if not request.is_secure():
            try:
                # Создаем HTTPS URL
                https_url = request.build_absolute_uri().replace('http://', 'https://', 1)
            except DisallowedHost:
                # Let Django return a regular DisallowedHost response without noisy middleware traceback.
                return None

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

        try:
            host = request.get_host()
        except DisallowedHost:
            return None

        # Проверяем, что запрос идет с www
        if host.startswith('www.'):
            # Создаем URL без www
            non_www_url = request.build_absolute_uri().replace('://www.', '://', 1)

            # Выполняем постоянный редирект (301)
            return HttpResponsePermanentRedirect(non_www_url)

        return None


class SubdomainURLRoutingMiddleware(MiddlewareMixin):
    """
    Middleware для маршрутизации поддоменов.
    Если запрос приходит на main.domain.com, переключаем urlconf на специальный конфиг.
    """

    def process_request(self, request):
        try:
            host = request.get_host().split(":")[0].lower()
        except DisallowedHost:
            return None

        # DTF subdomain should run its own site/urlconf.
        if host.startswith('dtf.'):
            request.urlconf = 'twocomms.urls_dtf'
            return None

        # Если это management поддомен
        if host.startswith('management.'):
            request.urlconf = 'twocomms.urls_management'
            return None

        # Продолжаем обычную обработку
        return None


class SubdomainRedirectFallbackMiddleware(RedirectFallbackMiddleware):
    """
    RedirectFallbackMiddleware only for non-DTF hosts.

    DTF pages should not hit django_redirect lookups for each 404 path probe.
    """

    def process_response(self, request, response):
        try:
            host = request.get_host().split(":")[0].lower()
        except Exception:
            host = ""
        if host.startswith("dtf."):
            return response
        return super().process_response(request, response)


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


class RequestTraceMiddleware(MiddlewareMixin):
    """
    Lightweight request tracing for DTF diagnostics.

    Enabled per-request via header: X-DTF-Debug: 1
    """

    def process_request(self, request):
        request._twc_trace_start = time.perf_counter()
        return None

    def process_response(self, request, response):
        started = getattr(request, "_twc_trace_start", None)
        if started is None:
            return response

        duration_ms = (time.perf_counter() - started) * 1000.0

        debug_header = request.META.get("HTTP_X_DTF_DEBUG", "")
        if str(debug_header).strip() != "1":
            return response

        try:
            host = request.get_host().split(":")[0].lower()
        except Exception:
            host = ""
        if not host.startswith("dtf."):
            return response

        response["X-App-Pid"] = str(os.getpid())
        response["X-App-Django-Ms"] = f"{duration_ms:.2f}"
        existing_server_timing = response.get("Server-Timing")
        trace_value = f"django;dur={duration_ms:.2f}"
        response["Server-Timing"] = (
            f"{existing_server_timing}, {trace_value}"
            if existing_server_timing
            else trace_value
        )
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

        # DTF public pages are read-heavy and already protected by endpoint-level limits.
        # Skip generic IP limiter for safe methods to reduce cache I/O in hot path.
        try:
            host = request.get_host().split(':')[0].lower()
        except Exception:
            host = ''
        if host.startswith('dtf.') and request.method in ('GET', 'HEAD', 'OPTIONS'):
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
