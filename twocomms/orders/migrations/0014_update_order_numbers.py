from django.db import migrations
from datetime import datetime

def update_order_numbers(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    
    # Получаем все заказы без номеров или с неправильными номерами
    orders = Order.objects.filter(order_number__isnull=True) | Order.objects.filter(order_number='')
    
    for order in orders:
        # Генерируем новый номер
        today = order.created.date()
        date_str = today.strftime('%d%m%Y')
        
        # Получаем количество заказов за эту дату
        today_orders = Order.objects.filter(
            created__date=today
        ).count()
        
        # Номер по счету (начиная с 01)
        order_count = today_orders + 1
        
        new_number = f"TWC{date_str}N{order_count:02d}"
        order.order_number = new_number
        order.save()

def reverse_update_order_numbers(apps, schema_editor):
    # Обратная миграция не нужна
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0013_alter_order_payment_status'),
    ]

    operations = [
        migrations.RunPython(update_order_numbers, reverse_update_order_numbers),
    ]
