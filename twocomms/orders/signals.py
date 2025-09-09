"""
Сигналы для уведомлений о заказах
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Order
from .telegram_notifications import telegram_notifier


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
                telegram_notifier.send_order_status_update(
                    instance, 
                    old_instance.get_status_display(), 
                    instance.get_status_display()
                )
            
            # Отслеживаем добавление ТТН
            if not old_instance.tracking_number and instance.tracking_number:
                telegram_notifier.send_ttn_added_notification(instance)
                
        except Order.DoesNotExist:
            pass
