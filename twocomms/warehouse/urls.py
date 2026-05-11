"""URL conf для warehouse subdomain (storage.twocomms.shop)."""
from django.urls import path

from warehouse import views
from warehouse.views.dashboard import verify_today_all
from warehouse.telegram_views import (
    storage_telegram_webhook,
    storage_install_pwa,
)

app_name = "warehouse"

urlpatterns = [
    # Auth
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Dashboard
    path("", views.dashboard, name="dashboard"),
    path("today/", views.today_changes, name="today"),
    path("today/verify-all/", verify_today_all, name="today_verify_all"),

    # Categories
    path("categories/", views.category_list, name="category_list"),
    path("categories/<slug:slug>/", views.category_detail, name="category_detail"),
    path(
        "categories/<slug:slug>/bulk-add/",
        views.stock_bulk_add,
        name="category_bulk_add",
    ),

    # Prints
    path("prints/", views.print_list, name="print_list"),
    path("prints/new/", views.print_create, name="print_create"),
    path("prints/<slug:slug>/", views.print_detail, name="print_detail"),
    path("prints/<slug:slug>/edit/", views.print_edit, name="print_edit"),

    # Write-off (from Telegram or Order)
    path(
        "order/<uuid:token>/write-off/",
        views.write_off_entry,
        name="write_off",
    ),
    path(
        "order/<uuid:token>/write-off/submit/",
        views.write_off_submit,
        name="write_off_submit",
    ),

    # History
    path("history/", views.history_list, name="history"),
    path("history/verify/", views.history_verify, name="history_verify"),

    # Finance
    path("finance/", views.finance_dashboard, name="finance"),

    # AJAX endpoints
    path("api/stock-adjust/", views.stock_adjust, name="api_stock_adjust"),
    path("api/print-adjust/", views.print_adjust, name="api_print_adjust"),

    # Telegram webhook
    path("tg/webhook/<str:secret>/", storage_telegram_webhook, name="telegram_webhook"),

    # PWA install entrypoint
    path("install/", storage_install_pwa, name="install"),
]
