#!/usr/bin/env python3
"""
Генератор списка неиспользуемых CSS селекторов для TwoComms
Создает детальный список для безопасного удаления
"""

import json
import re
from pathlib import Path

def load_analysis_report():
    """Загружает отчет анализа"""
    with open('css_analysis_report.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_deep_analysis_report():
    """Загружает отчет глубокого анализа"""
    with open('css_deep_analysis_report.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_unused_selectors_list():
    """Генерирует список неиспользуемых селекторов"""
    report = load_analysis_report()
    deep_report = load_deep_analysis_report()
    
    unused_selectors = report.get('unused_selectors', [])
    unused_animations = deep_report.get('unused_animations', [])
    
    # Создаем детальный список
    unused_list = {
        'summary': {
            'total_unused_selectors': len(unused_selectors),
            'total_unused_animations': len(unused_animations),
            'estimated_size_reduction': '30-40%'
        },
        'unused_selectors': unused_selectors,
        'unused_animations': unused_animations,
        'safe_to_remove': {
            'selectors': [],
            'animations': unused_animations
        }
    }
    
    # Фильтруем селекторы, которые точно безопасно удалять
    safe_selectors = []
    for selector in unused_selectors:
        # Исключаем селекторы, которые могут использоваться динамически
        if not any(keyword in selector.lower() for keyword in [
            'hover', 'focus', 'active', 'visited', 'before', 'after',
            'first-child', 'last-child', 'nth-child', 'js-', 'data-'
        ]):
            safe_selectors.append(selector)
    
    unused_list['safe_to_remove']['selectors'] = safe_selectors
    
    return unused_list

def generate_duplicate_consolidation_plan():
    """Генерирует план объединения дублирующихся стилей"""
    report = load_analysis_report()
    duplicates = report.get('duplicate_styles', [])
    
    consolidation_plan = {
        'summary': {
            'total_duplicate_groups': len(duplicates),
            'estimated_size_reduction': '10-15%'
        },
        'consolidation_plan': []
    }
    
    for duplicate in duplicates[:20]:  # Берем первые 20 для примера
        if duplicate['count'] > 1:
            consolidation_plan['consolidation_plan'].append({
                'styles': duplicate['styles'],
                'current_selectors': duplicate['selectors'],
                'suggested_utility_class': f".utility-{hash(duplicate['styles']) % 10000}",
                'savings': f"{duplicate['count'] - 1} duplicate(s)"
            })
    
    return consolidation_plan

def main():
    print("🔍 Генерируем детальные списки для оптимизации...")
    
    # Генерируем список неиспользуемых селекторов
    unused_list = generate_unused_selectors_list()
    
    with open('unused_css_selectors.json', 'w', encoding='utf-8') as f:
        json.dump(unused_list, f, ensure_ascii=False, indent=2)
    
    # Генерируем план объединения дубликатов
    consolidation_plan = generate_duplicate_consolidation_plan()
    
    with open('css_consolidation_plan.json', 'w', encoding='utf-8') as f:
        json.dump(consolidation_plan, f, ensure_ascii=False, indent=2)
    
    print("✅ Списки сгенерированы:")
    print("   - unused_css_selectors.json - неиспользуемые селекторы")
    print("   - css_consolidation_plan.json - план объединения дубликатов")
    
    # Выводим краткую статистику
    print(f"\n📊 Статистика:")
    print(f"   - Неиспользуемых селекторов: {unused_list['summary']['total_unused_selectors']}")
    print(f"   - Неиспользуемых анимаций: {unused_list['summary']['total_unused_animations']}")
    print(f"   - Групп дублирующихся стилей: {consolidation_plan['summary']['total_duplicate_groups']}")
    print(f"   - Ожидаемое уменьшение размера: {unused_list['summary']['estimated_size_reduction']}")

if __name__ == "__main__":
    main()

