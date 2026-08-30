from django.db import migrations, models


TABLE = "orders_paymentattempt"
COLUMNS = {
    "provider_recheck_state": {
        "mysql": "varchar(16) NOT NULL DEFAULT ''",
        "sqlite": "varchar(16) NOT NULL DEFAULT ''",
    },
    "provider_recheck_next_at": {
        "mysql": "datetime(6) NULL",
        "sqlite": "datetime NULL",
    },
    "provider_recheck_until": {
        "mysql": "datetime(6) NULL",
        "sqlite": "datetime NULL",
    },
    "provider_recheck_claim_token": {
        "mysql": "varchar(64) NOT NULL DEFAULT ''",
        "sqlite": "varchar(64) NOT NULL DEFAULT ''",
    },
    "provider_recheck_claim_until": {
        "mysql": "datetime(6) NULL",
        "sqlite": "datetime NULL",
    },
    "provider_recheck_attempts": {
        "mysql": "smallint unsigned NOT NULL DEFAULT 0",
        "sqlite": "smallint unsigned NOT NULL DEFAULT 0",
    },
    "provider_recheck_last_status": {
        "mysql": "varchar(32) NOT NULL DEFAULT ''",
        "sqlite": "varchar(32) NOT NULL DEFAULT ''",
    },
}
INDEXES = {
    "pay_attempt_recheck_due": (
        "provider_recheck_state",
        "provider_recheck_next_at",
        "id",
    ),
    "pay_attempt_recheck_lease": (
        "provider_recheck_claim_until",
        "id",
    ),
}


def ensure_provider_recheck_schema(apps, schema_editor):
    """Resume safely after any partially committed MariaDB ALTER."""

    vendor = schema_editor.connection.vendor
    dialect = "mysql" if vendor in {"mysql", "mariadb"} else "sqlite"
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor,
                TABLE,
            )
        }
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor,
            TABLE,
        )
    for column_name, definitions in COLUMNS.items():
        if column_name in columns:
            continue
        schema_editor.execute(
            f"ALTER TABLE {quote(TABLE)} ADD COLUMN "
            f"{quote(column_name)} {definitions[dialect]}"
        )
    # Refresh constraints after columns have been added; a prior interrupted run
    # may already have committed either index independently.
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor,
            TABLE,
        )
    for index_name, fields in INDEXES.items():
        if index_name in constraints:
            continue
        columns_sql = ", ".join(quote(field) for field in fields)
        schema_editor.execute(
            f"CREATE INDEX {quote(index_name)} ON {quote(TABLE)} ({columns_sql})"
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        # Symbolic integration boundary: if another branch adds orders.0057,
        # renumber this additive leaf and point it at the merged predecessor.
        ("orders", "0056_alter_paymentsideeffectjob_kind"),
    ]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    ensure_provider_recheck_schema,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="paymentattempt",
                    name="provider_recheck_state",
                    field=models.CharField(
                        blank=True,
                        choices=[
                            ("", "Не потрібна"),
                            ("pending", "Очікує перевірки провайдера"),
                            ("checking", "Перевіряється"),
                            ("resolved", "Підтверджено провайдером"),
                            ("exhausted", "Потрібна ручна перевірка"),
                        ],
                        default="",
                        max_length=16,
                    ),
                ),
                migrations.AddField(
                    model_name="paymentattempt",
                    name="provider_recheck_next_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="paymentattempt",
                    name="provider_recheck_until",
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="paymentattempt",
                    name="provider_recheck_claim_token",
                    field=models.CharField(blank=True, default="", max_length=64),
                ),
                migrations.AddField(
                    model_name="paymentattempt",
                    name="provider_recheck_claim_until",
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="paymentattempt",
                    name="provider_recheck_attempts",
                    field=models.PositiveSmallIntegerField(default=0),
                ),
                migrations.AddField(
                    model_name="paymentattempt",
                    name="provider_recheck_last_status",
                    field=models.CharField(blank=True, default="", max_length=32),
                ),
                migrations.AddIndex(
                    model_name="paymentattempt",
                    index=models.Index(
                        fields=[
                            "provider_recheck_state",
                            "provider_recheck_next_at",
                            "id",
                        ],
                        name="pay_attempt_recheck_due",
                    ),
                ),
                migrations.AddIndex(
                    model_name="paymentattempt",
                    index=models.Index(
                        fields=["provider_recheck_claim_until", "id"],
                        name="pay_attempt_recheck_lease",
                    ),
                ),
            ],
        ),
    ]
