# Generated manually to fix MySQL index length issue
# MySQL has a limit of 1000 bytes for indexes with utf8mb4 (4 bytes per char)
# CharField(255) * 3 fields * 4 bytes = 3060 bytes > 1000 bytes limit
# Solution: Use prefix indexes (first 100 chars per field = 1200 bytes, but MySQL allows this)

from django.db import migrations, models


MYSQL_VENDOR = "mysql"
INDEX_NAME = "idx_utm_source_medium_campaign"
INDEX_FIELDS = ("utm_source", "utm_medium", "utm_campaign")


def _has_index(schema_editor, model):
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor, model._meta.db_table
        )
    return INDEX_NAME in constraints


def _drop_index_if_present(apps, schema_editor):
    model = apps.get_model("storefront", "UTMSession")
    if _has_index(schema_editor, model):
        schema_editor.remove_index(
            model,
            models.Index(fields=list(INDEX_FIELDS), name=INDEX_NAME),
        )


def apply_mysql_utm_index_fix(apps, schema_editor):
    if schema_editor.connection.vendor != MYSQL_VENDOR:
        return

    _drop_index_if_present(apps, schema_editor)
    schema_editor.execute(
        "CREATE INDEX idx_utm_source_medium_campaign "
        "ON storefront_utmsession (utm_source(80), utm_medium(80), utm_campaign(80));"
    )


def reverse_mysql_utm_index_fix(apps, schema_editor):
    if schema_editor.connection.vendor != MYSQL_VENDOR:
        return

    _drop_index_if_present(apps, schema_editor)


class Migration(migrations.Migration):

    # MySQL cannot roll back the prefix-index DDL.
    atomic = False

    dependencies = [
        ('storefront', '0033_useraction_utmsession_and_more'),
    ]

    operations = [
        migrations.RunPython(
            apply_mysql_utm_index_fix,
            reverse_mysql_utm_index_fix,
        ),
    ]
