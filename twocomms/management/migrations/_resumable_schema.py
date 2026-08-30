"""Stable helpers for retry-safe non-transactional schema additions."""


def _columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor,
            table_name,
        )
    return {column.name: column for column in description}


def _constraints(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return schema_editor.connection.introspection.get_constraints(
            cursor,
            table_name,
        )


def _validate_engine(schema_editor, table_name):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            [table_name],
        )
        row = cursor.fetchone()
    if not row or str(row[0]).upper() != "INNODB":
        raise RuntimeError(f"{table_name} must use InnoDB")


def _validate_field(schema_editor, table_name, field, column):
    if not hasattr(column, "type_code"):
        return
    actual = schema_editor.connection.introspection.get_field_type(
        column.type_code,
        column,
    )
    physical_field = (
        field.target_field
        if getattr(field, "is_relation", False)
        and getattr(field, "many_to_one", False)
        else field
    )
    expected = physical_field.get_internal_type()
    compatible = {
        "BigAutoField": {"BigAutoField", "BigIntegerField"},
        "AutoField": {"AutoField", "IntegerField"},
        "PositiveBigIntegerField": {"PositiveBigIntegerField", "BigIntegerField"},
        "PositiveIntegerField": {"PositiveIntegerField", "IntegerField"},
        "PositiveSmallIntegerField": {
            "PositiveSmallIntegerField", "SmallIntegerField", "IntegerField",
        },
    }.get(expected, {expected})
    if (
        expected == "BooleanField"
        and schema_editor.connection.vendor == "mysql"
        and actual == "IntegerField"
        and getattr(column, "internal_size", None) == 1
    ):
        compatible = compatible | {"IntegerField"}
    if actual not in compatible:
        raise RuntimeError(
            f"{table_name}.{field.column} has type {actual}, expected {expected}"
        )
    if bool(column.null_ok) != bool(field.null):
        raise RuntimeError(
            f"{table_name}.{field.column} has incompatible nullability"
        )
    expected_size = getattr(field, "max_length", None)
    actual_size = getattr(column, "internal_size", None)
    if expected_size and actual_size not in (None, expected_size):
        raise RuntimeError(
            f"{table_name}.{field.column} has length {actual_size}, "
            f"expected {expected_size}"
        )


def ensure_additive_schema(
    apps,
    schema_editor,
    *,
    field_specs,
    index_specs=(),
    constraint_specs=(),
):
    """Add only missing objects and reject incompatible partial DDL."""
    tables = set(schema_editor.connection.introspection.table_names())
    by_model = {}
    validated_tables = set()
    for app_label, model_name, field_name in field_specs:
        model = by_model.setdefault(
            (app_label, model_name),
            apps.get_model(app_label, model_name),
        )
        table_name = model._meta.db_table
        if table_name not in tables:
            raise RuntimeError(f"required table is missing: {table_name}")
        if table_name not in validated_tables:
            _validate_engine(schema_editor, table_name)
            validated_tables.add(table_name)
        columns = _columns(schema_editor, table_name)
        field = model._meta.get_field(field_name)
        existing = columns.get(field.column)
        if existing is not None:
            _validate_field(schema_editor, table_name, field, existing)
            continue
        schema_editor.add_field(model, field)

    for app_label, model_name, index_name in index_specs:
        model = by_model.setdefault(
            (app_label, model_name),
            apps.get_model(app_label, model_name),
        )
        existing = _constraints(schema_editor, model._meta.db_table)
        if index_name in existing:
            actual = existing[index_name]
            expected_index = next(
                item for item in model._meta.indexes if item.name == index_name
            )
            expected_columns = tuple(
                model._meta.get_field(field_name.lstrip("-")).column
                for field_name in expected_index.fields
            )
            actual_columns = actual.get("columns")
            if actual_columns and tuple(actual_columns) != expected_columns:
                raise RuntimeError(
                    f"{index_name} has columns {tuple(actual_columns)}, "
                    f"expected {expected_columns}"
                )
            if "index" in actual and not actual.get("index"):
                raise RuntimeError(f"{index_name} exists but is not an index")
            if actual.get("check") or actual.get("foreign_key"):
                raise RuntimeError(f"{index_name} has an incompatible object type")
            if actual.get("unique"):
                raise RuntimeError(f"{index_name} is unexpectedly unique")
            continue
        index = next(item for item in model._meta.indexes if item.name == index_name)
        schema_editor.add_index(model, index)

    for app_label, model_name, constraint_name in constraint_specs:
        model = by_model.setdefault(
            (app_label, model_name),
            apps.get_model(app_label, model_name),
        )
        existing = _constraints(schema_editor, model._meta.db_table)
        if constraint_name in existing:
            actual = existing[constraint_name]
            constraint = next(
                item for item in model._meta.constraints
                if item.name == constraint_name
            )
            if "check" in actual and not actual.get("check"):
                raise RuntimeError(
                    f"{constraint_name} exists but is not a check constraint"
                )
            if (
                actual.get("index")
                or actual.get("unique")
                or actual.get("primary_key")
                or actual.get("foreign_key")
            ):
                raise RuntimeError(
                    f"{constraint_name} has an incompatible object type"
                )
            expected_fields = set()
            for child in getattr(constraint.condition, "children", ()):
                if isinstance(child, tuple) and child:
                    expected_fields.add(str(child[0]).split("__", 1)[0])
            expected_columns = {
                model._meta.get_field(field_name).column
                for field_name in expected_fields
            }
            actual_columns = set(actual.get("columns") or ())
            if actual_columns and actual_columns != expected_columns:
                raise RuntimeError(
                    f"{constraint_name} has columns {sorted(actual_columns)}, "
                    f"expected {sorted(expected_columns)}"
                )
            continue
        constraint = next(
            item for item in model._meta.constraints
            if item.name == constraint_name
        )
        schema_editor.add_constraint(model, constraint)
