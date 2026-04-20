from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0043_seo_timestamps_product_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="sizegrid",
            name="guide_data",
            field=models.JSONField(blank=True, default=dict, verbose_name="Структуровані дані сітки"),
        ),
    ]
