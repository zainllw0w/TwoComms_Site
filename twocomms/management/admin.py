from django.contrib import admin
from .models import Client

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('shop_name', 'phone', 'full_name', 'contact_role', 'last_call_result', 'next_call_at')
    list_filter = ('contact_role', 'last_call_result', 'is_non_conversion')
    search_fields = ('shop_name', 'phone', 'full_name')
