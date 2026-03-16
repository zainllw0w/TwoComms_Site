from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0018_userprofile_birth_date_userprofile_viber_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="tg_manager_alert_15m",
            field=models.BooleanField(default=True, verbose_name="Нагадування за 15 хв"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="tg_manager_alert_5m",
            field=models.BooleanField(default=True, verbose_name="Нагадування за 5 хв"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="tg_manager_alert_due_now",
            field=models.BooleanField(default=True, verbose_name="Нагадування в момент дзвінка"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="tg_manager_alert_missed_callback",
            field=models.BooleanField(default=True, verbose_name="Алерт про пропущений передзвін"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="tg_manager_alert_report_late",
            field=models.BooleanField(default=True, verbose_name="Нагадування про прострочений звіт"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="tg_manager_daily_advice_enabled",
            field=models.BooleanField(default=True, verbose_name="Щоденні поради в Telegram"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="tg_manager_critical_advice_enabled",
            field=models.BooleanField(default=True, verbose_name="Критичні поради в Telegram"),
        ),
    ]
