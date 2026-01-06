from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.http import Http404
from . import views
# Import auth views from the modular auth.py module
from .views import auth as auth_views


def _legacy_view(name):
    """Lazy loader for legacy views living in the monolithic views.py."""

    def _wrapped(request, *args, **kwargs):
        from . import views as storefront_views

        if hasattr(storefront_views, '_load_legacy_views'):
            try:
                storefront_views._load_legacy_views(force=True)
            except Exception:
                # Even if legacy load fails, continue to 404 below
                pass

        handler = getattr(storefront_views, name, None)
        if handler is None:
            raise Http404(f"Legacy view '{name}' not found")
        return handler(request, *args, **kwargs)

    _wrapped.__name__ = name
    return _wrapped
def admin_panel_view(request, *args, **kwargs):
    from .views.admin import admin_panel as _admin_panel

    return _admin_panel(request, *args, **kwargs)

urlpatterns=[
    path('', views.home, name='home'),
    path('load-more-products/', views.load_more_products, name='load_more_products'),
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/<slug:cat_slug>/', views.catalog, name='catalog_by_cat'),
    path('product/<slug:slug>/', views.product_detail, name='product'),
    path('add-product/', views.add_product, name='add_product'),
    path('admin-panel/product/add/', views.add_product, name='admin_add_product'),
    path('add-category/', views.add_category, name='add_category'),
    path('cart/', views.cart, name='cart'),
    path('cart/add/', views.add_to_cart, name='cart_add'),
    path('cart/remove/', views.cart_remove, name='cart_remove'),

    path('cart/summary/', views.cart_summary, name='cart_summary'),
    path('cart/mini/', views.cart_mini, name='cart_mini'),
    path('cart/items/', views.cart_items_api, name='cart_items_api'),
    path('cart/clean/', views.clean_cart, name='clean_cart'),
    # path('checkout/', views.checkout, name='checkout'), # REMOVED: Dead code
    # auth - using modular auth views with proper password validation
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('register/', auth_views.register_view, name='register'),
    path('profile/setup/', views.profile_setup_db, name='profile_setup'),
    # admin panel
    path('admin-panel/', admin_panel_view, name='admin_panel'),
    path('admin-panel/update-user/', _legacy_view('admin_update_user'), name='admin_update_user'),
    path('admin-panel/order/update/', _legacy_view('admin_order_update'), name='admin_order_update'),
    path('admin-panel/order/update-status/', _legacy_view('admin_order_update'), name='admin_update_order_status'),
    path('admin-panel/order/update-payment-status/', _legacy_view('admin_update_payment_status'), name='admin_update_payment_status'),
    path('admin-panel/order/approve-payment/', _legacy_view('admin_approve_payment'), name='admin_approve_payment'),
    path('admin-panel/order/<int:pk>/delete/', _legacy_view('admin_order_delete'), name='admin_order_delete'),
    # orders
    path('orders/create/', views.order_create, name='order_create'),
    path('orders/success/<int:order_id>/', views.order_success, name='order_success'),
    path('orders/success-preview/', views.order_success_preview, name='order_success_preview'),  # Тестовый preview
    path('my/orders/', views.my_orders, name='my_orders'),
    path('orders/update-payment-method/', views.update_payment_method, name='update_payment_method'),
    path('orders/confirm-payment/', views.confirm_payment, name='confirm_payment'),

    path('user/points/', views.user_points, name='user_points'),
    path('my-promocodes/', views.my_promocodes, name='my_promocodes'),
    path('buy-with-points/', views.buy_with_points, name='buy_with_points'),
    path('purchase-with-points/', views.purchase_with_points, name='purchase_with_points'),
    # catalogs CRUD
    path('admin-panel/category/new/', _legacy_view('admin_category_new'), name='admin_category_new'),
    path('admin-panel/category/<int:pk>/edit/', _legacy_view('admin_category_edit'), name='admin_category_edit'),
    path('admin-panel/category/<int:pk>/delete/', _legacy_view('admin_category_delete'), name='admin_category_delete'),
    path('admin-panel/product/new/', _legacy_view('admin_product_new'), name='admin_product_new'),
    path('admin-panel/product/builder/', _legacy_view('admin_product_builder'), name='admin_product_builder'),
    path('admin-panel/product/<int:product_id>/builder/', _legacy_view('admin_product_builder'), name='admin_product_builder_edit'),
    path('admin-panel/product/<int:pk>/edit/', _legacy_view('admin_product_edit'), name='admin_product_edit'),
    path('admin-panel/product/<int:pk>/edit-simple/', _legacy_view('admin_product_edit_simple'), name='admin_product_edit_simple'),
    path('admin-panel/product/<int:pk>/edit-unified/', _legacy_view('admin_product_edit_unified'), name='admin_product_edit_unified'),
    path('admin-panel/product/<int:pk>/delete/', _legacy_view('admin_product_delete'), name='admin_product_delete'),
    path('admin-panel/product/<int:pk>/colors/', _legacy_view('admin_product_colors'), name='admin_product_colors'),
    path('admin-panel/product/<int:product_pk>/color/<int:color_pk>/delete/', _legacy_view('admin_product_color_delete'), name='admin_product_color_delete'),
    path('admin-panel/product/<int:product_pk>/image/<int:image_pk>/delete/', _legacy_view('admin_product_image_delete'), name='admin_product_image_delete'),
    path('admin-panel/products/reorder/', views.admin_reorder_products, name='admin_reorder_products'),
    path('admin-panel/products/update-status/', views.admin_update_product_status, name='admin_update_product_status'),
    # promocodes
    path('admin-panel/promocodes/', views.admin_promocodes, name='admin_promocodes'),
    path('admin-panel/promocode/create/', views.admin_promocode_create, name='admin_promocode_create'),
    path('admin-panel/promocode/<int:pk>/edit/', views.admin_promocode_edit, name='admin_promocode_edit'),
    path('admin-panel/promocode/<int:pk>/toggle/', views.admin_promocode_toggle, name='admin_promocode_toggle'),
    path('admin-panel/promocode/<int:pk>/delete/', views.admin_promocode_delete, name='admin_promocode_delete'),
    # promo groups
    path('admin-panel/promo-groups/', views.admin_promo_groups, name='admin_promo_groups'),
    path('admin-panel/promo-group/create/', views.admin_promo_group_create, name='admin_promo_group_create'),
    path('admin-panel/promo-group/<int:pk>/edit/', views.admin_promo_group_edit, name='admin_promo_group_edit'),
    path('admin-panel/promo-group/<int:pk>/delete/', views.admin_promo_group_delete, name='admin_promo_group_delete'),
    # promo statistics
    path('admin-panel/promo-stats/', views.admin_promo_stats, name='admin_promo_stats'),
    # promo export
    path('admin-panel/promo-export/', views.admin_promo_export, name='admin_promo_export'),
    # promo AJAX endpoints
    path('admin-panel/promocode/<int:pk>/get-form/', views.admin_promocode_get_form, name='admin_promocode_get_form'),
    path('admin-panel/promocode/<int:pk>/edit-ajax/', views.admin_promocode_edit_ajax, name='admin_promocode_edit_ajax'),
    path('admin-panel/promocode/<int:pk>/change-group/', views.admin_promocode_change_group, name='admin_promocode_change_group'),
    path('admin-panel/promo-group/<int:pk>/get-form/', views.admin_promo_group_get_form, name='admin_promo_group_get_form'),
    path('admin-panel/promo-group/<int:pk>/edit-ajax/', views.admin_promo_group_edit_ajax, name='admin_promo_group_edit_ajax'),
    path('admin-panel/user/<int:user_id>/toggle-manager/', views.admin_toggle_manager, name='admin_toggle_manager'),
    # offline stores
    path('admin-panel/offline-stores/', views.admin_offline_stores, name='admin_offline_stores'),
    path('admin-panel/offline-store/create/', views.admin_offline_store_create, name='admin_offline_store_create'),
    path('admin-panel/offline-store/<int:pk>/edit/', views.admin_offline_store_edit, name='admin_offline_store_edit'),
    path('admin-panel/offline-store/<int:pk>/toggle/', views.admin_offline_store_toggle, name='admin_offline_store_toggle'),
    path('admin-panel/offline-store/<int:pk>/delete/', views.admin_offline_store_delete, name='admin_offline_store_delete'),
    # store management
    path('admin-panel/offline-store/<int:store_id>/manage/', views.admin_store_management, name='admin_store_management'),
    path('admin-panel/offline-store/<int:store_id>/add-to-order/', views.admin_store_add_product_to_order, name='admin_store_add_product_to_order'),
    path('admin-panel/offline-store/<int:store_id>/order/<int:order_id>/items/', views.admin_store_get_order_items, name='admin_store_get_order_items'),
    path('admin-panel/offline-store/<int:store_id>/product/<int:product_id>/colors/', views.admin_store_get_product_colors, name='admin_store_get_product_colors'),
    path('admin-panel/offline-store/<int:store_id>/order/<int:order_id>/remove-item/<int:item_id>/', views.admin_store_remove_product_from_order, name='admin_store_remove_product_from_order'),
    path('admin-panel/offline-store/<int:store_id>/add-to-store/', views.admin_store_add_products_to_store, name='admin_store_add_products_to_store'),
    path('admin-panel/offline-store/<int:store_id>/generate-invoice/', views.admin_store_generate_invoice, name='admin_store_generate_invoice'),
    path('admin-panel/offline-store/<int:store_id>/product/<int:product_id>/update/', views.admin_store_update_product, name='admin_store_update_product'),
    path('admin-panel/offline-store/<int:store_id>/product/<int:product_id>/mark-sold/', views.admin_store_mark_product_sold, name='admin_store_mark_product_sold'),
    path('admin-panel/offline-store/<int:store_id>/product/<int:product_id>/remove/', views.admin_store_remove_product, name='admin_store_remove_product'),
    # print proposals
    path('admin-panel/print-proposal/update-status/', views.admin_print_proposal_update_status, name='admin_print_proposal_update_status'),
    path('admin-panel/print-proposal/award-points/', views.admin_print_proposal_award_points, name='admin_print_proposal_award_points'),
    path('admin-panel/print-proposal/award-promocode/', views.admin_print_proposal_award_promocode, name='admin_print_proposal_award_promocode'),
    # promocodes in cart
    path('cart/apply-promo/', views.apply_promo_code, name='apply_promo_code'),
    path('cart/remove-promo/', views.remove_promo_code, name='remove_promo_code'),
    # Contact manager
    path('cart/contact-manager/', views.contact_manager, name='contact_manager'),
    # Monobank acquiring
    path('cart/monobank/create-invoice/', views.monobank_create_invoice, name='monobank_create_invoice'),
    path('cart/monobank/quick/', views.monobank_create_checkout, name='monobank_quick_invoice'),
    path('payments/monobank/return/', views.monobank_return, name='monobank_return'),
    path('payments/monobank/webhook/', csrf_exempt(views.monobank_webhook), name='monobank_webhook'),
    # API endpoints
    path('api/colors/', _legacy_view('api_colors'), name='api_colors'),
    path('debug/media/', views.debug_media, name='debug_media'),
    path('debug/media-page/', views.debug_media_page, name='debug_media_page'),
    path('debug/product-images/', views.debug_product_images, name='debug_product_images'),
    # dev helper
    path('dev/grant-admin/', views.dev_grant_admin, name='dev_grant_admin'),
    # static pages
    path('add-print/', views.add_print, name='add_print'),
    path('delivery/', views.delivery_view, name='delivery'),
    path('cooperation/', views.cooperation, name='cooperation'),
    path('about/', views.about, name='about'),
    # Google Merchant Center
    path('google-merchant-feed.xml', views.google_merchant_feed, name='google_merchant_feed'),
    # alternate no-cache path
    path('google-merchant-feed-v2.xml', views.google_merchant_feed, name='google_merchant_feed_v2'),
    # UAPROM-style product feed (legacy Bezet feed)
    path('products_feed.xml', views.uaprom_products_feed, name='uaprom_products_feed'),
    # New Dynamic Prom.ua feed
    path('prom-feed.xml', views.prom_feed_xml, name='prom_feed_xml'),
    # Try to intercept media path (might be blocked by Nginx, but worth adding for user request)
    path('media/prom-feed.xml', views.prom_feed_xml, name='prom_feed_xml_legacy_path'),
    
    path('contacts/', views.contacts, name='contacts'),
    path('search/', views.search, name='search'),
    # Test analytics events page
    path('test-analytics/', views.test_analytics_events, name='test_analytics'),
    # favorites
    path('favorites/', views.favorites_list, name='favorites'),
    path('favorites/toggle/<int:product_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('favorites/check/<int:product_id>/', views.check_favorite_status, name='check_favorite_status'),
    path('favorites/count/', views.favorites_count, name='favorites_count'),
    # wholesale prices
    path('pricelist_opt.xlsx', _legacy_view('wholesale_prices_xlsx'), name='wholesale_prices_xlsx'),
    path('pricelist/', _legacy_view('pricelist_page'), name='pricelist_page'),
    path('test-pricelist/', _legacy_view('test_pricelist'), name='test_wholesale_prices'),
    path('wholesale/', _legacy_view('wholesale_page'), name='wholesale_page'),
    path('opt/', _legacy_view('wholesale_page'), name='wholesale_page_alt'),
    path('wholesale/order-form/', _legacy_view('wholesale_order_form'), name='wholesale_order_form'),
    path('wholesale/generate-invoice/', _legacy_view('generate_wholesale_invoice'), name='generate_wholesale_invoice'),
    path('wholesale/download-invoice/<int:invoice_id>/', _legacy_view('download_invoice_file'), name='download_invoice_file'),
    path('wholesale/delete-invoice/<int:invoice_id>/', _legacy_view('delete_wholesale_invoice'), name='delete_wholesale_invoice'),
    path('wholesale/check-approval/<int:invoice_id>/', _legacy_view('check_invoice_approval_status'), name='check_invoice_approval_status'),
    path('wholesale/check-payment-status/<int:invoice_id>/', _legacy_view('check_payment_status'), name='check_payment_status'),
    path('wholesale/debug-invoices/', _legacy_view('debug_invoices'), name='debug_invoices'),
    path('wholesale/create-payment/', _legacy_view('create_wholesale_payment'), name='create_wholesale_payment'),
    path('wholesale/payment-webhook/', _legacy_view('wholesale_payment_webhook'), name='wholesale_payment_webhook'),
    path('wholesale/invoices/', _legacy_view('get_user_invoices'), name='get_user_invoices'),
    # Collaboration admin (staff-only) - теперь в admin_panel?section=collaboration
    path('admin-panel/invoices/update-status/<int:invoice_id>/', views.admin_update_invoice_status, name='admin_update_invoice_status'),
    path('admin-panel/invoices/toggle-approval/<int:invoice_id>/', views.toggle_invoice_approval, name='toggle_invoice_approval'),
    path('admin-panel/invoices/toggle-payment/<int:invoice_id>/', views.toggle_invoice_payment_status, name='toggle_invoice_payment_status'),
    path('admin-panel/invoices/reset-all-status/', views.reset_all_invoices_status, name='reset_all_invoices_status'),
    # Dropship orders admin
    path('admin-panel/dropship/update-status/<int:order_id>/', views.admin_update_dropship_status, name='admin_update_dropship_status'),
    path('admin-panel/dropship/get-order/<int:order_id>/', views.admin_get_dropship_order, name='admin_get_dropship_order'),
    path('admin-panel/dropship/update-order/<int:order_id>/', views.admin_update_dropship_order, name='admin_update_dropship_order'),
    path('admin-panel/dropship/delete-order/<int:order_id>/', views.admin_delete_dropship_order, name='admin_delete_dropship_order'),
]
