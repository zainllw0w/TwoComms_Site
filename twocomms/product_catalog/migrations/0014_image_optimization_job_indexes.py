from django.db import migrations, models


def _table_names(schema_editor):
    return set(schema_editor.connection.introspection.table_names())


def _columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor,
            table_name,
        )
    return {column.name: column for column in description}


def _constraints(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return schema_editor.connection.introspection.get_constraints(cursor, table_name)


def _validate_mysql_engine(schema_editor, table_name):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            [table_name],
        )
        row = cursor.fetchone()
    if not row or str(row[0]).upper() != "INNODB":
        raise RuntimeError(f"{table_name} must use InnoDB before recovery")


def _validate_existing_field(schema_editor, table_name, field, column):
    if not hasattr(column, "type_code"):
        return
    actual_type = schema_editor.connection.introspection.get_field_type(
        column.type_code,
        column,
    )
    expected_type = field.get_internal_type()
    compatible = {
        "BigAutoField": {"BigAutoField", "BigIntegerField"},
        "PositiveBigIntegerField": {"PositiveBigIntegerField", "BigIntegerField"},
        "CharField": {"CharField"},
    }.get(expected_type, {expected_type})
    # SQLite reports every INTEGER PRIMARY KEY as AutoField even when the
    # migration state is BigAutoField.  Keep the strict MySQL check while
    # allowing the equivalent local test representation.
    if expected_type == "BigAutoField" and schema_editor.connection.vendor == "sqlite":
        compatible.add("AutoField")
    if actual_type not in compatible:
        raise RuntimeError(
            f"{table_name}.{field.column} has type {actual_type}, expected {expected_type}"
        )
    if bool(column.null_ok) != bool(field.null):
        raise RuntimeError(f"{table_name}.{field.column} has incompatible nullability")
    expected_size = getattr(field, "max_length", None)
    actual_size = getattr(column, "internal_size", None)
    if expected_size and actual_size not in (None, expected_size):
        raise RuntimeError(f"{table_name}.{field.column} has incompatible length")


def _expected_index_columns(model, index):
    return tuple(
        model._meta.get_field(field_name.lstrip("-")).column
        for field_name in index.fields
    )


def ensure_image_job_indexes(apps, schema_editor):
    """Apply lease/index additions even when the original job table pre-dates 0014."""

    model = apps.get_model("product_catalog", "ImageOptimizationJob")
    table_name = model._meta.db_table
    if table_name not in _table_names(schema_editor):
        schema_editor.create_model(model)
        return

    _validate_mysql_engine(schema_editor, table_name)
    existing_columns = _columns(schema_editor, table_name)
    for field in model._meta.local_fields:
        if field.column in existing_columns:
            _validate_existing_field(schema_editor, table_name, field, existing_columns[field.column])
            continue
        schema_editor.add_field(model, field)
        existing_columns[field.column] = None

    constraints = _constraints(schema_editor, table_name)
    for index in model._meta.indexes:
        expected_columns = _expected_index_columns(model, index)
        existing = constraints.get(index.name)
        if existing:
            actual_columns = tuple(existing.get("columns") or ())
            if actual_columns != expected_columns:
                raise RuntimeError(
                    f"{index.name} has columns {actual_columns}, expected {expected_columns}"
                )
            continue
        schema_editor.add_index(model, index)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("product_catalog", "0013_image_optimization_job"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    ensure_image_job_indexes,
                    reverse_code=migrations.RunPython.noop,
                )
            ],
            state_operations=[
                migrations.AddField(
                    model_name="imageoptimizationjob",
                    name="lease_token",
                    field=models.CharField(blank=True, default="", max_length=32),
                ),
                migrations.AddIndex(
                    model_name="imageoptimizationjob",
                    index=models.Index(
                        fields=["status", "-updated_at"],
                        name="pc_job_status_upd_9f3d_idx",
                    ),
                ),
                migrations.AddIndex(
                    model_name="imageoptimizationjob",
                    index=models.Index(
                        fields=["status", "created_at"],
                        name="pc_job_status_crt_9f3d_idx",
                    ),
                ),
            ],
        ),
    ]
