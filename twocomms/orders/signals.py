"""
Сигналы для уведомлений о заказах
"""
import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from django.db.models.signals import post_save, pre_save
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



@receiver(pre_save, sender=WholesaleInvoice)
def track_wholesale_invoice_payment(sender, instance, **kwargs):
    if not getattr(instance, 'pk', None):
        return
    try:
        old_instance = WholesaleInvoice.objects.only('payment_status').get(pk=instance.pk)
    except WholesaleInvoice.DoesNotExist:
        return

    instance._mgmt_just_paid = (old_instance.payment_status != 'paid' and instance.payment_status == 'paid')


@receiver(post_save, sender=WholesaleInvoice)
def award_manager_commission_for_paid_wholesale_invoice(sender, instance, created, **kwargs):
    just_paid = bool(getattr(instance, '_mgmt_just_paid', False) or (created and instance.payment_status == 'paid'))
    if not just_paid:
        return

    manager = getattr(instance, 'created_by', None)
    if not manager:
        return

    try:
        from management.models import ManagerCommissionAccrual
    except Exception:
        return

    try:
        prof = manager.userprofile
        percent_val = getattr(prof, 'manager_commission_percent', None) or 0
    except Exception:
        percent_val = 0

    try:
        percent = Decimal(str(percent_val))
    except Exception:
        percent = Decimal('0')

    try:
        base_amount = Decimal(str(getattr(instance, 'total_amount', 0) or 0))
    except Exception:
        base_amount = Decimal('0')

    if percent < 0:
        percent = Decimal('0')
    if base_amount < 0:
        base_amount = Decimal('0')

    amount = (base_amount * percent / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if amount < 0:
        amount = Decimal('0')

    frozen_until = timezone.now() + timedelta(days=14)

    try:
        ManagerCommissionAccrual.objects.get_or_create(
            invoice=instance,
            defaults={
                'owner': manager,
                'base_amount': base_amount,
                'percent': percent,
                'amount': amount,
                'frozen_until': frozen_until,
            },
        )
    except Exception as exc:
        logger.warning(
            'Failed to create commission accrual for WholesaleInvoice %s: %s',
            getattr(instance, 'pk', None),
            exc,
            exc_info=True,
        )
