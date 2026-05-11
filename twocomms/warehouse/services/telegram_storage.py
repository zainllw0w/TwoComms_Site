"""Storage-бот: вечірнє нагадування + обробка callback'ів.

Окремий від основного бота. Має одну головну задачу: о 22:00 (Київ) питати
адмінів «Чи були сьогодні зміни?». Якщо так — давати посилання на сторінку
сьогоднішніх рухів для верифікації.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Iterable

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}"


def get_bot_token() -> str:
    return os.environ.get("TELEGRAM_STORAGE_BOT_TOKEN") or getattr(
        settings, "TELEGRAM_STORAGE_BOT_TOKEN", ""
    )


def get_default_chat_ids() -> list[str]:
    """Default chat ids from env or settings (fallback)."""
    raw = os.environ.get("TELEGRAM_STORAGE_CHAT_IDS", "") or getattr(
        settings, "TELEGRAM_STORAGE_CHAT_IDS", ""
    )
    if not raw:
        return []
    return [c.strip() for c in str(raw).replace(";", ",").split(",") if c.strip()]


def _post(method: str, payload: dict, *, timeout: int = 10):
    token = get_bot_token()
    if not token:
        logger.warning("TELEGRAM_STORAGE_BOT_TOKEN не задано — пропуск %s", method)
        return None
    url = API_BASE.format(token=token) + f"/{method}"
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        data = response.json()
        if not data.get("ok"):
            logger.warning("Storage TG %s failed: %s", method, data)
        return data
    except Exception as exc:
        logger.warning("Storage TG %s exception: %s", method, exc)
        return None


def send_message(
    chat_id: str | int,
    text: str,
    *,
    reply_markup: dict | None = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> dict | None:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _post("sendMessage", payload)


def answer_callback(callback_query_id: str, text: str = "", *, show_alert: bool = False) -> dict | None:
    payload = {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": show_alert,
    }
    return _post("answerCallbackQuery", payload)


def edit_message_text(
    chat_id: str | int,
    message_id: int,
    text: str,
    *,
    reply_markup: dict | None = None,
    parse_mode: str = "HTML",
) -> dict | None:
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _post("editMessageText", payload)


def set_webhook(url: str, *, secret_token: str | None = None) -> dict | None:
    payload = {"url": url, "allowed_updates": ["message", "callback_query"]}
    if secret_token:
        payload["secret_token"] = secret_token
    return _post("setWebhook", payload)


def get_webhook_info() -> dict | None:
    return _post("getWebhookInfo", {})


# ---------------------------------------------------------------------------
# High-level operations
# ---------------------------------------------------------------------------


def build_evening_reminder_text(
    *,
    movements_count: int,
    unverified_count: int,
    today_str: str,
) -> str:
    if movements_count == 0:
        return (
            f"🌙 <b>Вечірня перевірка складу</b>\n"
            f"Дата: {today_str}\n\n"
            f"Сьогодні рухів не зафіксовано.\n"
            f"Чи були сьогодні зміни на складі, що ще не введено в систему?"
        )
    return (
        f"🌙 <b>Вечірня перевірка складу</b>\n"
        f"Дата: {today_str}\n\n"
        f"Сьогодні зафіксовано <b>{movements_count}</b> рухів "
        f"(не перевірено: <b>{unverified_count}</b>).\n\n"
        f"Чи всі зміни перевірено та внесено коректно?"
    )


def build_evening_reminder_keyboard(today_url: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Все ок", "callback_data": "verify_all_today"},
                {"text": "📝 Перевірити", "url": today_url},
            ],
        ]
    }


def send_evening_reminder(
    *,
    chat_ids: Iterable[str],
    movements_count: int,
    unverified_count: int,
    today_url: str,
    today_str: str,
) -> int:
    text = build_evening_reminder_text(
        movements_count=movements_count,
        unverified_count=unverified_count,
        today_str=today_str,
    )
    keyboard = build_evening_reminder_keyboard(today_url)
    sent = 0
    for chat_id in chat_ids:
        result = send_message(chat_id, text, reply_markup=keyboard)
        if result and result.get("ok"):
            sent += 1
    return sent
