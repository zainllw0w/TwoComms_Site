from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0055_payment_side_effect_job")]

    operations = [
        migrations.AlterField(
            model_name="paymentsideeffectjob",
            name="kind",
            field=models.CharField(
                choices=[
                    ("attempt_add_payment_info", "Meta AddPaymentInfo"),
                    ("attempt_telegram_started", "Telegram: спроба оплати"),
                    ("order_post_payment", "Події після оплати"),
                    (
                        "order_telegram_notification",
                        "Telegram: зміна замовлення",
                    ),
                ],
                max_length=40,
            ),
        ),
    ]
