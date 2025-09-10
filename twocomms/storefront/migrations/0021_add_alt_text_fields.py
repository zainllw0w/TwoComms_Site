# Generated manually for alt text fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0020_add_ai_content_fields'),  # Latest migration
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='main_image_alt',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Alt-текст головного зображення'),
        ),
        migrations.AddField(
            model_name='productimage',
            name='alt_text',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Alt-текст зображення'),
        ),
    ]
