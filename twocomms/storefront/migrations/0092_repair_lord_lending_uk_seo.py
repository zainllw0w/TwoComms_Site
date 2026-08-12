"""Align the audited Ukrainian PDP SEO copy for product 31 with its H1.

The print/theme name ``Lord Of The Lending`` remains valid editorial context;
only the stale Ukrainian identity-bearing fields are repaired. Exact-value
guards make this migration idempotent and prevent overwriting later editorial
changes.
"""

from django.db import migrations


PRODUCT_SLUG = "lord-of-the-lending"
OLD_SEO_DESCRIPTION = (
    "Футболка «Lord Of The Lending» TwoComms — сатирична фентезі-пародія про "
    "владу банків і кредитів. Шиємо в Україні, DTF-друк, бавовна. Доставка "
    "Новою Поштою. Підтримуємо ЗСУ."
)
NEW_SEO_DESCRIPTION = (
    "Футболка «Це Моя Посадка» TwoComms — англомовна сатира на кредитну "
    "культуру: принт Lord Of The Lending. Сатирична фентезі-пародія про "
    "владу банків і кредитів. Шиємо в Україні, DTF-друк, бавовна. Доставка "
    "Новою Поштою. Підтримуємо ЗСУ."
)
OLD_MAIN_IMAGE_ALT = (
    "Футболка «LORD OF THE LENDING» TwoComms - стильная футболка з унікальним "
    "дизайном для модних поціновувачів."
)
NEW_MAIN_IMAGE_ALT = (
    "Футболка «Це Моя Посадка» TwoComms — стильна футболка з англомовним "
    "сатиричним принтом Lord Of The Lending."
)


def repair_lord_lending_uk_seo(apps, schema_editor):
    Product = apps.get_model("storefront", "Product")
    Product._base_manager.filter(
        pk=31,
        slug=PRODUCT_SLUG,
        seo_description_uk=OLD_SEO_DESCRIPTION,
    ).update(seo_description_uk=NEW_SEO_DESCRIPTION)
    Product._base_manager.filter(
        pk=31,
        slug=PRODUCT_SLUG,
        main_image_alt_uk=OLD_MAIN_IMAGE_ALT,
    ).update(main_image_alt_uk=NEW_MAIN_IMAGE_ALT)


def reverse_lord_lending_uk_seo(apps, schema_editor):
    Product = apps.get_model("storefront", "Product")
    Product._base_manager.filter(
        pk=31,
        slug=PRODUCT_SLUG,
        seo_description_uk=NEW_SEO_DESCRIPTION,
    ).update(seo_description_uk=OLD_SEO_DESCRIPTION)
    Product._base_manager.filter(
        pk=31,
        slug=PRODUCT_SLUG,
        main_image_alt_uk=NEW_MAIN_IMAGE_ALT,
    ).update(main_image_alt_uk=OLD_MAIN_IMAGE_ALT)


class Migration(migrations.Migration):
    dependencies = [("storefront", "0091_cleanup_legacy_discount_links")]
    operations = [
        migrations.RunPython(repair_lord_lending_uk_seo, reverse_lord_lending_uk_seo),
    ]
