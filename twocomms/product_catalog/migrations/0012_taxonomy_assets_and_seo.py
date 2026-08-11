from django.db import migrations, models


FIELD_NAMES = (
    "icon",
    "seo_h1_uk",
    "seo_h1_ru",
    "seo_h1_en",
    "seo_keywords_uk",
    "seo_keywords_ru",
    "seo_keywords_en",
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


def _validate_existing_field(schema_editor, table_name, field, column):
    if not hasattr(column, "type_code"):
        return
    actual_type = schema_editor.connection.introspection.get_field_type(
        column.type_code,
        column,
    )
    expected_type = field.get_internal_type()
    compatible = {
        "FileField": {"CharField"},
        "ImageField": {"CharField"},
        "CharField": {"CharField"},
        "TextField": {"TextField"},
    }.get(expected_type, {expected_type})
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
    actual_default = getattr(column, "default", None)
    if getattr(field, "default", None) == "" and actual_default not in (None, ""):
        raise RuntimeError(f"{table_name}.{field.column} has incompatible default")


def ensure_taxonomy_fields(apps, schema_editor):
    """Finish a previously interrupted MySQL ADD COLUMN sequence."""

    model = apps.get_model("product_catalog", "MerchCollection")
    _validate_mysql_engine(schema_editor, model._meta.db_table)
    existing = _columns(schema_editor, model._meta.db_table)
    for name in FIELD_NAMES:
        field = model._meta.get_field(name)
        if field.column in existing:
            _validate_existing_field(
                schema_editor,
                model._meta.db_table,
                field,
                existing[field.column],
            )
            continue
        schema_editor.add_field(model, field)
        existing[field.column] = None


def remove_taxonomy_fields(apps, schema_editor):
    model = apps.get_model("product_catalog", "MerchCollection")
    existing = _columns(schema_editor, model._meta.db_table)
    for name in reversed(FIELD_NAMES):
        field = model._meta.get_field(name)
        if field.column not in existing:
            continue
        schema_editor.remove_field(model, field)
        existing.pop(field.column)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("product_catalog", "0011_refine_brigade_taxonomy"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="merchcollection",
                    name="icon",
                    field=models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="product_catalog/merch_collection_icons/",
                    ),
                ),
                migrations.AddField(
                    model_name="merchcollection",
                    name="seo_h1_uk",
                    field=models.CharField(blank=True, default="", max_length=180),
                ),
                migrations.AddField(
                    model_name="merchcollection",
                    name="seo_h1_ru",
                    field=models.CharField(blank=True, default="", max_length=180),
                ),
                migrations.AddField(
                    model_name="merchcollection",
                    name="seo_h1_en",
                    field=models.CharField(blank=True, default="", max_length=180),
                ),
                migrations.AddField(
                    model_name="merchcollection",
                    name="seo_keywords_uk",
                    field=models.TextField(blank=True, default=""),
                ),
                migrations.AddField(
                    model_name="merchcollection",
                    name="seo_keywords_ru",
                    field=models.TextField(blank=True, default=""),
                ),
                migrations.AddField(
                    model_name="merchcollection",
                    name="seo_keywords_en",
                    field=models.TextField(blank=True, default=""),
                ),
            ],
        ),
        migrations.RunPython(ensure_taxonomy_fields, remove_taxonomy_fields),
    ]
