from django.contrib import admin
from .models import (
    Category,
    CustomPrintLead,
    CustomPrintLeadAttachment,
    PrintProposal,
    Product,
    ProductFitOption,
    ProductImage,
    PushNotificationCampaign,
    PushNotificationDelivery,
    SurveySession,
    UserPromoCode,
    WebPushDeviceSubscription,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'is_active', 'ai_generation_enabled', 'ai_content_generated')
    list_filter = ('is_active', 'is_featured', 'ai_generation_enabled', 'ai_content_generated')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at', 'ai_content_generated')
    fieldsets = (
        ('Основне', {
            'fields': ('name', 'slug', 'description', 'order', 'is_active', 'is_featured', 'icon', 'cover'),
        }),
        ('AI-генерація SEO', {
            'fields': ('ai_generation_enabled', 'ai_keywords', 'ai_description', 'ai_content_generated'),
            'description': (
                'AI використовується ЛИШЕ коли поставлено галочку '
                '«Дозволити AI-генерацію SEO». За замовчуванням мета-теги '
                'формуються з ручних SEO-полів та fallback.'
            ),
            'classes': ('collapse',),
        }),
        ('Службове', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'category', 'price', 'discount_percent', 'points_reward',
        'featured', 'status', 'fit_selector_enabled', 'ai_generation_enabled',
    )
    list_filter = ('category', 'featured', 'status', 'fit_selector_enabled', 'ai_generation_enabled')
    search_fields = ('title', 'slug', 'seo_title', 'seo_keywords')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at', 'ai_content_generated', 'published_at', 'last_reviewed_at')
    fieldsets = (
        ('Основне', {
            'fields': (
                'title', 'slug', 'category', 'catalog', 'size_grid',
                'price', 'discount_percent', 'featured', 'priority',
                'main_image', 'main_image_alt', 'home_card_image',
            ),
        }),
        ('Описи', {
            'fields': ('short_description', 'full_description', 'description', 'details_text', 'target_audience', 'care_instructions'),
            'classes': ('collapse',),
        }),
        ('SEO (ручне керування)', {
            'fields': ('seo_title', 'seo_description', 'seo_keywords', 'seo_schema'),
            'description': (
                'Заповніть ці поля, щоб повністю контролювати мета-теги і Schema. '
                'AI ніколи не перезаписує ці поля автоматично.'
            ),
        }),
        ('AI-генерація SEO', {
            'fields': ('ai_generation_enabled', 'ai_keywords', 'ai_description', 'ai_content_generated'),
            'description': (
                'AI використовується тільки якщо поставлено галочку '
                '«Дозволити AI-генерацію SEO». Після цього команда '
                '`generate_ai_content` згенерує ai_keywords/ai_description, '
                'які використовуються як fallback, коли ручні SEO-поля порожні.'
            ),
            'classes': ('collapse',),
        }),
        ('UX товару', {
            'fields': ('fit_selector_enabled', 'recommendation_tags'),
        }),
        ('Дропшип', {
            'fields': (
                'is_dropship_available', 'drop_price', 'recommended_price',
                'wholesale_price', 'dropship_note',
            ),
            'classes': ('collapse',),
        }),
        ('Публікація', {
            'fields': ('status', 'published_at', 'last_reviewed_at', 'unpublished_reason', 'points_reward'),
            'classes': ('collapse',),
        }),
        ('Службове', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'image')


@admin.register(ProductFitOption)
class ProductFitOptionAdmin(admin.ModelAdmin):
    list_display = ('product', 'code', 'label', 'order', 'is_default', 'is_active')
    list_filter = ('is_active', 'is_default')
    search_fields = ('product__title', 'code', 'label')


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
