"""
Phase 1: AI opt-in for SEO + per-product fit selector toggle.

Adds:
    - Category.ai_generation_enabled (default=False)
    - Product.ai_generation_enabled (default=False)
    - Product.fit_selector_enabled (default=True)

Data migration:
    - For Category and Product where ai_content_generated=True, set
      ai_generation_enabled=True so existing AI-generated content keeps
      being used in meta-tags fallback (preserves current behavior).
"""
from django.db import migrations, models


def enable_ai_for_existing_generated(apps, schema_editor):
    Product = apps.get_model('storefront', 'Product')
    Category = apps.get_model('storefront', 'Category')
    Product.objects.filter(ai_content_generated=True).update(ai_generation_enabled=True)
    Category.objects.filter(ai_content_generated=True).update(ai_generation_enabled=True)


def reverse_noop(apps, schema_editor):
    # No reverse needed: the flag will simply be dropped with the column.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0049_product_content_faq'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='ai_generation_enabled',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Якщо вимкнено — AI ніколи не використовується для цієї категорії; '
                    'мета-теги та Schema беруть лише вручну заповнені SEO-поля та fallback.'
                ),
                verbose_name='Дозволити AI-генерацію SEO',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='ai_generation_enabled',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Якщо вимкнено — AI не використовується для цього товару. '
                    'Мета-теги та Schema будуть братися лише з вручну заповнених SEO-полів та fallback.'
                ),
                verbose_name='Дозволити AI-генерацію SEO',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='fit_selector_enabled',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'Якщо вимкнено — блок з вибором крою не відображається на сторінці товару.'
                ),
                verbose_name='Показувати селектор крою (класика / оверсайз)',
            ),
        ),
        migrations.RunPython(enable_ai_for_existing_generated, reverse_noop),
    ]
