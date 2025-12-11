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
    path('', views.home, name='management_home'),
]
