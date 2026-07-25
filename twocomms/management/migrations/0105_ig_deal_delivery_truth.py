from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0104_ig_order_attribution"),
    ]

    operations = [
        migrations.AddField(
            model_name="igdeal",
            name="delivery_error",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="igdeal",
            name="delivery_source",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="igdeal",
            name="delivery_status",
            field=models.CharField(
                choices=[
                    ("unverified", "Доставку не підтверджено"),
                    ("validated", "Доставку підтверджено довідником НП"),
                    ("needs_review", "Потрібна перевірка доставки"),
                    ("invalid", "Дані доставки невалідні"),
                ],
                db_index=True,
                default="unverified",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="igdeal",
            name="delivery_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="igdeal",
            name="np_city_ref",
            field=models.CharField(blank=True, default="", max_length=36),
        ),
        migrations.AddField(
            model_name="igdeal",
            name="np_settlement_ref",
            field=models.CharField(blank=True, default="", max_length=36),
        ),
        migrations.AddField(
            model_name="igdeal",
            name="np_warehouse_kind",
            field=models.CharField(blank=True, default="branch", max_length=16),
        ),
        migrations.AddField(
            model_name="igdeal",
            name="np_warehouse_ref",
            field=models.CharField(blank=True, default="", max_length=36),
        ),
    ]
