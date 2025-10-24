#!/usr/bin/env python3
"""
Скрипт аналізу функцій, що залишились у старому views.py.

Порівнює функції в старому views.py з функціями в нових модулях
та визначає, які функції ще не мігровані.
"""

import re
from pathlib import Path
from typing import Set, Dict, List
from collections import defaultdict

# Кольори для виводу
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str, color=Colors.BLUE):
    """Друк заголовку."""
    print(f"\n{Colors.BOLD}{color}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{color}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{color}{'='*80}{Colors.END}\n")

def get_functions_from_file(file_path: Path) -> Dict[str, int]:
    """
    Отримати словник функцій з файлу: {назва: номер_рядка}.
    """
    functions = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                # Шукаємо def функції на початку рядка
                match = re.match(r'^def ([a-z_][a-z0-9_]*)\s*\(', line)
                if match:
                    func_name = match.group(1)
                    # Пропускаємо приватні функції (що починаються з _)
                    if not func_name.startswith('_'):
                        functions[func_name] = line_num
                
                # Також шукаємо класи (форми тощо)
                class_match = re.match(r'^class ([A-Z][a-zA-Z0-9_]*)', line)
                if class_match:
                    class_name = class_match.group(1)
                    functions[class_name] = line_num
                    
    except Exception as e:
        print(f"{Colors.RED}❌ Помилка читання {file_path}: {e}{Colors.END}")
    
    return functions

def get_all_module_functions(views_dir: Path) -> Dict[str, str]:
    """
    Отримати всі функції з нових модулів.
    Повертає: {назва_функції: назва_модуля}
    """
    all_functions = {}
    
    # Модулі для перевірки (нові модулі міграції)
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
        'utils.py',
        'debug.py',  # Debug functions
    ]
    
    for module_name in modules:
        module_path = views_dir / module_name
        if module_path.exists():
            functions = get_functions_from_file(module_path)
            for func_name in functions.keys():
                all_functions[func_name] = module_name
    
    return all_functions

def categorize_functions(func_name: str) -> str:
    """
    Категоризувати функцію за її назвою.
    """
    name_lower = func_name.lower()
    
    if 'monobank' in name_lower or 'mono' in name_lower:
        return 'Monobank'
    elif 'wholesale' in name_lower or 'pricelist' in name_lower:
        return 'Wholesale'
    elif 'admin' in name_lower:
        return 'Admin'
    elif 'store' in name_lower and 'offline' in name_lower:
        return 'Offline Stores'
    elif 'dropship' in name_lower:
        return 'Dropshipping'
    elif 'cart' in name_lower or 'promo' in name_lower:
        return 'Cart'
    elif 'api' in name_lower or 'json' in name_lower:
        return 'API'
    elif 'login' in name_lower or 'register' in name_lower or 'logout' in name_lower or 'auth' in name_lower:
        return 'Auth'
    elif 'catalog' in name_lower or 'category' in name_lower or 'search' in name_lower:
        return 'Catalog'
    elif 'product' in name_lower and 'admin' not in name_lower:
        return 'Product'
    elif 'checkout' in name_lower or 'order' in name_lower and 'admin' not in name_lower:
        return 'Checkout/Orders'
    elif 'profile' in name_lower or 'favorite' in name_lower or 'points' in name_lower:
        return 'Profile'
    elif 'debug' in name_lower:
        return 'Debug'
    elif any(word in name_lower for word in ['robots', 'sitemap', 'about', 'contact', 'delivery', 'cooperation']):
        return 'Static Pages'
    else:
        return 'Other'

def analyze_remaining_functions(old_views_path: Path, views_dir: Path):
    """
    Проаналізувати функції, що залишились у старому views.py.
    """
    print_header("🔍 АНАЛІЗ ЗАЛИШКОВИХ ФУНКЦІЙ", Colors.CYAN)
    
    # Отримуємо функції зі старого views.py
    old_functions = get_functions_from_file(old_views_path)
    print(f"{Colors.CYAN}ℹ️  Функцій у старому views.py: {len(old_functions)}{Colors.END}")
    
    # Отримуємо всі функції з нових модулів
    new_module_functions = get_all_module_functions(views_dir)
    print(f"{Colors.CYAN}ℹ️  Функцій у нових модулях: {len(new_module_functions)}{Colors.END}")
    
    # Визначаємо, які функції ще не мігровані
    remaining = {}
    migrated = {}
    
    for func_name, line_num in old_functions.items():
        if func_name in new_module_functions:
            migrated[func_name] = (line_num, new_module_functions[func_name])
        else:
            remaining[func_name] = line_num
    
    print(f"{Colors.GREEN}✅ Мігровано: {len(migrated)}{Colors.END}")
    print(f"{Colors.YELLOW}⚠️  Залишилось: {len(remaining)}{Colors.END}")
    
    return old_functions, new_module_functions, migrated, remaining

def print_migrated_summary(migrated: Dict[str, tuple]):
    """
    Вивести підсумок мігрованих функцій.
    """
    print_header("✅ МІГРОВАНІ ФУНКЦІЇ", Colors.GREEN)
    
    # Групуємо за модулями
    by_module = defaultdict(list)
    for func_name, (line_num, module_name) in migrated.items():
        by_module[module_name].append((func_name, line_num))
    
    for module_name in sorted(by_module.keys()):
        functions = sorted(by_module[module_name], key=lambda x: x[1])
        print(f"\n{Colors.BOLD}{module_name}{Colors.END} ({len(functions)} функцій):")
        for func_name, line_num in functions:
            print(f"  • {func_name:40} (рядок {line_num:5})")

def print_remaining_summary(remaining: Dict[str, int]):
    """
    Вивести підсумок залишкових функцій.
    """
    print_header("⚠️ ЗАЛИШКОВІ ФУНКЦІЇ", Colors.YELLOW)
    
    if not remaining:
        print(f"{Colors.GREEN}🎉 Всі функції мігровано!{Colors.END}")
        return
    
    # Групуємо за категоріями
    by_category = defaultdict(list)
    for func_name, line_num in remaining.items():
        category = categorize_functions(func_name)
        by_category[category].append((func_name, line_num))
    
    for category in sorted(by_category.keys()):
        functions = sorted(by_category[category], key=lambda x: x[1])
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}{category}{Colors.END} ({len(functions)} функцій):")
        for func_name, line_num in functions:
            print(f"  • {func_name:40} (рядок {line_num:5})")

def generate_migration_recommendations(remaining: Dict[str, int]):
    """
    Згенерувати рекомендації для міграції залишкових функцій.
    """
    print_header("💡 РЕКОМЕНДАЦІЇ ДЛЯ МІГРАЦІЇ", Colors.BLUE)
    
    if not remaining:
        print(f"{Colors.GREEN}✨ Міграція повністю завершена! Рекомендацій немає.{Colors.END}")
        return
    
    # Групуємо за категоріями
    by_category = defaultdict(list)
    for func_name, line_num in remaining.items():
        category = categorize_functions(func_name)
        by_category[category].append((func_name, line_num))
    
    recommendations = {
        'Auth': ('auth.py', 'Функції аутентифікації'),
        'Cart': ('cart.py', 'Функції кошика та промокодів'),
        'API': ('api.py', 'API endpoints'),
        'Catalog': ('catalog.py', 'Функції каталогу та пошуку'),
        'Product': ('product.py', 'Функції роботи з товарами'),
        'Checkout/Orders': ('checkout.py', 'Функції оформлення замовлень'),
        'Profile': ('profile.py', 'Функції профілю користувача'),
        'Static Pages': ('static_pages.py', 'Статичні сторінки'),
        'Debug': ('debug.py', 'Debug функції (можливо видалити)'),
        'Other': (None, 'Потребують аналізу')
    }
    
    for category in sorted(by_category.keys()):
        functions = by_category[category]
        target_module, description = recommendations.get(category, (None, 'Невідома категорія'))
        
        print(f"\n{Colors.BOLD}{category}{Colors.END} ({len(functions)} функцій)")
        if target_module:
            print(f"  → Рекомендований модуль: {Colors.CYAN}{target_module}{Colors.END}")
        else:
            print(f"  → {Colors.YELLOW}Потребує ручного визначення модуля{Colors.END}")
        print(f"  → {description}")
        
        # Перші 3 функції як приклад
        for func_name, line_num in functions[:3]:
            print(f"     • {func_name} (рядок {line_num})")
        if len(functions) > 3:
            print(f"     ... та ще {len(functions) - 3}")

def generate_cleanup_plan(remaining: Dict[str, int]):
    """
    Згенерувати план очищення старого views.py.
    """
    print_header("🗑️ ПЛАН ОЧИЩЕННЯ", Colors.RED)
    
    total_old_functions = len(remaining)
    
    if total_old_functions == 0:
        print(f"{Colors.GREEN}✅ Всі функції мігровано!{Colors.END}")
        print(f"\n{Colors.BOLD}Наступні кроки:{Colors.END}")
        print("  1. Запустити всі тести")
        print("  2. Перевірити backward compatibility")
        print("  3. Створити backup старого views.py")
        print("  4. Видалити старий views.py")
        print("  5. Оновити __init__.py (видалити _old_views import)")
    else:
        print(f"{Colors.YELLOW}⚠️  Залишилось {total_old_functions} функцій для міграції{Colors.END}")
        print(f"\n{Colors.BOLD}Рекомендації:{Colors.END}")
        print("  1. Мігрувати залишкові функції згідно з рекомендаціями вище")
        print("  2. Оновити __init__.py для нових функцій")
        print("  3. Запустити тести")
        print("  4. Після успішної міграції - видалити старий views.py")

def main():
    """Головна функція."""
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("╔════════════════════════════════════════════════════════════════════════════╗")
    print("║               АНАЛІЗ ЗАЛИШКОВИХ ФУНКЦІЙ У VIEWS.PY                        ║")
    print("║                         TwoComms E-commerce                                ║")
    print("╚════════════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")
    
    # Шляхи до файлів
    project_root = Path(__file__).parent / 'twocomms'
    old_views_path = project_root / 'storefront' / 'views.py'
    views_dir = project_root / 'storefront' / 'views'
    
    if not old_views_path.exists():
        print(f"{Colors.YELLOW}⚠️  Старий views.py не знайдено: {old_views_path}{Colors.END}")
        print(f"{Colors.GREEN}✅ Це означає, що міграція повністю завершена!{Colors.END}")
        return
    
    if not views_dir.exists():
        print(f"{Colors.RED}❌ Директорія views не знайдена: {views_dir}{Colors.END}")
        return
    
    # Аналіз
    old_functions, new_module_functions, migrated, remaining = analyze_remaining_functions(old_views_path, views_dir)
    
    # Виводи
    print_migrated_summary(migrated)
    print_remaining_summary(remaining)
    generate_migration_recommendations(remaining)
    generate_cleanup_plan(remaining)
    
    # Фінальний підсумок
    print_header("📊 ФІНАЛЬНИЙ ПІДСУМОК", Colors.BOLD)
    migration_percent = (len(migrated) / len(old_functions) * 100) if old_functions else 100
    
    print(f"{Colors.BOLD}Статистика міграції:{Colors.END}")
    print(f"  • Всього функцій у старому views.py: {len(old_functions)}")
    print(f"  • Мігровано: {Colors.GREEN}{len(migrated)}{Colors.END}")
    print(f"  • Залишилось: {Colors.YELLOW}{len(remaining)}{Colors.END}")
    print(f"  • Прогрес: {Colors.CYAN}{migration_percent:.1f}%{Colors.END}")
    
    if migration_percent == 100:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 МІГРАЦІЯ ЗАВЕРШЕНА НА 100%! 🎉{Colors.END}")
    elif migration_percent >= 75:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✨ МІГРАЦІЯ МАЙЖЕ ЗАВЕРШЕНА! ✨{Colors.END}")
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚙️  МІГРАЦІЯ В ПРОЦЕСІ... ⚙️{Colors.END}")

if __name__ == '__main__':
    main()

