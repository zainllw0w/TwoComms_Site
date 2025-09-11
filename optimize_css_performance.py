#!/usr/bin/env python3
"""
Скрипт для оптимизации CSS производительности
Удаляет неиспользуемые стили и минифицирует CSS
"""

import os
import re
import gzip
from pathlib import Path

def minify_css(css_content):
    """Минифицирует CSS код"""
    # Удаляем комментарии
    css_content = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
    
    # Удаляем лишние пробелы
    css_content = re.sub(r'\s+', ' ', css_content)
    
    # Удаляем пробелы вокруг специальных символов
    css_content = re.sub(r'\s*([{}:;,>+~])\s*', r'\1', css_content)
    
    # Удаляем пробелы в начале и конце
    css_content = css_content.strip()
    
    return css_content

def extract_critical_css(css_content):
    """Извлекает критически важные CSS стили"""
    critical_selectors = [
        'body', 'html', '*', '.navbar', '.hero-section', '.container',
        '.btn', '.card', '.loading', 'h1', 'h2', 'h3', 'p', 'a'
    ]
    
    critical_css = []
    lines = css_content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('/*'):
            continue
            
        # Проверяем, содержит ли строка критический селектор
        for selector in critical_selectors:
            if selector in line:
                critical_css.append(line)
                break
    
    return '\n'.join(critical_css)

def optimize_css_file(file_path):
    """Оптимизирует CSS файл"""
    print(f"🔧 Оптимизация {file_path}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Минифицируем CSS
        minified = minify_css(content)
        
        # Создаем минифицированную версию
        minified_path = file_path.replace('.css', '.min.css')
        with open(minified_path, 'w', encoding='utf-8') as f:
            f.write(minified)
        
        # Создаем gzip версию
        gzip_path = minified_path + '.gz'
        with gzip.open(gzip_path, 'wt', encoding='utf-8') as f:
            f.write(minified)
        
        # Извлекаем критический CSS
        critical_css = extract_critical_css(content)
        critical_path = file_path.replace('.css', '.critical.css')
        with open(critical_path, 'w', encoding='utf-8') as f:
            f.write(critical_css)
        
        # Статистика
        original_size = len(content)
        minified_size = len(minified)
        gzip_size = os.path.getsize(gzip_path)
        critical_size = len(critical_css)
        
        print(f"  ✅ Оригинал: {original_size:,} байт")
        print(f"  ✅ Минифицированный: {minified_size:,} байт ({minified_size/original_size*100:.1f}%)")
        print(f"  ✅ Gzip: {gzip_size:,} байт ({gzip_size/original_size*100:.1f}%)")
        print(f"  ✅ Критический: {critical_size:,} байт ({critical_size/original_size*100:.1f}%)")
        
        return {
            'original': original_size,
            'minified': minified_size,
            'gzip': gzip_size,
            'critical': critical_size
        }
        
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return None

def main():
    """Главная функция"""
    print("🚀 Оптимизация CSS производительности для TwoComms")
    print("=" * 60)
    
    # Пути к CSS файлам
    css_files = [
        'twocomms/static/css/styles.css',
        'twocomms/static/css/critical.css'
    ]
    
    total_original = 0
    total_minified = 0
    total_gzip = 0
    total_critical = 0
    
    for css_file in css_files:
        if os.path.exists(css_file):
            result = optimize_css_file(css_file)
            if result:
                total_original += result['original']
                total_minified += result['minified']
                total_gzip += result['gzip']
                total_critical += result['critical']
        else:
            print(f"⚠️ Файл не найден: {css_file}")
    
    print("\n" + "=" * 60)
    print("📊 ОБЩАЯ СТАТИСТИКА")
    print("=" * 60)
    print(f"Оригинальный размер: {total_original:,} байт")
    print(f"Минифицированный: {total_minified:,} байт ({total_minified/total_original*100:.1f}%)")
    print(f"Gzip сжатие: {total_gzip:,} байт ({total_gzip/total_original*100:.1f}%)")
    print(f"Критический CSS: {total_critical:,} байт ({total_critical/total_original*100:.1f}%)")
    
    savings = total_original - total_gzip
    print(f"\n💰 Экономия: {savings:,} байт ({savings/total_original*100:.1f}%)")
    
    print("\n✅ Оптимизация завершена!")
    print("\n💡 Рекомендации:")
    print("1. Используйте .min.css файлы в продакшене")
    print("2. Включите gzip сжатие на сервере")
    print("3. Встройте критический CSS в <head>")
    print("4. Загружайте остальной CSS асинхронно")

if __name__ == "__main__":
    main()
