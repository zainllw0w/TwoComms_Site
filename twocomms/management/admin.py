from django.contrib import admin

from .models import (
    ClientFollowUp,
    ManagementDailyActivity,
    ManagementStatsAdviceDismissal,
    ManagementStatsConfig,
)


@admin.register(ManagementStatsConfig)
class ManagementStatsConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "updated_at")


@admin.register(ManagementDailyActivity)
class ManagementDailyActivityAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "active_seconds", "last_seen_at", "updated_at")
    list_filter = ("date",)
    search_fields = ("user__username", "user__email")


@admin.register(ClientFollowUp)
class ClientFollowUpAdmin(admin.ModelAdmin):
    list_display = ("owner", "client", "due_at", "status", "scheduled_at", "closed_at")
    list_filter = ("status", "due_date")
    search_fields = ("owner__username", "client__shop_name", "client__phone")


@admin.register(ManagementStatsAdviceDismissal)
class ManagementStatsAdviceDismissalAdmin(admin.ModelAdmin):
    list_display = ("user", "key", "dismissed_at", "expires_at")
    list_filter = ("expires_at",)
    search_fields = ("user__username", "key")
