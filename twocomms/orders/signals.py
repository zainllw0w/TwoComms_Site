"""
Сигналы для уведомлений о заказах
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Order
from .tasks import send_telegram_notification_task


# Отключен автоматический сигнал - уведомления отправляются вручную в views
# @receiver(post_save, sender=Order)
# def send_new_order_notification(sender, instance, created, **kwargs):
#     """Отправляет уведомление при создании нового заказа"""
#     if created:
#         # Отправляем уведомление о новом заказе
#         telegram_notifier.send_new_order_notification(instance)


@receiver(pre_save, sender=Order)
def track_order_changes(sender, instance, **kwargs):
    """Отслеживает изменения в заказе"""
    if instance.pk:
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            
            # Отслеживаем изменение статуса заказа
            if old_instance.status != instance.status:
                # Async Telegram notification
                send_telegram_notification_task.delay(
                    instance.id, 
                    'status_update', 
                    old_status=old_instance.get_status_display(), 
                    new_status=instance.get_status_display()
                )
            
            # Отслеживаем добавление ТТН
            if not old_instance.tracking_number and instance.tracking_number:
                send_telegram_notification_task.delay(instance.id, 'ttn_added')
                
        except Order.DoesNotExist:
            pass
