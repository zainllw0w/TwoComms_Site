"""Remove the audited keyword-list override from one standard PDP.

The production row for ``futbolka-posmikhnys`` stored a truncated Ukrainian
keyword list in both the legacy and Ukrainian ``Product.seo_title`` fields.
Those fields are inherited by every color and color-fit URL.  Clearing only
the exact stale pair lets the normal identity/variant metadata generator
describe the selected path without changing product copy, translations,
inventory, media, or any other product.
"""

from django.db import migrations


PRODUCT_PK = 107
PRODUCT_SLUG = "futbolka-posmikhnys"
OLD_SEO_TITLE = (
    "молочна футболка з написом, футболка, футболка з принтом, "
    "купити футболку, футболка oversize, бежева футболка, унісекс "
    "футболка, футболка з написом, молочна фут"
)


def _plain_manager(model):
    """Bypass modeltranslation lookup rewriting when called outside RunPython."""

    manager = model._base_manager
    rewrite = getattr(manager, "rewrite", None)
    return rewrite(False) if callable(rewrite) else manager


def repair_posmikhnys_seo(apps, schema_editor):
    Product = apps.get_model("storefront", "Product")
    _plain_manager(Product).filter(
        pk=PRODUCT_PK,
        slug=PRODUCT_SLUG,
        seo_title=OLD_SEO_TITLE,
        seo_title_uk=OLD_SEO_TITLE,
    ).update(seo_title="", seo_title_uk="")


def reverse_posmikhnys_seo(apps, schema_editor):
    Product = apps.get_model("storefront", "Product")
    _plain_manager(Product).filter(
        pk=PRODUCT_PK,
        slug=PRODUCT_SLUG,
        seo_title="",
        seo_title_uk="",
    ).update(seo_title=OLD_SEO_TITLE, seo_title_uk=OLD_SEO_TITLE)


class Migration(migrations.Migration):
    dependencies = [("storefront", "0092_repair_lord_lending_uk_seo")]
    operations = [
        migrations.RunPython(repair_posmikhnys_seo, reverse_posmikhnys_seo),
    ]
