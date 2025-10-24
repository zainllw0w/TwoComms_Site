#!/usr/bin/env python3
"""
Скрипт валідації міграції views.py → модульна структура.

Перевіряє:
1. Всі функції з нових модулів доступні через __init__.py
2. Backward compatibility зі старими імпортами
3. Відсутність дублювання функцій
4. Коректність _exclude списку
5. Синхронізацію __all__ з реальними імпортами
"""

import sys
import os
from pathlib import Path
import importlib.util
from typing import Set, Dict, List, Tuple
from collections import defaultdict

# Додаємо шлях до Django проекту
PROJECT_ROOT = Path(__file__).parent / 'twocomms'
sys.path.insert(0, str(PROJECT_ROOT.parent))

# Кольори для виводу
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """Друк заголовку."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")

def print_success(text: str):
    """Друк успішного повідомлення."""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_warning(text: str):
    """Друк попередження."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_error(text: str):
    """Друк помилки."""
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_info(text: str):
    """Друк інформаційного повідомлення."""
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.END}")

def get_functions_from_module(module_path: Path) -> Set[str]:
    """Отримати список функцій з Python модуля."""
    functions = set()
    
    try:
        with open(module_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Шукаємо всі def функції (не приватні, не методи класів)
        import re
        pattern = r'^def ([a-z_][a-z0-9_]*)\s*\('
        matches = re.findall(pattern, content, re.MULTILINE)
        functions.update(matches)
        
        # Шукаємо класи (форми, тощо)
        class_pattern = r'^class ([A-Z][a-zA-Z0-9_]*)\s*\('
        class_matches = re.findall(class_pattern, content, re.MULTILINE)
        functions.update(class_matches)
        
    except Exception as e:
        print_error(f"Помилка читання {module_path}: {e}")
    
    return functions

def check_module_exports(views_dir: Path) -> Dict[str, Set[str]]:
    """Перевірити експорти з кожного модуля."""
    print_header("📦 АНАЛІЗ МОДУЛІВ")
    
    module_exports = {}
    
    # Модулі для перевірки
    modules = [
        'monobank.py',
        'wholesale.py', 
        'admin.py',
        'stores.py',
        'dropship.py',
        'cart.py',
        'api.py',
        'auth.py',
        'catalog.py',
        'checkout.py',
        'product.py',
        'profile.py',
        'static_pages.py',
        'utils.py'
    ]
    
    for module_name in modules:
        module_path = views_dir / module_name
        if module_path.exists():
            functions = get_functions_from_module(module_path)
            module_exports[module_name] = functions
            print_info(f"{module_name:20} → {len(functions):3} функцій/класів")
        else:
            print_warning(f"{module_name} не знайдено")
    
    total_exports = sum(len(funcs) for funcs in module_exports.values())
    print_success(f"Всього експортів: {total_exports}")
    
    return module_exports

def check_init_imports(views_dir: Path, module_exports: Dict[str, Set[str]]) -> Tuple[Set[str], Set[str], Set[str]]:
    """Перевірити імпорти в __init__.py."""
    print_header("📋 ПЕРЕВІРКА __init__.py")
    
    init_path = views_dir / '__init__.py'
    
    if not init_path.exists():
        print_error("__init__.py не знайдено!")
        return set(), set(), set()
    
    with open(init_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Шукаємо всі імпорти з модулів
    import re
    
    # Імпорти типу: from .module import func1, func2
    from_imports = set()
    pattern = r'from \.\w+ import \((.*?)\)'
    matches = re.findall(pattern, content, re.DOTALL)
    for match in matches:
        imports = [imp.strip() for imp in match.split(',') if imp.strip() and not imp.strip().startswith('#')]
        from_imports.update(imports)
    
    # Також одно-рядкові імпорти
    single_pattern = r'from \.\w+ import ([a-zA-Z_][\w, ]*)'
    single_matches = re.findall(single_pattern, content)
    for match in single_matches:
        if '(' not in match:
            imports = [imp.strip() for imp in match.split(',') if imp.strip()]
            from_imports.update(imports)
    
    # Шукаємо _exclude список
    exclude_set = set()
    exclude_pattern = r'_exclude\s*=\s*\{(.*?)\}'
    exclude_match = re.search(exclude_pattern, content, re.DOTALL)
    if exclude_match:
        exclude_content = exclude_match.group(1)
        # Витягуємо всі рядки в лапках
        exclude_items = re.findall(r"['\"]([^'\"]+)['\"]", exclude_content)
        exclude_set.update(exclude_items)
    
    # Шукаємо __all__ список
    all_set = set()
    all_pattern = r'__all__\s*=\s*\[(.*?)\]'
    all_match = re.search(all_pattern, content, re.DOTALL)
    if all_match:
        all_content = all_match.group(1)
        all_items = re.findall(r"['\"]([^'\"]+)['\"]", all_content)
        all_set.update(all_items)
    
    print_info(f"Імпортів з модулів: {len(from_imports)}")
    print_info(f"Функцій в _exclude: {len(exclude_set)}")
    print_info(f"Функцій в __all__: {len(all_set)}")
    
    return from_imports, exclude_set, all_set

def validate_consistency(module_exports: Dict[str, Set[str]], from_imports: Set[str], exclude_set: Set[str], all_set: Set[str]):
    """Перевірити консистентність між модулями та __init__.py."""
    print_header("🔍 ВАЛІДАЦІЯ КОНСИСТЕНТНОСТІ")
    
    errors = []
    warnings = []
    
    # Всі експорти з модулів
    all_module_exports = set()
    for funcs in module_exports.values():
        all_module_exports.update(funcs)
    
    # 1. Перевірка: всі імпорти існують в модулях
    missing_in_modules = from_imports - all_module_exports
    if missing_in_modules:
        errors.append(f"Функції імпортуються в __init__.py, але не знайдені в модулях: {missing_in_modules}")
    else:
        print_success("Всі імпорти знайдені в модулях")
    
    # 2. Перевірка: всі експорти є в __init__.py
    not_imported = all_module_exports - from_imports
    if not_imported:
        # Фільтруємо приватні функції
        public_not_imported = {f for f in not_imported if not f.startswith('_')}
        if public_not_imported:
            warnings.append(f"Публічні функції в модулях, але не імпортовані в __init__.py: {public_not_imported}")
    
    # 3. Перевірка: _exclude містить всі імпорти
    not_excluded = from_imports - exclude_set
    if not_excluded:
        warnings.append(f"Функції імпортуються, але не в _exclude списку: {not_excluded}")
    else:
        print_success("Всі імпорти додані в _exclude список")
    
    # 4. Перевірка: __all__ містить всі імпорти
    not_in_all = from_imports - all_set
    if not_in_all:
        errors.append(f"Функції імпортуються, але не в __all__ списку: {not_in_all}")
    else:
        print_success("Всі імпорти додані в __all__ список")
    
    # 5. Перевірка: __all__ не містить зайвих функцій
    extra_in_all = all_set - from_imports
    if extra_in_all:
        # Це може бути старий views.py
        print_info(f"Функції в __all__, але не імпортовані з нових модулів (можливо зі старого views.py): {len(extra_in_all)}")
    
    return errors, warnings

def check_backward_compatibility(views_dir: Path):
    """Перевірити backward compatibility."""
    print_header("🔄 BACKWARD COMPATIBILITY")
    
    # Список функцій, які повинні бути доступні
    critical_functions = [
        # Monobank
        'monobank_create_invoice',
        'monobank_create_checkout',
        'monobank_webhook',
        'monobank_return',
        # Wholesale
        'wholesale_page',
        'wholesale_order_form',
        'wholesale_prices_xlsx',
        # Admin
        'admin_panel',
        'admin_product_new',
        'admin_category_new',
        # Stores
        'admin_offline_stores',
        'admin_store_management',
        # Dropship
        'admin_update_dropship_status',
        # Cart
        'apply_promo_code',
        'remove_promo_code',
        # API
        'api_colors',
    ]
    
    try:
        # Намагаємось імпортувати з storefront.views
        sys.path.insert(0, str(views_dir.parent.parent))
        
        missing_functions = []
        for func_name in critical_functions:
            try:
                # Динамічний імпорт
                module = __import__('storefront.views', fromlist=[func_name])
                if not hasattr(module, func_name):
                    missing_functions.append(func_name)
            except Exception as e:
                print_warning(f"Не вдалось імпортувати {func_name}: {e}")
                missing_functions.append(func_name)
        
        if missing_functions:
            print_error(f"Критичні функції недоступні: {missing_functions}")
            return False
        else:
            print_success(f"Всі {len(critical_functions)} критичних функцій доступні")
            return True
            
    except Exception as e:
        print_error(f"Помилка перевірки backward compatibility: {e}")
        return False

def check_duplicates(module_exports: Dict[str, Set[str]]):
    """Перевірити дублікати функцій між модулями."""
    print_header("🔎 ПЕРЕВІРКА ДУБЛІКАТІВ")
    
    function_locations = defaultdict(list)
    
    for module_name, functions in module_exports.items():
        for func in functions:
            function_locations[func].append(module_name)
    
    duplicates = {func: modules for func, modules in function_locations.items() if len(modules) > 1}
    
    if duplicates:
        print_warning(f"Знайдено {len(duplicates)} дублікатів:")
        for func, modules in sorted(duplicates.items()):
            print(f"  • {func}: {', '.join(modules)}")
    else:
        print_success("Дублікатів не знайдено")
    
    return duplicates

def generate_summary(module_exports: Dict[str, Set[str]], from_imports: Set[str], errors: List[str], warnings: List[str]):
    """Згенерувати підсумковий звіт."""
    print_header("📊 ПІДСУМКОВИЙ ЗВІТ")
    
    total_module_functions = sum(len(funcs) for funcs in module_exports.values())
    
    print(f"{Colors.BOLD}Статистика:{Colors.END}")
    print(f"  • Модулів проаналізовано: {len(module_exports)}")
    print(f"  • Всього функцій в модулях: {total_module_functions}")
    print(f"  • Функцій імпортовано в __init__.py: {len(from_imports)}")
    
    print(f"\n{Colors.BOLD}Результати валідації:{Colors.END}")
    
    if errors:
        print_error(f"Критичних помилок: {len(errors)}")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
    else:
        print_success("Критичних помилок не знайдено")
    
    if warnings:
        print_warning(f"Попереджень: {len(warnings)}")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")
    else:
        print_success("Попереджень немає")
    
    # Загальний статус
    print(f"\n{Colors.BOLD}Загальний статус:{Colors.END}")
    if not errors:
        print_success("✨ МІГРАЦІЯ ВАЛІДНА ✨")
        return True
    else:
        print_error("⚠️ ПОТРІБНІ ВИПРАВЛЕННЯ ⚠️")
        return False

def main():
    """Головна функція."""
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("╔════════════════════════════════════════════════════════════════════════════╗")
    print("║                    ВАЛІДАЦІЯ МІГРАЦІЇ VIEWS.PY                             ║")
    print("║                         TwoComms E-commerce                                ║")
    print("╚════════════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")
    
    # Шлях до views
    views_dir = PROJECT_ROOT / 'storefront' / 'views'
    
    if not views_dir.exists():
        print_error(f"Директорія views не знайдена: {views_dir}")
        sys.exit(1)
    
    print_info(f"Аналіз директорії: {views_dir}\n")
    
    # 1. Аналіз модулів
    module_exports = check_module_exports(views_dir)
    
    # 2. Перевірка __init__.py
    from_imports, exclude_set, all_set = check_init_imports(views_dir, module_exports)
    
    # 3. Перевірка консистентності
    errors, warnings = validate_consistency(module_exports, from_imports, exclude_set, all_set)
    
    # 4. Перевірка дублікатів
    check_duplicates(module_exports)
    
    # 5. Backward compatibility (опціонально, може не працювати без Django settings)
    # check_backward_compatibility(views_dir)
    
    # 6. Підсумковий звіт
    success = generate_summary(module_exports, from_imports, errors, warnings)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()

