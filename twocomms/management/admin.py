from django.contrib import admin

from .models import (
    ClientFollowUp,
    LeadParsingJob,
    LeadParsingResult,
    ManagementDailyActivity,
    ManagementLead,
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


@admin.register(ManagementLead)
class ManagementLeadAdmin(admin.ModelAdmin):
    list_display = (
        "shop_name",
        "phone",
        "status",
        "lead_source",
        "niche_status",
        "city",
        "added_by",
        "processed_by",
        "created_at",
    )
    list_filter = ("status", "lead_source", "niche_status", "city")
    search_fields = ("shop_name", "phone", "phone_normalized", "google_place_id")


@admin.register(LeadParsingJob)
class LeadParsingJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "request_limit",
        "request_count",
        "added_to_moderation",
        "duplicate_skipped",
        "started_at",
        "finished_at",
    )
    list_filter = ("status", "started_at")
    search_fields = ("id", "current_query")


@admin.register(LeadParsingResult)
class LeadParsingResultAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "status", "place_name", "phone", "keyword", "city", "created_at")
    list_filter = ("status", "city", "keyword")
    search_fields = ("place_name", "phone", "place_id")
