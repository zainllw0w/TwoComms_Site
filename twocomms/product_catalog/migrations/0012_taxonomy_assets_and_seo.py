from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("product_catalog", "0011_refine_brigade_taxonomy"),
    ]

    operations = [
        migrations.AddField(
            model_name="merchcollection",
            name="icon",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="product_catalog/merch_collection_icons/",
            ),
        ),
        migrations.AddField(
            model_name="merchcollection",
            name="seo_h1_uk",
            field=models.CharField(blank=True, default="", max_length=180),
        ),
        migrations.AddField(
            model_name="merchcollection",
            name="seo_h1_ru",
            field=models.CharField(blank=True, default="", max_length=180),
        ),
        migrations.AddField(
            model_name="merchcollection",
            name="seo_h1_en",
            field=models.CharField(blank=True, default="", max_length=180),
        ),
        migrations.AddField(
            model_name="merchcollection",
            name="seo_keywords_uk",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="merchcollection",
            name="seo_keywords_ru",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="merchcollection",
            name="seo_keywords_en",
            field=models.TextField(blank=True, default=""),
        ),
    ]
