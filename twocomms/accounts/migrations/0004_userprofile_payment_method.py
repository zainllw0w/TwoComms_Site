# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_userprofile_telegram_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='payment_method',
            field=models.CharField(
                choices=[('card', 'На картку'), ('iban', 'IBAN')],
                default='card',
                max_length=20,
                verbose_name='Спосіб виплати'
            ),
        ),
    ]

