from django.db import migrations, models

from management.migration_operations import (
    IdempotentAddConstraint,
    IdempotentAddField,
    IdempotentAddIndex,
)


TABLE = "orders_paymentattempt"
FIELD_EXPECTATIONS = {
    "checkout_series_key": ({"CharField"}, True, 64),
    "checkout_generation": (
        {"PositiveIntegerField", "IntegerField"},
        True,
        None,
    ),
    "checkout_winner_claimed": ({"BooleanField"}, False, None),
}
INDEX_EXPECTATIONS = {
    "pay_attempt_series_idx": (
        "checkout_series_key",
        "checkout_generation",
        "id",
    ),
    "pay_attempt_winner_idx": (
        "checkout_series_key",
        "checkout_winner_claimed",
        "id",
    ),
}
UNIQUE_NAME = "pay_attempt_series_gen_once"
UNIQUE_COLUMNS = ("checkout_series_key", "checkout_generation")
CHECK_NAME = "pay_attempt_series_shape"
CHECK_COLUMNS = {
    "checkout_series_key",
    "checkout_generation",
    "checkout_winner_claimed",
}


def _description(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        rows = schema_editor.connection.introspection.get_table_description(
            cursor,
            TABLE,
        )
    return {row.name: row for row in rows}


def _constraints(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        return schema_editor.connection.introspection.get_constraints(
            cursor,
            TABLE,
        )


def _validate_engine(schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            [TABLE],
        )
        row = cursor.fetchone()
    if not row or str(row[0] or "").upper() != "INNODB":
        raise RuntimeError(f"{TABLE} must use InnoDB")


def _validate_field(schema_editor, name, column):
    allowed_types, nullable, expected_size = FIELD_EXPECTATIONS[name]
    actual_type = schema_editor.connection.introspection.get_field_type(
        column.type_code,
        column,
    )
    if actual_type not in allowed_types:
        raise RuntimeError(
            f"{TABLE}.{name} has type {actual_type}; "
            f"expected {sorted(allowed_types)}"
        )
    if bool(column.null_ok) != nullable:
        raise RuntimeError(f"{TABLE}.{name} has incompatible nullability")
    actual_size = getattr(column, "internal_size", None)
    if expected_size is not None and actual_size not in (None, expected_size):
        raise RuntimeError(
            f"{TABLE}.{name} has length {actual_size}; expected {expected_size}"
        )


def _validate_index(name, actual):
    if (
        tuple(actual.get("columns") or ()) != INDEX_EXPECTATIONS[name]
        or bool(actual.get("unique"))
        or ("index" in actual and not bool(actual.get("index")))
        or actual.get("check")
        or actual.get("foreign_key")
    ):
        raise RuntimeError(f"{TABLE}.{name} has incompatible index shape")


def _validate_unique(actual):
    if (
        tuple(actual.get("columns") or ()) != UNIQUE_COLUMNS
        or not bool(actual.get("unique"))
        or actual.get("check")
        or actual.get("foreign_key")
    ):
        raise RuntimeError(f"{TABLE}.{UNIQUE_NAME} has incompatible unique shape")


def _validate_check(actual):
    actual_columns = set(actual.get("columns") or ())
    if not bool(actual.get("check")) or (
        actual_columns and actual_columns != CHECK_COLUMNS
    ):
        raise RuntimeError(f"{TABLE}.{CHECK_NAME} has incompatible check shape")


def _validate_rows(schema_editor):
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {quote(TABLE)} WHERE "
            f"({quote('checkout_series_key')} IS NULL AND ("
            f"{quote('checkout_generation')} IS NOT NULL OR "
            f"{quote('checkout_winner_claimed')} <> 0)) OR "
            f"({quote('checkout_series_key')} IS NOT NULL AND ("
            f"{quote('checkout_series_key')} = '' OR "
            f"{quote('checkout_generation')} IS NULL OR "
            f"{quote('checkout_generation')} < 1))"
        )
        invalid_count = int(cursor.fetchone()[0])
    if invalid_count:
        raise RuntimeError(
            f"{TABLE} contains {invalid_count} incompatible checkout-series rows"
        )


def _validate_schema(schema_editor, *, require_complete):
    _validate_engine(schema_editor)
    columns = _description(schema_editor)
    for name in FIELD_EXPECTATIONS:
        column = columns.get(name)
        if column is None:
            if require_complete:
                raise RuntimeError(f"{TABLE}.{name} is missing")
            continue
        _validate_field(schema_editor, name, column)

    constraints = _constraints(schema_editor)
    for name in INDEX_EXPECTATIONS:
        actual = constraints.get(name)
        if actual is None:
            if require_complete:
                raise RuntimeError(f"{TABLE}.{name} is missing")
            continue
        _validate_index(name, actual)
    unique = constraints.get(UNIQUE_NAME)
    if unique is None:
        if require_complete:
            raise RuntimeError(f"{TABLE}.{UNIQUE_NAME} is missing")
    else:
        _validate_unique(unique)
    check = constraints.get(CHECK_NAME)
    if check is None:
        if require_complete:
            raise RuntimeError(f"{TABLE}.{CHECK_NAME} is missing")
    else:
        _validate_check(check)

    if set(FIELD_EXPECTATIONS).issubset(columns):
        _validate_rows(schema_editor)


def validate_partial_schema(apps, schema_editor):
    del apps
    _validate_schema(schema_editor, require_complete=False)


def validate_complete_schema(apps, schema_editor):
    del apps
    _validate_schema(schema_editor, require_complete=True)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("orders", "0057_paymentattempt_provider_recheck"),
    ]

    operations = [
        migrations.RunPython(
            validate_partial_schema,
            migrations.RunPython.noop,
        ),
        IdempotentAddField(
            model_name="paymentattempt",
            name="checkout_series_key",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        IdempotentAddField(
            model_name="paymentattempt",
            name="checkout_generation",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        IdempotentAddField(
            model_name="paymentattempt",
            name="checkout_winner_claimed",
            field=models.BooleanField(default=False),
        ),
        IdempotentAddIndex(
            model_name="paymentattempt",
            index=models.Index(
                fields=["checkout_series_key", "checkout_generation", "id"],
                name="pay_attempt_series_idx",
            ),
        ),
        IdempotentAddIndex(
            model_name="paymentattempt",
            index=models.Index(
                fields=["checkout_series_key", "checkout_winner_claimed", "id"],
                name="pay_attempt_winner_idx",
            ),
        ),
        IdempotentAddConstraint(
            model_name="paymentattempt",
            constraint=models.UniqueConstraint(
                fields=("checkout_series_key", "checkout_generation"),
                name=UNIQUE_NAME,
            ),
        ),
        IdempotentAddConstraint(
            model_name="paymentattempt",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        checkout_series_key__isnull=True,
                        checkout_generation__isnull=True,
                        checkout_winner_claimed=False,
                    )
                    | (
                        models.Q(
                            checkout_series_key__isnull=False,
                            checkout_generation__isnull=False,
                            checkout_generation__gte=1,
                        )
                        & ~models.Q(checkout_series_key="")
                    )
                ),
                name=CHECK_NAME,
            ),
        ),
        migrations.RunPython(validate_complete_schema),
    ]
