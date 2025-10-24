# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0028_dropshipperorder_dropshipper_payment_required_and_more'),
    ]

    operations = [
        # Обновляем статусы заказов
        migrations.AlterField(
            model_name='dropshipperorder',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Чернетка'),
                    ('pending', 'Очікує підтвердження'),
                    ('awaiting_payment', 'Очікує оплати'),
                    ('confirmed', 'Підтверджено'),
                    ('processing', 'В обробці'),
                    ('awaiting_shipment', 'Очікує відправки'),
                    ('shipped', 'Відправлено'),
                    ('delivered_awaiting_pickup', 'Доставлено, очікує отримувача'),
                    ('received', 'Товар отримано'),
                    ('refused', 'Від товару відмовились'),
                    ('delivered', 'Доставлено'),
                    ('cancelled', 'Скасовано'),
                ],
                default='draft',
                max_length=35,  # Увеличиваем размер для новых статусов
                verbose_name='Статус'
            ),
        ),
        
        # Добавляем поля для отслеживания НП
        migrations.AddField(
            model_name='dropshipperorder',
            name='shipment_status',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Статус НП'),
        ),
        migrations.AddField(
            model_name='dropshipperorder',
            name='shipment_status_updated',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Оновлення статусу НП'),
        ),
        migrations.AddField(
            model_name='dropshipperorder',
            name='payout_processed',
            field=models.BooleanField(default=False, verbose_name='Виплату оброблено'),
        ),
        
        # Обновляем модель выплат
        migrations.AddField(
            model_name='dropshipperpayout',
            name='order',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='single_payout',
                to='orders.dropshipperorder',
                verbose_name='Замовлення'
            ),
        ),
        migrations.AddField(
            model_name='dropshipperpayout',
            name='description',
            field=models.CharField(blank=True, max_length=500, verbose_name='Опис'),
        ),
        migrations.AlterField(
            model_name='dropshipperpayout',
            name='payment_method',
            field=models.CharField(
                blank=True,
                choices=[
                    ('card', 'На картку'),
                    ('bank', 'Банківський переказ'),
                    ('cash', 'Готівка'),
                    ('crypto', 'Криптовалюта'),
                ],
                max_length=20,
                null=True,
                verbose_name='Спосіб виплати'
            ),
        ),
        migrations.AlterField(
            model_name='dropshipperpayout',
            name='payment_details',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Деталі виплати (номер картки/рахунку)'),
        ),
        migrations.AlterField(
            model_name='dropshipperpayout',
            name='included_orders',
            field=models.ManyToManyField(blank=True, related_name='payouts', to='orders.dropshipperorder', verbose_name='Включені замовлення'),
        ),
    ]

