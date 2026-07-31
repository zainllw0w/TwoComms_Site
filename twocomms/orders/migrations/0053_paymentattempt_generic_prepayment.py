from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0052_dynamic_prepayment_choice")]

    operations = [
        migrations.AlterField(
            model_name="paymentattempt",
            name="pay_type",
            field=models.CharField(
                choices=[
                    ("online_full", "Онлайн оплата (повна сума)"),
                    ("prepayment", "Передоплата за погодженою сумою"),
                    ("prepay_200", "Передплата 200 грн"),
                ],
                max_length=20,
            ),
        ),
    ]
