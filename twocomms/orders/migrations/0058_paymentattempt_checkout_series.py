import re

from django.db import migrations, models

from management.migration_operations import (
    IdempotentAddConstraint,
    IdempotentAddField,
    IdempotentAddIndex,
)


TABLE = "orders_paymentattempt"
FIELD_EXPECTATIONS = {
    "checkout_series_key": ({"CharField"}, True, 64, None),
    "checkout_generation": (
        {"PositiveIntegerField", "IntegerField"},
        True,
        None,
        None,
    ),
    # MariaDB/MySQL introspection may expose TINYINT(1) as IntegerField.
    "checkout_winner_claimed": (
        {"BooleanField", "IntegerField"},
        False,
        1,
        0,
    ),
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
_EXPECTED_CHECK_CLAUSES = {
    "mysql": (
        """checkout_generation is null and checkout_series_key is null
        and checkout_winner_claimed = 0x00 or checkout_generation >= 1
        and checkout_generation is not null and checkout_series_key is not null
        and (checkout_series_key <> '' or checkout_series_key is null)""",
    ),
    "sqlite": (
        """((checkout_generation is null and checkout_series_key is null
        and checkout_winner_claimed = 0) or (checkout_generation >= 1
        and checkout_generation is not null and checkout_series_key is not null
        and not (checkout_series_key = '' and checkout_series_key is not null)))""",
    ),
}
_CHECK_TRUTH_TABLE = (
    (None, None, 0, True),
    ("a" * 64, 1, 0, True),
    ("b" * 64, 1, 1, True),
    ("c" * 64, 2, 0, True),
    ("d" * 64, 99, 1, True),
    (None, None, 1, False),
    (None, 1, 0, False),
    (None, 1, 1, False),
    ("e" * 64, None, 0, False),
    ("f" * 64, None, 1, False),
    ("", 1, 0, False),
    ("", 1, 1, False),
    ("g" * 64, 0, 0, False),
    ("h" * 64, 0, 1, False),
)


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


def _normalized_default(value):
    if value is None:
        return None
    text = str(value).strip()
    while len(text) >= 2 and text[0] == "(" and text[-1] == ")":
        text = text[1:-1].strip()
    if text.casefold() in {"null", "none"}:
        return None
    if text in {"''", '""'}:
        return ""
    try:
        return int(text)
    except ValueError:
        return text.strip("'\"")


def _validate_field(schema_editor, name, column):
    allowed_types, nullable, expected_size, expected_default = FIELD_EXPECTATIONS[name]
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
    actual_default = _normalized_default(getattr(column, "default", None))
    if actual_default != expected_default:
        raise RuntimeError(
            f"{TABLE}.{name} has default {actual_default!r}; "
            f"expected {expected_default!r}"
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


def _strip_outer_parentheses(value):
    value = str(value or "").strip()
    while value.startswith("(") and value.endswith(")"):
        depth = 0
        closes_at_end = True
        for index, character in enumerate(value):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0 and index != len(value) - 1:
                    closes_at_end = False
                    break
        if not closes_at_end or depth != 0:
            break
        value = value[1:-1].strip()
    return value


def _normalize_check_clause(value):
    value = _strip_outer_parentheses(value)
    value = value.replace("`", "").replace('"', "").casefold()
    value = value.replace("0x00", "0")
    return re.sub(r"\s+", "", value)


def _sqlite_check_clause(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=%s",
            [TABLE],
        )
        row = cursor.fetchone()
    create_sql = str(row[0] if row else "")
    match = re.search(
        rf"CONSTRAINT\s+['\"`]?{re.escape(CHECK_NAME)}['\"`]?\s+CHECK\s*\(",
        create_sql,
        re.IGNORECASE,
    )
    if match is None:
        return ""
    start = match.end() - 1
    depth = 0
    quote = ""
    for index in range(start, len(create_sql)):
        character = create_sql[index]
        if quote:
            if character == quote:
                if index + 1 < len(create_sql) and create_sql[index + 1] == quote:
                    continue
                quote = ""
            continue
        if character in {"'", '"'}:
            quote = character
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return create_sql[start + 1:index]
    return ""


def _physical_check_clause(schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "mysql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT cc.CHECK_CLAUSE "
                "FROM information_schema.CHECK_CONSTRAINTS cc "
                "JOIN information_schema.TABLE_CONSTRAINTS tc ON "
                "tc.CONSTRAINT_SCHEMA=cc.CONSTRAINT_SCHEMA AND "
                "tc.CONSTRAINT_NAME=cc.CONSTRAINT_NAME "
                "WHERE tc.TABLE_SCHEMA=DATABASE() AND tc.TABLE_NAME=%s AND "
                "tc.CONSTRAINT_NAME=%s AND tc.CONSTRAINT_TYPE='CHECK'",
                [TABLE, CHECK_NAME],
            )
            rows = cursor.fetchall()
        if len(rows) != 1:
            return ""
        return str(rows[0][0] or "")
    if vendor == "sqlite":
        return _sqlite_check_clause(schema_editor)
    raise RuntimeError(
        f"{TABLE}.{CHECK_NAME} predicate validation unsupported for {vendor}"
    )


def _validate_check_truth_table(schema_editor, clause):
    quote = schema_editor.quote_name
    expression = str(clause or "")
    if not expression:
        raise RuntimeError(f"{TABLE}.{CHECK_NAME} physical predicate is missing")
    for series_key, generation, winner, expected in _CHECK_TRUTH_TABLE:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT CASE WHEN ({expression}) THEN 1 ELSE 0 END FROM ("
                f"SELECT %s AS {quote('checkout_series_key')}, "
                f"%s AS {quote('checkout_generation')}, "
                f"%s AS {quote('checkout_winner_claimed')}) candidate",
                [series_key, generation, winner],
            )
            actual = bool(cursor.fetchone()[0])
        if actual != expected:
            raise RuntimeError(
                f"{TABLE}.{CHECK_NAME} rejects the required truth table"
            )


def _validate_check(schema_editor, actual):
    actual_columns = set(actual.get("columns") or ())
    if not bool(actual.get("check")) or (
        actual_columns and actual_columns != CHECK_COLUMNS
    ):
        raise RuntimeError(f"{TABLE}.{CHECK_NAME} has incompatible check shape")
    clause = _physical_check_clause(schema_editor)
    normalized = _normalize_check_clause(clause)
    expected = {
        _normalize_check_clause(value)
        for value in _EXPECTED_CHECK_CLAUSES.get(
            schema_editor.connection.vendor,
            (),
        )
    }
    if normalized not in expected:
        raise RuntimeError(
            f"{TABLE}.{CHECK_NAME} has incompatible normalized predicate"
        )
    _validate_check_truth_table(schema_editor, clause)


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
        _validate_check(schema_editor, check)

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
            field=models.BooleanField(db_default=False, default=False),
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
