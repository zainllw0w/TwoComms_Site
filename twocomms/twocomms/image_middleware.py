"""
Middleware для автоматической оптимизации изображений при загрузке
"""

import os
import logging
import hashlib
from django.http import HttpResponse, FileResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from PIL import Image
import io

logger = logging.getLogger(__name__)

class ImageOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware для автоматической оптимизации изображений с кэшированием на диске
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.cache_dir = os.path.join(settings.MEDIA_ROOT, 'optimized_cache')
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
            
    def process_request(self, request):
        """
        Проверяем наличие кэшированной версии изображения перед обработкой запроса
        """
        if not self._is_image_request(request):
            return None
            
        # Генерируем ключ кэша на основе URL
        cache_key = self._get_cache_key(request.path)
        cache_path = os.path.join(self.cache_dir, cache_key)
        
        # Если файл есть в кэше, отдаем его сразу
        if os.path.exists(cache_path):
            # logger.debug(f"Serving cached image: {request.path}")
            response = FileResponse(open(cache_path, 'rb'))
            response['Content-Type'] = 'image/webp'  # Мы всегда конвертируем в WebP
            response['Cache-Control'] = 'public, max-age=31536000'
            response['X-Image-Cache'] = 'HIT'
            return response
            
        return None
    
    def process_response(self, request, response):
        # Проверяем, что это запрос изображения
        if not self._is_image_request(request):
            return response
        
        # Проверяем, что ответ содержит изображение и статус 200
        if response.status_code != 200 or not self._is_image_response(response):
            return response
            
        # Если уже отдали из кэша (в process_request), ничего не делаем
        if response.has_header('X-Image-Cache'):
            return response
        
        # Оптимизируем изображение
        try:
            optimized_response = self._optimize_image_response(request, response)
            return optimized_response
        except Exception as e:
            logger.error(f"Ошибка оптимизации изображения: {e}")
            return response
    
    def _is_image_request(self, request):
        """Проверяет, является ли запрос запросом изображения"""
        path = request.path.lower()
        # Игнорируем админку и статику (обычно статика уже оптимизирована при сборке)
        if path.startswith('/static/') or path.startswith('/admin/'):
            return False
        return any(path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp'])
    
    def _is_image_response(self, response):
        """Проверяет, является ли ответ изображением"""
        content_type = response.get('Content-Type', '').lower()
        return any(img_type in content_type for img_type in ['image/jpeg', 'image/png', 'image/webp'])
    
    def _get_cache_key(self, path):
        """Генерирует имя файла кэша на основе MD5 хеша пути"""
        hash_object = hashlib.md5(path.encode())
        return f"{hash_object.hexdigest()}.webp"
    
    def _optimize_image_response(self, request, response):
        """Оптимизирует изображение в ответе и сохраняет в кэш"""
        # Получаем содержимое изображения
        if hasattr(response, 'content'):
            image_data = response.content
        else:
            # Если это FileResponse или StreamingHttpResponse, мы не можем легко получить контент
            return response
        
        # Проверяем размер изображения
        if len(image_data) < 1024:  # Меньше 1KB - не оптимизируем
            return response
        
        try:
            # Открываем изображение
            with Image.open(io.BytesIO(image_data)) as img:
                # Определяем формат
                original_format = img.format
                
                # Проверяем, нужно ли оптимизировать
                if not self._should_optimize(img, len(image_data)):
                    return response
                
                # Оптимизируем изображение
                optimized_data = self._optimize_image(img, original_format)
                
                if optimized_data and len(optimized_data) < len(image_data):
                    # Сохраняем в кэш
                    cache_key = self._get_cache_key(request.path)
                    cache_path = os.path.join(self.cache_dir, cache_key)
                    
                    with open(cache_path, 'wb') as f:
                        f.write(optimized_data)
                    
                    # Создаем новый ответ с оптимизированным изображением
                    optimized_response = HttpResponse(
                        optimized_data,
                        content_type='image/webp', # Всегда WebP
                        status=response.status_code
                    )
                    
                    # Копируем заголовки
                    for key, value in response.items():
                        if key.lower() not in ['content-length', 'content-type']:
                            optimized_response[key] = value
                    
                    # Обновляем Content-Length
                    optimized_response['Content-Length'] = str(len(optimized_data))
                    
                    # Добавляем заголовки кеширования
                    optimized_response['Cache-Control'] = 'public, max-age=31536000'  # 1 год
                    optimized_response['ETag'] = f'"{hash(optimized_data)}"'
                    optimized_response['X-Image-Cache'] = 'MISS'
                    
                    # logger.info(f"Оптимизировано изображение: {request.path} ({len(image_data)} -> {len(optimized_data)} bytes)")
                    
                    return optimized_response
        
        except Exception as e:
            logger.error(f"Ошибка при оптимизации изображения {request.path}: {e}")
        
        return response
    
    def _should_optimize(self, img, size):
        """Определяет, нужно ли оптимизировать изображение"""
        # Не оптимизируем очень маленькие изображения
        if size < 5 * 1024:  # Меньше 5KB
            return False
        
        # Не оптимизируем уже оптимизированные форматы (если они уже WebP)
        if img.format == 'WEBP':
            return False
        
        # Оптимизируем все остальное
        return True
    
    def _optimize_image(self, img, original_format):
        """Оптимизирует изображение"""
        try:
            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'LA', 'P'):
                # Для WebP прозрачность поддерживается, оставляем RGBA
                if img.mode == 'P':
                    img = img.convert('RGBA')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Сохраняем в буфер как WebP
            output_buffer = io.BytesIO()
            img.save(output_buffer, format='WEBP', quality=80, method=4) # method=4 быстрее чем 6, но хорошее качество
            
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации изображения: {e}")
            return None