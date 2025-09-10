# Generated manually for alt text field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('productcolors', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='productcolorimage',
            name='alt_text',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Alt-текст зображення'),
        ),
    ]
