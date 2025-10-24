"""
Storefront views package.

Рефакторинг views.py на модульную структуру.

Этот файл обеспечивает обратную совместимость, импортируя все views
из соответствующих модулей и из старого views.py.

Структура:
- utils.py - Утилиты и helper функции
- auth.py - Аутентификация (login, register, logout)
- catalog.py - Каталог товаров (в разработке)
- product.py - Детали товара (в разработке)
- cart.py - Корзина (в разработке)
- checkout.py - Оформление заказа (в разработке)
- profile.py - Профиль пользователя (в разработке)
- admin.py - Админ панель (в разработке)
- api.py - AJAX/API endpoints (в разработке)
- static_pages.py - Статические страницы (в разработке)
"""

# ==================== НОВЫЕ МОДУЛИ ====================

# Утилиты
from .utils import (
    cache_page_for_anon,
    unique_slugify,
    get_cart_from_session,
    save_cart_to_session,
    calculate_cart_total,
    get_favorites_from_session,
    save_favorites_to_session,
    HOME_PRODUCTS_PER_PAGE,
)

# Аутентификация
from .auth import (
    # Forms
    LoginForm,
    RegisterForm,
    ProfileSetupForm,
    # Views
    login_view,
    register_view,
    logout_view,
)

# Каталог
from .catalog import (
    home,
    load_more_products,
    catalog,
    search,
)

# Товары
from .product import (
    product_detail,
    add_product,
    add_category,
    add_print,
)

# Корзина
from .cart import (
    add_to_cart,
    cart_summary,
    cart_mini,
    cart_remove,
    cart,
    remove_promo_code,
)

# Статические страницы
from .static_pages import (
    uaprom_products_feed,
    google_merchant_feed,
    robots_txt,
    static_verification_file,
    static_sitemap,
)

# Профиль
from .profile import (
    profile_setup_db,
    favorites_list,
    favorites_count,
    toggle_favorite,
    profile_view,
    edit_profile,
    change_password,
    user_orders,
    user_order_detail,
    user_points_history,
    cooperation_view,
)

# API endpoints
from .api import (
    get_product_variants_api,
    get_product_info_api,
    get_product_price_api,
    get_product_images_api,
    get_category_products_api,
    get_categories_api,
    get_cart_items_api,
    apply_promo_code_api,
    get_order_status_api,
    get_user_profile_api,
)

# Оформление заказа
from .checkout import (
    checkout_view,
    create_order,
    monobank_webhook,
    monobank_return,
    monobank_checkout_view,
    monobank_checkout_callback,
    monobank_checkout_return,
    monobank_checkout_status,
)

# Админка
from .admin import (
    admin_dashboard,
    admin_orders,
    admin_order_detail,
    admin_products,
    admin_product_edit,
    admin_categories,
    admin_category_edit,
    admin_users,
    admin_user_edit,
    admin_promo_codes,
    admin_promo_code_edit,
    admin_print_proposals,
    admin_print_proposal_detail,
)


# ==================== ВРЕМЕННЫЙ ИМПОРТ ИЗ СТАРОГО views.py ====================
# TODO: Постепенно мигрировать все функции в соответствующие модули

# Импортируем все остальное из старого views.py
# Это обеспечивает обратную совместимость во время рефакторинга
import sys
import os

# Получаем путь к старому views.py (на уровень выше)
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)

try:
    # Импортируем старый модуль views
    from storefront import views as _old_views
    
    # Список функций/классов для НЕ импорта (уже есть в новых модулях)
    _exclude = {
        # utils.py
        'cache_page_for_anon', 'unique_slugify', 'get_cart_from_session',
        'save_cart_to_session', 'calculate_cart_total', 'get_favorites_from_session',
        'save_favorites_to_session', 'HOME_PRODUCTS_PER_PAGE',
        # auth.py
        'LoginForm', 'RegisterForm', 'ProfileSetupForm',
        'login_view', 'register_view', 'logout_view',
        # catalog.py
        'home', 'load_more_products', 'catalog', 'search',
        # product.py
        'product_detail', 'add_product', 'add_category', 'add_print',
        # cart.py
        'add_to_cart', 'cart_summary', 'cart_mini', 'cart_remove', 'cart', 'remove_promo_code',
        # static_pages.py
        'uaprom_products_feed', 'google_merchant_feed', 'robots_txt', 
        'static_verification_file', 'static_sitemap',
        # profile.py
        'profile_setup_db', 'favorites_list', 'favorites_count', 'toggle_favorite',
        'profile_view', 'edit_profile', 'change_password', 'user_orders',
        'user_order_detail', 'user_points_history', 'cooperation_view',
        # api.py
        'get_product_variants_api', 'get_product_info_api', 'get_product_price_api',
        'get_product_images_api', 'get_category_products_api', 'get_categories_api',
        'get_cart_items_api', 'apply_promo_code_api', 'get_order_status_api', 'get_user_profile_api',
        # checkout.py
        'checkout_view', 'create_order', 'monobank_webhook', 'monobank_return',
        'monobank_checkout_view', 'monobank_checkout_callback', 'monobank_checkout_return',
        'monobank_checkout_status',
        # admin.py
        'admin_dashboard', 'admin_orders', 'admin_order_detail', 'admin_products',
        'admin_product_edit', 'admin_categories', 'admin_category_edit', 'admin_users',
        'admin_user_edit', 'admin_promo_codes', 'admin_promo_code_edit',
        'admin_print_proposals', 'admin_print_proposal_detail',
        # Технические атрибуты Python
        '__name__', '__doc__', '__package__', '__loader__', '__spec__',
        '__file__', '__cached__', '__builtins__',
    }
    
    # Импортируем все остальное из старого views
    for name in dir(_old_views):
        if not name.startswith('_') and name not in _exclude:
            globals()[name] = getattr(_old_views, name)
            
finally:
    # Убираем parent_dir из sys.path
    if parent_dir in sys.path:
        sys.path.remove(parent_dir)


# ==================== ЭКСПОРТЫ ====================

__all__ = [
    # Utils
    'cache_page_for_anon', 'unique_slugify', 'get_cart_from_session',
    'save_cart_to_session', 'calculate_cart_total', 'get_favorites_from_session',
    'save_favorites_to_session', 'HOME_PRODUCTS_PER_PAGE',
    
    # Auth
    'LoginForm', 'RegisterForm', 'ProfileSetupForm',
    'login_view', 'register_view', 'logout_view',
    
    # Catalog
    'home', 'load_more_products', 'catalog', 'search',
    
    # Product
    'product_detail', 'add_product', 'add_category', 'add_print',
    
    # Cart
    'add_to_cart', 'cart_summary', 'cart_mini', 'cart_remove', 'cart', 'remove_promo_code',
    
    # Static Pages
    'uaprom_products_feed', 'google_merchant_feed', 'robots_txt', 
    'static_verification_file', 'static_sitemap',
    
    # Profile
    'profile_setup_db', 'favorites_list', 'favorites_count', 'toggle_favorite',
    'profile_view', 'edit_profile', 'change_password', 'user_orders',
    'user_order_detail', 'user_points_history', 'cooperation_view',
    
    # API
    'get_product_variants_api', 'get_product_info_api', 'get_product_price_api',
    'get_product_images_api', 'get_category_products_api', 'get_categories_api',
    'get_cart_items_api', 'apply_promo_code_api', 'get_order_status_api', 'get_user_profile_api',
    
    # Checkout
    'checkout_view', 'create_order', 'monobank_webhook', 'monobank_return',
    'monobank_checkout_view', 'monobank_checkout_callback', 'monobank_checkout_return',
    'monobank_checkout_status',
    
    # Admin
    'admin_dashboard', 'admin_orders', 'admin_order_detail', 'admin_products',
    'admin_product_edit', 'admin_categories', 'admin_category_edit', 'admin_users',
    'admin_user_edit', 'admin_promo_codes', 'admin_promo_code_edit',
    'admin_print_proposals', 'admin_print_proposal_detail',
]

