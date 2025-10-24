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
    register_view_new,
    dev_grant_admin,
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
    cart_summary,
    cart_mini,
    apply_promo_code,
    remove_promo_code,
    clean_cart,
    cart_remove,
    cart,
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
    cooperation,
    custom_sitemap,
    delivery_view,
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
    # Additional Profile Views
    profile_setup_db,
    favorites_list_view,
)

# Backward compatibility alias
favorites_list = favorites_list_view

# Debug views
from .debug import (
    debug_media,
    debug_media_page,
    debug_product_images,
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
    api_colors,
)

# Оформление заказа
from .checkout import (
    checkout,
    create_order,
    payment_method,
    payment_callback,
    order_success,
    order_failed,
    calculate_shipping,
    process_guest_order,
    order_create,
    my_orders,
    # Payment Management
    update_payment_method,
    confirm_payment,
)

# Monobank платежи
from .monobank import (
    monobank_create_invoice,
    monobank_create_checkout,
    monobank_return,
    monobank_webhook,
    MonobankAPIError,
)

# Wholesale (оптовые продажи)
from .wholesale import (
    wholesale_page,
    wholesale_order_form,
    wholesale_prices_xlsx,
    pricelist_page,
    pricelist_redirect,
    test_pricelist,
    generate_wholesale_invoice,
    download_invoice_file,
    delete_wholesale_invoice,
    get_user_invoices,
    update_invoice_status,
    reset_all_invoices_status,
    toggle_invoice_approval,
    check_invoice_approval_status,
    toggle_invoice_payment_status,
    check_payment_status,
    create_wholesale_payment,
    wholesale_payment_webhook,
    debug_invoices,
)

# Dropshipping
from .dropship import (
    admin_update_dropship_status,
    admin_get_dropship_order,
    admin_update_dropship_order,
    admin_delete_dropship_order,
)

# Offline Stores (оффлайн магазини)
from .stores import (
    # CRUD для магазинів
    admin_offline_stores,
    admin_offline_store_create,
    admin_offline_store_edit,
    admin_offline_store_toggle,
    admin_offline_store_delete,
    OfflineStoreForm,
    # Управління магазином
    admin_store_management,
    admin_store_get_order_items,
    admin_store_get_product_colors,
    admin_store_add_product_to_order,
    admin_store_remove_product_from_order,
    admin_store_add_products_to_store,
    admin_store_generate_invoice,
    admin_store_update_product,
    admin_store_remove_product,
    admin_store_mark_product_sold,
)

# Админка
from .admin import (
    # Базові функції панелі
    admin_dashboard,
    admin_panel,
    # Управління товарами
    manage_products,
    add_product,
    admin_product_new,
    admin_product_edit,
    admin_product_edit_unified,
    admin_product_edit_simple,
    admin_product_colors,
    admin_product_color_delete,
    admin_product_image_delete,
    admin_product_delete,
    # Управління категоріями
    add_category,
    admin_category_new,
    admin_category_edit,
    admin_category_delete,
    # Управління промокодами
    manage_promo_codes,
    PromoCodeForm,
    admin_promocodes,
    admin_promocode_create,
    admin_promocode_edit,
    admin_promocode_toggle,
    admin_promocode_delete,
    # Управління принтами
    add_print,
    manage_print_proposals,
    admin_print_proposal_update_status,
    admin_print_proposal_award_points,
    admin_print_proposal_award_promocode,
    # Управління замовленнями
    manage_orders,
    admin_order_update,
    admin_update_payment_status,
    admin_approve_payment,
    admin_order_delete,
    # Управління накладними
    admin_update_invoice_status,
    # Управління користувачами
    admin_update_user,
    # Інші функції
    generate_seo_content,
    generate_alt_texts,
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
        # debug.py
        'debug_media', 'debug_media_page', 'debug_product_images',
        # auth.py
        'register_view_new', 'dev_grant_admin',
        # profile.py
        'favorites_list', 'favorites_list_view', 'profile_setup_db',
        # auth.py
        'LoginForm', 'RegisterForm', 'ProfileSetupForm',
        'login_view', 'register_view', 'logout_view',
        # catalog.py
        'home', 'load_more_products', 'catalog', 'search',
        # product.py
        'product_detail', 'get_product_images', 'get_product_variants', 'quick_view',
        # cart.py
        'view_cart', 'add_to_cart', 'update_cart', 'remove_from_cart', 'clear_cart',
        'get_cart_count', 'cart_summary', 'cart_mini', 'apply_promo_code', 'remove_promo_code',
        'clean_cart', 'cart_remove', 'cart',
        # static_pages.py
        'robots_txt', 'static_sitemap', 'google_merchant_feed', 'uaprom_products_feed',
        'static_verification_file', 'about', 'contacts', 'delivery', 'returns',
        'privacy_policy', 'terms_of_service', 'cooperation', 'custom_sitemap', 'delivery_view',
        # profile.py
        'profile', 'edit_profile', 'profile_setup', 'order_history', 'order_detail',
        'favorites', 'favorites_list', 'toggle_favorite', 'add_to_favorites', 
        'remove_from_favorites', 'check_favorite_status', 'favorites_count', 
        'points_history', 'settings',
        'user_points', 'my_promocodes', 'buy_with_points', 'purchase_with_points',
        'profile_setup_db', 'favorites_list_view', 'favorites_list',
        # api.py
        'get_product_json', 'get_categories_json', 'track_event', 'search_suggestions',
        'product_availability', 'get_related_products', 'newsletter_subscribe', 'contact_form', 'api_colors',
        # checkout.py
        'checkout', 'create_order', 'payment_method', 'payment_callback',
        'order_success', 'order_failed', 'calculate_shipping',
        'process_guest_order', 'order_create', 'my_orders', 'update_payment_method', 'confirm_payment',
        # monobank.py
        'monobank_create_invoice', 'monobank_create_checkout', 'monobank_return', 
        'monobank_webhook', 'MonobankAPIError',
        # wholesale.py
        'wholesale_page', 'wholesale_order_form', 'wholesale_prices_xlsx',
        'pricelist_page', 'pricelist_redirect', 'test_pricelist',
        'generate_wholesale_invoice', 'download_invoice_file', 'delete_wholesale_invoice',
        'get_user_invoices', 'update_invoice_status', 'reset_all_invoices_status',
        'toggle_invoice_approval', 'check_invoice_approval_status',
        'toggle_invoice_payment_status', 'check_payment_status',
        'create_wholesale_payment', 'wholesale_payment_webhook', 'debug_invoices',
        # dropship.py
        'admin_update_dropship_status', 'admin_get_dropship_order',
        'admin_update_dropship_order', 'admin_delete_dropship_order',
        # stores.py
        'admin_offline_stores', 'admin_offline_store_create', 'admin_offline_store_edit',
        'admin_offline_store_toggle', 'admin_offline_store_delete', 'OfflineStoreForm',
        'admin_store_management', 'admin_store_get_order_items', 'admin_store_get_product_colors',
        'admin_store_add_product_to_order', 'admin_store_remove_product_from_order',
        'admin_store_add_products_to_store', 'admin_store_generate_invoice',
        'admin_store_update_product', 'admin_store_remove_product', 'admin_store_mark_product_sold',
        # admin.py
        'admin_dashboard', 'admin_panel', 'manage_products', 'add_product', 'add_category', 'add_print',
        'admin_product_new', 'admin_product_edit', 'admin_product_edit_unified', 'admin_product_edit_simple',
        'admin_product_colors', 'admin_product_color_delete', 'admin_product_image_delete', 'admin_product_delete',
        'admin_category_new', 'admin_category_edit', 'admin_category_delete',
        'manage_print_proposals', 'manage_promo_codes', 'PromoCodeForm', 'admin_promocodes',
        'admin_promocode_create', 'admin_promocode_edit', 'admin_promocode_toggle', 'admin_promocode_delete',
        'admin_print_proposal_update_status', 'admin_print_proposal_award_points', 'admin_print_proposal_award_promocode',
        'manage_orders', 'admin_order_update', 'admin_update_payment_status', 'admin_approve_payment', 'admin_order_delete',
        'admin_update_invoice_status', 'admin_update_user',
        'generate_seo_content', 'generate_alt_texts', 'sales_statistics', 'inventory_management',
        # Aliases (чтобы не конфликтовали)
        'cart', 'cart_remove', 'clean_cart', 'profile_setup_db', 'order_create', 'register_view_new',
        # Технические атрибуты Python
        '__name__', '__doc__', '__package__', '__loader__', '__spec__',
        '__file__', '__cached__', '__builtins__',
    }
    
    # Импортируем все остальное из старого views
    for name in dir(_old_views):
        if not name.startswith('_') and name not in _exclude:
            globals()[name] = getattr(_old_views, name)
            
except Exception as e:
    # Если не удалось импортировать старый views.py, это нормально
    # (например, если его уже удалили после полной миграции)
    import warnings
    warnings.warn(f"Could not import old views.py: {e}")


# ==================== АЛИАСЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ ====================
# Эти алиасы обеспечивают совместимость с старым views.py и storefront/urls.py

# Cart aliases
cart = view_cart  # для urls.py: views.cart
cart_remove = remove_from_cart  # для urls.py: views.cart_remove
clean_cart = clear_cart  # для urls.py: views.clean_cart

# Profile aliases (если нужны)
profile_setup_db = profile_setup  # для urls.py: views.profile_setup_db

# Checkout aliases  
order_create = create_order  # для urls.py: views.order_create

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
    'get_cart_count', 'cart_summary', 'cart_mini', 'apply_promo_code', 'remove_promo_code',
    'clean_cart', 'cart_remove', 'cart',
    
    # Static Pages
    'robots_txt', 'static_sitemap', 'google_merchant_feed', 'uaprom_products_feed',
    'static_verification_file', 'about', 'contacts', 'delivery', 'returns',
    'privacy_policy', 'terms_of_service', 'cooperation', 'custom_sitemap', 'delivery_view',
    
    # Profile
    'profile', 'edit_profile', 'profile_setup', 'order_history', 'order_detail',
    'favorites', 'favorites_list', 'toggle_favorite', 'add_to_favorites', 
    'remove_from_favorites', 'check_favorite_status', 'favorites_count', 
    'points_history', 'settings',
    'user_points', 'my_promocodes', 'buy_with_points', 'purchase_with_points',
    'profile_setup_db', 'favorites_list_view',
    
    # API
    'get_product_json', 'get_categories_json', 'track_event', 'search_suggestions',
    'product_availability', 'get_related_products', 'newsletter_subscribe', 'contact_form', 'api_colors',
    
    # Checkout
    'checkout', 'create_order', 'payment_method', 'payment_callback',
    'order_success', 'order_failed', 'calculate_shipping',
    'process_guest_order', 'order_create', 'my_orders', 'update_payment_method', 'confirm_payment',
    
    # Monobank
    'monobank_create_invoice', 'monobank_create_checkout', 'monobank_return',
    'monobank_webhook', 'MonobankAPIError',
    
    # Wholesale
    'wholesale_page', 'wholesale_order_form', 'wholesale_prices_xlsx',
    'pricelist_page', 'pricelist_redirect', 'test_pricelist',
    'generate_wholesale_invoice', 'download_invoice_file', 'delete_wholesale_invoice',
    'get_user_invoices', 'update_invoice_status', 'reset_all_invoices_status',
    'toggle_invoice_approval', 'check_invoice_approval_status',
    'toggle_invoice_payment_status', 'check_payment_status',
    'create_wholesale_payment', 'wholesale_payment_webhook', 'debug_invoices',
    
    # Dropshipping
    'admin_update_dropship_status', 'admin_get_dropship_order',
    'admin_update_dropship_order', 'admin_delete_dropship_order',
    
    # Offline Stores
    'admin_offline_stores', 'admin_offline_store_create', 'admin_offline_store_edit',
    'admin_offline_store_toggle', 'admin_offline_store_delete', 'OfflineStoreForm',
    'admin_store_management', 'admin_store_get_order_items', 'admin_store_get_product_colors',
    'admin_store_add_product_to_order', 'admin_store_remove_product_from_order',
    'admin_store_add_products_to_store', 'admin_store_generate_invoice',
    'admin_store_update_product', 'admin_store_remove_product', 'admin_store_mark_product_sold',
    
    # Admin
    'admin_dashboard', 'admin_panel', 'manage_products', 'add_product', 'add_category', 'add_print',
    'admin_product_new', 'admin_product_edit', 'admin_product_edit_unified', 'admin_product_edit_simple',
    'admin_product_colors', 'admin_product_color_delete', 'admin_product_image_delete', 'admin_product_delete',
    'admin_category_new', 'admin_category_edit', 'admin_category_delete',
    'manage_print_proposals', 'manage_promo_codes', 'PromoCodeForm', 'admin_promocodes',
    'admin_promocode_create', 'admin_promocode_edit', 'admin_promocode_toggle', 'admin_promocode_delete',
    'admin_print_proposal_update_status', 'admin_print_proposal_award_points', 'admin_print_proposal_award_promocode',
    'manage_orders', 'admin_order_update', 'admin_update_payment_status', 'admin_approve_payment', 'admin_order_delete',
    'admin_update_invoice_status', 'admin_update_user',
    'generate_seo_content', 'generate_alt_texts', 'sales_statistics', 'inventory_management',
    
    # Debug
    'debug_media', 'debug_media_page', 'debug_product_images',
    
    # Aliases (для обратной совместимости)
    'cart', 'cart_remove', 'clean_cart', 'profile_setup_db', 'order_create', 'register_view_new',
    'dev_grant_admin', 'favorites_list',
]

