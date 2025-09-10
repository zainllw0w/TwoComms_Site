# Generated manually for AI content fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0019_sitesession_pageview'),  # Latest migration
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='ai_keywords',
            field=models.TextField(blank=True, null=True, verbose_name='AI-ключові слова'),
        ),
        migrations.AddField(
            model_name='category',
            name='ai_description',
            field=models.TextField(blank=True, null=True, verbose_name='AI-опис'),
        ),
        migrations.AddField(
            model_name='category',
            name='ai_content_generated',
            field=models.BooleanField(default=False, verbose_name='AI-контент згенеровано'),
        ),
        migrations.AddField(
            model_name='product',
            name='ai_keywords',
            field=models.TextField(blank=True, null=True, verbose_name='AI-ключові слова'),
        ),
        migrations.AddField(
            model_name='product',
            name='ai_description',
            field=models.TextField(blank=True, null=True, verbose_name='AI-опис'),
        ),
        migrations.AddField(
            model_name='product',
            name='ai_content_generated',
            field=models.BooleanField(default=False, verbose_name='AI-контент згенеровано'),
        ),
    ]
