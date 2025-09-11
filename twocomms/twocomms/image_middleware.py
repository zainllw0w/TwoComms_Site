"""
Middleware для автоматической оптимизации изображений при загрузке
"""

import os
import logging
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from PIL import Image
import io

logger = logging.getLogger(__name__)

class ImageOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware для автоматической оптимизации изображений
    """
    
    def process_response(self, request, response):
        # Проверяем, что это запрос изображения
        if not self._is_image_request(request):
            return response
        
        # Проверяем, что ответ содержит изображение
        if not self._is_image_response(response):
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
        return any(path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.avif'])
    
    def _is_image_response(self, response):
        """Проверяет, является ли ответ изображением"""
        content_type = response.get('Content-Type', '').lower()
        return any(img_type in content_type for img_type in ['image/jpeg', 'image/png', 'image/webp', 'image/avif'])
    
    def _optimize_image_response(self, request, response):
        """Оптимизирует изображение в ответе"""
        # Получаем содержимое изображения
        image_data = response.content
        
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
                    # Создаем новый ответ с оптимизированным изображением
                    optimized_response = HttpResponse(
                        optimized_data,
                        content_type=response.get('Content-Type'),
                        status=response.status_code
                    )
                    
                    # Копируем заголовки
                    for key, value in response.items():
                        if key.lower() not in ['content-length']:
                            optimized_response[key] = value
                    
                    # Обновляем Content-Length
                    optimized_response['Content-Length'] = str(len(optimized_data))
                    
                    # Добавляем заголовки кеширования
                    optimized_response['Cache-Control'] = 'public, max-age=31536000'  # 1 год
                    optimized_response['ETag'] = f'"{hash(optimized_data)}"'
                    
                    logger.info(f"Оптимизировано изображение: {request.path} "
                              f"({len(image_data)} -> {len(optimized_data)} bytes)")
                    
                    return optimized_response
        
        except Exception as e:
            logger.error(f"Ошибка при оптимизации изображения {request.path}: {e}")
        
        return response
    
    def _should_optimize(self, img, size):
        """Определяет, нужно ли оптимизировать изображение"""
        # Не оптимизируем очень маленькие изображения
        if size < 5 * 1024:  # Меньше 5KB
            return False
        
        # Не оптимизируем уже оптимизированные форматы
        if img.format in ['WEBP', 'AVIF']:
            return False
        
        # Оптимизируем большие изображения
        if size > 50 * 1024:  # Больше 50KB
            return True
        
        # Оптимизируем изображения с большими размерами
        width, height = img.size
        if width > 800 or height > 600:
            return True
        
        return False
    
    def _optimize_image(self, img, original_format):
        """Оптимизирует изображение"""
        try:
            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'LA', 'P'):
                if original_format in ('JPEG', 'WEBP'):
                    # Создаем белый фон для прозрачности
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                else:
                    img = img.convert('RGBA')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Определяем оптимальный формат
            if original_format == 'PNG' and img.mode == 'RGBA':
                # Для PNG с прозрачностью используем WebP
                output_format = 'WEBP'
                quality = 80
            elif original_format in ('JPEG', 'PNG'):
                # Для JPEG и PNG без прозрачности используем WebP
                output_format = 'WEBP'
                quality = 85
            else:
                # Для других форматов используем оригинальный
                output_format = original_format
                quality = 85
            
            # Сохраняем в буфер
            output_buffer = io.BytesIO()
            
            if output_format == 'WEBP':
                img.save(output_buffer, format='WEBP', quality=quality, method=6)
            elif output_format == 'JPEG':
                img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
            elif output_format == 'PNG':
                img.save(output_buffer, format='PNG', optimize=True)
            else:
                img.save(output_buffer, format=output_format)
            
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации изображения: {e}")
            return None