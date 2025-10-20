from django.core.management.base import BaseCommand
from orders.models import DropshipperOrder, DropshipperOrderItem, DropshipperStats, DropshipperPayout


class Command(BaseCommand):
    help = 'Удаляет все заказы дропшиперов и сбрасывает статистику'

    def handle(self, *args, **options):
        # Удаляем все элементы заказов
        deleted_items = DropshipperOrderItem.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Удалено элементов заказов: {deleted_items[0]}'))
        
        # Удаляем все заказы
        deleted_orders = DropshipperOrder.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Удалено заказов: {deleted_orders[0]}'))
        
        # Сбрасываем статистику
        stats = DropshipperStats.objects.all()
        for stat in stats:
            stat.total_orders = 0
            stat.completed_orders = 0
            stat.cancelled_orders = 0
            stat.total_revenue = 0
            stat.total_profit = 0
            stat.total_drop_cost = 0
            stat.total_items_sold = 0
            stat.last_order_date = None
            stat.save()
        
        self.stdout.write(self.style.SUCCESS(f'Сброшена статистика для {stats.count()} пользователей'))
        
        self.stdout.write(self.style.SUCCESS('✅ Все заказы дропшиперов успешно удалены!'))

