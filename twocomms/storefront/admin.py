from django.contrib import admin
from .models import Category, Product, ProductImage
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
