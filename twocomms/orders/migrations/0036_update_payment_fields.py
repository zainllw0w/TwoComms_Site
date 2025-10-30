# Generated migration for payment system update

from django.db import migrations, models


def migrate_payment_statuses(apps, schema_editor):
    """
    Миграция данных: преобразует 'partial' в 'prepaid' для payment_status.
    Также преобразует старые значения pay_type в новые.
    """
    Order = apps.get_model('orders', 'Order')
    
    # Обновляем payment_status: partial → prepaid
    Order.objects.filter(payment_status='partial').update(payment_status='prepaid')
    
    # Обновляем pay_type: full → online_full, partial → prepay_200
    Order.objects.filter(pay_type='full').update(pay_type='online_full')
    Order.objects.filter(pay_type='partial').update(pay_type='prepay_200')
    
    print(f"✅ Migrated payment statuses successfully")


def reverse_migrate_payment_statuses(apps, schema_editor):
    """Обратная миграция (откат)"""
    Order = apps.get_model('orders', 'Order')
    
    # Откат изменений
    Order.objects.filter(payment_status='prepaid').update(payment_status='partial')
    Order.objects.filter(pay_type='online_full').update(pay_type='full')
    Order.objects.filter(pay_type='prepay_200').update(pay_type='partial')


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0035_dropshipperorder_monobank_invoice_id'),
    ]

    operations = [
        # 1. Расширяем max_length для pay_type
        migrations.AlterField(
            model_name='order',
            name='pay_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('online_full', 'Онлайн оплата (повна сума)'),
                    ('prepay_200', 'Передплата 200 грн'),
                    ('cod', 'Оплата при отриманні'),
                    ('full', 'Повна оплата'),
                    ('partial', 'Часткова оплата'),
                ],
                default='online_full'
            ),
        ),
        
        # 2. Обновляем choices для payment_status (не меняет схему, только choices)
        migrations.AlterField(
            model_name='order',
            name='payment_status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('unpaid', 'Не оплачено'),
                    ('checking', 'На перевірці'),
                    ('prepaid', 'Внесена передплата'),
                    ('paid', 'Оплачено повністю'),
                    ('partial', 'Внесена передплата (старе)'),
                ],
                default='unpaid'
            ),
        ),
        
        # 3. Миграция данных
        migrations.RunPython(
            migrate_payment_statuses,
            reverse_migrate_payment_statuses
        ),
    ]

