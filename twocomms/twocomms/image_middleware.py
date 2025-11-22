"""
Middleware для автоматической оптимизации изображений при загрузке
"""

import os
import io
import logging
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor

from django.http import HttpResponse, FileResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from PIL import Image

logger = logging.getLogger(__name__)

class ImageOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware для автоматической оптимизации изображений с кэшированием на диске
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.enabled = getattr(settings, "IMAGE_OPTIMIZATION_MIDDLEWARE_ENABLED", False)
        self.allow_on_demand = getattr(settings, "IMAGE_OPTIMIZATION_ALLOW_ON_DEMAND", False)
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._pending_paths = set()
        self._pending_lock = threading.Lock()
        self.SMALL_IMAGE_THRESHOLD = 200 * 1024  # 200KB — можно оптимизировать синхронно
        if self.enabled:
            self.cache_dir = os.path.join(settings.MEDIA_ROOT, 'optimized_cache')
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir, exist_ok=True)
        else:
            self.cache_dir = None
            
    def process_request(self, request):
        """
        Проверяем наличие кэшированной версии изображения перед обработкой запроса
        """
        if not self.enabled:
            return None
        if not self._is_image_request(request):
            return None
        if not self._client_supports_webp(request):
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
        if not self.enabled:
            return response
        if not self._is_image_request(request):
            return response
        
        # Проверяем, что ответ содержит изображение и статус 200
        if response.status_code != 200 or not self._is_image_response(response):
            return response

        if not self._client_supports_webp(request):
            return response
            
        # Если уже отдали из кэша (в process_request), ничего не делаем
        if response.has_header('X-Image-Cache'):
            return response
        # В продакшене отключаем оптимизацию "на лету" — только возвращаем исходный ответ
        if not self.allow_on_demand:
            return response
        
        # Оптимизируем изображение
        try:
            cache_key = self._get_cache_key(request.path)
            cache_path = os.path.join(self.cache_dir, cache_key)
            content = getattr(response, 'content', None)
            if content is None:
                # Streaming/FileResponse без .content оптимизировать не будем
                return response
            # Всегда используем фоновую оптимизацию, чтобы не блокировать поток
            # Отдаем оригинал первому пользователю (Optimistic Response)
            self._schedule_async_optimization(cache_path, content)
            response['X-Image-Cache'] = 'WARMUP'
            return response
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

    def _client_supports_webp(self, request):
        """Определяет, умеет ли клиент работать с WebP"""
        accept = request.META.get('HTTP_ACCEPT', '')
        if 'image/webp' in accept:
            return True
        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        # Базовая эвристика: современные браузеры, кроме старого Safari
        if 'chrome' in ua or 'firefox' in ua or 'edg' in ua or 'opera' in ua or 'android' in ua:
            if 'safari' in ua and 'chrome' not in ua:
                return 'version/14' in ua or 'version/15' in ua or 'version/16' in ua or 'version/17' in ua
            return True
        return False
    
    def _is_image_response(self, response):
        """Проверяет, является ли ответ изображением"""
        content_type = response.get('Content-Type', '').lower()
        return any(img_type in content_type for img_type in ['image/jpeg', 'image/png', 'image/webp'])
    
    def _get_cache_key(self, path):
        """Генерирует имя файла кэша на основе MD5 хеша пути"""
        hash_object = hashlib.md5(path.encode())
        return f"{hash_object.hexdigest()}.webp"
    
    def _optimize_and_build_response(self, cache_path, image_data, original_response):
        """Оптимизирует изображение синхронно и возвращает HttpResponse"""
        optimized_data = self._convert_to_webp_bytes(image_data)
        if not optimized_data:
            return None
        if len(optimized_data) >= len(image_data):
            return None
        self._write_cache_file(cache_path, optimized_data)
        optimized_response = HttpResponse(
            optimized_data,
            content_type='image/webp',
            status=original_response.status_code
        )
        for key, value in original_response.items():
            if key.lower() not in ['content-length', 'content-type']:
                optimized_response[key] = value
        optimized_response['Content-Length'] = str(len(optimized_data))
        optimized_response['Cache-Control'] = 'public, max-age=31536000'
        optimized_response['ETag'] = f'"{hash(optimized_data)}"'
        optimized_response['X-Image-Cache'] = 'MISS'
        return optimized_response

    def _schedule_async_optimization(self, cache_path, image_data):
        """Запускает оптимизацию в фоне, чтобы не блокировать основной поток"""
        path_key = cache_path
        with self._pending_lock:
            if path_key in self._pending_paths:
                return
            self._pending_paths.add(path_key)

        data_copy = bytes(image_data)

        def task():
            try:
                optimized_data = self._convert_to_webp_bytes(data_copy)
                if optimized_data and len(optimized_data) < len(data_copy):
                    self._write_cache_file(cache_path, optimized_data)
            except Exception as exc:
                logger.error(f"Ошибка фоновой оптимизации {cache_path}: {exc}")
            finally:
                with self._pending_lock:
                    self._pending_paths.discard(path_key)

        self.executor.submit(task)
    
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

    def _convert_to_webp_bytes(self, image_data):
        """Конвертирует изображение в WebP и возвращает байты"""
        if len(image_data) < 1024:
            return None
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                if not self._should_optimize(img, len(image_data)):
                    return None
                return self._optimize_image(img)
        except Exception as exc:
            logger.error(f"Ошибка конвертации изображения: {exc}")
            return None

    def _write_cache_file(self, cache_path, optimized_data):
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'wb') as f:
            f.write(optimized_data)
    
    def _optimize_image(self, img):
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
