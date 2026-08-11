from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("product_catalog", "0012_taxonomy_assets_and_seo"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImageOptimizationJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("model_label", models.CharField(db_index=True, max_length=120)),
                ("object_id", models.PositiveBigIntegerField(db_index=True)),
                ("field_name", models.CharField(max_length=80)),
                ("source_name", models.CharField(default="", max_length=500)),
                ("status", models.CharField(choices=[("pending", "В черзі"), ("running", "Опрацьовується"), ("completed", "Готово"), ("error", "Помилка"), ("cancelled", "Скасовано")], default="pending", max_length=16)),
                ("stage", models.CharField(default="queued", max_length=32)),
                ("progress", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, default="")),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "indexes": [models.Index(fields=["model_label", "object_id", "field_name", "-created_at"], name="product_cat_model_l_5e4b9f_idx")],
            },
        ),
    ]
