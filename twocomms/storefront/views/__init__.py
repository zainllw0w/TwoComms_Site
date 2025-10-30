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

from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

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
    get_product_images,
    get_product_variants,
    quick_view,
)

# Корзина
from .cart import (
    view_cart,
    add_to_cart,
    update_cart,
    remove_from_cart,
    clear_cart,
    get_cart_count,
    apply_promo_code,
    remove_promo_code,
    cart_summary,
    cart_mini,
    contact_manager,
)

# Статические страницы
from .static_pages import (
    robots_txt,
    static_sitemap,
    google_merchant_feed,
    uaprom_products_feed,
    static_verification_file,
    about,
    contacts,
    delivery,
    returns,
    privacy_policy,
    terms_of_service,
)

# Профиль
from .profile import (
    profile,
    edit_profile,
    profile_setup,
    order_history,
    order_detail,
    favorites,
    favorites_list,
    toggle_favorite,
    add_to_favorites,
    remove_from_favorites,
    check_favorite_status,
    favorites_count,
    points_history,
    settings,
    # User Points & Rewards
    user_points,
    my_promocodes,
    buy_with_points,
    purchase_with_points,
)

# Промокоды
from .promo import (
    # Helper functions
    get_promo_admin_context,
    # Forms
    PromoCodeForm,
    PromoCodeGroupForm,
    # Admin views
    admin_promocodes,
    admin_promocode_create,
    admin_promocode_edit,
    admin_promocode_toggle,
    admin_promocode_delete,
    # Groups
    admin_promo_groups,
    admin_promo_group_create,
    admin_promo_group_edit,
    admin_promo_group_delete,
    # Statistics
    admin_promo_stats,
    # AJAX endpoints
    admin_promocode_get_form,
    admin_promocode_edit_ajax,
    admin_promo_group_get_form,
    admin_promo_group_edit_ajax,
    admin_promocode_change_group,
    admin_promo_export,
)

# API endpoints
from .api import (
    get_product_json,
    get_categories_json,
    track_event,
    search_suggestions,
    product_availability,
    get_related_products,
    newsletter_subscribe,
    contact_form,
)

# Оформление заказа
from .checkout import (
    checkout,
    create_order,
    payment_method,
    monobank_webhook,
    payment_callback,
    order_success,
    order_failed,
    calculate_shipping,
)

# Monobank оплата
from .monobank import (
    monobank_create_invoice,
)

# Админка
from .admin import (
    admin_dashboard,
    manage_products,
    add_product,
    admin_product_builder,
    add_category,
    add_print,
    manage_print_proposals,
    manage_promo_codes,
    generate_seo_content,
    generate_alt_texts,
    manage_orders,
    sales_statistics,
    inventory_management,
)


# ==================== ВРЕМЕННЫЙ ИМПОРТ ИЗ СТАРОГО views.py ====================
# TODO: Постепенно мигрировать все функции в соответствующие модули

# Импортируем все остальное из старого views.py
# Это обеспечивает обратную совместимость во время рефакторинга
import sys
import os
import importlib.util

# КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Инициализируем _old_views=None чтобы избежать NameError
_old_views = None

try:
    # Явно импортируем старый views.py файл (не пакет views/)
    views_py_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'views.py')
    spec = importlib.util.spec_from_file_location("storefront.views_old", views_py_path)
    _old_views = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_old_views)
    
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
        'product_detail', 'get_product_images', 'get_product_variants', 'quick_view',
        # cart.py
        'view_cart', 'add_to_cart', 'update_cart', 'remove_from_cart', 'clear_cart',
        'get_cart_count', 'apply_promo_code', 'remove_promo_code', 'cart_summary', 'cart_mini',
        # static_pages.py
        'robots_txt', 'static_sitemap', 'google_merchant_feed', 'uaprom_products_feed',
        'static_verification_file', 'about', 'contacts', 'delivery', 'returns',
        'privacy_policy', 'terms_of_service',
        # profile.py
        'profile', 'edit_profile', 'profile_setup', 'order_history', 'order_detail',
        'favorites', 'favorites_list', 'toggle_favorite', 'add_to_favorites', 
        'remove_from_favorites', 'check_favorite_status', 'favorites_count', 
        'points_history', 'settings',
        'user_points', 'my_promocodes', 'buy_with_points', 'purchase_with_points',
        # promo.py
        'PromoCodeForm', 'PromoCodeGroupForm', 'get_promo_admin_context',
        'admin_promocodes', 'admin_promocode_create', 'admin_promocode_edit',
        'admin_promocode_toggle', 'admin_promocode_delete',
        'admin_promo_groups', 'admin_promo_group_create', 'admin_promo_group_edit',
        'admin_promo_group_delete', 'admin_promo_stats',
        'admin_promocode_get_form', 'admin_promocode_edit_ajax',
        'admin_promo_group_get_form', 'admin_promo_group_edit_ajax',
        'admin_promocode_change_group', 'admin_promo_export',
        # api.py
        'get_product_json', 'get_categories_json', 'track_event', 'search_suggestions',
        'product_availability', 'get_related_products', 'newsletter_subscribe', 'contact_form',
        # checkout.py
        'checkout', 'create_order', 'payment_method', 'monobank_webhook', 'payment_callback',
        'order_success', 'order_failed', 'calculate_shipping',
        # admin.py
        'admin_dashboard', 'manage_products', 'add_product', 'add_category', 'add_print',
        'manage_print_proposals', 'manage_promo_codes', 'generate_seo_content',
        'generate_alt_texts', 'manage_orders', 'sales_statistics', 'inventory_management',
        # monobank.py
        'monobank_create_invoice',
        # Aliases (чтобы не конфликтовали)
        'cart', 'cart_remove', 'clean_cart', 'profile_setup_db', 'order_create', 'register_view_new',
        # Технические атрибуты Python
        '__name__', '__doc__', '__package__', '__loader__', '__spec__',
        '__file__', '__cached__', '__builtins__',
    }
    
    # Импортируем все остальное из старого views
    if _old_views:
        for name in dir(_old_views):
            if not name.startswith('_') and name not in _exclude:
                globals()[name] = getattr(_old_views, name)
            
except Exception as e:
    # Если не удалось импортировать старый views.py, это нормально
    # (например, если его уже удалили после полной миграции)
    import warnings
    warnings.warn(f"Could not import old views.py: {e}")
    _old_views = None  # Убеждаемся что _old_views определен


# ==================== АЛИАСЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ ====================
# Эти алиасы обеспечивают совместимость с старым views.py и storefront/urls.py

# КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем старую cart() из views.py, т.к. она обрабатывает POST
# view_cart() из cart.py НЕ обрабатывает form_type и создание заказов!
try:
    cart = _old_views.cart if _old_views else view_cart  # Старая функция с POST обработкой
except (NameError, AttributeError):
    cart = view_cart  # Fallback на новую если старая недоступна

# Cart aliases
cart_remove = remove_from_cart  # для urls.py: views.cart_remove
clean_cart = clear_cart  # для urls.py: views.clean_cart

# Profile aliases (если нужны)
profile_setup_db = profile_setup  # для urls.py: views.profile_setup_db

# Checkout aliases  
# КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем старую order_create() из views.py
try:
    order_create = _old_views.order_create if _old_views else create_order  # Старая функция с правильной логикой
except (NameError, AttributeError):
    order_create = create_order  # Fallback на новую

# Admin aliases (если нужны)
try:
    admin_panel = _old_views.admin_panel if _old_views else None
    if not admin_panel:
        raise AttributeError
except (NameError, AttributeError):
    @login_required
    def admin_panel(request):
        return redirect('admin_dashboard')

# Admin fallbacks for legacy logic (until fully modularized)
def _legacy_or_stub(name):
    try:
        legacy = getattr(_old_views, name) if _old_views else None
    except (NameError, AttributeError):
        legacy = None

    if legacy:
        return legacy

    @login_required
    def _stub(request, *args, **kwargs):
        return redirect('admin_panel')

    return _stub


admin_update_user = _legacy_or_stub('admin_update_user')
admin_order_update = _legacy_or_stub('admin_order_update')
admin_update_payment_status = _legacy_or_stub('admin_update_payment_status')
admin_approve_payment = _legacy_or_stub('admin_approve_payment')
admin_order_delete = _legacy_or_stub('admin_order_delete')
confirm_payment = _legacy_or_stub('confirm_payment')
admin_category_new = _legacy_or_stub('admin_category_new')
admin_category_edit = _legacy_or_stub('admin_category_edit')
admin_category_delete = _legacy_or_stub('admin_category_delete')
admin_product_new = _legacy_or_stub('admin_product_new')
admin_product_builder = _legacy_or_stub('admin_product_builder')
admin_product_edit = _legacy_or_stub('admin_product_edit')
admin_product_edit_simple = _legacy_or_stub('admin_product_edit_simple')
admin_product_edit_unified = _legacy_or_stub('admin_product_edit_unified')
admin_product_delete = _legacy_or_stub('admin_product_delete')
admin_product_colors = _legacy_or_stub('admin_product_colors')
admin_product_color_delete = _legacy_or_stub('admin_product_color_delete')
admin_product_image_delete = _legacy_or_stub('admin_product_image_delete')
admin_offline_stores = _legacy_or_stub('admin_offline_stores')
admin_offline_store_create = _legacy_or_stub('admin_offline_store_create')
admin_offline_store_edit = _legacy_or_stub('admin_offline_store_edit')
admin_offline_store_toggle = _legacy_or_stub('admin_offline_store_toggle')
admin_offline_store_delete = _legacy_or_stub('admin_offline_store_delete')
admin_store_management = _legacy_or_stub('admin_store_management')
admin_store_add_product_to_order = _legacy_or_stub('admin_store_add_product_to_order')
admin_store_get_order_items = _legacy_or_stub('admin_store_get_order_items')
admin_store_get_product_colors = _legacy_or_stub('admin_store_get_product_colors')
admin_store_remove_product_from_order = _legacy_or_stub('admin_store_remove_product_from_order')
admin_store_add_products_to_store = _legacy_or_stub('admin_store_add_products_to_store')
admin_store_generate_invoice = _legacy_or_stub('admin_store_generate_invoice')
admin_store_update_product = _legacy_or_stub('admin_store_update_product')
admin_store_mark_product_sold = _legacy_or_stub('admin_store_mark_product_sold')
admin_store_remove_product = _legacy_or_stub('admin_store_remove_product')
admin_print_proposal_update_status = _legacy_or_stub('admin_print_proposal_update_status')
admin_print_proposal_award_points = _legacy_or_stub('admin_print_proposal_award_points')
admin_print_proposal_award_promocode = _legacy_or_stub('admin_print_proposal_award_promocode')

# Auth aliases (если нужны)
register_view_new = register_view  # для urls.py: views.register_view_new


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
    'product_detail', 'get_product_images', 'get_product_variants', 'quick_view',
    
    # Cart
    'view_cart', 'add_to_cart', 'update_cart', 'remove_from_cart', 'clear_cart',
    'get_cart_count', 'apply_promo_code', 'remove_promo_code', 'cart_summary', 'cart_mini',
    
    # Static Pages
    'robots_txt', 'static_sitemap', 'google_merchant_feed', 'uaprom_products_feed',
    'static_verification_file', 'about', 'contacts', 'delivery', 'returns',
    'privacy_policy', 'terms_of_service',
    
    # Profile
    'profile', 'edit_profile', 'profile_setup', 'order_history', 'order_detail',
    'favorites', 'favorites_list', 'toggle_favorite', 'add_to_favorites', 
    'remove_from_favorites', 'check_favorite_status', 'favorites_count', 
    'points_history', 'settings',
    'user_points', 'my_promocodes', 'buy_with_points', 'purchase_with_points',
    
    # Promo Codes
    'PromoCodeForm', 'PromoCodeGroupForm', 'get_promo_admin_context',
    'admin_promocodes', 'admin_promocode_create', 'admin_promocode_edit',
    'admin_promocode_toggle', 'admin_promocode_delete',
    'admin_promo_groups', 'admin_promo_group_create', 'admin_promo_group_edit',
    'admin_promo_group_delete', 'admin_promo_stats',
    'admin_promocode_get_form', 'admin_promocode_edit_ajax',
    'admin_promo_group_get_form', 'admin_promo_group_edit_ajax',
    'admin_promocode_change_group', 'admin_promo_export',
    
    # API
    'get_product_json', 'get_categories_json', 'track_event', 'search_suggestions',
    'product_availability', 'get_related_products', 'newsletter_subscribe', 'contact_form',
    
    # Checkout
    'checkout', 'create_order', 'payment_method', 'monobank_webhook', 'payment_callback',
    'order_success', 'order_failed', 'calculate_shipping',
    
    # Admin
    'admin_panel', 'admin_dashboard', 'manage_products', 'add_product', 'add_category', 'add_print',
    'manage_print_proposals', 'manage_promo_codes', 'generate_seo_content',
    'generate_alt_texts', 'manage_orders', 'sales_statistics', 'inventory_management',
    
    # Aliases (для обратной совместимости)
    'cart', 'cart_remove', 'clean_cart', 'profile_setup_db', 'order_create', 'register_view_new',
]


def __getattr__(name):
    try:
        if _old_views:
            return getattr(_old_views, name)
        raise AttributeError(f"module 'storefront.views' has no attribute '{name}'")
    except (NameError, AttributeError):
        raise AttributeError(f"module 'storefront.views' has no attribute '{name}'")
