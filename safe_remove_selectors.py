#!/usr/bin/env python3
"""
Безопасное удаление неиспользуемых CSS селекторов
Исправляет проблемы с синтаксисом CSS
"""

import re
import json

def load_safe_selectors():
    """Загружает список безопасных для удаления селекторов"""
    with open('safe_to_remove_selectors_js.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def is_safe_to_remove(selector):
    """Проверяет, безопасно ли удалять селектор"""
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
    
    # Исключаем селекторы, которые являются частью keyframes
    if selector.strip() in ['0%', '25%', '50%', '75%', '100%']:
        return False
    
    return True

def remove_css_rule_safely(content, selector):
    """Безопасно удаляет CSS правило"""
    # Очищаем селектор от комментариев
    clean_selector = re.sub(r'/\*.*?\*/', '', selector).strip()
    if not clean_selector:
        return content, False
    
    # Экранируем специальные символы
    escaped_selector = re.escape(clean_selector)
    
    # Ищем полное CSS правило
    # Паттерн: селектор { содержимое }
    pattern = rf'({escaped_selector})\s*\{{[^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*\}}'
    
    match = re.search(pattern, content, flags=re.DOTALL)
    if match:
        # Удаляем найденное правило
        new_content = content.replace(match.group(0), '')
        return new_content, True
    
    return content, False

def remove_unused_selectors_safely(css_file, selectors_to_remove):
    """Безопасно удаляет неиспользуемые селекторы из CSS файла"""
    with open(css_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_size = len(content)
    removed_count = 0
    
    for selector in selectors_to_remove:
        if is_safe_to_remove(selector):
            new_content, removed = remove_css_rule_safely(content, selector)
            if removed:
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
    print("🔍 Безопасно удаляем неиспользуемые CSS селекторы...")
    
    # Загружаем список безопасных селекторов
    data = load_safe_selectors()
    all_safe_selectors = data['safe_to_remove']
    
    # Фильтруем только безопасные для удаления
    safe_to_remove = [s for s in all_safe_selectors if is_safe_to_remove(s)]
    
    print(f"✅ Найдено безопасных для удаления селекторов: {len(safe_to_remove)}")
    
    if not safe_to_remove:
        print("❌ Нет безопасных селекторов для удаления")
        return
    
    # Показываем первые 10 для подтверждения
    print(f"\n📋 Селекторы для удаления (первые 10):")
    for i, selector in enumerate(safe_to_remove[:10]):
        print(f"   {i+1}. {selector}")
    if len(safe_to_remove) > 10:
        print(f"   ... и еще {len(safe_to_remove) - 10}")
    
    # Удаляем селекторы
    css_file = 'twocomms/twocomms_django_theme/static/css/styles.css'
    removed_count, size_reduction = remove_unused_selectors_safely(css_file, safe_to_remove)
    
    print(f"\n✅ Безопасное удаление завершено!")

if __name__ == "__main__":
    main()
