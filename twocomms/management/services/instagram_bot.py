"""
Сервіс Instagram Direct бота TwoComms.

Єдина точка логіки для поллера (management-команда) і webhook-приймача.

Канали отримання:
- Поллінг: читаємо інбокс @twocomms через page-token (graph.facebook.com),
  знаходимо нові вхідні після reply_after і відповідаємо.
- Webhook: payload з entry[].messaging[].message (працює лише в Live-режимі).

Відповідь:
- AI-режим (ai_enabled): вільна розмова через Gemini (модель gemini_model)
  з урахуванням історії переписки та system_prompt («правило»).
- Простий режим: текст, що дорівнює trigger_text -> reply_text.

Захист: відповідаємо лише відправникам зі списку allowed_senders (щоб на
тесті не писати реальним клієнтам). Дедуп за message id (mid).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from management.models import (
    InstagramBotLog,
    InstagramBotProcessedMessage,
    InstagramBotSettings,
)

GRAPH_VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
GENAI = "https://generativelanguage.googleapis.com/v1beta"

LOG_KEEP_ROWS = 500
HISTORY_LIMIT = 8  # скільки останніх повідомлень діалогу даємо моделі

# Кеш, щоб НЕ робити важкі виклики в кожному циклі.
PAGE_TOKEN_TTL = 1200          # page-token живе довго
CONV_IDS_TTL = 180             # список діалогів /conversations дуже повільний
                               # (~20-27 c) — оновлюємо не частіше цього
HTTP_TIMEOUT = 12              # короткий таймаут у гарячому циклі
CONV_LIST_TIMEOUT = 30         # тільки для рідкісного оновлення списку діалогів


# ---------------------------------------------------------------------------
# Лог-консоль
# ---------------------------------------------------------------------------
def log(level: str, event: str, detail: str = "") -> None:
    try:
        InstagramBotLog.objects.create(level=level, event=event, detail=(detail or "")[:4000])
        if InstagramBotLog.objects.count() > LOG_KEEP_ROWS + 100:
            ids = list(
                InstagramBotLog.objects.order_by("-id").values_list("id", flat=True)[:LOG_KEEP_ROWS]
            )
            if ids:
                InstagramBotLog.objects.exclude(id__in=ids).delete()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Облікові дані
# ---------------------------------------------------------------------------
def resolve_direct_token(s: InstagramBotSettings) -> str:
    if s.direct_source == InstagramBotSettings.CredSource.CUSTOM:
        return (s.custom_direct_token or "").strip()
    return os.environ.get("DIRECT_API", "").strip()


def resolve_gemini_key(s: InstagramBotSettings) -> str:
    if s.gemini_source == InstagramBotSettings.CredSource.CUSTOM:
        return (s.custom_gemini_key or "").strip()
    return os.environ.get("GEMINI_API", "").strip()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _http(url: str, *, data: bytes | None = None, timeout: int = HTTP_TIMEOUT):
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:
        return -1, repr(exc)


def get_page_token(s: InstagramBotSettings, *, force: bool = False) -> str:
    token = resolve_direct_token(s)
    if not token:
        return ""
    ck = "ig_bot_page_token"
    if not force:
        cached = cache.get(ck)
        if cached:
            return cached
    code, body = _http(
        f"{GRAPH}/me/accounts?fields=name,access_token&access_token={token}",
        timeout=HTTP_TIMEOUT,
    )
    if code != 200:
        log("error", "page_token", f"HTTP {code}: {body[:200]}")
        return ""
    try:
        for page in json.loads(body).get("data", []):
            if str(page.get("id")) == s.page_id:
                pt = page.get("access_token") or ""
                if pt:
                    cache.set(ck, pt, PAGE_TOKEN_TTL)
                return pt
    except Exception as exc:
        log("error", "page_token_parse", repr(exc))
    return ""


def refresh_conv_ids(s: InstagramBotSettings, page_token: str) -> list[str]:
    """Важкий виклик /conversations (~20-27 c). Викликається РІДКО і поза
    гарячим циклом (фоновий потік демона), щоб не блокувати опитування."""
    code, body = _http(
        f"{GRAPH}/{s.page_id}/conversations?platform=instagram"
        f"&fields=id&limit=10&access_token={page_token}",
        timeout=CONV_LIST_TIMEOUT,
    )
    if code != 200:
        stale = cache.get("ig_bot_conv_ids")
        if stale is not None:
            return stale
        log("warning", "conversations", f"HTTP {code}: {body[:150]}")
        return []
    try:
        ids = [c["id"] for c in json.loads(body).get("data", [])]
        cache.set("ig_bot_conv_ids", ids, 3600)
        return ids
    except Exception:
        return cache.get("ig_bot_conv_ids") or []


def get_conv_ids_cached() -> list[str] | None:
    return cache.get("ig_bot_conv_ids")


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------
def send_text(s: InstagramBotSettings, recipient_id: str, text: str) -> bool:
    page_token = get_page_token(s)
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
    code, resp = _http(f"{GRAPH}/{s.page_id}/messages?access_token={page_token}", data=body)
    if code == 200:
        log("success", "reply_sent", f"→ {recipient_id}: {text[:300]}")
        return True
    log("error", "send", f"HTTP {code}: {resp[:300]}")
    return False


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
def gemini_generate(s: InstagramBotSettings, history: list[dict]) -> str | None:
    """history: [{'role': 'user'|'model', 'text': str}, ...] у хронологічному порядку."""
    key = resolve_gemini_key(s)
    if not key:
        log("error", "gemini", "Немає GEMINI ключа.")
        return None
    contents = [{"role": h["role"], "parts": [{"text": h["text"]}]} for h in history if h.get("text")]
    if not contents:
        return None
    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 600},
    }
    if (s.system_prompt or "").strip():
        payload["system_instruction"] = {"parts": [{"text": s.system_prompt.strip()}]}
    model = (s.gemini_model or "gemini-2.5-flash").strip()
    code, body = _http(
        f"{GENAI}/models/{model}:generateContent?key={key}",
        data=json.dumps(payload).encode("utf-8"),
        timeout=40,
    )
    if code != 200:
        log("error", "gemini", f"HTTP {code}: {body[:300]}")
        return None
    try:
        data = json.loads(body)
        cand = (data.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            log("warning", "gemini_empty", f"finishReason={cand.get('finishReason')}")
            return None
        return text
    except Exception as exc:
        log("error", "gemini_parse", repr(exc))
        return None


# ---------------------------------------------------------------------------
# Allowlist / dedup
# ---------------------------------------------------------------------------
def allowed_sender_ids(s: InstagramBotSettings) -> set[str]:
    raw = s.allowed_senders or ""
    ids = {p.strip() for p in raw.replace(",", " ").replace("\n", " ").split() if p.strip()}
    return ids


def _is_allowed(s: InstagramBotSettings, sender_id: str) -> bool:
    ids = allowed_sender_ids(s)
    if not ids:
        return True  # порожній список = всі (небезпечно, але дозволено явно)
    return sender_id in ids


def _mark_processed(mid: str) -> bool:
    """True, якщо mid новий (ще не оброблений)."""
    if not mid:
        return True
    try:
        with transaction.atomic():
            InstagramBotProcessedMessage.objects.create(mid=mid)
        return True
    except IntegrityError:
        return False


# ---------------------------------------------------------------------------
# Core: відповідь на одне вхідне повідомлення
# ---------------------------------------------------------------------------
def respond(
    s: InstagramBotSettings,
    *,
    sender_id: str,
    text: str,
    mid: str,
    history: list[dict] | None = None,
    source: str = "poll",
) -> bool:
    text = (text or "").strip()
    sender_id = (sender_id or "").strip()
    if not sender_id or not text:
        return False
    if sender_id == s.ig_user_id:
        return False  # власні повідомлення

    if not _is_allowed(s, sender_id):
        log("info", "skip_not_allowed", f"[{source}] {sender_id}: поза білим списком")
        return False

    if not _mark_processed(mid):
        return False  # вже оброблено

    s.last_inbound_at = timezone.now()
    s.save(update_fields=["last_inbound_at"])

    # Визначаємо текст відповіді.
    if s.ai_enabled:
        hist = history or [{"role": "user", "text": text}]
        log("info", "incoming", f"[{source}] {sender_id}: {text[:200]}")
        reply = gemini_generate(s, hist)
        if not reply:
            return False
    else:
        if text != s.trigger_text:
            log("info", "ignored", f"[{source}] {sender_id}: {text[:80]!r} (не тригер)")
            return False
        log("info", "trigger", f"[{source}] {sender_id}: {text!r} → відповідаю")
        reply = s.reply_text

    ok = send_text(s, sender_id, reply)
    if ok:
        s.replies_count = (s.replies_count or 0) + 1
        s.last_reply_at = timezone.now()
        s.save(update_fields=["replies_count", "last_reply_at"])
    return ok


# ---------------------------------------------------------------------------
# Webhook payload (single-turn; повноцінно запрацює в Live-режимі)
# ---------------------------------------------------------------------------
def handle_webhook_payload(s: InstagramBotSettings, payload: dict) -> None:
    def _one(sender_id, msg):
        if not msg or msg.get("is_echo"):
            return
        respond(
            s,
            sender_id=sender_id,
            text=msg.get("text", ""),
            mid=msg.get("mid", ""),
            history=[{"role": "user", "text": msg.get("text", "")}],
            source="webhook",
        )

    for entry in payload.get("entry", []) or []:
        for event in entry.get("messaging", []) or []:
            _one((event.get("sender") or {}).get("id", ""), event.get("message") or {})
        for change in entry.get("changes", []) or []:
            if change.get("field") == "messages":
                value = change.get("value") or {}
                _one((value.get("sender") or {}).get("id", ""), value.get("message") or {})


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
def _parse_ig_time(raw: str):
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None


def poll_once(s: InstagramBotSettings | None = None) -> dict:
    s = s or InstagramBotSettings.load()
    now = timezone.now()
    s.heartbeat_at = now
    s.last_poll_at = now
    s.save(update_fields=["heartbeat_at", "last_poll_at"])

    if not s.is_enabled:
        return {"ok": True, "enabled": False, "handled": 0}

    page_token = get_page_token(s)
    if not page_token:
        return {"ok": False, "error": "no_page_token", "handled": 0}

    conv_ids = get_conv_ids_cached()
    if conv_ids is None:
        # Перший раз (або кеш порожній) — посіяти список (повільно, одноразово).
        conv_ids = refresh_conv_ids(s, page_token)
    if not conv_ids:
        return {"ok": True, "enabled": True, "handled": 0, "conversations": 0}

    if s.last_error:
        s.last_error = ""
        s.save(update_fields=["last_error"])

    reply_after = s.reply_after or s.last_started_at
    handled = 0

    for cid in conv_ids:
        code, body = _http(
            f"{GRAPH}/{cid}?fields=messages.limit({HISTORY_LIMIT})"
            f"{{message,from,created_time,id}}&access_token={page_token}",
            timeout=HTTP_TIMEOUT,
        )
        if code != 200:
            continue
        try:
            msgs = json.loads(body).get("messages", {}).get("data", [])
        except Exception:
            continue
        if not msgs:
            continue

        latest = msgs[0]  # найновіше
        latest_sender = (latest.get("from") or {}).get("id", "")
        if not latest_sender or latest_sender == s.ig_user_id:
            continue
        created = _parse_ig_time(latest.get("created_time", ""))
        if reply_after and created and created <= reply_after:
            continue

        history = []
        for m in reversed(msgs):
            t = (m.get("message") or "").strip()
            if not t:
                continue
            role = "model" if (m.get("from") or {}).get("id") == s.ig_user_id else "user"
            history.append({"role": role, "text": t})

        if respond(
            s,
            sender_id=latest_sender,
            text=latest.get("message", ""),
            mid=latest.get("id", ""),
            history=history,
            source="poll",
        ):
            handled += 1

    return {"ok": True, "enabled": True, "handled": handled, "conversations": len(conv_ids)}


# ---------------------------------------------------------------------------
# Start / Stop (ідемпотентні — не логують повторно)
# ---------------------------------------------------------------------------
def start_bot() -> InstagramBotSettings:
    s = InstagramBotSettings.load()
    was = s.is_enabled
    s.is_enabled = True
    s.last_started_at = timezone.now()
    s.reply_after = timezone.now()
    s.last_error = ""
    s.save(update_fields=["is_enabled", "last_started_at", "reply_after", "last_error"])
    if not was:
        log("success", "start", "Бот запущено, очікую повідомлення.")
    return s


def stop_bot() -> InstagramBotSettings:
    s = InstagramBotSettings.load()
    was = s.is_enabled
    s.is_enabled = False
    s.last_stopped_at = timezone.now()
    s.save(update_fields=["is_enabled", "last_stopped_at"])
    if was:
        log("warning", "stop", "Бот зупинено.")
    return s


def status_snapshot() -> dict:
    s = InstagramBotSettings.load()
    now = timezone.now()
    hb = s.heartbeat_at
    alive = bool(hb and (now - hb).total_seconds() < 90)
    # Окремий heartbeat демона (його пише сам процес-демон).
    dhb = cache.get("ig_bot_daemon_hb")
    daemon_online = bool(dhb and (time.time() - float(dhb)) < 45)
    return {
        "is_enabled": s.is_enabled,
        "alive": alive,
        "daemon_online": daemon_online,
        "running": s.is_enabled and (daemon_online or alive),
        "heartbeat_at": hb.isoformat() if hb else "",
        "last_poll_at": s.last_poll_at.isoformat() if s.last_poll_at else "",
        "last_inbound_at": s.last_inbound_at.isoformat() if s.last_inbound_at else "",
        "last_reply_at": s.last_reply_at.isoformat() if s.last_reply_at else "",
        "replies_count": s.replies_count,
        "last_error": s.last_error,
        "direct_source": s.direct_source,
        "gemini_source": s.gemini_source,
        "ai_enabled": s.ai_enabled,
        "gemini_model": s.gemini_model,
        "trigger_text": s.trigger_text,
        "reply_text": s.reply_text,
        "poll_interval_seconds": s.poll_interval_seconds,
    }
