"""
Сервіс Instagram Direct бота TwoComms.

Єдина точка логіки, яку використовують і поллер (management-команда), і
webhook-приймач. Облікові дані (DIRECT_API / GEMINI_API) беруться з ENV або з
кастомних значень у налаштуваннях. Відповідь — тестова: на текст, що дорівнює
trigger_text ("1"), бот відповідає reply_text ("Привет, ты написал единичку").

Канали отримання:
- Поллінг: читаємо інбокс @twocomms через page-token (graph.facebook.com),
  знаходимо нові вхідні після reply_after і відповідаємо.
- Webhook: payload з entry[].messaging[].message або entry[].changes[].value.

Обидва канали дедуплікуються за message id (mid), тож подвійних відповідей не
буде, хто б першим не доставив подію.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from management.models import (
    InstagramBotLog,
    InstagramBotProcessedMessage,
    InstagramBotSettings,
)

GRAPH_VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Скільки рядків логу тримаємо (старіші підрізаються).
LOG_KEEP_ROWS = 500


# ---------------------------------------------------------------------------
# Лог-консоль
# ---------------------------------------------------------------------------
def log(level: str, event: str, detail: str = "") -> None:
    try:
        InstagramBotLog.objects.create(level=level, event=event, detail=detail[:4000])
        # Періодична підрізка, щоб таблиця не росла нескінченно.
        if InstagramBotLog.objects.count() > LOG_KEEP_ROWS + 100:
            ids = list(
                InstagramBotLog.objects.order_by("-id").values_list("id", flat=True)[:LOG_KEEP_ROWS]
            )
            if ids:
                InstagramBotLog.objects.exclude(id__in=ids).delete()
    except Exception:
        # Лог не повинен ламати основну логіку.
        pass


# ---------------------------------------------------------------------------
# Облікові дані
# ---------------------------------------------------------------------------
def resolve_direct_token(settings_obj: InstagramBotSettings) -> str:
    if settings_obj.direct_source == InstagramBotSettings.CredSource.CUSTOM:
        return (settings_obj.custom_direct_token or "").strip()
    return os.environ.get("DIRECT_API", "").strip()


def resolve_gemini_key(settings_obj: InstagramBotSettings) -> str:
    if settings_obj.gemini_source == InstagramBotSettings.CredSource.CUSTOM:
        return (settings_obj.custom_gemini_key or "").strip()
    return os.environ.get("GEMINI_API", "").strip()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _http(url: str, *, data: bytes | None = None, timeout: int = 20):
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # network / timeout
        return -1, repr(exc)


def get_page_token(settings_obj: InstagramBotSettings) -> str:
    """Page access token сторінки з user-токена DIRECT_API."""
    token = resolve_direct_token(settings_obj)
    if not token:
        return ""
    code, body = _http(
        f"{GRAPH}/me/accounts?fields=name,access_token&access_token={token}"
    )
    if code != 200:
        log("error", "page_token", f"HTTP {code}: {body[:300]}")
        return ""
    try:
        for page in json.loads(body).get("data", []):
            if str(page.get("id")) == settings_obj.page_id:
                return page.get("access_token") or ""
    except Exception as exc:
        log("error", "page_token_parse", repr(exc))
    return ""


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------
def send_text(settings_obj: InstagramBotSettings, recipient_id: str, text: str) -> bool:
    page_token = get_page_token(settings_obj)
    if not page_token:
        log("error", "send", "Немає page-token (перевірте DIRECT_API).")
        return False
    body = json.dumps(
        {
            "recipient": {"id": recipient_id},
            "message": {"text": text},
            "messaging_type": "RESPONSE",
        }
    ).encode("utf-8")
    code, resp = _http(
        f"{GRAPH}/{settings_obj.page_id}/messages?access_token={page_token}",
        data=body,
    )
    if code == 200:
        log("success", "reply_sent", f"→ {recipient_id}: {text}")
        return True
    log("error", "send", f"HTTP {code}: {resp[:300]}")
    return False


# ---------------------------------------------------------------------------
# Core: обробка одного вхідного повідомлення (спільне для poll і webhook)
# ---------------------------------------------------------------------------
def handle_inbound(
    settings_obj: InstagramBotSettings,
    *,
    sender_id: str,
    text: str,
    mid: str,
    created_at=None,
    source: str = "poll",
) -> bool:
    """Повертає True, якщо була відправлена відповідь."""
    text = (text or "").strip()
    sender_id = (sender_id or "").strip()
    if not sender_id or not text:
        return False

    # Не відповідаємо самим собі (наш IG-акаунт).
    if sender_id == settings_obj.ig_user_id:
        return False

    # Дедуп за mid.
    if mid:
        try:
            with transaction.atomic():
                InstagramBotProcessedMessage.objects.create(mid=mid)
        except IntegrityError:
            return False  # вже оброблено

    settings_obj.last_inbound_at = timezone.now()

    if text == settings_obj.trigger_text:
        log("info", "trigger", f"[{source}] від {sender_id}: {text!r} → відповідаю")
        ok = send_text(settings_obj, sender_id, settings_obj.reply_text)
        if ok:
            settings_obj.replies_count = (settings_obj.replies_count or 0) + 1
            settings_obj.last_reply_at = timezone.now()
        settings_obj.save(
            update_fields=["last_inbound_at", "replies_count", "last_reply_at"]
        )
        return ok

    log("info", "ignored", f"[{source}] від {sender_id}: {text!r} (не тригер)")
    settings_obj.save(update_fields=["last_inbound_at"])
    return False


# ---------------------------------------------------------------------------
# Webhook payload parsing
# ---------------------------------------------------------------------------
def handle_webhook_payload(settings_obj: InstagramBotSettings, payload: dict) -> None:
    for entry in payload.get("entry", []) or []:
        for event in entry.get("messaging", []) or []:
            msg = event.get("message") or {}
            if not msg or msg.get("is_echo"):
                continue
            handle_inbound(
                settings_obj,
                sender_id=(event.get("sender") or {}).get("id", ""),
                text=msg.get("text", ""),
                mid=msg.get("mid", ""),
                source="webhook",
            )
        for change in entry.get("changes", []) or []:
            if change.get("field") != "messages":
                continue
            value = change.get("value") or {}
            msg = value.get("message") or {}
            if not msg or msg.get("is_echo"):
                continue
            handle_inbound(
                settings_obj,
                sender_id=(value.get("sender") or {}).get("id", ""),
                text=msg.get("text", ""),
                mid=msg.get("mid", ""),
                source="webhook",
            )


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
def _parse_ig_time(raw: str):
    """'2026-06-14T00:23:26+0000' -> aware datetime."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None


def poll_once(settings_obj: InstagramBotSettings | None = None) -> dict:
    """Один цикл опитування інбоксу. Повертає короткий підсумок."""
    settings_obj = settings_obj or InstagramBotSettings.load()
    settings_obj.heartbeat_at = timezone.now()
    settings_obj.last_poll_at = timezone.now()
    settings_obj.save(update_fields=["heartbeat_at", "last_poll_at"])

    if not settings_obj.is_enabled:
        return {"ok": True, "enabled": False, "handled": 0}

    page_token = get_page_token(settings_obj)
    if not page_token:
        return {"ok": False, "error": "no_page_token", "handled": 0}

    # Останні діалоги (платформа instagram).
    code, body = _http(
        f"{GRAPH}/{settings_obj.page_id}/conversations?platform=instagram"
        f"&fields=id&limit=10&access_token={page_token}"
    )
    if code != 200:
        settings_obj.last_error = f"conversations HTTP {code}: {body[:200]}"
        settings_obj.save(update_fields=["last_error"])
        log("error", "poll_conversations", settings_obj.last_error)
        return {"ok": False, "error": "conversations", "handled": 0}

    try:
        conv_ids = [c["id"] for c in json.loads(body).get("data", [])]
    except Exception as exc:
        log("error", "poll_parse", repr(exc))
        return {"ok": False, "error": "parse", "handled": 0}

    reply_after = settings_obj.reply_after or settings_obj.last_started_at
    handled = 0

    for cid in conv_ids:
        code, body = _http(
            f"{GRAPH}/{cid}?fields=messages.limit(8)"
            f"{{message,from,created_time,id}}&access_token={page_token}"
        )
        if code != 200:
            continue
        try:
            messages = json.loads(body).get("messages", {}).get("data", [])
        except Exception:
            continue
        # Від старіших до новіших.
        for m in reversed(messages):
            sender = (m.get("from") or {}).get("id", "")
            if not sender or sender == settings_obj.ig_user_id:
                continue
            created = _parse_ig_time(m.get("created_time", ""))
            if reply_after and created and created <= reply_after:
                continue
            if handle_inbound(
                settings_obj,
                sender_id=sender,
                text=m.get("message", ""),
                mid=m.get("id", ""),
                created_at=created,
                source="poll",
            ):
                handled += 1

    return {"ok": True, "enabled": True, "handled": handled, "conversations": len(conv_ids)}


# ---------------------------------------------------------------------------
# Start / Stop
# ---------------------------------------------------------------------------
def start_bot() -> InstagramBotSettings:
    s = InstagramBotSettings.load()
    s.is_enabled = True
    s.last_started_at = timezone.now()
    # Відповідаємо лише на повідомлення, що прийдуть ПІСЛЯ старту.
    s.reply_after = timezone.now()
    s.last_error = ""
    s.save(
        update_fields=["is_enabled", "last_started_at", "reply_after", "last_error"]
    )
    log("success", "start", "Бот запущено, очікую повідомлення.")
    return s


def stop_bot() -> InstagramBotSettings:
    s = InstagramBotSettings.load()
    s.is_enabled = False
    s.last_stopped_at = timezone.now()
    s.save(update_fields=["is_enabled", "last_stopped_at"])
    log("warning", "stop", "Бот зупинено.")
    return s


def status_snapshot() -> dict:
    s = InstagramBotSettings.load()
    now = timezone.now()
    hb = s.heartbeat_at
    # «Живий», якщо heartbeat був нещодавно (поллер тікає).
    alive = bool(hb and (now - hb).total_seconds() < 90)
    return {
        "is_enabled": s.is_enabled,
        "alive": alive,
        "running": s.is_enabled and alive,
        "heartbeat_at": hb.isoformat() if hb else "",
        "last_poll_at": s.last_poll_at.isoformat() if s.last_poll_at else "",
        "last_inbound_at": s.last_inbound_at.isoformat() if s.last_inbound_at else "",
        "last_reply_at": s.last_reply_at.isoformat() if s.last_reply_at else "",
        "replies_count": s.replies_count,
        "last_error": s.last_error,
        "direct_source": s.direct_source,
        "gemini_source": s.gemini_source,
        "trigger_text": s.trigger_text,
        "reply_text": s.reply_text,
        "poll_interval_seconds": s.poll_interval_seconds,
    }
