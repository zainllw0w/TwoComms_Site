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
    path("prints/<slug:slug>/delete/", views.print_delete, name="print_delete"),

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

    # Consumables (розхідні матеріали)
    path("consumables/", views.consumables_list, name="consumables_list"),
    path("consumables/new/", views.consumable_create, name="consumable_create"),
    path("consumables/<int:pk>/", views.consumable_detail, name="consumable_detail"),
    path("consumables/<int:pk>/edit/", views.consumable_edit, name="consumable_edit"),
    path("consumables/<int:pk>/adjust/", views.consumable_adjust, name="consumable_adjust"),
    path("consumables/<int:pk>/delete/", views.consumable_delete, name="consumable_delete"),
    path("api/consumables/low-stock/", views.consumables_low_stock_api, name="consumables_low_stock_api"),
    path("history/verify/", views.history_verify, name="history_verify"),

    # Finance
    path("finance/", views.finance_dashboard, name="finance"),

    # Settings
    path("settings/", views.settings_index, name="settings"),
    path("settings/categories/", views.settings_categories, name="settings_categories"),
    path(
        "settings/categories/new/",
        views.settings_category_form,
        name="settings_category_new",
    ),
    path(
        "settings/categories/<slug:slug>/edit/",
        views.settings_category_form,
        name="settings_category_edit",
    ),
    path(
        "settings/categories/<slug:slug>/toggle/",
        views.settings_category_toggle,
        name="settings_category_toggle",
    ),
    path(
        "settings/categories/<slug:slug>/delete/",
        views.settings_category_delete,
        name="settings_category_delete",
    ),
    path(
        "settings/subcategories/",
        views.settings_subcategories,
        name="settings_subcategories",
    ),
    path(
        "settings/subcategories/new/",
        views.settings_subcategory_form,
        name="settings_subcategory_new",
    ),
    path(
        "settings/subcategories/<int:pk>/edit/",
        views.settings_subcategory_form,
        name="settings_subcategory_edit",
    ),
    path(
        "settings/subcategories/<int:pk>/toggle/",
        views.settings_subcategory_toggle,
        name="settings_subcategory_toggle",
    ),
    path(
        "settings/subcategories/<int:pk>/delete/",
        views.settings_subcategory_delete,
        name="settings_subcategory_delete",
    ),
    path(
        "settings/print-categories/",
        views.settings_print_categories,
        name="settings_print_categories",
    ),
    path(
        "settings/print-categories/new/",
        views.settings_print_category_form,
        name="settings_print_category_new",
    ),
    path(
        "settings/print-categories/<int:pk>/edit/",
        views.settings_print_category_form,
        name="settings_print_category_edit",
    ),
    path(
        "settings/print-categories/<int:pk>/toggle/",
        views.settings_print_category_toggle,
        name="settings_print_category_toggle",
    ),
    path(
        "settings/print-categories/<int:pk>/delete/",
        views.settings_print_category_delete,
        name="settings_print_category_delete",
    ),
    path(
        "settings/consumable-categories/",
        views.settings_consumable_categories,
        name="settings_consumable_categories",
    ),
    path(
        "settings/consumable-categories/new/",
        views.settings_consumable_category_form,
        name="settings_consumable_category_new",
    ),
    path(
        "settings/consumable-categories/<int:pk>/edit/",
        views.settings_consumable_category_form,
        name="settings_consumable_category_edit",
    ),
    path(
        "settings/consumable-categories/<int:pk>/toggle/",
        views.settings_consumable_category_toggle,
        name="settings_consumable_category_toggle",
    ),
    path(
        "settings/consumable-categories/<int:pk>/delete/",
        views.settings_consumable_category_delete,
        name="settings_consumable_category_delete",
    ),
    path("settings/notifications/", views.settings_notifications, name="settings_notifications"),
    path("settings/notifications/test/", views.settings_notifications_test, name="settings_notifications_test"),
    path("settings/telegram/", views.settings_telegram, name="settings_telegram"),
    path(
        "settings/telegram/test/",
        views.settings_telegram_test,
        name="settings_telegram_test",
    ),
    path("settings/colors/", views.settings_colors, name="settings_colors"),
    path(
        "settings/colors/new/",
        views.settings_color_form,
        name="settings_color_new",
    ),
    path(
        "settings/colors/<int:pk>/edit/",
        views.settings_color_form,
        name="settings_color_edit",
    ),

    # AJAX endpoints
    path("api/stock-adjust/", views.stock_adjust, name="api_stock_adjust"),
    path("api/print-adjust/", views.print_adjust, name="api_print_adjust"),
    path(
        "api/colors/create/",
        views.settings_color_create_ajax,
        name="api_color_create",
    ),

    # Telegram webhook
    path("tg/webhook/<str:secret>/", storage_telegram_webhook, name="telegram_webhook"),

    # PWA install entrypoint
    path("install/", storage_install_pwa, name="install"),
]
