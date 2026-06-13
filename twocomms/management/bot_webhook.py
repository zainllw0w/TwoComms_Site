"""
Мінімальний тестовий приймач Instagram webhook для бота TwoComms.

Призначення (фаза тесту):
- GET  /bot/webhook/  — верифікація підписки Meta (echo hub.challenge).
- POST /bot/webhook/  — приймає вхідні IG-повідомлення і миттєво відповідає
  ТІЛЬКИ якщо текст рівно "1" -> надсилає "Привет, ты написал единичку".
  На будь-який інший текст бот мовчить.

Це навмисно ізольований модуль без БД/моделей: спочатку перевіряємо, що
ланцюжок Meta -> наш сервер -> Send API працює. Повна вкладка керування
ботом (Start/Stop, ключі, Gemini) будується окремо після успішного тесту.
"""
import json
import logging
import os
import urllib.error
import urllib.request

from django.core.cache import cache
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger("ig_bot")

GRAPH_VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Сторінка Twocomms (Facebook Page id, до якої прив'язаний IG @twocomms).
PAGE_ID = "401216546416228"

# Verify token для верифікації webhook у Meta App Dashboard.
# За замовчуванням захардкоджений (щоб не чіпати ENV на час тесту),
# але можна перевизначити через змінну оточення IG_BOT_VERIFY_TOKEN.
VERIFY_TOKEN = os.environ.get("IG_BOT_VERIFY_TOKEN", "twc_ig_bot_a7f3k9q2_verify")

# Тестова логіка.
TEST_TRIGGER = "1"
TEST_REPLY = "Привет, ты написал единичку"


def _direct_token() -> str:
    return os.environ.get("DIRECT_API", "")


def _http_get_json(url: str):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _get_page_token() -> str:
    """Отримати page access token сторінки Twocomms з user-токена DIRECT_API."""
    token = _direct_token()
    if not token:
        return ""
    cached = cache.get("ig_bot_page_token")
    if cached:
        return cached
    try:
        data = _http_get_json(
            f"{GRAPH}/me/accounts?fields=name,access_token&access_token={token}"
        )
        for page in data.get("data", []):
            if str(page.get("id")) == PAGE_ID or str(page.get("name")) == "Twocomms":
                page_token = page.get("access_token") or ""
                if page_token:
                    cache.set("ig_bot_page_token", page_token, 60 * 30)
                    return page_token
    except Exception:
        logger.exception("ig_bot: failed to resolve page token")
    return token


def _send_text(recipient_id: str, text: str) -> None:
    page_token = _get_page_token()
    if not page_token:
        logger.error("ig_bot: no page token available, cannot send")
        return
    url = f"{GRAPH}/{PAGE_ID}/messages?access_token={page_token}"
    body = json.dumps(
        {
            "recipient": {"id": recipient_id},
            "message": {"text": text},
            "messaging_type": "RESPONSE",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            logger.info("ig_bot: sent reply, status=%s", resp.getcode())
    except urllib.error.HTTPError as exc:
        logger.error(
            "ig_bot: send HTTPError %s: %s",
            exc.code,
            exc.read()[:400].decode("utf-8", "replace"),
        )
    except Exception:
        logger.exception("ig_bot: send failed")


def _handle_messaging_event(event: dict) -> None:
    message = event.get("message") or {}
    # Ігноруємо echo (наші ж відправлені повідомлення) і службові події.
    if message.get("is_echo"):
        return
    mid = message.get("mid") or ""
    text = (message.get("text") or "").strip()
    sender_id = (event.get("sender") or {}).get("id") or ""
    if not sender_id or not text:
        return

    # Захист від повторної обробки (Meta може ретраїти доставку).
    if mid:
        dedup_key = f"ig_bot_seen:{mid}"
        if cache.get(dedup_key):
            return
        cache.set(dedup_key, 1, 60 * 60)

    if text == TEST_TRIGGER:
        _send_text(sender_id, TEST_REPLY)


def _handle_payload(payload: dict) -> None:
    # IG messaging: object == "instagram", entry[].messaging[]
    for entry in payload.get("entry", []) or []:
        for event in entry.get("messaging", []) or []:
            if "message" in event:
                _handle_messaging_event(event)


@csrf_exempt
def ig_webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge", "")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("forbidden", status=403)

    if request.method == "POST":
        # Завжди відповідаємо 200, щоб Meta не вимикала підписку.
        try:
            payload = json.loads(request.body.decode("utf-8", "replace"))
        except Exception:
            logger.warning("ig_bot: bad payload")
            return HttpResponse("ok")
        try:
            logger.info("ig_bot: payload %s", json.dumps(payload)[:1000])
            _handle_payload(payload)
        except Exception:
            logger.exception("ig_bot: handler error")
        return HttpResponse("ok")

    return HttpResponse(status=405)
