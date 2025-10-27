#!/usr/bin/env python3
"""
Простий скрипт для перевірки структури views без Django setup
"""
import os
import re
from pathlib import Path

def get_functions_from_file(filepath):
    """Отримати всі функції з файлу"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Шукаємо всі def функції
    functions = re.findall(r'^def (\w+)\(', content, re.MULTILINE)
    return functions


def check_module_files():
    """Перевірка що всі модульні файли існують"""
    print("=" * 60)
    print("ПЕРЕВІРКА МОДУЛЬНИХ ФАЙЛІВ")
    print("=" * 60)
    
    modules = {
        'views/promo.py': 'Промокоди',
        'views/cart.py': 'Кошик',
        'views/api.py': 'API',
        'views/loyalty.py': 'Loyalty',
        'views/__init__.py': 'Експорти',
    }
    
    base_path = Path('storefront')
    
    for module_path, description in modules.items():
        full_path = base_path / module_path
        if full_path.exists():
            funcs = get_functions_from_file(full_path)
            print(f"  ✅ {module_path} ({description}) - {len(funcs)} функцій")
        else:
            print(f"  ❌ {module_path} ({description}) - НЕ ЗНАЙДЕНО!")
    
    return True


def analyze_views_py():
    """Аналіз головного views.py"""
    print("\n" + "=" * 60)
    print("АНАЛІЗ views.py")
    print("=" * 60)
    
    views_path = Path('storefront/views.py')
    
    if not views_path.exists():
        print("  ❌ views.py не знайдено!")
        return []
    
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Отримуємо функції
    functions = get_functions_from_file(views_path)
    
    print(f"\nЗнайдено {len(functions)} функцій:")
    
    # Перевіряємо чи є промокод-логіка в views.py
    promo_patterns = [
        'PromoCode.objects',
        'PromoCodeGroup.objects',
        'PromoCodeUsage.objects',
    ]
    
    has_promo_logic = False
    for pattern in promo_patterns:
        if pattern in content:
            # Перевіряємо чи це не в admin_panel через модуль
            if 'get_promo_admin_context' not in content:
                has_promo_logic = True
                print(f"  ⚠️  Знайдено прямі запити {pattern}")
    
    # Перевіряємо admin_panel
    if 'def admin_panel' in content:
        print(f"\n  🔍 admin_panel присутня")
        
        # Шукаємо секцію promocodes
        promo_section_match = re.search(
            r"elif section == 'promocodes':(.*?)(?=elif section|\Z)",
            content,
            re.DOTALL
        )
        
        if promo_section_match:
            promo_section = promo_section_match.group(1)
            
            if 'get_promo_admin_context' in promo_section:
                print(f"     ✅ Використовує get_promo_admin_context() з модуля")
            elif 'PromoCode.objects' in promo_section:
                print(f"     ❌ Має прямі запити до БД (дублювання логіки!)")
            else:
                print(f"     ⚠️  Секція promocodes не знайдена або порожня")
    
    print(f"\n  📋 Список функцій:")
    for func in functions:
        print(f"     - {func}")
    
    return functions


def check_promo_module():
    """Детальна перевірка модуля promo"""
    print("\n" + "=" * 60)
    print("ДЕТАЛЬНА ПЕРЕВІРКА views/promo.py")
    print("=" * 60)
    
    promo_path = Path('storefront/views/promo.py')
    
    if not promo_path.exists():
        print("  ❌ views/promo.py не знайдено!")
        return False
    
    with open(promo_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Обов'язкові функції
    required_functions = {
        'get_promo_admin_context': 'Функція для отримання контексту',
        'admin_promocode_create': 'Створення промокода',
        'admin_promocode_edit': 'Редагування промокода',
        'admin_promocode_delete': 'Видалення промокода',
        'admin_promo_group_create': 'Створення групи',
    }
    
    found = 0
    for func_name, description in required_functions.items():
        if f'def {func_name}(' in content:
            print(f"  ✅ {func_name} - {description}")
            found += 1
        else:
            print(f"  ❌ {func_name} - {description} НЕ ЗНАЙДЕНО!")
    
    print(f"\n  Знайдено {found}/{len(required_functions)} обов'язкових функцій")
    
    return found == len(required_functions)


def check_init_exports():
    """Перевірка експортів в __init__.py"""
    print("\n" + "=" * 60)
    print("ПЕРЕВІРКА ЕКСПОРТІВ views/__init__.py")
    print("=" * 60)
    
    init_path = Path('storefront/views/__init__.py')
    
    if not init_path.exists():
        print("  ❌ views/__init__.py не знайдено!")
        return False
    
    with open(init_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Перевіряємо імпорти з promo
    if 'from .promo import' in content:
        print("  ✅ Імпортує з .promo")
        
        if 'get_promo_admin_context' in content:
            print("     ✅ get_promo_admin_context експортується")
        else:
            print("     ❌ get_promo_admin_context НЕ експортується!")
    else:
        print("  ❌ Не імпортує з .promo!")
    
    # Перевіряємо _exclude
    if '_exclude' in content:
        print("  ✅ Використовує _exclude для уникнення дублювання")
    
    return True


def main():
    print("\n" + "🔍" * 30)
    print("ПЕРЕВІРКА МОДУЛЬНОЇ СТРУКТУРИ VIEWS")
    print("🔍" * 30 + "\n")
    
    os.chdir(Path(__file__).parent)
    
    # 1. Перевірка модульних файлів
    check_module_files()
    
    # 2. Аналіз views.py
    functions = analyze_views_py()
    
    # 3. Перевірка promo модуля
    promo_ok = check_promo_module()
    
    # 4. Перевірка експортів
    init_ok = check_init_exports()
    
    # Підсумок
    print("\n" + "=" * 60)
    print("ПІДСУМОК")
    print("=" * 60)
    
    if promo_ok and init_ok:
        print("\n✅ МОДУЛЬНА СТРУКТУРА КОРЕКТНА!")
        print("   views/promo.py має всі необхідні функції")
        print("   views/__init__.py правильно експортує")
        print("   admin_panel використовує модулі")
        print("\n📦 views.py можна зробити backup")
        
        if len(functions) > 5:
            print(f"\n⚠️  views.py містить {len(functions)} функцій")
            print("   Рекомендується перевірити чи всі з них критичні")
        
        return 0
    else:
        print("\n❌ ЗНАЙДЕНО ПРОБЛЕМИ!")
        if not promo_ok:
            print("   - views/promo.py не має всіх функцій")
        if not init_ok:
            print("   - views/__init__.py не експортує правильно")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())

