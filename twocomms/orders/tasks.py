import logging
from celery import shared_task
from .models import Order
from .telegram_notifications import telegram_notifier

logger = logging.getLogger(__name__)

@shared_task
def send_telegram_notification_task(order_id, notification_type, **kwargs):
    """
    Celery task to send Telegram notifications.
    notification_type: 'new_order', 'status_update', 'ttn_added'
    """
    try:
        order = Order.objects.get(id=order_id)
        
        if notification_type == 'new_order':
            telegram_notifier.send_new_order_notification(order)
        
        elif notification_type == 'status_update':
            old_status = kwargs.get('old_status')
            new_status = kwargs.get('new_status')
            if old_status and new_status:
                telegram_notifier.send_order_status_update(order, old_status, new_status)
                
        elif notification_type == 'ttn_added':
            telegram_notifier.send_ttn_added_notification(order)
            
        logger.info(f"Telegram notification '{notification_type}' sent for order {order_id}")
        
    except Order.DoesNotExist:
        logger.warning(f"Order {order_id} not found for Telegram notification")
    except Exception as e:
        logger.error(f"Error sending Telegram notification for order {order_id}: {e}", exc_info=True)
