"""
Mobile-First Optimization Middleware
Оптимизирует ответы специально для мобильных устройств
"""

import re
import gzip
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse

logger = logging.getLogger(__name__)


class MobileDetectionMiddleware(MiddlewareMixin):
    """
    Детектирует мобильные устройства и добавляет соответствующий контекст
    """
    
    MOBILE_USER_AGENTS = [
        'iPhone', 'iPad', 'iPod', 'Android', 'BlackBerry',
        'Windows Phone', 'Opera Mini', 'IEMobile', 'Mobile'
    ]
    
    TABLET_USER_AGENTS = ['iPad', 'Android.*Tablet', 'Tablet']
    
    def process_request(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Определяем тип устройства
        request.is_mobile = any(re.search(agent, user_agent, re.I) 
                               for agent in self.MOBILE_USER_AGENTS)
        request.is_tablet = any(re.search(agent, user_agent, re.I) 
                               for agent in self.TABLET_USER_AGENTS)
        request.is_desktop = not (request.is_mobile or request.is_tablet)
        
        # Определяем конкретную платформу
        request.is_ios = bool(re.search(r'iPhone|iPad|iPod', user_agent, re.I))
        request.is_android = bool(re.search(r'Android', user_agent, re.I))
        
        # Добавляем информацию в заголовки ответа
        request.device_type = 'mobile' if request.is_mobile else (
            'tablet' if request.is_tablet else 'desktop'
        )
        
        return None


class MobileOptimizationMiddleware(MiddlewareMixin):
    """
    Оптимизирует HTML ответы для мобильных устройств
    """
    
    def process_response(self, request, response):
        # Применяем оптимизации только для HTML
        if not self._is_html_response(response):
            return response
        
        # Проверяем, что это мобильное устройство
        is_mobile = getattr(request, 'is_mobile', False)
        
        if not is_mobile:
            return response
        
        try:
            # Получаем содержимое
            content = response.content.decode('utf-8')
            
            # Применяем оптимизации
            content = self._remove_comments(content)
            content = self._minify_whitespace(content)
            content = self._optimize_mobile_resources(content)
            
            # Обновляем ответ
            response.content = content.encode('utf-8')
            response['Content-Length'] = str(len(response.content))
            
            # Добавляем заголовки для мобильных
            response['X-UA-Compatible'] = 'IE=edge'
            response['X-Mobile-Optimized'] = 'true'
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации для мобильных: {e}")
        
        return response
    
    def _is_html_response(self, response):
        """Проверяет, является ли ответ HTML"""
        content_type = response.get('Content-Type', '').lower()
        return 'text/html' in content_type and response.status_code == 200
    
    def _remove_comments(self, content):
        """Удаляет HTML комментарии (кроме условных)"""
        # Сохраняем условные комментарии IE
        content = re.sub(r'<!--(?!\[if)(?!<!\[endif).*?-->', '', content, flags=re.DOTALL)
        return content
    
    def _minify_whitespace(self, content):
        """Минифицирует пробелы и переносы строк"""
        # Не трогаем <pre>, <code>, <textarea>
        preserved_tags = []
        
        def preserve_tag(match):
            preserved_tags.append(match.group(0))
            return f'<!--PRESERVED_{len(preserved_tags)-1}-->'
        
        # Сохраняем содержимое тегов
        content = re.sub(
            r'<(pre|code|textarea)[^>]*>.*?</\1>',
            preserve_tag,
            content,
            flags=re.DOTALL | re.I
        )
        
        # Минифицируем
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'>\s+<', '><', content)
        
        # Восстанавливаем сохраненное содержимое
        for i, preserved in enumerate(preserved_tags):
            content = content.replace(f'<!--PRESERVED_{i}-->', preserved)
        
        return content.strip()
    
    def _optimize_mobile_resources(self, content):
        """Оптимизирует ресурсы для мобильных"""
        # Добавляем loading="lazy" к изображениям ниже fold
        # (кроме первых 2-3 изображений)
        img_pattern = r'<img(?![^>]*loading=)[^>]*>'
        imgs = re.findall(img_pattern, content)
        
        for i, img in enumerate(imgs):
            if i >= 2:  # Пропускаем первые 2 изображения
                new_img = img.replace('<img', '<img loading="lazy"')
                content = content.replace(img, new_img, 1)
        
        return content


class CompressionMiddleware(MiddlewareMixin):
    """
    Сжимает ответы с помощью gzip для экономии трафика
    """
    
    MIN_SIZE = 200  # Минимальный размер для сжатия (байты)
    
    COMPRESSIBLE_TYPES = [
        'text/html',
        'text/css',
        'text/javascript',
        'application/javascript',
        'application/json',
        'application/xml',
        'text/xml',
        'image/svg+xml'
    ]
    
    def process_response(self, request, response):
        # Проверяем, что клиент поддерживает gzip
        if not self._accepts_gzip(request):
            return response
        
        # Проверяем, что ответ можно сжимать
        if not self._is_compressible(response):
            return response
        
        # Проверяем, что ответ еще не сжат
        if response.get('Content-Encoding'):
            return response
        
        # Проверяем размер
        if len(response.content) < self.MIN_SIZE:
            return response
        
        try:
            # Сжимаем содержимое
            compressed_content = gzip.compress(response.content, compresslevel=6)
            
            # Проверяем, что сжатие дало результат
            if len(compressed_content) >= len(response.content):
                return response
            
            # Обновляем ответ
            response.content = compressed_content
            response['Content-Length'] = str(len(compressed_content))
            response['Content-Encoding'] = 'gzip'
            response['Vary'] = 'Accept-Encoding'
            
            logger.debug(f"Сжато {len(response.content)} -> {len(compressed_content)} байт")
            
        except Exception as e:
            logger.error(f"Ошибка сжатия: {e}")
        
        return response
    
    def _accepts_gzip(self, request):
        """Проверяет, поддерживает ли клиент gzip"""
        accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        return 'gzip' in accept_encoding.lower()
    
    def _is_compressible(self, response):
        """Проверяет, можно ли сжимать ответ"""
        if response.status_code != 200:
            return False
        
        content_type = response.get('Content-Type', '').lower().split(';')[0]
        return any(ct in content_type for ct in self.COMPRESSIBLE_TYPES)


class ClientHintsMiddleware(MiddlewareMixin):
    """
    Добавляет поддержку Client Hints для адаптивной загрузки ресурсов
    """
    
    def process_response(self, request, response):
        # Добавляем заголовок Accept-CH для запроса client hints
        response['Accept-CH'] = 'DPR, Viewport-Width, Width, Downlink, ECT, RTT, Save-Data'
        response['Accept-CH-Lifetime'] = '86400'  # 24 часа
        
        # Добавляем Vary для корректного кэширования
        vary_header = response.get('Vary', '')
        if vary_header:
            vary_header += ', '
        vary_header += 'DPR, Width, Viewport-Width, Downlink, Save-Data'
        response['Vary'] = vary_header
        
        return response


class AdaptiveImageHintsMiddleware(MiddlewareMixin):
    """
    Добавляет hints для адаптивной загрузки изображений
    на основе характеристик устройства и соединения
    """
    
    def process_request(self, request):
        # Получаем client hints
        dpr = float(request.META.get('HTTP_DPR', 1.0))
        viewport_width = request.META.get('HTTP_VIEWPORT_WIDTH', '')
        save_data = request.META.get('HTTP_SAVE_DATA', '') == 'on'
        ect = request.META.get('HTTP_ECT', '')  # Effective Connection Type
        
        # Сохраняем в request для использования в views
        request.client_hints = {
            'dpr': dpr,
            'viewport_width': int(viewport_width) if viewport_width.isdigit() else 0,
            'save_data': save_data,
            'ect': ect
        }
        
        # Определяем рекомендуемое качество изображений
        if save_data or ect in ['slow-2g', '2g']:
            request.image_quality = 'low'  # 60-70
        elif ect == '3g':
            request.image_quality = 'medium'  # 75-80
        else:
            request.image_quality = 'high'  # 85-90
        
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Добавляет дополнительные security заголовки для мобильных
    """
    
    def process_response(self, request, response):
        # Feature Policy для контроля доступа к API
        response['Permissions-Policy'] = (
            'accelerometer=(), '
            'camera=(), '
            'geolocation=(self), '
            'gyroscope=(), '
            'magnetometer=(), '
            'microphone=(), '
            'payment=(), '
            'usb=()'
        )
        
        # Дополнительные заголовки безопасности
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response


class PerformanceHintsMiddleware(MiddlewareMixin):
    """
    Добавляет hints для оптимизации производительности
    """
    
    def process_response(self, request, response):
        # Link headers для preconnect к критичным доменам
        preconnect_domains = [
            'https://cdn.jsdelivr.net',
            'https://fonts.googleapis.com',
            'https://fonts.gstatic.com'
        ]
        
        link_headers = [f'<{domain}>; rel=preconnect' for domain in preconnect_domains]
        
        if link_headers:
            response['Link'] = ', '.join(link_headers)
        
        # Server-Timing для мониторинга производительности
        if hasattr(request, '_start_time'):
            import time
            duration = (time.time() - request._start_time) * 1000
            response['Server-Timing'] = f'total;dur={duration:.2f}'
        
        return response
    
    def process_request(self, request):
        import time
        request._start_time = time.time()
        return None

