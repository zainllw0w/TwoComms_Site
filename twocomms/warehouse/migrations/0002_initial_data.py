"""Дані за замовчуванням: категорії, підкатегорії, група warehouse_admins."""
from django.db import migrations


INITIAL_CATEGORIES = [
    {
        "name": "Футболки",
        "slug": "tshirts",
        "icon": "shirt",
        "order": 10,
        "subcategories": [
            {"name": "Класична", "slug": "classic", "order": 10, "is_default": True},
            {"name": "Оверсайз ERC", "slug": "oversize-erc", "order": 20},
            {"name": "Базова без резинки", "slug": "basic-no-rib", "order": 30},
            {"name": "Жіноча", "slug": "female", "order": 40},
        ],
    },
    {
        "name": "Худі",
        "slug": "hoodies",
        "icon": "shirt",
        "order": 20,
        "subcategories": [
            {"name": "Класичне", "slug": "classic", "order": 10, "is_default": True},
            {"name": "Оверсайз", "slug": "oversize", "order": 20},
        ],
    },
    {
        "name": "Лонгсліви",
        "slug": "longsleeves",
        "icon": "shirt",
        "order": 30,
        "subcategories": [
            {"name": "Класичний", "slug": "classic", "order": 10, "is_default": True},
            {"name": "Бамбуковий", "slug": "bamboo", "order": 20},
        ],
    },
]


def seed_initial(apps, schema_editor):
    StorageCategory = apps.get_model("warehouse", "StorageCategory")
    StorageSubcategory = apps.get_model("warehouse", "StorageSubcategory")
    Group = apps.get_model("auth", "Group")

    for cat_data in INITIAL_CATEGORIES:
        cat, _ = StorageCategory.objects.get_or_create(
            slug=cat_data["slug"],
            defaults={
                "name": cat_data["name"],
                "icon": cat_data.get("icon", ""),
                "order": cat_data.get("order", 0),
            },
        )
        for sub in cat_data["subcategories"]:
            StorageSubcategory.objects.get_or_create(
                category=cat,
                slug=sub["slug"],
                defaults={
                    "name": sub["name"],
                    "order": sub.get("order", 0),
                    "is_default": sub.get("is_default", False),
                },
            )

    Group.objects.get_or_create(name="warehouse_admins")


def remove_initial(apps, schema_editor):
    StorageCategory = apps.get_model("warehouse", "StorageCategory")
    Group = apps.get_model("auth", "Group")
    StorageCategory.objects.filter(slug__in=[c["slug"] for c in INITIAL_CATEGORIES]).delete()
    Group.objects.filter(name="warehouse_admins").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("warehouse", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(seed_initial, remove_initial),
    ]
