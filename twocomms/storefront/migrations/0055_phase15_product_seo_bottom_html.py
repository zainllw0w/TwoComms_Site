"""Phase 15 — optional admin override for the per-product SEO landing
block. When ``Product.seo_bottom_html`` is non-empty, the partial
``partials/product_seo_landing.html`` renders it verbatim (with
``|safe``) instead of the auto-generated theme-aware text.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0054_phase10c_extended_seo_copy"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="seo_bottom_html",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="SEO-блок внизу сторінки (опційно)",
                help_text=(
                    "Опційний HTML-блок, який рендериться у нижній частині "
                    "картки товару перед футером. Якщо порожній — генерується "
                    "автоматично з тем та категорії товару."
                ),
            ),
        ),
    ]
