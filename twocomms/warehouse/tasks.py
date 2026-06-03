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
        get_admin_chat_ids,
        send_evening_reminder,
    )

    ws = WarehouseSettings.load()
    if not ws.evening_reminder_enabled:
        logger.info("Storage evening reminder disabled in settings.")
        return {"sent": 0, "skipped": True}

    chat_ids = get_admin_chat_ids()
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


@shared_task(name="warehouse.send_storage_report")
def send_storage_report_task(force_period: str | None = None):
    """Надсилає налаштований звіт по складу (пуш + дублювання в Telegram).

    Частота й вміст беруться з ``WarehouseSettings``. Запускається cron'ом
    щодня; для щотижневого режиму звіт надсилається лише у потрібний день.

    ``force_period`` ('daily'|'weekly') — для ручного тесту з UI.
    """
    from datetime import timedelta

    from warehouse.models import (
        ConsumableItem,
        StockMovement,
        WarehouseSettings,
    )
    from warehouse.services.finance import total_frozen_value
    from warehouse.services.telegram_storage import get_admin_chat_ids, send_report

    ws = WarehouseSettings.load()
    if not ws.push_enabled:
        logger.info("Storage report disabled (push_enabled=False).")
        return {"sent": 0, "skipped": True, "reason": "disabled"}

    frequency = force_period or ws.push_frequency
    today = timezone.localdate()

    if frequency == WarehouseSettings.Frequency.WEEKLY:
        if force_period is None and today.weekday() != ws.push_weekly_day:
            return {"sent": 0, "skipped": True, "reason": "not_report_day"}
        start = today - timedelta(days=6)
        period_label = f"тиждень {start.strftime('%d.%m')}–{today.strftime('%d.%m.%Y')}"
    else:
        start = today
        period_label = today.strftime("%d.%m.%Y")

    movements = StockMovement.objects.filter(
        created_at__date__gte=start, created_at__date__lte=today
    )
    from django.db.models import F

    stats = {
        "movements_count": movements.count(),
        "unverified_count": movements.filter(verified=False).count(),
        "low_stock_count": ConsumableItem.objects.filter(
            quantity__lte=F("min_stock_alert")
        ).count(),
        "frozen_value": total_frozen_value(),
        "prints_qty": 0,
    }
    try:
        from warehouse.models import PrintColorVariant
        from django.db.models import Sum

        stats["prints_qty"] = (
            PrintColorVariant.objects.aggregate(t=Sum("quantity"))["t"] or 0
        )
    except Exception:  # pragma: no cover
        pass

    blocks = ws.get_push_content()
    base_url = getattr(settings, "WAREHOUSE_SUBDOMAIN_URL", "https://storage.twocomms.shop").rstrip("/")

    sent = 0
    if ws.push_to_telegram:
        chat_ids = get_admin_chat_ids()
        if chat_ids:
            sent = send_report(
                chat_ids=chat_ids,
                blocks=blocks,
                period_label=period_label,
                stats=stats,
                report_url=f"{base_url}/",
            )

    return {"sent": sent, "frequency": frequency, "blocks": blocks}
