# Generated manually to fix MySQL index length issue
# MySQL has a limit of 1000 bytes for indexes with utf8mb4 (4 bytes per char)
# CharField(255) * 3 fields * 4 bytes = 3060 bytes > 1000 bytes limit
# Solution: Use prefix indexes (first 100 chars per field = 1200 bytes, but MySQL allows this)

from django.db import migrations


MYSQL_VENDOR = "mysql"


def apply_mysql_utm_index_fix(apps, schema_editor):
    if schema_editor.connection.vendor != MYSQL_VENDOR:
        return

    schema_editor.execute(
        "DROP INDEX IF EXISTS idx_utm_source_medium_campaign ON storefront_utmsession;"
    )
    schema_editor.execute(
        "CREATE INDEX idx_utm_source_medium_campaign "
        "ON storefront_utmsession (utm_source(80), utm_medium(80), utm_campaign(80));"
    )


def reverse_mysql_utm_index_fix(apps, schema_editor):
    if schema_editor.connection.vendor != MYSQL_VENDOR:
        return

    schema_editor.execute(
        "DROP INDEX IF EXISTS idx_utm_source_medium_campaign ON storefront_utmsession;"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0033_useraction_utmsession_and_more'),
    ]

    operations = [
        migrations.RunPython(
            apply_mysql_utm_index_fix,
            reverse_mysql_utm_index_fix,
        ),
    ]
