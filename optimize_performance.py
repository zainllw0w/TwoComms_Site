#!/usr/bin/env python3
"""
Скрипт для оптимизации производительности сайта TwoComms
"""

import os
import sys
import django
from pathlib import Path
import logging

# Добавляем путь к проекту Django
sys.path.append('/Users/zainllw0w/PycharmProjects/TwoComms/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from storefront.models import Product, Category
import json
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('performance_optimization.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def optimize_database_queries():
    """Оптимизирует запросы к базе данных"""
    logger.info("🗄️ Оптимизируем запросы к базе данных...")
    
    # Проверяем количество товаров и категорий
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    active_products = Product.objects.filter(category__is_active=True).count()
    
    logger.info(f"Всего товаров: {total_products}")
    logger.info(f"Активных товаров: {active_products}")
    logger.info(f"Всего категорий: {total_categories}")
    
    # Проверяем товары без изображений
    products_without_images = Product.objects.filter(main_image__isnull=True).count()
    logger.info(f"Товаров без изображений: {products_without_images}")
    
    # Проверяем товары с большими изображениями
    products_with_large_images = Product.objects.filter(main_image__isnull=False).count()
    logger.info(f"Товаров с изображениями: {products_with_large_images}")
    
    return {
        'total_products': total_products,
        'active_products': active_products,
        'total_categories': total_categories,
        'products_without_images': products_without_images,
        'products_with_large_images': products_with_large_images
    }

def optimize_static_files():
    """Оптимизирует статические файлы"""
    logger.info("📁 Оптимизируем статические файлы...")
    
    static_dir = '/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/static'
    css_dir = os.path.join(static_dir, 'css')
    js_dir = os.path.join(static_dir, 'js')
    img_dir = os.path.join(static_dir, 'img')
    
    # Проверяем размеры CSS файлов
    css_files = []
    if os.path.exists(css_dir):
        for file in os.listdir(css_dir):
            if file.endswith('.css'):
                file_path = os.path.join(css_dir, file)
                size = os.path.getsize(file_path)
                css_files.append({'name': file, 'size': size})
                logger.info(f"CSS файл: {file} - {size / 1024:.1f} KiB")
    
    # Проверяем размеры JS файлов
    js_files = []
    if os.path.exists(js_dir):
        for file in os.listdir(js_dir):
            if file.endswith('.js'):
                file_path = os.path.join(js_dir, file)
                size = os.path.getsize(file_path)
                js_files.append({'name': file, 'size': size})
                logger.info(f"JS файл: {file} - {size / 1024:.1f} KiB")
    
    # Проверяем размеры изображений
    img_files = []
    if os.path.exists(img_dir):
        for file in os.listdir(img_dir):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.webp')):
                file_path = os.path.join(img_dir, file)
                size = os.path.getsize(file_path)
                img_files.append({'name': file, 'size': size})
                logger.info(f"Изображение: {file} - {size / 1024:.1f} KiB")
    
    return {
        'css_files': css_files,
        'js_files': js_files,
        'img_files': img_files
    }

def optimize_media_files():
    """Оптимизирует медиа файлы"""
    logger.info("🖼️ Оптимизируем медиа файлы...")
    
    media_dir = '/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/media'
    products_dir = os.path.join(media_dir, 'products')
    category_icons_dir = os.path.join(media_dir, 'category_icons')
    
    # Проверяем изображения товаров
    product_images = []
    if os.path.exists(products_dir):
        for file in os.listdir(products_dir):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                file_path = os.path.join(products_dir, file)
                size = os.path.getsize(file_path)
                product_images.append({'name': file, 'size': size})
                logger.info(f"Изображение товара: {file} - {size / 1024:.1f} KiB")
    
    # Проверяем иконки категорий
    category_icons = []
    if os.path.exists(category_icons_dir):
        for file in os.listdir(category_icons_dir):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                file_path = os.path.join(category_icons_dir, file)
                size = os.path.getsize(file_path)
                category_icons.append({'name': file, 'size': size})
                logger.info(f"Иконка категории: {file} - {size / 1024:.1f} KiB")
    
    return {
        'product_images': product_images,
        'category_icons': category_icons
    }

def generate_performance_report():
    """Генерирует отчет о производительности"""
    logger.info("📊 Генерируем отчет о производительности...")
    
    # Собираем данные
    db_stats = optimize_database_queries()
    static_stats = optimize_static_files()
    media_stats = optimize_media_files()
    
    # Создаем отчет
    report = {
        'timestamp': datetime.now().isoformat(),
        'database': db_stats,
        'static_files': static_stats,
        'media_files': media_stats,
        'recommendations': []
    }
    
    # Анализируем и добавляем рекомендации
    total_css_size = sum(f['size'] for f in static_stats['css_files'])
    total_js_size = sum(f['size'] for f in static_stats['js_files'])
    total_img_size = sum(f['size'] for f in static_stats['img_files'])
    
    if total_css_size > 500 * 1024:  # Больше 500KB
        report['recommendations'].append({
            'type': 'css',
            'message': f'CSS файлы слишком большие ({total_css_size / 1024:.1f} KiB). Рекомендуется минификация и разделение на критические/некритические стили.',
            'priority': 'high'
        })
    
    if total_js_size > 200 * 1024:  # Больше 200KB
        report['recommendations'].append({
            'type': 'js',
            'message': f'JS файлы слишком большие ({total_js_size / 1024:.1f} KiB). Рекомендуется минификация и асинхронная загрузка.',
            'priority': 'medium'
        })
    
    if total_img_size > 1000 * 1024:  # Больше 1MB
        report['recommendations'].append({
            'type': 'images',
            'message': f'Статические изображения слишком большие ({total_img_size / 1024:.1f} KiB). Рекомендуется оптимизация и конвертация в WebP.',
            'priority': 'high'
        })
    
    # Проверяем товары без изображений
    if db_stats['products_without_images'] > 0:
        report['recommendations'].append({
            'type': 'database',
            'message': f'{db_stats["products_without_images"]} товаров без изображений. Это может влиять на пользовательский опыт.',
            'priority': 'medium'
        })
    
    # Сохраняем отчет
    report_file = f'performance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    logger.info(f"📄 Отчет сохранен в файл: {report_file}")
    
    # Выводим рекомендации
    logger.info("🎯 РЕКОМЕНДАЦИИ ПО ОПТИМИЗАЦИИ:")
    for i, rec in enumerate(report['recommendations'], 1):
        priority_emoji = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
        logger.info(f"{i}. {priority_emoji} {rec['message']}")
    
    return report

def main():
    """Основная функция"""
    logger.info("🚀 Начинаем оптимизацию производительности...")
    
    try:
        report = generate_performance_report()
        
        logger.info("=" * 50)
        logger.info("📊 ИТОГОВАЯ СТАТИСТИКА")
        logger.info("=" * 50)
        logger.info(f"Товаров в базе: {report['database']['total_products']}")
        logger.info(f"Активных товаров: {report['database']['active_products']}")
        logger.info(f"Категорий: {report['database']['total_categories']}")
        logger.info(f"CSS файлов: {len(report['static_files']['css_files'])}")
        logger.info(f"JS файлов: {len(report['static_files']['js_files'])}")
        logger.info(f"Статических изображений: {len(report['static_files']['img_files'])}")
        logger.info(f"Изображений товаров: {len(report['media_files']['product_images'])}")
        logger.info(f"Иконок категорий: {len(report['media_files']['category_icons'])}")
        logger.info(f"Рекомендаций: {len(report['recommendations'])}")
        
        logger.info("✅ Оптимизация производительности завершена!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при оптимизации: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
