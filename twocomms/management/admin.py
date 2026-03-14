from django.contrib import admin

from .models import (
    CommandRunLog,
    ClientFollowUp,
    CallQAReview,
    CallRecord,
    ComponentReadiness,
    DtfBridgeSnapshot,
    DuplicateReview,
    LeadParsingJob,
    LeadParsingResult,
    ManagementDailyActivity,
    ManagementLead,
    ManagerDayStatus,
    ManagementStatsAdviceDismissal,
    ManagementStatsConfig,
    NightlyScoreSnapshot,
    OwnershipChangeLog,
    ScoreAppeal,
    SupervisorActionLog,
    TelephonyHealthSnapshot,
    TelephonyWebhookLog,
)


@admin.register(ManagementStatsConfig)
class ManagementStatsConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "formula_version", "defaults_version", "rollout_state", "updated_at")


@admin.register(ComponentReadiness)
class ComponentReadinessAdmin(admin.ModelAdmin):
    list_display = ("component", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("component",)


@admin.register(CommandRunLog)
class CommandRunLogAdmin(admin.ModelAdmin):
    list_display = ("command_name", "run_key", "status", "rows_processed", "warnings_count", "started_at", "finished_at")
    list_filter = ("status", "command_name")
    search_fields = ("command_name", "run_key")


@admin.register(ManagerDayStatus)
class ManagerDayStatusAdmin(admin.ModelAdmin):
    list_display = ("owner", "day", "status", "capacity_factor", "reintegration_flag", "updated_at")
    list_filter = ("status", "reintegration_flag", "day")
    search_fields = ("owner__username", "source_reason")


@admin.register(NightlyScoreSnapshot)
class NightlyScoreSnapshotAdmin(admin.ModelAdmin):
    list_display = ("owner", "snapshot_date", "mosaic_score", "score_confidence", "formula_version", "defaults_version")
    list_filter = ("formula_version", "defaults_version", "snapshot_date")
    search_fields = ("owner__username",)


@admin.register(ScoreAppeal)
class ScoreAppealAdmin(admin.ModelAdmin):
    list_display = ("owner", "snapshot", "status", "created_at", "resolved_at")
    list_filter = ("status",)
    search_fields = ("owner__username", "reason")


@admin.register(DuplicateReview)
class DuplicateReviewAdmin(admin.ModelAdmin):
    list_display = ("incoming_shop_name", "incoming_phone", "zone", "status", "created_at")
    list_filter = ("zone", "status")
    search_fields = ("incoming_shop_name", "incoming_phone")


@admin.register(OwnershipChangeLog)
class OwnershipChangeLogAdmin(admin.ModelAdmin):
    list_display = ("entity_type", "entity_id", "previous_owner", "new_owner", "created_at")
    list_filter = ("entity_type",)
    search_fields = ("reason",)


@admin.register(TelephonyWebhookLog)
class TelephonyWebhookLogAdmin(admin.ModelAdmin):
    list_display = ("provider", "external_event_id", "event_type", "status", "received_at", "processed_at")
    list_filter = ("provider", "status", "event_type")
    search_fields = ("external_event_id",)


@admin.register(CallRecord)
class CallRecordAdmin(admin.ModelAdmin):
    list_display = ("provider", "external_call_id", "manager", "phone", "direction", "duration_seconds", "qa_status", "created_at")
    list_filter = ("provider", "direction", "qa_status")
    search_fields = ("external_call_id", "phone", "manager__username")


@admin.register(TelephonyHealthSnapshot)
class TelephonyHealthSnapshotAdmin(admin.ModelAdmin):
    list_display = ("provider", "status", "total_events", "unmatched_calls", "backlog_count", "snapshot_at")
    list_filter = ("provider", "status")


@admin.register(CallQAReview)
class CallQAReviewAdmin(admin.ModelAdmin):
    list_display = ("call_record", "reviewer", "score", "verdict", "created_at")
    list_filter = ("verdict",)
    search_fields = ("call_record__external_call_id", "reviewer__username")


@admin.register(SupervisorActionLog)
class SupervisorActionLogAdmin(admin.ModelAdmin):
    list_display = ("action_type", "manager", "actor", "created_at")
    list_filter = ("action_type",)
    search_fields = ("manager__username", "actor__username")


@admin.register(DtfBridgeSnapshot)
class DtfBridgeSnapshotAdmin(admin.ModelAdmin):
    list_display = ("source_key", "snapshot_date", "status", "freshness_seconds", "updated_at")
    list_filter = ("source_key", "status")
    search_fields = ("source_key",)


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
