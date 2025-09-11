#!/usr/bin/env python3
"""
Скрипт для оптимизации изображений TwoComms
Сжимает изображения и создает WebP/AVIF версии
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

def optimize_png(input_path, output_path, quality=85, max_width=None, max_height=None):
    """Оптимизирует PNG изображение"""
    try:
        with Image.open(input_path) as img:
            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'LA', 'P'):
                # Создаем белый фон для прозрачных изображений
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Изменяем размер если нужно
            if max_width or max_height:
                img.thumbnail((max_width or img.width, max_height or img.height), Image.Resampling.LANCZOS)
            
            # Сохраняем с оптимизацией
            img.save(output_path, 'PNG', optimize=True, compress_level=9)
            return True
    except Exception as e:
        print(f"Ошибка оптимизации PNG {input_path}: {e}")
        return False

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

def optimize_image(input_path, output_dir=None):
    """Оптимизирует изображение и создает разные версии"""
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
    
    # Создаем оптимизированную версию
    optimized_path = output_dir / f"{input_path.stem}_optimized{input_path.suffix}"
    
    if input_path.suffix.lower() in ['.png', '.PNG']:
        success = optimize_png(input_path, optimized_path)
    elif input_path.suffix.lower() in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
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
    
    # Создаем WebP версию
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
    
    # Создаем адаптивные версии для иконок (если размер больше 24x24)
    if width > 24 or height > 24:
        # Создаем версию 24x24 для иконок
        icon_path = output_dir / f"{input_path.stem}_24x24{input_path.suffix}"
        if input_path.suffix.lower() in ['.png', '.PNG']:
            optimize_png(input_path, icon_path, max_width=24, max_height=24)
        elif input_path.suffix.lower() in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
            optimize_jpg(input_path, icon_path, max_width=24, max_height=24)
        
        if os.path.exists(icon_path):
            icon_size = get_file_size(icon_path)
            icon_savings = original_size - icon_size
            icon_savings_percent = (icon_savings / original_size) * 100
            
            results['icon_24x24'] = {
                'path': str(icon_path),
                'size': icon_size,
                'savings': icon_savings,
                'savings_percent': icon_savings_percent
            }
            
            print(f"   ✅ 24x24: {format_size(icon_size)} (экономия {format_size(icon_savings)}, {icon_savings_percent:.1f}%)")
    
    return results

def main():
    """Главная функция"""
    print("🖼️ Оптимизация изображений TwoComms")
    print("=" * 60)
    
    # Список изображений для оптимизации
    images_to_optimize = [
        'twocomms/twocomms_django_theme/static/img/noise.png',
        'twocomms/media/category_icons/free-icon-tshirt-1867631.png',
        'twocomms/twocomms_django_theme/static/img/bg_blur_1.png',
        'twocomms/twocomms_django_theme/static/img/vignette.png'
    ]
    
    total_original = 0
    total_optimized = 0
    total_webp = 0
    total_savings = 0
    
    results = {}
    
    for image_path in images_to_optimize:
        if os.path.exists(image_path):
            result = optimize_image(image_path)
            if result:
                results[image_path] = result
                total_original += result['original']['size']
                
                if 'optimized' in result:
                    total_optimized += result['optimized']['size']
                    total_savings += result['optimized']['savings']
                
                if 'webp' in result:
                    total_webp += result['webp']['size']
        else:
            print(f"⚠️ Файл не найден: {image_path}")
    
    print("\n" + "=" * 60)
    print("📊 ОБЩАЯ СТАТИСТИКА")
    print("=" * 60)
    print(f"Оригинальный размер: {format_size(total_original)}")
    print(f"Оптимизированный: {format_size(total_optimized)}")
    print(f"WebP версии: {format_size(total_webp)}")
    print(f"Общая экономия: {format_size(total_savings)} ({total_savings/total_original*100:.1f}%)")
    
    print("\n💡 Рекомендации:")
    print("1. Используйте WebP версии для современных браузеров")
    print("2. Используйте адаптивные версии для иконок")
    print("3. Настройте fallback на оригинальные форматы")
    print("4. Включите сжатие изображений на сервере")
    
    return results

if __name__ == "__main__":
    # Проверяем наличие PIL
    try:
        from PIL import Image
    except ImportError:
        print("❌ Требуется установить Pillow: pip install Pillow")
        sys.exit(1)
    
    main()
