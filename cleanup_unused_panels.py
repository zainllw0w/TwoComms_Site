#!/usr/bin/env python3
"""
Скрипт для удаления неиспользуемых элементов пользовательских панелей
"""

import re
import os
from pathlib import Path

def cleanup_unused_elements():
    """Удаляет неиспользуемые элементы из HTML файлов"""
    
    # Элементы, которые мы точно используем и НЕ должны удалять
    USED_ELEMENTS = {
        'user-panel',           # Десктопная панель пользователя
        'user-panel-mobile',    # Мобильная панель пользователя  
        'user-toggle',          # Кнопка десктопной панели
        'user-toggle-mobile',   # Кнопка мобильной панели
        'cart-toggle',          # Кнопка корзины десктоп
        'cart-toggle-mobile',   # Кнопка корзины мобильная
        'favorites-menu-item',  # Используется в нашем JS для скрытия
        'favorites-mobile-bottom-nav',  # Используется в нашем JS для скрытия
        'favorites-mobile-user-panel',  # Используется в нашем JS для скрытия
    }
    
    # Элементы для удаления (старые, неиспользуемые)
    ELEMENTS_TO_REMOVE = [
        # Старые счетчики корзины (есть новые в main.js)
        {'id': 'cart-count', 'file': 'header.html'},
        {'id': 'cart-count-mobile', 'file': 'header.html'},
        
        # Старые счетчики favorites (есть новые в main.js)  
        {'id': 'favorites-count', 'file': 'header.html'},
        {'id': 'favorites-count-mini', 'file': 'header.html'},
        {'id': 'favorites-count-mobile', 'file': 'header.html'},
        
        # Старые панели корзины (дублируются)
        {'id': 'mini-cart-panel', 'file': 'header.html'},
        {'id': 'mini-cart-panel-mobile', 'file': 'base.html'},
        {'id': 'mini-cart-content', 'file': 'header.html'},
        {'id': 'mini-cart-content-mobile', 'file': 'base.html'},
    ]
    
    print("🧹 Очистка неиспользуемых элементов...")
    print("=" * 50)
    
    # Пути к файлам
    files = {
        'header.html': Path("twocomms/twocomms_django_theme/templates/partials/header.html"),
        'base.html': Path("twocomms/twocomms_django_theme/templates/base.html")
    }
    
    total_removed = 0
    
    for element in ELEMENTS_TO_REMOVE:
        element_id = element['id']
        file_key = element['file']
        file_path = files[file_key]
        
        if not file_path.exists():
            print(f"❌ Файл {file_path} не найден")
            continue
            
        print(f"🔍 Удаляем {element_id} из {file_key}...")
        
        content = file_path.read_text(encoding='utf-8')
        original_size = len(content)
        
        # Паттерн для поиска элемента с указанным ID
        # Ищем от открывающего тега до закрывающего
        pattern = rf'<[^>]*id=["\']?{re.escape(element_id)}["\']?[^>]*>.*?</[^>]*>'
        
        # Удаляем элемент
        new_content = re.sub(pattern, '', content, flags=re.DOTALL)
        
        if len(new_content) != original_size:
            file_path.write_text(new_content, encoding='utf-8')
            removed_size = original_size - len(new_content)
            print(f"  ✅ Удален {element_id} ({removed_size} символов)")
            total_removed += 1
        else:
            print(f"  ⚠️  Элемент {element_id} не найден")
    
    print(f"\n📊 Результат: удалено {total_removed} элементов")
    return total_removed

def cleanup_unused_css():
    """Удаляет неиспользуемые CSS стили"""
    
    print("\n🎨 Очистка неиспользуемых CSS стилей...")
    print("=" * 50)
    
    css_file = Path("twocomms/twocomms_django_theme/static/css/styles.css")
    
    if not css_file.exists():
        print("❌ CSS файл не найден")
        return 0
    
    content = css_file.read_text(encoding='utf-8')
    original_size = len(content)
    
    # CSS классы для удаления (старые, неиспользуемые)
    css_to_remove = [
        # Старые стили счетчиков
        r'\.favorites-badge[^-][^{]*\{[^}]*\}',
        r'\.cart-badge[^-][^{]*\{[^}]*\}',
        r'#favorites-count[^{]*\{[^}]*\}',
        r'#cart-count[^{]*\{[^}]*\}',
        
        # Старые стили панелей корзины
        r'\.mini-cart-panel[^-][^{]*\{[^}]*\}',
        r'\.mini-cart-content[^-][^{]*\{[^}]*\}',
    ]
    
    removed_count = 0
    
    for pattern in css_to_remove:
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            content = re.sub(pattern, '', content, flags=re.DOTALL)
            print(f"  ✅ Удален CSS: {pattern[:30]}... ({len(matches)} вхождений)")
            removed_count += len(matches)
    
    if len(content) != original_size:
        css_file.write_text(content, encoding='utf-8')
        removed_size = original_size - len(content)
        print(f"  📊 Удалено {removed_size} символов CSS")
    
    return removed_count

def main():
    print("🚀 Очистка неиспользуемых элементов TwoComms")
    print("=" * 60)
    
    # Удаляем неиспользуемые HTML элементы
    html_removed = cleanup_unused_elements()
    
    # Удаляем неиспользуемые CSS стили
    css_removed = cleanup_unused_css()
    
    print("\n" + "=" * 60)
    print("✅ Очистка завершена!")
    print(f"📊 Удалено HTML элементов: {html_removed}")
    print(f"📊 Удалено CSS правил: {css_removed}")
    
    if html_removed > 0 or css_removed > 0:
        print("\n💡 Рекомендации:")
        print("  1. Проверьте работу сайта")
        print("  2. Убедитесь, что все функции работают корректно")
        print("  3. Закоммитьте изменения")

if __name__ == "__main__":
    main()
