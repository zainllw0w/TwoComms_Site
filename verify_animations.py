#!/usr/bin/env python3
"""
Проверка использования анимаций в CSS и HTML/JS файлах
"""

import re
import os
from pathlib import Path

def find_keyframes_in_css(css_file):
    """Находит все @keyframes в CSS файле"""
    with open(css_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    keyframes = re.findall(r'@keyframes\s+([a-zA-Z0-9_-]+)', content)
    return keyframes

def find_animation_usage_in_css(css_file):
    """Находит использование анимаций в CSS"""
    with open(css_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Ищем animation и animation-name
    animations = re.findall(r'animation(?:-name)?\s*:\s*([^;]+)', content)
    used_animations = set()
    
    for anim in animations:
        # Разбиваем на отдельные анимации (могут быть через запятую)
        anim_list = [a.strip() for a in anim.split(',')]
        for a in anim_list:
            # Берем только имя анимации (до первого пробела)
            anim_name = a.split()[0] if a.split() else a
            used_animations.add(anim_name)
    
    return used_animations

def find_animation_usage_in_templates(templates_dir):
    """Находит использование анимаций в HTML/JS файлах"""
    used_animations = set()
    
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith(('.html', '.js')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Ищем animation в style атрибутах и JavaScript
                    animations = re.findall(r'animation\s*:\s*([^;]+)', content)
                    for anim in animations:
                        anim_list = [a.strip() for a in anim.split(',')]
                        for a in anim_list:
                            anim_name = a.split()[0] if a.split() else a
                            used_animations.add(anim_name)
                    
                    # Ищем в JavaScript
                    js_animations = re.findall(r'\.style\.animation\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                    for anim in js_animations:
                        anim_name = anim.split()[0] if anim.split() else anim
                        used_animations.add(anim_name)
                        
                except Exception as e:
                    print(f"Ошибка чтения {file_path}: {e}")
    
    return used_animations

def main():
    css_file = 'twocomms/twocomms_django_theme/static/css/styles.css'
    templates_dir = 'twocomms/twocomms_django_theme/templates'
    
    print("🔍 Проверяем использование анимаций...")
    
    # Находим все keyframes
    all_keyframes = find_keyframes_in_css(css_file)
    print(f"✅ Найдено keyframes: {len(all_keyframes)}")
    
    # Находим использование в CSS
    css_used = find_animation_usage_in_css(css_file)
    print(f"✅ Используется в CSS: {len(css_used)}")
    
    # Находим использование в шаблонах
    template_used = find_animation_usage_in_templates(templates_dir)
    print(f"✅ Используется в шаблонах: {len(template_used)}")
    
    # Объединяем все использования
    all_used = css_used | template_used
    
    # Находим неиспользуемые
    unused = set(all_keyframes) - all_used
    
    print(f"\n📊 Результаты:")
    print(f"   - Всего keyframes: {len(all_keyframes)}")
    print(f"   - Используется: {len(all_used)}")
    print(f"   - Не используется: {len(unused)}")
    
    if unused:
        print(f"\n❌ Неиспользуемые анимации:")
        for anim in sorted(unused):
            print(f"   - {anim}")
    else:
        print(f"\n✅ Все анимации используются!")
    
    # Показываем все keyframes для справки
    print(f"\n📋 Все keyframes:")
    for anim in sorted(all_keyframes):
        status = "✅" if anim in all_used else "❌"
        print(f"   {status} {anim}")

if __name__ == "__main__":
    main()

