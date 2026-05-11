"""Django admin для аварійних кейсів."""
from __future__ import annotations

from django.contrib import admin

from warehouse.models import (
    Print,
    PrintColorVariant,
    StockItem,
    StockMovement,
    StorageCategory,
    StorageSubcategory,
    WarehouseSettings,
    WriteOffRequest,
)


@admin.register(StorageCategory)
class StorageCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "linked_storefront_category", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("order", "is_active")


class StorageSubcategoryInline(admin.TabularInline):
    model = StorageSubcategory
    extra = 1
    prepopulated_fields = {"slug": ("name",)}


@admin.register(StorageSubcategory)
class StorageSubcategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "slug", "is_default", "order", "is_active")
    list_filter = ("category", "is_active", "is_default")
    search_fields = ("name", "slug")


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ("subcategory", "color", "size", "quantity", "cost_price", "updated_at")
    list_filter = ("subcategory__category", "size")
    search_fields = ("subcategory__name", "color__name", "size")
    raw_id_fields = ("color",)
    readonly_fields = ("created_at", "updated_at")


class PrintColorVariantInline(admin.TabularInline):
    model = PrintColorVariant
    extra = 1


@admin.register(Print)
class PrintAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [PrintColorVariantInline]
    filter_horizontal = ("default_products",)


@admin.register(PrintColorVariant)
class PrintColorVariantAdmin(admin.ModelAdmin):
    list_display = ("print", "color_name", "quantity", "cost_price", "is_default")
    list_filter = ("print", "is_default")
    search_fields = ("color_name", "print__name")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "reason", "delta", "quantity_after", "verified", "created_by")
    list_filter = ("reason", "verified", "created_at")
    search_fields = ("comment", "created_by__username", "order__order_number")
    readonly_fields = (
        "content_type",
        "object_id",
        "delta",
        "quantity_after",
        "reason",
        "comment",
        "order",
        "write_off_request",
        "created_by",
        "created_at",
        "verified",
        "verified_at",
        "verified_by",
    )
    date_hierarchy = "created_at"


@admin.register(WriteOffRequest)
class WriteOffRequestAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "opened_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("order__order_number",)
    readonly_fields = ("token", "created_at", "updated_at")


@admin.register(WarehouseSettings)
class WarehouseSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "evening_reminder_enabled",
        "evening_reminder_hour",
        "evening_reminder_minute",
        "last_reminder_sent_at",
    )

    def has_add_permission(self, request):
        return not WarehouseSettings.objects.exists()
