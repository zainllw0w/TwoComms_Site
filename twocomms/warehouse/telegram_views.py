"""Webhook та допоміжні endpoint'и для Storage Telegram-бота."""
from __future__ import annotations

import hmac
import json
import logging
import os

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from warehouse.models import StockMovement, WarehouseSettings
from warehouse.services.telegram_storage import (
    answer_callback,
    edit_message_text,
    get_default_chat_ids,
)

logger = logging.getLogger(__name__)


def _get_webhook_secret() -> str:
    return (
        os.environ.get("TELEGRAM_STORAGE_WEBHOOK_SECRET")
        or getattr(settings, "TELEGRAM_STORAGE_WEBHOOK_SECRET", "")
        or ""
    )


@csrf_exempt
@require_POST
def storage_telegram_webhook(request, secret: str):
    """Webhook endpoint для Storage-бота."""
    expected = _get_webhook_secret()
    if expected and not hmac.compare_digest(str(secret), expected):
        return HttpResponse(status=403)

    # Telegram also supports X-Telegram-Bot-Api-Secret-Token header verification.
    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if expected and header_secret and not hmac.compare_digest(header_secret, expected):
        return HttpResponse(status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)

    callback = payload.get("callback_query")
    if callback:
        return _handle_callback(callback)

    message = payload.get("message")
    if message:
        return _handle_message(message)

    return JsonResponse({"ok": True, "skipped": True})


def _handle_callback(callback: dict):
    callback_id = callback.get("id")
    data = callback.get("data") or ""
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")

    if data == "verify_all_today":
        today = timezone.localdate()
        qs = StockMovement.objects.filter(created_at__date=today, verified=False)
        count = qs.update(verified=True, verified_at=timezone.now())

        if callback_id:
            answer_callback(callback_id, f"Перевірено {count} рухів")
        if chat_id and message_id:
            edit_message_text(
                chat_id,
                message_id,
                f"✅ <b>Перевірено всі рухи за день</b>\n\nВідмічено: {count}",
                reply_markup={"inline_keyboard": []},
            )
        return JsonResponse({"ok": True})

    if callback_id:
        answer_callback(callback_id, "Невідома дія")
    return JsonResponse({"ok": True})


def _handle_message(message: dict):
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if text.startswith("/start"):
        from warehouse.services.telegram_storage import send_message

        send_message(
            chat_id,
            (
                "👋 Привіт! Це Storage-бот TwoComms.\n\n"
                "Я нагадую о 22:00 (Київ) перевірити сьогоднішні зміни на складі.\n"
                "Щоб перейти до інтерфейсу складу — натисни кнопку нижче."
            ),
            reply_markup={
                "inline_keyboard": [
                    [
                        {
                            "text": "🏪 Відкрити склад",
                            "url": "https://storage.twocomms.shop/",
                        }
                    ]
                ]
            },
        )

        # Auto-register chat_id if it's not yet in settings.
        try:
            ws = WarehouseSettings.load()
            ids = ws.reminder_chat_ids_list
            if str(chat_id) not in ids:
                ids.append(str(chat_id))
                ws.evening_reminder_chat_ids = ",".join(ids)
                ws.save(update_fields=["evening_reminder_chat_ids"])
        except Exception as exc:
            logger.warning("Failed to auto-register chat_id %s: %s", chat_id, exc)

    return JsonResponse({"ok": True})


@require_GET
def storage_install_pwa(request):
    """Сторінка-інструкція як додати склад на робочий стіл (PWA install)."""
    from django.shortcuts import render

    return render(request, "warehouse/install.html")
