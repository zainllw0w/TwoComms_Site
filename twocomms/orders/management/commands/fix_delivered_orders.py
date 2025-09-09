"""
Django management команда для исправления статусов заказов с полученными посылками
"""
from django.core.management.base import BaseCommand
from orders.models import Order
from orders.nova_poshta_service import NovaPoshtaService


class Command(BaseCommand):
    help = 'Исправляет статусы заказов с полученными посылками'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет изменено без фактического изменения',
        )

    def handle(self, *args, **options):
        service = NovaPoshtaService()
        
        # Находим заказы с ТТН и статусом посылки, но статусом заказа не "done"
        orders_to_fix = Order.objects.filter(
            tracking_number__isnull=False
        ).exclude(
            tracking_number=''
        ).exclude(
            shipment_status__isnull=True
        ).exclude(
            shipment_status=''
        ).exclude(
            status='done'
        )
        
        total_orders = orders_to_fix.count()
        
        if total_orders == 0:
            self.stdout.write("Нет заказов для исправления")
            return
        
        self.stdout.write(f"Найдено {total_orders} заказов для проверки")
        
        fixed_count = 0
        
        for order in orders_to_fix:
            # Проверяем, получена ли посылка
            if order.shipment_status:
                parts = order.shipment_status.split(' - ')
                status = parts[0] if parts else order.shipment_status
                status_description = parts[1] if len(parts) > 1 else ''
                
                # Проверяем ключевые слова доставки
                delivered_keywords = [
                    'отримано', 'получено', 'доставлено', 'вручено', 
                    'отримано отримувачем', 'получено получателем'
                ]
                
                status_lower = status.lower()
                description_lower = status_description.lower() if status_description else ''
                
                is_delivered = any(keyword in status_lower or keyword in description_lower 
                                  for keyword in delivered_keywords)
                
                if is_delivered:
                    if options['dry_run']:
                        self.stdout.write(
                            f"  {order.order_number}: {order.status} → done "
                            f"(посылка: {order.shipment_status})"
                        )
                    else:
                        old_status = order.status
                        order.status = 'done'
                        order.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✅ {order.order_number}: {old_status} → done "
                                f"(посылка: {order.shipment_status})"
                            )
                        )
                        fixed_count += 1
                else:
                    if options['dry_run']:
                        self.stdout.write(
                            f"  {order.order_number}: статус не изменен "
                            f"(посылка: {order.shipment_status})"
                        )
        
        if options['dry_run']:
            self.stdout.write(f"\nDRY RUN: Будет исправлено {fixed_count} заказов")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ Исправлено {fixed_count} заказов")
            )
