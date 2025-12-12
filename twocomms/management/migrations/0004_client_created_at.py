from django.db import migrations, models
from django.utils import timezone


def set_created(apps, schema_editor):
    Client = apps.get_model('management', 'Client')
    now = timezone.now()
    Client.objects.filter(created_at__isnull=True).update(created_at=now, updated_at=now)

def add_columns_if_missing(apps, schema_editor):
    """Add columns in a DB-compatible way (SQLite/MySQL/Postgres)."""
    table = 'management_client'
    with schema_editor.connection.cursor() as cursor:
        existing = {c.name for c in schema_editor.connection.introspection.get_table_description(cursor, table)}

    statements = []
    if 'created_at' not in existing:
        statements.append(f"ALTER TABLE {table} ADD COLUMN created_at datetime(6) NULL;")
    if 'updated_at' not in existing:
        statements.append(f"ALTER TABLE {table} ADD COLUMN updated_at datetime(6) NULL;")

    for sql in statements:
        schema_editor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0003_report'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_columns_if_missing, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='client',
                    name='created_at',
                    field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
                ),
                migrations.AddField(
                    model_name='client',
                    name='updated_at',
                    field=models.DateTimeField(auto_now=True, null=True, blank=True),
                ),
            ],
        ),
        migrations.RunPython(set_created, migrations.RunPython.noop),
    ]
