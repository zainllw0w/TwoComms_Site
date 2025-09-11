#!/usr/bin/env python3
"""
Скрипт для оптимизации всех изображений в проекте TwoComms
"""

import os
import sys
import django
from pathlib import Path

# Добавляем путь к проекту Django
sys.path.append('/Users/zainllw0w/PycharmProjects/TwoComms/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from image_optimizer import ImageOptimizer
from storefront.models import Product
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('image_optimization.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def optimize_all_images():
    """Оптимизирует все изображения в проекте"""
    
    optimizer = ImageOptimizer()
    total_savings = 0
    processed_files = 0
    
    # Пути к директориям
    media_dir = '/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/media'
    static_dir = '/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/static'
    
    logger.info("🚀 Начинаем оптимизацию изображений...")
    
    # 1. Оптимизируем изображения товаров
    logger.info("📦 Оптимизируем изображения товаров...")
    products_dir = os.path.join(media_dir, 'products')
    if os.path.exists(products_dir):
        for filename in os.listdir(products_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                file_path = os.path.join(products_dir, filename)
                original_size = os.path.getsize(file_path)
                
                logger.info(f"Обрабатываем: {filename} ({original_size / 1024:.1f} KiB)")
                
                optimized_images = optimizer.optimize_product_image(file_path)
                if optimized_images:
                    # Создаем директорию для оптимизированных изображений
                    optimized_dir = os.path.join(products_dir, 'optimized')
                    saved_files = optimizer.save_optimized_images(optimized_images, optimized_dir)
                    
                    # Вычисляем экономию
                    total_optimized_size = sum(os.path.getsize(f) for f in saved_files)
                    savings = original_size - total_optimized_size
                    total_savings += savings
                    processed_files += 1
                    
                    logger.info(f"✅ {filename}: экономия {savings / 1024:.1f} KiB")
    
    # 2. Оптимизируем иконки категорий
    logger.info("🏷️ Оптимизируем иконки категорий...")
    category_icons_dir = os.path.join(media_dir, 'category_icons')
    if os.path.exists(category_icons_dir):
        for filename in os.listdir(category_icons_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                file_path = os.path.join(category_icons_dir, filename)
                original_size = os.path.getsize(file_path)
                
                logger.info(f"Обрабатываем: {filename} ({original_size / 1024:.1f} KiB)")
                
                optimized_images = optimizer.optimize_category_icon(file_path)
                if optimized_images:
                    # Создаем директорию для оптимизированных иконок
                    optimized_dir = os.path.join(category_icons_dir, 'optimized')
                    saved_files = optimizer.save_optimized_images(optimized_images, optimized_dir)
                    
                    # Вычисляем экономию
                    total_optimized_size = sum(os.path.getsize(f) for f in saved_files)
                    savings = original_size - total_optimized_size
                    total_savings += savings
                    processed_files += 1
                    
                    logger.info(f"✅ {filename}: экономия {savings / 1024:.1f} KiB")
    
    # 3. Оптимизируем статические изображения
    logger.info("🖼️ Оптимизируем статические изображения...")
    static_img_dir = os.path.join(static_dir, 'img')
    if os.path.exists(static_img_dir):
        for filename in os.listdir(static_img_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                file_path = os.path.join(static_img_dir, filename)
                original_size = os.path.getsize(file_path)
                
                logger.info(f"Обрабатываем: {filename} ({original_size / 1024:.1f} KiB)")
                
                optimized_images = optimizer.optimize_static_image(file_path)
                if optimized_images:
                    # Создаем директорию для оптимизированных изображений
                    optimized_dir = os.path.join(static_img_dir, 'optimized')
                    saved_files = optimizer.save_optimized_images(optimized_images, optimized_dir)
                    
                    # Вычисляем экономию
                    total_optimized_size = sum(os.path.getsize(f) for f in saved_files)
                    savings = original_size - total_optimized_size
                    total_savings += savings
                    processed_files += 1
                    
                    logger.info(f"✅ {filename}: экономия {savings / 1024:.1f} KiB")
    
    # 4. Специальная оптимизация для noise.png
    noise_path = os.path.join(static_dir, 'img', 'noise.png')
    if os.path.exists(noise_path):
        logger.info("🎨 Специальная оптимизация noise.png...")
        original_size = os.path.getsize(noise_path)
        
        # Создаем сильно оптимизированную версию
        optimized_images = optimizer.optimize_static_image(noise_path)
        if optimized_images:
            optimized_dir = os.path.join(static_dir, 'img', 'optimized')
            saved_files = optimizer.save_optimized_images(optimized_images, optimized_dir)
            
            total_optimized_size = sum(os.path.getsize(f) for f in saved_files)
            savings = original_size - total_optimized_size
            total_savings += savings
            processed_files += 1
            
            logger.info(f"✅ noise.png: экономия {savings / 1024:.1f} KiB")
    
    # Итоговая статистика
    logger.info("=" * 50)
    logger.info("📊 ИТОГОВАЯ СТАТИСТИКА ОПТИМИЗАЦИИ")
    logger.info("=" * 50)
    logger.info(f"Обработано файлов: {processed_files}")
    logger.info(f"Общая экономия: {total_savings / 1024:.1f} KiB ({total_savings / (1024*1024):.2f} MB)")
    logger.info(f"Процент экономии: {(total_savings / (total_savings + sum(os.path.getsize(f) for f in [os.path.join(media_dir, 'products', 'optimized'), os.path.join(media_dir, 'category_icons', 'optimized'), os.path.join(static_dir, 'img', 'optimized')] if os.path.exists(f)) * 100)):.1f}%")
    
    return {
        'processed_files': processed_files,
        'total_savings': total_savings,
        'optimized_directories': [
            os.path.join(media_dir, 'products', 'optimized'),
            os.path.join(media_dir, 'category_icons', 'optimized'),
            os.path.join(static_dir, 'img', 'optimized')
        ]
    }

if __name__ == '__main__':
    try:
        result = optimize_all_images()
        print(f"\n🎉 Оптимизация завершена!")
        print(f"Обработано файлов: {result['processed_files']}")
        print(f"Общая экономия: {result['total_savings'] / 1024:.1f} KiB")
    except Exception as e:
        logger.error(f"Ошибка при оптимизации: {e}")
        sys.exit(1)
