"""Celery / cron-задачі warehouse-модуля."""
from __future__ import annotations

import logging

try:
    from celery import shared_task
except ImportError:  # pragma: no cover - Celery optional at import time
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        if args and callable(args[0]):
            return args[0]
        return decorator

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="warehouse.send_evening_reminder")
def send_evening_reminder_task():
    """Розсилає вечірнє нагадування адмінам у Telegram (Storage-бот).

    Запускається через Celery beat або системний cron о 22:00 (Київ).
    """
    from warehouse.models import StockMovement, WarehouseSettings
    from warehouse.services.telegram_storage import (
        get_default_chat_ids,
        send_evening_reminder,
    )

    ws = WarehouseSettings.load()
    if not ws.evening_reminder_enabled:
        logger.info("Storage evening reminder disabled in settings.")
        return {"sent": 0, "skipped": True}

    chat_ids = ws.reminder_chat_ids_list or get_default_chat_ids()
    if not chat_ids:
        logger.info("Storage evening reminder: no chat_ids configured.")
        return {"sent": 0, "skipped": True, "reason": "no_chat_ids"}

    today = timezone.localdate()
    movements = StockMovement.objects.filter(created_at__date=today)
    movements_count = movements.count()
    unverified_count = movements.filter(verified=False).count()

    base_url = getattr(settings, "WAREHOUSE_SUBDOMAIN_URL", "https://storage.twocomms.shop").rstrip("/")
    today_url = f"{base_url}/today/?date={today.isoformat()}"

    sent = send_evening_reminder(
        chat_ids=chat_ids,
        movements_count=movements_count,
        unverified_count=unverified_count,
        today_url=today_url,
        today_str=today.strftime("%d.%m.%Y"),
    )

    ws.last_reminder_sent_at = timezone.now()
    ws.save(update_fields=["last_reminder_sent_at"])

    return {"sent": sent, "movements_count": movements_count}
