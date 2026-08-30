import django.db.models.deletion
from django.db import migrations, models

from management.migrations._resumable_schema import ensure_additive_schema


EVENT_TABLE = "management_iganalysismaterialityevent"
JOB_FIELD_SPECS = tuple(
    ("management", "IgConversationAnalysisJob", name)
    for name in (
        "analyzed_materiality_digest",
        "analyzed_materiality_event_highwater",
        "artifact_digest",
        "authority_digest",
        "first_unanalysed_at",
        "last_relevant_at",
        "materiality_digest",
        "materiality_due_at",
        "materiality_episode",
        "materiality_event_highwater",
        "materiality_line_id",
    )
)
EVENT_FIELD_SPECS = tuple(
    ("management", "IgAnalysisMaterialityEvent", name)
    for name in (
        "id", "line_id", "source_role", "event_kind", "event_key",
        "event_digest", "authority_digest", "artifact_revision",
        "artifact_digest", "relevant_at", "created_at", "client",
        "customer_turn", "episode", "source_message",
    )
)
FIELD_SPECS = JOB_FIELD_SPECS + EVENT_FIELD_SPECS
JOB_INDEX_SPECS = (
    ("management", "IgConversationAnalysisJob", "ig_analysis_mat_due"),
)
EVENT_INDEX_SPECS = (
    ("management", "IgAnalysisMaterialityEvent", "ig_mat_client_id"),
    ("management", "IgAnalysisMaterialityEvent", "ig_mat_episode_id"),
    ("management", "IgAnalysisMaterialityEvent", "ig_mat_kind_id"),
    ("management", "IgAnalysisMaterialityEvent", "ig_mat_relevant"),
)
INDEX_SPECS = JOB_INDEX_SPECS + EVENT_INDEX_SPECS
CONSTRAINT_SPECS = ()


def ensure_materiality_schema(apps, schema_editor):
    introspection = schema_editor.connection.introspection
    tables = set(introspection.table_names())
    event_model = apps.get_model("management", "IgAnalysisMaterialityEvent")
    created = EVENT_TABLE not in tables
    if created:
        schema_editor.create_model(event_model)
    if schema_editor.connection.vendor == "mysql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                [EVENT_TABLE],
            )
            row = cursor.fetchone()
        if not row:
            raise RuntimeError(f"required materiality table missing: {EVENT_TABLE}")
        if str(row[0] or "").upper() != "INNODB":
            schema_editor.execute(
                f"ALTER TABLE {schema_editor.quote_name(EVENT_TABLE)} ENGINE=InnoDB"
            )
    ensure_additive_schema(
        apps,
        schema_editor,
        field_specs=(JOB_FIELD_SPECS if created else FIELD_SPECS),
        index_specs=(JOB_INDEX_SPECS if created else INDEX_SPECS),
        constraint_specs=CONSTRAINT_SPECS,
    )


def create_append_only_triggers(apps, schema_editor):
    del apps
    update_name = "ig_mat_no_update"
    delete_name = "ig_mat_no_delete"
    if schema_editor.connection.vendor == "mysql":
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {update_name}")
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {delete_name}")
        schema_editor.execute(
            f"CREATE TRIGGER {update_name} BEFORE UPDATE ON {EVENT_TABLE} "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' "
            "SET MESSAGE_TEXT='IgAnalysisMaterialityEvent is append-only'"
        )
        schema_editor.execute(
            f"CREATE TRIGGER {delete_name} BEFORE DELETE ON {EVENT_TABLE} "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' "
            "SET MESSAGE_TEXT='IgAnalysisMaterialityEvent is append-only'"
        )
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {update_name}")
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {delete_name}")
        schema_editor.execute(
            f"CREATE TRIGGER {update_name} BEFORE UPDATE ON {EVENT_TABLE} "
            "BEGIN SELECT RAISE(ABORT, 'IgAnalysisMaterialityEvent is append-only'); END"
        )
        schema_editor.execute(
            f"CREATE TRIGGER {delete_name} BEFORE DELETE ON {EVENT_TABLE} "
            "BEGIN SELECT RAISE(ABORT, 'IgAnalysisMaterialityEvent is append-only'); END"
        )
    elif schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "CREATE OR REPLACE FUNCTION ig_materiality_append_only_raise() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'IgAnalysisMaterialityEvent is append-only'; END; $$"
        )
        schema_editor.execute(
            f"DROP TRIGGER IF EXISTS {update_name} ON {EVENT_TABLE}"
        )
        schema_editor.execute(
            f"DROP TRIGGER IF EXISTS {delete_name} ON {EVENT_TABLE}"
        )
        schema_editor.execute(
            f"CREATE TRIGGER {update_name} BEFORE UPDATE ON {EVENT_TABLE} "
            "FOR EACH ROW EXECUTE FUNCTION ig_materiality_append_only_raise()"
        )
        schema_editor.execute(
            f"CREATE TRIGGER {delete_name} BEFORE DELETE ON {EVENT_TABLE} "
            "FOR EACH ROW EXECUTE FUNCTION ig_materiality_append_only_raise()"
        )


STATE_OPERATIONS = [
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="analyzed_materiality_digest",
        field=models.CharField(blank=True, default="", max_length=64),
    ),
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="analyzed_materiality_event_highwater",
        field=models.PositiveBigIntegerField(default=0),
    ),
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="artifact_digest",
        field=models.CharField(blank=True, default="", max_length=64),
    ),
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="authority_digest",
        field=models.CharField(blank=True, default="", max_length=64),
    ),
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="first_unanalysed_at",
        field=models.DateTimeField(blank=True, null=True),
    ),
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="last_relevant_at",
        field=models.DateTimeField(blank=True, null=True),
    ),
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="materiality_digest",
        field=models.CharField(blank=True, default="", max_length=64),
    ),
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="materiality_due_at",
        field=models.DateTimeField(blank=True, null=True),
    ),
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="materiality_episode",
        field=models.ForeignKey(
            blank=True,
            db_constraint=False,
            null=True,
            on_delete=django.db.models.deletion.DO_NOTHING,
            related_name="analysis_materiality_jobs",
            to="management.igcommercialepisode",
        ),
    ),
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="materiality_event_highwater",
        field=models.PositiveBigIntegerField(default=0),
    ),
    migrations.AddField(
        model_name="igconversationanalysisjob",
        name="materiality_line_id",
        field=models.CharField(blank=True, default="", max_length=96),
    ),
    migrations.CreateModel(
        name="IgAnalysisMaterialityEvent",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("line_id", models.CharField(blank=True, default="", max_length=96)),
            ("source_role", models.CharField(choices=[("user", "Клієнт"), ("manager", "Менеджер"), ("authority", "Авторитетний backend"), ("system", "Система")], max_length=16)),
            ("event_kind", models.CharField(choices=[("customer_turn", "Завершений хід клієнта"), ("payment_truth", "Зміна істини оплати"), ("order_truth", "Зміна істини замовлення"), ("manager_boundary", "Межа менеджера"), ("product_line", "Зміна товарної лінії"), ("deferred_intent", "Відкладений намір"), ("media_artifact", "Новий media artifact")], max_length=32)),
            ("event_key", models.CharField(max_length=160, unique=True)),
            ("event_digest", models.CharField(max_length=64)),
            ("authority_digest", models.CharField(blank=True, default="", max_length=64)),
            ("artifact_revision", models.PositiveBigIntegerField(default=0)),
            ("artifact_digest", models.CharField(blank=True, default="", max_length=64)),
            ("relevant_at", models.DateTimeField()),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("client", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="analysis_materiality_events", to="management.igclient")),
            ("customer_turn", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="analysis_materiality_events", to="management.igcustomerturn")),
            ("episode", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="analysis_materiality_events", to="management.igcommercialepisode")),
            ("source_message", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="analysis_materiality_events", to="management.instagrambotmessage")),
        ],
        options={
            "ordering": ["id"],
            "indexes": [
                models.Index(fields=["client", "-id"], name="ig_mat_client_id"),
                models.Index(fields=["episode", "-id"], name="ig_mat_episode_id"),
                models.Index(fields=["event_kind", "-id"], name="ig_mat_kind_id"),
                models.Index(fields=["relevant_at", "id"], name="ig_mat_relevant"),
            ],
        },
    ),
    migrations.AddIndex(
        model_name="igconversationanalysisjob",
        index=models.Index(fields=["materiality_due_at", "id"], name="ig_analysis_mat_due"),
    ),
]


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("management", "0181_gemini_accounting_v2_innodb")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=STATE_OPERATIONS,
        ),
        migrations.RunPython(ensure_materiality_schema),
        migrations.RunPython(create_append_only_triggers),
    ]
