"""URL-маршрути фінансового кабінету (fin.twocomms.shop).

Розділи за ТЗ 01 §3: /, /analytic, /ai, /calendar, /invoices, /rules, /users.
"""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # --- Авторизація ---
    path('login/', auth_views.LoginView.as_view(
        template_name='finance/login.html',
        redirect_authenticated_user=True,
    ), name='finance_login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='finance_login'), name='finance_logout'),

    # --- Розділи ---
    path('analytic/', views.analytics, name='finance_analytics'),
    path('ai/', views.ai_advisor, name='finance_ai'),
    path('calendar/', views.calendar, name='finance_calendar'),
    path('invoices/', views.invoices, name='finance_invoices'),
    path('rules/', views.rules, name='finance_rules'),
    path('users/', views.users, name='finance_users'),
    path('accounts/', views.accounts, name='finance_accounts'),

    # --- API: довідники + операції ---
    path('api/dropdowns/', views.dropdowns_api, name='finance_dropdowns_api'),
    path('api/entity/create/', views.quick_create_entity_api, name='finance_quick_create_entity_api'),
    path('api/transactions/create/', views.transaction_create_api, name='finance_txn_create_api'),
    path('api/transactions/bulk/', views.transactions_bulk_api, name='finance_txn_bulk_api'),
    path('api/transactions/<int:txn_id>/', views.transaction_detail_api, name='finance_txn_detail_api'),
    path('api/transactions/<int:txn_id>/update/', views.transaction_update_api, name='finance_txn_update_api'),
    path('api/transactions/<int:txn_id>/delete/', views.transaction_delete_api, name='finance_txn_delete_api'),
    path('api/transactions/<int:txn_id>/duplicate/', views.transaction_duplicate_api, name='finance_txn_duplicate_api'),
    path('api/transactions/<int:txn_id>/convert-transfer/', views.transaction_convert_transfer_api, name='finance_txn_convert_transfer_api'),
    path('api/transactions/<int:txn_id>/split/', views.transaction_split_api, name='finance_txn_split_api'),
    path('api/transactions/<int:txn_id>/mark-actual/', views.transaction_mark_actual_api, name='finance_txn_mark_actual_api'),

    # Журнал платежів — головна
    path('', views.payments, name='finance_home'),
]
