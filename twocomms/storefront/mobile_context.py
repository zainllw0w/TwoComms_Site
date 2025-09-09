"""
Мобильный контекстный процессор для оптимизации производительности
"""
import re

def mobile_optimization(request):
    """
    Добавляет информацию о мобильном устройстве в контекст
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    
    # Определяем тип устройства
    is_mobile = any(keyword in user_agent for keyword in [
        'mobile', 'android', 'iphone', 'ipod'
    ])
    
    is_tablet = any(keyword in user_agent for keyword in [
        'ipad', 'tablet', 'kindle'
    ])
    
    is_touch_device = is_mobile or is_tablet
    
    # Определяем возможности устройства
    connection = request.META.get('HTTP_SAVE_DATA', '')
    is_slow_connection = connection == '1' or '2g' in user_agent
    
    # Определяем размер экрана (примерно)
    screen_size = 'desktop'
    if is_mobile:
        screen_size = 'mobile'
    elif is_tablet:
        screen_size = 'tablet'
    
    # Определяем поддержку WebP
    accept_header = request.META.get('HTTP_ACCEPT', '')
    supports_webp = 'image/webp' in accept_header
    
    # Определяем поддержку современных форматов
    supports_avif = 'image/avif' in accept_header
    
    return {
        'is_mobile': is_mobile,
        'is_tablet': is_tablet,
        'is_touch_device': is_touch_device,
        'is_slow_connection': is_slow_connection,
        'screen_size': screen_size,
        'supports_webp': supports_webp,
        'supports_avif': supports_avif,
        'device_capabilities': {
            'webp': supports_webp,
            'avif': supports_avif,
            'touch': is_touch_device,
            'slow_connection': is_slow_connection
        }
    }

def mobile_performance_hints(request):
    """
    Добавляет подсказки для оптимизации производительности
    """
    # Проверяем заголовки для определения возможностей
    save_data = request.META.get('HTTP_SAVE_DATA', '') == '1'
    device_memory = request.META.get('HTTP_DEVICE_MEMORY', '')
    low_memory = device_memory and int(device_memory) <= 2
    
    # Определяем медленное соединение
    connection_type = request.META.get('HTTP_CONNECTION_TYPE', '')
    is_slow_connection = any(slow in connection_type.lower() for slow in ['2g', 'slow-2g'])
    
    # Определяем размер viewport
    viewport_width = request.META.get('HTTP_VIEWPORT_WIDTH', '')
    is_small_screen = viewport_width and int(viewport_width) <= 576
    
    # Рекомендации по оптимизации
    should_reduce_animations = save_data or low_memory or is_slow_connection
    should_use_lite_mode = save_data or low_memory or is_small_screen
    should_lazy_load_images = is_slow_connection or low_memory
    
    return {
        'performance_hints': {
            'save_data': save_data,
            'low_memory': low_memory,
            'slow_connection': is_slow_connection,
            'small_screen': is_small_screen,
            'reduce_animations': should_reduce_animations,
            'lite_mode': should_use_lite_mode,
            'lazy_load_images': should_lazy_load_images
        }
    }
