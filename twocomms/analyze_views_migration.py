# -*- coding: utf-8 -*-
import re
from pathlib import Path

def get_functions_from_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return set(re.findall(r'^def (\w+)\(', content, re.MULTILINE))
    except:
        return set()

def get_exclude_list():
    init_path = Path('storefront/views/__init__.py')
    with open(init_path, 'r', encoding='utf-8') as f:
        content = f.read()
    exclude_match = re.search(r'_exclude = \{(.*?)\}', content, re.DOTALL)
    if exclude_match:
        exclude_str = exclude_match.group(1)
        return set(re.findall(r"'([^']+)'", exclude_str))
    return set()

def main():
    print("="*70)
    print("VIEWS MIGRATION ANALYSIS")
    print("="*70)
    
    views_py_funcs = get_functions_from_file('storefront/views.py')
    print("\n[*] views.py: {} functions".format(len(views_py_funcs)))
    
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
    print("\n[*] Modules:")
    for module_name, funcs in modules.items():
        if funcs:
            print("  [+] {}: {} functions".format(module_name, len(funcs)))
            all_module_funcs.update(funcs)
        else:
            print("  [-] {}: not found or empty".format(module_name))
    
    print("\n  Total in modules: {} functions".format(len(all_module_funcs)))
    
    exclude_list = get_exclude_list()
    print("\n[*] _exclude list: {} items".format(len(exclude_list)))
    
    still_in_views_py = views_py_funcs - all_module_funcs - exclude_list
    
    print("\n[!] FUNCTIONS STILL ONLY IN views.py: {}".format(len(still_in_views_py)))
    
    if still_in_views_py:
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
                print("\n  [>] {} ({}):".format(category, len(funcs)))
                for func in funcs[:10]:  # First 10 only
                    print("     - {}".format(func))
                if len(funcs) > 10:
                    print("     ... and {} more".format(len(funcs) - 10))
    
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    
    if not still_in_views_py:
        print("\n[YES] ALL FUNCTIONS MIGRATED TO MODULES!")
        print("   Can:")
        print("   1. Remove import block from views.py in __init__.py (lines 179-254)")
        print("   2. Delete views.py itself")
    else:
        print("\n[NO] {} functions still need to be migrated".format(len(still_in_views_py)))
        print("   Need to:")
        print("   1. Move functions to appropriate modules")
        print("   2. Add them to _exclude list")
        print("   3. Then can delete views.py")
    
    duplicates = views_py_funcs & all_module_funcs
    if duplicates:
        print("\n[!] DUPLICATES (in views.py AND modules): {}".format(len(duplicates)))
        for func in sorted(list(duplicates)[:5]):
            for module_name, funcs in modules.items():
                if func in funcs:
                    print("     - {} (in {})".format(func, module_name))
                    break

if __name__ == '__main__':
    main()
