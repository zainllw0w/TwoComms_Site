"""URL-маршрути фінансового кабінету (fin.twocomms.shop).

Схема розділів за ТЗ 01 §3:
  /            Платежі (журнал операцій)
  /analytic    Аналітика (вітрина звітів)
  /ai          AI радник
  /calendar    Календар
  /invoices    Рахунки-фактури
  /rules       Автоправила
  /users       Користувачі
  /accounts    Керування рахунками
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

    # --- Основні розділи (каркас; наповнюються у наступних блоках) ---
    path('analytic/', views.analytics, name='finance_analytics'),
    path('ai/', views.ai_advisor, name='finance_ai'),
    path('calendar/', views.calendar, name='finance_calendar'),
    path('invoices/', views.invoices, name='finance_invoices'),
    path('rules/', views.rules, name='finance_rules'),
    path('users/', views.users, name='finance_users'),
    path('accounts/', views.accounts, name='finance_accounts'),

    # Журнал платежів — головна
    path('', views.payments, name='finance_home'),
]
