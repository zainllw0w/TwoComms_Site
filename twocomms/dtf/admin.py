from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html

from .models import (
    DtfEventLog,
    DtfLead,
    DtfLeadAttachment,
    DtfLifecycleStatus,
    DtfOrder,
    DtfPreflightReport,
    DtfPricingConfig,
    DtfQuote,
    DtfSampleLead,
    DtfStatusEvent,
    DtfUpload,
    DtfBuilderSession,
    DtfWork,
    KnowledgePost,
    LeadStatus,
    OrderStatus,
)
from .telegram import (
    notify_need_fix,
    notify_awaiting_payment,
    notify_paid,
    notify_shipped,
)
from .notify import notify_customer_status_change
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
    list_display = ("order_number", "name", "phone", "status_badge", "lifecycle_status", "meters_total", "price_total", "created_at")
    list_filter = ("status", "lifecycle_status", "requires_review", "order_type", "created_at")
    search_fields = ("order_number", "name", "phone")
    readonly_fields = ("order_number", "created_at", "updated_at")
    actions = [
        "action_approve_mockup",
        "action_request_fix",
        "action_send_payment_link",
        "action_mark_paid",
        "action_mark_shipped",
        "action_lifecycle_confirmed",
        "action_lifecycle_in_production",
        "action_lifecycle_delivered",
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
            try:
                order.transition_lifecycle(
                    DtfLifecycleStatus.SHIPPED,
                    actor="manager",
                    public_message=_("Замовлення відправлено"),
                )
                notify_customer_status_change(order, _("Замовлення відправлено"))
            except ValueError:
                pass
            notify_shipped(order)
            updated += 1
        if updated:
            self.message_user(request, _("Відправлено %(count)s замовлень") % {"count": updated}, messages.SUCCESS)
        else:
            self.message_user(request, _("Не знайдено ТТН для відправки"), messages.WARNING)

    @admin.action(description=_("Lifecycle → Confirmed"))
    def action_lifecycle_confirmed(self, request, queryset):
        updated = 0
        for order in queryset:
            try:
                order.transition_lifecycle(
                    DtfLifecycleStatus.CONFIRMED,
                    actor="manager",
                    public_message=_("Замовлення підтверджено менеджером"),
                )
                updated += 1
            except ValueError:
                continue
        self.message_user(request, _("Оновлено %(count)s lifecycle-переходів") % {"count": updated}, messages.SUCCESS)

    @admin.action(description=_("Lifecycle → In production"))
    def action_lifecycle_in_production(self, request, queryset):
        updated = 0
        for order in queryset:
            try:
                order.transition_lifecycle(
                    DtfLifecycleStatus.IN_PRODUCTION,
                    actor="manager",
                    public_message=_("Замовлення передано у виробництво"),
                )
                updated += 1
            except ValueError:
                continue
        self.message_user(request, _("Оновлено %(count)s lifecycle-переходів") % {"count": updated}, messages.SUCCESS)

    @admin.action(description=_("Lifecycle → Delivered"))
    def action_lifecycle_delivered(self, request, queryset):
        updated = 0
        for order in queryset:
            try:
                order.transition_lifecycle(
                    DtfLifecycleStatus.DELIVERED,
                    actor="manager",
                    public_message=_("Замовлення доставлено"),
                )
                notify_customer_status_change(order, _("Замовлення доставлено"))
                updated += 1
            except ValueError:
                continue
        self.message_user(request, _("Оновлено %(count)s lifecycle-переходів") % {"count": updated}, messages.SUCCESS)

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


@admin.register(KnowledgePost)
class KnowledgePostAdmin(admin.ModelAdmin):
    list_display = ("title", "pub_date", "is_published", "updated_at")
    list_filter = ("is_published", "pub_date")
    search_fields = ("title", "slug", "excerpt", "content_md")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("content_html", "created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": ("title", "slug", "is_published", "pub_date"),
        }),
        (_("Контент"), {
            "fields": ("excerpt", "content_md", "content_html"),
        }),
        (_("SEO"), {
            "fields": ("seo_title", "seo_description"),
        }),
        (_("Службове"), {
            "fields": ("created_at", "updated_at"),
        }),
    )


@admin.register(DtfSampleLead)
class DtfSampleLeadAdmin(admin.ModelAdmin):
    list_display = ("sample_number", "name", "phone", "sample_size", "status", "is_brand_volume", "created_at")
    list_filter = ("sample_size", "status", "is_brand_volume", "created_at")
    search_fields = ("sample_number", "name", "phone", "city", "np_branch")
    readonly_fields = ("sample_number", "created_at", "updated_at")


@admin.register(DtfBuilderSession)
class DtfBuilderSessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "status", "product_type", "placement", "quantity", "updated_at")
    list_filter = ("status", "product_type", "placement", "updated_at")
    search_fields = ("session_id", "delivery_city", "delivery_np_branch")
    readonly_fields = ("session_id", "created_at", "updated_at")


@admin.register(DtfPricingConfig)
class DtfPricingConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "is_active", "effective_from", "base_price_per_meter", "updated_at")
    list_filter = ("is_active", "effective_from")
    search_fields = ("name",)


@admin.register(DtfUpload)
class DtfUploadAdmin(admin.ModelAdmin):
    list_display = ("id", "sha256", "mime_type", "size_bytes", "source", "created_at")
    list_filter = ("mime_type", "source", "created_at")
    search_fields = ("sha256", "file")
    readonly_fields = ("sha256", "size_bytes", "created_at")


@admin.register(DtfPreflightReport)
class DtfPreflightReportAdmin(admin.ModelAdmin):
    list_display = ("id", "upload", "result", "engine_version", "created_at")
    list_filter = ("result", "engine_version", "created_at")
    search_fields = ("upload__sha256",)
    readonly_fields = ("created_at",)


@admin.register(DtfQuote)
class DtfQuoteAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "length_m", "unit_price", "total", "currency", "valid_until", "created_at")
    list_filter = ("source", "currency", "created_at")
    search_fields = ("source", "pricing_version")
    readonly_fields = ("created_at",)


@admin.register(DtfStatusEvent)
class DtfStatusEventAdmin(admin.ModelAdmin):
    list_display = ("order", "status_from", "status_to", "actor", "created_at")
    list_filter = ("status_from", "status_to", "actor", "created_at")
    search_fields = ("order__order_number", "public_message")
    readonly_fields = ("created_at",)


@admin.register(DtfEventLog)
class DtfEventLogAdmin(admin.ModelAdmin):
    list_display = ("event_name", "order", "created_at")
    list_filter = ("event_name", "created_at")
    search_fields = ("event_name", "order__order_number")
    readonly_fields = ("created_at",)
