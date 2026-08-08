from django.db import migrations


def refine_brigade_taxonomy(apps, schema_editor):
    MerchCollection = apps.get_model("fable5", "MerchCollection")
    brigades = MerchCollection.objects.filter(slug="brigades").first()
    if brigades is None:
        brigades = MerchCollection.objects.create(
            slug="brigades",
            kind="theme",
            name_uk="Бригади",
            name_ru="Бригады",
            name_en="Brigades",
            order=20,
            indexable=False,
            is_active=True,
        )
    else:
        brigades.parent = None
        brigades.kind = "theme"
        brigades.order = 20
        brigades.indexable = False
        brigades.is_active = True
        brigades.save(
            update_fields=["parent", "kind", "order", "indexable", "is_active"]
        )

    MerchCollection.objects.update_or_create(
        slug="127",
        defaults={
            "kind": "brigade",
            "parent": brigades,
            "name_uk": "127 бригада",
            "name_ru": "127 бригада",
            "name_en": "127 Brigade",
            "order": 31,
            "indexable": False,
            "is_active": True,
        },
    )


def restore_previous_taxonomy(apps, schema_editor):
    MerchCollection = apps.get_model("fable5", "MerchCollection")
    military = MerchCollection.objects.filter(slug="military").first()
    MerchCollection.objects.filter(slug="brigades").update(parent=military)
    MerchCollection.objects.filter(slug="127").update(is_active=False, indexable=False)


class Migration(migrations.Migration):
    dependencies = [
        ("fable5", "0010_merch_collections"),
    ]

    operations = [
        migrations.RunPython(refine_brigade_taxonomy, restore_previous_taxonomy),
    ]
