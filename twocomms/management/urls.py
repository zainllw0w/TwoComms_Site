from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='management/login.html',
        redirect_authenticated_user=True
    ), name='management_login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='management_login'), name='management_logout'),
    path('clients/<int:client_id>/delete/', views.delete_client, name='management_delete_client'),
    path('admin-panel/', views.admin_overview, name='management_admin'),
    path('admin-panel/user/<int:user_id>/clients/', views.admin_user_clients, name='management_admin_user_clients'),
    path('admin-panel/invoices/<int:invoice_id>/approve/', views.admin_invoice_approve_api, name='management_admin_invoice_approve_api'),
    path('admin-panel/invoices/<int:invoice_id>/reject/', views.admin_invoice_reject_api, name='management_admin_invoice_reject_api'),
    path('reports/', views.reports, name='management_reports'),
    path('reports/send/', views.send_report, name='management_send_report'),
    path('reminders/read/', views.reminder_read, name='management_reminder_read'),
    path('reminders/feed/', views.reminder_feed, name='management_reminder_feed'),
    path('profile/update/', views.profile_update, name='management_profile_update'),
    path('profile/bind-code/', views.profile_bind_code, name='management_profile_bind_code'),
    path('tg-manager/webhook/<str:token>/', views.management_bot_webhook, name='management_bot_webhook'),
    path('invoices/', views.invoices, name='management_invoices'),
    path('invoices/api/list/', views.invoices_list_api, name='management_invoices_list_api'),
    path('invoices/api/generate/', views.invoices_generate_api, name='management_invoices_generate_api'),
    path('invoices/<int:invoice_id>/download/', views.invoices_download, name='management_invoices_download'),
    path('invoices/api/<int:invoice_id>/delete/', views.invoices_delete_api, name='management_invoices_delete_api'),
    path('invoices/api/<int:invoice_id>/submit/', views.invoices_submit_for_review_api, name='management_invoices_submit_for_review_api'),
    path('invoices/api/<int:invoice_id>/create-payment/', views.invoices_create_payment_api, name='management_invoices_create_payment_api'),
    path('commercial-offer/email/', views.commercial_offer_email, name='management_commercial_offer_email'),
    path('commercial-offer/email/preview/', views.commercial_offer_email_preview_api, name='management_commercial_offer_email_preview_api'),
    path('commercial-offer/email/send/', views.commercial_offer_email_send_api, name='management_commercial_offer_email_send_api'),
    path('commercial-offer/email/check/', views.commercial_offer_email_check_api, name='management_commercial_offer_email_check_api'),
    path('commercial-offer/email/log/<int:log_id>/', views.commercial_offer_email_log_detail_api, name='management_commercial_offer_email_log_detail_api'),
    path('', views.home, name='management_home'),
]
