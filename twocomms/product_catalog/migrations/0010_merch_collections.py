from django.db import migrations, models
import django.db.models.deletion


COLLECTION_SEED = (
    {
        "slug": "military",
        "kind": "theme",
        "parent_slug": None,
        "name_uk": "Мілітарі",
        "name_ru": "Милитари",
        "name_en": "Military",
        "order": 10,
        "indexable": False,
    },
    {
        "slug": "brigades",
        "kind": "theme",
        "parent_slug": "military",
        "name_uk": "Бригади",
        "name_ru": "Бригады",
        "name_en": "Brigades",
        "order": 20,
        "indexable": False,
    },
    {
        "slug": "225",
        "kind": "brigade",
        "parent_slug": "brigades",
        "name_uk": "225 ОШП",
        "name_ru": "225 ОШП",
        "name_en": "225 Assault Regiment",
        "order": 30,
        "indexable": True,
    },
    {
        "slug": "streetwear",
        "kind": "theme",
        "parent_slug": None,
        "name_uk": "Стрітвір",
        "name_ru": "Стритвир",
        "name_en": "Streetwear",
        "order": 40,
        "indexable": False,
    },
    {
        "slug": "kharkiv",
        "kind": "city",
        "parent_slug": None,
        "name_uk": "Харків",
        "name_ru": "Харьков",
        "name_en": "Kharkiv",
        "order": 50,
        "indexable": False,
    },
)


def seed_merch_collections(apps, schema_editor):
    MerchCollection = apps.get_model("product_catalog", "MerchCollection")
    rows = {}
    for values in COLLECTION_SEED:
        parent_slug = values["parent_slug"]
        collection, _created = MerchCollection.objects.update_or_create(
            slug=values["slug"],
            defaults={
                "kind": values["kind"],
                "parent": rows.get(parent_slug),
                "name_uk": values["name_uk"],
                "name_ru": values["name_ru"],
                "name_en": values["name_en"],
                "order": values["order"],
                "indexable": values["indexable"],
                "is_active": True,
            },
        )
        rows[values["slug"]] = collection


class Migration(migrations.Migration):
    dependencies = [
        ("product_catalog", "0009_audience_taxonomy"),
    ]

    operations = [
        migrations.CreateModel(
            name="MerchCollection",
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
                ("slug", models.SlugField(max_length=80, unique=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("theme", "Тема"),
                            ("city", "Місто"),
                            ("brigade", "Бригада"),
                            ("collab", "Колаборація"),
                        ],
                        max_length=16,
                    ),
                ),
                ("name_uk", models.CharField(max_length=120)),
                ("name_ru", models.CharField(blank=True, default="", max_length=120)),
                ("name_en", models.CharField(blank=True, default="", max_length=120)),
                ("description_uk", models.TextField(blank=True, default="")),
                ("description_ru", models.TextField(blank=True, default="")),
                ("description_en", models.TextField(blank=True, default="")),
                ("seo_title_uk", models.CharField(blank=True, default="", max_length=180)),
                ("seo_title_ru", models.CharField(blank=True, default="", max_length=180)),
                ("seo_title_en", models.CharField(blank=True, default="", max_length=180)),
                ("seo_description_uk", models.CharField(blank=True, default="", max_length=320)),
                ("seo_description_ru", models.CharField(blank=True, default="", max_length=320)),
                ("seo_description_en", models.CharField(blank=True, default="", max_length=320)),
                (
                    "cover_image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="product_catalog/merch_collections/",
                    ),
                ),
                ("accent_token", models.SlugField(blank=True, default="", max_length=40)),
                ("indexable", models.BooleanField(default=False)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="product_catalog.merchcollection",
                    ),
                ),
            ],
            options={"ordering": ("order", "slug")},
        ),
        migrations.CreateModel(
            name="ProductMerchCollection",
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
                ("order", models.PositiveIntegerField(default=0)),
                ("display_label", models.CharField(blank=True, default="", max_length=120)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="product_assignments",
                        to="product_catalog.merchcollection",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="merch_collection_assignments",
                        to="storefront.product",
                    ),
                ),
            ],
            options={
                "ordering": (
                    "product_id",
                    "order",
                    "collection__order",
                    "collection_id",
                ),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("product", "collection"),
                        name="product_catalog_unique_product_merch_collection",
                    )
                ],
            },
        ),
        migrations.RunPython(seed_merch_collections, migrations.RunPython.noop),
    ]
