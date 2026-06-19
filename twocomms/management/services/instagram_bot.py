"""
Сервіс Instagram Direct бота TwoComms (event-driven).

Архітектура (best practice для хостингу без Celery):
- Webhook (подія) — приймає вхідне, перевіряє підпис, кладе в чергу
  (InstagramBotMessage, status=pending) і ВІДРАЗУ повертає 200. Жодної важкої
  логіки в запиті.
- Воркер (демон run_instagram_bot --forever) — забирає pending із черги,
  будує контекст з ЛОКАЛЬНОЇ історії (без read-запитів до IG), генерує
  відповідь Gemini і відправляє через Send API. Ретраї, дедуп.
- Поллінг IG — лише резервний міст до Live (receive_via_poll). Після Live
  його вимикають → бот суто event-driven, read-запитів до IG немає.

Відповідь: AI (Gemini, history+system_prompt) або простий trigger->reply.
Захист: allowed_senders (білий список), дедуп за mid, перевірка підпису
X-Hub-Signature-256 (IG_APP_SECRET), is_enabled-гейт.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from management.models import (
    IgClient,
    InstagramBotLog,
    InstagramBotMessage,
    InstagramBotSettings,
)

GRAPH_VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
GENAI = "https://generativelanguage.googleapis.com/v1beta"

LOG_KEEP_ROWS = 500
HISTORY_LIMIT = 12          # скільки останніх реплік даємо моделі
MAX_ATTEMPTS = 3            # ретраї обробки одного повідомлення
PAGE_TOKEN_TTL = 1200
HTTP_TIMEOUT = 12
CONV_LIST_TIMEOUT = 30
MSG_KEEP_ROWS = 2000        # підрізання історії

# Керуючі теги, які модель може додавати у відповідь (вирізаються перед
# відправкою клієнту). [STAGE:x] просуває воронку, [MANAGER] кличе людину.
STAGE_VALUES = {s.value for s in IgClient.Stage}
_CONTROL_TAG_RE = re.compile(r"\[([A-Z]+)(?::([^\]]+))?\]")


def _extract_control(reply: str) -> tuple[str, dict]:
    """Витягує керуючі теги ([MANAGER], [STAGE:x], [SPAM], [PAYLINK:x], [ORDER])
    з відповіді моделі. Повертає (очищений_текст, {tag_lower: value|True}).
    Кирилічні дужки [текст] не чіпаються (матчимо лише латиницю у верхньому регістрі)."""
    tags: dict = {}
    if not reply:
        return reply, tags
    for m in _CONTROL_TAG_RE.finditer(reply):
        name = m.group(1).lower()
        val = (m.group(2) or "").strip().lower()
        tags[name] = val or True
    clean = _CONTROL_TAG_RE.sub("", reply)
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return clean, tags


def _apply_stage(client, stage_value) -> bool:
    """Просуває клієнта на стадію, якщо вона валідна й відрізняється від поточної."""
    if not client or not stage_value or not isinstance(stage_value, str):
        return False
    if stage_value not in STAGE_VALUES:
        return False
    if client.stage == stage_value:
        return False
    try:
        client.set_stage(stage_value, reason="bot")
    except Exception:
        return False
    return True


# ---------------------------------------------------------------------------
# Модерація діалогу: стоп/старт, антиспам, перехоплення менеджером (Phase 7)
# ---------------------------------------------------------------------------
SPAM_STRIKES_LIMIT = 3
PHONE_RE = re.compile(r"(?:\+?38)?0\d{9}")


def _client_blocked(client) -> bool:
    """Бот не відповідає, якщо клієнта поставлено на паузу або заблоковано."""
    return bool(client and (client.bot_paused or client.is_blocked))


def _register_spam(client) -> bool:
    """+1 спам-страйк. На SPAM_STRIKES_LIMIT — пауза + стадія SPAM + сповіщення.
    Повертає True, якщо клієнта заблоковано цим страйком."""
    client.spam_strikes = (client.spam_strikes or 0) + 1
    fields = ["spam_strikes", "updated_at"]
    blocked = client.spam_strikes >= SPAM_STRIKES_LIMIT
    if blocked:
        client.bot_paused = True
        client.paused_reason = "spam"
        client.paused_at = timezone.now()
        fields += ["bot_paused", "paused_reason", "paused_at"]
    client.save(update_fields=fields)
    if blocked:
        try:
            client.set_stage(IgClient.Stage.SPAM, reason="spam")
        except Exception:
            pass
        notify_manager(
            f"🚫 IG: клієнт {client.username or client.igsid} заблокований "
            f"(3 спам-страйки). Бот зупинено для нього."
        )
        log("warning", "spam_block", f"{client.igsid}: 3 страйки → пауза")
    return blocked


def _maybe_capture_phone(client, text: str) -> bool:
    """Якщо у клієнта ще немає телефону, а в тексті є український номер — зберігає."""
    if not client or client.phone:
        return False
    cleaned = (text or "").replace(" ", "").replace("-", "")
    m = PHONE_RE.search(cleaned)
    if not m:
        return False
    try:
        from management.models import normalize_phone

        if not normalize_phone(m.group(0)):
            return False
    except Exception:
        pass
    client.phone = m.group(0)
    client.save(update_fields=["phone", "phone_normalized", "updated_at"])
    return True


def _bot_sent_key(recipient_id: str, text: str) -> str:
    norm = " ".join((text or "").lower().split())
    h = hashlib.md5((str(recipient_id) + "|" + norm).encode("utf-8")).hexdigest()[:16]
    return "ig_bot_sent:" + h


def _mark_bot_sent(recipient_id: str, text: str) -> None:
    """Позначає текст, який бот шле конкретному отримувачу — щоб відрізнити від
    відлуння повідомлення менеджера (echo). Привʼязка до отримувача прибирає
    хибні збіги між клієнтами з однаковим текстом."""
    try:
        cache.set(_bot_sent_key(recipient_id, text), 1, 1800)
    except Exception:
        pass


def _looks_like_contact_info(text: str) -> bool:
    """Евристика: схоже на контактні дані (телефон / адреса Нової Пошти)."""
    raw = (text or "")
    if PHONE_RE.search(raw.replace(" ", "").replace("-", "")):
        return True
    low = raw.lower()
    keys = ("відділенн", "поштомат", "нова пошта", "новапошта", "нп ", "індекс", "вул.", "вулиц", "м. ")
    return any(k in low for k in keys)


PAYLINK_PHRASES = (
    "посилання на оплат", "посилання на передоплат", "сформую посилання",
    "сформувати посилання", "формую посилання", "ось посилання", "ось пряме посилання",
    "тримай посилання", "надішлю посилання", "надсилаю посилання", "лінк на оплат",
    "ссылка на оплат", "ссылку на оплат", "ссылка на предоплат", "ссылку на предоплат",
    "сформирую ссылку", "вот ссылка", "вот ссылку", "держи ссылку",
)


def _wants_paylink(reply: str, control: dict) -> tuple[bool, str]:
    """Чи треба сформувати посилання на оплату і який тип (full/prepay).
    Тригер: тег [PAYLINK:x] АБО обіцянка посилання у тексті бота (фолбек, якщо
    модель забула тег). Тип беремо з тегу, інакше визначаємо за словом «передопл»."""
    val = control.get("paylink")
    low = (reply or "").lower()
    if val or any(ph in low for ph in PAYLINK_PHRASES):
        if isinstance(val, str) and val in ("full", "prepay"):
            return True, val
        pt = "prepay" if ("передопл" in low or "предопл" in low) else "full"
        return True, pt
    return False, "full"


def _handle_echo(recipient_igsid: str, text: str) -> None:
    """Echo-подія (повідомлення, надіслане сторінкою). Якщо це НЕ власне відлуння
    бота — значить відповів живий менеджер → ставимо бота на паузу для клієнта."""
    if not recipient_igsid:
        return
    if text and cache.get(_bot_sent_key(recipient_igsid, text)):
        return  # власне відлуння бота — ігноруємо
    client = IgClient.get_or_create_for_sender(recipient_igsid)
    if client.manager_takeover and client.bot_paused:
        return
    client.manager_takeover = True
    client.bot_paused = True
    client.paused_reason = "manager_takeover"
    client.paused_at = timezone.now()
    client.save(update_fields=[
        "manager_takeover", "bot_paused", "paused_reason", "paused_at", "updated_at",
    ])
    notify_manager(
        f"👤 IG: менеджер підключився до {client.username or client.igsid} — "
        f"бот на паузі для цього клієнта."
    )
    log("warning", "takeover", f"{recipient_igsid}: менеджер підключився")


def _match_allowed(sender_id: str, limit: int = 15, window: int = 3600) -> bool:
    """Cost-гард: не більше `limit` vision-матчингів на клієнта за `window` секунд
    (матчинг іде через дорожчу management-модель — захист квоти від спаму фото)."""
    key = f"ig_match_cnt:{sender_id}"
    try:
        n = cache.get(key) or 0
        if n >= limit:
            return False
        cache.set(key, n + 1, window)
    except Exception:
        return True
    return True


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
    # ENV: пріоритет постійному System User токену (IG_MARKER), потім DIRECT_API.
    return (
        os.environ.get("IG_MARKER", "").strip()
        or os.environ.get("DIRECT_API", "").strip()
    )


def resolve_gemini_key(s: InstagramBotSettings) -> str:
    if s.gemini_source == InstagramBotSettings.CredSource.CUSTOM:
        return (s.custom_gemini_key or "").strip()
    return os.environ.get("GEMINI_API", "").strip()


def app_secret() -> str:
    return os.environ.get("IG_APP_SECRET", "").strip()


# ---------------------------------------------------------------------------
# Webhook signature (X-Hub-Signature-256)
# ---------------------------------------------------------------------------
def verify_signature(raw_body: bytes, header: str) -> bool:
    """HMAC-SHA256 від тіла з APP_SECRET. Якщо секрет не заданий — пропускаємо
    (із warning), щоб не блокувати до налаштування ENV."""
    secret = app_secret()
    if not secret:
        return True  # не налаштовано — не блокуємо (див. лог у webhook)
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1].strip())


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


APP_ID = os.environ.get("IG_APP_ID", "2120980214971807")


def _exchange_long_lived(user_token: str) -> str:
    """short-lived -> long-lived (60 дн). Потрібен app_secret. Page-токен,
    похідний від long-lived user-токена, не має терміну дії."""
    secret = app_secret()
    if not secret or not user_token:
        return ""
    code, body = _http(
        f"{GRAPH}/oauth/access_token?grant_type=fb_exchange_token"
        f"&client_id={APP_ID}&client_secret={secret}&fb_exchange_token={user_token}",
        timeout=HTTP_TIMEOUT,
    )
    if code == 200:
        try:
            return json.loads(body).get("access_token", "") or ""
        except Exception:
            return ""
    return ""


def _effective_user_token(s: InstagramBotSettings) -> str:
    raw = resolve_direct_token(s)
    if not raw or not app_secret():
        return raw  # без секрету не можемо подовжити — використовуємо як є
    cached = cache.get("ig_bot_ll_user_token")
    if cached:
        return cached
    ll = _exchange_long_lived(raw)
    if ll:
        cache.set("ig_bot_ll_user_token", ll, 50 * 24 * 3600)  # ~50 днів
        return ll
    return raw


def _log_token_error(s: InstagramBotSettings, code, body: str) -> None:
    # Стабільна сигнатура: тіло містить мінливий «current time», тож беремо
    # error.code/error_subcode, щоб не логувати ту саму помилку щохвилини.
    sig = str(code)
    try:
        err = json.loads(body).get("error", {})
        sig = f"{code}:{err.get('code')}:{err.get('error_subcode')}"
    except Exception:
        sig = f"{code}:{(body or '')[:40]}"
    if cache.get("ig_bot_pt_errsig") != sig:
        cache.set("ig_bot_pt_errsig", sig, 3600)
        log("error", "page_token", f"HTTP {code}: {body[:160]}")
    try:
        s.last_error = (
            f"Direct токен недійсний (HTTP {code}). Онови DIRECT_API в ENV "
            f"(або свій токен у налаштуваннях)."
        )
        s.save(update_fields=["last_error"])
    except Exception:
        pass


def notify_manager(text: str) -> None:
    """Сповіщення менеджеру в Telegram (best-effort)."""
    token = os.environ.get("MANAGEMENT_TG_BOT_TOKEN", "").strip()
    chat = os.environ.get("MANAGEMENT_TG_ADMIN_CHAT_ID", "").strip()
    if not token or not chat:
        return
    try:
        body = json.dumps(
            {"chat_id": chat, "text": text[:3500], "disable_web_page_preview": True}
        ).encode("utf-8")
        _http(f"https://api.telegram.org/bot{token}/sendMessage", data=body, timeout=HTTP_TIMEOUT)
    except Exception:
        pass


def _rate_exceeded(s: InstagramBotSettings, sender_id: str, limit: int = 25, window: int = 3600) -> bool:
    """Анти-спам: не більше `limit` відповідей одному відправнику за `window` c."""
    key = f"ig_bot_rate:{sender_id}"
    try:
        n = cache.get(key) or 0
        if n >= limit:
            return True
        cache.set(key, n + 1, window)
    except Exception:
        return False
    return False


def _repeated_question(sender_id: str, text: str, window: int = 600) -> int:
    """Скільки разів цей самий текст від відправника за вікно (анти-абуз токенів)."""
    import hashlib

    norm = " ".join((text or "").lower().split())
    if not norm:
        return 0
    h = hashlib.md5(norm.encode("utf-8")).hexdigest()[:12]
    key = f"ig_bot_q:{sender_id}:{h}"
    try:
        n = (cache.get(key) or 0) + 1
        cache.set(key, n, window)
        return n
    except Exception:
        return 0


def get_page_token(s: InstagramBotSettings, *, force: bool = False) -> str:
    token = _effective_user_token(s)
    if not token:
        return ""
    ck = "ig_bot_page_token"
    if not force:
        cached = cache.get(ck)
        if cached:
            return cached
        if cache.get("ig_bot_pt_cooldown"):
            return ""
    code, body = _http(
        f"{GRAPH}/me/accounts?fields=name,access_token&access_token={token}",
        timeout=HTTP_TIMEOUT,
    )
    if code != 200:
        cache.set("ig_bot_pt_cooldown", 1, 60)
        _log_token_error(s, code, body)
        return ""
    try:
        for page in json.loads(body).get("data", []):
            if str(page.get("id")) == s.page_id:
                pt = page.get("access_token") or ""
                if pt:
                    # Якщо токен подовжений (є секрет) — page-токен постійний,
                    # кешуємо надовго; інакше — коротко.
                    ttl = 50 * 24 * 3600 if app_secret() else PAGE_TOKEN_TTL
                    cache.set(ck, pt, ttl)
                    cache.delete("ig_bot_pt_cooldown")
                    cache.delete("ig_bot_pt_errsig")
                return pt
    except Exception as exc:
        log("error", "page_token_parse", repr(exc))
    return ""


def refresh_conv_ids(s: InstagramBotSettings, page_token: str) -> list[str]:
    """Важкий виклик /conversations (~20-27 c) — лише у фоновому потоці демона."""
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
def send_sender_action(s: InstagramBotSettings, recipient_id: str, action: str) -> None:
    """typing_on / typing_off / mark_seen — для відчуття миттєвості (best practice)."""
    page_token = get_page_token(s)
    if not page_token:
        return
    try:
        body = json.dumps({"recipient": {"id": recipient_id}, "sender_action": action}).encode("utf-8")
        _http(f"{GRAPH}/{s.page_id}/messages?access_token={page_token}", data=body, timeout=HTTP_TIMEOUT)
    except Exception:
        pass


def _split_for_send(text: str, limit: int = 950, max_chunks: int = 4) -> list[str]:
    """Ріже текст на частини ≤limit байт (UTF-8). Send API дозволяє 1000 байт."""
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    rest = text
    while rest and len(chunks) < max_chunks:
        if len(rest.encode("utf-8")) <= limit:
            chunks.append(rest)
            rest = ""
            break
        # знайти межу різу по байтах, з відкатом до пробілу/переносу
        cut = limit
        while len(rest[:cut].encode("utf-8")) > limit and cut > 0:
            cut -= 1
        slice_ = rest[:cut]
        brk = max(slice_.rfind("\n"), slice_.rfind(". "), slice_.rfind(" "))
        if brk > int(cut * 0.5):
            slice_ = rest[:brk + 1]
        chunks.append(slice_.strip())
        rest = rest[len(slice_):]
    return [c for c in chunks if c]


RATE_LIMIT_CODES = {4, 17, 32, 613, 80007}  # тимчасові ліміти — варто ретраїти
PERMANENT_HINT = {
    200: "немає Advanced Access на instagram_manage_messages (потрібен App Review) "
         "АБО користувач не доданий у тестувальники застосунку",
    190: "токен недійсний (онови DIRECT_API/IG_MARKER)",
    10: "поза дозволеним вікном/політикою (24 год)",
    100: "некоректний параметр запиту",
}


def _classify_send_error(code: int, body: str) -> tuple[str, str]:
    """Повертає (kind, hint): kind = 'transient' | 'permanent'."""
    if code == -1 or code >= 500:
        return "transient", "тимчасова мережева/серверна помилка"
    ec = 0
    try:
        ec = int(json.loads(body).get("error", {}).get("code", 0) or 0)
    except Exception:
        ec = 0
    if ec in RATE_LIMIT_CODES:
        return "transient", "ліміт частоти (retry пізніше)"
    return "permanent", PERMANENT_HINT.get(ec, f"відмова Graph API (code {ec})")


def send_text(s: InstagramBotSettings, recipient_id: str, text: str) -> tuple[bool, str, str]:
    """Повертає (ok, kind, hint). kind: '' | 'transient' | 'permanent'."""
    page_token = get_page_token(s)
    if not page_token:
        return False, "permanent", "немає page-token (перевірте DIRECT_API/IG_MARKER)"
    parts = _split_for_send(text)
    if not parts:
        return False, "permanent", "порожня відповідь"
    ok_any = False
    for part in parts:
        # Позначаємо ДО відправки: echo цього чанка прийде асинхронно і не має
        # сприйнятись за повідомлення менеджера (виправляє хибний авто-стоп).
        _mark_bot_sent(recipient_id, part)
        body = json.dumps(
            {
                "recipient": {"id": recipient_id},
                "message": {"text": part},
                "messaging_type": "RESPONSE",
            }
        ).encode("utf-8")
        code, resp = _http(f"{GRAPH}/{s.page_id}/messages?access_token={page_token}", data=body)
        if code == 200:
            ok_any = True
            continue
        kind, hint = _classify_send_error(code, resp)
        log("error", "send", f"HTTP {code} [{kind}] {hint}: {resp[:200]}")
        return ok_any, kind, hint
    return True, "", ""


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
def gemini_generate(
    s: InstagramBotSettings, history: list[dict], images: list[tuple[str, bytes]] | None = None,
    match_hint: str | None = None, memory_note: str | None = None,
    context_note: str | None = None,
) -> str | None:
    """history: [{'role':'user'|'model','text':str}] хронологічно.
    images: список (mime_type, raw_bytes) для ОСТАННЬОГО (поточного) user-ходу."""
    contents = []
    for h in history:
        if h.get("text"):
            contents.append({"role": h["role"], "parts": [{"text": h["text"]}]})
    if not contents:
        contents = [{"role": "user", "parts": [{"text": "(порожнє повідомлення)"}]}]

    # Зображення додаємо в останній user-хід як inline_data.
    if images:
        last = contents[-1]
        if last.get("role") != "user":
            last = {"role": "user", "parts": [{"text": ""}]}
            contents.append(last)
        for mime, raw in images[:3]:
            try:
                last["parts"].append(
                    {"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode()}}
                )
            except Exception:
                pass

    # system_instruction = правило + оперативні директиви + база знань + каталог.
    sys_text = (s.system_prompt or "").strip()
    live = (s.knowledge_base or "").strip()
    if live:
        sys_text += "\n\n[ОПЕРАТИВНІ ДИРЕКТИВИ — найвищий пріоритет, дотримуйся беззаперечно]\n" + live
    try:
        from management.services.bot_knowledge import get_brand_knowledge

        kb = get_brand_knowledge()
        if kb:
            sys_text += "\n\n[БАЗА ЗНАНЬ ПРО БРЕНД]\n" + kb
    except Exception:
        pass
    try:
        from management.services.bot_catalog import get_catalog_context

        catalog = get_catalog_context()
        if catalog:
            sys_text += "\n\n" + catalog
    except Exception:
        pass
    try:
        from management.models import BotInstruction, BotQuickLink

        instr = BotInstruction.active_block()
        if instr:
            sys_text += "\n\n[ДОДАТКОВІ ІНСТРУКЦІЇ]\n" + instr
        links = BotQuickLink.active_block()
        if links:
            sys_text += "\n\n[ДОСТУПНІ ПОСИЛАННЯ — надсилай доречне за запитом]\n" + links
    except Exception:
        pass
    sys_text = sys_text.strip()
    if context_note:
        sys_text = (sys_text + "\n\n" + context_note).strip()
    if memory_note:
        sys_text = (sys_text + "\n\n" + memory_note).strip()
    if match_hint:
        sys_text = (sys_text + "\n\n" + match_hint).strip()

    payload = {
        "contents": contents,
        # 3.5-flash — thinking-модель: без обмеження вона зʼїдає весь бюджет на
        # внутрішнє мислення й повертає finishReason=MAX_TOKENS з порожнім текстом
        # (тоді чат завжди падав на молодші моделі). thinkingBudget=0 вимикає
        # мислення (чату потрібна пряма швидка відповідь), а 1536 токенів — запас
        # на сам текст.
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": 1536,
            "thinkingConfig": {"thinkingBudget": 0},
        },
        "safetySettings": [
            {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
            for c in (
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ],
    }
    if sys_text:
        payload["system_instruction"] = {"parts": [{"text": sys_text}]}

    # Діалог із клієнтом — найвищий пріоритет (роль 'chat'): пул ключів
    # GEMINI_API/2 → позичання GEMINI_API5/6, цепочка gen-3 (3.5-flash → 3.1).
    # Якщо адмін обрав CUSTOM-ключ — він пробується першим (manual_key).
    manual_key = None
    if s.gemini_source == InstagramBotSettings.CredSource.CUSTOM:
        manual_key = (s.custom_gemini_key or "").strip() or None
    from management.services.call_ai_analysis import (
        gemini_generate_text, CallAIAnalysisError,
    )
    try:
        out = gemini_generate_text(payload, role="chat", manual_key=manual_key)
    except CallAIAnalysisError as exc:
        log("error", "gemini", str(exc)[:300])
        return None
    except Exception as exc:
        log("error", "gemini", repr(exc))
        return None
    text = (out.get("parsed") or "").strip()
    if not text:
        log("warning", "gemini_empty", "порожня відповідь")
        return None
    log("info", "gemini_ok", f"model={out.get('model')} key={(out.get('meta') or {}).get('key')}")
    return text


def download_image(url: str) -> tuple[str, bytes] | None:
    """Завантажує зображення-вкладення для мультимодалу. Ліміт ~6 МБ."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TwoCommsBot/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            mime = (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
            if not mime.startswith("image/"):
                return None
            raw = resp.read(6 * 1024 * 1024 + 1)
            if len(raw) > 6 * 1024 * 1024:
                return None
            return mime, raw
    except Exception as exc:
        log("warning", "image_download", repr(exc))
        return None


def _collect_images(attachments_json: str | None, limit: int = 3) -> list[tuple[str, bytes]]:
    """Завантажує вкладення повідомлення у список (mime, bytes) для vision.

    attachments_json — JSON-рядок зі списком URL (як зберігає InstagramBotMessage).
    Невдалі/не-image завантаження тихо пропускаються. Cap на `limit`.
    """
    images: list[tuple[str, bytes]] = []
    if not attachments_json:
        return images
    try:
        urls = json.loads(attachments_json)
    except Exception:
        return images
    for url in (urls or [])[:limit]:
        img = download_image(url)
        if img:
            images.append(img)
    return images


def _match_hint_text(match: dict | None) -> str | None:
    """Формує підказку для моделі за результатом матчингу фото з каталогом.

    Висока впевненість → називаємо конкретний товар і ціну. Низька → просимо
    уточнити/запропонувати каталог і НЕ вигадувати товар.
    """
    if not match:
        return None
    try:
        from management.services.bot_vision import MATCH_THRESHOLD
    except Exception:
        MATCH_THRESHOLD = 0.6
    pid = match.get("product_id")
    try:
        conf = float(match.get("confidence") or 0)
    except Exception:
        conf = 0.0
    if pid and conf >= MATCH_THRESHOLD:
        try:
            from storefront.models import Product

            p = Product.objects.filter(id=pid).first()
        except Exception:
            p = None
        if p:
            try:
                price = int(getattr(p, "final_price", None) or p.price)
            except Exception:
                price = p.price
            url = f"https://twocomms.shop/product/{p.slug}/"
            return (
                f"[ЗБІГ ТОВАРУ ЗА ФОТО — впевненість {int(conf * 100)}%] Клієнт прислав "
                f"фото/пост, і це товар з каталогу: «{p.title}» — {price} грн, {url}. "
                f"Назви саме цей товар, дай ціну і за потреби посилання. Веди до покупки."
            )
    return (
        "[ФОТО БЕЗ ВПЕВНЕНОГО ЗБІГУ] Клієнт прислав фото/пост, але точно зіставити з "
        "каталогом не вдалось. Чемно уточни деталі (тип, колір, принт) або запропонуй "
        "переглянути каталог. НЕ вигадуй товар, ціну чи наявність."
    )


# ---------------------------------------------------------------------------
# Профіль клієнта (IG Graph) — ім'я / username / аватар
# ---------------------------------------------------------------------------
def fetch_ig_profile(s: InstagramBotSettings, igsid: str) -> dict:
    """Тягне профіль співрозмовника через Graph (name/username/profile_pic).
    Порожній dict, якщо немає токена або помилка."""
    page_token = get_page_token(s)
    if not page_token or not igsid:
        return {}
    code, body = _http(
        f"{GRAPH}/{igsid}?fields=name,username,profile_pic&access_token={page_token}",
        timeout=HTTP_TIMEOUT,
    )
    if code != 200:
        return {}
    try:
        data = json.loads(body)
    except Exception:
        return {}
    return {
        "name": data.get("name") or "",
        "username": data.get("username") or "",
        "profile_pic": data.get("profile_pic") or "",
    }


def ensure_profile(s: InstagramBotSettings, client, force: bool = False) -> bool:
    """Підвантажує профіль у картку (один раз). False, якщо вже є/немає даних.
    На невдачі ставить короткий кулдаун, щоб не смикати Graph щоповідомлення."""
    if not client:
        return False
    if client.profile_fetched_at and not force:
        return False
    cd_key = f"ig_profile_cd:{client.igsid}"
    if not force and cache.get(cd_key):
        return False
    prof = fetch_ig_profile(s, client.igsid)
    if not prof or not any(prof.values()):
        try:
            cache.set(cd_key, 1, 3600)
        except Exception:
            pass
        return False
    client.display_name = (prof.get("name") or client.display_name or "")[:255]
    client.username = (prof.get("username") or client.username or "")[:120]
    client.profile_pic_url = (prof.get("profile_pic") or client.profile_pic_url or "")[:600]
    client.profile_fetched_at = timezone.now()
    client.save(update_fields=[
        "display_name", "username", "profile_pic_url", "profile_fetched_at", "updated_at",
    ])
    return True


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------
def allowed_sender_ids(s: InstagramBotSettings) -> set[str]:
    raw = s.allowed_senders or ""
    return {p.strip() for p in raw.replace(",", " ").replace("\n", " ").split() if p.strip()}


def _is_allowed(s: InstagramBotSettings, sender_id: str) -> bool:
    ids = allowed_sender_ids(s)
    return True if not ids else sender_id in ids


# ---------------------------------------------------------------------------
# Черга: постановка вхідних
# ---------------------------------------------------------------------------
def enqueue_inbound(
    s: InstagramBotSettings, *, sender_id: str, text: str, mid: str,
    source: str = "webhook", attachments: list[str] | None = None
) -> bool:
    """Кладе вхідне в чергу (pending). Повертає True, якщо додано нове."""
    text = (text or "").strip()
    sender_id = (sender_id or "").strip()
    attachments = attachments or []
    if not sender_id:
        return False
    if not text and not attachments:
        return False  # ні тексту, ні зображення
    if sender_id == s.ig_user_id:
        return False
    if not s.is_enabled:
        return False
    if not _is_allowed(s, sender_id):
        log("info", "skip_not_allowed", f"[{source}] {sender_id} поза білим списком")
        return False
    client = IgClient.get_or_create_for_sender(sender_id)
    try:
        with transaction.atomic():
            InstagramBotMessage.objects.create(
                sender_id=sender_id,
                client=client,
                role=InstagramBotMessage.Role.USER,
                text=text or "(зображення)",
                mid=mid or None,
                status=InstagramBotMessage.Status.PENDING,
                source=source,
                attachments=json.dumps(attachments) if attachments else "",
            )
    except IntegrityError:
        return False  # вже у черзі/оброблено (mid unique)
    client.touch_inbound()
    s.last_inbound_at = timezone.now()
    s.save(update_fields=["last_inbound_at"])
    extra = f" (+{len(attachments)} фото)" if attachments else ""
    log("info", "queued", f"[{source}] {sender_id}: {text[:140]}{extra}")
    return True


# ---------------------------------------------------------------------------
# Воркер: обробка черги
# ---------------------------------------------------------------------------
def _build_history(sender_id: str) -> list[dict]:
    rows = list(
        InstagramBotMessage.objects.filter(sender_id=sender_id)
        .exclude(status=InstagramBotMessage.Status.FAILED)
        .order_by("-id")[:HISTORY_LIMIT]
    )
    rows.reverse()
    hist = []
    for r in rows:
        t = (r.text or "").strip()
        if t:
            hist.append({"role": r.role, "text": t})
    return hist


def _claim_next() -> InstagramBotMessage | None:
    """Атомарно (умовний UPDATE) забирає найстаріше pending-вхідне."""
    row = (
        InstagramBotMessage.objects.filter(
            role=InstagramBotMessage.Role.USER,
            status=InstagramBotMessage.Status.PENDING,
        )
        .order_by("id")
        .first()
    )
    if not row:
        return None
    claimed = InstagramBotMessage.objects.filter(
        id=row.id, status=InstagramBotMessage.Status.PENDING
    ).update(status=InstagramBotMessage.Status.PROCESSING, attempts=row.attempts + 1)
    if claimed == 1:
        row.status = InstagramBotMessage.Status.PROCESSING
        row.attempts += 1
        return row
    return None  # гонка — забрав хтось інший


def _process_one(s: InstagramBotSettings, row: InstagramBotMessage) -> bool:
    # Пауза/блок клієнта (стоп вручну або перехоплення менеджером) — не відповідаємо.
    if row.client_id and _client_blocked(row.client):
        row.status = InstagramBotMessage.Status.DONE
        row.processed_at = timezone.now()
        row.save(update_fields=["status", "processed_at"])
        log("info", "paused_skip", f"{row.sender_id}: на паузі ({row.client.paused_reason or 'manual'})")
        return False
    # Захоплення телефону клієнта (лід), якщо ще немає.
    if row.client_id:
        try:
            _maybe_capture_phone(row.client, row.text)
        except Exception:
            pass
    # Анти-спам: ліміт відповідей на одного відправника.
    if _rate_exceeded(s, row.sender_id):
        row.status = InstagramBotMessage.Status.DONE
        row.processed_at = timezone.now()
        row.save(update_fields=["status", "processed_at"])
        log("warning", "rate_limited", f"{row.sender_id}: перевищено ліміт відповідей")
        if not cache.get(f"ig_bot_rate_notified:{row.sender_id}"):
            cache.set(f"ig_bot_rate_notified:{row.sender_id}", 1, 3600)
            notify_manager(f"⚠️ IG бот: відправник {row.sender_id} перевищив ліміт повідомлень (можливий спам).")
        return False

    if s.ai_enabled:
        # Відразу показуємо клієнту, що бот побачив і «друкує» (best practice).
        send_sender_action(s, row.sender_id, "mark_seen")
        send_sender_action(s, row.sender_id, "typing_on")
        # Підвантажуємо профіль клієнта (раз на картку) для CRM.
        if row.client_id and not row.client.profile_fetched_at:
            try:
                ensure_profile(s, row.client)
            except Exception:
                pass
        # Анти-абуз: однакове питання багато разів — не жжемо токени Gemini.
        rep = _repeated_question(row.sender_id, row.text)
        if rep > 3 and not row.attachments:
            reply = "Я вже відповів(-ла) на це трохи вище 🙂 Якщо потрібно щось інше — уточніть, будь ласка."
            log("info", "repeat_guard", f"{row.sender_id}: повтор #{rep}, без Gemini")
        else:
            history = _build_history(row.sender_id)
            if not history:
                history = [{"role": "user", "text": row.text}]
            # Зображення-вкладення (фото, пересланий пост, reels, сторіс) ->
            # мультимодальний вхід Gemini.
            images = _collect_images(row.attachments)
            # Якщо є фото/пост — матчимо з каталогом і даємо моделі підказку.
            match_hint = None
            if images and _match_allowed(row.sender_id):
                try:
                    from management.services import bot_vision

                    match_hint = _match_hint_text(bot_vision.match(images))
                except Exception as exc:
                    log("warning", "match", repr(exc))
            # Пам'ять про клієнта (rolling summary) + контекст (реклама/постійний) —
            # щоб бот одразу орієнтувався.
            mem_note = None
            ctx_note = None
            if row.client_id:
                try:
                    from management.services import bot_memory

                    mem_note = bot_memory.memory_note(row.client)
                    ctx_note = bot_memory.client_context_note(row.client)
                except Exception:
                    pass
            reply = gemini_generate(
                s, history, images=images or None, match_hint=match_hint,
                memory_note=mem_note, context_note=ctx_note,
            )
    else:
        if (row.text or "").strip() != s.trigger_text:
            row.status = InstagramBotMessage.Status.DONE
            row.processed_at = timezone.now()
            row.save(update_fields=["status", "processed_at"])
            log("info", "ignored", f"{row.sender_id}: не тригер")
            return False
        reply = s.reply_text

    # Керуючі теги моделі: [MANAGER] (ескалація), [STAGE:x] (воронка) тощо.
    control = {}
    if reply:
        reply, control = _extract_control(reply)
    needs_manager = bool(control.get("manager"))

    # [SPAM] — модель розпізнала спам/провокацію: рахуємо страйк (на 3-й — пауза).
    if reply and row.client_id and control.get("spam"):
        try:
            _register_spam(row.client)
        except Exception:
            pass

    # Формування посилання на оплату: за тегом [PAYLINK] АБО коли бот пообіцяв
    # посилання у тексті (надійний фолбек, якщо модель забула тег).
    want_link, link_pt = _wants_paylink(reply, control)
    if reply and row.client_id and want_link:
        try:
            from management.services import bot_orders

            res = bot_orders.create_deal_and_link(
                row.client, pay_type=link_pt, product_id=control.get("product")
            )
            if res.get("ok") and res.get("invoice_url"):
                url = res["invoice_url"]
                if url not in reply:
                    reply = (reply + "\n\n💳 Посилання на оплату: " + url).strip()
                log("success", "paylink", f"{row.sender_id}: {url}")
            else:
                log("error", "paylink", f"{row.sender_id}: НЕ сформовано ({res.get('error')})")
                notify_manager(
                    f"⚠️ IG: бот обіцяв клієнту "
                    f"{(row.client.username or row.client.display_name or row.sender_id)} "
                    f"посилання на оплату, але НЕ зміг сформувати (причина: {res.get('error')}). "
                    f"Підключись вручну."
                )
        except Exception as exc:
            log("error", "paylink", repr(exc))

    if not reply:
        # невдача генерації — ретрай або failed
        if row.attempts >= MAX_ATTEMPTS:
            row.status = InstagramBotMessage.Status.FAILED
            row.save(update_fields=["status"])
            log("error", "give_up", f"{row.sender_id}: не вдалося згенерувати після {row.attempts} спроб")
            notify_manager(
                f"⚠️ IG бот не зміг згенерувати відповідь клієнту {row.sender_id} "
                f"(3 спроби). Питання: {row.text[:300]}"
            )
        else:
            row.status = InstagramBotMessage.Status.PENDING
            row.save(update_fields=["status"])
        return False

    ok, kind, hint = send_text(s, row.sender_id, reply)
    if not ok:
        if kind == "permanent":
            # Перманентна помилка (напр. #200 немає Advanced Access) — ретраї
            # безглузді. Падаємо одразу з чіткою причиною.
            row.status = InstagramBotMessage.Status.FAILED
            row.save(update_fields=["status"])
            log("error", "send_blocked", f"{row.sender_id}: {hint}")
            # Системну причину (одна на всіх) не спамимо — алерт раз на годину.
            if not cache.get("ig_bot_perm_alert"):
                cache.set("ig_bot_perm_alert", 1, 3600)
                notify_manager(
                    f"❗️ IG бот не може відповідати неролевим користувачам.\n"
                    f"Причина: {hint}.\n\n"
                    f"Щоб відповідати ВСІМ — подай instagram_manage_messages на "
                    f"App Review (Advanced Access). Для тесту — додай користувача "
                    f"в тестувальники. (Це системне; алерт раз на годину.)"
                )
        elif row.attempts >= MAX_ATTEMPTS:
            row.status = InstagramBotMessage.Status.FAILED
            row.save(update_fields=["status"])
            log("error", "give_up", f"{row.sender_id}: не вдалося відправити після {row.attempts} спроб ({hint})")
            notify_manager(
                f"⚠️ IG бот не зміг відповісти клієнту {row.sender_id} після {row.attempts} спроб. "
                f"Причина: {hint}. Питання: {row.text[:300]}"
            )
        else:
            row.status = InstagramBotMessage.Status.PENDING
            row.save(update_fields=["status"])
        return False

    # успіх: фіксуємо відповідь у локальній історії
    row.status = InstagramBotMessage.Status.DONE
    row.processed_at = timezone.now()
    row.save(update_fields=["status", "processed_at"])
    InstagramBotMessage.objects.create(
        sender_id=row.sender_id,
        client=row.client,
        role=InstagramBotMessage.Role.MODEL,
        text=reply,
        status=InstagramBotMessage.Status.DONE,
        source=row.source,
        processed_at=timezone.now(),
    )
    s.replies_count = (s.replies_count or 0) + 1
    s.last_reply_at = timezone.now()
    s.save(update_fields=["replies_count", "last_reply_at"])
    log("success", "reply_sent", f"→ {row.sender_id}: {reply[:240]}")
    # Періодично оновлюємо стислу пам'ять про клієнта.
    if row.client_id:
        try:
            from management.services.bot_memory import maybe_update_memory

            maybe_update_memory(row.client)
        except Exception:
            pass
        # Просування воронки за тегом [STAGE:x].
        _apply_stage(row.client, control.get("stage"))
        # [ORDER] або safety-net: оплачений клієнт надіслав контактні дані, а
        # модель не виставила тег — все одно намагаємось зібрати дані й створити заказ.
        if control.get("order") or (
            row.client.stage == IgClient.Stage.PAID and _looks_like_contact_info(row.text)
        ):
            try:
                from management.services import bot_orders

                bot_orders.collect_np_and_fulfill(row.client)
            except Exception:
                pass
    if needs_manager:
        if row.client_id:
            try:
                _apply_stage(row.client, IgClient.Stage.LEAD_TO_MANAGER)
            except Exception:
                pass
        notify_manager(
            f"🔔 IG Direct — клієнту потрібен менеджер.\n"
            f"IGSID: {row.sender_id}\nПитання: {row.text[:400]}"
        )
        log("warning", "escalation", f"{row.sender_id}: викликано менеджера")
    _trim_messages()
    return True


def process_pending(s: InstagramBotSettings | None = None, max_items: int = 15) -> int:
    s = s or InstagramBotSettings.load()
    if not s.is_enabled:
        return 0
    handled = 0
    for _ in range(max_items):
        row = _claim_next()
        if not row:
            break
        try:
            if _process_one(s, row):
                handled += 1
        except Exception as exc:
            log("error", "process", repr(exc))
            InstagramBotMessage.objects.filter(id=row.id).update(
                status=InstagramBotMessage.Status.PENDING
            )
            break
    return handled


def pending_count() -> int:
    return InstagramBotMessage.objects.filter(
        role=InstagramBotMessage.Role.USER, status=InstagramBotMessage.Status.PENDING
    ).count()


def unique_senders_count() -> int:
    """Скільки різних людей писали боту = к-сть карток IgClient (кожен sender має
    картку). Раніше рахувалось distinct sender_id, але Meta.ordering=['id'] ламав
    distinct (over-count) — тепер рахуємо картки."""
    return IgClient.objects.count()


def link_orphan_messages_to_clients() -> int:
    """Прив'язує повідомлення без картки до IgClient (бекофіл легасі історії).

    Для кожного унікального sender_id без картки створює/знаходить IgClient,
    проставляє first_contact_at/last_message_at з історії і лінкує повідомлення.
    Повертає кількість задіяних карток. Ідемпотентна (другий запуск → 0).
    """
    from django.db.models import Max, Min

    sender_ids = list(
        InstagramBotMessage.objects.filter(client__isnull=True)
        .exclude(sender_id="")
        .order_by("sender_id")  # скидаємо Meta.ordering=['id'], інакше distinct ламається
        .values_list("sender_id", flat=True)
        .distinct()
    )
    count = 0
    for sid in sender_ids:
        client = IgClient.get_or_create_for_sender(sid)
        agg = InstagramBotMessage.objects.filter(sender_id=sid).aggregate(
            first=Min("created_at"), last=Max("created_at")
        )
        fields = []
        if not client.first_contact_at and agg["first"]:
            client.first_contact_at = agg["first"]
            fields.append("first_contact_at")
        if agg["last"]:
            client.last_message_at = agg["last"]
            fields.append("last_message_at")
        if fields:
            fields.append("updated_at")
            client.save(update_fields=fields)
        InstagramBotMessage.objects.filter(sender_id=sid, client__isnull=True).update(client=client)
        count += 1
    return count


def _trim_messages() -> None:
    try:
        if InstagramBotMessage.objects.count() > MSG_KEEP_ROWS + 200:
            ids = list(
                InstagramBotMessage.objects.order_by("-id").values_list("id", flat=True)[:MSG_KEEP_ROWS]
            )
            if ids:
                InstagramBotMessage.objects.exclude(id__in=ids).delete()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Сире логування подій (Phase 0 / Task 1) — діагностика форматів вебхуків
# ---------------------------------------------------------------------------
RAW_EVENT_KEEP_ROWS = 400


def _iter_events(payload: dict):
    """Yield (sender_id, recipient_id, message_dict, referral_dict) з payload.

    Покриває обидва канали доставки Meta: entry[].messaging[] (Send/Receive)
    та entry[].changes[] з field=messages (деякі IG-події). Referral береться
    і з події, і з postback.referral (перший контакт із Click-to-IG реклами).
    recipient_id потрібен для echo (повідомлення сторінки/менеджера клієнту).
    """
    for entry in payload.get("entry", []) or []:
        for event in entry.get("messaging", []) or []:
            ref = (
                event.get("referral")
                or (event.get("postback") or {}).get("referral")
                or {}
            )
            yield (
                (event.get("sender") or {}).get("id", ""),
                (event.get("recipient") or {}).get("id", ""),
                event.get("message") or {},
                ref,
            )
        for change in entry.get("changes", []) or []:
            if change.get("field") == "messages":
                value = change.get("value") or {}
                yield (
                    (value.get("sender") or {}).get("id", ""),
                    (value.get("recipient") or {}).get("id", ""),
                    value.get("message") or {},
                    value.get("referral") or {},
                )


def record_raw_event(payload: dict):
    """Зберігає сирий вебхук + витягнуті ознаки (типи вкладень, referral, echo).

    Best-effort: ніколи не кидає, щоб не зламати прийом вебхука. Підрізає
    найстаріші рядки, щоб не накопичувати нескінченно.
    """
    from management.models import InstagramBotRawEvent

    sender_id = ""
    att_types: list[str] = []
    has_referral = False
    has_echo = False
    try:
        for sid, _rid, msg, ref in _iter_events(payload):
            if sid and not sender_id:
                sender_id = sid
            if msg.get("is_echo"):
                has_echo = True
            for att in (msg.get("attachments") or []):
                t = att.get("type") or "unknown"
                if t not in att_types:
                    att_types.append(t)
            if ref or msg.get("referral"):
                has_referral = True
    except Exception:
        pass
    try:
        raw = json.dumps(payload, ensure_ascii=False)[:20000]
    except Exception:
        raw = str(payload)[:20000]
    ev = InstagramBotRawEvent.objects.create(
        sender_id=(sender_id or "")[:64],
        attachment_types=",".join(att_types)[:255],
        has_referral=has_referral,
        has_echo=has_echo,
        payload=raw,
    )
    try:
        if InstagramBotRawEvent.objects.count() > RAW_EVENT_KEEP_ROWS + 100:
            ids = list(
                InstagramBotRawEvent.objects.order_by("-id").values_list("id", flat=True)[:RAW_EVENT_KEEP_ROWS]
            )
            if ids:
                InstagramBotRawEvent.objects.exclude(id__in=ids).delete()
    except Exception:
        pass
    return ev


# ---------------------------------------------------------------------------
# Webhook payload -> черга (швидко, без важкої логіки)
# ---------------------------------------------------------------------------
MEDIA_ATTACH_TYPES = {
    "image", "share", "ig_reel", "reel", "story_mention", "story", "video", "file", "link",
}
MEDIA_MAX = 3


def _extract_media_urls(msg: dict) -> list[str]:
    """Збирає завантажувані URL з повідомлення: вкладення будь-якого медіа-типу
    (а не лише image) + відповідь на сторіс (reply_to.story.url). Дедуп, cap.

    download_image() сам відсіє не-image (відео/файл), тож їх URL безпечні.
    """
    urls: list[str] = []
    for att in (msg.get("attachments") or []):
        t = (att.get("type") or "").lower()
        if t not in MEDIA_ATTACH_TYPES:
            continue
        u = (att.get("payload") or {}).get("url")
        if u:
            urls.append(u)
    story = (msg.get("reply_to") or {}).get("story") or {}
    if story.get("url"):
        urls.append(story["url"])
    out: list[str] = []
    for u in urls:
        if u and u not in out:
            out.append(u)
    return out[:MEDIA_MAX]


def _apply_referral(sender_id: str, ref: dict) -> None:
    """Зберігає атрибуцію реклами (Click-to-IG-Direct) у картку клієнта.

    ref містить ref/ad_id/source та ads_context_data (ad_title, photo_url/
    video_url). Це дає боту зрозуміти, ЩО продавала реклама, ще до питань.
    """
    if not ref:
        return
    client = IgClient.get_or_create_for_sender(sender_id)
    acd = ref.get("ads_context_data") or {}
    client.ad_ref = (str(ref.get("ref") or ""))[:255]
    client.ad_id = (str(ref.get("ad_id") or ""))[:64]
    client.ad_source = (str(ref.get("source") or ""))[:64]
    client.ad_title = (str(acd.get("ad_title") or ""))[:255]
    client.ad_creative_url = (str(acd.get("photo_url") or acd.get("video_url") or ""))[:600]
    try:
        client.referral_payload = ref
    except Exception:
        client.referral_payload = {}
    client.save(update_fields=[
        "ad_ref", "ad_id", "ad_source", "ad_title", "ad_creative_url",
        "referral_payload", "updated_at",
    ])


def handle_webhook_payload(s: InstagramBotSettings, payload: dict) -> int:
    """Розбирає payload вебхука і кладе вхідні в чергу. Повертає к-сть доданих.

    Echo (повідомлення сторінки/менеджера) поки пропускаємо для черги — їх
    використає авто-перехоплення менеджером (Task 21).
    """
    enq = 0
    for sender_id, recipient_id, msg, ref in _iter_events(payload):
        if not msg:
            continue
        if msg.get("is_deleted") or msg.get("is_unsupported"):
            continue
        # Echo (повідомлення сторінки/менеджера) → перехоплення менеджером.
        if msg.get("is_echo"):
            try:
                _handle_echo(recipient_id, msg.get("text", ""))
            except Exception as exc:
                log("warning", "echo", repr(exc))
            continue
        if not sender_id:
            continue
        if ref:
            try:
                _apply_referral(sender_id, ref)
            except Exception as exc:
                log("warning", "referral", repr(exc))
        media = _extract_media_urls(msg)
        if enqueue_inbound(
            s,
            sender_id=sender_id,
            text=msg.get("text", ""),
            mid=msg.get("mid", ""),
            source="webhook",
            attachments=media,
        ):
            enq += 1
    return enq


# ---------------------------------------------------------------------------
# Polling (резервний міст до Live) -> кладе в чергу
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


def poll_ingest(s: InstagramBotSettings) -> dict:
    """Читає інбокс IG і кладе нові вхідні в чергу. Лише коли receive_via_poll."""
    if not s.is_enabled or not s.receive_via_poll:
        return {"ok": True, "enqueued": 0, "skipped": True}
    page_token = get_page_token(s)
    if not page_token:
        return {"ok": False, "error": "no_page_token"}
    conv_ids = get_conv_ids_cached()
    if conv_ids is None:
        conv_ids = refresh_conv_ids(s, page_token)
    if not conv_ids:
        return {"ok": True, "enqueued": 0, "conversations": 0}
    if s.last_error:
        s.last_error = ""
        s.save(update_fields=["last_error"])
    reply_after = s.reply_after or s.last_started_at
    enq = 0
    for cid in conv_ids:
        code, body = _http(
            f"{GRAPH}/{cid}?fields=messages.limit(5)"
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
        latest = msgs[0]
        sender = (latest.get("from") or {}).get("id", "")
        if not sender or sender == s.ig_user_id:
            continue
        created = _parse_ig_time(latest.get("created_time", ""))
        if reply_after and created and created <= reply_after:
            continue
        if enqueue_inbound(
            s, sender_id=sender, text=latest.get("message", ""), mid=latest.get("id", ""), source="poll"
        ):
            enq += 1
    return {"ok": True, "enqueued": enq, "conversations": len(conv_ids)}


# Зворотна сумісність для --once: інгест + обробка.
def poll_once(s: InstagramBotSettings | None = None) -> dict:
    s = s or InstagramBotSettings.load()
    s.heartbeat_at = timezone.now()
    s.last_poll_at = timezone.now()
    s.save(update_fields=["heartbeat_at", "last_poll_at"])
    res = poll_ingest(s)
    res["handled"] = process_pending(s)
    return res


# ---------------------------------------------------------------------------
# Start / Stop / Status
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
    dhb = cache.get("ig_bot_daemon_hb")
    daemon_online = bool(dhb and (time.time() - float(dhb)) < 45)
    return {
        "is_enabled": s.is_enabled,
        "alive": alive,
        "daemon_online": daemon_online,
        "running": s.is_enabled and (daemon_online or alive),
        "heartbeat_at": hb.isoformat() if hb else "",
        "last_inbound_at": s.last_inbound_at.isoformat() if s.last_inbound_at else "",
        "last_reply_at": s.last_reply_at.isoformat() if s.last_reply_at else "",
        "replies_count": s.replies_count,
        "pending": pending_count(),
        "unique_senders": unique_senders_count(),
        "allow_all": not bool(allowed_sender_ids(s)),
        "last_error": s.last_error,
        "direct_source": s.direct_source,
        "gemini_source": s.gemini_source,
        "ai_enabled": s.ai_enabled,
        "gemini_model": s.gemini_model,
        "receive_via_poll": s.receive_via_poll,
        "app_secret_set": bool(app_secret()),
        "trigger_text": s.trigger_text,
        "reply_text": s.reply_text,
        "poll_interval_seconds": s.poll_interval_seconds,
    }
