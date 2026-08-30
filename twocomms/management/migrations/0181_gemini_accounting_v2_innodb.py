from django.db import migrations


GEMINI_ACCOUNTING_TABLES = (
    "management_geminiquotaprofile",
    "management_geminiquotastate",
    "management_geminirequest",
    "management_geminirequestattempt",
    "management_geminimodelquotausage",
)

EXPECTED_COLUMNS = {
    "management_geminiquotaprofile": {
        "id", "profile_version", "model", "rpm_limit", "input_tpm_limit",
        "rpd_limit", "permit_limit", "estimator_version", "source",
        "source_reference", "observed_at", "effective_from", "effective_until",
        "created_at",
    },
    "management_geminiquotastate": {
        "id", "project_identity", "model", "quota_profile_id", "pacific_day",
        "rpd_reserved", "rpd_dispatched", "rpd_uncertain", "in_flight_count",
        "next_permit_expiry_at", "provider_blocks", "external_usage_suspected",
        "accounting_status", "last_success_at", "last_failure_at",
        "last_failure_kind", "last_http_code", "last_latency_ms",
        "latency_ewma_ms", "revision", "created_at", "updated_at",
    },
    "management_geminirequest": {
        "id", "request_id", "parent_request_id", "lane", "task_class",
        "reasoning_task", "logical_turn_id", "source_message_id", "client_id",
        "recovery_job_id", "reply_message_id", "routing_policy_version",
        "accounting_policy_version", "quota_profile_version",
        "authority_snapshot_version", "routing_mode", "commercial_risk",
        "requires_media_reasoning", "candidate_plan", "candidate_plan_digest",
        "candidate_outcomes", "deadline_ms", "deadline_at", "accounting_mode",
        "terminal_resolution", "terminal_reason", "winner_attempt_id",
        "created_at", "provider_phase_started_at", "resolved_at", "updated_at",
    },
    "management_geminirequestattempt": {
        "accounting_mode", "dispatch_pacific_day", "estimated_prompt_tokens",
        "finished_at", "fsm_state", "permit_expires_at", "permit_released_at",
        "project_identity", "provider_block_until", "provider_quota_dimensions",
        "provider_quota_id", "provider_quota_metric",
        "provider_retry_after_seconds", "provider_started_at",
        "reservation_expires_at", "reservation_released_at", "reserved_at",
        "reserved_prompt_tokens", "settled_at", "shadow_decision",
        "shadow_deny_reason", "total_tokens", "winner_claimed",
        "quota_profile_id", "request_graph_id",
    },
}


def verify_gemini_accounting_schema(apps, schema_editor):
    """Fail closed if an interrupted DDL run did not fully reconcile columns."""
    introspection = schema_editor.connection.introspection
    with schema_editor.connection.cursor() as cursor:
        present_tables = set(introspection.table_names(cursor))
        for table, expected in EXPECTED_COLUMNS.items():
            if table not in present_tables:
                raise RuntimeError(
                    f"required Gemini accounting table is missing: {table}"
                )
            description = introspection.get_table_description(cursor, table)
            present_columns = {
                str(getattr(column, "name", None) or column[0])
                for column in description
            }
            missing = sorted(expected - present_columns)
            if missing:
                raise RuntimeError(
                    f"Gemini accounting schema is incomplete for {table}: "
                    + ", ".join(missing)
                )


def ensure_gemini_accounting_tables_innodb(apps, schema_editor):
    """Idempotently converge every V2 lock participant after schema/seed."""
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in GEMINI_ACCOUNTING_TABLES:
            cursor.execute(
                "SELECT ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                [table],
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(
                    f"required Gemini accounting table is missing: {table}"
                )
            if str(row[0] or "").upper() != "INNODB":
                schema_editor.execute(
                    f"ALTER TABLE {schema_editor.quote_name(table)} ENGINE=InnoDB"
                )


class Migration(migrations.Migration):
    # ALTER TABLE issues an implicit commit on MariaDB. Keep it out of the
    # atomic schema/profile migration so a failed engine conversion is visible
    # and safely retryable: completed ALTERs are skipped on the next run.
    atomic = False

    dependencies = [
        ("management", "0180_seed_gemini_quota_profiles"),
    ]

    operations = [
        migrations.RunPython(
            verify_gemini_accounting_schema,
            migrations.RunPython.noop,
        ),
        migrations.RunPython(
            ensure_gemini_accounting_tables_innodb,
            migrations.RunPython.noop,
        ),
    ]
