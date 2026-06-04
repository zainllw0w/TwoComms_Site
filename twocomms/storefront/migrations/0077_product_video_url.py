from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0076_alter_useraction_action_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='video_url',
            field=models.URLField(
                blank=True,
                max_length=500,
                help_text=(
                    'Посилання на YouTube-відео товару (watch, youtu.be, embed або shorts). '
                    'Зʼявиться у галереї товару окремим слайдом та у структурованих даних.'
                ),
                verbose_name='Відео товару (YouTube)',
            ),
        ),
    ]
