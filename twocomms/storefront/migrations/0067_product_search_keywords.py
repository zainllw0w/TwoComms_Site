"""SEO molecular-upgrade US-6 — admin-editable per-product search keywords.

Adds ``Product.search_keywords`` (JSONField, blank, default=list) to
back the «Часті пошуки» chip strip on PDPs. See the model docstring
and ``storefront/services/product_search_keywords.py`` for routing.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0066_customprintlead_telegram_verified_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="search_keywords",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'Список словників [{"label": "купити чорну футболку оверсайз", '
                    '"url": "/catalog/tshirts/black/", "weight": 100}]. '
                    'Auto-generated chips додаються після manual.'
                ),
                verbose_name="Часті пошуки (manual override)",
            ),
        ),
    ]
