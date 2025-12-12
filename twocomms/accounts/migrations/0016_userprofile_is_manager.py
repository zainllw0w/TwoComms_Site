from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0015_manager_bot_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_manager',
            field=models.BooleanField(default=False, verbose_name='Менеджер (доступ до Management)'),
        ),
    ]
