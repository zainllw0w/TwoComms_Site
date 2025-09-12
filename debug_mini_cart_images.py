#!/usr/bin/env python3
"""
Скрипт для отладки проблем с изображениями в мини-корзине
"""

import os
import sys
import django
from pathlib import Path

# Добавляем путь к проекту
sys.path.append('/Users/zainllw0w/PycharmProjects/TwoComms/twocomms')

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from storefront.models import Product
from productcolors.models import ProductColorVariant
from django.conf import settings

def check_image_paths():
    """Проверяем пути к изображениям товаров"""
    print("=== ПРОВЕРКА ПУТЕЙ К ИЗОБРАЖЕНИЯМ ===\n")
    
    # Получаем несколько товаров для тестирования
    products = Product.objects.filter(main_image__isnull=False)[:5]
    
    for product in products:
        print(f"Товар: {product.title}")
        print(f"ID: {product.id}")
        
        # Проверяем основное изображение
        if product.main_image:
            main_image_path = product.main_image.path
            print(f"  Основное изображение: {product.main_image.url}")
            print(f"  Путь к файлу: {main_image_path}")
            print(f"  Файл существует: {os.path.exists(main_image_path)}")
            
            # Проверяем оптимизированные версии
            base_path = Path(main_image_path)
            base_name = base_path.stem
            optimized_dir = base_path.parent / "optimized"
            
            webp_path = optimized_dir / f"{base_name}.webp"
            avif_path = optimized_dir / f"{base_name}.avif"
            
            print(f"  WebP версия: {webp_path} - {webp_path.exists()}")
            print(f"  AVIF версия: {avif_path} - {avif_path.exists()}")
            
            # Проверяем адаптивные версии
            for size in [320, 640, 768, 1024]:
                webp_responsive = optimized_dir / f"{base_name}_{size}w.webp"
                avif_responsive = optimized_dir / f"{base_name}_{size}w.avif"
                print(f"  WebP {size}w: {webp_responsive.exists()}")
                print(f"  AVIF {size}w: {avif_responsive.exists()}")
        
        # Проверяем display_image
        if product.display_image:
            display_image_path = product.display_image.path
            print(f"  Display изображение: {product.display_image.url}")
            print(f"  Путь к файлу: {display_image_path}")
            print(f"  Файл существует: {os.path.exists(display_image_path)}")
        
        # Проверяем цветовые варианты
        color_variants = ProductColorVariant.objects.filter(product=product)
        if color_variants.exists():
            print(f"  Цветовые варианты: {color_variants.count()}")
            for variant in color_variants[:2]:  # Показываем только первые 2
                if variant.images.exists():
                    first_image = variant.images.first()
                    print(f"    Цвет {variant.color.name}: {first_image.image.url}")
                    print(f"    Файл существует: {os.path.exists(first_image.image.path)}")
        
        print("-" * 50)

def check_media_settings():
    """Проверяем настройки медиа"""
    print("\n=== НАСТРОЙКИ МЕДИА ===\n")
    print(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
    print(f"MEDIA_URL: {settings.MEDIA_URL}")
    print(f"MEDIA_ROOT существует: {os.path.exists(settings.MEDIA_ROOT)}")
    
    # Проверяем папку optimized
    optimized_dir = Path(settings.MEDIA_ROOT) / "optimized"
    print(f"Папка optimized: {optimized_dir}")
    print(f"Папка optimized существует: {optimized_dir.exists()}")
    
    if optimized_dir.exists():
        # Считаем файлы в папке optimized
        webp_files = list(optimized_dir.rglob("*.webp"))
        avif_files = list(optimized_dir.rglob("*.avif"))
        print(f"WebP файлов: {len(webp_files)}")
        print(f"AVIF файлов: {len(avif_files)}")
        
        if webp_files:
            print(f"Пример WebP файла: {webp_files[0]}")
        if avif_files:
            print(f"Пример AVIF файла: {avif_files[0]}")

def test_optimized_image_tag():
    """Тестируем тег optimized_image"""
    print("\n=== ТЕСТ ТЕГА OPTIMIZED_IMAGE ===\n")
    
    from storefront.templatetags.responsive_images import optimized_image
    
    # Получаем товар с изображением
    product = Product.objects.filter(main_image__isnull=False).first()
    if not product:
        print("Нет товаров с изображениями для тестирования")
        return
    
    print(f"Тестируем товар: {product.title}")
    print(f"Изображение: {product.main_image.url}")
    
    # Тестируем тег
    result = optimized_image(
        image_path=product.main_image.url,
        alt_text=product.title,
        class_name="test-class",
        width=48,
        height=48
    )
    
    print("Результат тега optimized_image:")
    for key, value in result.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    try:
        check_image_paths()
        check_media_settings()
        test_optimized_image_tag()
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
