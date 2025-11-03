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

from functools import wraps

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
    cart_items_api,
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
    test_analytics_events,
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
    order_success_preview,
    order_failed,
    calculate_shipping,
)

# Monobank оплата
from .monobank import (
    monobank_create_invoice,
    _monobank_finalize_invoice,
)

# Админка
from .admin import (
    admin_panel,
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

_legacy_loaded = False
_legacy_error = None


def _load_legacy_views(force: bool = False):
    """Загружает старый monolithic views.py для обратной совместимости."""
    global _legacy_loaded, _legacy_error, _old_views

    if _legacy_loaded and not force:
        return

    try:
        views_py_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'views.py')
        spec = importlib.util.spec_from_file_location("storefront.views_old", views_py_path)
        _old_views = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_old_views)

        _exclude = {
            'cache_page_for_anon', 'unique_slugify', 'get_cart_from_session',
            'save_cart_to_session', 'calculate_cart_total', 'get_favorites_from_session',
            'save_favorites_to_session', 'HOME_PRODUCTS_PER_PAGE',
            'LoginForm', 'RegisterForm', 'ProfileSetupForm',
            'login_view', 'register_view', 'logout_view',
            'home', 'load_more_products', 'catalog', 'search',
            'product_detail', 'get_product_images', 'get_product_variants', 'quick_view',
            'view_cart', 'add_to_cart', 'update_cart', 'remove_from_cart', 'clear_cart',
            'get_cart_count', 'apply_promo_code', 'remove_promo_code', 'cart_summary', 'cart_mini', 'cart_items_api',
            'robots_txt', 'static_sitemap', 'google_merchant_feed', 'uaprom_products_feed',
            'static_verification_file', 'about', 'contacts', 'delivery', 'returns',
            'privacy_policy', 'terms_of_service',
            'profile', 'edit_profile', 'profile_setup', 'order_history', 'order_detail',
            'favorites', 'favorites_list', 'toggle_favorite', 'add_to_favorites',
            'remove_from_favorites', 'check_favorite_status', 'favorites_count',
            'points_history', 'settings', 'user_points', 'my_promocodes',
            'buy_with_points', 'purchase_with_points',
            'PromoCodeForm', 'PromoCodeGroupForm', 'get_promo_admin_context',
            'admin_promocodes', 'admin_promocode_create', 'admin_promocode_edit',
            'admin_promocode_toggle', 'admin_promocode_delete',
            'admin_promo_groups', 'admin_promo_group_create', 'admin_promo_group_edit',
            'admin_promo_group_delete', 'admin_promo_stats',
            'admin_promocode_get_form', 'admin_promocode_edit_ajax',
            'admin_promo_group_get_form', 'admin_promo_group_edit_ajax',
            'admin_promocode_change_group', 'admin_promo_export',
            'get_product_json', 'get_categories_json', 'track_event', 'search_suggestions',
            'product_availability', 'get_related_products', 'newsletter_subscribe', 'contact_form',
            'checkout', 'create_order', 'payment_method', 'monobank_webhook', 'payment_callback',
            'order_success', 'order_failed', 'calculate_shipping',
            'admin_panel', 'admin_dashboard', 'manage_products', 'add_product', 'add_category', 'add_print',
            'manage_print_proposals', 'manage_promo_codes', 'generate_seo_content',
            'generate_alt_texts', 'manage_orders', 'sales_statistics', 'inventory_management',
            'cart', 'cart_remove', 'clean_cart', 'profile_setup_db', 'order_create', 'register_view_new',
            '__name__', '__doc__', '__package__', '__loader__', '__spec__',
            '__file__', '__cached__', '__builtins__',
        }

        for name in dir(_old_views):
            if not name.startswith('_') and name not in _exclude:
                globals()[name] = getattr(_old_views, name)

        _legacy_loaded = True
        _legacy_error = None
    except Exception as exc:
        _legacy_error = exc
        if force:
            return
        try:
            from django.core.exceptions import AppRegistryNotReady
        except Exception:  # pragma: no cover - fail silently without Django
            AppRegistryNotReady = None

        if AppRegistryNotReady and isinstance(exc, AppRegistryNotReady):
            return

        import warnings
        warnings.warn(f"Could not import old views.py: {exc}")


_load_legacy_views()


def __getattr__(name):
    """Ленивая прокси для функций из legacy views.py."""

    if name in globals():
        return globals()[name]

    try:
        from django.apps import apps
    except Exception:
        apps = None

    if apps is not None and not apps.ready:

        def _deferred(*args, **kwargs):
            _load_legacy_views(force=True)
            handler = globals().get(name)
            if handler is None:
                raise AttributeError(name)
            return handler(*args, **kwargs)

        _deferred.__name__ = name
        return _deferred

    _load_legacy_views(force=True)
    if name in globals():
        return globals()[name]

    raise AttributeError(name)


# ==================== АЛИАСЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ ====================
# Эти алиасы обеспечивают совместимость с старым views.py и storefront/urls.py

# Используем новую view_cart, она теперь обрабатывает POST (update_profile / guest / order_create)
cart = view_cart

# Cart aliases
cart_remove = remove_from_cart  # для urls.py: views.cart_remove
clean_cart = clear_cart  # для urls.py: views.clean_cart

# Profile aliases (если нужны)
profile_setup_db = profile_setup  # для urls.py: views.profile_setup_db

# Checkout aliases  
# КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем старую order_create() из views.py
try:
    _legacy_module = globals().get('_old_views')
    if _legacy_module is not None:
        order_create = _legacy_module.order_create  # Старая функция с правильной логикой
    else:
        raise AttributeError
except (AttributeError, NameError):
    order_create = create_order  # Fallback на новую

# Admin aliases (если нужны)

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
    'privacy_policy', 'terms_of_service', 'test_analytics_events',
    
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
