#!/usr/bin/env python3
"""
Image Optimization Script для TwoComms
Оптимизирует все изображения в media/products
"""
import os
import sys
from PIL import Image
from pathlib import Path

def get_image_size_kb(path):
    """Получить размер файла в KB"""
    return os.path.getsize(path) / 1024

def optimize_image(image_path, quality=85, max_width=1920, max_height=1920):
    """
    Оптимизировать одно изображение
    
    Args:
        image_path: путь к изображению
        quality: качество JPEG (0-100)
        max_width: максимальная ширина
        max_height: максимальная высота
    
    Returns:
        dict с результатами оптимизации
    """
    try:
        original_size = get_image_size_kb(image_path)
        
        # Открыть изображение
        img = Image.open(image_path)
        original_format = img.format
        original_dimensions = img.size
        
        # Конвертировать в RGB если необходимо
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if 'A' in img.mode:
                bg.paste(img, mask=img.split()[-1])
            else:
                bg.paste(img)
            img = bg
        
        # Изменить размер если слишком большое
        resized = False
        if img.size[0] > max_width or img.size[1] > max_height:
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            resized = True
        
        # Сохранить оптимизированный JPEG
        img.save(
            image_path,
            'JPEG',
            quality=quality,
            optimize=True,
            progressive=True
        )
        
        # Создать WebP версию
        webp_path = os.path.splitext(image_path)[0] + '.webp'
        img.save(webp_path, 'WEBP', quality=quality, method=6)
        
        new_size = get_image_size_kb(image_path)
        webp_size = get_image_size_kb(webp_path)
        
        return {
            'success': True,
            'original_size': original_size,
            'new_size': new_size,
            'webp_size': webp_size,
            'saved': original_size - new_size,
            'saved_percent': ((original_size - new_size) / original_size * 100) if original_size > 0 else 0,
            'resized': resized,
            'original_dimensions': original_dimensions,
            'new_dimensions': img.size,
            'webp_created': True
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def format_size(kb):
    """Форматировать размер в читаемый вид"""
    if kb < 1024:
        return f"{kb:.1f} KB"
    else:
        return f"{kb/1024:.1f} MB"

def main():
    """Основная функция"""
    print("🖼️  Image Optimization для TwoComms")
    print("=" * 60)
    
    # Путь к media/products
    base_dir = Path(__file__).parent
    media_dir = base_dir / 'twocomms' / 'media' / 'products'
    
    if not media_dir.exists():
        print(f"❌ Папка не найдена: {media_dir}")
        sys.exit(1)
    
    print(f"📁 Папка: {media_dir}\n")
    
    # Найти все изображения
    extensions = ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG']
    images = []
    for ext in extensions:
        images.extend(media_dir.rglob(ext))
    
    if not images:
        print("ℹ️  Изображения не найдены")
        sys.exit(0)
    
    print(f"📊 Найдено изображений: {len(images)}\n")
    
    # Спросить подтверждение
    response = input("Продолжить оптимизацию? (y/n): ").lower()
    if response != 'y':
        print("Отменено")
        sys.exit(0)
    
    # Оптимизировать каждое изображение
    total_images = len(images)
    optimized = 0
    failed = 0
    total_saved_kb = 0
    
    for i, image_path in enumerate(images, 1):
        print(f"\n[{i}/{total_images}] {image_path.name}")
        print(f"  Размер: {format_size(get_image_size_kb(str(image_path)))}", end=" → ")
        
        result = optimize_image(str(image_path), quality=85)
        
        if result['success']:
            print(f"{format_size(result['new_size'])}")
            print(f"  ✅ Сохранено: {format_size(result['saved'])} ({result['saved_percent']:.1f}%)")
            print(f"  📐 Размер: {result['original_dimensions']} → {result['new_dimensions']}")
            print(f"  🌐 WebP: {format_size(result['webp_size'])}")
            
            optimized += 1
            total_saved_kb += result['saved']
        else:
            print(f"\n  ❌ Ошибка: {result['error']}")
            failed += 1
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 ИТОГИ:")
    print(f"  ✅ Оптимизировано: {optimized}/{total_images}")
    print(f"  ❌ Ошибок: {failed}")
    print(f"  💾 Всего сохранено: {format_size(total_saved_kb)}")
    
    if optimized > 0:
        avg_saved = (total_saved_kb / optimized)
        print(f"  📉 Средняя экономия: {format_size(avg_saved)} ({(avg_saved/800*100):.1f}% от среднего)")
    
    print("\n✅ Оптимизация завершена!")
    print("\n💡 Следующие шаги:")
    print("  1. Проверьте качество оптимизированных изображений")
    print("  2. Обновите шаблоны для использования WebP с fallback на JPEG")
    print("  3. Настройте CDN для раздачи изображений")
    
    sys.exit(0)

if __name__ == '__main__':
    main()

