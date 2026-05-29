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
    path('analytic/report/<str:kind>/', views.report, name='finance_report'),
    path('analytic/report/<str:kind>/export/', views.report_export, name='finance_report_export'),
    path('api/metrics/create/', views.metric_create_api, name='finance_metric_create_api'),
    path('api/debt/<int:txn_id>/settle/', views.debt_settle_api, name='finance_debt_settle_api'),
    path('ai/', views.ai_advisor, name='finance_ai'),
    path('calendar/', views.calendar, name='finance_calendar'),
    path('invoices/', views.invoices, name='finance_invoices'),
    path('invoices/new/', views.invoice_form, name='finance_invoice_new'),
    path('invoices/<int:invoice_id>/edit/', views.invoice_form, name='finance_invoice_edit'),
    path('invoices/<int:invoice_id>/print/', views.invoice_print, name='finance_invoice_print'),
    path('api/invoices/save/', views.invoice_save_api, name='finance_invoice_save_api'),
    path('api/invoices/<int:invoice_id>/save/', views.invoice_save_api, name='finance_invoice_update_api'),
    path('api/invoices/<int:invoice_id>/delete/', views.invoice_delete_api, name='finance_invoice_delete_api'),
    path('api/invoices/<int:invoice_id>/pay/', views.invoice_pay_api, name='finance_invoice_pay_api'),
    path('rules/', views.rules, name='finance_rules'),
    path('api/rules/save/', views.rule_save_api, name='finance_rule_save_api'),
    path('api/rules/<int:rule_id>/save/', views.rule_save_api, name='finance_rule_update_api'),
    path('api/rules/<int:rule_id>/toggle/', views.rule_toggle_api, name='finance_rule_toggle_api'),
    path('api/rules/<int:rule_id>/delete/', views.rule_delete_api, name='finance_rule_delete_api'),
    path('api/rules/<int:rule_id>/preview/', views.rule_preview_api, name='finance_rule_preview_api'),
    path('api/rules/<int:rule_id>/apply/', views.rule_apply_api, name='finance_rule_apply_api'),
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

    # --- API: рахунки ---
    path('api/accounts/create/', views.account_create_api, name='finance_account_create_api'),
    path('api/accounts/reorder/', views.accounts_reorder_api, name='finance_accounts_reorder_api'),
    path('api/accounts/<int:account_id>/update/', views.account_update_api, name='finance_account_update_api'),
    path('api/accounts/<int:account_id>/archive/', views.account_archive_api, name='finance_account_archive_api'),
    path('api/accounts/<int:account_id>/delete/', views.account_delete_api, name='finance_account_delete_api'),
    path('api/accounts/<int:account_id>/correct/', views.account_correct_balance_api, name='finance_account_correct_api'),

    # --- API: інтеграції ---
    path('api/integrations/providers/', views.integration_providers_api, name='finance_integration_providers_api'),
    path('api/integrations/start/', views.integration_start_api, name='finance_integration_start_api'),
    path('api/integrations/<int:conn_id>/status/', views.integration_status_api, name='finance_integration_status_api'),
    path('api/integrations/<int:conn_id>/refresh-qr/', views.integration_refresh_qr_api, name='finance_integration_refresh_qr_api'),
    path('api/integrations/<int:conn_id>/link/', views.integration_link_api, name='finance_integration_link_api'),
    path('api/integrations/<int:conn_id>/cancel/', views.integration_cancel_api, name='finance_integration_cancel_api'),

    # --- API: імпорт виписки ---
    path('api/import/preview/', views.import_preview_api, name='finance_import_preview_api'),
    path('api/import/confirm/', views.import_confirm_api, name='finance_import_confirm_api'),

    # --- API: календар ---
    path('api/calendar/day/<str:date_str>/', views.calendar_day_api, name='finance_calendar_day_api'),

    # Журнал платежів — головна
    path('', views.payments, name='finance_home'),
]
