"""
Endpoints для верифікації Telegram-контакту користувача через бота.

Сценарій:
1. Користувач на сторінці кастомного принта обирає канал «Telegram» і натискає
   «Підтвердити Telegram через бота».
2. JS викликає POST `/custom-print/telegram-verify/start/`. Сервер створює
   `TelegramVerificationSession` (TTL 5 хв) і повертає `deep_link_url`.
3. JS відкриває `t.me/<bot>?start=verify_<token>` у новій вкладці й починає
   опитувати GET `/custom-print/telegram-verify/status/?token=...` кожні 2 сек.
4. У боті користувач тапає «📱 Поділитися номером», бот зберігає phone +
   telegram_id у сесії й помічає її verified.
5. Поллінг ловить status=verified, форма автоматично заповнюється
   `contact_value` (Telegram username) та зберігає phone у hidden-полях лида.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import time
from datetime import timedelta
from urllib.parse import quote

import requests
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from accounts.models import TelegramVerificationSession


logger = logging.getLogger(__name__)


VERIFICATION_TTL_SECONDS = 5 * 60
MAX_ACTIVE_SESSIONS_PER_KEY = 5  # rate-limit creation per session_key

_BOT_USERNAME_CACHE = {"value": "", "fetched_at": 0.0, "token": ""}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _get_bot_token() -> str:
    return (
        os.environ.get("TELEGRAM_BOT_TOKEN")
        or getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        or ""
    )


def _get_bot_username() -> str:
    """Возвращает username главного бота. Сначала проверяем env, потом
    запрашиваем `getMe` (с кэшем на 10 минут)."""
    name = (
        os.environ.get("TELEGRAM_BOT_USERNAME")
        or getattr(settings, "TELEGRAM_BOT_USERNAME", "")
        or ""
    ).strip().lstrip("@")
    if name:
        return name

    token = _get_bot_token()
    if not token:
        return ""

    now = time.time()
    cache = _BOT_USERNAME_CACHE
    if cache["value"] and cache["token"] == token and now - cache["fetched_at"] < 600:
        return cache["value"]

    try:
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=4)
        data = resp.json()
        if data.get("ok") and data.get("result", {}).get("username"):
            username = data["result"]["username"].lstrip("@")
            _BOT_USERNAME_CACHE.update({"value": username, "fetched_at": now, "token": token})
            return username
    except Exception as exc:
        logger.warning("getMe failed: %s", exc)
    return ""


def _ensure_session_key(request) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ""


def _expire_old_sessions(session_key: str):
    """Помічає прострочені сесії як expired, а також скасовує надмірні
    активні (понад MAX_ACTIVE_SESSIONS_PER_KEY) для одного session_key —
    це додатковий захист від спаму."""
    now = timezone.now()
    TelegramVerificationSession.objects.filter(
        status__in=[
            TelegramVerificationSession.STATUS_PENDING,
            TelegramVerificationSession.STATUS_BOT_OPENED,
        ],
        expires_at__lt=now,
    ).update(status=TelegramVerificationSession.STATUS_EXPIRED)

    if session_key:
        # Якщо в одного юзера висить занадто багато — скасуємо старіші.
        active_qs = (
            TelegramVerificationSession.objects.filter(
                session_key=session_key,
                status__in=[
                    TelegramVerificationSession.STATUS_PENDING,
                    TelegramVerificationSession.STATUS_BOT_OPENED,
                ],
            )
            .order_by("-created_at")
        )
        excess = list(active_qs[MAX_ACTIVE_SESSIONS_PER_KEY:])
        if excess:
            ids = [obj.pk for obj in excess]
            TelegramVerificationSession.objects.filter(pk__in=ids).update(
                status=TelegramVerificationSession.STATUS_CANCELLED,
            )


# ──────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────


@csrf_protect
@require_POST
def telegram_verify_start(request):
    """Створює нову сесію верифікації Telegram-контакту.

    POST body (JSON або form-encoded):
        - lead_id (optional): прив'язати до існуючого CustomPrintLead.
        - name (optional): імʼя клієнта на момент створення.

    Response:
        {
            "ok": true,
            "token": "<urlsafe>",
            "expires_at": "...",
            "deep_link_url": "https://t.me/<bot>?start=verify_<token>",
            "deep_link_app": "tg://resolve?domain=<bot>&start=verify_<token>",
            "bot_username": "<bot>"
        }
    """
    bot_token = _get_bot_token()
    if not bot_token:
        return JsonResponse(
            {"ok": False, "error": "Telegram-бот не налаштований на сервері."},
            status=503,
        )

    bot_username = _get_bot_username()
    if not bot_username:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Не вдалося отримати username бота. Адміністратор має задати "
                    "TELEGRAM_BOT_USERNAME у середовищі."
                ),
            },
            status=503,
        )

    # Парсимо payload (підтримуємо JSON і form data)
    payload = {}
    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
        else:
            payload = {k: v for k, v in request.POST.items()}
    except Exception:
        payload = {}

    lead_id_raw = payload.get("lead_id") or ""
    name_raw = (payload.get("name") or "").strip()

    session_key = _ensure_session_key(request)
    _expire_old_sessions(session_key)

    # Привʼязка до ліда (опційно)
    lead = None
    if lead_id_raw:
        try:
            from storefront.models import CustomPrintLead

            lead = CustomPrintLead.objects.filter(pk=int(lead_id_raw)).first()
        except (TypeError, ValueError):
            lead = None

    token = secrets.token_urlsafe(24)
    now = timezone.now()
    expires_at = now + timedelta(seconds=VERIFICATION_TTL_SECONDS)

    session = TelegramVerificationSession.objects.create(
        token=token,
        purpose=TelegramVerificationSession.PURPOSE_CUSTOM_PRINT,
        status=TelegramVerificationSession.STATUS_PENDING,
        session_key=session_key,
        user=request.user if request.user.is_authenticated else None,
        lead=lead,
        initial_name=name_raw[:200],
        expires_at=expires_at,
    )

    deep_link_url = f"https://t.me/{bot_username}?start=verify_{quote(token)}"
    deep_link_app = f"tg://resolve?domain={bot_username}&start=verify_{quote(token)}"

    return JsonResponse(
        {
            "ok": True,
            "token": session.token,
            "expires_at": session.expires_at.isoformat(),
            "ttl_seconds": VERIFICATION_TTL_SECONDS,
            "deep_link_url": deep_link_url,
            "deep_link_app": deep_link_app,
            "bot_username": bot_username,
        }
    )


@require_GET
def telegram_verify_status(request):
    """Повертає поточний статус сесії за token.

    GET ?token=<token>

    Response:
        {
            "ok": true,
            "status": "pending|bot_opened|verified|expired|cancelled",
            "verified": false,
            "phone": "...",
            "telegram_username": "...",
            "telegram_first_name": "...",
            "expires_at": "..."
        }
    """
    token = (request.GET.get("token") or "").strip()
    if not token:
        return JsonResponse({"ok": False, "error": "missing token"}, status=400)

    session = TelegramVerificationSession.objects.filter(token=token).first()
    if not session:
        return JsonResponse({"ok": False, "error": "session not found"}, status=404)

    # Перевірка що поллить «свій» (один з варіантів):
    # - сесія належить тому ж session_key, або
    # - сесія належить тому ж авторизованому юзеру.
    session_key = request.session.session_key or ""
    own_session = (
        (session.session_key and session.session_key == session_key)
        or (session.user_id and request.user.is_authenticated and session.user_id == request.user.id)
    )
    if not own_session and not session.is_verified:
        # Дозволяємо тільки факт verified (без чутливих даних), щоб уникнути
        # leak phone до сторонніх. Але повернемо "обрублений" статус.
        return JsonResponse(
            {"ok": True, "status": session.status, "verified": session.is_verified},
        )

    # Якщо expired — відобразимо це
    if session.is_expired and session.status in {
        TelegramVerificationSession.STATUS_PENDING,
        TelegramVerificationSession.STATUS_BOT_OPENED,
    }:
        session.status = TelegramVerificationSession.STATUS_EXPIRED
        session.save(update_fields=["status"])

    session.mark_polled()
    return JsonResponse({"ok": True, **session.to_public_dict()})


@csrf_protect
@require_POST
def telegram_verify_cancel(request):
    """Скасовує сесію (користувач закрив модалку / обрав інший спосіб).

    POST body: {"token": "..."}
    """
    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
        else:
            payload = {k: v for k, v in request.POST.items()}
    except Exception:
        payload = {}
    token = (payload.get("token") or "").strip()
    if not token:
        return JsonResponse({"ok": False, "error": "missing token"}, status=400)

    session_key = request.session.session_key or ""
    session = TelegramVerificationSession.objects.filter(token=token).first()
    if not session:
        return JsonResponse({"ok": True, "skipped": True})

    own = (
        (session.session_key and session.session_key == session_key)
        or (session.user_id and request.user.is_authenticated and session.user_id == request.user.id)
    )
    if not own:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    if session.status in {
        TelegramVerificationSession.STATUS_PENDING,
        TelegramVerificationSession.STATUS_BOT_OPENED,
    }:
        session.status = TelegramVerificationSession.STATUS_CANCELLED
        session.save(update_fields=["status"])
    return JsonResponse({"ok": True})
