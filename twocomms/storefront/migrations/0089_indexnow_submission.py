from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storefront", "0088_product_sales_semantic_profiles"),
    ]

    operations = [
        migrations.CreateModel(
            name="IndexNowSubmission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("url", models.CharField(max_length=512, verbose_name="URL")),
                (
                    "status",
                    models.CharField(
                        choices=[("success", "Прийнято"), ("failed", "Помилка")],
                        max_length=16,
                    ),
                ),
                ("http_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("source", models.CharField(blank=True, max_length=32)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "IndexNow submission",
                "verbose_name_plural": "IndexNow submissions",
                "ordering": ["-submitted_at"],
                "indexes": [
                    models.Index(fields=["url", "-submitted_at"], name="idx_in_url_submitted"),
                    models.Index(fields=["status", "-submitted_at"], name="idx_in_status_time"),
                ],
            },
        ),
    ]
