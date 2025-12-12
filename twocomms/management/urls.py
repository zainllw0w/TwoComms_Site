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
    path('reports/', views.reports, name='management_reports'),
    path('reports/send/', views.send_report, name='management_send_report'),
    path('reminders/read/', views.reminder_read, name='management_reminder_read'),
    path('reminders/feed/', views.reminder_feed, name='management_reminder_feed'),
    path('profile/update/', views.profile_update, name='management_profile_update'),
    path('profile/bind-code/', views.profile_bind_code, name='management_profile_bind_code'),
    path('tg-manager/webhook/<str:token>/', views.management_bot_webhook, name='management_bot_webhook'),
    path('', views.home, name='management_home'),
]
