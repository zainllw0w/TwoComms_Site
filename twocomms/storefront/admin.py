from django.contrib import admin
from .models import Category, Product, ProductImage, PrintProposal, SurveySession, UserPromoCode
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display=('name','slug','order'); prepopulated_fields={'slug':('name',)}
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display=('title','category','price','discount_percent','points_reward','featured')
    list_filter=('category','featured')
    search_fields=('title','slug')
    prepopulated_fields={'slug':('title',)}
@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display=('product','image')

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
