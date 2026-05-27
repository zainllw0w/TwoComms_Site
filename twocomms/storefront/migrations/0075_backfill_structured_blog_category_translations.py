from django.db import migrations


CATEGORY_TRANSLATIONS = {
    "news": {
        "name": "Новини",
        "name_uk": "Новини",
        "name_ru": "Новости",
        "name_en": "News",
        "description": "Новини TwoComms",
        "description_uk": "Новини TwoComms",
        "description_ru": "Новости TwoComms",
        "description_en": "TwoComms news",
    },
    "reviews": {
        "name": "Огляди",
        "name_uk": "Огляди",
        "name_ru": "Обзоры",
        "name_en": "Reviews",
        "description": "Огляди продукції TwoComms",
        "description_uk": "Огляди продукції TwoComms",
        "description_ru": "Обзоры продукции TwoComms",
        "description_en": "TwoComms product reviews",
    },
    "veteran-fund": {
        "name": "Український ветеранський фонд",
        "name_uk": "Український ветеранський фонд",
        "name_ru": "Украинский ветеранский фонд",
        "name_en": "Ukrainian Veteran Fund",
        "description": "Звіти та новини щодо Українського ветеранського фонду.",
        "description_uk": "Звіти та новини щодо Українського ветеранського фонду.",
        "description_ru": "Отчеты и новости об Украинском ветеранском фонде.",
        "description_en": "Reports and news about the Ukrainian Veteran Fund.",
    },
    "product-reviews": {
        "name": "Огляди продукції",
        "name_uk": "Огляди продукції",
        "name_ru": "Обзоры продукции",
        "name_en": "Product reviews",
        "description": "Огляди речей TwoComms.",
        "description_uk": "Огляди речей TwoComms.",
        "description_ru": "Обзоры вещей TwoComms.",
        "description_en": "TwoComms product reviews.",
    },
}


def backfill_category_translations(apps, schema_editor):
    BlogCategory = apps.get_model("storefront", "BlogCategory")
    db = schema_editor.connection.alias
    for slug, values in CATEGORY_TRANSLATIONS.items():
        BlogCategory.objects.using(db).filter(slug=slug).update(**values)


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0074_blogpost_cover_caption_blogpost_cover_caption_en_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_category_translations, migrations.RunPython.noop),
    ]
