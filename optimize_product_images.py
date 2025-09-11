#!/usr/bin/env python3
"""
Скрипт для оптимизации изображений товаров TwoComms
Создает адаптивные версии и WebP форматы для всех изображений товаров
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageOps
import subprocess

def get_file_size(file_path):
    """Получает размер файла в байтах"""
    return os.path.getsize(file_path)

def format_size(size_bytes):
    """Форматирует размер в читаемый вид"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KiB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MiB"

def optimize_jpg(input_path, output_path, quality=85, max_width=None, max_height=None):
    """Оптимизирует JPEG изображение"""
    try:
        with Image.open(input_path) as img:
            # Конвертируем в RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Изменяем размер если нужно
            if max_width or max_height:
                img.thumbnail((max_width or img.width, max_height or img.height), Image.Resampling.LANCZOS)
            
            # Сохраняем с оптимизацией
            img.save(output_path, 'JPEG', quality=quality, optimize=True, progressive=True)
            return True
    except Exception as e:
        print(f"Ошибка оптимизации JPEG {input_path}: {e}")
        return False

def create_webp(input_path, output_path, quality=85, max_width=None, max_height=None):
    """Создает WebP версию изображения"""
    try:
        with Image.open(input_path) as img:
            # Изменяем размер если нужно
            if max_width or max_height:
                img.thumbnail((max_width or img.height, max_height or img.height), Image.Resampling.LANCZOS)
            
            # Сохраняем как WebP
            img.save(output_path, 'WebP', quality=quality, optimize=True)
            return True
    except Exception as e:
        print(f"Ошибка создания WebP {input_path}: {e}")
        return False

def create_responsive_versions(input_path, output_dir):
    """Создает адаптивные версии изображения для разных размеров экранов"""
    if not os.path.exists(input_path):
        return {}
    
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    original_size = get_file_size(input_path)
    results = {
        'original': {
            'path': str(input_path),
            'size': original_size,
            'format': input_path.suffix.lower()
        }
    }
    
    print(f"🖼️ Оптимизация: {input_path.name}")
    print(f"   Оригинал: {format_size(original_size)}")
    
    # Определяем тип изображения
    try:
        with Image.open(input_path) as img:
            width, height = img.size
            print(f"   Размер: {width}x{height} пикселей")
    except Exception as e:
        print(f"   ❌ Ошибка чтения изображения: {e}")
        return results
    
    # Размеры для адаптивных изображений (ширина экрана)
    responsive_sizes = [
        (320, "mobile"),      # Мобильные
        (640, "tablet"),      # Планшеты
        (768, "tablet_large"), # Большие планшеты
        (1024, "desktop"),    # Десктоп
        (1280, "desktop_large"), # Большие экраны
        (1920, "4k")          # 4K экраны
    ]
    
    # Создаем адаптивные версии
    for size, name in responsive_sizes:
        if width > size:  # Создаем только если оригинал больше
            # JPEG версия
            jpg_path = output_dir / f"{input_path.stem}_{size}w.jpg"
            if optimize_jpg(input_path, jpg_path, max_width=size):
                jpg_size = get_file_size(jpg_path)
                results[f'jpg_{size}w'] = {
                    'path': str(jpg_path),
                    'size': jpg_size,
                    'width': size
                }
                print(f"   ✅ {size}w JPEG: {format_size(jpg_size)}")
            
            # WebP версия
            webp_path = output_dir / f"{input_path.stem}_{size}w.webp"
            if create_webp(input_path, webp_path, max_width=size):
                webp_size = get_file_size(webp_path)
                results[f'webp_{size}w'] = {
                    'path': str(webp_path),
                    'size': webp_size,
                    'width': size
                }
                print(f"   ✅ {size}w WebP: {format_size(webp_size)}")
    
    # Создаем оптимизированную версию оригинального размера
    optimized_path = output_dir / f"{input_path.stem}_optimized{input_path.suffix}"
    if optimize_jpg(input_path, optimized_path):
        optimized_size = get_file_size(optimized_path)
        savings = original_size - optimized_size
        savings_percent = (savings / original_size) * 100
        
        results['optimized'] = {
            'path': str(optimized_path),
            'size': optimized_size,
            'savings': savings,
            'savings_percent': savings_percent
        }
        
        print(f"   ✅ Оптимизировано: {format_size(optimized_size)} (экономия {format_size(savings)}, {savings_percent:.1f}%)")
    
    # Создаем WebP версию оригинального размера
    webp_path = output_dir / f"{input_path.stem}.webp"
    if create_webp(input_path, webp_path):
        webp_size = get_file_size(webp_path)
        webp_savings = original_size - webp_size
        webp_savings_percent = (webp_savings / original_size) * 100
        
        results['webp'] = {
            'path': str(webp_path),
            'size': webp_size,
            'savings': webp_savings,
            'savings_percent': webp_savings_percent
        }
        
        print(f"   ✅ WebP: {format_size(webp_size)} (экономия {format_size(webp_savings)}, {webp_savings_percent:.1f}%)")
    
    return results

def optimize_all_product_images():
    """Оптимизирует все изображения товаров"""
    print("🖼️ Оптимизация изображений товаров TwoComms")
    print("=" * 60)
    
    # Пути к папкам с изображениями
    image_dirs = [
        'twocomms/media/products',
        'twocomms/media/product_colors',
        'twocomms/media/payment_screenshots'
    ]
    
    total_original = 0
    total_optimized = 0
    total_webp = 0
    total_savings = 0
    
    results = {}
    
    for image_dir in image_dirs:
        if not os.path.exists(image_dir):
            print(f"⚠️ Папка не найдена: {image_dir}")
            continue
        
        print(f"\n📁 Обработка папки: {image_dir}")
        
        # Находим все JPEG файлы
        for file_path in Path(image_dir).rglob('*.jpg'):
            if file_path.is_file():
                # Создаем папку для оптимизированных версий
                output_dir = file_path.parent / 'optimized'
                
                result = create_responsive_versions(file_path, output_dir)
                if result:
                    results[str(file_path)] = result
                    total_original += result['original']['size']
                    
                    if 'optimized' in result:
                        total_optimized += result['optimized']['size']
                        total_savings += result['optimized']['savings']
                    
                    if 'webp' in result:
                        total_webp += result['webp']['size']
    
    print("\n" + "=" * 60)
    print("📊 ОБЩАЯ СТАТИСТИКА")
    print("=" * 60)
    print(f"Оригинальный размер: {format_size(total_original)}")
    print(f"Оптимизированный: {format_size(total_optimized)}")
    print(f"WebP версии: {format_size(total_webp)}")
    print(f"Общая экономия: {format_size(total_savings)} ({total_savings/total_original*100:.1f}%)")
    
    print("\n💡 Рекомендации:")
    print("1. Используйте адаптивные изображения с srcset")
    print("2. Используйте WebP версии для современных браузеров")
    print("3. Настройте lazy loading для изображений товаров")
    print("4. Используйте правильные размеры для контейнеров")
    
    return results

def main():
    """Главная функция"""
    # Проверяем наличие PIL
    try:
        from PIL import Image
    except ImportError:
        print("❌ Требуется установить Pillow: pip install Pillow")
        sys.exit(1)
    
    return optimize_all_product_images()

if __name__ == "__main__":
    main()
