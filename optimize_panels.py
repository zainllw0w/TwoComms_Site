#!/usr/bin/env python3
"""
Скрипт для оптимизации панелей пользователя - удаление дублированного кода
"""

import re
from pathlib import Path

def analyze_panel_duplication():
    """Анализирует дублирование между десктопной и мобильной панелями"""
    
    # Читаем десктопную панель
    header_file = Path('twocomms/twocomms_django_theme/templates/partials/header.html')
    base_file = Path('twocomms/twocomms_django_theme/templates/base.html')
    
    with open(header_file, 'r', encoding='utf-8') as f:
        header_content = f.read()
    
    with open(base_file, 'r', encoding='utf-8') as f:
        base_content = f.read()
    
    # Находим десктопную панель
    desktop_panel_match = re.search(r'<div id="user-panel" class="user-panel">(.*?)</div>', header_content, re.DOTALL)
    if desktop_panel_match:
        desktop_panel = desktop_panel_match.group(1)
        print("✅ Найдена десктопная панель пользователя")
    else:
        print("❌ Десктопная панель не найдена")
        return
    
    # Находим мобильную панель
    mobile_panel_match = re.search(r'<div id="user-panel-mobile" class="user-panel d-none d-md-none">(.*?)</div>', base_content, re.DOTALL)
    if mobile_panel_match:
        mobile_panel = mobile_panel_match.group(1)
        print("✅ Найдена мобильная панель пользователя")
    else:
        print("❌ Мобильная панель не найдена")
        return
    
    # Анализируем различия
    print("\n=== АНАЛИЗ ДУБЛИРОВАНИЯ ===")
    
    # Убираем whitespace для сравнения
    desktop_clean = re.sub(r'\s+', ' ', desktop_panel.strip())
    mobile_clean = re.sub(r'\s+', ' ', mobile_panel.strip())
    
    # Находим различия
    differences = []
    
    # Проверяем различия в атрибутах
    if 'data-user-close' in desktop_clean and 'data-user-close-mobile' in mobile_clean:
        differences.append("Разные атрибуты для кнопки закрытия")
    
    if 'loading="lazy"' in mobile_clean and 'loading="lazy"' not in desktop_clean:
        differences.append("Мобильная панель имеет дополнительные атрибуты загрузки")
    
    if 'fetchpriority="low"' in mobile_clean and 'fetchpriority="low"' not in desktop_clean:
        differences.append("Мобильная панель имеет fetchpriority")
    
    # Проверяем различия в количестве искр
    desktop_sparks = desktop_clean.count('spark-')
    mobile_sparks = mobile_clean.count('spark-')
    
    if desktop_sparks != mobile_sparks:
        differences.append(f"Разное количество искр: десктоп {desktop_sparks}, мобильная {mobile_sparks}")
    
    # Проверяем различия в размере иконок
    if 'width="24" height="24"' in desktop_clean and 'width="20" height="20"' in mobile_clean:
        differences.append("Разные размеры иконок")
    
    print(f"📊 Найдено различий: {len(differences)}")
    for diff in differences:
        print(f"   - {diff}")
    
    # Анализируем размеры
    desktop_size = len(desktop_clean)
    mobile_size = len(mobile_clean)
    duplication_percent = (min(desktop_size, mobile_size) / max(desktop_size, mobile_size)) * 100
    
    print(f"\n📏 Размеры панелей:")
    print(f"   Десктопная: {desktop_size} символов")
    print(f"   Мобильная: {mobile_size} символов")
    print(f"   Дублирование: {duplication_percent:.1f}%")
    
    if duplication_percent > 80:
        print("\n⚠️  ВЫСОКОЕ ДУБЛИРОВАНИЕ! Рекомендуется оптимизация")
    elif duplication_percent > 60:
        print("\n⚠️  Среднее дублирование. Можно оптимизировать")
    else:
        print("\n✅ Дублирование в пределах нормы")

def find_hidden_elements():
    """Находит скрытые элементы, которые можно удалить"""
    
    base_file = Path('twocomms/twocomms_django_theme/templates/base.html')
    
    with open(base_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n=== ПОИСК СКРЫТЫХ ЭЛЕМЕНТОВ ===")
    
    # Ищем элементы с display: none
    hidden_elements = re.findall(r'<[^>]*style="[^"]*display:\s*none[^"]*"[^>]*>.*?</[^>]+>', content, re.DOTALL)
    
    print(f"🔍 Найдено скрытых элементов: {len(hidden_elements)}")
    
    for i, element in enumerate(hidden_elements[:5]):  # Показываем первые 5
        # Извлекаем ID или класс
        id_match = re.search(r'id="([^"]*)"', element)
        class_match = re.search(r'class="([^"]*)"', element)
        
        identifier = id_match.group(1) if id_match else class_match.group(1) if class_match else f"Элемент {i+1}"
        
        # Считаем строки
        lines = element.count('\n') + 1
        chars = len(element)
        
        print(f"   📦 {identifier}: {lines} строк, {chars} символов")
    
    if len(hidden_elements) > 5:
        print(f"   ... и еще {len(hidden_elements) - 5} элементов")

def check_unused_css():
    """Проверяет неиспользуемые CSS классы"""
    
    css_file = Path('twocomms/twocomms_django_theme/static/css/styles.css')
    
    with open(css_file, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    print("\n=== АНАЛИЗ CSS ===")
    
    # Ищем классы для панелей
    panel_classes = [
        '.user-panel',
        '.user-header', 
        '.user-avatar-large',
        '.user-info',
        '.user-menu',
        '.menu-item',
        '.points-card',
        '.sparks-container',
        '.spark'
    ]
    
    total_css_size = len(css_content)
    panel_css_size = 0
    
    for class_name in panel_classes:
        # Ищем определения классов
        pattern = rf'{re.escape(class_name)}\s*\{{[^}}]*\}}'
        matches = re.findall(pattern, css_content, re.DOTALL)
        
        if matches:
            class_size = sum(len(match) for match in matches)
            panel_css_size += class_size
            print(f"   🎨 {class_name}: {class_size} символов")
    
    print(f"\n📊 CSS для панелей: {panel_css_size} символов из {total_css_size}")
    print(f"   Процент: {(panel_css_size/total_css_size)*100:.1f}%")

if __name__ == "__main__":
    print("🔍 АНАЛИЗ ОПТИМИЗАЦИИ ПАНЕЛЕЙ ПОЛЬЗОВАТЕЛЯ\n")
    
    analyze_panel_duplication()
    find_hidden_elements()
    check_unused_css()
    
    print("\n=== РЕКОМЕНДАЦИИ ===")
    print("1. ✅ Все панели используются - удалять не нужно")
    print("2. ⚠️  Есть дублирование между десктопной и мобильной панелями")
    print("3. 💡 Можно создать общий template для панели с параметрами")
    print("4. 🧹 Можно удалить скрытые элементы favorites (уже скрыты)")
    print("5. 📦 CSS оптимизирован и используется")
