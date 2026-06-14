"""
Instagram webhook приймач TwoComms.

- GET  /bot/webhook/  — верифікація підписки Meta (echo hub.challenge).
- POST /bot/webhook/  — вхідні події IG. Делегуються в services.instagram_bot.

Verify token береться з ENV (IG_BOT_VERIFY_TOKEN). У коді секрету немає.

Вхідні `messages` доставляються лише в Live-режимі застосунку; поки застосунок
на верифікації, реальні відповіді забезпечує поллер. Обидва канали йдуть через
один сервіс і дедуплікуються за mid, тож подвійних відповідей не буде.
"""
import json
import logging
import os

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from management.models import InstagramBotSettings
from management.services import instagram_bot as bot

logger = logging.getLogger("ig_bot")


def _verify_token() -> str:
    return os.environ.get("IG_BOT_VERIFY_TOKEN", "").strip()


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
        # Завжди 200, щоб Meta не вимикала підписку.
        raw = request.body.decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except Exception:
            logger.warning("ig_bot: bad payload")
            return HttpResponse("ok")
        try:
            settings_obj = InstagramBotSettings.load()
            # Лог сирого payload у консоль (обрізаний).
            bot.log("info", "webhook_in", raw[:1000])
            bot.handle_webhook_payload(settings_obj, payload)
        except Exception as exc:
            logger.exception("ig_bot: handler error")
            try:
                bot.log("error", "webhook_error", repr(exc))
            except Exception:
                pass
        return HttpResponse("ok")

    return HttpResponse(status=405)
