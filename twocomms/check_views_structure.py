#!/usr/bin/env python3
"""
Скрипт для перевірки структури views та можливості видалення views.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from storefront import views
from storefront.views import (
    promo, cart, api, loyalty
)

def check_imports():
    """Перевірка що всі необхідні функції імпортуються"""
    print("=" * 60)
    print("ПЕРЕВІРКА ІМПОРТІВ З МОДУЛІВ")
    print("=" * 60)
    
    errors = []
    warnings = []
    
    # Промокоди
    print("\n📦 Перевірка модуля PROMO:")
    promo_functions = [
        'get_promo_admin_context',
        'admin_promocode_create',
        'admin_promocode_edit',
        'admin_promocode_toggle',
        'admin_promocode_delete',
        'admin_promo_group_create',
        'admin_promo_group_edit',
        'admin_promo_group_delete',
    ]
    
    for func_name in promo_functions:
        if hasattr(promo, func_name):
            print(f"  ✅ {func_name}")
        else:
            errors.append(f"  ❌ {func_name} не знайдено в promo")
            print(f"  ❌ {func_name}")
    
    # Кошик
    print("\n🛒 Перевірка модуля CART:")
    cart_functions = [
        'apply_promo_code',
        'remove_promo_code',
    ]
    
    for func_name in cart_functions:
        if hasattr(cart, func_name):
            print(f"  ✅ {func_name}")
        else:
            errors.append(f"  ❌ {func_name} не знайдено в cart")
            print(f"  ❌ {func_name}")
    
    # API
    print("\n🔌 Перевірка модуля API:")
    api_functions = [
        'get_product_json',
        'get_categories_json',
    ]
    
    for func_name in api_functions:
        if hasattr(api, func_name):
            print(f"  ✅ {func_name}")
        else:
            warnings.append(f"  ⚠️  {func_name} не знайдено в api")
            print(f"  ⚠️  {func_name}")
    
    # Loyalty
    print("\n⭐ Перевірка модуля LOYALTY:")
    loyalty_functions = [
        'buy_with_points',
        'purchase_with_points',
    ]
    
    for func_name in loyalty_functions:
        if hasattr(loyalty, func_name):
            print(f"  ✅ {func_name}")
        else:
            warnings.append(f"  ⚠️  {func_name} не знайдено в loyalty")
            print(f"  ⚠️  {func_name}")
    
    return errors, warnings


def check_views_py_functions():
    """Перевірка функцій в views.py"""
    print("\n" + "=" * 60)
    print("АНАЛІЗ ФУНКЦІЙ В views.py")
    print("=" * 60)
    
    import inspect
    
    # Отримуємо всі функції з views.py
    views_file = 'storefront/views.py'
    
    with open(views_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Шукаємо всі def функції
    import re
    functions = re.findall(r'^def (\w+)\(', content, re.MULTILINE)
    
    print(f"\nЗнайдено {len(functions)} функцій в views.py:")
    
    critical_functions = []
    modular_functions = []
    
    for func in functions:
        # Перевіряємо чи ця функція є в модулях
        is_in_modules = False
        module_location = None
        
        if hasattr(promo, func):
            is_in_modules = True
            module_location = 'views/promo.py'
        elif hasattr(cart, func):
            is_in_modules = True
            module_location = 'views/cart.py'
        elif hasattr(api, func):
            is_in_modules = True
            module_location = 'views/api.py'
        elif hasattr(loyalty, func):
            is_in_modules = True
            module_location = 'views/loyalty.py'
        
        if is_in_modules:
            print(f"  📁 {func} → {module_location}")
            modular_functions.append(func)
        else:
            print(f"  🔴 {func} → ТІЛЬКИ В views.py (критична)")
            critical_functions.append(func)
    
    print(f"\n📊 Статистика:")
    print(f"  - Функцій в модулях: {len(modular_functions)}")
    print(f"  - Критичних функцій: {len(critical_functions)}")
    
    if critical_functions:
        print(f"\n⚠️  КРИТИЧНІ ФУНКЦІЇ (потрібно перенести або залишити):")
        for func in critical_functions:
            print(f"    - {func}")
    
    return critical_functions


def check_admin_panel_dependencies():
    """Перевірка що admin_panel використовує тільки модулі"""
    print("\n" + "=" * 60)
    print("ПЕРЕВІРКА ЗАЛЕЖНОСТЕЙ admin_panel")
    print("=" * 60)
    
    with open('storefront/views.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Знаходимо функцію admin_panel
    import re
    admin_panel_match = re.search(
        r'def admin_panel\(.*?\):(.*?)(?=\ndef |\Z)',
        content,
        re.DOTALL
    )
    
    if admin_panel_match:
        admin_panel_code = admin_panel_match.group(1)
        
        # Перевіряємо чи використовує модулі для промокодів
        if 'get_promo_admin_context' in admin_panel_code:
            print("  ✅ admin_panel використовує get_promo_admin_context() з модуля promo")
        else:
            print("  ❌ admin_panel НЕ використовує модульну функцію для промокодів!")
        
        # Перевіряємо чи є прямі імпорти моделей промокодів
        if 'PromoCode.objects' in admin_panel_code and 'get_promo_admin_context' not in admin_panel_code:
            print("  ⚠️  admin_panel має прямі запити до PromoCode (дублювання логіки)")
        else:
            print("  ✅ admin_panel не дублює логіку промокодів")
    
    return True


def main():
    print("\n" + "🔍" * 30)
    print("ДЕТАЛЬНА ПЕРЕВІРКА СТРУКТУРИ VIEWS")
    print("🔍" * 30 + "\n")
    
    # 1. Перевірка імпортів
    errors, warnings = check_imports()
    
    # 2. Аналіз views.py
    critical_functions = check_views_py_functions()
    
    # 3. Перевірка admin_panel
    check_admin_panel_dependencies()
    
    # Підсумок
    print("\n" + "=" * 60)
    print("ПІДСУМОК")
    print("=" * 60)
    
    if errors:
        print(f"\n❌ ПОМИЛКИ ({len(errors)}):")
        for error in errors:
            print(error)
    
    if warnings:
        print(f"\n⚠️  ПОПЕРЕДЖЕННЯ ({len(warnings)}):")
        for warning in warnings:
            print(warning)
    
    if not errors and len(critical_functions) <= 1:
        print("\n✅ ВСЕ ДОБРЕ!")
        print("   Структура модульна, views.py можна бекапити")
        if critical_functions:
            print(f"   Критичні функції: {', '.join(critical_functions)}")
            print("   (це нормально якщо це admin_panel або подібна головна функція)")
        return 0
    else:
        print("\n⚠️  ПОТРІБНА УВАГА!")
        print(f"   Знайдено {len(errors)} помилок")
        print(f"   Знайдено {len(critical_functions)} критичних функцій в views.py")
        return 1


if __name__ == '__main__':
    sys.exit(main())

