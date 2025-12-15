from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0010_commercial_offer_email_v3"),
    ]

    operations = [
        migrations.AddField(
            model_name="commercialofferemailsettings",
            name="pricing_mode",
            field=models.CharField(
                choices=[("OPT", "Опт"), ("DROP", "Дроп")],
                default="OPT",
                max_length=10,
                verbose_name="База входу (опт/дроп)",
            ),
        ),
        migrations.AddField(
            model_name="commercialofferemailsettings",
            name="opt_tier",
            field=models.CharField(
                choices=[
                    ("8_15", "8–15"),
                    ("16_31", "16–31"),
                    ("32_63", "32–63"),
                    ("64_99", "64–99"),
                    ("100_PLUS", "100+"),
                ],
                default="8_15",
                max_length=10,
                verbose_name="Опт: обсяг (tier)",
            ),
        ),
        migrations.AddField(
            model_name="commercialofferemailsettings",
            name="drop_tee_price",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Дроп ціна футболка (грн)"),
        ),
        migrations.AddField(
            model_name="commercialofferemailsettings",
            name="drop_hoodie_price",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Дроп ціна худі (грн)"),
        ),
        migrations.AddField(
            model_name="commercialofferemailsettings",
            name="dropship_loyalty_bonus",
            field=models.BooleanField(default=False, verbose_name="Дроп бонус (-10 грн)"),
        ),
        migrations.AddField(
            model_name="commercialofferemaillog",
            name="pricing_mode",
            field=models.CharField(
                choices=[("OPT", "Опт"), ("DROP", "Дроп")],
                default="OPT",
                max_length=10,
                verbose_name="База входу (опт/дроп)",
            ),
        ),
        migrations.AddField(
            model_name="commercialofferemaillog",
            name="opt_tier",
            field=models.CharField(
                choices=[
                    ("8_15", "8–15"),
                    ("16_31", "16–31"),
                    ("32_63", "32–63"),
                    ("64_99", "64–99"),
                    ("100_PLUS", "100+"),
                ],
                default="8_15",
                max_length=10,
                verbose_name="Опт: обсяг (tier)",
            ),
        ),
        migrations.AddField(
            model_name="commercialofferemaillog",
            name="drop_tee_price",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Дроп ціна футболка (грн)"),
        ),
        migrations.AddField(
            model_name="commercialofferemaillog",
            name="drop_hoodie_price",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Дроп ціна худі (грн)"),
        ),
        migrations.AddField(
            model_name="commercialofferemaillog",
            name="dropship_loyalty_bonus",
            field=models.BooleanField(default=False, verbose_name="Дроп бонус (-10 грн)"),
        ),
    ]

