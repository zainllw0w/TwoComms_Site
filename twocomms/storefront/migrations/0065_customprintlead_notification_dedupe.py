# Generated for custom-print Telegram dedupe (Phase 23)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0064_phase22_google_indexing_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="customprintlead",
            name="last_notification_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name="Останнє Telegram-сповіщення",
            ),
        ),
        migrations.AddField(
            model_name="customprintlead",
            name="notification_count",
            field=models.PositiveSmallIntegerField(
                default=0,
                verbose_name="Лічильник Telegram-сповіщень",
            ),
        ),
    ]
