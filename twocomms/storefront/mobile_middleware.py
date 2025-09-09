"""
Middleware для мобильной оптимизации
"""
import re
from django.utils.deprecation import MiddlewareMixin

class MobileOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware для оптимизации мобильных устройств
    """
    
    def process_request(self, request):
        """
        Анализирует запрос и добавляет информацию о мобильном устройстве
        """
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        # Определяем тип устройства
        request.is_mobile = any(keyword in user_agent for keyword in [
            'mobile', 'android', 'iphone', 'ipod'
        ])
        
        request.is_tablet = any(keyword in user_agent for keyword in [
            'ipad', 'tablet', 'kindle'
        ])
        
        request.is_touch_device = request.is_mobile or request.is_tablet
        
        # Определяем возможности соединения
        save_data = request.META.get('HTTP_SAVE_DATA', '') == '1'
        device_memory = request.META.get('HTTP_DEVICE_MEMORY', '')
        low_memory = device_memory and int(device_memory) <= 2
        
        # Определяем медленное соединение
        connection_type = request.META.get('HTTP_CONNECTION_TYPE', '')
        is_slow_connection = any(slow in connection_type.lower() for slow in ['2g', 'slow-2g'])
        
        # Добавляем флаги оптимизации
        request.mobile_optimization = {
            'save_data': save_data,
            'low_memory': low_memory,
            'slow_connection': is_slow_connection,
            'should_reduce_animations': save_data or low_memory or is_slow_connection,
            'should_use_lite_mode': save_data or low_memory,
            'should_lazy_load_images': is_slow_connection or low_memory
        }
        
        return None
    
    def process_response(self, request, response):
        """
        Оптимизирует ответ для мобильных устройств
        """
        if hasattr(request, 'is_mobile') and request.is_mobile:
            # Добавляем заголовки для мобильной оптимизации
            response['Vary'] = 'User-Agent, Save-Data, Device-Memory'
            
            # Добавляем заголовки для кэширования
            if request.mobile_optimization.get('slow_connection'):
                response['Cache-Control'] = 'public, max-age=3600'
            
            # Добавляем заголовки для сжатия
            if 'gzip' in request.META.get('HTTP_ACCEPT_ENCODING', ''):
                response['Content-Encoding'] = 'gzip'
        
        return response

class MobilePerformanceMiddleware(MiddlewareMixin):
    """
    Middleware для мониторинга производительности на мобильных устройствах
    """
    
    def process_request(self, request):
        """
        Логирует информацию о производительности для мобильных устройств
        """
        if hasattr(request, 'is_mobile') and request.is_mobile:
            # Логируем информацию о устройстве для аналитики
            device_info = {
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'connection_type': request.META.get('HTTP_CONNECTION_TYPE', ''),
                'device_memory': request.META.get('HTTP_DEVICE_MEMORY', ''),
                'save_data': request.META.get('HTTP_SAVE_DATA', ''),
                'viewport_width': request.META.get('HTTP_VIEWPORT_WIDTH', ''),
                'path': request.path
            }
            
            # Здесь можно добавить логирование в базу данных или аналитику
            # logger.info(f"Mobile device info: {device_info}")
        
        return None
