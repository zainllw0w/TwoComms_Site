#!/usr/bin/env python3
"""
Скрипт для анализа пользовательских панелей и определения неиспользуемых элементов
"""

import re
import os
from pathlib import Path

def find_element_usage():
    """Находит все элементы пользовательских панелей и их использование"""
    
    # Пути к файлам
    base_html = Path("twocomms/twocomms_django_theme/templates/base.html")
    header_html = Path("twocomms/twocomms_django_theme/templates/partials/header.html")
    main_js = Path("twocomms/twocomms_django_theme/static/js/main.js")
    
    # Паттерны для поиска
    id_pattern = r'id="([^"]*)"'
    getElementById_pattern = r'getElementById\(["\']([^"\']*)["\']\)'
    
    elements = {}
    usage = set()
    
    print("🔍 Анализ пользовательских панелей...")
    print("=" * 50)
    
    # 1. Находим все элементы с ID в HTML файлах
    for file_path in [base_html, header_html]:
        if file_path.exists():
            content = file_path.read_text(encoding='utf-8')
            ids = re.findall(id_pattern, content)
            for element_id in ids:
                if any(keyword in element_id.lower() for keyword in ['user', 'panel', 'mobile', 'cart', 'favorites']):
                    elements[element_id] = str(file_path)
    
    # 2. Находим использование в JavaScript
    if main_js.exists():
        js_content = main_js.read_text(encoding='utf-8')
        used_ids = re.findall(getElementById_pattern, js_content)
        usage.update(used_ids)
    
    # 3. Анализируем результаты
    print("📋 Найденные элементы:")
    for element_id, file_path in sorted(elements.items()):
        status = "✅ ИСПОЛЬЗУЕТСЯ" if element_id in usage else "❌ НЕ ИСПОЛЬЗУЕТСЯ"
        print(f"  {element_id:<30} | {status:<15} | {file_path}")
    
    print("\n" + "=" * 50)
    print("📊 Сводка:")
    
    used_elements = [eid for eid in elements.keys() if eid in usage]
    unused_elements = [eid for eid in elements.keys() if eid not in usage]
    
    print(f"✅ Используемые элементы: {len(used_elements)}")
    print(f"❌ Неиспользуемые элементы: {len(unused_elements)}")
    
    if unused_elements:
        print("\n🗑️  Неиспользуемые элементы для удаления:")
        for element_id in unused_elements:
            print(f"  - {element_id}")
    
    return elements, usage, unused_elements

def analyze_css_classes():
    """Анализирует CSS классы, связанные с пользовательскими панелями"""
    
    css_file = Path("twocomms/twocomms_django_theme/static/css/styles.css")
    
    if not css_file.exists():
        print("❌ CSS файл не найден")
        return
    
    content = css_file.read_text(encoding='utf-8')
    
    # Паттерны для поиска CSS классов
    patterns = [
        r'\.user-panel[^-]',
        r'\.user-profile[^-]',
        r'\.mini-profile[^-]',
        r'\.cart-panel[^-]',
        r'\.bottom-nav[^-]',
    ]
    
    print("\n🎨 Анализ CSS классов:")
    print("=" * 50)
    
    for pattern in patterns:
        matches = re.findall(pattern, content)
        if matches:
            print(f"  {pattern}: {len(matches)} вхождений")
    
    # Поиск медиа-запросов для мобильных
    mobile_media = re.findall(r'@media.*max-width.*\d+px.*\{[^}]*\}', content, re.DOTALL)
    print(f"\n📱 Мобильные медиа-запросы: {len(mobile_media)}")

def main():
    print("🚀 Анализ пользовательских панелей TwoComms")
    print("=" * 60)
    
    # Анализ элементов
    elements, usage, unused_elements = find_element_usage()
    
    # Анализ CSS
    analyze_css_classes()
    
    print("\n" + "=" * 60)
    print("✅ Анализ завершен!")
    
    if unused_elements:
        print(f"\n💡 Рекомендация: Удалить {len(unused_elements)} неиспользуемых элементов")
        print("   Это поможет оптимизировать размер HTML и CSS")
    else:
        print("\n💡 Все элементы используются - удаление не требуется")

if __name__ == "__main__":
    main()
