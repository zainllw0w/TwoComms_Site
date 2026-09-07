"""
Instagram webhook приймач TwoComms (event-driven).

- GET  /bot/webhook/  — верифікація підписки Meta (echo hub.challenge).
- POST /bot/webhook/  — перевіряє підпис X-Hub-Signature-256, кладе вхідні в
  чергу і ВІДРАЗУ повертає 200 (best practice). Обробку (класифікація,
  Gemini, media, notifications і Send API) виконує singleton worker daemon.

Verify token і APP_SECRET — лише з ENV (IG_BOT_VERIFY_TOKEN, IG_APP_SECRET).
"""
import json
import logging
import os
import threading

from django.core.cache import cache
from django.conf import settings
from django.db import DatabaseError
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from management.models import InstagramBotSettings
from management.services import instagram_bot as bot

logger = logging.getLogger("ig_bot")
_CONFIG_WARNING_LOCK = threading.Lock()
_CONFIG_WARNING_EMITTED = False


def _verify_token() -> str:
    return os.environ.get("IG_BOT_VERIFY_TOKEN", "").strip()


def _warn_signature_configuration_once():
    """Record one bounded warning when production cannot verify signatures."""
    global _CONFIG_WARNING_EMITTED
    if bot.webhook_signature_status()["healthy"]:
        return
    with _CONFIG_WARNING_LOCK:
        if _CONFIG_WARNING_EMITTED:
            return
        try:
            if not cache.add("ig_bot_webhook_signature_warning", 1, 3600):
                _CONFIG_WARNING_EMITTED = True
                return
        except Exception:
            pass
        _CONFIG_WARNING_EMITTED = True
    bot.log("warning", "no_app_secret", "IG_APP_SECRET не заданий — підпис webhook відхиляється")


@csrf_exempt
def ig_webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge", "")
        expected = _verify_token()
        if mode == "subscribe" and expected and token == expected:
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("forbidden", status=403)

    if request.method == "POST":
        from management.services.ig_webhook_inbox import (
            WebhookRejected,
            accept_webhook,
            max_body_bytes,
        )

        try:
            declared_length = int(request.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            declared_length = 0
        if declared_length > max_body_bytes():
            bot.record_webhook_response(413, reason="body_too_large")
            return HttpResponse("body_too_large", status=413)
        raw = request.read(max_body_bytes() + 1)
        if len(raw) > max_body_bytes():
            bot.record_webhook_response(413, reason="body_too_large")
            return HttpResponse("body_too_large", status=413)
        sig = request.headers.get("X-Hub-Signature-256", "")
        if not bot.verify_signature(raw, sig):
            _warn_signature_configuration_once()
            logger.warning("ig_bot: bad signature")
            bot.log("warning", "bad_signature", "Невірний підпис webhook — відхилено")
            bot.record_webhook_response(403, reason="invalid_signature")
            return HttpResponse("forbidden", status=403)

        if not bool(getattr(settings, "IG_WEBHOOK_INBOX_ENABLED", True)):
            bot.record_webhook_response(503, reason="inbox_consumer_unavailable")
            return HttpResponse("retry", status=503)

        try:
            settings_obj = InstagramBotSettings.load()
            acceptance = accept_webhook(raw, settings_obj)
        except WebhookRejected as exc:
            bot.log("error", "webhook_rejected", f"len={len(raw)} code={exc.code}")
            bot.record_webhook_response(exc.status, reason=exc.code)
            return HttpResponse(exc.code, status=exc.status)
        except DatabaseError:
            bot.log("error", "webhook_inbox_unavailable", f"len={len(raw)}")
            bot.record_webhook_response(503, reason="inbox_unavailable")
            return HttpResponse("retry", status=503)
        # Do not retain a signed foreign/rejected body in raw diagnostics.
        # Accepted-fragment inspection belongs to the authenticated inbox drain.
        bot.log(
            "info", "webhook_inbox_committed",
            f"accepted={acceptance.accepted} rejected={acceptance.rejected} duplicates={acceptance.duplicates}",
        )

        # 2xx only after every accepted/rejected event has a durable receipt.
        bot.record_webhook_response(200)
        return HttpResponse(f"accepted={acceptance.accepted};rejected={acceptance.rejected};duplicates={acceptance.duplicates}")

    return HttpResponse(status=405)
