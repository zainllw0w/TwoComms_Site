from django.core.management.base import BaseCommand
from orders.models import Order
from datetime import datetime


class Command(BaseCommand):
    help = 'Генерирует номера заказов для существующих записей'

    def handle(self, *args, **options):
        orders = Order.objects.filter(order_number__isnull=True)
        
        if not orders.exists():
            self.stdout.write(
                self.style.SUCCESS('Все заказы уже имеют номера')
            )
            return
        
        self.stdout.write(f'Найдено {orders.count()} заказов без номеров')
        
        # Группируем заказы по дате создания
        orders_by_date = {}
        for order in orders:
            date_key = order.created.date()
            if date_key not in orders_by_date:
                orders_by_date[date_key] = []
            orders_by_date[date_key].append(order)
        
        # Генерируем номера для каждой даты
        for date, date_orders in orders_by_date.items():
            date_str = date.strftime('%d%m%Y')
            
            # Получаем количество заказов за эту дату (включая уже пронумерованные)
            existing_count = Order.objects.filter(
                created__date=date,
                order_number__isnull=False
            ).count()
            
            for i, order in enumerate(date_orders, 1):
                order_count = existing_count + i
                order.order_number = f"TWC{date_str}N{order_count:02d}"
                order.save()
                
                self.stdout.write(
                    f'Заказ {order.id}: {order.order_number}'
                )
        
        self.stdout.write(
            self.style.SUCCESS('Все номера заказов успешно сгенерированы')
        )
