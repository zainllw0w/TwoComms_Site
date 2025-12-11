from django.db import migrations, models
from django.utils import timezone


def set_created(apps, schema_editor):
    Client = apps.get_model('management', 'Client')
    now = timezone.now()
    Client.objects.filter(created_at__isnull=True).update(created_at=now, updated_at=now)


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0003_report'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE management_client
                    ADD COLUMN IF NOT EXISTS created_at datetime(6) NULL;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE management_client
                    ADD COLUMN IF NOT EXISTS updated_at datetime(6) NULL;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
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
