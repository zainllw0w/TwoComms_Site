"""
Django management команда для обновления статусов посылок
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from orders.nova_poshta_service import NovaPoshtaService


class Command(BaseCommand):
    help = 'Обновляет статусы посылок через API Новой Почты'

    def add_arguments(self, parser):
        parser.add_argument(
            '--order-number',
            type=str,
            help='Обновить статус конкретного заказа по номеру',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет обновлено без фактического обновления',
        )

    def handle(self, *args, **options):
        # Проверяем наличие API ключа
        if not getattr(settings, 'NOVA_POSHTA_API_KEY', ''):
            self.stdout.write(
                self.style.WARNING(
                    "NOVA_POSHTA_API_KEY не настроен в settings. "
                    "Добавьте ключ API Новой Почты в переменные окружения."
                )
            )
            return

        service = NovaPoshtaService()
        
        if options['order_number']:
            # Обновляем конкретный заказ
            self._update_single_order(service, options['order_number'], options['dry_run'])
        else:
            # Обновляем все заказы
            self._update_all_orders(service, options['dry_run'])

    def _update_single_order(self, service, order_number, dry_run):
        """Обновляет статус одного заказа"""
        from orders.models import Order
        
        try:
            order = Order.objects.get(order_number=order_number)
            
            if not order.tracking_number:
                self.stdout.write(
                    self.style.WARNING(f"Заказ {order_number} не имеет ТТН")
                )
                return
            
            self.stdout.write(f"Обновление статуса для заказа {order_number}...")
            
            if dry_run:
                tracking_info = service.get_tracking_info(order.tracking_number)
                if tracking_info:
                    status = tracking_info.get('Status', '')
                    status_desc = tracking_info.get('StatusDescription', '')
                    self.stdout.write(
                        f"Текущий статус: {status} - {status_desc}"
                    )
                else:
                    self.stdout.write("Не удалось получить информацию о статусе")
            else:
                if service.update_order_tracking_status(order):
                    self.stdout.write(
                        self.style.SUCCESS(f"Статус заказа {order_number} обновлен")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Статус заказа {order_number} не изменился")
                    )
                    
        except Order.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Заказ {order_number} не найден")
            )

    def _update_all_orders(self, service, dry_run):
        """Обновляет статусы всех заказов"""
        from orders.models import Order
        
        orders_with_ttn = Order.objects.filter(
            tracking_number__isnull=False
        ).exclude(tracking_number='')
        
        total_orders = orders_with_ttn.count()
        
        if total_orders == 0:
            self.stdout.write("Нет заказов с ТТН для обновления")
            return
        
        self.stdout.write(f"Найдено {total_orders} заказов с ТТН")
        
        if dry_run:
            self.stdout.write("DRY RUN - показываем что будет обновлено:")
            for order in orders_with_ttn:
                tracking_info = service.get_tracking_info(order.tracking_number)
                if tracking_info:
                    status = tracking_info.get('Status', '')
                    status_desc = tracking_info.get('StatusDescription', '')
                    current_status = order.shipment_status or 'Неизвестно'
                    new_status = f"{status} - {status_desc}" if status_desc else status
                    
                    if current_status != new_status:
                        self.stdout.write(
                            f"  {order.order_number}: {current_status} → {new_status}"
                        )
                    else:
                        self.stdout.write(
                            f"  {order.order_number}: статус не изменился ({current_status})"
                        )
                else:
                    self.stdout.write(f"  {order.order_number}: ошибка получения статуса")
        else:
            from django.utils import timezone
            
            self.stdout.write(f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Начало обновления статусов...")
            result = service.update_all_tracking_statuses()
            
            summary = (
                f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Обновление завершено:\n"
                f"  Всего заказов с ТТН: {result['total_orders']}\n"
                f"  Обновлено статусов: {result['updated']}\n"
                    f"  Ошибок: {result['errors']}"
            )
            
            if result['updated'] > 0:
                self.stdout.write(self.style.SUCCESS(summary))
            else:
                self.stdout.write(self.style.WARNING(summary))
