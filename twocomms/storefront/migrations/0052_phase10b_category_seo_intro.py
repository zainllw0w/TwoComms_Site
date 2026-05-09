"""Phase 10b — Category.seo_intro_html for above-grid SEO copy."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0051_phase10_category_seo_blocks"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="seo_intro_html",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Короткий HTML-блок під H1 (1–3 речення з основними ключами + "
                    "опційно <details>...</details> або <div data-seo-collapsible> "
                    "для розгортуваного блоку). Не показується на /catalog/ без "
                    "фільтру категорії."
                ),
                verbose_name="SEO-інтро над сіткою товарів",
            ),
        ),
    ]
