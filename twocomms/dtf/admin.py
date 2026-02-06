from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html

from .models import (
    DtfLead,
    DtfLeadAttachment,
    DtfOrder,
    DtfWork,
    LeadStatus,
    OrderStatus,
)
from .telegram import (
    notify_need_fix,
    notify_awaiting_payment,
    notify_paid,
    notify_shipped,
)
from .utils import calculate_pricing


class DtfLeadAttachmentInline(admin.TabularInline):
    model = DtfLeadAttachment
    extra = 0


@admin.register(DtfLead)
class DtfLeadAdmin(admin.ModelAdmin):
    list_display = ("lead_number", "name", "phone", "lead_type", "status", "created_at")
    list_filter = ("status", "lead_type", "created_at")
    search_fields = ("lead_number", "name", "phone")
    inlines = [DtfLeadAttachmentInline]
    readonly_fields = ("lead_number", "created_at", "updated_at")


@admin.register(DtfOrder)
class DtfOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "name", "phone", "status_badge", "meters_total", "price_total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "name", "phone")
    readonly_fields = ("order_number", "created_at", "updated_at")
    actions = [
        "action_approve_mockup",
        "action_request_fix",
        "action_send_payment_link",
        "action_mark_paid",
        "action_mark_shipped",
    ]

    def status_badge(self, obj):
        colors = {
            OrderStatus.NEW_ORDER: "#94a3b8",
            OrderStatus.CHECK_MOCKUP: "#f59e0b",
            OrderStatus.NEED_FIX: "#ef4444",
            OrderStatus.AWAITING_PAYMENT: "#8b5cf6",
            OrderStatus.PRINTING: "#0ea5e9",
            OrderStatus.READY: "#10b981",
            OrderStatus.SHIPPED: "#06b6d4",
            OrderStatus.CLOSED: "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:700;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = _("Статус")

    @admin.action(description=_("Підтвердити макет (AwaitingPayment)"))
    def action_approve_mockup(self, request, queryset):
        updated = queryset.update(status=OrderStatus.AWAITING_PAYMENT)
        for order in queryset:
            notify_awaiting_payment(order)
        self.message_user(request, _("Оновлено %(count)s замовлень") % {"count": updated}, messages.SUCCESS)

    @admin.action(description=_("Запросити правки (NeedFix)"))
    def action_request_fix(self, request, queryset):
        updated = queryset.update(status=OrderStatus.NEED_FIX, need_fix_reason="Потрібні правки макета")
        for order in queryset:
            notify_need_fix(order, order.need_fix_reason or "Потрібні правки")
        self.message_user(request, _("Оновлено %(count)s замовлень") % {"count": updated}, messages.WARNING)

    @admin.action(description=_("Надіслати посилання на оплату (AwaitingPayment)"))
    def action_send_payment_link(self, request, queryset):
        updated = queryset.update(status=OrderStatus.AWAITING_PAYMENT)
        for order in queryset:
            notify_awaiting_payment(order)
        self.message_user(request, _("Оновлено %(count)s замовлень") % {"count": updated}, messages.SUCCESS)

    @admin.action(description=_("Позначити як оплачено (Paid)"))
    def action_mark_paid(self, request, queryset):
        for order in queryset:
            notify_paid(order)
        self.message_user(request, _("Сповіщення про оплату надіслано"), messages.SUCCESS)

    @admin.action(description=_("Відправлено (Shipped + ТТН)"))
    def action_mark_shipped(self, request, queryset):
        updated = 0
        for order in queryset:
            if not order.tracking_number:
                continue
            order.status = OrderStatus.SHIPPED
            order.save(update_fields=["status"])
            notify_shipped(order)
            updated += 1
        if updated:
            self.message_user(request, _("Відправлено %(count)s замовлень") % {"count": updated}, messages.SUCCESS)
        else:
            self.message_user(request, _("Не знайдено ТТН для відправки"), messages.WARNING)

    def save_model(self, request, obj, form, change):
        if obj.length_m and obj.copies:
            pricing = calculate_pricing(obj.length_m, obj.copies)
            if pricing:
                obj.meters_total = pricing["meters_total"]
                obj.price_per_meter = pricing["rate"]
                obj.price_total = pricing["price_total"]
                obj.pricing_tier = pricing["pricing_tier"]
                obj.requires_review = pricing["requires_review"]
        super().save_model(request, obj, form, change)


@admin.register(DtfWork)
class DtfWorkAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_active", "sort_order")
    list_filter = ("category", "is_active")
    search_fields = ("title",)
    ordering = ("sort_order",)
