#!/usr/bin/env python3
"""
Точная проверка использования CSS селекторов
"""

import re
import os
import json
from pathlib import Path

def extract_css_selectors(css_file):
    """Извлекает все селекторы из CSS файла"""
    with open(css_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Убираем комментарии
    content_no_comments = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    # Находим все правила CSS
    rules = re.findall(r'([^{}]+)\s*\{[^{}]*\}', content_no_comments, re.DOTALL)
    
    selectors = []
    for rule in rules:
        # Разбиваем селекторы (могут быть через запятую)
        rule_selectors = [s.strip() for s in rule.split(',')]
        for selector in rule_selectors:
            if selector.strip() and not selector.strip().startswith('@'):
                selectors.append(selector.strip())
    
    return selectors

def extract_classes_and_ids_from_selector(selector):
    """Извлекает классы и ID из селектора"""
    classes = set()
    ids = set()
    
    # Находим классы (.class-name)
    class_matches = re.findall(r'\.([a-zA-Z0-9_-]+)', selector)
    classes.update(class_matches)
    
    # Находим ID (#id-name)
    id_matches = re.findall(r'#([a-zA-Z0-9_-]+)', selector)
    ids.update(id_matches)
    
    return classes, ids

def scan_templates_for_usage(templates_dir):
    """Сканирует шаблоны для поиска используемых классов и ID"""
    used_classes = set()
    used_ids = set()
    
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Находим классы в HTML
                    class_matches = re.findall(r'class=["\']([^"\']*)["\']', content)
                    for class_string in class_matches:
                        classes = class_string.split()
                        used_classes.update(classes)
                    
                    # Находим ID в HTML
                    id_matches = re.findall(r'id=["\']([^"\']*)["\']', content)
                    used_ids.update(id_matches)
                    
                except Exception as e:
                    print(f"Ошибка чтения {file_path}: {e}")
    
    return used_classes, used_ids

def is_selector_safe_to_remove(selector, used_classes, used_ids):
    """Проверяет, безопасно ли удалять селектор"""
    # Не удаляем селекторы с псевдоклассами, псевдоэлементами
    if any(pseudo in selector for pseudo in [':hover', ':focus', ':active', ':visited', ':before', ':after', 
                                           ':first-child', ':last-child', ':nth-child', ':nth-of-type']):
        return False
    
    # Не удаляем селекторы с атрибутами
    if '[' in selector and ']' in selector:
        return False
    
    # Не удаляем селекторы с data- атрибутами
    if 'data-' in selector:
        return False
    
    # Не удаляем селекторы с js- классами (могут использоваться в JS)
    if 'js-' in selector:
        return False
    
    # Не удаляем базовые HTML элементы
    if any(tag in selector.lower() for tag in ['html', 'body', 'head', 'script', 'style', 'meta', 'link']):
        return False
    
    # Не удаляем селекторы с медиа-запросами
    if '@media' in selector or '@keyframes' in selector:
        return False
    
    # Извлекаем классы и ID из селектора
    selector_classes, selector_ids = extract_classes_and_ids_from_selector(selector)
    
    # Проверяем, используются ли все классы и ID
    unused_classes = selector_classes - used_classes
    unused_ids = selector_ids - used_ids
    
    # Если есть неиспользуемые классы или ID, селектор можно удалить
    return len(unused_classes) > 0 or len(unused_ids) > 0

def main():
    css_file = 'twocomms/twocomms_django_theme/static/css/styles.css'
    templates_dir = 'twocomms/twocomms_django_theme/templates'
    
    print("🔍 Проверяем использование CSS селекторов...")
    
    # Извлекаем селекторы
    selectors = extract_css_selectors(css_file)
    print(f"✅ Найдено селекторов: {len(selectors)}")
    
    # Сканируем шаблоны
    used_classes, used_ids = scan_templates_for_usage(templates_dir)
    print(f"✅ Найдено используемых классов: {len(used_classes)}")
    print(f"✅ Найдено используемых ID: {len(used_ids)}")
    
    # Находим безопасные для удаления селекторы
    safe_to_remove = []
    for selector in selectors:
        if is_selector_safe_to_remove(selector, used_classes, used_ids):
            safe_to_remove.append(selector)
    
    print(f"\n📊 Результаты:")
    print(f"   - Всего селекторов: {len(selectors)}")
    print(f"   - Безопасно удалить: {len(safe_to_remove)}")
    
    # Сохраняем список безопасных для удаления селекторов
    with open('safe_to_remove_selectors.json', 'w', encoding='utf-8') as f:
        json.dump({
            'total_selectors': len(selectors),
            'safe_to_remove': safe_to_remove,
            'count': len(safe_to_remove)
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Список сохранен в safe_to_remove_selectors.json")
    
    # Показываем первые 20 для примера
    if safe_to_remove:
        print(f"\n📋 Примеры безопасных для удаления селекторов:")
        for i, selector in enumerate(safe_to_remove[:20]):
            print(f"   {i+1}. {selector}")
        if len(safe_to_remove) > 20:
            print(f"   ... и еще {len(safe_to_remove) - 20}")

if __name__ == "__main__":
    main()

