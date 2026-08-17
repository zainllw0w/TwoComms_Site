"""Compatibility entrypoint for durable order Telegram intents."""


def send_telegram_notification_task(order_id, notification_type, **kwargs):
    """Persist a status/TTN intent without starting provider I/O."""
    from .payment_side_effects import enqueue_order_telegram_notification

    return enqueue_order_telegram_notification(
        order_id, notification_type, **kwargs
    )


# Совместимость со старыми вызовами Celery-стиля.
send_telegram_notification_task.delay = send_telegram_notification_task
send_telegram_notification_task.apply_async = (
    lambda args=None, kwargs=None, **_kw: send_telegram_notification_task(
        *(args or ()), **(kwargs or {})
    )
)
