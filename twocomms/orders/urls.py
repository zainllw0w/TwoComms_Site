from django.urls import path
from django.shortcuts import render
from . import dropshipper_views

app_name = 'orders'

urlpatterns = [
    # Дропшип маршруты
    path('dropshipper/', dropshipper_views.dropshipper_dashboard, name='dropshipper_dashboard'),
    path('dropshipper/products/', dropshipper_views.dropshipper_products, name='dropshipper_products'),
    path('dropshipper/orders/', dropshipper_views.dropshipper_orders, name='dropshipper_orders'),
    path('dropshipper/statistics/', dropshipper_views.dropshipper_statistics, name='dropshipper_statistics'),
    path('dropshipper/payouts/', dropshipper_views.dropshipper_payouts, name='dropshipper_payouts'),
    path('dropshipper/company/', dropshipper_views.dropshipper_company_settings, name='dropshipper_company'),
    path('dropshipper/test/', lambda request: render(request, 'pages/dropshipper_test.html'), name='dropshipper_test'),
    
    # API маршруты
    path('dropshipper/api/create-order/', dropshipper_views.create_dropshipper_order, name='create_dropshipper_order'),
    path('dropshipper/api/update-order-status/<int:order_id>/', dropshipper_views.update_order_status, name='update_order_status'),
    path('dropshipper/api/request-payout/', dropshipper_views.request_payout, name='request_payout'),
    path('dropshipper/api/product/<int:product_id>/', dropshipper_views.get_product_details, name='get_product_details'),
    
    # API маршруты для корзины
    path('dropshipper/api/cart/add/', dropshipper_views.add_to_cart, name='add_to_cart'),
    path('dropshipper/api/cart/get/', dropshipper_views.get_cart, name='get_cart'),
    path('dropshipper/api/cart/remove/', dropshipper_views.remove_from_cart, name='remove_from_cart'),
    path('dropshipper/api/cart/clear/', dropshipper_views.clear_cart, name='clear_cart'),
]
