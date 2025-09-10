#!/usr/bin/env python3
"""
Объединение дублирующихся CSS стилей
"""

import re
import json

def load_consolidation_plan():
    """Загружает план объединения дубликатов"""
    with open('css_consolidation_plan.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def consolidate_duplicates(css_file, consolidation_plan):
    """Объединяет дублирующиеся стили"""
    with open(css_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_size = len(content)
    consolidated_count = 0
    total_savings = 0
    
    # Добавляем utility классы в начало файла
    utility_classes = []
    
    for item in consolidation_plan[:50]:  # Берем первые 50 для безопасности
        styles = item['styles']
        selectors = item['current_selectors']
        utility_class = item['suggested_utility_class']
        
        # Создаем utility класс
        utility_rule = f"{utility_class} {{\n  {styles}\n}}\n\n"
        utility_classes.append(utility_rule)
        
        # Удаляем дублирующиеся правила
        for selector in selectors:
            # Очищаем селектор от комментариев
            clean_selector = re.sub(r'/\*.*?\*/', '', selector).strip()
            if not clean_selector:
                continue
                
            # Экранируем специальные символы
            escaped_selector = re.escape(clean_selector)
            
            # Ищем и удаляем правило
            pattern = rf'{escaped_selector}\s*\{{[^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*\}}'
            match = re.search(pattern, content, flags=re.DOTALL)
            
            if match:
                content = content.replace(match.group(0), '')
                consolidated_count += 1
                print(f"✅ Объединен селектор: {clean_selector}")
    
    # Добавляем utility классы в начало файла
    if utility_classes:
        # Находим место после комментариев в начале файла
        first_rule_match = re.search(r'^[^{]*\{', content, re.MULTILINE)
        if first_rule_match:
            insert_pos = first_rule_match.start()
            utility_css = '\n'.join(utility_classes)
            content = content[:insert_pos] + utility_css + content[insert_pos:]
        else:
            # Если не нашли правила, добавляем в конец
            content += '\n\n' + '\n'.join(utility_classes)
    
    # Убираем лишние пустые строки
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    
    # Сохраняем обновленный файл
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    new_size = len(content)
    size_reduction = original_size - new_size
    
    print(f"\n📊 Результаты объединения:")
    print(f"   - Объединено правил: {consolidated_count}")
    print(f"   - Добавлено utility классов: {len(utility_classes)}")
    print(f"   - Уменьшение размера: {size_reduction} символов ({size_reduction/original_size*100:.1f}%)")
    print(f"   - Новый размер: {new_size} символов")
    
    return consolidated_count, size_reduction

def main():
    print("🔍 Объединяем дублирующиеся CSS стили...")
    
    # Загружаем план объединения
    plan = load_consolidation_plan()
    consolidation_plan = plan['consolidation_plan']
    
    print(f"✅ Найдено групп дублирующихся стилей: {len(consolidation_plan)}")
    
    if not consolidation_plan:
        print("❌ Нет дублирующихся стилей для объединения")
        return
    
    # Показываем первые 5 для подтверждения
    print(f"\n📋 Примеры для объединения (первые 5):")
    for i, item in enumerate(consolidation_plan[:5]):
        print(f"   {i+1}. {item['suggested_utility_class']} - {item['savings']}")
        print(f"      Стили: {item['styles'][:50]}...")
    
    # Объединяем дубликаты
    css_file = 'twocomms/twocomms_django_theme/static/css/styles.css'
    consolidated_count, size_reduction = consolidate_duplicates(css_file, consolidation_plan)
    
    print(f"\n✅ Объединение завершено!")

if __name__ == "__main__":
    main()
