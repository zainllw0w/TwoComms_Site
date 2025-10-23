# Generated migration for adding available_for_payout field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0031_add_dropshipper_status_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='dropshipperstats',
            name='available_for_payout',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Доступно до виплати'),
        ),
    ]

