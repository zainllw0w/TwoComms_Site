"""
Сигналы для уведомлений о заказах
"""
import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from django.db.models.signals import post_save, pre_save
from django.db import transaction
from django.dispatch import receiver
from .models import Order, WholesaleInvoice
from .tasks import send_telegram_notification_task
from .telegram_notifications import telegram_notifier

logger = logging.getLogger(__name__)


def _safe_queue_notification(order_id, notification_type, **kwargs):
    """
    Отправляет задачу в Celery, не падая, если брокер недоступен.
    В продакшене були ситуации, когда Redis/Celery недоступен, из-за чего
    падало сохранение статуса заказа. Теперь логируем и продолжаем.
    При недоступности брокера дополнительно пробуем синхронную отправку,
    чтобы админ мгновенно увидел уведомление.
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
        # Фолбэк: пробуем отправить синхронно, чтобы уведомление всё же дошло
        try:
            order = Order.objects.filter(id=order_id).select_related('user__userprofile').first()
            if not order:
                return
            if notification_type == 'status_update':
                telegram_notifier.send_order_status_update(
                    order,
                    kwargs.get('old_status'),
                    kwargs.get('new_status'),
                )
            elif notification_type == 'ttn_added':
                telegram_notifier.send_ttn_added_notification(order)
            elif notification_type == 'new_order':
                telegram_notifier.send_new_order_notification(order)
        except Exception as sync_exc:
            logger.warning(
                "Синхронна відправка Telegram нотифікації (%s) для замовлення %s також не вдалася: %s",
                notification_type,
                order_id,
                sync_exc,
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

    if instance.pk:
        try:
            previous_tracking = (Order.objects.only('tracking_number').get(pk=instance.pk).tracking_number or '').strip()
        except Order.DoesNotExist:
            previous_tracking = ''
        instance._ig_ttn_transition = bool(
            (instance.tracking_number or '').strip() and not previous_tracking
        )
    else:
        instance._ig_ttn_transition = bool((instance.tracking_number or '').strip())


@receiver(post_save, sender=Order)
def project_instagram_tracking_transition(sender, instance, created, **kwargs):
    """Project every first non-empty TTN save, not only the admin helper path."""
    if not getattr(instance, '_ig_ttn_transition', False):
        return
    order_id = instance.pk

    def _emit():
        try:
            from management.ig_bot_models import IgLifecycleEvent
            from management.services.ig_lifecycle import dispatch_lifecycle_event, ensure_lifecycle_event

            order = Order.objects.get(pk=order_id)
            event, _created = ensure_lifecycle_event(
                order,
                IgLifecycleEvent.Kind.TTN_CREATED,
                payload={
                    'tracking_number': (order.tracking_number or '').strip(),
                    'order_number': order.order_number,
                },
            )
            if event is not None:
                dispatch_lifecycle_event(event.pk)
        except Exception:
            logger.exception('Unable to project Instagram TTN transition for order %s', order_id)

    transaction.on_commit(_emit)
