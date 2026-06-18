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
import time
import urllib.error
import urllib.request
from datetime import datetime

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from management.models import (
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
    s: InstagramBotSettings, history: list[dict], images: list[tuple[str, bytes]] | None = None
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
    sys_text = sys_text.strip()

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.6, "maxOutputTokens": 700},
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
    try:
        with transaction.atomic():
            InstagramBotMessage.objects.create(
                sender_id=sender_id,
                role=InstagramBotMessage.Role.USER,
                text=text or "(зображення)",
                mid=mid or None,
                status=InstagramBotMessage.Status.PENDING,
                source=source,
                attachments=json.dumps(attachments) if attachments else "",
            )
    except IntegrityError:
        return False  # вже у черзі/оброблено (mid unique)
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
        # Анти-абуз: однакове питання багато разів — не жжемо токени Gemini.
        rep = _repeated_question(row.sender_id, row.text)
        if rep > 3 and not row.attachments:
            reply = "Я вже відповів(-ла) на це трохи вище 🙂 Якщо потрібно щось інше — уточніть, будь ласка."
            log("info", "repeat_guard", f"{row.sender_id}: повтор #{rep}, без Gemini")
        else:
            history = _build_history(row.sender_id)
            if not history:
                history = [{"role": "user", "text": row.text}]
            # Зображення-вкладення -> мультимодальний вхід.
            images = []
            if row.attachments:
                try:
                    for url in json.loads(row.attachments)[:3]:
                        img = download_image(url)
                        if img:
                            images.append(img)
                except Exception:
                    pass
            reply = gemini_generate(s, history, images=images or None)
    else:
        if (row.text or "").strip() != s.trigger_text:
            row.status = InstagramBotMessage.Status.DONE
            row.processed_at = timezone.now()
            row.save(update_fields=["status", "processed_at"])
            log("info", "ignored", f"{row.sender_id}: не тригер")
            return False
        reply = s.reply_text

    # Ескалація на людину: модель додає тег [MANAGER], коли потрібен менеджер.
    needs_manager = False
    if reply and "[MANAGER]" in reply:
        needs_manager = True
        reply = reply.replace("[MANAGER]", "").strip()

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
    if needs_manager:
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
    """Скільки різних людей писали боту (для аналітики тесту)."""
    return (
        InstagramBotMessage.objects.filter(role=InstagramBotMessage.Role.USER)
        .values("sender_id")
        .distinct()
        .count()
    )


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
# Webhook payload -> черга (швидко, без важкої логіки)
# ---------------------------------------------------------------------------
def handle_webhook_payload(s: InstagramBotSettings, payload: dict) -> int:
    enq = 0

    def _imgs(msg):
        urls = []
        for att in (msg.get("attachments") or []):
            if (att.get("type") == "image"):
                u = (att.get("payload") or {}).get("url")
                if u:
                    urls.append(u)
        return urls

    def _one(sender_id, msg):
        nonlocal enq
        if not msg or msg.get("is_echo") or msg.get("is_deleted") or msg.get("is_unsupported"):
            return
        if enqueue_inbound(
            s, sender_id=sender_id, text=msg.get("text", ""), mid=msg.get("mid", ""),
            source="webhook", attachments=_imgs(msg),
        ):
            enq += 1

    for entry in payload.get("entry", []) or []:
        for event in entry.get("messaging", []) or []:
            _one((event.get("sender") or {}).get("id", ""), event.get("message") or {})
        for change in entry.get("changes", []) or []:
            if change.get("field") == "messages":
                value = change.get("value") or {}
                _one((value.get("sender") or {}).get("id", ""), value.get("message") or {})
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
