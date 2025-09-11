"""
Система автоматической оптимизации изображений для TwoComms
"""

import os
import logging
from PIL import Image, ImageOps
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import io
from pathlib import Path

logger = logging.getLogger(__name__)

class ImageOptimizer:
    """Класс для оптимизации изображений"""
    
    # Качество сжатия для разных форматов
    QUALITY_SETTINGS = {
        'JPEG': 85,
        'PNG': 95,
        'WEBP': 80,
        'AVIF': 75
    }
    
    # Размеры для адаптивных изображений
    RESPONSIVE_SIZES = [
        (320, 240),   # Mobile small
        (640, 480),   # Mobile large
        (768, 576),   # Tablet
        (1024, 768),  # Desktop small
        (1920, 1080)  # Desktop large
    ]
    
    def __init__(self):
        self.media_root = settings.MEDIA_ROOT
        self.static_root = settings.STATIC_ROOT
        
    def optimize_image(self, image_path, output_format='WEBP', quality=None, max_size=None):
        """
        Оптимизирует изображение
        
        Args:
            image_path: Путь к изображению
            output_format: Формат вывода (WEBP, AVIF, JPEG, PNG)
            quality: Качество сжатия (если None, используется по умолчанию)
            max_size: Максимальный размер (width, height)
        """
        try:
            # Открываем изображение
            with Image.open(image_path) as img:
                # Конвертируем в RGB если нужно
                if img.mode in ('RGBA', 'LA', 'P'):
                    if output_format in ('JPEG', 'WEBP'):
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
                
                # Изменяем размер если нужно
                if max_size:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Настраиваем качество
                if quality is None:
                    quality = self.QUALITY_SETTINGS.get(output_format, 85)
                
                # Сохраняем в нужном формате
                output_buffer = io.BytesIO()
                
                if output_format == 'WEBP':
                    img.save(output_buffer, format='WEBP', quality=quality, method=6)
                elif output_format == 'AVIF':
                    img.save(output_buffer, format='AVIF', quality=quality)
                elif output_format == 'JPEG':
                    img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
                elif output_format == 'PNG':
                    img.save(output_buffer, format='PNG', optimize=True)
                
                return output_buffer.getvalue()
                
        except Exception as e:
            logger.error(f"Ошибка оптимизации изображения {image_path}: {e}")
            return None
    
    def create_responsive_images(self, image_path, base_name):
        """
        Создает адаптивные версии изображения
        
        Args:
            image_path: Путь к оригинальному изображению
            base_name: Базовое имя файла
        """
        responsive_images = {}
        
        for size in self.RESPONSIVE_SIZES:
            # Создаем WebP версию
            webp_data = self.optimize_image(image_path, 'WEBP', max_size=size)
            if webp_data:
                webp_name = f"{base_name}_{size[0]}w.webp"
                responsive_images[webp_name] = webp_data
            
            # Создаем AVIF версию (если поддерживается)
            try:
                avif_data = self.optimize_image(image_path, 'AVIF', max_size=size)
                if avif_data:
                    avif_name = f"{base_name}_{size[0]}w.avif"
                    responsive_images[avif_name] = avif_data
            except Exception:
                # AVIF может не поддерживаться
                pass
        
        return responsive_images
    
    def optimize_product_image(self, product_image_path):
        """
        Оптимизирует изображение товара
        
        Args:
            product_image_path: Путь к изображению товара
        """
        if not os.path.exists(product_image_path):
            return None
        
        # Получаем информацию о файле
        file_name = Path(product_image_path).stem
        file_ext = Path(product_image_path).suffix.lower()
        
        optimized_images = {}
        
        # Создаем оптимизированную версию в оригинальном формате
        if file_ext in ['.jpg', '.jpeg']:
            optimized_data = self.optimize_image(product_image_path, 'JPEG', quality=85)
            if optimized_data:
                optimized_images[f"{file_name}_optimized.jpg"] = optimized_data
        
        # Создаем WebP версию
        webp_data = self.optimize_image(product_image_path, 'WEBP', quality=80)
        if webp_data:
            optimized_images[f"{file_name}.webp"] = webp_data
        
        # Создаем AVIF версию
        try:
            avif_data = self.optimize_image(product_image_path, 'AVIF', quality=75)
            if avif_data:
                optimized_images[f"{file_name}.avif"] = avif_data
        except Exception:
            pass
        
        # Создаем адаптивные версии
        responsive_images = self.create_responsive_images(product_image_path, file_name)
        optimized_images.update(responsive_images)
        
        return optimized_images
    
    def optimize_category_icon(self, icon_path):
        """
        Оптимизирует иконку категории
        
        Args:
            icon_path: Путь к иконке категории
        """
        if not os.path.exists(icon_path):
            return None
        
        file_name = Path(icon_path).stem
        
        optimized_images = {}
        
        # Оптимизируем для размера 24x24 (размер контейнера)
        small_size = (24, 24)
        
        # Создаем оптимизированную PNG версию
        png_data = self.optimize_image(icon_path, 'PNG', max_size=small_size)
        if png_data:
            optimized_images[f"{file_name}_24x24.png"] = png_data
        
        # Создаем WebP версию
        webp_data = self.optimize_image(icon_path, 'WEBP', max_size=small_size, quality=80)
        if webp_data:
            optimized_images[f"{file_name}_24x24.webp"] = webp_data
        
        # Создаем SVG версию (если возможно)
        try:
            # Для PNG иконок создаем упрощенную версию
            with Image.open(icon_path) as img:
                if img.size[0] > 48:  # Если иконка большая
                    img.thumbnail((48, 48), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG', optimize=True)
                    optimized_images[f"{file_name}_48x48.png"] = buffer.getvalue()
        except Exception:
            pass
        
        return optimized_images
    
    def optimize_static_image(self, static_image_path):
        """
        Оптимизирует статическое изображение
        
        Args:
            static_image_path: Путь к статическому изображению
        """
        if not os.path.exists(static_image_path):
            return None
        
        file_name = Path(static_image_path).stem
        file_ext = Path(static_image_path).suffix.lower()
        
        optimized_images = {}
        
        # Определяем оптимальный размер в зависимости от типа изображения
        if 'noise' in file_name.lower():
            # Для noise.png используем оригинальный размер
            max_size = None
        else:
            # Для других изображений ограничиваем размер
            max_size = (1920, 1080)
        
        # Создаем оптимизированную версию
        if file_ext in ['.jpg', '.jpeg']:
            optimized_data = self.optimize_image(static_image_path, 'JPEG', quality=85, max_size=max_size)
            if optimized_data:
                optimized_images[f"{file_name}_optimized.jpg"] = optimized_data
        elif file_ext == '.png':
            optimized_data = self.optimize_image(static_image_path, 'PNG', max_size=max_size)
            if optimized_images:
                optimized_images[f"{file_name}_optimized.png"] = optimized_data
        
        # Создаем WebP версию
        webp_data = self.optimize_image(static_image_path, 'WEBP', quality=80, max_size=max_size)
        if webp_data:
            optimized_images[f"{file_name}.webp"] = webp_data
        
        # Создаем AVIF версию
        try:
            avif_data = self.optimize_image(static_image_path, 'AVIF', quality=75, max_size=max_size)
            if avif_data:
                optimized_images[f"{file_name}.avif"] = avif_data
        except Exception:
            pass
        
        return optimized_images
    
    def save_optimized_images(self, optimized_images, output_dir):
        """
        Сохраняет оптимизированные изображения
        
        Args:
            optimized_images: Словарь с оптимизированными изображениями
            output_dir: Директория для сохранения
        """
        os.makedirs(output_dir, exist_ok=True)
        
        saved_files = []
        for filename, image_data in optimized_images.items():
            output_path = os.path.join(output_dir, filename)
            try:
                with open(output_path, 'wb') as f:
                    f.write(image_data)
                saved_files.append(output_path)
                logger.info(f"Сохранено оптимизированное изображение: {output_path}")
            except Exception as e:
                logger.error(f"Ошибка сохранения {output_path}: {e}")
        
        return saved_files
