"""
Add created_at and updated_at timestamp fields to Product and Category models
for SEO sitemap lastmod support.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0042_customprintlead_moderation_db_default'),
    ]

    operations = [
        # Category timestamps
        migrations.AddField(
            model_name='category',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True, verbose_name='Створено'),
        ),
        migrations.AddField(
            model_name='category',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True, verbose_name='Оновлено'),
        ),
        # Product timestamps
        migrations.AddField(
            model_name='product',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True, verbose_name='Створено'),
        ),
        migrations.AddField(
            model_name='product',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True, verbose_name='Оновлено'),
        ),
    ]
