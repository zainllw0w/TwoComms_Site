#!/usr/bin/env python3
"""
Удаление очевидно неиспользуемых CSS селекторов
Консервативный подход - удаляем только те, которые точно не используются
"""

import re
import json

def load_safe_selectors():
    """Загружает список безопасных для удаления селекторов"""
    with open('safe_to_remove_selectors_js.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def is_obviously_unused(selector):
    """Проверяет, является ли селектор очевидно неиспользуемым"""
    # Исключаем селекторы, которые могут использоваться в CSS
    if any(keyword in selector for keyword in [
        'perf-lite', 'modal-glass', 'panel-glass', 'card.glassy', 'hero.bg-hero',
        'cart-message', 'cart-promo', 'cart-total', 'order-card', 'order-total'
    ]):
        return False
    
    # Исключаем селекторы с псевдоклассами
    if any(pseudo in selector for pseudo in [':hover', ':focus', ':active', ':visited', ':before', ':after']):
        return False
    
    # Исключаем селекторы с атрибутами
    if '[' in selector and ']' in selector:
        return False
    
    # Исключаем базовые HTML элементы
    if any(tag in selector.lower() for tag in ['html', 'body', 'head', 'script', 'style']):
        return False
    
    # Исключаем селекторы с медиа-запросами
    if '@media' in selector or '@keyframes' in selector:
        return False
    
    return True

def remove_unused_selectors(css_file, selectors_to_remove):
    """Удаляет неиспользуемые селекторы из CSS файла"""
    with open(css_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_size = len(content)
    removed_count = 0
    
    for selector in selectors_to_remove:
        # Создаем паттерн для поиска правила CSS
        # Экранируем специальные символы
        escaped_selector = re.escape(selector)
        
        # Ищем правило CSS с этим селектором
        pattern = rf'{escaped_selector}\s*\{{[^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*\}}'
        
        # Удаляем правило
        new_content = re.sub(pattern, '', content, flags=re.DOTALL)
        
        if new_content != content:
            content = new_content
            removed_count += 1
            print(f"✅ Удален селектор: {selector}")
    
    # Убираем лишние пустые строки
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    
    # Сохраняем обновленный файл
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    new_size = len(content)
    size_reduction = original_size - new_size
    
    print(f"\n📊 Результаты удаления:")
    print(f"   - Удалено селекторов: {removed_count}")
    print(f"   - Уменьшение размера: {size_reduction} символов ({size_reduction/original_size*100:.1f}%)")
    print(f"   - Новый размер: {new_size} символов")
    
    return removed_count, size_reduction

def main():
    print("🔍 Удаляем очевидно неиспользуемые CSS селекторы...")
    
    # Загружаем список безопасных селекторов
    data = load_safe_selectors()
    all_safe_selectors = data['safe_to_remove']
    
    # Фильтруем только очевидно неиспользуемые
    obviously_unused = [s for s in all_safe_selectors if is_obviously_unused(s)]
    
    print(f"✅ Найдено очевидно неиспользуемых селекторов: {len(obviously_unused)}")
    
    if not obviously_unused:
        print("❌ Нет очевидно неиспользуемых селекторов для удаления")
        return
    
    # Показываем первые 10 для подтверждения
    print(f"\n📋 Селекторы для удаления (первые 10):")
    for i, selector in enumerate(obviously_unused[:10]):
        print(f"   {i+1}. {selector}")
    if len(obviously_unused) > 10:
        print(f"   ... и еще {len(obviously_unused) - 10}")
    
    # Удаляем селекторы
    css_file = 'twocomms/twocomms_django_theme/static/css/styles.css'
    removed_count, size_reduction = remove_unused_selectors(css_file, obviously_unused)
    
    print(f"\n✅ Удаление завершено!")

if __name__ == "__main__":
    main()
