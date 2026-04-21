from django.contrib import admin
from .models import (
    Category,
    CustomPrintLead,
    CustomPrintLeadAttachment,
    PrintProposal,
    Product,
    ProductImage,
    PushNotificationCampaign,
    PushNotificationDelivery,
    SurveySession,
    UserPromoCode,
    WebPushDeviceSubscription,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order'); prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'price', 'discount_percent', 'points_reward', 'featured')
    list_filter = ('category', 'featured')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'image')


@admin.register(PrintProposal)
class PrintProposalAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'awarded_points', 'awarded_promocode', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'description', 'link_url')


@admin.register(SurveySession)
class SurveySessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'survey_key', 'status', 'started_at', 'last_activity_at')
    list_filter = ('status', 'survey_key')
    search_fields = ('user__username', 'survey_key')


@admin.register(UserPromoCode)
class UserPromoCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'promo_code', 'survey_key', 'expires_at', 'created_at')
    list_filter = ('survey_key',)
    search_fields = ('user__username', 'promo_code__code', 'survey_key')


class CustomPrintLeadAttachmentInline(admin.TabularInline):
    model = CustomPrintLeadAttachment
    extra = 0


@admin.register(CustomPrintLead)
class CustomPrintLeadAdmin(admin.ModelAdmin):
    list_display = (
        'lead_number',
        'name',
        'service_kind',
        'product_type',
        'contact_channel',
        'status',
        'created_at',
    )
    list_filter = ('service_kind', 'product_type', 'contact_channel', 'status', 'client_kind')
    search_fields = ('lead_number', 'name', 'contact_value', 'brand_name', 'brief')
    readonly_fields = ('lead_number', 'created_at', 'updated_at')
    inlines = [CustomPrintLeadAttachmentInline]


@admin.register(WebPushDeviceSubscription)
class WebPushDeviceSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'user', 'device_type', 'browser_family', 'is_active', 'last_seen_at')
    list_filter = ('is_active', 'device_type', 'browser_family', 'operating_system')
    search_fields = ('endpoint', 'installation_id', 'user__username')
    readonly_fields = ('subscribed_at', 'updated_at', 'last_seen_at', 'last_success_at', 'last_failure_at')


class PushNotificationDeliveryInline(admin.TabularInline):
    model = PushNotificationDelivery
    extra = 0
    readonly_fields = ('subscription', 'status', 'sent_at', 'displayed_at', 'clicked_at', 'failed_at')
    can_delete = False


@admin.register(PushNotificationCampaign)
class PushNotificationCampaignAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'targeted_count', 'sent_count', 'displayed_count', 'clicked_count', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'body', 'target_url')
    readonly_fields = (
        'created_at',
        'updated_at',
        'sent_started_at',
        'sent_finished_at',
        'targeted_count',
        'sent_count',
        'displayed_count',
        'clicked_count',
        'closed_count',
        'failed_count',
    )
    inlines = [PushNotificationDeliveryInline]
