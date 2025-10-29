from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('productcolors', '0002_add_alt_text_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='productcolorvariant',
            name='barcode',
            field=models.CharField(blank=True, max_length=64, verbose_name='Штрих-код'),
        ),
        migrations.AddField(
            model_name='productcolorvariant',
            name='metadata',
            field=models.JSONField(blank=True, default=dict, verbose_name='Додаткові дані'),
        ),
        migrations.AddField(
            model_name='productcolorvariant',
            name='price_override',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Ціна для варіанту (грн)'),
        ),
        migrations.AddField(
            model_name='productcolorvariant',
            name='sku',
            field=models.CharField(blank=True, max_length=64, verbose_name='SKU'),
        ),
        migrations.AddField(
            model_name='productcolorvariant',
            name='stock',
            field=models.PositiveIntegerField(default=0, verbose_name='Залишок'),
        ),
        migrations.AddIndex(
            model_name='productcolorvariant',
            index=models.Index(fields=['product', 'order'], name='idx_variant_product_order'),
        ),
        migrations.AddIndex(
            model_name='productcolorvariant',
            index=models.Index(fields=['product', 'is_default'], name='idx_variant_default'),
        ),
        migrations.AddIndex(
            model_name='productcolorvariant',
            index=models.Index(fields=['sku'], name='idx_variant_sku'),
        ),
    ]
