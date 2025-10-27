#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализ какие функции все еще в views.py и не перенесены в модули
"""
import re
from pathlib import Path

def get_functions_from_file(filepath):
    """Получить все функции"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return set(re.findall(r'^def (\w+)\(', content, re.MULTILINE))
    except:
        return set()

def get_exclude_list():
    """Получить список исключений из __init__.py"""
    init_path = Path('storefront/views/__init__.py')
    with open(init_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Найти _exclude = {...}
    exclude_match = re.search(r'_exclude = \{(.*?)\}', content, re.DOTALL)
    if exclude_match:
        exclude_str = exclude_match.group(1)
        # Извлечь все строки в кавычках
        return set(re.findall(r"'([^']+)'", exclude_str))
    return set()

def main():
    print("="*70)
    print("АНАЛИЗ МІГРАЦІЇ views.py -> модулі")
    print("="*70)
    
    # 1. Функции из views.py
    views_py_funcs = get_functions_from_file('storefront/views.py')
    print(f"\n📄 views.py: {len(views_py_funcs)} функцій")
    
    # 2. Функции из модулей
    modules = {
        'views/cart.py': get_functions_from_file('storefront/views/cart.py'),
        'views/promo.py': get_functions_from_file('storefront/views/promo.py'),
        'views/api.py': get_functions_from_file('storefront/views/api.py'),
        'views/auth.py': get_functions_from_file('storefront/views/auth.py'),
        'views/catalog.py': get_functions_from_file('storefront/views/catalog.py'),
        'views/product.py': get_functions_from_file('storefront/views/product.py'),
        'views/checkout.py': get_functions_from_file('storefront/views/checkout.py'),
        'views/profile.py': get_functions_from_file('storefront/views/profile.py'),
        'views/admin.py': get_functions_from_file('storefront/views/admin.py'),
        'views/static_pages.py': get_functions_from_file('storefront/views/static_pages.py'),
        'views/utils.py': get_functions_from_file('storefront/views/utils.py'),
    }
    
    all_module_funcs = set()
    print("\n📦 Модулі:")
    for module_name, funcs in modules.items():
        if funcs:
            print(f"  ✅ {module_name}: {len(funcs)} функцій")
            all_module_funcs.update(funcs)
        else:
            print(f"  ❌ {module_name}: файл не знайдено або порожній")
    
    print(f"\n  Всього в модулях: {len(all_module_funcs)} функцій")
    
    # 3. Exclude list
    exclude_list = get_exclude_list()
    print(f"\n🚫 _exclude список: {len(exclude_list)} елементів")
    
    # 4. Функции которые ВСЕ ЕЩЕ в views.py и НЕ в модулях
    still_in_views_py = views_py_funcs - all_module_funcs - exclude_list
    
    print(f"\n⚠️  ФУНКЦІЇ ЯКІ ВСЕ ЩЕ ТІЛЬКИ В views.py: {len(still_in_views_py)}")
    
    if still_in_views_py:
        # Группируем по категориям
        categories = {
            'Admin': [],
            'Order/Checkout': [],
            'Monobank/Payment': [],
            'Wholesale': [],
            'Feed/SEO': [],
            'Other': [],
        }
        
        for func in sorted(still_in_views_py):
            if 'admin_' in func:
                categories['Admin'].append(func)
            elif 'order_' in func or 'checkout' in func:
                categories['Order/Checkout'].append(func)
            elif 'monobank' in func or 'payment' in func or 'invoice' in func:
                categories['Monobank/Payment'].append(func)
            elif 'wholesale' in func or 'pricelist' in func:
                categories['Wholesale'].append(func)
            elif 'feed' in func or 'sitemap' in func or 'seo' in func:
                categories['Feed/SEO'].append(func)
            else:
                categories['Other'].append(func)
        
        for category, funcs in categories.items():
            if funcs:
                print(f"\n  📁 {category} ({len(funcs)}):")
                for func in funcs:
                    print(f"     - {func}")
    
    # 5. Рекомендации
    print("\n" + "="*70)
    print("РЕКОМЕНДАЦІЇ")
    print("="*70)
    
    if not still_in_views_py:
        print("\n✅ ВСІ ФУНКЦІЇ ПЕРЕНЕСЕНІ В МОДУЛІ!")
        print("   Можна:")
        print("   1. Видалити блок import з views.py в __init__.py (рядки 179-254)")
        print("   2. Видалити сам views.py")
    else:
        print(f"\n⚠️  {len(still_in_views_py)} функцій все ще потрібно перенести")
        print("   Потрібно:")
        print("   1. Перенести функції в відповідні модулі")
        print("   2. Додати їх в _exclude список")
        print("   3. Тоді можна видалити views.py")
    
    # 6. Функции которые в модулях И в views.py (дублікати)
    duplicates = views_py_funcs & all_module_funcs
    if duplicates:
        print(f"\n⚠️  ДУБЛІКАТИ (в views.py І в модулях): {len(duplicates)}")
        for func in sorted(duplicates):
            # Знайти в якому модулі
            for module_name, funcs in modules.items():
                if func in funcs:
                    print(f"     - {func} (в {module_name})")
                    break

if __name__ == '__main__':
    main()

