from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError


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
EXPECTED_COLUMNS = {
    "provider_recheck_state": ("CharField", False, 16, ""),
    "provider_recheck_next_at": ("DateTimeField", True, None, None),
    "provider_recheck_until": ("DateTimeField", True, None, None),
    "provider_recheck_claim_token": ("CharField", False, 64, ""),
    "provider_recheck_claim_until": ("DateTimeField", True, None, None),
    "provider_recheck_attempts": (
        ("PositiveSmallIntegerField", "SmallIntegerField"),
        False,
        None,
        0,
    ),
    "provider_recheck_last_status": ("CharField", False, 32, ""),
}


def _normalized_default(value):
    if value is None:
        return None
    text = str(value).strip()
    while len(text) >= 2 and text[0] == "(" and text[-1] == ")":
        text = text[1:-1].strip()
    if text in {"''", '""'}:
        return ""
    try:
        return int(text)
    except ValueError:
        return text.strip("'\"")


def _validate_column(connection, column):
    expected_type, expected_null, expected_size, expected_default = EXPECTED_COLUMNS[
        column.name
    ]
    actual_type = connection.introspection.get_field_type(column.type_code, column)
    allowed_types = (
        set(expected_type) if isinstance(expected_type, tuple) else {expected_type}
    )
    if actual_type not in allowed_types:
        raise RuntimeError(
            f"{TABLE}.{column.name} has incompatible type {actual_type}; "
            f"expected {sorted(allowed_types)}"
        )
    if bool(column.null_ok) != expected_null:
        raise RuntimeError(
            f"{TABLE}.{column.name} has incompatible nullability"
        )
    actual_size = getattr(column, "internal_size", None)
    if expected_size is not None and int(actual_size or 0) != expected_size:
        raise RuntimeError(
            f"{TABLE}.{column.name} has incompatible size {actual_size}"
        )
    if _normalized_default(getattr(column, "default", None)) != expected_default:
        raise RuntimeError(
            f"{TABLE}.{column.name} has incompatible default"
        )


def _validate_index(name, constraint):
    expected_columns = list(INDEXES[name])
    if (
        list(constraint.get("columns") or []) != expected_columns
        or bool(constraint.get("unique"))
        or not bool(constraint.get("index"))
    ):
        raise RuntimeError(f"{TABLE}.{name} has incompatible index definition")


def ensure_provider_recheck_schema(apps, schema_editor):
    """Resume safely after any partially committed MariaDB ALTER."""

    vendor = schema_editor.connection.vendor
    dialect = "mysql" if vendor in {"mysql", "mariadb"} else "sqlite"
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        descriptions = schema_editor.connection.introspection.get_table_description(
            cursor,
            TABLE,
        )
    columns = {column.name: column for column in descriptions}
    for column_name, definitions in COLUMNS.items():
        if column_name in columns:
            _validate_column(schema_editor.connection, columns[column_name])
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
            _validate_index(index_name, constraints[index_name])
            continue
        columns_sql = ", ".join(quote(field) for field in fields)
        schema_editor.execute(
            f"CREATE INDEX {quote(index_name)} ON {quote(TABLE)} ({columns_sql})"
        )


def refuse_reverse(apps, schema_editor):
    raise IrreversibleError(
        "orders.0057 preserves provider reconciliation evidence and is irreversible"
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
                    refuse_reverse,
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
