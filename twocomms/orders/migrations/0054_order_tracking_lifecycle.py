from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0053_paymentattempt_generic_prepayment")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="tracking_status_code",
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True, verbose_name="Код статуса НП"),
        ),
        migrations.AddField(
            model_name="order",
            name="tracking_checked_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="Последняя проверка НП"),
        ),
        migrations.AddField(
            model_name="order",
            name="tracking_provider_event_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Событие НП"),
        ),
        migrations.AddField(
            model_name="order",
            name="tracking_next_check_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="Следующая проверка НП"),
        ),
        migrations.AddField(
            model_name="order",
            name="tracking_failure_count",
            field=models.PositiveIntegerField(default=0, verbose_name="Ошибки проверки НП"),
        ),
        migrations.AddField(
            model_name="order",
            name="tracking_terminal_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Терминальный статус НП"),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["tracking_terminal_at", "tracking_next_check_at"], name="order_track_next"),
        ),
    ]
