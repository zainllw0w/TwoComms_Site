"""
Оптимизированные URL-паттерны для storefront приложения
"""

from django.urls import path
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from . import views

# Кэшируемые представления (только для чтения)
cached_views = [
    'home',
    'catalog', 
    'product_detail',
    'about',
    'contacts',
    'cooperation',
]

# Оптимизированные URL-паттерны
urlpatterns = [
    # Главная страница с кэшированием
    path('', cache_page(300)(views.home), name='home'),
    
    # AJAX загрузка товаров
    path('load-more-products/', views.load_more_products, name='load_more_products'),
    
    # Каталог с кэшированием
    path('catalog/', cache_page(600)(views.catalog), name='catalog'),
    path('catalog/<slug:cat_slug>/', cache_page(600)(views.catalog), name='catalog_by_cat'),
    
    # Детали товара с кэшированием
    path('product/<slug:slug>/', cache_page(300)(views.product_detail), name='product'),
    
    # Поиск
    path('search/', views.search, name='search'),
    
    # Статические страницы с кэшированием
    path('about/', cache_page(3600)(views.about), name='about'),
    path('contacts/', cache_page(3600)(views.contacts), name='contacts'),
    path('cooperation/', cache_page(3600)(views.cooperation), name='cooperation'),
    
    # Аутентификация
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view_new, name='register'),
    path('profile/setup/', views.profile_setup_db, name='profile_setup'),
    
    # Корзина
    path('cart/', views.cart, name='cart'),
    path('cart/add/', views.add_to_cart, name='cart_add'),
    path('cart/remove/', views.cart_remove, name='cart_remove'),
    path('cart/summary/', views.cart_summary, name='cart_summary'),
    path('cart/mini/', views.cart_mini, name='cart_mini'),
    path('cart/clean/', views.clean_cart, name='clean_cart'),
    path('checkout/', views.checkout, name='checkout'),
    
    # Промокоды в корзине
    path('cart/apply-promo/', views.apply_promo_code, name='apply_promo_code'),
    path('cart/remove-promo/', views.remove_promo_code, name='remove_promo_code'),
    
    # Заказы
    path('orders/create/', views.order_create, name='order_create'),
    path('orders/success/<int:order_id>/', views.order_success, name='order_success'),
    path('my/orders/', views.my_orders, name='my_orders'),
    path('orders/update-payment-method/', views.update_payment_method, name='update_payment_method'),
    path('orders/confirm-payment/', views.confirm_payment, name='confirm_payment'),
    
    # Пользовательские функции
    path('user/points/', views.user_points, name='user_points'),
    path('my-promocodes/', views.my_promocodes, name='my_promocodes'),
    path('buy-with-points/', views.buy_with_points, name='buy_with_points'),
    path('purchase-with-points/', views.purchase_with_points, name='purchase_with_points'),
    
    # Избранное
    path('favorites/', views.favorites_list, name='favorites'),
    path('favorites/toggle/<int:product_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('favorites/check/<int:product_id>/', views.check_favorite_status, name='check_favorite_status'),
    
    # Админ-панель
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('admin-panel/update-user/', views.admin_update_user, name='admin_update_user'),
    path('admin-panel/order/update/', views.admin_order_update, name='admin_order_update'),
    path('admin-panel/order/update-status/', views.admin_order_update, name='admin_update_order_status'),
    path('admin-panel/order/update-payment-status/', views.admin_update_payment_status, name='admin_update_payment_status'),
    path('admin-panel/order/approve-payment/', views.admin_approve_payment, name='admin_approve_payment'),
    
    # CRUD товаров
    path('add-product/', views.add_product, name='add_product'),
    path('admin-panel/product/add/', views.add_product, name='admin_add_product'),
    path('admin-panel/product/new/', views.admin_product_new, name='admin_product_new'),
    path('admin-panel/product/<int:pk>/edit/', views.admin_product_edit, name='admin_product_edit'),
    path('admin-panel/product/<int:pk>/edit-simple/', views.admin_product_edit_simple, name='admin_product_edit_simple'),
    path('admin-panel/product/<int:pk>/edit-unified/', views.admin_product_edit_unified, name='admin_product_edit_unified'),
    path('admin-panel/product/<int:pk>/delete/', views.admin_product_delete, name='admin_product_delete'),
    path('admin-panel/product/<int:pk>/colors/', views.admin_product_colors, name='admin_product_colors'),
    path('admin-panel/product/<int:product_pk>/color/<int:color_pk>/delete/', views.admin_product_color_delete, name='admin_product_color_delete'),
    path('admin-panel/product/<int:product_pk>/image/<int:image_pk>/delete/', views.admin_product_image_delete, name='admin_product_image_delete'),
    
    # CRUD категорий
    path('add-category/', views.add_category, name='add_category'),
    path('admin-panel/category/new/', views.admin_category_new, name='admin_category_new'),
    path('admin-panel/category/<int:pk>/edit/', views.admin_category_edit, name='admin_category_edit'),
    path('admin-panel/category/<int:pk>/delete/', views.admin_category_delete, name='admin_category_delete'),
    
    # Промокоды
    path('admin-panel/promocodes/', views.admin_promocodes, name='admin_promocodes'),
    path('admin-panel/promocode/create/', views.admin_promocode_create, name='admin_promocode_create'),
    path('admin-panel/promocode/<int:pk>/edit/', views.admin_promocode_edit, name='admin_promocode_edit'),
    path('admin-panel/promocode/<int:pk>/toggle/', views.admin_promocode_toggle, name='admin_promocode_toggle'),
    path('admin-panel/promocode/<int:pk>/delete/', views.admin_promocode_delete, name='admin_promocode_delete'),
    
    # Офлайн магазины
    path('admin-panel/offline-stores/', views.admin_offline_stores, name='admin_offline_stores'),
    path('admin-panel/offline-store/create/', views.admin_offline_store_create, name='admin_offline_store_create'),
    path('admin-panel/offline-store/<int:pk>/edit/', views.admin_offline_store_edit, name='admin_offline_store_edit'),
    path('admin-panel/offline-store/<int:pk>/toggle/', views.admin_offline_store_toggle, name='admin_offline_store_toggle'),
    path('admin-panel/offline-store/<int:pk>/delete/', views.admin_offline_store_delete, name='admin_offline_store_delete'),
    
    # Предложения принтов
    path('add-print/', views.add_print, name='add_print'),
    path('admin-panel/print-proposal/update-status/', views.admin_print_proposal_update_status, name='admin_print_proposal_update_status'),
    path('admin-panel/print-proposal/award-points/', views.admin_print_proposal_award_points, name='admin_print_proposal_award_points'),
    path('admin-panel/print-proposal/award-promocode/', views.admin_print_proposal_award_promocode, name='admin_print_proposal_award_promocode'),
    
    # API endpoints
    path('api/colors/', views.api_colors, name='api_colors'),
    
    # Отладочные страницы
    path('debug/media/', views.debug_media, name='debug_media'),
    path('debug/media-page/', views.debug_media_page, name='debug_media_page'),
    path('debug/product-images/', views.debug_product_images, name='debug_product_images'),
    
    # Dev helper
    path('dev/grant-admin/', views.dev_grant_admin, name='dev_grant_admin'),
]

# Оптимизированные URL-паттерны с дополнительными заголовками
optimized_urlpatterns = [
    # Главная страница с варьированием по заголовкам
    path('', vary_on_headers('Accept-Language')(cache_page(300)(views.home)), name='home_optimized'),
    
    # Каталог с варьированием по заголовкам
    path('catalog/', vary_on_headers('Accept-Language')(cache_page(600)(views.catalog)), name='catalog_optimized'),
    path('catalog/<slug:cat_slug>/', vary_on_headers('Accept-Language')(cache_page(600)(views.catalog)), name='catalog_by_cat_optimized'),
    
    # Детали товара с варьированием по заголовкам
    path('product/<slug:slug>/', vary_on_headers('Accept-Language')(cache_page(300)(views.product_detail)), name='product_optimized'),
]

# Функция для получения оптимизированных URL-паттернов
def get_optimized_urlpatterns():
    """
    Возвращает оптимизированные URL-паттерны
    """
    return optimized_urlpatterns

# Функция для получения кэшированных URL-паттернов
def get_cached_urlpatterns():
    """
    Возвращает URL-паттерны с кэшированием
    """
    return urlpatterns

# Функция для инвалидации кэша URL
def invalidate_url_cache():
    """
    Инвалидация кэша для URL-паттернов
    """
    from django.core.cache import cache
    cache_keys = [
        'home_data',
        'catalog_data',
        'categories_menu',
        'featured_products',
    ]
    cache.delete_many(cache_keys)
