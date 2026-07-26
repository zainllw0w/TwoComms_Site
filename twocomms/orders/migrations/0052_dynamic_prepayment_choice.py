from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0051_paymentattempt"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="pay_type",
            field=models.CharField(
                choices=[
                    ("online_full", "Онлайн оплата (повна сума)"),
                    ("prepayment", "Передоплата за погодженою сумою"),
                    ("prepay_200", "Передплата 200 грн"),
                    ("cod", "Оплата при отриманні"),
                    ("full", "Повна оплата"),
                    ("partial", "Часткова оплата"),
                ],
                default="online_full",
                max_length=20,
            ),
        ),
    ]
