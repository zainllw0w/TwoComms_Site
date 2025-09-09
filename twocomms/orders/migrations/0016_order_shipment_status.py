# Generated manually for Nova Poshta integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0015_order_payment_screenshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='shipment_status',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Статус посылки'),
        ),
        migrations.AddField(
            model_name='order',
            name='shipment_status_updated',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Время обновления статуса'),
        ),
    ]
