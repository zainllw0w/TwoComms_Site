from django.db import migrations


INDEX_NAMES = (
    "pc_job_status_upd_9f3d_idx",
    "pc_job_status_crt_9f3d_idx",
)


def _columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor,
            table_name,
        )
    return {column.name: column for column in description}


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


def _validate_lease_field(schema_editor, table_name, field, column):
    if not hasattr(column, "type_code"):
        return
    actual_type = schema_editor.connection.introspection.get_field_type(
        column.type_code,
        column,
    )
    if actual_type != "CharField":
        raise RuntimeError(
            f"{table_name}.{field.column} has type {actual_type}, expected CharField"
        )
    if bool(column.null_ok) != bool(field.null):
        raise RuntimeError(f"{table_name}.{field.column} has incompatible nullability")
    actual_size = getattr(column, "internal_size", None)
    if actual_size not in (None, field.max_length):
        raise RuntimeError(f"{table_name}.{field.column} has incompatible length")


def _index_columns(model, index):
    return tuple(
        model._meta.get_field(field_name.lstrip("-")).column
        for field_name in index.fields
    )


def ensure_image_job_runtime_schema(apps, schema_editor):
    """Materialize lease/index state that an earlier recovery migration could miss."""

    model = apps.get_model("product_catalog", "ImageOptimizationJob")
    table_name = model._meta.db_table
    tables = set(schema_editor.connection.introspection.table_names())
    if table_name not in tables:
        schema_editor.create_model(model)
        return

    _validate_mysql_engine(schema_editor, table_name)
    columns = _columns(schema_editor, table_name)
    lease_field = model._meta.get_field("lease_token")
    if lease_field.column in columns:
        _validate_lease_field(
            schema_editor,
            table_name,
            lease_field,
            columns[lease_field.column],
        )
    else:
        schema_editor.add_field(model, lease_field)

    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor,
            table_name,
        )
    indexes = {index.name: index for index in model._meta.indexes}
    for name in INDEX_NAMES:
        index = indexes[name]
        expected_columns = _index_columns(model, index)
        existing = constraints.get(name)
        if existing:
            actual_columns = tuple(existing.get("columns") or ())
            if actual_columns != expected_columns:
                raise RuntimeError(
                    f"{name} has columns {actual_columns}, expected {expected_columns}"
                )
            continue
        schema_editor.add_index(model, index)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("product_catalog", "0014_image_optimization_job_indexes"),
    ]

    operations = [
        migrations.RunPython(
            ensure_image_job_runtime_schema,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
