from django.db import migrations, models
import django.db.models.deletion


AUDIENCE_SEED = (
    {
        "code": "unisex",
        "label_uk": "Унісекс",
        "label_ru": "Унисекс",
        "label_en": "Unisex",
        "order": 0,
    },
    {
        "code": "women",
        "label_uk": "Жіночі",
        "label_ru": "Женские",
        "label_en": "Women",
        "order": 1,
    },
    {
        "code": "men",
        "label_uk": "Чоловічі",
        "label_ru": "Мужские",
        "label_en": "Men",
        "order": 2,
    },
)


def seed_audience_tags(apps, schema_editor):
    AudienceTag = apps.get_model("fable5", "AudienceTag")
    for values in AUDIENCE_SEED:
        AudienceTag.objects.update_or_create(
            code=values["code"],
            defaults={**values, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("fable5", "0008_product_inventory_policy"),
    ]

    operations = [
        migrations.CreateModel(
            name="AudienceTag",
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
                ("code", models.SlugField(max_length=32, unique=True)),
                ("label_uk", models.CharField(max_length=80)),
                ("label_ru", models.CharField(max_length=80)),
                ("label_en", models.CharField(max_length=80)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("order", "code")},
        ),
        migrations.CreateModel(
            name="ProductAudience",
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
                ("note", models.CharField(blank=True, default="", max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="audience_assignments",
                        to="storefront.product",
                    ),
                ),
                (
                    "tag",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="product_assignments",
                        to="fable5.audiencetag",
                    ),
                ),
            ],
            options={
                "ordering": ("product_id", "tag__order", "tag_id"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("product", "tag"),
                        name="f5_unique_product_audience",
                    )
                ],
            },
        ),
        # Reverse CreateModel operations remove assignments before tags.
        # Do not delete protected seed rows while assignments still exist.
        migrations.RunPython(seed_audience_tags, migrations.RunPython.noop),
    ]
