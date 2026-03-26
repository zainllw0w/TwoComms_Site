from django.contrib import admin

from .models import (
    ClientStageEvent,
    CommandRunLog,
    ClientFollowUp,
    CallQAReview,
    CallRecord,
    ComponentReadiness,
    DtfBridgeSnapshot,
    DuplicateReview,
    FollowUpEvent,
    LeadParsingJob,
    LeadParsingQueryState,
    LeadParsingResult,
    LeadParsingRuntimeLock,
    ManagementDailyActivity,
    ManagementLead,
    ManagerDayFact,
    ManagerDayStatus,
    ManagementStatsAdviceDismissal,
    ManagementStatsConfig,
    NightlyScoreSnapshot,
    OwnershipChangeLog,
    ReasonSignal,
    ScoreAppeal,
    ScoreAmendment,
    SupervisorActionLog,
    TelephonyHealthSnapshot,
    TelephonyWebhookLog,
    VerifiedWorkEvent,
    WorkingCalendarAssignment,
    WorkingCalendarException,
    WorkingCalendarProfile,
)


class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


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
class NightlyScoreSnapshotAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
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
class DtfBridgeSnapshotAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("source_key", "snapshot_date", "status", "freshness_seconds", "updated_at")
    list_filter = ("source_key", "status")
    search_fields = ("source_key",)


@admin.register(ManagementDailyActivity)
class ManagementDailyActivityAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "active_seconds", "last_seen_at", "updated_at")
    list_filter = ("date",)
    search_fields = ("user__username", "user__email")


@admin.register(ClientFollowUp)
class ClientFollowUpAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("owner", "client", "due_at", "status", "followup_kind", "scheduled_at", "closed_at")
    list_filter = ("status", "followup_kind", "due_date")
    search_fields = ("owner__username", "client__shop_name", "client__phone")


@admin.register(FollowUpEvent)
class FollowUpEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("owner", "followup", "event_type", "followup_kind", "occurred_at", "source")
    list_filter = ("event_type", "followup_kind", "source")
    search_fields = ("event_key", "owner__username", "client__shop_name", "client__phone")


@admin.register(ClientStageEvent)
class ClientStageEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("owner", "client", "stage_code", "phase_number", "result_code", "occurred_at")
    list_filter = ("stage_code", "phase_number", "result_code")
    search_fields = ("event_key", "owner__username", "client__shop_name", "client__phone")


@admin.register(ReasonSignal)
class ReasonSignalAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("owner", "client", "reason_code", "quality_label", "captured_at")
    list_filter = ("quality_label", "reason_code")
    search_fields = ("event_key", "owner__username", "client__shop_name", "client__phone")


@admin.register(VerifiedWorkEvent)
class VerifiedWorkEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("owner", "client", "verification_level", "evidence_kind", "verified_at")
    list_filter = ("verification_level", "evidence_kind")
    search_fields = ("event_key", "owner__username", "client__shop_name", "client__phone")


@admin.register(ManagerDayFact)
class ManagerDayFactAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("owner", "day", "fact_key", "day_status", "interactions_total", "followups_overdue", "materialized_at")
    list_filter = ("fact_key", "day_status", "day")
    search_fields = ("owner__username",)


@admin.register(ScoreAmendment)
class ScoreAmendmentAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("owner", "effective_date", "status", "delta_score", "updated_at")
    list_filter = ("status", "effective_date")
    search_fields = ("event_key", "owner__username", "reason")


@admin.register(WorkingCalendarProfile)
class WorkingCalendarProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "timezone_name", "is_active", "updated_at")
    list_filter = ("is_active", "timezone_name")
    search_fields = ("name", "owner__username")


@admin.register(WorkingCalendarAssignment)
class WorkingCalendarAssignmentAdmin(admin.ModelAdmin):
    list_display = ("owner", "profile", "effective_from", "effective_to", "priority", "updated_at")
    list_filter = ("effective_from", "effective_to")
    search_fields = ("owner__username", "profile__name")


@admin.register(WorkingCalendarException)
class WorkingCalendarExceptionAdmin(admin.ModelAdmin):
    list_display = ("profile", "owner", "day", "status", "capacity_factor", "updated_at")
    list_filter = ("status", "day")
    search_fields = ("profile__name", "owner__username", "source_reason")


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
        "requires_phone_completion",
        "status",
        "lead_source",
        "niche_status",
        "city",
        "added_by",
        "processed_by",
        "created_at",
    )
    list_filter = ("status", "lead_source", "niche_status", "city")
    search_fields = ("shop_name", "phone", "phone_normalized", "website_url", "website_match_key", "google_place_id")


@admin.register(LeadParsingJob)
class LeadParsingJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "history_lookback_days",
        "save_no_phone_leads",
        "included_type",
        "request_limit",
        "target_leads_limit",
        "request_count",
        "saved_no_phone_to_moderation",
        "added_to_moderation",
        "queries_exhausted_normal",
        "queries_exhausted_anomaly",
        "duplicate_skipped",
        "recent_history_phone_skipped",
        "recent_history_place_skipped",
        "stop_reason_code",
        "started_at",
        "finished_at",
    )
    list_filter = ("status", "started_at", "history_lookback_days")
    search_fields = ("id", "current_query")


@admin.register(LeadParsingResult)
class LeadParsingResultAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "status", "place_name", "phone", "keyword", "city", "created_at")
    list_filter = ("status", "city", "keyword")
    search_fields = ("place_name", "phone", "place_id")


@admin.register(LeadParsingQueryState)
class LeadParsingQueryStateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job",
        "status",
        "keyword",
        "city",
        "included_type",
        "pages_fetched",
        "places_seen_count",
        "places_added_count",
        "exhausted_reason_code",
        "updated_at",
    )
    list_filter = ("status", "included_type", "city")
    search_fields = ("keyword", "city", "text_query", "exhausted_reason_code")


@admin.register(LeadParsingRuntimeLock)
class LeadParsingRuntimeLockAdmin(admin.ModelAdmin):
    list_display = ("singleton_key", "active_job", "updated_at")
    readonly_fields = ("singleton_key", "updated_at")
