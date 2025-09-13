#!/usr/bin/env python3
"""
Скрипт для анализа использования панелей пользователя и корзины
"""

import os
import re
from pathlib import Path

def find_panel_usage():
    """Находит все панели и анализирует их использование"""
    
    # Панели, которые мы нашли
    panels = {
        'mini-cart-panel': 'Десктопная мини-корзина',
        'mini-cart-panel-mobile': 'Мобильная мини-корзина', 
        'user-panel': 'Десктопная панель пользователя',
        'user-panel-mobile': 'Мобильная панель пользователя'
    }
    
    # Результаты анализа
    analysis = {}
    
    # Поиск в JavaScript файлах
    js_files = list(Path('twocomms/twocomms_django_theme/static/js').glob('*.js'))
    
    for panel_id, description in panels.items():
        usage = {
            'description': description,
            'found_in_js': [],
            'found_in_css': [],
            'found_in_templates': [],
            'is_used': False
        }
        
        # Поиск в JavaScript
        for js_file in js_files:
            try:
                with open(js_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if panel_id in content:
                        usage['found_in_js'].append(str(js_file))
                        usage['is_used'] = True
            except:
                pass
        
        # Поиск в CSS
        css_files = list(Path('twocomms/twocomms_django_theme/static/css').glob('*.css'))
        for css_file in css_files:
            try:
                with open(css_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if panel_id in content:
                        usage['found_in_css'].append(str(css_file))
                        usage['is_used'] = True
            except:
                pass
        
        # Поиск в шаблонах
        template_files = list(Path('twocomms/twocomms_django_theme/templates').rglob('*.html'))
        for template_file in template_files:
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if panel_id in content:
                        usage['found_in_templates'].append(str(template_file))
                        usage['is_used'] = True
            except:
                pass
        
        analysis[panel_id] = usage
    
    return analysis

def print_analysis():
    """Выводит результаты анализа"""
    analysis = find_panel_usage()
    
    print("=== АНАЛИЗ ИСПОЛЬЗОВАНИЯ ПАНЕЛЕЙ ===\n")
    
    for panel_id, usage in analysis.items():
        print(f"📋 {usage['description']} (ID: {panel_id})")
        print(f"   Используется: {'✅ ДА' if usage['is_used'] else '❌ НЕТ'}")
        
        if usage['found_in_js']:
            print(f"   📄 JavaScript: {len(usage['found_in_js'])} файлов")
            for file in usage['found_in_js']:
                print(f"      - {file}")
        
        if usage['found_in_css']:
            print(f"   🎨 CSS: {len(usage['found_in_css'])} файлов")
            for file in usage['found_in_css']:
                print(f"      - {file}")
        
        if usage['found_in_templates']:
            print(f"   📝 Шаблоны: {len(usage['found_in_templates'])} файлов")
            for file in usage['found_in_templates']:
                print(f"      - {file}")
        
        print()

def find_unused_panels():
    """Находит неиспользуемые панели"""
    analysis = find_panel_usage()
    
    unused = []
    for panel_id, usage in analysis.items():
        if not usage['is_used']:
            unused.append((panel_id, usage['description']))
    
    return unused

if __name__ == "__main__":
    print_analysis()
    
    unused = find_unused_panels()
    if unused:
        print("=== НЕИСПОЛЬЗУЕМЫЕ ПАНЕЛИ ===")
        for panel_id, description in unused:
            print(f"❌ {description} (ID: {panel_id})")
    else:
        print("✅ Все панели используются")
