#!/usr/bin/env python3
"""
Умный скрипт для оптимизации изображений товаров TwoComms
Обрабатывает только оригинальные файлы, избегая дублирования
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

def is_original_file(file_path):
    """Проверяет, является ли файл оригинальным (не оптимизированным)"""
    file_name = file_path.name.lower()
    # Исключаем уже оптимизированные файлы
    exclude_patterns = [
        '_optimized', '_320w', '_640w', '_768w', '_1024w', '_1280w', '_1920w',
        '.webp', '_mobile', '_tablet', '_desktop', '_4k'
    ]
    return not any(pattern in file_name for pattern in exclude_patterns)

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
                img.thumbnail((max_width or img.width, max_height or img.height), Image.Resampling.LANCZOS)
            
            # Сохраняем как WebP
            img.save(output_path, 'WebP', quality=quality, optimize=True)
            return True
    except Exception as e:
        print(f"Ошибка создания WebP {input_path}: {e}")
        return False

def optimize_single_image(input_path, output_dir=None):
    """Оптимизирует одно изображение и создает разные версии"""
    if not os.path.exists(input_path):
        print(f"Файл не найден: {input_path}")
        return None
    
    input_path = Path(input_path)
    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
    
    # Создаем папку если не существует
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
    
    # Создаем оптимизированную версию оригинального размера
    optimized_path = output_dir / f"{input_path.stem}_optimized{input_path.suffix}"
    
    if input_path.suffix.lower() in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
        success = optimize_jpg(input_path, optimized_path)
    else:
        print(f"   ⚠️ Неподдерживаемый формат: {input_path.suffix}")
        return results
    
    if success:
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
    
    # Создаем адаптивные версии только для больших изображений
    if width > 640:  # Создаем адаптивные версии только для изображений больше 640px
        responsive_sizes = [
            (320, "mobile"),      # Мобильные
            (640, "tablet"),      # Планшеты
            (768, "tablet_large"), # Большие планшеты
            (1024, "desktop"),    # Десктоп
        ]
        
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
    
    return results

def find_original_images():
    """Находит все оригинальные изображения для оптимизации"""
    image_dirs = [
        'twocomms/media/products',
        'twocomms/media/product_colors',
        'twocomms/media/payment_screenshots'
    ]
    
    original_images = []
    
    for image_dir in image_dirs:
        if not os.path.exists(image_dir):
            continue
        
        # Находим все JPEG файлы
        for file_path in Path(image_dir).rglob('*.jpg'):
            if file_path.is_file() and is_original_file(file_path):
                # Проверяем размер файла (оптимизируем только большие файлы)
                file_size = get_file_size(file_path)
                if file_size > 100 * 1024:  # Больше 100KB
                    original_images.append(file_path)
    
    return original_images

def main():
    """Главная функция"""
    print("🖼️ Умная оптимизация изображений товаров TwoComms")
    print("=" * 60)
    
    # Проверяем наличие PIL
    try:
        from PIL import Image
    except ImportError:
        print("❌ Требуется установить Pillow: pip install Pillow")
        sys.exit(1)
    
    # Находим оригинальные изображения
    original_images = find_original_images()
    
    if not original_images:
        print("❌ Не найдено оригинальных изображений для оптимизации")
        return
    
    print(f"📁 Найдено {len(original_images)} оригинальных изображений для оптимизации")
    
    total_original = 0
    total_optimized = 0
    total_webp = 0
    total_savings = 0
    
    results = {}
    
    for i, image_path in enumerate(original_images, 1):
        print(f"\n[{i}/{len(original_images)}]")
        result = optimize_single_image(image_path)
        if result:
            results[str(image_path)] = result
            total_original += result['original']['size']
            
            if 'optimized' in result:
                total_optimized += result['optimized']['size']
                total_savings += result['optimized']['savings']
            
            if 'webp' in result:
                total_webp += result['webp']['size']
    
    print("\n" + "=" * 60)
    print("📊 ОБЩАЯ СТАТИСТИКА")
    print("=" * 60)
    print(f"Обработано изображений: {len(original_images)}")
    print(f"Оригинальный размер: {format_size(total_original)}")
    print(f"Оптимизированный: {format_size(total_optimized)}")
    print(f"WebP версии: {format_size(total_webp)}")
    print(f"Общая экономия: {format_size(total_savings)} ({total_savings/total_original*100:.1f}%)")
    
    print("\n💡 Рекомендации:")
    print("1. Используйте WebP версии для современных браузеров")
    print("2. Используйте адаптивные версии для разных размеров экранов")
    print("3. Настройте lazy loading для изображений товаров")
    print("4. Обновите шаблоны для использования оптимизированных версий")
    
    return results

if __name__ == "__main__":
    main()
