# Generated migration for adding idle_seconds field
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0035_migrate_existing_managers'),
    ]

    operations = [
        migrations.AddField(
            model_name='managementdailyactivity',
            name='idle_seconds',
            field=models.PositiveIntegerField(default=0, verbose_name='Відкритий але неактивний час (сек)'),
        ),
    ]
