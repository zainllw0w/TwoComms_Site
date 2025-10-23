# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0032_add_available_for_payout'),
    ]

    operations = [
        migrations.AddField(
            model_name='dropshipperstats',
            name='successful_orders',
            field=models.PositiveIntegerField(default=0, verbose_name='Успішних замовлень (отримано)'),
        ),
        migrations.AddField(
            model_name='dropshipperstats',
            name='loyalty_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=6, verbose_name='Знижка лояльності (грн)'),
        ),
    ]

