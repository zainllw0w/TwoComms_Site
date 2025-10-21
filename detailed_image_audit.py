#!/usr/bin/env python3
"""
Детальный аудит всех изображений в проекте
"""
from PIL import Image
from pathlib import Path
import json

def audit_images():
    media_dir = Path('twocomms/media')
    results = {
        'total_count': 0,
        'total_size_mb': 0,
        'by_format': {},
        'unoptimized': [],
        'missing_webp': [],
        'oversized': [],
        'details': []
    }
    
    print("🔍 Сканирование изображений...\n")
    
    for img_path in media_dir.rglob('*'):
        if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif']:
            try:
                size_bytes = img_path.stat().st_size
                size_mb = size_bytes / 1024 / 1024
                
                with Image.open(img_path) as img:
                    width, height = img.size
                    format_name = img.format
                    
                    info = {
                        'path': str(img_path.relative_to('twocomms')),
                        'size_mb': round(size_mb, 2),
                        'width': width,
                        'height': height,
                        'format': format_name,
                        'pixels': width * height
                    }
                    
                    results['details'].append(info)
                    results['total_count'] += 1
                    results['total_size_mb'] += size_mb
                    
                    # По форматам
                    if format_name not in results['by_format']:
                        results['by_format'][format_name] = {'count': 0, 'size_mb': 0}
                    results['by_format'][format_name]['count'] += 1
                    results['by_format'][format_name]['size_mb'] += size_mb
                    
                    # Проверки
                    if size_mb > 0.5:  # >500KB
                        results['unoptimized'].append(info)
                    
                    if size_mb > 1.0:  # >1MB
                        results['oversized'].append(info)
                    
                    # Проверить WebP версию
                    if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                        webp_path = img_path.with_suffix('.webp')
                        if not webp_path.exists():
                            results['missing_webp'].append(info['path'])
                            
            except Exception as e:
                print(f"⚠️ Ошибка при обработке {img_path}: {e}")
    
    return results

def print_results(results):
    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТЫ АУДИТА ИЗОБРАЖЕНИЙ")
    print("=" * 70)
    
    print(f"\n📊 Общая статистика:")
    print(f"  Всего изображений: {results['total_count']}")
    print(f"  Общий размер: {results['total_size_mb']:.1f} MB")
    
    print(f"\n📁 По форматам:")
    for fmt, data in sorted(results['by_format'].items()):
        print(f"  {fmt}: {data['count']} файлов ({data['size_mb']:.1f} MB)")
    
    print(f"\n🔴 Неоптимизированные изображения (>500KB): {len(results['unoptimized'])}")
    for img in sorted(results['unoptimized'], key=lambda x: x['size_mb'], reverse=True)[:20]:
        print(f"  {img['size_mb']:.2f}MB - {img['path']} ({img['width']}x{img['height']})")
    
    print(f"\n🔴 Очень большие изображения (>1MB): {len(results['oversized'])}")
    for img in sorted(results['oversized'], key=lambda x: x['size_mb'], reverse=True)[:10]:
        print(f"  {img['size_mb']:.2f}MB - {img['path']}")
    
    print(f"\n⚠️ Отсутствует WebP версия: {len(results['missing_webp'])} файлов")
    for path in results['missing_webp'][:10]:
        print(f"  {path}")
    if len(results['missing_webp']) > 10:
        print(f"  ... и ещё {len(results['missing_webp']) - 10}")
    
    # Топ-20 самых больших
    print(f"\n📊 Топ-20 самых больших изображений:")
    for i, img in enumerate(sorted(results['details'], key=lambda x: x['size_mb'], reverse=True)[:20], 1):
        print(f"  {i}. {img['size_mb']:.2f}MB - {img['path']}")
    
    # Сохранить JSON
    with open('artifacts/audit_2025-10-21/images-detailed.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Детальный отчёт сохранён: artifacts/audit_2025-10-21/images-detailed.json")

if __name__ == '__main__':
    results = audit_images()
    print_results(results)
