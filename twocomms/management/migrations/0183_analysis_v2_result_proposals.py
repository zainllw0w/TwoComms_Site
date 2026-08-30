from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models

from management.migrations._resumable_schema import ensure_additive_schema


RESULT_TABLE = "management_igconversationanalysisresult"
PROPOSAL_TABLE = "management_iganalysisproposal"

RESULT_FIELDS = (
    "id", "result_key", "line_id", "watermark_message_id", "job_revision",
    "materiality_event_highwater", "materiality_digest", "authority_digest",
    "artifact_digest", "state_correlation", "result_schema_version",
    "normalizer_version", "source_kind", "interaction_type", "score_band",
    "detected_language", "purchase_probability", "purchase_confidence",
    "probability_basis", "evidence_manifest", "customer_evidence_count",
    "manager_evidence_count", "authority_evidence_count",
    "active_objection_type", "active_objection_confidence", "deferred_kind",
    "deferred_until", "deferred_condition_code", "repeat_intent_kind",
    "repeat_intent_confidence", "prior_purchase_count", "ltv_signal",
    "injection_risk", "injection_evidence_message_ids", "has_conflicts",
    "conflict_codes", "uncertainty_codes", "analysis_model", "prompt_version",
    "routing_policy_version", "reasoning_policy_version", "project_slot",
    "gemini_request_ref", "usage_status", "prompt_tokens", "thoughts_tokens",
    "candidates_tokens", "total_tokens", "analysis_latency_ms",
    "result_digest", "analyzed_at", "created_at",
    "client", "commercial_episode", "legacy_snapshot",
)
PROPOSAL_FIELDS = (
    "id", "proposal_key", "ordinal", "line_id", "proposal_type",
    "target_scope", "target_definition_key", "target_definition_version",
    "target_key", "typed_value", "evidence_message_ids", "confidence",
    "source_result_digest", "expected_materiality_digest",
    "expected_authority_digest", "expected_state_correlation", "status",
    "decision_code", "projector_version", "decided_at", "created_at",
    "updated_at", "analysis_result", "client", "commercial_episode",
)
FIELD_SPECS = tuple(
    ("management", "IgConversationAnalysisResult", field)
    for field in RESULT_FIELDS
) + tuple(
    ("management", "IgAnalysisProposal", field)
    for field in PROPOSAL_FIELDS
)
INDEX_SPECS = tuple(
    ("management", "IgConversationAnalysisResult", name)
    for name in (
        "ig_anres_client_created", "ig_anres_episode_line",
        "ig_anres_materiality", "ig_anres_probability",
    )
) + tuple(
    ("management", "IgAnalysisProposal", name)
    for name in (
        "ig_anprop_status_id", "ig_anprop_client_status",
        "ig_anprop_episode_line", "ig_anprop_type_status",
    )
)
CHECK_SPECS = tuple(
    ("management", "IgConversationAnalysisResult", name)
    for name in (
        "ig_anres_probability_range", "ig_anres_confidence_range",
        "ig_anres_objection_conf_range", "ig_anres_repeat_conf_range",
        "ig_anres_materiality_positive",
    )
) + tuple(
    ("management", "IgAnalysisProposal", name)
    for name in ("ig_anprop_confidence_range", "ig_anprop_status_valid")
)
UNIQUE_SPECS = (
    ("management", "IgConversationAnalysisResult", "ig_anres_result_key_uniq", ("result_key",)),
    ("management", "IgConversationAnalysisResult", "ig_anres_snapshot_uniq", ("legacy_snapshot",)),
    (
        "management", "IgConversationAnalysisResult",
        "ig_anres_cursor_version_uniq",
        ("client", "job_revision", "materiality_event_highwater", "result_schema_version"),
    ),
    ("management", "IgAnalysisProposal", "ig_anprop_key_uniq", ("proposal_key",)),
    (
        "management", "IgAnalysisProposal", "ig_anprop_result_ordinal_uniq",
        ("analysis_result", "ordinal"),
    ),
)


def _ensure_innodb(schema_editor, table_name):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            [table_name],
        )
        row = cursor.fetchone()
    if not row:
        raise RuntimeError(f"required Analysis V2 table missing: {table_name}")
    if str(row[0] or "").upper() != "INNODB":
        schema_editor.execute(
            f"ALTER TABLE {schema_editor.quote_name(table_name)} ENGINE=InnoDB"
        )


def _ensure_unique_shape(apps, schema_editor, spec):
    app_label, model_name, name, field_names = spec
    model = apps.get_model(app_label, model_name)
    expected_columns = tuple(
        model._meta.get_field(field_name).column for field_name in field_names
    )
    with schema_editor.connection.cursor() as cursor:
        existing = schema_editor.connection.introspection.get_constraints(
            cursor,
            model._meta.db_table,
        )
    named = existing.get(name)
    if named is not None:
        if not named.get("unique") or tuple(named.get("columns") or ()) != expected_columns:
            raise RuntimeError(f"{name} has incompatible shape")
        return
    if any(
        row.get("unique")
        and tuple(row.get("columns") or ()) == expected_columns
        for row in existing.values()
    ):
        return
    schema_editor.add_constraint(
        model,
        models.UniqueConstraint(fields=field_names, name=name),
    )


def ensure_analysis_v2_schema(apps, schema_editor):
    introspection = schema_editor.connection.introspection
    original_tables = set(introspection.table_names())
    result_model = apps.get_model("management", "IgConversationAnalysisResult")
    proposal_model = apps.get_model("management", "IgAnalysisProposal")

    if RESULT_TABLE not in original_tables:
        schema_editor.create_model(result_model)
    _ensure_innodb(schema_editor, RESULT_TABLE)
    if PROPOSAL_TABLE not in original_tables:
        schema_editor.create_model(proposal_model)
    _ensure_innodb(schema_editor, PROPOSAL_TABLE)

    existing_models = {
        "IgConversationAnalysisResult" if RESULT_TABLE in original_tables else "",
        "IgAnalysisProposal" if PROPOSAL_TABLE in original_tables else "",
    }
    ensure_additive_schema(
        apps,
        schema_editor,
        field_specs=tuple(
            spec for spec in FIELD_SPECS if spec[1] in existing_models
        ),
        index_specs=tuple(
            spec for spec in INDEX_SPECS if spec[1] in existing_models
        ),
        constraint_specs=tuple(
            spec for spec in CHECK_SPECS if spec[1] in existing_models
        ),
    )
    for spec in UNIQUE_SPECS:
        table_name = apps.get_model(spec[0], spec[1])._meta.db_table
        if table_name in original_tables:
            _ensure_unique_shape(apps, schema_editor, spec)


def create_result_append_only_triggers(apps, schema_editor):
    del apps
    update_name = "ig_anres_no_update"
    delete_name = "ig_anres_no_delete"
    proposal_delete_name = "ig_anprop_no_delete"
    proposal_update_name = "ig_anprop_identity_update"
    identity_columns = (
        "proposal_key", "analysis_result_id", "ordinal", "client_id",
        "commercial_episode_id", "line_id", "proposal_type", "target_scope",
        "target_definition_key", "target_definition_version", "target_key",
        "typed_value", "evidence_message_ids", "confidence",
        "source_result_digest", "expected_materiality_digest",
        "expected_authority_digest", "expected_state_correlation", "created_at",
    )
    if schema_editor.connection.vendor == "mysql":
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {update_name}")
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {delete_name}")
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {proposal_delete_name}")
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {proposal_update_name}")
        schema_editor.execute(
            f"CREATE TRIGGER {update_name} BEFORE UPDATE ON {RESULT_TABLE} "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' "
            "SET MESSAGE_TEXT='IgConversationAnalysisResult is append-only'"
        )
        schema_editor.execute(
            f"CREATE TRIGGER {delete_name} BEFORE DELETE ON {RESULT_TABLE} "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' "
            "SET MESSAGE_TEXT='IgConversationAnalysisResult is append-only'"
        )
        schema_editor.execute(
            f"CREATE TRIGGER {proposal_delete_name} BEFORE DELETE ON {PROPOSAL_TABLE} "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' "
            "SET MESSAGE_TEXT='IgAnalysisProposal cannot be deleted'"
        )
        unchanged = " AND ".join(
            f"OLD.{column} <=> NEW.{column}" for column in identity_columns
        )
        schema_editor.execute(
            f"CREATE TRIGGER {proposal_update_name} BEFORE UPDATE ON {PROPOSAL_TABLE} "
            f"FOR EACH ROW BEGIN IF NOT ({unchanged}) THEN "
            "SIGNAL SQLSTATE '45000' "
            "SET MESSAGE_TEXT='IgAnalysisProposal identity is immutable'; "
            "END IF; END"
        )
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {update_name}")
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {delete_name}")
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {proposal_delete_name}")
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {proposal_update_name}")
        schema_editor.execute(
            f"CREATE TRIGGER {update_name} BEFORE UPDATE ON {RESULT_TABLE} "
            "BEGIN SELECT RAISE(ABORT, 'IgConversationAnalysisResult is append-only'); END"
        )
        schema_editor.execute(
            f"CREATE TRIGGER {delete_name} BEFORE DELETE ON {RESULT_TABLE} "
            "BEGIN SELECT RAISE(ABORT, 'IgConversationAnalysisResult is append-only'); END"
        )
        schema_editor.execute(
            f"CREATE TRIGGER {proposal_delete_name} BEFORE DELETE ON {PROPOSAL_TABLE} "
            "BEGIN SELECT RAISE(ABORT, 'IgAnalysisProposal cannot be deleted'); END"
        )
        changed = " OR ".join(
            f"OLD.{column} IS NOT NEW.{column}" for column in identity_columns
        )
        schema_editor.execute(
            f"CREATE TRIGGER {proposal_update_name} BEFORE UPDATE ON {PROPOSAL_TABLE} "
            f"WHEN {changed} BEGIN SELECT RAISE(ABORT, "
            "'IgAnalysisProposal identity is immutable'); END"
        )
    elif schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "CREATE OR REPLACE FUNCTION ig_analysis_v2_append_only_raise() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'IgConversationAnalysisResult is append-only'; END; $$"
        )
        for name, action in ((update_name, "UPDATE"), (delete_name, "DELETE")):
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {name} ON {RESULT_TABLE}")
            schema_editor.execute(
                f"CREATE TRIGGER {name} BEFORE {action} ON {RESULT_TABLE} "
                "FOR EACH ROW EXECUTE FUNCTION ig_analysis_v2_append_only_raise()"
            )
        schema_editor.execute(
            f"DROP TRIGGER IF EXISTS {proposal_delete_name} ON {PROPOSAL_TABLE}"
        )
        schema_editor.execute(
            f"CREATE TRIGGER {proposal_delete_name} BEFORE DELETE ON {PROPOSAL_TABLE} "
            "FOR EACH ROW EXECUTE FUNCTION ig_analysis_v2_append_only_raise()"
        )
        schema_editor.execute(
            "CREATE OR REPLACE FUNCTION ig_analysis_proposal_identity_raise() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "IF ROW(OLD.proposal_key, OLD.analysis_result_id, OLD.ordinal, OLD.client_id, "
            "OLD.commercial_episode_id, OLD.line_id, OLD.proposal_type, OLD.target_scope, "
            "OLD.target_definition_key, OLD.target_definition_version, OLD.target_key, "
            "OLD.typed_value, OLD.evidence_message_ids, OLD.confidence, "
            "OLD.source_result_digest, OLD.expected_materiality_digest, "
            "OLD.expected_authority_digest, OLD.expected_state_correlation, OLD.created_at) "
            "IS DISTINCT FROM ROW(NEW.proposal_key, NEW.analysis_result_id, NEW.ordinal, "
            "NEW.client_id, NEW.commercial_episode_id, NEW.line_id, NEW.proposal_type, "
            "NEW.target_scope, NEW.target_definition_key, NEW.target_definition_version, "
            "NEW.target_key, NEW.typed_value, NEW.evidence_message_ids, NEW.confidence, "
            "NEW.source_result_digest, NEW.expected_materiality_digest, "
            "NEW.expected_authority_digest, NEW.expected_state_correlation, NEW.created_at) "
            "THEN RAISE EXCEPTION 'IgAnalysisProposal identity is immutable'; END IF; "
            "RETURN NEW; END; $$"
        )
        schema_editor.execute(
            f"DROP TRIGGER IF EXISTS {proposal_update_name} ON {PROPOSAL_TABLE}"
        )
        schema_editor.execute(
            f"CREATE TRIGGER {proposal_update_name} BEFORE UPDATE ON {PROPOSAL_TABLE} "
            "FOR EACH ROW EXECUTE FUNCTION ig_analysis_proposal_identity_raise()"
        )


STATE_OPERATIONS = [
    migrations.CreateModel(
        name="IgConversationAnalysisResult",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("result_key", models.CharField(max_length=160, unique=True)),
            ("line_id", models.CharField(blank=True, default="", max_length=96)),
            ("watermark_message_id", models.PositiveBigIntegerField()),
            ("job_revision", models.PositiveBigIntegerField()),
            ("materiality_event_highwater", models.PositiveBigIntegerField()),
            ("materiality_digest", models.CharField(max_length=64)),
            ("authority_digest", models.CharField(blank=True, default="", max_length=64)),
            ("artifact_digest", models.CharField(blank=True, default="", max_length=64)),
            ("state_correlation", models.CharField(max_length=64)),
            ("result_schema_version", models.CharField(max_length=32)),
            ("normalizer_version", models.CharField(max_length=32)),
            ("source_kind", models.CharField(choices=[("ai", "Gemini analysis"), ("rules", "Deterministic rules")], default="ai", max_length=16)),
            ("interaction_type", models.CharField(choices=[("unknown", "Невідомо"), ("reaction_only", "Лише реакція"), ("information_only", "Лише інформація"), ("product_interest", "Інтерес до товару"), ("size_fit_question", "Питання про розмір"), ("custom_print", "Кастомний принт"), ("price_objection", "Заперечення щодо ціни"), ("high_intent", "Високий намір"), ("payment_pending", "Очікує оплату"), ("paid_order_waiting", "Оплачено / очікує товар"), ("no_reply", "Не відповідає"), ("explicit_no_buy", "Явно не купує"), ("opt_out", "Відмовився від повідомлень"), ("spam_abuse", "Спам / образи"), ("manager_observation", "Спостереження менеджера"), ("collaboration", "Співпраця / creator"), ("wholesale_b2b", "Опт / B2B"), ("support_complaint", "Підтримка / скарга"), ("exchange_request", "Обмін товару"), ("return_request", "Повернення товару"), ("community_casual", "Спільнота / casual")], db_index=True, default="unknown", max_length=32)),
            ("score_band", models.CharField(choices=[("cold", "Холодний"), ("exploring", "Вивчає"), ("qualified", "Кваліфікований"), ("high_intent", "Високий намір"), ("checkout", "Оформлення"), ("paid", "Оплачено"), ("lost", "Втрачено"), ("opted_out", "Відмовився від повідомлень")], db_index=True, max_length=24)),
            ("detected_language", models.CharField(blank=True, default="", max_length=12)),
            ("purchase_probability", models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
            ("purchase_confidence", models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
            ("probability_basis", models.CharField(choices=[("customer_evidence", "Customer evidence"), ("deterministic_no_buy", "Explicit no-buy"), ("deterministic_opt_out", "Explicit opt-out"), ("insufficient_evidence", "Insufficient evidence")], default="insufficient_evidence", max_length=32)),
            ("evidence_manifest", models.JSONField(blank=True, default=list)),
            ("customer_evidence_count", models.PositiveSmallIntegerField(default=0)),
            ("manager_evidence_count", models.PositiveSmallIntegerField(default=0)),
            ("authority_evidence_count", models.PositiveSmallIntegerField(default=0)),
            ("active_objection_type", models.CharField(blank=True, default="", max_length=32)),
            ("active_objection_confidence", models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
            ("deferred_kind", models.CharField(choices=[("none", "Not deferred"), ("date", "Specific date"), ("event", "External event"), ("payday", "Payday"), ("indefinite", "No exact time")], default="none", max_length=16)),
            ("deferred_until", models.DateTimeField(blank=True, null=True)),
            ("deferred_condition_code", models.CharField(blank=True, default="", max_length=32)),
            ("repeat_intent_kind", models.CharField(blank=True, default="", max_length=32)),
            ("repeat_intent_confidence", models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
            ("prior_purchase_count", models.PositiveIntegerField(default=0)),
            ("ltv_signal", models.CharField(choices=[("unknown", "Unknown"), ("first_purchase", "First purchase"), ("repeat_customer", "Repeat customer"), ("reactivation", "Reactivation")], default="unknown", max_length=24)),
            ("injection_risk", models.CharField(choices=[("none", "No signal"), ("suspected", "Suspected"), ("high", "High confidence signal")], default="none", max_length=16)),
            ("injection_evidence_message_ids", models.JSONField(blank=True, default=list)),
            ("has_conflicts", models.BooleanField(default=False)),
            ("conflict_codes", models.JSONField(blank=True, default=list)),
            ("uncertainty_codes", models.JSONField(blank=True, default=list)),
            ("analysis_model", models.CharField(blank=True, default="", max_length=80)),
            ("prompt_version", models.CharField(blank=True, default="", max_length=40)),
            ("routing_policy_version", models.CharField(blank=True, default="", max_length=32)),
            ("reasoning_policy_version", models.CharField(blank=True, default="", max_length=32)),
            ("project_slot", models.CharField(blank=True, default="", max_length=24)),
            ("gemini_request_ref", models.CharField(blank=True, default="", max_length=40)),
            ("usage_status", models.CharField(choices=[("accounting_unknown", "Accounting unknown"), ("provider_reported", "Provider reported"), ("estimated", "Estimated")], default="accounting_unknown", max_length=24)),
            ("prompt_tokens", models.PositiveBigIntegerField(default=0)),
            ("thoughts_tokens", models.PositiveBigIntegerField(default=0)),
            ("candidates_tokens", models.PositiveBigIntegerField(default=0)),
            ("total_tokens", models.PositiveBigIntegerField(default=0)),
            ("analysis_latency_ms", models.PositiveIntegerField(default=0)),
            ("result_digest", models.CharField(max_length=64)),
            ("analyzed_at", models.DateTimeField()),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("client", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="analysis_v2_results", to="management.igclient")),
            ("commercial_episode", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="analysis_v2_results", to="management.igcommercialepisode")),
            ("legacy_snapshot", models.OneToOneField(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="analysis_v2_result", to="management.igconversationanalysissnapshot")),
        ],
        options={
            "ordering": ["-id"],
            "indexes": [
                models.Index(fields=["client", "-created_at"], name="ig_anres_client_created"),
                models.Index(fields=["commercial_episode", "line_id", "-id"], name="ig_anres_episode_line"),
                models.Index(fields=["materiality_event_highwater", "-id"], name="ig_anres_materiality"),
                models.Index(fields=["purchase_probability", "-id"], name="ig_anres_probability"),
            ],
            "constraints": [
                models.UniqueConstraint(fields=("client", "job_revision", "materiality_event_highwater", "result_schema_version"), name="ig_anres_cursor_version_uniq"),
                models.CheckConstraint(condition=models.Q(("purchase_probability__isnull", True), models.Q(("purchase_probability__gte", Decimal("0")), ("purchase_probability__lte", Decimal("1"))), _connector="OR"), name="ig_anres_probability_range"),
                models.CheckConstraint(condition=models.Q(("purchase_confidence__isnull", True), models.Q(("purchase_confidence__gte", Decimal("0")), ("purchase_confidence__lte", Decimal("1"))), _connector="OR"), name="ig_anres_confidence_range"),
                models.CheckConstraint(condition=models.Q(("active_objection_confidence__isnull", True), models.Q(("active_objection_confidence__gte", Decimal("0")), ("active_objection_confidence__lte", Decimal("1"))), _connector="OR"), name="ig_anres_objection_conf_range"),
                models.CheckConstraint(condition=models.Q(("repeat_intent_confidence__isnull", True), models.Q(("repeat_intent_confidence__gte", Decimal("0")), ("repeat_intent_confidence__lte", Decimal("1"))), _connector="OR"), name="ig_anres_repeat_conf_range"),
                models.CheckConstraint(condition=models.Q(("materiality_event_highwater__gt", 0)), name="ig_anres_materiality_positive"),
            ],
        },
    ),
    migrations.CreateModel(
        name="IgAnalysisProposal",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("proposal_key", models.CharField(max_length=160, unique=True)),
            ("ordinal", models.PositiveSmallIntegerField()),
            ("line_id", models.CharField(blank=True, default="", max_length=96)),
            ("proposal_type", models.CharField(choices=[("close_node", "Close funnel node"), ("invalidate_node", "Invalidate funnel node"), ("open_subfunnel", "Open sub-funnel"), ("switch_active_line", "Switch active line"), ("start_repeat_episode", "Start repeat episode"), ("record_objection", "Record objection"), ("record_deferred_intent", "Record deferred intent"), ("update_probability", "Update probability"), ("request_clarification", "Request clarification")], max_length=32)),
            ("target_scope", models.CharField(choices=[("client", "Client"), ("episode", "Episode"), ("line", "Line"), ("funnel_node", "Funnel node"), ("subfunnel", "Sub-funnel")], max_length=24)),
            ("target_definition_key", models.CharField(blank=True, default="", max_length=96)),
            ("target_definition_version", models.CharField(blank=True, default="", max_length=32)),
            ("target_key", models.CharField(blank=True, default="", max_length=96)),
            ("typed_value", models.JSONField(blank=True, default=dict)),
            ("evidence_message_ids", models.JSONField(blank=True, default=list)),
            ("confidence", models.DecimalField(decimal_places=4, max_digits=5)),
            ("source_result_digest", models.CharField(max_length=64)),
            ("expected_materiality_digest", models.CharField(max_length=64)),
            ("expected_authority_digest", models.CharField(blank=True, default="", max_length=64)),
            ("expected_state_correlation", models.CharField(max_length=64)),
            ("status", models.CharField(choices=[("pending", "Pending validation"), ("shadow_validated", "Validated in shadow"), ("blocked_dependency", "Blocked by dependency"), ("blocked_legacy_owner", "Blocked by legacy owner"), ("rejected", "Rejected"), ("applied", "Applied")], db_index=True, default="pending", max_length=24)),
            ("decision_code", models.CharField(blank=True, default="", max_length=64)),
            ("projector_version", models.CharField(blank=True, default="", max_length=32)),
            ("decided_at", models.DateTimeField(blank=True, null=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("analysis_result", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="proposals", to="management.igconversationanalysisresult")),
            ("client", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="analysis_v2_proposals", to="management.igclient")),
            ("commercial_episode", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="analysis_v2_proposals", to="management.igcommercialepisode")),
        ],
        options={
            "ordering": ["id"],
            "indexes": [
                models.Index(fields=["status", "id"], name="ig_anprop_status_id"),
                models.Index(fields=["client", "status", "id"], name="ig_anprop_client_status"),
                models.Index(fields=["commercial_episode", "line_id", "status", "id"], name="ig_anprop_episode_line"),
                models.Index(fields=["proposal_type", "status", "id"], name="ig_anprop_type_status"),
            ],
            "constraints": [
                models.UniqueConstraint(fields=("analysis_result", "ordinal"), name="ig_anprop_result_ordinal_uniq"),
                models.CheckConstraint(condition=models.Q(("confidence__gte", Decimal("0")), ("confidence__lte", Decimal("1"))), name="ig_anprop_confidence_range"),
                models.CheckConstraint(condition=models.Q(("status__in", ["pending", "shadow_validated", "blocked_dependency", "blocked_legacy_owner", "rejected", "applied"])), name="ig_anprop_status_valid"),
            ],
        },
    ),
]


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("management", "0182_analysis_materiality_ledger")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=STATE_OPERATIONS,
        ),
        migrations.RunPython(ensure_analysis_v2_schema, reverse_code=None),
        migrations.RunPython(create_result_append_only_triggers, reverse_code=None),
    ]
