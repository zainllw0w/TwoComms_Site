"""
Сигналы для уведомлений о заказах
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Order
from .tasks import send_telegram_notification_task

logger = logging.getLogger(__name__)


def _safe_queue_notification(order_id, notification_type, **kwargs):
    """
    Отправляет задачу в Celery, не падая, если брокер недоступен.
    В продакшене були ситуации, когда Redis/Celery недоступен, из-за чего
    падало сохранение статуса заказа. Теперь логируем и продолжаем.
    """
    try:
        send_telegram_notification_task.delay(order_id, notification_type, **kwargs)
    except Exception as exc:
        logger.warning(
            "Не удалось поставити в чергу Telegram нотифікацію (%s) для замовлення %s: %s",
            notification_type,
            order_id,
            exc,
            exc_info=True,
        )


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
                # Async Telegram notification (не блочим збереження при помилці)
                _safe_queue_notification(
                    instance.id,
                    'status_update',
                    old_status=old_instance.get_status_display(),
                    new_status=instance.get_status_display()
                )
            
            # Отслеживаем добавление ТТН
            if not old_instance.tracking_number and instance.tracking_number:
                _safe_queue_notification(instance.id, 'ttn_added')
                
        except Order.DoesNotExist:
            pass
