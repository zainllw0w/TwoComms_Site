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
import logging
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from django.core.cache import cache
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, F, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from management.models import (
    IgClient,
    IgBotNotification,
    IgConversationAnalysisJob,
    IgPollCursor,
    InstagramBotLog,
    InstagramBotMessage,
    InstagramBotSettings,
)

GRAPH_VERSION = "v25.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
INSTAGRAM_GRAPH = f"https://graph.instagram.com/{GRAPH_VERSION}"
LEGACY_PAGE_TRANSPORT = "legacy_page"
INSTAGRAM_LOGIN_TRANSPORT = "instagram_login"
GENAI = "https://generativelanguage.googleapis.com/v1beta"

LOG_KEEP_ROWS = 500
HISTORY_LIMIT = 12          # скільки останніх реплік даємо моделі
MAX_ATTEMPTS = 3            # ретраї обробки одного повідомлення
PAGE_TOKEN_TTL = 1200
INSTAGRAM_TOKEN_REFRESH_INTERVAL = 30 * 24 * 3600
INSTAGRAM_TOKEN_REFRESH_RETRY = 24 * 3600
INSTAGRAM_TOKEN_CACHE_TTL = 70 * 24 * 3600
HTTP_TIMEOUT = 12
CONV_LIST_TIMEOUT = 30
CONV_PAGE_LIMIT = 50
CONV_DISCOVERY_PAGES_PER_REFRESH = 5
CONV_MAX_IDS = 500
CONV_MAX_PAGES = (CONV_MAX_IDS + CONV_PAGE_LIMIT - 1) // CONV_PAGE_LIMIT
CONV_MIN_INTERVAL = 0.5  # Meta Conversations API: at most 2 requests/second.
CONV_CACHE_TTL = 3600
CONV_REFRESH_LOCK_TTL = CONV_LIST_TIMEOUT * CONV_DISCOVERY_PAGES_PER_REFRESH + 30
INGRESS_DEGRADATION_TTL = 15 * 60
WEBHOOK_ERROR_WINDOW_SECONDS = 5 * 60
WEBHOOK_ERROR_MIN_COUNT = 5
WEBHOOK_ERROR_MIN_RATE = 0.25
_CONV_ID_RE = re.compile(r"^[A-Za-z0-9:_-]{1,255}$")
_CONV_CURSOR_RE = re.compile(r"^[A-Za-z0-9_+=/.:~-]{1,1024}$")
_SENDER_ID_RE = re.compile(r"^[A-Za-z0-9:_-]{1,64}$")
_GRAPH_VERSION_PATH_RE = re.compile(r"^/v\d+(?:\.\d+)?(?:/|$)")
POLL_MESSAGE_TIMEOUT = 12
POLL_MESSAGE_MAX_PAGES = 5
POLL_INSTAGRAM_MESSAGE_LIMIT = 20
POLL_REPLY_WINDOW = timedelta(hours=23)
POLL_MAX_REQUESTS = 40
POLL_MAX_SECONDS = 20
POLL_FAILURE_BACKOFF_MAX = 6 * 60 * 60
AUTOMATION_LEASE_TTL = timedelta(minutes=3)
PROFILE_REFRESH_INTERVAL = 15 * 60
PROFILE_REFRESH_BATCH = 25
PROFILE_PERMISSION_COOLDOWN = 6 * 60 * 60


@dataclass(frozen=True)
class ProviderDeliveryReceipt:
    """Structured Meta receipt with an explicit legacy tuple projection."""

    ok: bool
    kind: str
    hint: str = ""
    provider_message_id: str = ""

    def as_legacy_tuple(self) -> tuple[bool, str, str]:
        return self.ok, self.kind, self.hint


def _delivery_receipt(result) -> tuple[bool, str, str, str, bool]:
    """Normalize old tuple callers while making an explicit receipt auditable."""
    if isinstance(result, ProviderDeliveryReceipt):
        return (
            bool(result.ok),
            str(result.kind or ""),
            str(result.hint or ""),
            str(result.provider_message_id or ""),
            True,
        )
    ok, kind, hint = result
    return bool(ok), str(kind or ""), str(hint or ""), "", False


def _provider_message_id(response_body) -> str:
    try:
        payload = json.loads(response_body or "{}") if isinstance(response_body, str) else response_body
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("message_id") or payload.get("id") or "").strip()

# Керуючі теги, які модель може додавати у відповідь (вирізаються перед
# відправкою клієнту). [STAGE:x] просуває воронку, [MANAGER] кличе людину.
STAGE_VALUES = {s.value for s in IgClient.Stage}
MODEL_HARD_STAGES = {
    IgClient.Stage.PAID,
    IgClient.Stage.ORDER_CREATED,
    IgClient.Stage.DONE,
}
_CONTROL_TAG_RE = re.compile(r"\[([A-Z][A-Z_]*)(?::([^\]]+))?\]")
_PRICE_CLAIM_RE = re.compile(
    r"(?<![\d])(?P<amount>\d{3,7}(?:[.,]\d{1,2})?)\s*(?:грн|₴|uah)\b",
    re.IGNORECASE,
)
_PRICE_RANGE_RE = re.compile(
    r"(?:"
    r"\b(?:від|from)\s*\d{3,7}(?:[.,]\d{1,2})?\s*(?:грн|₴|uah)?\s*"
    r"(?:до|to)\s*\d{3,7}(?:[.,]\d{1,2})?\s*(?:грн|₴|uah)"
    r"|\b\d{3,7}(?:[.,]\d{1,2})?\s*[-–/]\s*"
    r"\d{3,7}(?:[.,]\d{1,2})?\s*(?:грн|₴|uah)"
    r")",
    re.IGNORECASE,
)
_OPTION_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{0,48}$", re.IGNORECASE)
_SECRET_PARAM_RE = re.compile(
    r"((?:access_token|client_secret|api[_-]?key|password|token)=)[^&\s]+",
    re.IGNORECASE,
)


def _redact_secret_text(value: str) -> str:
    """Remove credential-like query parameters before writing diagnostics."""
    return _SECRET_PARAM_RE.sub(r"\1[REDACTED]", str(value or ""))


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
        if name == "item":
            tags.setdefault("items", []).append(val)
        elif name in {"option", "opt"}:
            tags.setdefault("options", []).append(val)
        else:
            parsed = val or True
            if name in tags and tags[name] != parsed:
                tags["_invalid"] = True
                tags.setdefault("_conflicts", []).append(name)
            else:
                tags[name] = parsed
    clean = _CONTROL_TAG_RE.sub("", reply)
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return clean, tags


def _apply_stage(client, stage_value) -> bool:
    """Apply only model-authorized workflow stages.

    Payment and fulfilment stages belong exclusively to verified provider/order
    services.  The model may neither claim them nor regress an existing hard
    stage through a generated control tag.
    """
    if not client or not stage_value or not isinstance(stage_value, str):
        return False
    if stage_value not in STAGE_VALUES:
        return False
    if stage_value in MODEL_HARD_STAGES or client.stage in MODEL_HARD_STAGES:
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


# Скільки тримати паузу після останньої репліки менеджера. Порахований факт із
# прода 02.08.2026: у `manager_takeover` перебувало **57 клієнтів із 289** (20%
# бази), найстаріший — з 19 червня, і зняти це можна було лише руками через
# адмінку. Тобто одна репліка менеджера півтора місяця тому назавжди виключала
# автоматику для клієнта, і жодного сигналу про це не було.
#
# 12 годин обрані так: жива передача діалогу менеджеру триває хвилини-години,
# і поки менеджер пише, кожна його репліка зсуває відлік. Якщо ж людина пішла
# і не повернулась, до наступного дня бот має право відповісти сам — інакше
# клієнт просто лишається без відповіді.
MANAGER_TAKEOVER_IDLE_HOURS = 12


def maybe_release_stale_takeover(client) -> bool:
    """Зняти паузу, якщо менеджер давно не писав.

    Ручне «повернути бота» лишається головним шляхом; це — страховка від
    назавжди замовклого бота, у тому числі від хибного takeover.
    """
    if not client or not getattr(client, "pk", None):
        return False
    if not client.manager_takeover:
        return False
    if str(client.paused_reason or "") != "manager_takeover":
        return False
    last = client.last_manager_message_at or client.paused_at
    if not last:
        return False
    idle_hours = (timezone.now() - last).total_seconds() / 3600.0
    if idle_hours < MANAGER_TAKEOVER_IDLE_HOURS:
        return False
    # Явна відмова клієнта від автоматичних повідомлень сильніша за таймаут.
    active_opt_out = bool(
        client.opted_out_at
        and (not client.opted_in_at or client.opted_in_at < client.opted_out_at)
    )
    if active_opt_out or client.is_blocked or client.hidden_at:
        return False
    from management.services.ig_reply_boundary import pause_reply_boundary

    try:
        with pause_reply_boundary():
            with transaction.atomic():
                fresh = IgClient.objects.select_for_update().filter(pk=client.pk).first()
                if fresh is None or not fresh.manager_takeover:
                    return False
                if str(fresh.paused_reason or "") != "manager_takeover":
                    return False
                fresh_last = fresh.last_manager_message_at or fresh.paused_at
                if fresh_last and (timezone.now() - fresh_last).total_seconds() / 3600.0 < MANAGER_TAKEOVER_IDLE_HOURS:
                    return False
                fresh.manager_takeover = False
                fresh.bot_paused = False
                fresh.paused_reason = ""
                fresh.reply_permission_epoch = int(fresh.reply_permission_epoch or 0) + 1
                fresh.save(update_fields=[
                    "manager_takeover", "bot_paused", "paused_reason",
                    "reply_permission_epoch", "updated_at",
                ])
    except Exception as exc:  # noqa: BLE001
        log("warning", "takeover_release", repr(exc))
        return False
    client.manager_takeover = False
    client.bot_paused = False
    client.paused_reason = ""
    log(
        "info",
        "takeover_released",
        f"{client.igsid}: менеджер не писав {int(idle_hours)} год — бот повернувся",
    )
    notify_manager(
        f"🤖 IG: бот знову відповідає клієнту {client.username or client.igsid} — "
        f"від вашої останньої репліки минуло {int(idle_hours)} год. "
        "Якщо діалог ще ваш, поставте бота на паузу в картці клієнта.",
        dedupe_key=f"takeover_released:{client.pk}:{int(idle_hours) // 24}",
        event_type="takeover_released",
        client=client,
    )
    return True


def _client_blocked(client) -> bool:
    """Бот не відповідає, якщо клієнта поставлено на паузу або заблоковано."""
    active_opt_out = bool(
        client
        and client.opted_out_at
        and (not client.opted_in_at or client.opted_in_at < client.opted_out_at)
    )
    return bool(
        client
        and (client.bot_paused or client.is_blocked or client.hidden_at or active_opt_out)
    )


def _register_spam(client) -> bool:
    """+1 спам-страйк. На SPAM_STRIKES_LIMIT — пауза + стадія SPAM + сповіщення.
    Повертає True, якщо клієнта заблоковано цим страйком."""
    client.spam_strikes = (client.spam_strikes or 0) + 1
    fields = ["spam_strikes", "updated_at"]
    blocked = client.spam_strikes >= SPAM_STRIKES_LIMIT
    if blocked:
        client.bot_paused = True
        client.reply_permission_epoch = int(client.reply_permission_epoch or 0) + 1
        client.paused_reason = "spam"
        client.paused_at = timezone.now()
        fields += ["bot_paused", "reply_permission_epoch", "paused_reason", "paused_at"]
    client.save(update_fields=fields)
    try:
        from management.services.ig_funnel_analytics import record_drop_off_for_client

        record_drop_off_for_client(
            client,
            kind="spam",
            reason_code="spam_marker",
            occurred_at=timezone.now(),
            stage=client.stage,
            actor="bot_classifier",
            evidence={"spam_strikes": int(client.spam_strikes or 0)},
            is_recoverable=False,
        )
    except DatabaseError:
        raise
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


def _register_outgoing_message(message_id: str, recipient_id: str = "", *, kind: str = "text") -> None:
    """Запам'ятати наш `message_id`, щоб не прийняти власне echo за менеджера."""
    if not message_id:
        return
    try:
        from management.services.ig_outgoing_registry import register_outgoing

        register_outgoing(message_id, recipient_id=recipient_id, kind=kind)
    except Exception as exc:  # noqa: BLE001
        log("warning", "outgoing_registry", repr(exc))


def _mark_bot_sent(recipient_id: str, text: str) -> None:
    """Позначає текст, який бот шле конкретному отримувачу — щоб відрізнити від
    відлуння повідомлення менеджера (echo). Привʼязка до отримувача прибирає
    хибні збіги між клієнтами з однаковим текстом."""
    try:
        cache.set(_bot_sent_key(recipient_id, text), 1, 1800)
    except Exception:
        pass


def _clear_bot_sent(recipient_id: str, text: str) -> None:
    """Roll back a speculative echo marker after a definite provider rejection."""
    try:
        cache.delete(_bot_sent_key(recipient_id, text))
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
    "формую персональну пропозицію", "сформую персональну пропозицію",
    "формирую персональное предложение", "сформирую персональное предложение",
    "preparing your personal offer",
)

_PAYLINK_REFERENCE_RE = re.compile(
    r"\b(?:посилання|лінк\w*|ссылк\w*|link)\b",
    re.IGNORECASE,
)
_PAYLINK_REFUSAL_RE = re.compile(
    r"(?:\b(?:посилання|лінк\w*|ссылк\w*|link)\b.{0,24}"
    r"\bне\s+(?:нужн\w*|потрібн\w*|треба|надо)\b|"
    r"\bне\s+(?:нужн\w*|потрібн\w*|треба|надо|хочу|буду)\b.{0,24}"
    r"\b(?:посилання|лінк\w*|ссылк\w*|link)\b|"
    r"\bне\s+(?:присыл\w*|надсила\w*|відправля\w*|отправля\w*)\b.{0,24}"
    r"\b(?:посилання|лінк\w*|ссылк\w*|link)\b|"
    r"\b(?:do\s+not|don't|dont)\s+(?:need|want|send)\b.{0,24}\blink\b|"
    r"\bno\s+(?:payment\s+)?link\b)",
    re.IGNORECASE,
)
_PAYLINK_ACTION_RE = re.compile(
    r"\b(?:ось|вот|трим\w*|держ\w*|дай\w*|дайте|скин\w*|надішл\w*|"
    r"пришл\w*|send|share|form\w*|с?форм\w*|персональн\w*|personal)\b",
    re.IGNORECASE,
)
_PAYLINK_CONTEXT_RE = re.compile(
    r"\b(?:оплат\w*|передоплат\w*|предоплат\w*|оформл\w*|замовл\w*|заказ\w*|"
    r"checkout|payment|offer)\b",
    re.IGNORECASE,
)
_CHECKOUT_SELECTION_CONTEXT_KEY = "assisted_checkout_selection"
_CHECKOUT_COLOR_PATTERNS = {
    "black": re.compile(r"(?<!\w)(?:black|чорн\w*|черн\w*)(?!\w)", re.IGNORECASE),
    "white": re.compile(
        r"(?<!\w)(?:white|біл(?:ий|а|е|і|ого|ій|ому|им|их|у)?|"
        r"бел(?:ый|ая|ое|ые|ого|ой|ому|ым|ых|ую)?)(?!\w)",
        re.IGNORECASE,
    ),
    "pink": re.compile(r"(?<!\w)(?:pink|рожев\w*|розов\w*)(?!\w)", re.IGNORECASE),
    "olive": re.compile(r"(?<!\w)(?:olive|олив\w*)(?!\w)", re.IGNORECASE),
    "khaki": re.compile(r"(?<!\w)(?:khaki|хакі|хаки)(?!\w)", re.IGNORECASE),
    "gray": re.compile(
        r"(?<!\w)(?:gray|grey|сір\w*|"
        r"сер(?:ый|ая|ое|ые|ого|ой|ому|ым|ых|ую)?)(?!\w)",
        re.IGNORECASE,
    ),
}
_CHECKOUT_COLOR_NEGATION_PREFIX_RE = re.compile(
    r"(?:^|\b)(?:не(?:\s+\w+){0,2}|без|кроме|окрім|not|without|except)\s+$",
    re.IGNORECASE,
)

_PURCHASE_COMMITMENT_RE = re.compile(
    r"\b(хочу|беру|забираю|оформл\w*|замовл\w*|заказ\w*|купл\w*|куп\w*|"
    r"давайте|підтверджую|подтверждаю)\b",
    re.IGNORECASE,
)


def _control_product_id(control: dict) -> int | None:
    """Parse a model product tag without treating JSON booleans as IDs."""
    if not isinstance(control, dict) or "product" not in control:
        return None
    raw = control.get("product")
    if isinstance(raw, bool):
        return None
    try:
        product_id = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return product_id if product_id > 0 else None


def _control_positive_int(control: dict, key: str, *, default: int = 1, maximum: int = 50) -> int | None:
    """Parse bounded numeric control and fail closed when it was explicit."""
    if not isinstance(control, dict) or key not in control:
        return default
    raw = control.get(key)
    if isinstance(raw, bool):
        return None
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if 1 <= value <= maximum else None


def _control_item_specs(control: dict) -> list[dict]:
    """Parse repeated [ITEM:id|qty|size|fit|color_variant_id|key=value;...] tags."""
    raw_items = control.get("items") if isinstance(control, dict) else None
    if not isinstance(raw_items, (list, tuple)):
        return []
    specs = []
    for raw in raw_items:
        parts = [part.strip() for part in str(raw or "").split("|")]
        if len(parts) not in {4, 5, 6}:
            return []
        try:
            product_id = int(parts[0])
            qty = int(parts[1])
        except (TypeError, ValueError):
            return []
        if product_id <= 0 or qty < 1 or qty > 50:
            return []
        color_variant_id = None
        if len(parts) > 4 and parts[4]:
            try:
                color_variant_id = int(parts[4])
            except (TypeError, ValueError):
                return []
            if color_variant_id <= 0:
                return []
        option_values = _parse_option_pairs(parts[5]) if len(parts) > 5 and parts[5] else {}
        if option_values is None:
            return []
        spec = {
            "product_id": product_id,
            "qty": qty,
            "size": parts[2].upper()[:16],
            "fit_option_code": parts[3].lower()[:50],
            "color_variant_id": color_variant_id,
        }
        if option_values:
            spec["option_values"] = option_values
        specs.append(spec)
    return specs


def _parse_option_pairs(raw) -> dict | None:
    """Parse bounded ``key=value;key=value`` option payloads from model tags."""
    value = str(raw or "").strip()
    if not value:
        return {}
    result = {}
    for pair in value.split(";"):
        if "=" not in pair:
            return None
        key, option = (part.strip().lower() for part in pair.split("=", 1))
        if not _OPTION_KEY_RE.fullmatch(key) or not option or len(option) > 100:
            return None
        if key in result:
            return None
        result[key] = option
    return result if len(result) <= 12 else None


def _control_option_values(control: dict) -> dict | None:
    """Return arbitrary option axes announced by ``[OPTION:key=value]`` tags."""
    if not isinstance(control, dict):
        return {}
    result = {}
    for raw in control.get("options") or ():
        parsed = _parse_option_pairs(raw)
        if parsed is None:
            return None
        for key, value in parsed.items():
            if key in result and result[key] != value:
                return None
            result[key] = value
    return result


def _should_pin_product_media(media: list[dict] | None) -> bool:
    """Only a purchase candidate may change durable current-product memory."""
    return any(
        isinstance(item, dict)
        and item.get("role") == "product"
        and item.get("intent") == "purchase_candidate"
        and item.get("catalog_match_allowed") is True
        for item in (media or [])
    )


def _conversation_negotiated_price(client, control: dict) -> Decimal | None:
    """Validate [PRICE:x] against persisted chat evidence before invoicing."""
    if not isinstance(control, dict):
        return None
    raw = control.get("price") if "price" in control else None
    if isinstance(raw, bool) or not client:
        return None
    value = None
    if raw is not None:
        try:
            value = Decimal(str(raw).replace(",", ".")).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if value <= 0 or value > Decimal("1000000"):
            return None
    try:
        from management.services.bot_orders import _validated_negotiated_price
        from storefront.models import Product, ProductStatus

        product = None
        product_id = _control_product_id(control)
        if product_id:
            product = Product.objects.filter(
                pk=product_id,
                status=ProductStatus.PUBLISHED,
            ).first()
        if product is None:
            product = getattr(client, "current_product", None)
        if product is None:
            return _validated_negotiated_price(client, value)
        return _validated_negotiated_price(client, value, product=product)
    except Exception:
        return None


def _validated_price_quote(client, control: dict) -> dict | None:
    """Validate a delivered-price marker against authoritative configuration pricing."""
    if not client or not isinstance(control, dict) or control.get("_invalid"):
        return None
    raw = control.get("price_quoted")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        amount = Decimal(str(raw).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if amount <= 0 or amount > Decimal("1000000"):
        return None
    item_specs = None
    if "items" in control:
        item_specs = _control_item_specs(control)
        if len(item_specs) != 1:
            return None
    item_spec = item_specs[0] if item_specs else None
    tagged_product_id = _control_product_id(control)
    item_product_id = item_spec.get("product_id") if item_spec else None
    if tagged_product_id and item_product_id and tagged_product_id != item_product_id:
        return None
    product_id = (
        tagged_product_id
        or item_product_id
        or getattr(client, "current_product_id", None)
    )
    if not product_id:
        return None
    from storefront.models import Product, ProductStatus

    product = Product.objects.filter(pk=product_id, status=ProductStatus.PUBLISHED).first()
    if product is None:
        return None
    selection = _checkout_selection_state(client, product_id)
    raw_variant_id = (
        control.get("color_variant_id")
        or control.get("variant")
        or (item_spec or {}).get("color_variant_id")
        or selection.get("color_variant_id")
    )
    try:
        variant_id = int(raw_variant_id or 0)
    except (TypeError, ValueError):
        return None
    tagged_fit = str(control.get("fit") or "").strip().lower()
    item_fit = str((item_spec or {}).get("fit_option_code") or "").strip().lower()
    if tagged_fit and item_fit and tagged_fit != item_fit:
        return None
    fit_code = str(
        tagged_fit or item_fit or selection.get("fit_option_code") or ""
    ).strip().lower()
    control_options = _control_option_values(control)
    if control_options is None:
        return None
    persisted_options = selection.get("option_values")
    persisted_options = dict(persisted_options) if isinstance(persisted_options, dict) else {}
    item_options = (item_spec or {}).get("option_values") or {}
    if not isinstance(item_options, dict):
        return None
    for key, value in item_options.items():
        if key in control_options and control_options[key] != value:
            # An explicit [OPTION] tag must agree with the item snapshot.
            return None
    option_values = {**persisted_options, **item_options, **control_options}
    if fit_code:
        option_values["fit"] = fit_code
    if "price" in control:
        negotiated = _conversation_negotiated_price(client, control)
        if negotiated is not None and negotiated == amount:
            return {
                "amount": str(amount),
                "product_id": int(product_id),
                "color_variant_id": variant_id or None,
                "fit_option_code": fit_code,
                "option_values": option_values,
                "price_source": "conversation_evidence",
            }
    from management.services.ig_catalog_pricing import resolve_product_pricing

    pricing = resolve_product_pricing(
        product,
        selected_variant_id=variant_id or None,
        option_values=option_values or None,
    )
    if not pricing.get("exact") or pricing.get("minimum") != amount:
        return None
    return {
        "amount": str(amount),
        "product_id": int(product_id),
        "color_variant_id": variant_id or None,
        "fit_option_code": fit_code,
        "option_values": option_values,
        "price_source": "catalog",
    }


def _extract_authoritative_price_claim(client, reply: str, control: dict):
    """Bind one exact customer-facing amount to the same catalog truth as checkout.

    Models sometimes omit the hidden ``[PRICE_QUOTED]`` tag while still writing a
    concrete amount.  A single amount with a currency suffix is therefore
    treated as an exact claim and validated server-side.  A mismatch is
    fail-closed so a cheaper base price can never be sent for a surcharge
    variant.  Ranges (multiple amounts) remain descriptive and are not silently
    converted into an exact quote.
    """
    if not isinstance(control, dict) or not isinstance(reply, str):
        return reply, control, None
    matches = list(_PRICE_CLAIM_RE.finditer(reply))
    range_match = _PRICE_RANGE_RE.search(reply)
    if range_match:
        range_amounts = re.findall(
            r"\d{3,7}(?:[.,]\d{1,2})?",
            range_match.group(0),
        )
        claimed_amounts = [match.group("amount").replace(",", ".") for match in matches]
        if (
            len(claimed_amounts) <= len(range_amounts)
            and all(
            amount.replace(",", ".") in {
                value.replace(",", ".") for value in range_amounts
            }
            for amount in claimed_amounts
            )
            and all(
                range_match.start() <= match.start()
                and match.end() <= range_match.end()
                for match in matches
            )
        ):
            if "price_quoted" in control:
                control["_price_claim_invalid"] = True
                return None, control, None
            return reply, control, None
    raw_amounts = [match.group("amount").replace(",", ".") for match in matches]
    amounts = list(raw_amounts)
    payment_amount = str(control.get("payment") or "").replace(",", ".")
    payment_only = False
    if payment_amount:
        try:
            payment_decimal = Decimal(payment_amount).quantize(Decimal("0.01"))
            payment_only = len(raw_amounts) == 1 and (
                Decimal(raw_amounts[0]).quantize(Decimal("0.01")) == payment_decimal
            )
            amounts = [
                value for value in amounts
                if Decimal(value).quantize(Decimal("0.01")) != payment_decimal
            ]
        except (InvalidOperation, TypeError, ValueError):
            pass
    amounts = list(dict.fromkeys(amounts))
    if not amounts and "price_quoted" not in control:
        if not raw_amounts or payment_only:
            return reply, control, None
        control["_price_claim_invalid"] = True
        return None, control, None
    if len(amounts) != 1:
        control["_price_claim_invalid"] = True
        return None, control, None
    raw = amounts[0]
    explicit_marker = control.get("price_quoted")
    if explicit_marker is not None:
        try:
            if Decimal(str(explicit_marker).replace(",", ".")).quantize(Decimal("0.01")) != Decimal(raw).quantize(Decimal("0.01")):
                control["_price_claim_invalid"] = True
                return None, control, None
        except (InvalidOperation, TypeError, ValueError):
            control["_price_claim_invalid"] = True
            return None, control, None
    if "price_quoted" not in control:
        control["price_quoted"] = raw
    quote = _validated_price_quote(client, control)
    if quote is not None:
        return reply, control, quote
    control["_price_claim_invalid"] = True
    return None, control, None


def _conversation_payment_amount(client, control: dict) -> Decimal | None:
    """Validate/infer the exact current-episode prepayment amount."""
    if not isinstance(control, dict) or not client:
        return None
    raw = control.get("payment") if "payment" in control else None
    if isinstance(raw, bool):
        return None
    try:
        from management.services.bot_orders import _validated_payment_amount

        return _validated_payment_amount(client, raw)
    except Exception:
        return None


def _looks_like_paylink_request(text: str) -> bool:
    normalized = " ".join(str(text or "").split()).casefold()
    if not normalized:
        return False
    if _PAYLINK_REFERENCE_RE.search(normalized) and _PAYLINK_REFUSAL_RE.search(normalized):
        return False
    if any(phrase in normalized for phrase in PAYLINK_PHRASES):
        return True
    return bool(
        _PAYLINK_REFERENCE_RE.search(normalized)
        and (
            _PAYLINK_ACTION_RE.search(normalized)
            or _PAYLINK_CONTEXT_RE.search(normalized)
        )
    )


def _checkout_selection_state(client, product_id) -> dict:
    context = getattr(client, "sales_context", {})
    if not isinstance(context, dict):
        return {}
    state = context.get(_CHECKOUT_SELECTION_CONTEXT_KEY)
    if not isinstance(state, dict):
        return {}
    try:
        state_product_id = int(state.get("product_id") or 0)
        product_id = int(product_id or 0)
    except (TypeError, ValueError):
        return {}
    return dict(state) if product_id and state_product_id == product_id else {}


def _persist_checkout_selection(client, product_id, selection: dict) -> None:
    if not getattr(client, "pk", None) or not product_id or not selection:
        return
    context = dict(getattr(client, "sales_context", {}) or {})
    value = {
        "product_id": int(product_id),
        "fit_option_code": str(selection.get("fit_option_code") or "")[:50],
    }
    option_values = selection.get("option_values")
    if isinstance(option_values, dict):
        normalized_options = _parse_option_pairs(
            ";".join(
                f"{key}={value}"
                for key, value in option_values.items()
            )
        )
        if normalized_options:
            value["option_values"] = normalized_options
    try:
        color_variant_id = int(selection.get("color_variant_id") or 0)
    except (TypeError, ValueError):
        color_variant_id = 0
    if color_variant_id > 0:
        value["color_variant_id"] = color_variant_id
    pay_type = str(selection.get("pay_type") or "").strip().lower()
    if pay_type in {"full", "prepay"}:
        value["pay_type"] = pay_type
    if context.get(_CHECKOUT_SELECTION_CONTEXT_KEY) == value:
        return
    context[_CHECKOUT_SELECTION_CONTEXT_KEY] = value
    client.sales_context = context
    client.save(update_fields=["sales_context", "updated_at"])


def _persist_control_selection_unlocked(client, control: dict, *, product_id=None) -> list[str]:
    """Зберегти конфігурацію, яку модель назвала тегами, навіть без [PAYLINK].

    Без цього воронка не рухалась. Модель питала фасон, клієнт відповідав
    «classic», модель ставила [FIT:classic] — але зберігалось це лише всередині
    `finalize_paylink`, тобто **тільки** коли того ж ходу створювалось посилання.
    Хід «уточнили фасон, тепер питаємо розмір» нічого не зберігав, і наступного
    разу фасон знову був невідомий. Звідси нескінченне коло уточнень.

    Тепер кожен хід, у якому модель дізналась факт, цей факт фіксує. Модель
    накопичує стан крок за кроком, як це робить продавець у голові.
    """
    if not getattr(client, "pk", None) or not isinstance(control, dict):
        return []
    if control.get("_invalid"):
        return []
    product_id = _control_product_id(control) or product_id or getattr(client, "current_product_id", None)
    try:
        product_id = int(product_id or 0)
    except (TypeError, ValueError):
        product_id = 0
    if not product_id:
        return []

    changed: list[str] = []
    update_fields: list[str] = []

    size = str(control.get("size") or "").strip().upper()[:16]
    if size and size != str(getattr(client, "current_size", "") or "").strip().upper():
        client.current_size = size
        update_fields.append("current_size")
        changed.append("size")

    qty = _control_positive_int(control, "qty", default=0)
    if qty and qty != int(getattr(client, "current_qty", 1) or 1):
        client.current_qty = qty
        update_fields.append("current_qty")
        changed.append("quantity")

    if update_fields:
        try:
            client.save(update_fields=[*update_fields, "updated_at"])
        except Exception as exc:  # noqa: BLE001
            log("warning", "selection_persist", f"{getattr(client, 'pk', '?')}: {exc!r}")
            changed = [item for item in changed if item not in {"size", "quantity"}]

    selection = _checkout_selection_state(client, product_id) or {"product_id": product_id}
    fit_code = str(control.get("fit") or "").strip().lower()[:50]
    if fit_code and fit_code != str(selection.get("fit_option_code") or ""):
        selection["fit_option_code"] = fit_code
        changed.append("fit")
    variant_id = control.get("color_variant_id") or control.get("variant")
    try:
        variant_id = int(variant_id or 0)
    except (TypeError, ValueError):
        variant_id = 0
    if variant_id > 0 and variant_id != int(selection.get("color_variant_id") or 0):
        selection["color_variant_id"] = variant_id
        changed.append("color")
    option_values = _control_option_values(control)
    if option_values is None:
        return []
    if option_values:
        current_options = selection.get("option_values")
        current_options = dict(current_options) if isinstance(current_options, dict) else {}
        if any(current_options.get(key) != value for key, value in option_values.items()):
            current_options.update(option_values)
            selection["option_values"] = current_options
            changed.extend(f"option:{key}" for key in option_values)
    if changed and selection:
        _persist_checkout_selection(client, product_id, selection)
    return changed


def persist_control_selection(
    client,
    control: dict,
    *,
    product_id=None,
    source_message_id=None,
) -> list[str]:
    """Persist a model-confirmed configuration and append its funnel fact atomically."""
    from django.db import transaction

    from management.models import IgClient, IgFunnelStepEvent
    from management.services.ig_commercial_episodes import (
        ensure_open_episode_for_locked_client,
    )
    from management.services.ig_funnel_analytics import (
        record_client_step_event_in_transaction,
    )

    if not getattr(client, "pk", None):
        return []
    with transaction.atomic():
        locked = IgClient.objects.select_for_update().get(pk=client.pk)
        changed = _persist_control_selection_unlocked(
            locked,
            control,
            product_id=product_id,
        )
        resolved_product_id = _control_product_id(control) or product_id or locked.current_product_id
        selection = _checkout_selection_state(locked, resolved_product_id)
        fit_code = str(selection.get("fit_option_code") or "").strip().lower()
        size = str(locked.current_size or "").strip().upper()
        try:
            variant_id = int(selection.get("color_variant_id") or 0)
        except (TypeError, ValueError):
            variant_id = 0
        if resolved_product_id and size and (fit_code or variant_id > 0):
            episode = ensure_open_episode_for_locked_client(
                locked,
                materialization_prefix="ig-funnel",
            )
            event_key = (
                f"ig-variant-selected:{episode.pk}:{int(resolved_product_id)}:"
                f"{variant_id}:{fit_code}:{size}:{int(locked.current_qty or 1)}"
            )
            evidence = {
                "product_id": int(resolved_product_id),
                "color_variant_id": variant_id or None,
                "fit_option_code": fit_code,
                "size": size,
                "qty": int(locked.current_qty or 1),
            }
            if source_message_id:
                evidence["source_message_id"] = int(source_message_id)
            record_client_step_event_in_transaction(
                locked,
                event_type=IgFunnelStepEvent.Type.VARIANT_SELECTED,
                event_key=event_key,
                occurred_at=timezone.now(),
                stage=locked.stage,
                actor="bot",
                evidence=evidence,
            )
        for field in (
            "current_product_id",
            "current_size",
            "current_color",
            "current_qty",
            "sales_context",
        ):
            setattr(client, field, getattr(locked, field))
    return changed


def _wants_paylink(
    reply: str,
    control: dict,
    *,
    trigger_text: str = "",
) -> tuple[bool, str]:
    """Чи треба сформувати посилання на оплату і який тип (full/prepay).
    Тригер: тег [PAYLINK:x] АБО обіцянка посилання у тексті бота (фолбек, якщо
    модель забула тег). Тип беремо з тегу, інакше визначаємо за словом «передопл»."""
    if (
        _PAYLINK_REFERENCE_RE.search(str(trigger_text or ""))
        and _PAYLINK_REFUSAL_RE.search(str(trigger_text or ""))
    ):
        return False, "full"
    val = control.get("paylink")
    combined = " ".join(part for part in (str(reply or ""), str(trigger_text or "")) if part)
    low = combined.casefold()
    if val or _looks_like_paylink_request(reply) or _looks_like_paylink_request(trigger_text):
        if isinstance(val, str) and val in ("full", "prepay"):
            return True, val
        pt = "prepay" if ("передопл" in low or "предопл" in low) else "full"
        return True, pt
    return False, "full"


def _has_open_paid_deal(client) -> bool:
    """Чи є оплачена угода, по якій замовлення ще не завершене.

    Саме це, а не «колись платив», є причиною не створювати новий рахунок:
    гроші вже прийшли, і другий рахунок став би дублем. Коли ж замовлення
    закрите (`order_created` + виконане) або скасоване, людина має повне право
    купити знову — і це нормальний, очікуваний повторний продаж.
    """
    if not getattr(client, "pk", None):
        return False
    from management.models import IgDeal
    from management.services.bot_payment_truth import verified_payment_q

    return (
        IgDeal.objects.filter(client=client)
        .filter(verified_payment_q())
        .exclude(status=IgDeal.Status.CANCELLED)
        .filter(order__isnull=True)
        .exists()
    )


def payment_link_allowed(client, control: dict, reply: str) -> bool:
    """Require a product and purchase evidence before creating an invoice.

    A model phrase such as ``"сформую посилання"`` is not itself a purchase
    decision. The provider deal/link path is authoritative and must remain
    unreachable for a size/price question or an unresolved image.
    """
    if not client or not isinstance(control, dict):
        return False
    if control.get("_invalid"):
        return False
    if getattr(client, "pk", None):
        # Захист від дубля рахунку по **поточній незакритій** угоді, а не
        # пожиттєва заборона продавати. Раніше тут стояв
        # `client_has_verified_payment(client)`, тобто будь-хто, хто колись
        # оплатив, більше ніколи не міг отримати посилання: постійний клієнт не
        # мав можливості купити вдруге. W3 навчила систему бачити покупців —
        # і цей гейт почав різати саме їх.
        try:
            if _has_open_paid_deal(client):
                return False
        except Exception:
            # A provider-truth lookup failure must not open a new invoice path.
            return False
    explicit_item_specs = None
    if "items" in control:
        explicit_item_specs = _control_item_specs(control)
        if not explicit_item_specs:
            return False
    if "product" in control:
        # The deal resolver performs the authoritative published-catalog check;
        # this gate only rejects malformed/boolean model tags before any DB side
        # effect. A stale/unpublished product then fails closed in the resolver.
        product_id = _control_product_id(control)
        if not product_id:
            return False
        if explicit_item_specs and any(
            int(item.get("product_id") or 0) != product_id
            for item in explicit_item_specs
        ):
            return False
    else:
        item_specs = explicit_item_specs or _control_item_specs(control)
        product_id = (
            item_specs[0]["product_id"]
            if item_specs
            else getattr(client, "current_product_id", None)
        )
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return False
    if not product_id:
        return False
    intent = str(getattr(client, "intent", "") or "").casefold()
    if "custom" in intent:
        return False
    low = " ".join(str(reply or "").split()).casefold()
    # `stage == paid` тут навмисно **не** блокує: стадія означає «є оплачене
    # замовлення в роботі», а не «ця людина більше нічого не купить». Дубль
    # рахунку відсікає `_has_open_paid_deal` вище — за фактом грошей, не за
    # робочим станом воронки.
    if _PURCHASE_COMMITMENT_RE.search(low):
        return True
    stage = str(getattr(client, "stage", "") or "").casefold()
    if intent in {"payment", "checkout"} and stage in {"checkout", "payment_pending"}:
        return True
    # A direct question such as "How can I pay?" is already a purchase signal
    # when the conversation has a fully resolved fit/size configuration.  Do
    # not require the classifier to advance the CRM stage before issuing the
    # first-party proposal, but still fail closed for a missing choice.
    if intent in {"payment", "checkout"} and stage == "product_matched":
        item_specs = explicit_item_specs or _control_item_specs(control)
        if item_specs:
            return all(
                str(item.get("size") or "").strip()
                and str(item.get("fit_option_code") or "").strip()
                for item in item_specs
            )
        selected_size = str(control.get("size") or getattr(client, "current_size", "") or "").strip()
        selected_fit = str(control.get("fit") or "").strip()
        return bool(selected_size and selected_fit)
    return False


# Монобанк-подібні URL — щоб прибрати вигадане моделлю платіжне посилання й
# лишити лише реальний invoice. Товарні/каталожні URL (twocomms.shop) не чіпаємо.
_PAY_URL_RE = re.compile(r"https?://[^\s]*(?:mbnk|monobank)[^\s]*", re.I)

# Безпечний холдер, коли лінк не вдалось сформувати: НЕ лишаємо клієнта з
# висячою обіцянкою «ось посилання», а м'яко тримаємо діалог поки підключиться
# менеджер (його одночасно сповіщаємо).
PAYLINK_FALLBACK_TEXT = "Дякую! Уточню деталі щодо оплати і за мить повернуся до вас 🙌"
_PAYLINK_FALLBACK_TEXT = {
    "uk": PAYLINK_FALLBACK_TEXT,
    "ru": "Спасибо! Уточню детали оплаты и через минуту вернусь к вам 🙌",
    "en": "Thank you! I will confirm the payment details and get right back to you 🙌",
}

# Єдиний порядок джерел потрібен саме в runtime: production зберігає власний
# `system_prompt`, тому зміна DEFAULT_BOT_SYSTEM_PROMPT не виправить уже живий
# конфлікт між старою стилістикою, каталогом і редагованими директивами.
CANONICAL_PROMPT_AUTHORITY_POLICY = (
    "[ЄДИНИЙ ПОРЯДОК ІСТИНИ — службове]\n"
    "Якщо джерела суперечать одне одному, застосовуй їх лише в такому порядку: "
    "(1) підтверджені системою факти про оплату, замовлення та сервісний кейс; "
    "(2) [СТАН ОФОРМЛЕННЯ] і факт обраної конфігурації з каталогу "
    "(variant_id, колір/матеріал, фасон, розмір, кількість, точна ціна); "
    "(3) поточна репліка клієнта та [СТАН ДІАЛОГУ]; "
    "(4) поточні оперативні директиви й доречні playbook-інструкції; "
    "(5) старий базовий промпт і стиль. Директива не може скасувати факт з пунктів 1-3.\n"
    "Явне прохання клієнта писати UA/RU/EN або однозначна мова поточної репліки "
    "має перевагу над застарілим формулюванням базового промпта чи старою мовою картки.\n"
    "Якщо ціна залежить від кольору, матеріалу, variant_id, фасону чи іншої опції, "
    "не називай одну точну суму, доки конфігурацію не визначено; не підмінюй її "
    "базовою ціною товару. Позначена в каталозі знижка — це лише факт вже "
    "порахованої ціни, а не дозвіл самостійно пропонувати rescue-знижку.\n"
    "Не вигадуй товар, залишок, ціну, доставку, оплату чи знижку. В одній відповіді "
    "має бути не більше одного запитання, одного чіткого CTA і одного доречного "
    "апселлу; без тиску."
)

# Протокол оплати — інжектимо в system_instruction завжди (migration-free), щоб
# модель давала ЯВНИЙ сигнал товару й типу оплати, а не лише обіцяла лінк текстом.
# Не чіпаємо DEFAULT_BOT_SYSTEM_PROMPT (щоб не робити міграцію й не затирати
# правки адміна в UI) — інжект застосовується до будь-яких налаштувань.
PAYMENT_PROTOCOL_NOTE = (
    "[ПРОТОКОЛ ПЕРСОНАЛЬНОЇ ПРОПОЗИЦІЇ — службове, клієнт цього не бачить]\n"
    "Це правило має пріоритет над старими фразами про пряме посилання на оплату. "
    "Коли клієнт підтвердив КОНКРЕТНИЙ товар і готовий платити — додай у самому "
    "кінці відповіді службові теги: [PAYLINK:prepay] для погодженої передоплати або "
    "[PAYLINK:full] (повна оплата), і поряд [PRODUCT:<id>], де <id> — число з "
    "рядка каталогу (формат «id=NN»). Система надішле персональну пропозицію TwoComms "
    "на власному сайті, а не прямий Monobank checkout. НЕ вигадуй і НЕ пиши URL "
    "власноруч. На сторінці клієнт перевіряє товари, вводить Нову Пошту та email для "
    "чека за бажанням, після чого сам переходить до оплати. Не збирай email, ПІБ, телефон, місто "
    "чи відділення в Direct для assisted checkout і не став [ORDER] у цьому сценарії. "
    "Посилання дійсне 25 хвилин від створення, його можна переслати; зміни товарів клієнт просить "
    "у Direct до створення рахунку. Якщо товар ще не визначено однозначно — спершу "
    "уточни його, тег [PAYLINK] поки не став. Для кожної позиції додай "
    "[ITEM:<product_id>|<qty>|<size>|<fit>|<color_variant_id>|<key=value;...>] "
    "(шосте поле можна залишити порожнім лише коли додаткових опцій немає), щоб "
    "зберегти кількість, розмір, крій, колір і всі осі конфігурації. Для однієї "
    "позиції додаткові осі також можна передати тегами [OPTION:<key>=<value>]. "
    "Якщо ціна залежить від кольору/матеріалу або фасону, спочатку уточни їх і "
    "назви точну ціну саме цієї конфігурації та ОБОВ'ЯЗКОВО додай [PRICE_QUOTED:<сума>] "
    "у тому ж ходу. Точна сума в тексті без маркера буде перевірена сервером і "
    "заблокована при несовпадении с каталогом. Для футболки з "
    "кількома фасонами спочатку обов'язково запитай classic чи oversize, покажи сітку "
    "саме обраного фасону і лише потім запитуй розмір. Для однієї позиції також дозволено "
    "[QTY:n] [SIZE:XS] [FIT:oversize]. "
    "ВАЖЛИВО: став [FIT:...], [SIZE:...], [QTY:...] і [PRODUCT:...] ОДРАЗУ того ходу, "
    "коли ти дізналась відповідь, навіть якщо до посилання ще далеко і решти даних "
    "бракує. Ці теги — те, як ти запам'ятовуєш вибір клієнта: без них наступного разу "
    "ти знову не знатимеш фасону й перепитаєш те саме. Якщо клієнт передумав і назвав "
    "інший товар — став [PRODUCT:<новий id>], і тоді розмір/колір потрібно уточнити "
    "заново, бо для нового товару вони можуть бути інші. "
    "Для передоплати обов'язково додай "
    "[PAYMENT:сума], але лише якщо ця точна сума явно погоджена в поточному діалозі. "
    "Не використовуй фіксовані 200 грн і не перенось суму з попереднього замовлення. "
    "Якщо менеджер явно погодив іншу ціну, додай [PRICE:число] лише коли це число "
    "дослівно є у збереженій переписці; не вигадуй знижку. Якщо клієнт просить "
    "показати товари/фото, додай [SHOW_PRODUCTS:<id1,id2>] з точними id каталогу; "
    "система надішле 3–4 реальні фото без товарних URL. Додавай [CATALOG_LINK] "
    "тільки коли клієнт прямо попросив посилання на товар.\n"
    "ПОРЯДОК ПОКАЗУ ФОТО. Фото — це відповідь на конкретний запит, а не спосіб "
    "почати розмову. Спершу з'ясуй текстом, що людині потрібно: тип речі "
    "(футболка/худі/лонгслів), тематика принта, колір, фасон. Показуй фото, коли "
    "звужено до 2–3 конкретних товарів або коли клієнт прямо попросив показати. "
    "Не надсилай фото у відповідь на загальне «порекомендуй» — спочатку задай "
    "одне уточнююче питання. До кожної відправки фото ОБОВ'ЯЗКОВО додай текст, "
    "який називає показані товари по порядку («1) …, 2) …») з ціною: клієнт має "
    "розуміти, що саме бачить, і мати змогу відповісти «беру першу». "
    "Якщо клієнт просить «звичайну», «класичну», «стандартну», «просту» футболку "
    "без принта — це базові моделі з логотипом на груді, а не товар із великим "
    "принтом; знайди в каталозі саме таку позицію (у назві є «класична»/«classic») "
    "і не підставляй принтований товар. Замість вгадування можна прямо "
    "запропонувати надіслати посилання на товар із сайту або скриншот — так "
    "швидше й точніше, ніж перебирати варіанти."
)

# Тексти, які лишились, супроводжують **реальне** посилання на оплату: вони
# несуть факти (термін дії 25 хвилин, оплата через Monobank, скрин не потрібен),
# а не ведуть діалог. Усі формулювання-питання («який фасон обираєте», «підкажіть
# розмір», «варіант недоступний») звідси прибрані свідомо: саме вони підміняли
# відповідь моделі й приходили клієнту дослівно однаковими, чужою мовою.
_ASSISTED_CHECKOUT_COPY = {
    "uk": {
        "proposal": (
            "Перевірте товари в персональній пропозиції TwoComms, додайте дані Нової "
            "Пошти та email для чека за бажанням. Після підтвердження даних безпечна оплата "
            "відкриється через Monobank; скрин оплати надсилати не потрібно. Це займає до двох "
            "хвилин. Посилання дійсне 25 хвилин від створення, його можна переслати іншій людині. "
            "Якщо треба щось змінити в товарах, напишіть мені сюди до оплати."
        ),
        "proposal_with_summary": (
            "Перевірте товари в персональній пропозиції TwoComms, додайте дані Нової "
            "Пошти та email для чека за бажанням. Це займає до двох хвилин. Посилання "
            "дійсне 25 хвилин від створення, його можна переслати іншій людині. Якщо треба "
            "щось змінити в товарах, напишіть мені сюди до оплати."
        ),
    },
    "ru": {
        "proposal": (
            "Проверьте товары в персональном предложении TwoComms, добавьте данные Новой "
            "почты и email для чека по желанию. После подтверждения данных безопасная оплата "
            "откроется через Monobank; скрин оплаты присылать не нужно. Это занимает до двух "
            "минут. Ссылка действует 25 минут с момента создания, ее можно переслать другому человеку. "
            "Если нужно что-то изменить в товарах, напишите мне сюда до оплаты."
        ),
        "proposal_with_summary": (
            "Проверьте товары в персональном предложении TwoComms, добавьте данные Новой "
            "почты и email для чека по желанию. Это занимает до двух минут. Ссылка действует "
            "25 минут с момента создания, ее можно переслать другому человеку. Если нужно "
            "что-то изменить в товарах, напишите мне сюда до оплаты."
        ),
    },
    "en": {
        "proposal": (
            "Review the items in your personal TwoComms offer, add Nova Poshta delivery "
            "details and an optional receipt email. After you confirm the details, secure payment "
            "opens through Monobank; you do not need to send a payment screenshot. It takes about two "
            "minutes. The link is valid for 25 minutes from creation and can be forwarded. Message me "
            "here before paying if you would like to change the items."
        ),
        "proposal_with_summary": (
            "Review the items in your personal TwoComms offer and add Nova Poshta delivery "
            "details and an optional receipt email. It takes about two minutes. The link is valid "
            "for 25 minutes from creation and can be forwarded. Message me here before paying if "
            "you would like to change the items."
        ),
    },
}


def _assisted_checkout_locale(client) -> str:
    language = str(getattr(client, "language", "") or "").lower()
    if language.startswith("ru"):
        return "ru"
    if language.startswith("en"):
        return "en"
    return "uk"


def _assisted_checkout_copy(client, key: str) -> str:
    locale = _assisted_checkout_locale(client)
    return _ASSISTED_CHECKOUT_COPY.get(locale, _ASSISTED_CHECKOUT_COPY["uk"]).get(
        key,
        _ASSISTED_CHECKOUT_COPY["uk"].get(key, ""),
    )


def _paylink_fallback(client=None) -> str:
    locale = _assisted_checkout_locale(client) if client is not None else "uk"
    return _PAYLINK_FALLBACK_TEXT.get(locale, PAYLINK_FALLBACK_TEXT)


def _checkout_offer_details(locale: str, summary: dict) -> str:
    if not isinstance(summary, dict) or not summary:
        return ""

    locale = locale if locale in {"uk", "ru", "en"} else "uk"
    item_parts = []
    raw_items = summary.get("items")
    if isinstance(raw_items, (list, tuple)):
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            title = str(raw_item.get("title") or "").strip()
            color_label = str(raw_item.get("color_label") or "").strip()
            fit_label = str(raw_item.get("fit_label") or "").strip()
            size = str(raw_item.get("size") or "").strip()
            try:
                quantity = int(raw_item.get("quantity"))
            except (TypeError, ValueError):
                quantity = 0
            facts = [title] if title else []
            if color_label:
                facts.append(color_label)
            if fit_label:
                facts.append(fit_label)
            option_labels = raw_item.get("option_labels")
            option_values = raw_item.get("option_values")
            if isinstance(option_values, dict):
                for key, value in option_values.items():
                    if key == "fit":
                        continue
                    label = (
                        str(option_labels.get(key) or "").strip()
                        if isinstance(option_labels, dict) else ""
                    )
                    facts.append(label or str(value))
            if size:
                facts.append({"uk": f"розмір {size}", "ru": f"размер {size}", "en": f"size {size}"}[locale])
            if quantity > 0:
                facts.append({"uk": f"{quantity} шт.", "ru": f"{quantity} шт.", "en": f"{quantity} pcs"}[locale])
            try:
                unit_price = Decimal(str(raw_item.get("unit_price"))).quantize(Decimal("0.01"))
                line_total = Decimal(str(raw_item.get("line_total"))).quantize(Decimal("0.01"))
            except (InvalidOperation, TypeError, ValueError):
                unit_price = line_total = None
            if unit_price is not None and line_total is not None:
                unit = format(unit_price, "f").rstrip("0").rstrip(".")
                line = format(line_total, "f").rstrip("0").rstrip(".")
                facts.append(
                    {"uk": f"{unit} грн/шт, сума {line} грн", "ru": f"{unit} грн/шт, сумма {line} грн", "en": f"{unit} UAH/pc, line {line} UAH"}[locale]
                )
            if facts:
                item_parts.append(", ".join(facts))

    total = ""
    catalog_total = ""
    discount = ""
    try:
        value = Decimal(str(summary.get("quoted_total")))
        if value.is_finite() and value >= 0:
            total = format(value, "f").rstrip("0").rstrip(".") or "0"
    except (InvalidOperation, TypeError, ValueError):
        pass
    try:
        value = Decimal(str(summary.get("catalog_total")))
        if value.is_finite() and value >= 0:
            catalog_total = format(value, "f").rstrip("0").rstrip(".") or "0"
    except (InvalidOperation, TypeError, ValueError):
        pass
    try:
        value = Decimal(str(summary.get("discount")))
        if value.is_finite() and value > 0:
            discount = format(value, "f").rstrip("0").rstrip(".") or "0"
    except (InvalidOperation, TypeError, ValueError):
        pass

    if not item_parts and not total:
        return ""

    labels = {
        "uk": ("Замовлення", "Разом", "грн", "Після перевірки безпечна оплата відкриється через Monobank; скрин підтвердження не потрібен - нічого надсилати не треба."),
        "ru": ("Заказ", "Итого", "грн", "После проверки безопасная оплата откроется через Monobank; скрин подтверждения не нужен - ничего присылать не надо."),
        "en": ("Order", "Total", "UAH", "After review, secure payment opens through Monobank. No payment screenshot is needed - there is nothing to send us."),
    }
    order_label, total_label, currency, guidance = labels[locale]
    lines = []
    if item_parts:
        lines.append(f"{order_label}: {'; '.join(item_parts)}.")
    if total:
        if catalog_total and discount:
            lines.append({
                "uk": f"Каталожна сума: {catalog_total} грн. Знижка: -{discount} грн.",
                "ru": f"Каталожная сумма: {catalog_total} грн. Скидка: -{discount} грн.",
                "en": f"Catalog subtotal: {catalog_total} UAH. Discount: -{discount} UAH.",
            }[locale])
        lines.append(f"{total_label}: {total} {currency}.")
    lines.append(guidance)
    return "\n".join(lines)

# Правило точності — інжектимо разом із протоколом оплати. Прямо забороняє
# «вигадану відмову» (типу «такого немає / це кастом»), як це сталось із реальним
# товаром «Харків Edition».
ANTI_HALLUCINATION_NOTE = (
    "[ПРАВИЛО ТОЧНОСТІ — службове]\n"
    "Ніколи не стверджуй, що товару немає або що це «кастом/під замовлення», не "
    "звіривши з каталогом нижче. Якщо точного збігу не видно — НЕ відмовляй і НЕ "
    "вигадуй: запропонуй переглянути каталог або чемно уточни деталі (тип, колір, "
    "принт, місто/напис на принті). Ціни, наявність і назви бери ЛИШЕ з каталогу."
)

SALES_AUTOMATION_GUARDRAILS = (
    "[SALES AUTOMATION GUARDRAILS — службове]\n"
    "Відповідай короткими Instagram-повідомленнями, мовою клієнта (UA/RU/EN). "
    "Якщо клієнт пише англійською, відповідай англійською навіть якщо старіша "
    "базова інструкція згадує лише UA/RU. "
    "Не вигадуй SKU, товар, наявність, ціну, оплату, знижку чи фінальну ціну "
    "кастомного принта. Знижку НЕ пропонуй сам: система окремо керує rescue "
    "оферами 5%, максимум 10% лише як фінальний/узгоджений варіант. Якщо клієнт "
    "каже «не буду купувати», «стоп», «не пишіть» — зроби максимум одне коротке "
    "ввічливе закриття без тиску і без повторних follow-up. Для custom print: "
    "коротко поясни, що можливий будь-який DTF-принт, ціна залежить від крою, "
    "розміру принта і готовності файлу, фінальний прорахунок робить менеджер; "
    "збери базове ТЗ і переведи в Telegram менеджера, не називаючи фінальну суму."
)

# F-CTX-002: the block above is injected unconditionally, so a customer in the
# middle of a size exchange is served by a prompt that explains how to hand out
# rescue discounts. The service variant keeps every safety rule (language,
# no invented facts, escalation) and drops only the selling part.
POST_SALE_SERVICE_GUARDRAILS_TEMPLATE = (
    "[POST-SALE SERVICE MODE — службове]\n"
    "Клієнт уже купив, і по його замовленню відкрито сервісне звернення: {case}. "
    "Зараз це не продаж. Не пропонуй знижок, не пропонуй інший товар, "
    "не підганяй до нової покупки і не згадуй акції. "
    "Твоє завдання — довести сервісне звернення до кінця: підтвердити потрібний "
    "розмір або причину, назвати наступний крок і, якщо потрібне рішення "
    "людини, передати менеджеру.\n"
    "Відповідай короткими Instagram-повідомленнями, мовою клієнта (UA/RU/EN). "
    "Не вигадуй SKU, товар, наявність, ціну, строки, номер ТТН чи умови обміну — "
    "якщо факту немає в наданому контексті, скажи, що уточниш у менеджера."
)

_POST_SALE_CASE_LABELS = {
    "exchange": "обмін товару",
    "return": "повернення товару",
}


def automation_guardrails(client) -> str:
    """Pick the guardrail block that matches what this conversation is about."""
    case = None
    if getattr(client, "pk", None):
        try:
            from management.services.ig_post_sale import open_service_case

            case = open_service_case(client)
        except Exception:
            case = None
    if case is None:
        return SALES_AUTOMATION_GUARDRAILS
    label = _POST_SALE_CASE_LABELS.get(str(case.case_type), "сервісне звернення")
    status = ""
    try:
        status = str(case.get_status_display() or "").strip()
    except Exception:
        status = ""
    described = f"{label} ({status})" if status else label
    return POST_SALE_SERVICE_GUARDRAILS_TEMPLATE.format(case=described)


def _strip_invented_pay_urls(text: str, keep_url: str = "") -> str:
    """Прибирає будь-які платіжні URL (monobank/mbnk), КРІМ keep_url (реального).

    Захищає від ситуації, коли модель сама «вигадала» посилання на оплату —
    клієнт має отримати лише наш справжній invoice, а не фантазійний лінк.
    """
    if not text:
        return text

    def _repl(m):
        u = m.group(0)
        return u if (keep_url and u == keep_url) else ""

    out = _PAY_URL_RE.sub(_repl, text)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


def _rewrite_failed_paylink(reply: str, client=None) -> str:
    """Прибирає висяче обіцяння лінку (фрази-обіцянки) + вигадані платіжні URL.

    Якщо після чистки корисного тексту майже не лишилось — повертає безпечний
    холдер (PAYLINK_FALLBACK_TEXT), щоб не надсилати клієнту порожню обіцянку.
    """
    text = _strip_invented_pay_urls(reply or "", keep_url="")
    # Двокрапка — теж межа. Модель зазвичай пише «Ось ваше посилання: <далі
    # корисне>», і розбиття лише по .!? викидало корисне разом з обіцянкою:
    # від відповіді не лишалось нічого, і клієнт отримував безликий холдер
    # замість питання, яке модель насправді задала.
    chunks = re.split(r"(?<=[.!?:])\s+|\n+", text)
    kept = []
    for ch in chunks:
        low = ch.lower()
        if _looks_like_paylink_request(low):
            continue
        if ch.strip():
            kept.append(ch.strip())
    cleaned = re.sub(r"[ \t]{2,}", " ", " ".join(kept)).strip()
    if len(cleaned) < 12:
        return _paylink_fallback(client)
    return cleaned


def _checkout_color_keys(text: str) -> set[str]:
    normalized = " ".join(str(text or "").casefold().split())
    keys = set()
    for key, pattern in _CHECKOUT_COLOR_PATTERNS.items():
        for match in pattern.finditer(normalized):
            prefix = normalized[max(0, match.start() - 48):match.start()]
            if _CHECKOUT_COLOR_NEGATION_PREFIX_RE.search(prefix):
                continue
            keys.add(key)
            break
    return keys


def _current_color_variant_id(client, product_id, quantity, *, trigger_text: str = ""):
    if not product_id:
        return None
    try:
        from productcolors.models import ProductColorVariant

        variants = list(
            ProductColorVariant.objects.filter(
                product_id=product_id,
            ).select_related("color").order_by("order", "id")
        )
        references = (str(trigger_text or "").strip(),)
        for reference in references:
            if not reference:
                continue
            normalized = " ".join(reference.casefold().split())
            reference_keys = _checkout_color_keys(reference)
            matches = []
            for variant in variants:
                color_name = str(getattr(getattr(variant, "color", None), "name", "") or "")
                slug = str(getattr(variant, "slug", "") or "")
                candidate_values = {
                    " ".join(color_name.casefold().split()),
                    " ".join(slug.casefold().split()),
                }
                if normalized in candidate_values or (
                    reference_keys
                    and reference_keys.intersection(_checkout_color_keys(f"{color_name} {slug}"))
                ):
                    matches.append(variant.pk)
            if len(matches) == 1:
                return matches[0]
        return None
    except Exception:
        return None


# Коди, які означають «діалог ще не завершений», а не «система зламалась».
# Раніше кожен із них перетворювався на готову фразу з таблиці копій і підміняв
# відповідь моделі. Тепер це лише класифікація: інцидент чи звичайний хід.
_CONFIGURATION_GAP_CODES = frozenset({
    "missing_configuration",
    "missing_size",
    "missing_fit_option",
    "invalid_size",
    "invalid_fit",
    "invalid_fit_option",
    "invalid_color",
    "invalid_color_variant",
    "missing_color_variant",
    "insufficient_stock",
    "unavailable_selection",
    "unpublished_product",
    "invalid_product",
})


def _is_configuration_gap(result) -> bool:
    """Чи це «ще не вистачає даних від клієнта», а не збій.

    Різниця важлива: у першому випадку менеджера кликати не треба і стадію
    збивати в `lead_manager` не треба — розмову продовжує бот. У другому
    (непідтверджена ціна, сума передоплати, битий тег) потрібна людина.
    """
    if not isinstance(result, dict):
        return False
    return str(result.get("error") or "") in _CONFIGURATION_GAP_CODES


def finalize_paylink(
    reply: str,
    control: dict,
    client,
    sender_id: str = "",
    *,
    trigger_text: str = "",
) -> str:
    """Узгоджує відповідь бота з результатом формування лінку на оплату.

    Гарантія: клієнт НІКОЛИ не отримає обіцянку «ось посилання» без самого лінку
    (це і був баг «скинув, але не скинув і чекає оплату»).

    - лінк не потрібен → reply без змін;
    - потрібен і сформований → реальний URL присутній у тексті, будь-який
      вигаданий моделлю платіжний URL прибраний;
    - потрібен, але НЕ сформований → прибирає висяче обіцяння, ставить безпечний
      холдер, кличе менеджера й піднімає стадію lead_manager.
    """
    if not reply or not client:
        return reply
    product_id = _control_product_id(control) or getattr(client, "current_product_id", None)
    selection = _checkout_selection_state(client, product_id)
    control_fit = str(control.get("fit") or "").strip().lower()[:50]
    if control_fit:
        # Фасон приходить тільки як явний вибір моделі ([FIT:...]).
        # Раніше сюди ж потрапляло будь-яке *згадування* слова «оверсайз» у
        # тексті клієнта, і питання «Покажи на оверсайз розмірну сітку» молча
        # переписувало платіжний вибір з classic на oversize. Це вже не UX-баг,
        # а гроші: клієнт отримав би рахунок на не той фасон.
        selection["fit_option_code"] = control_fit
    control_options = _control_option_values(control)
    if control.get("options") and control_options is None:
        log("warning", "paylink_option_gate", f"{sender_id}: malformed option controls")
        return _rewrite_failed_paylink(reply, client)
    if control_options:
        persisted_options = selection.get("option_values")
        persisted_options = dict(persisted_options) if isinstance(persisted_options, dict) else {}
        persisted_options.update(control_options)
        selection["option_values"] = persisted_options
    selected_color_variant_id = _current_color_variant_id(
        client,
        product_id,
        _control_positive_int(
            control,
            "qty",
            default=getattr(client, "current_qty", 1) or 1,
        ) or 1,
        trigger_text=trigger_text,
    )
    if selected_color_variant_id:
        selection["color_variant_id"] = selected_color_variant_id
    want, pt = _wants_paylink(reply, control, trigger_text=trigger_text)
    if not want:
        return reply
    from management.services.ig_alerts import alert_dedupe_key
    selection["pay_type"] = pt
    if control.get("_invalid"):
        log("warning", "paylink_control_gate", f"{sender_id}: conflicting control tags")
        return _rewrite_failed_paylink(reply, client)
    if "items" in control and not _control_item_specs(control):
        log("warning", "paylink_item_gate", f"{sender_id}: malformed explicit item tags")
        try:
            notify_manager(
                f"⚠️ IG: платіжне посилання для "
                f"{(client.username or client.display_name or sender_id)} заблоковано: "
                "не вдалося безпечно розібрати товар, кількість, розмір або крій.",
                dedupe_key=alert_dedupe_key(
                    "paylink_item_gate", client_id=getattr(client, "pk", None),
                    window_minutes=360,
                ),
                event_type="paylink_item_gate",
                client=client,
            )
        except Exception:
            pass
        return _paylink_fallback(client)
    if not payment_link_allowed(client, control, reply):
        log("warning", "paylink_gate", f"{sender_id}: blocked without purchase candidate")
        try:
            notify_manager(
                f"⚠️ IG: платіжне посилання для {(client.username or client.display_name or sender_id)} "
                "заблоковано: немає підтвердженого purchase candidate або товару.",
                dedupe_key=alert_dedupe_key(
                    "paylink_no_candidate", client_id=getattr(client, "pk", None),
                    window_minutes=360,
                ),
                event_type="paylink_no_candidate",
                client=client,
            )
        except Exception:
            pass
        return _rewrite_failed_paylink(reply, client)
    if selection:
        _persist_checkout_selection(client, product_id, selection)
    from management.services import bot_orders

    item_specs = _control_item_specs(control)
    if not item_specs:
        try:
            persisted_qty = int(getattr(client, "current_qty", 1) or 1)
        except (TypeError, ValueError):
            persisted_qty = 1
        parsed_qty = _control_positive_int(control, "qty", default=persisted_qty)
        if parsed_qty is None:
            log("warning", "paylink_qty_gate", f"{sender_id}: invalid explicit quantity")
            return _rewrite_failed_paylink(reply, client)
        fallback_spec = {
            "product_id": _control_product_id(control) or getattr(client, "current_product_id", None),
            "qty": parsed_qty,
            "size": str(control.get("size") or getattr(client, "current_size", "") or "").strip().upper()[:16],
            "fit_option_code": str(
                control.get("fit") or selection.get("fit_option_code") or ""
            ).strip().lower()[:50],
            "color_variant_id": (
                control.get("color_variant_id")
                or control.get("variant")
                or selection.get("color_variant_id")
                or _current_color_variant_id(
                    client,
                    _control_product_id(control) or getattr(client, "current_product_id", None),
                    parsed_qty,
                    trigger_text=trigger_text,
                )
            ),
        }
        if selection.get("option_values"):
            fallback_spec["option_values"] = dict(selection["option_values"])
        item_specs = [fallback_spec]

    aggregate_quantity = sum(
        int(item.get("qty") or item.get("quantity") or 1)
        for item in item_specs
    )
    from storefront.models import Product, ProductStatus

    price_product = None
    if len(item_specs) == 1:
        price_product = Product.objects.filter(
            pk=item_specs[0].get("product_id"),
            status=ProductStatus.PUBLISHED,
        ).first()
    price_decision = bot_orders._conversation_price_decision(
        client,
        product=price_product,
        qty=aggregate_quantity,
    )
    negotiated_price = (
        price_decision.get("price")
        if price_decision.get("status") == "accepted"
        else None
    )
    if "price" in control:
        try:
            requested_price = Decimal(str(control.get("price")).replace(",", ".")).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            requested_price = None
        if requested_price is None or requested_price != negotiated_price:
            negotiated_price = None
    if "price" in control and negotiated_price is None:
        log("warning", "paylink_price_gate", f"{sender_id}: blocked unverified negotiated price")
        try:
            notify_manager(
                f"⚠️ IG: платіжне посилання для {(client.username or client.display_name or sender_id)} "
                "заблоковано: модель вказала ціну, але її не підтверджено актуальною перепискою. "
                "Перевірте погоджену суму вручну.",
                dedupe_key=alert_dedupe_key(
                    "paylink_price_gate", client_id=getattr(client, "pk", None),
                    window_minutes=360,
                ),
                event_type="paylink_price_gate",
                client=client,
            )
        except Exception:
            pass
        try:
            client.set_stage(IgClient.Stage.LEAD_TO_MANAGER, reason="paylink_unverified_price")
        except Exception:
            pass
        return _rewrite_failed_paylink(reply, client)

    payment_amount = None
    if pt == "prepay":
        payment_amount = _conversation_payment_amount(client, control)
        if payment_amount is None:
            log("warning", "paylink_payment_amount_gate", f"{sender_id}: missing or unverified prepayment amount")
            try:
                notify_manager(
                    f"⚠️ IG: платіжне посилання для {(client.username or client.display_name or sender_id)} "
                    "заблоковано: сума передоплати не погоджена доказово в поточному діалозі.",
                    dedupe_key=alert_dedupe_key(
                        "paylink_prepay_gate",
                        client_id=getattr(client, "pk", None),
                        window_minutes=360,
                    ),
                    event_type="paylink_prepay_gate",
                    client=client,
                )
            except Exception:
                pass
            try:
                client.set_stage(IgClient.Stage.LEAD_TO_MANAGER, reason="paylink_unverified_payment_amount")
            except Exception:
                pass
            return _rewrite_failed_paylink(reply, client)

    negotiated_total = None
    if negotiated_price is not None:
        if price_decision.get("kind") == "order_total":
            negotiated_total = negotiated_price
        elif price_decision.get("kind") == "unit_price" and len(item_specs) == 1:
            negotiated_total = negotiated_price * aggregate_quantity
        else:
            log("warning", "paylink_multi_price_gate", f"{sender_id}: price allocation required")
            return _rewrite_failed_paylink(reply, client)

    try:
        kwargs = {
            "pay_type": pt,
            "item_specs": item_specs,
            "negotiated_total": negotiated_total,
            "requested_payment_amount": payment_amount,
        }
        evidence_ids = []
        if negotiated_price is not None:
            evidence_ids.extend(
                value for value in (
                    price_decision.get("source_message_id"),
                    price_decision.get("acceptance_message_id"),
                ) if value
            )
        if payment_amount is not None:
            payment_decision = bot_orders._conversation_payment_amount_decision(client)
            evidence_ids.extend(payment_decision.get("evidence_message_ids") or [])
        evidence_ids = list(dict.fromkeys(int(value) for value in evidence_ids if value))
        if evidence_ids:
            kwargs["evidence"] = {"message_ids": evidence_ids}
        res = bot_orders.create_checkout_proposal_link(client, **kwargs)
    except Exception as exc:
        log("error", "paylink", repr(exc))
        res = {"ok": False, "error": repr(exc)}

    if res.get("ok") and res.get("invoice_url"):
        if res.get("proposal_pk"):
            control["_funnel_proposal_pk"] = int(res["proposal_pk"])
        if res.get("proposal_id"):
            control["_funnel_proposal_id"] = str(res["proposal_id"])
        url = res["invoice_url"]
        lead = _rewrite_failed_paylink(reply, client)
        if lead == _paylink_fallback(client):
            lead = ""
        locale = _assisted_checkout_locale(client)
        order_details = _checkout_offer_details(locale, res.get("order_summary") or {})
        proposal_key = "proposal_with_summary" if order_details else "proposal"
        proposal_copy = _assisted_checkout_copy(client, proposal_key)
        proposal_marker = proposal_copy.split(",", 1)[0].casefold()
        if proposal_marker and proposal_marker in lead.casefold():
            proposal_copy = ""
        reply = "\n\n".join(
            part for part in (lead, order_details, proposal_copy, url) if part
        ).strip()
        log("success", "paylink", f"{sender_id}: {url}")
        return reply

    if _is_configuration_gap(res):
        # Не інцидент, а звичайний хід діалогу: ще не вистачає фасону, розміру
        # або кольору. Раніше тут повертався готовий текст із таблиці копій, і
        # саме він приходив клієнту дослівно однаковим (прод, 02.08: три рази
        # підряд одна й та сама російська фраза українцеві). Тепер відповідь
        # лишається за моделлю — вона вже бачила брак у блоці [СТАН ОФОРМЛЕННЯ]
        # ще до генерації, тому питає своїми словами й мовою клієнта.
        log(
            "info",
            "paylink_awaiting_configuration",
            f"{sender_id}: {res.get('error')} missing={sorted(res.get('missing_fields') or [])}",
        )
        return _rewrite_failed_paylink(reply, client)

    # Невдача формування: прибираємо висяче обіцяння й ескалюємо на менеджера.
    log("error", "paylink", f"{sender_id}: НЕ сформовано ({res.get('error')})")
    safe = _rewrite_failed_paylink(reply, client)
    try:
        client.set_stage(IgClient.Stage.LEAD_TO_MANAGER, reason="paylink_failed")
    except Exception:
        pass
    try:
        notify_manager(
            f"⚠️ IG: бот обіцяв клієнту "
            f"{(client.username or client.display_name or sender_id)} посилання на "
            f"оплату, але НЕ зміг сформувати (причина: {res.get('error')}). "
            f"Підключись вручну."
        )
    except Exception:
        pass
    return safe


def _attachment_items(msg: dict) -> list[dict] | None:
    """Normalize legacy attachment lists and Instagram Login data envelopes."""
    if not isinstance(msg, dict):
        return []
    raw = msg.get("attachments")
    if raw is None:
        return []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("data")
        if not isinstance(items, list):
            return None
        paging = raw.get("paging")
        if paging is not None and not isinstance(paging, dict):
            return None
    else:
        return None
    if len(items) > 50 or any(not isinstance(item, dict) for item in items):
        return None
    return items


def _attachment_media_candidates(attachment: dict) -> list[tuple[str, str, str]]:
    """Return bounded (type, url, title) candidates without trusting unknown fields."""
    result: list[tuple[str, str, str]] = []
    legacy_payload = attachment.get("payload")
    if isinstance(legacy_payload, dict):
        url = str(legacy_payload.get("url") or "").strip()
        if url.startswith(("https://", "http://")):
            result.append((
                str(attachment.get("type") or "image")[:32],
                url,
                str(legacy_payload.get("title") or "")[:700],
            ))
    for key, value in attachment.items():
        if key in {"payload", "type"} or not isinstance(value, dict):
            continue
        url = str(value.get("url") or value.get("file_url") or value.get("preview_url") or "").strip()
        if not url.startswith(("https://", "http://")):
            continue
        media_type = key[:-5] if key.endswith("_data") else key
        result.append((media_type[:32] or "image", url, str(value.get("title") or "")[:700]))
    direct_url = str(attachment.get("file_url") or attachment.get("url") or "").strip()
    if direct_url.startswith(("https://", "http://")):
        result.append((str(attachment.get("type") or "file")[:32], direct_url, ""))
    return result[:8]


def _echo_media_items(msg: dict) -> list[dict]:
    """Keep bounded manager media metadata for the durable echo message."""
    result = []
    for attachment in _attachment_items(msg) or []:
        for media_type, url, title in _attachment_media_candidates(attachment):
            result.append({
                "url": url[:1200],
                "type": media_type,
                "title": title,
                "role": "manager_reference",
            })
    return result[:8]


def _handle_echo(
    recipient_igsid: str,
    text: str,
    *,
    attachments: list[dict] | None = None,
    mid: str = "",
    received_at=None,
    persistence_only: bool = False,
) -> None:
    """Echo-подія (повідомлення, надіслане сторінкою). Якщо це НЕ власне відлуння
    бота — значить відповів живий менеджер → ставимо бота на паузу для клієнта."""
    recipient_igsid = str(recipient_igsid or "").strip()
    mid = str(mid or "").strip()
    if not _SENDER_ID_RE.fullmatch(recipient_igsid):
        return
    if mid and not _valid_message_id(mid):
        return
    # Позитивна ознака «це наше» перевіряється ПЕРШОЮ і до будь-якої зміни
    # стану клієнта. Раніше єдиною перевіркою був відпечаток по тексту, а в
    # медіа-echo тексту немає — тому карусель бота вмикала `manager_takeover`,
    # ставила клієнта на паузу і бот замовкав (прод, 02.08.2026, клієнт #5).
    from management.services.ig_outgoing_registry import is_our_outgoing

    if mid and is_our_outgoing(mid):
        return  # власне відлуння бота — ігноруємо
    if text and cache.get(_bot_sent_key(recipient_igsid, text)):
        return  # сумісність зі старим текстовим відпечатком
    if not text and attachments and client_automation_busy(
        IgClient.objects.filter(igsid=recipient_igsid).first()
    ):
        # Медіа-echo без тексту, поки активна ліза автоматики саме на цьому
        # клієнті, — майже напевно наша ж карусель, чий `message_id` не встиг
        # зареєструватись. Свідомо не тихо: випадок має бути видимий у логу,
        # інакше ми знову втратимо реальний takeover непоміченим.
        log(
            "warning",
            "echo_media_during_automation",
            f"{recipient_igsid}: медіа-echo під час активної відповіді бота — "
            "вважаю власним, takeover не вмикаю",
        )
        return
    from management.services.ig_reply_boundary import pause_reply_boundary

    now = timezone.now()
    # The takeover notification is a state transition, not a per-message
    # event. Lock the client row so two webhook workers cannot both announce
    # the same transition while manager messages are still stored separately.
    with pause_reply_boundary():
        with transaction.atomic():
            client, _ = IgClient.objects.select_for_update().get_or_create(
                igsid=recipient_igsid,
                defaults={"first_contact_at": now, "last_message_at": now},
            )
            if mid and InstagramBotMessage.objects.filter(mid=mid).exists():
                return
            takeover_started = not client.manager_takeover
            client.manager_takeover = True
            client.bot_paused = True
            client.reply_permission_epoch = int(client.reply_permission_epoch or 0) + 1
            client.paused_reason = "manager_takeover"
            if takeover_started:
                client.paused_at = now
            client.last_manager_message_at = now
            update_fields = [
                "manager_takeover", "bot_paused", "paused_reason",
                "reply_permission_epoch",
                "last_manager_message_at", "updated_at",
            ]
            if takeover_started:
                update_fields.append("paused_at")
            client.save(update_fields=update_fields)
            InstagramBotMessage.objects.filter(
                client=client,
                role=InstagramBotMessage.Role.USER,
                status__in=[
                    InstagramBotMessage.Status.PENDING,
                    InstagramBotMessage.Status.PROCESSING,
                ],
            ).exclude(send_state="sending").update(
                status=InstagramBotMessage.Status.DONE,
                processed_at=now,
                processing_started_at=None,
            )
            msg = None
            if text or attachments:
                try:
                    with transaction.atomic():
                        msg = InstagramBotMessage.objects.create(
                            sender_id=recipient_igsid,
                            client=client,
                            role=InstagramBotMessage.Role.MANAGER,
                            text=text or "(зображення менеджера)",
                            mid=mid or None,
                            status=InstagramBotMessage.Status.DONE,
                            source="echo",
                            attachments=json.dumps(
                                [item.get("url") for item in (attachments or []) if item.get("url")],
                                ensure_ascii=False,
                            ) if attachments else "",
                            provider_created_at=received_at,
                            processed_at=timezone.now(),
                        )
                except IntegrityError:
                    msg = InstagramBotMessage.objects.filter(mid=mid).first() if mid else None
                except Exception:
                    if persistence_only:
                        raise
                    msg = None
            if takeover_started:
                from management.models import IgFunnelStepEvent
                from management.services.ig_funnel_analytics import (
                    record_client_step_event_in_transaction,
                )

                record_client_step_event_in_transaction(
                    client,
                    event_type=IgFunnelStepEvent.Type.MANAGER_ENGAGED,
                    event_key=f"ig-manager-engaged:{client.pk}:{int(client.paused_at.timestamp()) if client.paused_at else int(now.timestamp())}",
                    occurred_at=now,
                    stage=client.stage,
                    actor="manager",
                    evidence={
                        "manager_message_id": msg.pk if msg else None,
                        "provider_mid": mid,
                        "takeover_started": True,
                    },
                )
            try:
                from management.services import bot_followups, bot_sales_classifier
                from management.services.bot_conversation_analysis import schedule_analysis

                bot_followups.cancel_pending(client, reason="manager_takeover")
                if msg:
                    schedule_analysis(client, msg, trigger="manager_message")
                    if not persistence_only:
                        bot_sales_classifier.classify_message(
                            client,
                            message=msg,
                            role=InstagramBotMessage.Role.MANAGER,
                            media_context=_recover_current_message_media(msg),
                        )
            except Exception:
                if persistence_only:
                    raise
            if takeover_started:
                notification_persisted = notify_manager(
                    f"👤 IG: менеджер підключився до {client.username or client.igsid} — "
                    f"бот на паузі для цього клієнта.",
                    dedupe_key=(
                        f"takeover:{client.pk}:"
                        f"{client.paused_at.isoformat() if client.paused_at else 'unknown'}"
                    ),
                    event_type="takeover",
                    client=client,
                    deliver_immediately=not persistence_only,
                )
                if persistence_only and not notification_persisted:
                    raise RuntimeError("manager takeover notification was not persisted")
    if takeover_started:
        log("warning", "takeover", f"{recipient_igsid}: менеджер підключився")
    else:
        log("info", "manager_message", f"{recipient_igsid}: повідомлення менеджера збережено")


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
_LOG_LEVELS = {
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "success": logging.INFO,
    "info": logging.INFO,
}
_INCIDENT_LOGGER = logging.getLogger("ig_bot")


def log(level: str, event: str, detail: str = "") -> None:
    """Write the compact UI log and a durable, PII-redacted incident trail.

    Routine successful messages intentionally omit detail in the file because
    the console may contain a customer-facing reply excerpt.  Warnings/errors
    preserve the diagnostic detail and pass through the global PII filter.
    """
    level = str(level or "info").lower()
    event = str(event or "unknown")[:120]
    detail = str(detail or "")[:4000]
    try:
        suffix = f" detail={detail}" if level in {"warning", "error"} and detail else ""
        _INCIDENT_LOGGER.log(
            _LOG_LEVELS.get(level, logging.INFO),
            "ig_bot event=%s level=%s%s",
            event,
            level,
            suffix,
        )
    except Exception:
        # Observability must never block message intake or payment recovery.
        pass
    try:
        InstagramBotLog.objects.create(level=level, event=event, detail=detail)
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


def resolve_instagram_login_token() -> str:
    """Return the Instagram User token for the approved Instagram Login flow.

    The token intentionally has its own cPanel name so it can never be used as
    the webhook HMAC key.
    """
    return os.environ.get("IG_INSTAGRAM_BOT", "").strip()


def provider_transport(_s: InstagramBotSettings) -> str:
    """Select one complete provider contract; deployed legacy tokens fail closed."""
    explicit = os.environ.get("IG_PROVIDER_TRANSPORT", "").strip().lower()
    if explicit == LEGACY_PAGE_TRANSPORT:
        return LEGACY_PAGE_TRANSPORT
    if explicit == INSTAGRAM_LOGIN_TRANSPORT:
        return INSTAGRAM_LOGIN_TRANSPORT
    if resolve_instagram_login_token():
        return INSTAGRAM_LOGIN_TRANSPORT
    # The deployed cPanel environment still contains old credentials during
    # cutover. Their presence must never revive the legacy contract if the new
    # token is accidentally removed or renamed. Legacy remains available only
    # via an explicit mode; credential-free local/test fixtures keep their
    # historical behavior.
    if os.environ.get("IG_MARKER", "").strip() or os.environ.get("DIRECT_API", "").strip():
        return INSTAGRAM_LOGIN_TRANSPORT
    return LEGACY_PAGE_TRANSPORT


def provider_token_configured(s: InstagramBotSettings) -> bool:
    if provider_transport(s) == INSTAGRAM_LOGIN_TRANSPORT:
        return bool(resolve_instagram_login_token())
    return bool(resolve_direct_token(s))


def _provider_account_id(s: InstagramBotSettings) -> str:
    if provider_transport(s) == INSTAGRAM_LOGIN_TRANSPORT:
        return str(getattr(s, "ig_user_id", "") or "").strip()
    return str(getattr(s, "page_id", "") or "").strip()


def resolve_gemini_key(s: InstagramBotSettings) -> str:
    if s.gemini_source == InstagramBotSettings.CredSource.CUSTOM:
        return (s.custom_gemini_key or "").strip()
    return os.environ.get("GEMINI_API", "").strip()


def instagram_login_app_secret() -> str:
    """Return the Instagram Login app secret used by Instagram webhooks."""
    return os.environ.get("IG_APP_SECRET", "").strip()


def parent_meta_app_secret() -> str:
    """Return only the parent Meta app secret used by OAuth/compliance."""
    return (
        os.environ.get("META_APP_SECRET", "").strip()
        or os.environ.get("FACEBOOK_APP_SECRET", "").strip()
    )


def app_secret() -> str:
    """Return the webhook HMAC secret without access-token inference."""
    explicit_transport = os.environ.get("IG_PROVIDER_TRANSPORT", "").strip().lower()
    if explicit_transport == LEGACY_PAGE_TRANSPORT:
        return parent_meta_app_secret()
    return instagram_login_app_secret()


def facebook_app_secret() -> str:
    """Compatibility wrapper for parent Meta signed requests/legacy OAuth."""
    return parent_meta_app_secret()


def webhook_secrets() -> tuple[str, ...]:
    """Усі наші HMAC-секрети, якими Meta може підписати webhook.

    Токени доступу тут навмисно не використовуються — тільки app secret.

    Чому секретів декілька. У Meta підпис `X-Hub-Signature-256` робиться app
    secret **того додатку, який доставляє подію**, а в нас їх два: Instagram
    Login app (`IG_APP_SECRET`) і батьківський Meta app (`META_APP_SECRET`).
    Обидва прописані в оточенні прода, але перевірявся лише перший.

    Наслідок був виміряний по access-логу 02.08.2026: на `/bot/webhook/`
    **496 відповідей 403 проти 44 успішних**, усі відхилені — від
    `facebookexternalua` з IPv6-підмереж Meta. Тобто 92% входящих подій
    відкидалось на порозі, і бот бачив діалоги лише через резервний polling,
    із затримкою. Це і є справжня причина «бот майже не відповідає»:
    27 відповідей моделі на 1025 повідомлень клієнтів за тиждень.

    Перебір кількох секретів не послаблює перевірку: кожен із них — наш, а
    `compare_digest` лишається строгим. Підробити підпис без секрету
    неможливо так само, як і раніше.
    """
    candidates = (
        instagram_login_app_secret(),
        parent_meta_app_secret(),
        app_secret(),
    )
    ordered: list[str] = []
    for secret in candidates:
        if secret and secret not in ordered:
            ordered.append(secret)
    return tuple(ordered)


def allow_unsigned_webhooks() -> bool:
    """Return the explicit development-only bypass for signature checks."""
    raw = os.environ.get("IG_BOT_ALLOW_UNSIGNED_WEBHOOKS")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    try:
        from django.conf import settings

        return bool(getattr(settings, "IG_BOT_ALLOW_UNSIGNED_WEBHOOKS", False))
    except Exception:
        return False


def webhook_signature_status() -> dict[str, object]:
    configured = bool(webhook_secrets())
    override = allow_unsigned_webhooks()
    return {
        "configured": configured,
        "unsigned_override": override,
        "healthy": configured or override,
        "state": "configured" if configured else ("development_override" if override else "missing_secret"),
    }


def _webhook_status_key(bucket: int, kind: str) -> str:
    return f"ig_bot_webhook_status:{kind}:{bucket}"


def webhook_rejection_status() -> dict[str, object] | None:
    """Return the current bounded 4xx incident signal, without a Graph call."""
    value = cache.get("ig_bot_webhook_4xx_degraded")
    if not isinstance(value, dict):
        return None
    try:
        errors = max(0, int(value.get("errors") or 0))
        total = max(errors, int(value.get("total") or 0))
    except (TypeError, ValueError):
        return None
    if not errors or not total:
        return None
    return {
        "errors": errors,
        "total": total,
        "rate": round(errors / total, 4),
        "reason": str(value.get("reason") or "")[:64],
    }


def record_webhook_response(status_code: int, *, reason: str = "") -> dict[str, object]:
    """Count webhook HTTP outcomes and queue one alert for a sustained 4xx rate.

    The handler must stay fast and must never transmit Telegram synchronously.
    Counters are deliberately cache-only: durable evidence is in ``ig_bot.log``
    and the alert outbox, while this is a short-lived detection window.
    """
    was_degraded = webhook_rejection_status() is not None
    try:
        status_code = int(status_code)
    except (TypeError, ValueError):
        status_code = 0
    now = timezone.now()
    bucket = int(now.timestamp() // WEBHOOK_ERROR_WINDOW_SECONDS)
    ttl = WEBHOOK_ERROR_WINDOW_SECONDS * 2
    total_key = _webhook_status_key(bucket, "total")
    error_key = _webhook_status_key(bucket, "4xx")
    try:
        cache.add(total_key, 0, ttl)
        total = int(cache.incr(total_key))
        is_client_error = 400 <= status_code < 500
        if is_client_error:
            cache.add(error_key, 0, ttl)
            errors = int(cache.incr(error_key))
        else:
            errors = int(cache.get(error_key) or 0)
    except Exception:
        return {"available": False, "status_code": status_code}

    rate = errors / total if total else 0.0
    degraded = errors >= WEBHOOK_ERROR_MIN_COUNT and rate >= WEBHOOK_ERROR_MIN_RATE
    if degraded:
        cache.set(
            "ig_bot_webhook_4xx_degraded",
            {
                "errors": errors,
                "total": total,
                "reason": str(reason or "http_4xx")[:64],
                "at": now.timestamp(),
            },
            INGRESS_DEGRADATION_TTL,
        )
        if not was_degraded:
            try:
                from management.services.ig_alerts import alert_dedupe_key, format_alert

                notify_manager(
                    format_alert(
                        "🚨 IG webhook: високий рівень 4xx",
                        lines=(
                            f"За {WEBHOOK_ERROR_WINDOW_SECONDS // 60} хв: {errors}/{total} "
                            f"({rate:.0%})",
                            f"Причина: {str(reason or 'http_4xx')[:64]}",
                        ),
                    ),
                    dedupe_key=alert_dedupe_key(
                        "ig_webhook_4xx_rate",
                        window_minutes=15,
                        text=f"{bucket}:{reason}",
                    ),
                    event_type="ig_webhook_4xx_rate",
                    deliver_immediately=False,
                )
            except Exception:
                pass
    elif errors < WEBHOOK_ERROR_MIN_COUNT or rate < WEBHOOK_ERROR_MIN_RATE:
        # Recover only after this bucket actually falls below the incident
        # threshold. One successful delivery must not hide an ongoing 4xx wave.
        cache.delete("ig_bot_webhook_4xx_degraded")
    return {
        "available": True,
        "status_code": status_code,
        "errors": errors,
        "total": total,
        "rate": rate,
        "degraded": degraded,
    }


# ---------------------------------------------------------------------------
# Webhook signature (X-Hub-Signature-256)
# ---------------------------------------------------------------------------
def verify_signature(raw_body: bytes, header: str) -> bool:
    """Verify Meta's X-Hub-Signature-256 header.

    Missing credentials fail closed. The unsigned bypass is intentionally
    explicit and exists only for local development/test environments.
    """
    secrets_ = webhook_secrets()
    if not secrets_:
        return allow_unsigned_webhooks()
    if not header or not header.startswith("sha256="):
        return False
    supplied = header.split("=", 1)[1].strip()
    labels = ("ig_app", "meta_app", "resolved_app")
    for index, secret in enumerate(secrets_):
        if hmac.compare_digest(
            hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest(),
            supplied,
        ):
            # Яким саме секретом підписана подія — операційно важливо: рік тому
            # відмова ingress була невидимою, і її знайшли випадково, по логах
            # веб-сервера. Пишемо мітку (не сам секрет) не частіше разу на годину.
            if index > 0:
                key = f"ig_bot_webhook_secret_seen:{index}"
                if not cache.get(key):
                    cache.set(key, 1, 3600)
                    log(
                        "info",
                        "webhook_signature_source",
                        f"підпис підтверджено секретом {labels[index] if index < len(labels) else index}",
                    )
            return True
    return False


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
GRAPH_SENSITIVE_QUERY_KEYS = frozenset({
    "access_token", "client_secret", "app_secret", "api_key", "password",
})
META_ENDPOINT_CLASSES = ("conversations", "send", "read", "oauth")
META_OBSERVABILITY_TTL = 86400
META_DEGRADED_TTL = 120


def _meta_endpoint_class(url: str) -> str:
    try:
        path = urlsplit(url).path
    except (TypeError, ValueError):
        return "read"
    path = path.removeprefix(f"/{GRAPH_VERSION}/")
    if "/conversations" in path:
        return "conversations"
    if path.endswith("/messages"):
        return "send"
    if path.startswith("oauth/"):
        return "oauth"
    return "read"


def _increment_meta_counter(key: str) -> None:
    try:
        if cache.add(key, 1, META_OBSERVABILITY_TTL):
            return
        cache.incr(key)
        return
    except Exception:
        pass
    try:
        cache.set(key, int(cache.get(key) or 0) + 1, META_OBSERVABILITY_TTL)
    except Exception:
        pass


def _record_meta_http_observation(endpoint: str, code: int, body: str = "") -> None:
    """Record bounded endpoint/rate facts without persisting provider payloads."""
    endpoint = endpoint if endpoint in META_ENDPOINT_CLASSES else "read"
    _increment_meta_counter(f"ig_meta_http_total:{endpoint}")
    if code == -1:
        _increment_meta_counter(f"ig_meta_http_transport:{endpoint}")
    try:
        graph_code, _graph_subcode = _graph_error_codes(body)
    except Exception:
        graph_code = 0
    rate_limited = code == 429 or graph_code in RATE_LIMIT_CODES
    if not rate_limited:
        return
    _increment_meta_counter(f"ig_meta_http_rate:{endpoint}")
    try:
        cache.set(
            "ig_meta_http_last_rate",
            {"endpoint": endpoint, "at": timezone.now().isoformat()},
            META_OBSERVABILITY_TTL,
        )
        cache.set("ig_meta_http_degraded_until", time.time() + META_DEGRADED_TTL, META_DEGRADED_TTL)
    except Exception:
        pass


def meta_rate_limit_status() -> dict[str, object]:
    try:
        until = float(cache.get("ig_meta_http_degraded_until") or 0)
    except (TypeError, ValueError):
        until = 0
    endpoints = {}
    for endpoint in META_ENDPOINT_CLASSES:
        try:
            total = int(cache.get(f"ig_meta_http_total:{endpoint}") or 0)
            rate = int(cache.get(f"ig_meta_http_rate:{endpoint}") or 0)
            transport = int(cache.get(f"ig_meta_http_transport:{endpoint}") or 0)
        except (TypeError, ValueError):
            total = rate = transport = 0
        endpoints[endpoint] = {
            "requests": total,
            "rate_limited": rate,
            "transport_errors": transport,
        }
    last = cache.get("ig_meta_http_last_rate")
    if not isinstance(last, dict):
        last = {}
    return {
        "degraded": until > time.time(),
        "degraded_until": datetime.fromtimestamp(until, tz=dt_timezone.utc).isoformat() if until else "",
        "last_rate_limited_at": str(last.get("at") or ""),
        "last_rate_limited_endpoint": str(last.get("endpoint") or ""),
        "endpoints": endpoints,
    }


def _send_rate_limit_backoff_key(s: InstagramBotSettings) -> str:
    return f"ig_bot_send_rate_backoff:{_provider_owner_id(s)}"


def _activate_send_rate_limit_backoff(s: InstagramBotSettings) -> None:
    try:
        cache.set(_send_rate_limit_backoff_key(s), 1, META_DEGRADED_TTL)
    except Exception:
        pass


def _send_rate_limit_backoff_active(s: InstagramBotSettings) -> bool:
    try:
        return bool(cache.get(_send_rate_limit_backoff_key(s)))
    except Exception:
        return False


def _gemini_backoff_key(s: InstagramBotSettings) -> str:
    return f"ig_bot_gemini_backoff:{_provider_owner_id(s)}"


def _gemini_backoff_active(s: InstagramBotSettings) -> bool:
    try:
        if (
            s.gemini_source == InstagramBotSettings.CredSource.CUSTOM
            and str(s.custom_gemini_key or "").strip()
        ):
            return False
        return bool(cache.get(_gemini_backoff_key(s)))
    except Exception:
        return False


def _defer_for_gemini_cooldown(
    row: InstagramBotMessage,
    s: InstagramBotSettings,
) -> bool:
    """Return the current claim to pending while every pooled chat key cools down."""
    try:
        if (
            s.gemini_source == InstagramBotSettings.CredSource.CUSTOM
            and str(s.custom_gemini_key or "").strip()
        ):
            return False

        from management.services import gemini_keys

        now = timezone.now()
        if gemini_keys.has_available_key("chat", now=now):
            return False
        soonest = gemini_keys.soonest_cooldown("chat", now=now)
        if not soonest:
            return False
        ttl = max(1, min(24 * 60 * 60, int((soonest - now).total_seconds())))
        cache.set(_gemini_backoff_key(s), 1, ttl)
        attempts = max(0, int(row.attempts or 0) - 1)
        updated = _own_processing_claim(row).update(
            status=InstagramBotMessage.Status.PENDING,
            attempts=attempts,
            processing_started_at=None,
        )
        if not updated:
            return False
        row.status = InstagramBotMessage.Status.PENDING
        row.attempts = attempts
        row.processing_started_at = None
        log(
            "warning",
            "gemini_backoff",
            f"{row.sender_id}: усі chat-ключі в cooldown на {ttl}с",
        )
        return True
    except Exception as exc:
        log("warning", "gemini_backoff", repr(exc))
        return False


def _valid_provider_request_url(url: str, host: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if (
        parsed.scheme != "https"
        or parsed.netloc != host
        or not parsed.path.startswith(f"/{GRAPH_VERSION}/")
        or parsed.fragment
    ):
        return False
    query_keys = {key.lower() for key, _value in parse_qsl(parsed.query, keep_blank_values=True)}
    return not query_keys.intersection(GRAPH_SENSITIVE_QUERY_KEYS)


def _valid_graph_request_url(url: str) -> bool:
    return _valid_provider_request_url(url, "graph.facebook.com")


def _valid_instagram_graph_request_url(url: str) -> bool:
    return _valid_provider_request_url(url, "graph.instagram.com")


def _valid_instagram_refresh_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except (TypeError, ValueError):
        return False
    if (
        parsed.scheme != "https"
        or parsed.netloc != "graph.instagram.com"
        or parsed.path != "/refresh_access_token"
        or parsed.fragment
    ):
        return False
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if len(pairs) != 2 or {key for key, _value in pairs} != {
        "grant_type",
        "access_token",
    }:
        return False
    values = dict(pairs)
    return bool(
        values.get("grant_type") == "ig_refresh_token"
        and values.get("access_token")
    )


def _strip_graph_query_credentials(url: str, token: str = "") -> tuple[str, str]:
    """Remove provider paging credentials before URL policy validation.

    Meta may put the current access token in ``paging.next`` URLs. The request
    already carries the token in the Authorization header, so retaining that
    query parameter both leaks a credential and causes our URL policy to reject
    an otherwise valid page.
    """
    parsed = urlsplit(url)
    query = []
    extracted_token = token or ""
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in GRAPH_SENSITIVE_QUERY_KEYS:
            if key.lower() != "access_token":
                raise ValueError("unexpected Graph credential query parameter")
            if not extracted_token:
                extracted_token = value
            continue
        query.append((key, value))
    clean_url = urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), "")
    )
    return clean_url, extracted_token


def _provider_graph_url(host: str, path: str, params: dict | None = None) -> str:
    """Build one versioned provider URL with credentials outside the query."""
    parsed = urlsplit(str(path or ""))
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        raise ValueError("Graph path must be relative")
    if parsed.fragment or _GRAPH_VERSION_PATH_RE.match(parsed.path):
        raise ValueError("invalid Graph path")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if params:
        query.update({str(key): str(value) for key, value in params.items()})
    if {key.lower() for key in query}.intersection(GRAPH_SENSITIVE_QUERY_KEYS):
        raise ValueError("Graph credentials cannot be placed in query")
    url = urlunsplit(("https", host, f"/{GRAPH_VERSION}{parsed.path}", urlencode(query), ""))
    if not _valid_provider_request_url(url, host):
        raise ValueError("invalid versioned Graph URL")
    return url


def _graph_url(path: str, params: dict | None = None) -> str:
    """Build a legacy Facebook Graph URL."""
    return _provider_graph_url("graph.facebook.com", path, params)


def _instagram_graph_url(path: str, params: dict | None = None) -> str:
    """Build an Instagram Login Graph URL."""
    return _provider_graph_url("graph.instagram.com", path, params)


def _provider_url(
    s: InstagramBotSettings,
    path: str,
    params: dict | None = None,
) -> str:
    if provider_transport(s) == INSTAGRAM_LOGIN_TRANSPORT:
        return _instagram_graph_url(path, params)
    return _graph_url(path, params)


def _provider_graph_http(
    url: str,
    *,
    host: str,
    token: str = "",
    data: bytes | None = None,
    timeout: int = HTTP_TIMEOUT,
    headers: dict | None = None,
):
    """Call one Graph host after enforcing version and removing credentials."""
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != host
            or not parsed.path.startswith(f"/{GRAPH_VERSION}/")
            or parsed.fragment
        ):
            return -1, "graph_url_policy"
        clean_url, token = _strip_graph_query_credentials(url, token)
    except (TypeError, ValueError):
        return -1, "graph_url_policy"
    if not _valid_provider_request_url(clean_url, host):
        return -1, "graph_url_policy"
    request_headers = dict(headers or {})
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    endpoint = _meta_endpoint_class(clean_url)
    code, body = _http(clean_url, data=data, timeout=timeout, headers=request_headers)
    _record_meta_http_observation(endpoint, code, body)
    return code, body


def _graph_http(
    url: str,
    *,
    token: str = "",
    data: bytes | None = None,
    timeout: int = HTTP_TIMEOUT,
    headers: dict | None = None,
):
    return _provider_graph_http(
        url,
        host="graph.facebook.com",
        token=token,
        data=data,
        timeout=timeout,
        headers=headers,
    )


def _instagram_graph_http(
    url: str,
    *,
    token: str = "",
    data: bytes | None = None,
    timeout: int = HTTP_TIMEOUT,
    headers: dict | None = None,
):
    return _provider_graph_http(
        url,
        host="graph.instagram.com",
        token=token,
        data=data,
        timeout=timeout,
        headers=headers,
    )


def _provider_http(
    s: InstagramBotSettings,
    url: str,
    *,
    token: str = "",
    data: bytes | None = None,
    timeout: int = HTTP_TIMEOUT,
    headers: dict | None = None,
):
    if provider_transport(s) == INSTAGRAM_LOGIN_TRANSPORT:
        return _instagram_graph_http(
            url,
            token=token,
            data=data,
            timeout=timeout,
            headers=headers,
        )
    return _graph_http(
        url,
        token=token,
        data=data,
        timeout=timeout,
        headers=headers,
    )


def _http(
    url: str,
    *,
    data: bytes | None = None,
    timeout: int = HTTP_TIMEOUT,
    headers: dict | None = None,
):
    host = urlsplit(url).netloc
    if host == "graph.facebook.com" and not _valid_graph_request_url(url):
        return -1, "graph_url_policy"
    if host == "graph.instagram.com" and not (
        _valid_instagram_graph_request_url(url)
        or _valid_instagram_refresh_url(url)
    ):
        return -1, "graph_url_policy"
    request_headers = dict(headers or {})
    if data is not None:
        request_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:
        return -1, repr(exc)


APP_ID = os.environ.get("IG_APP_ID", "2120980214971807")


def _credential_fingerprint(*values: str) -> str:
    """Return a non-reversible cache namespace for credential inputs."""
    material = "\x00".join(str(value or "") for value in values)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def _long_lived_token_cache_key(raw_token: str) -> str:
    return "ig_bot_ll_user_token:" + _credential_fingerprint(
        APP_ID,
        raw_token,
        facebook_app_secret(),
    )


def _instagram_login_token_cache_key(raw_token: str) -> str:
    return "ig_bot_instagram_user_token:" + _credential_fingerprint(raw_token)


def _refresh_instagram_login_token(token: str) -> str:
    """Refresh a long-lived Instagram User token without logging credentials."""
    if not token:
        return ""
    url = urlunsplit((
        "https",
        "graph.instagram.com",
        "/refresh_access_token",
        urlencode({
            "grant_type": "ig_refresh_token",
            "access_token": token,
        }),
        "",
    ))
    if not _valid_instagram_refresh_url(url):
        return ""
    code, body = _http(url, timeout=HTTP_TIMEOUT)
    if code != 200:
        return ""
    try:
        refreshed = json.loads(body).get("access_token") or ""
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    return refreshed if isinstance(refreshed, str) else ""


def _effective_instagram_login_token() -> str:
    raw = resolve_instagram_login_token()
    if not raw:
        return ""
    cache_key = _instagram_login_token_cache_key(raw)
    now = time.time()
    state = cache.get(cache_key)
    if not isinstance(state, dict):
        state = {}
    token = state.get("token") if isinstance(state.get("token"), str) else raw
    try:
        refreshed_at = float(state.get("refreshed_at") or 0)
        attempted_at = float(state.get("attempted_at") or 0)
    except (TypeError, ValueError):
        refreshed_at = 0
        attempted_at = 0
    refresh_due = not refreshed_at or now - refreshed_at >= INSTAGRAM_TOKEN_REFRESH_INTERVAL
    retry_due = not attempted_at or now - attempted_at >= INSTAGRAM_TOKEN_REFRESH_RETRY
    if not refresh_due or not retry_due:
        return token
    lock_key = f"{cache_key}:refresh_lock"
    try:
        acquired = bool(cache.add(lock_key, 1, INSTAGRAM_TOKEN_REFRESH_RETRY))
    except Exception:
        acquired = False
    if not acquired:
        return token
    try:
        refreshed = _refresh_instagram_login_token(token)
        state = {
            "token": refreshed or token,
            "refreshed_at": now if refreshed else refreshed_at,
            "attempted_at": now,
        }
        cache.set(cache_key, state, INSTAGRAM_TOKEN_CACHE_TTL)
        return state["token"]
    finally:
        cache.delete(lock_key)


def _page_token_cache_keys(s: InstagramBotSettings, token: str) -> tuple[str, str]:
    namespace = _credential_fingerprint(
        APP_ID,
        s.page_id,
        token,
        facebook_app_secret(),
    )
    prefix = f"ig_bot_page_token:{namespace}"
    return prefix, f"{prefix}:cooldown"


def _exchange_long_lived(user_token: str) -> str:
    """short-lived -> long-lived (60 дн). Потрібен app_secret. Page-токен,
    похідний від long-lived user-токена, не має терміну дії."""
    secret = facebook_app_secret()
    if not secret or not user_token:
        return ""
    body = urlencode({
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": secret,
        "fb_exchange_token": user_token,
    }).encode("utf-8")
    code, response_body = _graph_http(
        _graph_url("/oauth/access_token"),
        data=body,
        timeout=HTTP_TIMEOUT,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if code == 200:
        try:
            return json.loads(response_body).get("access_token", "") or ""
        except Exception:
            return ""
    return ""


def _effective_user_token(s: InstagramBotSettings) -> str:
    raw = resolve_direct_token(s)
    if not raw or not facebook_app_secret():
        return raw  # без секрету не можемо подовжити — використовуємо як є
    cache_key = _long_lived_token_cache_key(raw)
    cached = cache.get(cache_key)
    if cached:
        return cached
    ll = _exchange_long_lived(raw)
    if ll:
        cache.set(cache_key, ll, 50 * 24 * 3600)  # ~50 днів
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
        log("error", "page_token", f"HTTP {code}: {_redact_secret_text(body)[:160]}")
    try:
        s.last_error = (
            f"Direct токен недійсний (HTTP {code}). Онови DIRECT_API в ENV "
            f"(або свій токен у налаштуваннях)."
        )
        s.save(update_fields=["last_error"])
    except Exception:
        pass


NOTIFICATION_STALE_SENDING_SECONDS = 300
NOTIFICATION_MAX_ATTEMPTS = 5
NOTIFICATION_TERMINAL_ALERT_WINDOW_MINUTES = 60
NOTIFICATION_TERMINAL_MONITOR_CACHE_KEY = "ig_notification_terminal_monitor_due"
NOTIFICATION_TERMINAL_MONITOR_INTERVAL_SECONDS = 60


def _telegram_media_url_candidates(media: dict) -> list[str]:
    """Build absolute, deduplicated media URLs with original-source fallback."""
    from django.conf import settings

    base = (getattr(settings, "SITE_BASE_URL", "") or "https://twocomms.shop").rstrip("/") + "/"
    result = []
    for raw in (media.get("local_url"), media.get("url")):
        value = str(raw or "").strip()
        if not value:
            continue
        if value.startswith("/"):
            value = urljoin(base, value.lstrip("/"))
        if value.startswith(("https://", "http://")) and value not in result:
            result.append(value)
    return result


def _notification_retry_at(row, now, *, minimum_delay_seconds=0):
    base = min(3600, 30 * (2 ** max(0, int(row.attempts or 1) - 1)))
    jitter = int(hashlib.sha256(row.dedupe_key.encode("utf-8")).hexdigest()[:2], 16) % 16
    try:
        provider_delay = max(0, min(int(minimum_delay_seconds or 0), 86400))
    except (TypeError, ValueError):
        provider_delay = 0
    return now + timedelta(seconds=max(base, provider_delay) + jitter)


def _finish_notification(
    dedupe_key,
    *,
    status,
    error="",
    failure_kind="",
    message_id="",
    retry_after_seconds=0,
):
    now = timezone.now()
    with transaction.atomic():
        row = IgBotNotification.objects.select_for_update().get(dedupe_key=dedupe_key)
        if row.status != IgBotNotification.Status.SENDING:
            return False
        delivery_succeeded = status == IgBotNotification.Status.SENT
        review_status = (row.payload or {}).get("review_status") if isinstance(row.payload, dict) else ""
        row.status = (
            IgBotNotification.Status.RESOLVED
            if delivery_succeeded and review_status in {"confirmed", "cancelled"}
            else status
        )
        row.telegram_message_id = message_id
        row.last_error = (error or "")[:500]
        row.failure_kind = (failure_kind or "")[:32]
        row.sent_at = now if delivery_succeeded else None
        row.next_attempt_at = (
            _notification_retry_at(row, now, minimum_delay_seconds=retry_after_seconds)
            if status == IgBotNotification.Status.FAILED
            else None
        )
        if status == IgBotNotification.Status.FAILED and row.attempts >= NOTIFICATION_MAX_ATTEMPTS:
            row.status = IgBotNotification.Status.DEAD_LETTER
            row.failure_kind = "retry_exhausted"
            row.next_attempt_at = None
        row.save(update_fields=[
            "status", "telegram_message_id", "last_error", "failure_kind",
            "sent_at", "next_attempt_at", "updated_at",
        ])
        return delivery_succeeded


def _deliver_manager_notification(dedupe_key: str) -> bool:
    from management.services.ig_maintenance import notification_send_boundary

    with notification_send_boundary() as send_allowed:
        if not send_allowed:
            return False
        return _deliver_manager_notification_unlocked(dedupe_key)


def _deliver_manager_notification_unlocked(dedupe_key: str) -> bool:
    now = timezone.now()
    row = IgBotNotification.objects.filter(dedupe_key=dedupe_key).first()
    if not row:
        return False
    if row.status == IgBotNotification.Status.SENT:
        return True
    if row.status in {
        IgBotNotification.Status.UNKNOWN,
        IgBotNotification.Status.DEAD_LETTER,
        IgBotNotification.Status.RESOLVED,
    }:
        return False
    if row.status == IgBotNotification.Status.SENDING:
        stale_before = now - timedelta(seconds=NOTIFICATION_STALE_SENDING_SECONDS)
        IgBotNotification.objects.filter(
            pk=row.pk,
            status=IgBotNotification.Status.SENDING,
            last_attempt_at__lte=stale_before,
        ).update(
            status=IgBotNotification.Status.UNKNOWN,
            failure_kind="ambiguous_stale_sending",
            last_error="delivery outcome unknown after interrupted send",
            next_attempt_at=None,
            updated_at=now,
        )
        return False
    eligible = Q(status=IgBotNotification.Status.PENDING) | Q(
        status=IgBotNotification.Status.FAILED,
        next_attempt_at__isnull=True,
    ) | Q(
        status=IgBotNotification.Status.FAILED,
        next_attempt_at__lte=now,
    )
    claimed = IgBotNotification.objects.filter(pk=row.pk).filter(eligible).update(
        status=IgBotNotification.Status.SENDING,
        attempts=F("attempts") + 1,
        last_attempt_at=now,
        next_attempt_at=None,
        last_error="",
        failure_kind="",
        updated_at=now,
    )
    if claimed != 1:
        return False
    row.refresh_from_db()
    payload = dict(row.payload or {})

    token = os.environ.get("MANAGEMENT_TG_BOT_TOKEN", "").strip()
    chat = os.environ.get("MANAGEMENT_TG_ADMIN_CHAT_ID", "").strip() or str(payload.get("chat_id") or "")
    text = str(payload.get("text") or "")[:3500]
    if not token or not chat:
        _finish_notification(
            dedupe_key,
            status=IgBotNotification.Status.FAILED,
            error="telegram_not_configured",
            failure_kind="configuration",
        )
        return False
    reply_markup = payload.get("reply_markup")
    if not isinstance(reply_markup, dict):
        reply_markup = None

    def persist_payload():
        IgBotNotification.objects.filter(
            dedupe_key=dedupe_key,
            status=IgBotNotification.Status.SENDING,
        ).update(payload=payload, updated_at=timezone.now())

    def parse_response(code, response_body):
        try:
            parsed = json.loads(response_body or "{}")
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None

    main_message_id = str(payload.get("main_delivery_message_id") or "")
    if not main_message_id:
        try:
            body = json.dumps({
                "chat_id": chat,
                "text": text,
                "disable_web_page_preview": True,
                **({"reply_markup": reply_markup} if reply_markup is not None else {}),
            }).encode("utf-8")
            code, response_body = _http(
                f"https://api.telegram.org/bot{token}/sendMessage", data=body, timeout=HTTP_TIMEOUT
            )
        except Exception as exc:
            _finish_notification(
                dedupe_key,
                status=IgBotNotification.Status.UNKNOWN,
                error=repr(exc),
                failure_kind="ambiguous_transport",
            )
            return False
        response = parse_response(code, response_body)
        if code < 0 or (code == 200 and response is None):
            _finish_notification(
                dedupe_key,
                status=IgBotNotification.Status.UNKNOWN,
                error=response_body or "Telegram returned an unreadable success response",
                failure_kind="ambiguous_provider_response" if code == 200 else "ambiguous_transport",
            )
            return False
        response = response or {}
        if code != 200 or not response.get("ok"):
            retryable = code == 429 or code >= 500
            parameters = response.get("parameters")
            retry_after = parameters.get("retry_after") if code == 429 and isinstance(parameters, dict) else 0
            _finish_notification(
                dedupe_key,
                status=(IgBotNotification.Status.FAILED if retryable else IgBotNotification.Status.DEAD_LETTER),
                error=str(response.get("description") or f"HTTP {code}"),
                failure_kind=("rate_limited" if code == 429 else ("provider_retryable" if retryable else "provider_permanent")),
                retry_after_seconds=retry_after,
            )
            return False
        main_message_id = str((response.get("result") or {}).get("message_id") or "")
        if not main_message_id:
            _finish_notification(
                dedupe_key,
                status=IgBotNotification.Status.UNKNOWN,
                error="Telegram success response has no message_id",
                failure_kind="ambiguous_provider_response",
            )
            return False
        payload["main_delivery_message_id"] = main_message_id
        persist_payload()

    media_rows = payload.get("media") if isinstance(payload.get("media"), list) else []
    for media in media_rows[:8]:
        if not isinstance(media, dict) or media.get("delivery_status") == "sent":
            continue
        media_urls = _telegram_media_url_candidates(media)
        if not media_urls:
            media["delivery_status"] = "skipped_invalid_url"
            media["delivery_error"] = "invalid_media_url"
            persist_payload()
            _finish_notification(
                dedupe_key,
                status=IgBotNotification.Status.DEAD_LETTER,
                error="invalid_media_url",
                failure_kind="media_permanent",
                message_id=main_message_id,
            )
            return False
        role = str(media.get("role") or "other")
        caption_parts = [{
            "product": "Зображення товару",
            "receipt": "Чек з переписки",
            "payment_candidate": "Ймовірний чек — потрібна звірка",
            "custom_reference": "Референс custom print",
            "manager_reference": "Зображення менеджера",
            "other": "Невизначене зображення",
        }.get(role, "Зображення")]
        if media.get("message_id"):
            caption_parts.append(f"Повідомлення #{media['message_id']}")
        if media.get("product_title"):
            caption_parts.append(str(media["product_title"]))
        if media.get("product_url"):
            caption_parts.append(str(media["product_url"]))
        media_code, media_response_body, media_response = 0, "", {}
        delivered = False
        for media_url in media_urls:
            try:
                media_body = json.dumps({
                    "chat_id": chat,
                    "photo": media_url,
                    "caption": "\n".join(caption_parts)[:1000],
                    "reply_to_message_id": int(main_message_id),
                }).encode("utf-8")
                media_code, media_response_body = _http(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    data=media_body,
                    timeout=HTTP_TIMEOUT,
                )
            except Exception as exc:
                media["delivery_status"] = "unknown"
                media["delivery_error"] = repr(exc)[:300]
                persist_payload()
                _finish_notification(
                    dedupe_key,
                    status=IgBotNotification.Status.UNKNOWN,
                    error=repr(exc),
                    failure_kind="media_ambiguous_transport",
                    message_id=main_message_id,
                )
                return False
            media_response = parse_response(media_code, media_response_body)
            if media_code == 200 and isinstance(media_response, dict) and media_response.get("ok"):
                delivered = True
                break
            # A permanent URL-specific rejection may be recovered by the
            # original signed source URL. Retryable/ambiguous outcomes stop.
            if media_code == 429 or media_code >= 500 or media_code < 0:
                break
        if media_code < 0 or (media_code == 200 and media_response is None):
            media["delivery_status"] = "unknown"
            media["delivery_error"] = str(media_response_body or "unreadable response")[:300]
            persist_payload()
            _finish_notification(
                dedupe_key,
                status=IgBotNotification.Status.UNKNOWN,
                error=media["delivery_error"],
                failure_kind="media_ambiguous_provider",
                message_id=main_message_id,
            )
            return False
        media_response = media_response or {}
        if not delivered:
            retryable = media_code == 429 or media_code >= 500
            parameters = media_response.get("parameters")
            retry_after = parameters.get("retry_after") if media_code == 429 and isinstance(parameters, dict) else 0
            media["delivery_status"] = "failed" if retryable else "dead_letter"
            media["delivery_error"] = str(media_response.get("description") or f"HTTP {media_code}")[:300]
            persist_payload()
            _finish_notification(
                dedupe_key,
                status=(IgBotNotification.Status.FAILED if retryable else IgBotNotification.Status.DEAD_LETTER),
                error=media["delivery_error"],
                failure_kind="media_retryable" if retryable else "media_permanent",
                message_id=main_message_id,
                retry_after_seconds=retry_after,
            )
            return False
        media_message_id = str((media_response.get("result") or {}).get("message_id") or "")
        if not media_message_id:
            media["delivery_status"] = "unknown"
            media["delivery_error"] = "Telegram photo success response has no message_id"
            persist_payload()
            _finish_notification(
                dedupe_key,
                status=IgBotNotification.Status.UNKNOWN,
                error=media["delivery_error"],
                failure_kind="media_ambiguous_provider",
                message_id=main_message_id,
            )
            return False
        media["delivery_status"] = "sent"
        media["delivery_message_id"] = media_message_id
        media.pop("delivery_error", None)
        persist_payload()

    payload.pop("media_delivery_errors", None)
    persist_payload()
    return _finish_notification(
        dedupe_key,
        status=IgBotNotification.Status.SENT,
        message_id=main_message_id,
    )


def drain_manager_notifications(*, limit: int = 20) -> int:
    now = timezone.now()
    stale_before = now - timedelta(seconds=NOTIFICATION_STALE_SENDING_SECONDS)
    stale_ids = list(
        IgBotNotification.objects.filter(
            status=IgBotNotification.Status.SENDING,
            last_attempt_at__lte=stale_before,
        ).values_list("dedupe_key", flat=True)[:limit]
    )
    for dedupe_key in stale_ids:
        _deliver_manager_notification(dedupe_key)
    due_ids = list(
        IgBotNotification.objects.filter(
            status__in=[IgBotNotification.Status.PENDING, IgBotNotification.Status.FAILED]
        ).filter(
            Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)
        ).order_by("next_attempt_at", "id").values_list("dedupe_key", flat=True)[:limit]
    )
    sent = 0
    from management.services.ig_alerts import throttle_gate

    for dedupe_key in due_ids:
        # Глобальний ліміт на потік, а не на подію. Без нього цей цикл
        # відправляв усе, що встиг набрати, а сам він крутиться в демоні кожні
        # 1.5 секунди — звідси й «спам із 10 штук». Черга не втрачається:
        # незадоволені лишаються в `pending` і поїдуть наступного вікна.
        allowed, retry_after = throttle_gate()
        if not allowed:
            log(
                "info",
                "notification_throttled",
                f"ліміт потоку алертів; лишилось у черзі {len(due_ids) - sent}, "
                f"наступна спроба через {retry_after}с",
            )
            break
        sent += int(_deliver_manager_notification(dedupe_key))
    # Queue terminal-state monitoring after this pass.  A row that becomes
    # UNKNOWN/DEAD_LETTER during the current send is thus visible to the next
    # bounded pass, without recursively sending an alert inside its own drain.
    _monitor_terminal_notifications()
    return sent


def _monitor_terminal_notifications(*, limit: int = 100, force: bool = False) -> int:
    """Queue one bounded operator summary for unresolved terminal deliveries.

    UNKNOWN and DEAD_LETTER rows are deliberately not replayed: the provider
    outcome may already be visible to Telegram/Meta, or the retry budget is
    exhausted.  They still need a durable, periodic signal so an operator can
    reconcile them instead of relying on a dashboard counter.
    """
    if not force:
        try:
            if not cache.add(
                NOTIFICATION_TERMINAL_MONITOR_CACHE_KEY,
                1,
                timeout=NOTIFICATION_TERMINAL_MONITOR_INTERVAL_SECONDS,
            ):
                return 0
        except Exception as exc:
            # A broken cache must not make terminal notifications invisible.
            logger.warning("Unable to rate-limit terminal notification monitor: %r", exc)

    terminal_statuses = [
        IgBotNotification.Status.UNKNOWN,
        IgBotNotification.Status.DEAD_LETTER,
    ]
    counts = {status: 0 for status in terminal_statuses}
    for item in (
        IgBotNotification.objects.filter(status__in=terminal_statuses)
        .exclude(event_type="notification_terminal_monitor")
        .values("status")
        .annotate(total=Count("id"))
    ):
        counts[item["status"]] = item["total"]
    rows = list(
        IgBotNotification.objects.filter(status__in=terminal_statuses)
        .exclude(event_type="notification_terminal_monitor")
        .order_by("updated_at", "id")
        .values("id", "status", "event_type", "last_error")[:limit]
    )
    if not rows:
        return 0
    now = timezone.now()
    bucket = int(now.timestamp() // (NOTIFICATION_TERMINAL_ALERT_WINDOW_MINUTES * 60))
    samples = []
    for row in rows:
        if len(samples) < 6:
            samples.append(
                f"#{row['id']} {row['event_type']}: "
                f"{_redact_secret_text(row['last_error'] or 'без опису')[:120]}"
            )
    lines = [
        f"UNKNOWN: {counts[IgBotNotification.Status.UNKNOWN]}",
        f"DEAD_LETTER: {counts[IgBotNotification.Status.DEAD_LETTER]}",
        "Потрібна ручна звірка в журналі Telegram-алертів.",
        *samples,
    ]
    try:
        from management.services.ig_alerts import format_alert, management_base_url

        queued = notify_manager(
            format_alert(
                "⚠️ IG: є незавершені Telegram-алерти",
                lines=lines,
                url=f"{management_base_url()}/bot/",
                url_label="Перевірка:",
            ),
            dedupe_key=f"ig-notification-terminal:w{bucket}",
            event_type="notification_terminal_monitor",
            metadata={"terminal_counts": counts, "sample_count": len(samples)},
            deliver_immediately=False,
        )
    except Exception:
        logger.exception("Unable to queue terminal notification monitor")
        return 0
    return int(queued)


def notify_manager(
    text: str,
    *,
    dedupe_key: str | None = None,
    event_type: str = "generic",
    client: IgClient | None = None,
    reply_markup: dict | None = None,
    media: list[dict] | None = None,
    metadata: dict | None = None,
    deliver_immediately: bool = True,
) -> bool:
    """Persist one idempotent notification and optionally deliver it now."""
    text = (text or "").strip()[:3500]
    if not text:
        return False
    if not dedupe_key:
        dedupe_key = "generic:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    chat = os.environ.get("MANAGEMENT_TG_ADMIN_CHAT_ID", "").strip()
    payload = {"text": text, "chat_id": chat}
    if isinstance(metadata, dict):
        payload.update({
            str(key)[:64]: value
            for key, value in metadata.items()
            if isinstance(key, str)
        })
    if isinstance(reply_markup, dict):
        payload["reply_markup"] = reply_markup
    if isinstance(media, list):
        payload["media"] = [
            {
                key: str(item.get(key) or "")[:1200]
                for key in (
                    "role", "url", "local_url", "message_id", "product_id",
                    "product_title", "product_url", "confidence",
                )
                if item.get(key)
            }
            for item in media[:8]
            if isinstance(item, dict) and (item.get("url") or item.get("local_url"))
        ]
    try:
        with transaction.atomic():
            row, created = IgBotNotification.objects.select_for_update().get_or_create(
                dedupe_key=dedupe_key,
                defaults={
                    "client": client,
                    "event_type": (event_type or "generic")[:64],
                    "payload": payload,
                },
            )
            if not created and row.status in {
                IgBotNotification.Status.PENDING,
                IgBotNotification.Status.FAILED,
            }:
                previous_payload = row.payload if isinstance(row.payload, dict) else {}
                if previous_payload.get("main_delivery_message_id"):
                    payload["main_delivery_message_id"] = previous_payload["main_delivery_message_id"]
                    previous_media = previous_payload.get("media") if isinstance(previous_payload.get("media"), list) else []
                    delivery_by_key = {
                        (
                            str(item.get("role") or ""),
                            str(item.get("local_url") or item.get("url") or ""),
                            str(item.get("message_id") or ""),
                        ): item
                        for item in previous_media if isinstance(item, dict)
                    }
                    for item in payload.get("media") or []:
                        old = delivery_by_key.get((
                            str(item.get("role") or ""),
                            str(item.get("local_url") or item.get("url") or ""),
                            str(item.get("message_id") or ""),
                        ))
                        if old:
                            for key in ("delivery_status", "delivery_message_id", "delivery_error"):
                                if old.get(key):
                                    item[key] = old[key]
                row.client = client or row.client
                row.event_type = (event_type or row.event_type or "generic")[:64]
                row.payload = payload
                row.save(update_fields=["client", "event_type", "payload", "updated_at"])
            elif not created and row.status in {
                IgBotNotification.Status.SENT,
                IgBotNotification.Status.RESOLVED,
            }:
                previous_payload = row.payload if isinstance(row.payload, dict) else {}
                previous_media = previous_payload.get("media") if isinstance(previous_payload.get("media"), list) else []
                media_by_key = {
                    (
                        str(item.get("role") or ""),
                        str(item.get("local_url") or item.get("url") or ""),
                        str(item.get("message_id") or ""),
                    ): dict(item)
                    for item in previous_media if isinstance(item, dict)
                }
                added = False
                for item in payload.get("media") or []:
                    key = (
                        str(item.get("role") or ""),
                        str(item.get("local_url") or item.get("url") or ""),
                        str(item.get("message_id") or ""),
                    )
                    if key not in media_by_key:
                        media_by_key[key] = item
                        added = True
                if added:
                    row.payload = {
                        **previous_payload,
                        "media": list(media_by_key.values())[:8],
                        "main_delivery_message_id": (
                            previous_payload.get("main_delivery_message_id")
                            or row.telegram_message_id
                        ),
                    }
                    row.status = IgBotNotification.Status.PENDING
                    row.next_attempt_at = timezone.now()
                    row.save(update_fields=["payload", "status", "next_attempt_at", "updated_at"])
    except Exception:
        return False
    return _deliver_manager_notification(dedupe_key) if deliver_immediately else True


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
    if provider_transport(s) == INSTAGRAM_LOGIN_TRANSPORT:
        # Instagram Login already yields the provider token.  Never pass it
        # through the legacy Facebook /me/accounts Page-token exchange.
        if not _provider_account_id(s):
            return ""
        return _effective_instagram_login_token()
    token = _effective_user_token(s)
    if not token:
        return ""
    ck, cooldown_key = _page_token_cache_keys(s, token)
    if not force:
        cached = cache.get(ck)
        if cached:
            return cached
        if cache.get(cooldown_key):
            return ""
    code, body = _graph_http(
        _graph_url("/me/accounts", {"fields": "name,access_token"}),
        token=token,
        timeout=HTTP_TIMEOUT,
    )
    if code != 200:
        cache.set(cooldown_key, 1, 60)
        _log_token_error(s, code, body)
        return ""
    try:
        for page in json.loads(body).get("data", []):
            if str(page.get("id")) == s.page_id:
                pt = page.get("access_token") or ""
                if pt:
                    # Якщо токен подовжений (є секрет) — page-токен постійний,
                    # кешуємо надовго; інакше — коротко.
                    ttl = 50 * 24 * 3600 if facebook_app_secret() else PAGE_TOKEN_TTL
                    cache.set(ck, pt, ttl)
                    cache.delete(cooldown_key)
                    cache.delete("ig_bot_pt_errsig")
                return pt
    except Exception as exc:
        log("error", "page_token_parse", repr(exc))
    return ""


def ensure_instagram_subscription(s: InstagramBotSettings) -> dict[str, object]:
    """Install the Instagram Login app on the configured professional account."""
    if provider_transport(s) != INSTAGRAM_LOGIN_TRANSPORT:
        return {"ok": False, "http": 0, "state": "legacy_transport"}
    account_id = _provider_account_id(s)
    if not account_id:
        return {"ok": False, "http": 0, "state": "missing_credentials"}
    token = get_page_token(s)
    if not token:
        return {"ok": False, "http": 0, "state": "missing_credentials"}
    body = urlencode({"subscribed_fields": "messages"}).encode("utf-8")
    code, response_body = _provider_http(
        s,
        _provider_url(s, f"/{account_id}/subscribed_apps"),
        token=token,
        data=body,
        timeout=HTTP_TIMEOUT,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if code == 200:
        try:
            if json.loads(response_body).get("success") is True:
                return {"ok": True, "http": 200}
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return {
        "ok": False,
        "http": int(code),
        "state": _classify_poll_provider_failure(code, response_body),
    }


def _provider_owner_id(s: InstagramBotSettings) -> str:
    """Durable, token-free owner identity for caches and discovery cursors."""
    account_id = _provider_account_id(s) or "unknown"
    if provider_transport(s) == LEGACY_PAGE_TRANSPORT:
        # Preserve existing cache/database ownership for the legacy contract.
        return account_id
    return f"{INSTAGRAM_LOGIN_TRANSPORT}:{account_id}"


def _conv_cache_key(s: InstagramBotSettings) -> str:
    return f"ig_bot_conv_ids:{_provider_owner_id(s)}"


def _ingress_degradation_key(s: InstagramBotSettings, source: str) -> str:
    return f"ig_bot_ingress_{source}_degraded:{_provider_owner_id(s)}"


def _record_ingress_degradation(
    s: InstagramBotSettings,
    source: str,
    *,
    state: str,
    reason: str,
) -> None:
    cache.set(
        _ingress_degradation_key(s, source),
        {
            "state": state,
            "reason": _redact_secret_text(reason)[:240],
            "at": timezone.now().timestamp(),
        },
        INGRESS_DEGRADATION_TTL,
    )


def _clear_ingress_degradation(s: InstagramBotSettings, source: str) -> None:
    cache.delete(_ingress_degradation_key(s, source))


def _current_ingress_degradation(s: InstagramBotSettings) -> dict[str, object] | None:
    signals = []
    for source in ("refresh", "poll"):
        value = cache.get(_ingress_degradation_key(s, source))
        if not isinstance(value, dict) or not isinstance(value.get("state"), str):
            continue
        try:
            observed_at = float(value.get("at") or 0)
        except (TypeError, ValueError):
            observed_at = 0.0
        signals.append({
            "source": source,
            "state": value["state"][:80],
            "reason": str(value.get("reason") or "provider_unavailable")[:240],
            "at": observed_at,
        })
    if not signals:
        return None
    return max(signals, key=lambda item: item["at"])


def _valid_conv_snapshot(value) -> list[str]:
    if not isinstance(value, list) or len(value) > CONV_MAX_IDS:
        return []
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            return []
        item = item.strip()
        if not _CONV_ID_RE.fullmatch(item):
            return []
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _valid_conversation_page_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
    except (TypeError, ValueError):
        return False
    query_keys = {key.lower() for key, _value in parse_qsl(parsed.query, keep_blank_values=True)}
    # Meta includes access_token in paging.next. It is stripped before any
    # request; other credential-like parameters remain invalid.
    query_keys.discard("access_token")
    return (
        parsed.scheme == "https"
        and parsed.netloc in {"graph.facebook.com", "graph.instagram.com"}
        and parsed.path.startswith(f"/{GRAPH_VERSION}/")
        and not parsed.fragment
        and not query_keys.intersection(GRAPH_SENSITIVE_QUERY_KEYS)
    )


def _valid_provider_conversation_page_url(
    s: InstagramBotSettings,
    value: str,
) -> bool:
    if not _valid_conversation_page_url(value):
        return False
    expected_host = (
        "graph.instagram.com"
        if provider_transport(s) == INSTAGRAM_LOGIN_TRANSPORT
        else "graph.facebook.com"
    )
    return urlsplit(value).netloc == expected_host


def _valid_conversation_cursor(value) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value or not _CONV_CURSOR_RE.fullmatch(value):
        return ""
    return value


def _merge_conv_ids(*collections) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for collection in collections:
        for item in _valid_conv_snapshot(list(collection) if isinstance(collection, tuple) else collection):
            if item not in seen:
                seen.add(item)
                merged.append(item)
                if len(merged) >= CONV_MAX_IDS:
                    return merged
    return merged


def _stored_conversation_discovery_ids(s: InstagramBotSettings) -> list[str]:
    owner_page_id = str(getattr(s, "conversation_discovery_page_id", "") or "").strip()
    current_page_id = _provider_owner_id(s)
    if owner_page_id and owner_page_id != current_page_id:
        return []
    return _valid_conv_snapshot(getattr(s, "conversation_discovery_ids", []))


def _stored_conversation_discovery_cursor(s: InstagramBotSettings) -> str:
    owner_page_id = str(getattr(s, "conversation_discovery_page_id", "") or "").strip()
    if owner_page_id and owner_page_id != _provider_owner_id(s):
        return ""
    return _valid_conversation_cursor(
        getattr(s, "conversation_discovery_cursor", "")
    )


def _valid_conversation_cursor_hashes(value) -> list[str]:
    if not isinstance(value, list) or len(value) > CONV_MAX_PAGES:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{64}", item):
            return []
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


class _ConversationDiscoveryLeaseLost(RuntimeError):
    pass


def _claim_conversation_discovery_lease(s: InstagramBotSettings) -> str | None:
    if not s.pk:
        return None
    now = timezone.now()
    token = secrets.token_hex(16)
    available = (
        Q(conversation_discovery_lease_token="")
        | Q(conversation_discovery_lease_expires_at__isnull=True)
        | Q(conversation_discovery_lease_expires_at__lte=now)
    )
    updated = InstagramBotSettings.objects.filter(pk=s.pk).filter(available).update(
        conversation_discovery_lease_token=token,
        conversation_discovery_lease_expires_at=(
            now + timedelta(seconds=CONV_REFRESH_LOCK_TTL)
        ),
        updated_at=now,
    )
    return token if updated == 1 else None


def _release_conversation_discovery_lease(settings_pk: int, token: str) -> None:
    if not settings_pk or not token:
        return
    InstagramBotSettings.objects.filter(
        pk=settings_pk,
        conversation_discovery_lease_token=token,
    ).update(
        conversation_discovery_lease_token="",
        conversation_discovery_lease_expires_at=None,
        updated_at=timezone.now(),
    )


def _save_conversation_discovery(
    s: InstagramBotSettings,
    ids: list[str],
    cursor: str = "",
    *,
    lease_token: str,
    scan_ids: list[str] | None = None,
    pages_seen: int = 0,
    cursor_hashes: list[str] | None = None,
    completed_at=None,
) -> list[str]:
    ids = _valid_conv_snapshot(ids)
    cursor = _valid_conversation_cursor(cursor)
    scan_ids = _valid_conv_snapshot(scan_ids or [])
    cursor_hashes = _valid_conversation_cursor_hashes(cursor_hashes or [])
    pages_seen = max(0, min(int(pages_seen or 0), CONV_MAX_PAGES))
    now = timezone.now()
    values = {
        "conversation_discovery_ids": ids,
        "conversation_discovery_cursor": cursor,
        "conversation_discovery_page_id": _provider_owner_id(s),
        "conversation_discovery_scan_ids": scan_ids,
        "conversation_discovery_cursor_hashes": cursor_hashes,
        "conversation_discovery_pages_seen": pages_seen,
        "conversation_discovery_updated_at": now,
        "updated_at": now,
    }
    if completed_at is not None:
        values["conversation_discovery_completed_at"] = completed_at
    updated = InstagramBotSettings.objects.filter(
        pk=s.pk,
        conversation_discovery_lease_token=lease_token,
    ).update(**values)
    if updated != 1:
        raise _ConversationDiscoveryLeaseLost("conversation discovery lease lost")
    for name, value in values.items():
        setattr(s, name, value)
    cache.set(_conv_cache_key(s), ids, CONV_CACHE_TTL)
    return ids


def _reset_conversation_discovery_owner(
    s: InstagramBotSettings,
    lease_token: str,
) -> None:
    _save_conversation_discovery(
        s,
        [],
        "",
        lease_token=lease_token,
        scan_ids=[],
        pages_seen=0,
        cursor_hashes=[],
    )
    InstagramBotSettings.objects.filter(
        pk=s.pk,
        conversation_discovery_lease_token=lease_token,
    ).update(conversation_discovery_completed_at=None)
    s.conversation_discovery_completed_at = None


def _conversation_discovery_url(s: InstagramBotSettings, cursor: str = "") -> str:
    if provider_transport(s) == LEGACY_PAGE_TRANSPORT:
        params = {
            "platform": "instagram",
            "fields": "id",
            "limit": CONV_PAGE_LIMIT,
        }
    else:
        params = {
            "fields": "id,participants,updated_time",
            "limit": CONV_PAGE_LIMIT,
        }
    if cursor:
        params["after"] = cursor
    return _provider_url(
        s,
        f"/{_provider_account_id(s)}/conversations",
        params,
    )


def _validate_conversation_discovery_page(
    envelope,
    s: InstagramBotSettings | None = None,
) -> tuple[list[dict], str]:
    if not isinstance(envelope, dict) or not isinstance(envelope.get("data"), list):
        raise ValueError("malformed data")
    conversations: list[dict] = []
    seen: set[str] = set()
    for conversation in envelope["data"]:
        if not isinstance(conversation, dict):
            raise ValueError("malformed conversation")
        conversation_id = conversation.get("id")
        if (
            not isinstance(conversation_id, str)
            or not _CONV_ID_RE.fullmatch(conversation_id.strip())
        ):
            raise ValueError("malformed conversation id")
        conversation_id = conversation_id.strip()
        if conversation_id not in seen:
            seen.add(conversation_id)
            participants = conversation.get("participants")
            if participants is not None and (
                not isinstance(participants, dict)
                or not isinstance(participants.get("data"), list)
            ):
                # One malformed participant block must fail that conversation
                # closed, not leave an older participant mapping poll-eligible.
                participants = None
            updated_time = conversation.get("updated_time")
            if updated_time is not None and (
                not isinstance(updated_time, str)
                or _parse_ig_time(updated_time) is None
            ):
                raise ValueError("malformed conversation time")
            conversations.append({
                "id": conversation_id,
                "participants": participants,
                "updated_time": updated_time,
            })
    paging = envelope.get("paging")
    if paging is None:
        return conversations, ""
    if not isinstance(paging, dict):
        raise ValueError("malformed paging")
    next_url = paging.get("next")
    if not next_url:
        return conversations, ""
    valid_page_url = bool(
        isinstance(next_url, str)
        and (
            _valid_provider_conversation_page_url(s, next_url)
            if s is not None
            else _valid_conversation_page_url(next_url)
        )
    )
    if not isinstance(next_url, str) or not valid_page_url:
        raise ValueError("untrusted paging URL")
    query_cursor = _valid_conversation_cursor(
        dict(parse_qsl(urlsplit(next_url).query, keep_blank_values=True)).get("after")
    )
    cursors = paging.get("cursors") or {}
    if not isinstance(cursors, dict):
        raise ValueError("malformed cursors")
    cursor = _valid_conversation_cursor(cursors.get("after"))
    if not cursor or not query_cursor:
        raise ValueError("malformed cursor")
    if cursor != query_cursor:
        raise ValueError("conflicting cursor")
    return conversations, cursor


def _conversation_participant_state(
    s: InstagramBotSettings,
    conversation: dict,
) -> tuple[str, str]:
    """Return the sole external participant or a fail-closed exclusion reason."""
    if provider_transport(s) != INSTAGRAM_LOGIN_TRANSPORT:
        return "", ""
    participants = conversation.get("participants")
    if participants is None:
        return "", "ambiguous_participants"
    data = participants.get("data") if isinstance(participants, dict) else None
    if not isinstance(data, list):
        return "", "ambiguous_participants"
    owner_id = _provider_account_id(s)
    participant_ids: list[str] = []
    for participant in data:
        participant_id = (
            str(participant.get("id") or "").strip()
            if isinstance(participant, dict)
            else ""
        )
        if not participant_id or not _SENDER_ID_RE.fullmatch(participant_id):
            return "", "ambiguous_participants"
        if participant_id not in participant_ids:
            participant_ids.append(participant_id)
    external = [item for item in participant_ids if item != owner_id]
    if owner_id not in participant_ids or len(external) != 1:
        return "", "ambiguous_participants"
    return external[0], ""


def _sync_discovered_conversation_state(
    s: InstagramBotSettings,
    conversations: list[dict],
) -> None:
    """Persist participant/update metadata so polling can avoid hidden/unchanged threads."""
    if provider_transport(s) != INSTAGRAM_LOGIN_TRANSPORT or not conversations:
        return
    normalized: list[tuple[str, str, str, datetime | None]] = []
    for conversation in conversations:
        participant_igsid, exclusion = _conversation_participant_state(s, conversation)
        normalized.append((
            conversation["id"],
            participant_igsid,
            exclusion,
            _parse_ig_time(conversation.get("updated_time") or ""),
        ))
    now = timezone.now()
    automatic_exclusions = {"client_hidden", "ambiguous_participants"}
    for conversation_id, participant_igsid, exclusion, provider_updated_at in normalized:
        with transaction.atomic():
            client = None
            if participant_igsid:
                client = (
                    IgClient.objects.select_for_update()
                    .only("id", "hidden_at")
                    .filter(igsid=participant_igsid)
                    .first()
                )
            cursor, _created = IgPollCursor.objects.get_or_create(
                conversation_id=conversation_id
            )
            cursor = IgPollCursor.objects.select_for_update().get(pk=cursor.pk)
            update_fields = ["participant_igsid", "provider_updated_at", "updated_at"]
            cursor.participant_igsid = participant_igsid
            cursor.provider_updated_at = provider_updated_at
            if client is not None and client.hidden_at:
                exclusion = "client_hidden"
            if exclusion:
                cursor.excluded_at = cursor.excluded_at or now
                cursor.excluded_reason = exclusion
                update_fields.extend(["excluded_at", "excluded_reason"])
            elif cursor.excluded_reason in automatic_exclusions:
                cursor.excluded_at = None
                cursor.excluded_reason = ""
                cursor.synced_provider_updated_at = None
                cursor.next_attempt_at = None
                update_fields.extend([
                    "excluded_at",
                    "excluded_reason",
                    "synced_provider_updated_at",
                    "next_attempt_at",
                ])
            cursor.updated_at = now
            cursor.save(update_fields=list(dict.fromkeys(update_fields)))


def refresh_conv_ids(s: InstagramBotSettings, page_token: str) -> list[str]:
    """Refresh Instagram conversations in small resumable Graph pages."""
    if not _provider_account_id(s):
        _record_ingress_degradation(
            s,
            "refresh",
            state="conversation_refresh_failed",
            reason="missing_provider_account_id",
        )
        return []
    lease_token = _claim_conversation_discovery_lease(s)
    if not lease_token:
        fresh = InstagramBotSettings.objects.get(pk=s.pk)
        return get_conv_ids_cached(fresh) or []
    try:
        fresh = InstagramBotSettings.objects.get(pk=s.pk)
        owner_page_id = str(
            getattr(fresh, "conversation_discovery_page_id", "") or ""
        ).strip()
        if owner_page_id and owner_page_id != _provider_owner_id(fresh):
            _reset_conversation_discovery_owner(fresh, lease_token)
            fresh.refresh_from_db()
        stale = _merge_conv_ids(
            _stored_conversation_discovery_ids(fresh),
            _valid_conv_snapshot(cache.get(_conv_cache_key(fresh))),
        )
        return _refresh_conv_ids_unlocked(fresh, page_token, stale, lease_token)
    except _ConversationDiscoveryLeaseLost:
        fresh = InstagramBotSettings.objects.get(pk=s.pk)
        return get_conv_ids_cached(fresh) or []
    finally:
        _release_conversation_discovery_lease(s.pk, lease_token)


def _refresh_conv_ids_unlocked(
    s: InstagramBotSettings,
    page_token: str,
    stale: list[str],
    lease_token: str,
) -> list[str]:
    """Advance the durable conversation discovery cursor by a bounded slice.

    The old implementation waited for a full list before publishing. In
    production a heavy first page could fail forever and polling stayed pinned
    to an old two-thread cache. This function publishes each validated slice
    while keeping a MariaDB cursor so the next cycle resumes rather than
    restarts.
    """
    stored = _stored_conversation_discovery_ids(s)
    cursor = _stored_conversation_discovery_cursor(s)
    base_snapshot = _merge_conv_ids(stored, stale)
    discovered = (
        _valid_conv_snapshot(getattr(s, "conversation_discovery_scan_ids", []))
        if cursor
        else []
    )
    seen = set(discovered)
    published = list(base_snapshot)
    page_cursor = cursor
    pages_seen = int(getattr(s, "conversation_discovery_pages_seen", 0) or 0) if cursor else 0
    cursor_hashes = (
        _valid_conversation_cursor_hashes(
            getattr(s, "conversation_discovery_cursor_hashes", [])
        )
        if cursor
        else []
    )
    visited_cursor_hashes = set(cursor_hashes)
    for page_index in range(CONV_DISCOVERY_PAGES_PER_REFRESH):
        if pages_seen >= CONV_MAX_PAGES:
            _record_ingress_degradation(
                s,
                "refresh",
                state="conversation_refresh_failed",
                reason="page_cap",
            )
            _save_conversation_discovery(
                s,
                published,
                "",
                lease_token=lease_token,
                scan_ids=[],
                pages_seen=0,
                cursor_hashes=[],
            )
            return published
        if page_index:
            # Fixed conservative spacing is easier to reason about than a
            # provider-header guess and remains within the documented limit.
            time.sleep(CONV_MIN_INTERVAL)
        page_url = _conversation_discovery_url(s, page_cursor)
        code, body = _provider_http(
            s,
            page_url,
            token=page_token,
            timeout=CONV_LIST_TIMEOUT,
        )
        if code != 200:
            _record_ingress_degradation(
                s,
                "refresh",
                state="conversation_refresh_failed",
                reason=_classify_poll_provider_failure(code, body),
            )
            log("warning", "conversations", f"page={page_index + 1} HTTP {code}; keeping published cache")
            cache.set(_conv_cache_key(s), published, CONV_CACHE_TTL)
            return published
        try:
            page_conversations, next_cursor = _validate_conversation_discovery_page(
                json.loads(body),
                s,
            )
            _sync_discovered_conversation_state(s, page_conversations)
            page_ids = [conversation["id"] for conversation in page_conversations]
            for conversation_id in page_ids:
                if conversation_id not in seen:
                    seen.add(conversation_id)
                    discovered.append(conversation_id)
                    if len(discovered) > CONV_MAX_IDS:
                        raise ValueError("conversation cap exceeded")
            pages_seen += 1
            if not next_cursor:
                ids = _save_conversation_discovery(
                    s,
                    discovered,
                    "",
                    lease_token=lease_token,
                    scan_ids=[],
                    pages_seen=0,
                    cursor_hashes=[],
                    completed_at=timezone.now(),
                )
                _clear_ingress_degradation(s, "refresh")
                return ids
            cursor_hash = hashlib.sha256(next_cursor.encode("utf-8")).hexdigest()
            if cursor_hash in visited_cursor_hashes:
                raise ValueError("repeated paging cursor")
            page_cursor = next_cursor
            cursor_hashes.append(cursor_hash)
            visited_cursor_hashes.add(cursor_hash)
            published = _save_conversation_discovery(
                s,
                _merge_conv_ids(discovered, base_snapshot),
                page_cursor,
                lease_token=lease_token,
                scan_ids=discovered,
                pages_seen=pages_seen,
                cursor_hashes=cursor_hashes,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            _record_ingress_degradation(
                s,
                "refresh",
                state="conversation_refresh_failed",
                reason=f"malformed:{exc}",
            )
            log("warning", "conversations", f"page={page_index + 1} malformed; keeping published cache ({exc})")
            cache.set(_conv_cache_key(s), published, CONV_CACHE_TTL)
            return published
    log("info", "conversations", "page budget reached; cursor saved")
    return published


def get_conv_ids_cached(s: InstagramBotSettings | None = None) -> list[str] | None:
    if s is None:
        return None
    cache_key = _conv_cache_key(s)
    stored = _stored_conversation_discovery_ids(s)
    value = cache.get(cache_key)
    if value is None:
        if stored:
            cache.set(cache_key, stored, CONV_CACHE_TTL)
            return stored
        return None
    valid = _valid_conv_snapshot(value)
    if value == []:
        if stored:
            cache.set(cache_key, stored, CONV_CACHE_TTL)
            return stored
        return []
    if not valid:
        cache.delete(cache_key)
        log("warning", "poll_cache", "invalid conversation cache discarded")
        if stored:
            cache.set(cache_key, stored, CONV_CACHE_TTL)
            return stored
        return None
    merged = _merge_conv_ids(stored, valid)
    if merged != value:
        cache.set(cache_key, merged, CONV_CACHE_TTL)
    return merged


def conversation_discovery_status(
    s: InstagramBotSettings,
    *,
    now=None,
) -> dict[str, object]:
    """Expose token-free discovery progress for operations and the dashboard."""
    now = now or timezone.now()
    owner_page_id = str(
        getattr(s, "conversation_discovery_page_id", "") or ""
    ).strip()
    current_page_id = _provider_owner_id(s)
    owner_matches = not owner_page_id or owner_page_id == current_page_id
    ids = _stored_conversation_discovery_ids(s) if owner_matches else []
    scan_ids = (
        _valid_conv_snapshot(getattr(s, "conversation_discovery_scan_ids", []))
        if owner_matches
        else []
    )
    in_progress = bool(owner_matches and _stored_conversation_discovery_cursor(s))
    updated_at = getattr(s, "conversation_discovery_updated_at", None)
    completed_at = getattr(s, "conversation_discovery_completed_at", None)
    lease_expires_at = getattr(s, "conversation_discovery_lease_expires_at", None)
    if not owner_matches:
        state = "account_changed"
    elif in_progress:
        state = "in_progress"
    elif completed_at:
        state = "complete"
    else:
        state = "not_observed"
    result: dict[str, object] = {
        "state": state,
        "conversation_count": len(ids),
        "scan_count": len(scan_ids),
        "pages_seen": int(
            getattr(s, "conversation_discovery_pages_seen", 0) or 0
        ),
        "owner_matches": owner_matches,
        "lease_active": bool(lease_expires_at and lease_expires_at > now),
    }
    if updated_at:
        result["updated_age_seconds"] = round(
            max(0.0, (now - updated_at).total_seconds()),
            1,
        )
    if completed_at:
        result["completed_age_seconds"] = round(
            max(0.0, (now - completed_at).total_seconds()),
            1,
        )
    return result


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------
def send_sender_action(s: InstagramBotSettings, recipient_id: str, action: str) -> None:
    """typing_on / typing_off / mark_seen — для відчуття миттєвості (best practice)."""
    account_id = _provider_account_id(s)
    if not account_id:
        return
    page_token = get_page_token(s)
    if not page_token:
        return
    try:
        body = json.dumps({"recipient": {"id": recipient_id}, "sender_action": action}).encode("utf-8")
        _provider_http(
            s,
            _provider_url(s, f"/{account_id}/messages"),
            token=page_token,
            data=body,
            timeout=HTTP_TIMEOUT,
        )
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
ADVANCED_ACCESS_SUBCODE = 2534048
MESSAGING_WINDOW_CLOSED_SUBCODE = 1545041
LINK_SENDING_RESTRICTED_CODE = 508
LINK_SENDING_RESTRICTED_SUBCODE = 2534122
LINK_SENDING_CIRCUIT_TTL = timedelta(hours=24)
_CUSTOMER_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
PERMANENT_HINT = {
    200: "немає потрібного дозволу Meta для Instagram Messaging",
    190: "provider token недійсний (онови IG_INSTAGRAM_BOT або явний legacy token)",
    10: "помилка дозволів або політики Meta",
    100: "некоректний параметр запиту",
    551: "отримувач недоступний (блокування, деактивація або обмеження діалогу)",
}


def _graph_error(body: str) -> dict:
    try:
        err = json.loads(body).get("error", {}) or {}
    except Exception:
        return {}
    return err if isinstance(err, dict) else {}


def _graph_error_codes(body: str) -> tuple[int, int]:
    err = _graph_error(body)
    try:
        return int(err.get("code", 0) or 0), int(err.get("error_subcode", 0) or 0)
    except Exception:
        return 0, 0


def _graph_error_fbtrace_id(body: str) -> str:
    value = str(_graph_error(body).get("fbtrace_id") or "").strip()
    return value[:128] if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) else ""


def _contains_customer_url(text: str) -> bool:
    return bool(_CUSTOMER_URL_RE.search(str(text or "")))


def _strip_customer_urls(text: str) -> str:
    """Remove blocked URLs while preserving useful product/size/price text."""
    kept: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = _CUSTOMER_URL_RE.sub("", raw_line)
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        if line.casefold().rstrip(":") in {
            "💳 посилання на оплату",
            "💳 ссылка на оплату",
            "посилання",
            "ссылка",
            "link",
        }:
            continue
        if line:
            kept.append(line)
    cleaned = "\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip(" \n-:")
    return cleaned


def _invoice_deal_for_reply(client: IgClient | None, reply: str):
    """Return the persisted deal whose exact payment/proposal URL is in reply."""
    if not client or not getattr(client, "pk", None) or not reply:
        return None
    try:
        # Assisted checkout links are bearer URLs, so resolve only their
        # digest to the proposal/deal. Never persist or log the raw token.
        proposal_match = re.search(r"/offer/a/([^\s/?#]+)/?", str(reply or ""))
        if proposal_match:
            from management.ig_bot_models import IgCheckoutAccessToken

            proposal = (
                IgCheckoutAccessToken.objects.select_related("proposal__deal")
                .filter(
                    token_digest=IgCheckoutAccessToken.digest(proposal_match.group(1)),
                    proposal__client_id=client.pk,
                )
                .first()
            )
            if proposal and proposal.proposal.deal_id:
                return proposal.proposal.deal
        deals = (
            client.deals.exclude(invoice_url="")
            .only("id", "client_id", "invoice_id", "invoice_url", "updated_at")
            .order_by("-updated_at", "-id")[:20]
        )
        for deal in deals:
            if deal.invoice_url and deal.invoice_url in reply:
                return deal
    except Exception:
        return None
    return None


def _allows_linkless_fallback(
    reply: str,
    control: dict | None,
    client: IgClient | None = None,
) -> bool:
    """Catalog links may degrade to text; real payment URLs never may."""
    control = control if isinstance(control, dict) else {}
    return not bool(
        control.get("paylink")
        or _PAY_URL_RE.search(str(reply or ""))
        or _invoice_deal_for_reply(client, reply)
    )


def _link_circuit_active(s: InstagramBotSettings) -> bool:
    return bool(s.link_send_blocked_until and s.link_send_blocked_until > timezone.now())


def _activate_link_send_circuit(
    s: InstagramBotSettings,
    body: str,
    *,
    emit_alert: bool = True,
) -> None:
    now = timezone.now()
    blocked_until = now + LINK_SENDING_CIRCUIT_TTL
    fbtrace_id = _graph_error_fbtrace_id(body)
    try:
        s.link_send_blocked_until = blocked_until
        s.link_send_last_error_at = now
        s.link_send_last_fbtrace_id = fbtrace_id
        s.save(update_fields=[
            "link_send_blocked_until",
            "link_send_last_error_at",
            "link_send_last_fbtrace_id",
            "updated_at",
        ])
    except Exception:
        pass
    if emit_alert:
        try:
            notify_manager(
                "⚠️ Instagram тимчасово обмежив надсилання посилань у Direct "
                "(Meta 508/2534122). Бот продовжить відповідати корисним текстом без URL. "
                "Платіжні посилання не будуть маскуватися; їх потрібно перевірити менеджеру. "
                "Перевірте Instagram → Налаштування → Статус облікового запису.",
                dedupe_key=f"ig_link_restriction:{now.date().isoformat()}",
                event_type="link_send_restriction",
            )
        except Exception:
            pass


def _permanent_send_alert_text(hint: str, *, graph_subcode: int = 0) -> str:
    if graph_subcode == ADVANCED_ACCESS_SUBCODE:
        return (
            "❗️ IG бот не може відповідати нерольовим користувачам.\n"
            f"Причина: {hint}.\n\n"
            "Перевірте Advanced Access для instagram_business_manage_messages "
            "(або legacy instagram_manage_messages) та ролі застосунку."
        )
    return (
        "❗️ Meta відхилила відповідь Instagram-клієнту.\n"
        f"Причина: {hint}.\n"
        "Це не є доказом проблеми з дозволами; потрібна окрема перевірка діалогу/"
        "контенту в Meta Inbox."
    )


def _is_advanced_access_hint(hint: str) -> bool:
    value = str(hint or "")
    return (
        value.startswith("Meta відхилила нерольового отримувача:")
        and "Advanced Access" in value
    )


def _payment_delivery_failure_reason(hint: str) -> str:
    value = str(hint or "").casefold()
    if "advanced access" in value or "нерольового отримувача" in value:
        return "meta_advanced_access"
    if "24-годинне" in value or "вікно відповіді" in value:
        return "meta_messaging_window_closed"
    if (
        "508" in value
        and "2534122" in value
    ) or "блокує посилання" in value or "обмежив надсилання посилань" in value:
        return "meta_link_restriction"
    if "provider token" in value or "недійсний" in value:
        return "provider_token_invalid"
    return "meta_send_blocked"


def _queue_payment_link_delivery_review(
    client: IgClient,
    reply: str,
    hint: str,
    *,
    deal=None,
) -> bool:
    """Preserve a generated invoice URL for a manager; never strip it silently."""
    deal = deal or _invoice_deal_for_reply(client, reply)
    if not client or (deal is None and not _PAY_URL_RE.search(str(reply or ""))):
        return False
    from management.models import IgFollowUpTask

    now = timezone.now()
    failure_reason = _payment_delivery_failure_reason(hint)
    cancelled_payment_reminders = 0
    with transaction.atomic():
        IgClient.objects.select_for_update().only("id").get(pk=client.pk)
        task_qs = (
            IgFollowUpTask.objects.select_for_update()
            .filter(
                client=client,
                kind=IgFollowUpTask.Kind.MANAGER_TASK,
                reason="payment_link_delivery_review",
                status=IgFollowUpTask.Status.SKIPPED,
            )
        )
        if deal is not None:
            invoice_url = str(getattr(deal, "invoice_url", "") or "").strip()
            task_qs = task_qs.filter(deal=deal)
            if invoice_url and invoice_url in str(reply or ""):
                task_qs = task_qs.filter(message_text__contains=invoice_url)
            else:
                task_qs = task_qs.filter(message_text=reply)
        else:
            task_qs = task_qs.filter(deal__isnull=True, message_text=reply)
        task = task_qs.order_by("-id").first()
        if task is None:
            task = IgFollowUpTask.objects.create(
                client=client,
                deal=deal,
                due_at=now,
                status=IgFollowUpTask.Status.SKIPPED,
                kind=IgFollowUpTask.Kind.MANAGER_TASK,
                reason="payment_link_delivery_review",
                message_text=reply,
                skip_reason=failure_reason,
                last_error=(hint or failure_reason)[:500],
            )
        if deal is not None:
            cancelled_payment_reminders = IgFollowUpTask.objects.filter(
                client=client,
                deal=deal,
                kind=IgFollowUpTask.Kind.PAYMENT,
                status=IgFollowUpTask.Status.PENDING,
            ).update(
                status=IgFollowUpTask.Status.CANCELLED,
                skip_reason="payment_link_not_delivered",
                updated_at=now,
            )
    if cancelled_payment_reminders:
        from management.services import bot_followups

        bot_followups._update_client_next(client)
    try:
        _apply_stage(client, IgClient.Stage.LEAD_TO_MANAGER)
    except Exception:
        pass
    label = client.username or client.display_name or client.igsid
    if failure_reason == "meta_link_restriction":
        alert = (
            f"🧍 IG: Meta заблокувала доставку платіжного посилання для {label}.\n"
            "Invoice збережено в завданні менеджеру; надішліть його вручну після перевірки Meta Inbox.\n"
            f"Платіжне повідомлення:\n{str(reply or '')[:1500]}\n"
            f"Причина: {hint}"
        )
    else:
        alert = (
            f"🧍 IG: платіжне повідомлення для {label} не доставлено.\n"
            "Invoice збережено в окремому завданні менеджеру; перевірте діалог і надішліть його вручну.\n"
            f"Платіжне повідомлення:\n{str(reply or '')[:1500]}\n"
            f"Причина: {hint}"
        )
    try:
        notify_manager(
            alert,
            dedupe_key=f"ig_payment_link_delivery:{client.pk}:{task.pk}",
            event_type="payment_link_delivery_review",
            client=client,
        )
    except Exception:
        pass
    return True


def _classify_poll_provider_failure(code: int, body: str) -> str:
    """Keep operator-visible polling failures actionable without storing body."""
    graph_code, graph_subcode = _graph_error_codes(body)
    if graph_subcode == ADVANCED_ACCESS_SUBCODE:
        return "meta_advanced_access"
    if graph_code == 190:
        return "provider_token_invalid"
    if graph_code in {10, 200}:
        return "meta_permission_error"
    if graph_subcode == MESSAGING_WINDOW_CLOSED_SUBCODE:
        return "meta_messaging_window_closed"
    if code == 429 or graph_code in RATE_LIMIT_CODES:
        return "meta_rate_limit"
    if code == -1:
        if str(body or "") == "graph_url_policy":
            return "graph_url_policy"
        return "provider_network_error"
    return f"http_{code}"


def _classify_send_error(code: int, body: str) -> tuple[str, str]:
    """Повертає (kind, hint) без здогадок про Advanced Access."""
    if code == -1 or code >= 500:
        return "transient", "тимчасова мережева/серверна помилка"
    ec, sub = _graph_error_codes(body)
    if code == 429 or ec in RATE_LIMIT_CODES:
        # Meta explicitly rejected this request before delivery, so the worker
        # may retry it later without the duplicate risk of a timeout or 5xx.
        return "retryable", "ліміт частоти (retry пізніше)"
    if sub == ADVANCED_ACCESS_SUBCODE:
        return (
            "permanent",
            "Meta відхилила нерольового отримувача: немає Advanced Access на "
            "instagram_business_manage_messages (legacy instagram_manage_messages) "
            "або отримувач не має ролі в застосунку",
        )
    if sub == MESSAGING_WINDOW_CLOSED_SUBCODE:
        return (
            "permanent",
            "24-годинне вікно відповіді Meta закрите; потрібен дозволений message tag "
            "або нове повідомлення від користувача",
        )
    if (
        code == 400
        and ec == LINK_SENDING_RESTRICTED_CODE
        and sub == LINK_SENDING_RESTRICTED_SUBCODE
    ):
        return (
            "link_restricted",
            "Instagram тимчасово обмежив надсилання посилань "
            f"(code {ec}, subcode {sub})",
        )
    suffix = f" (code {ec}, subcode {sub})" if sub else f" (code {ec})"
    return "permanent", PERMANENT_HINT.get(ec, "відмова Graph API") + suffix


def _delivery_status_for_error(code: int, body: str) -> str:
    graph_code, graph_subcode = _graph_error_codes(body)
    if graph_subcode == ADVANCED_ACCESS_SUBCODE:
        return IgClient.DeliveryStatus.ADVANCED_ACCESS
    if graph_subcode == MESSAGING_WINDOW_CLOSED_SUBCODE:
        return IgClient.DeliveryStatus.WINDOW_CLOSED
    if graph_code == 551:
        # Graph #551 is ambiguous: it can be a blocked/restricted thread as
        # well as an inbox request. Ask the operator to inspect Requests,
        # but never claim we proved that the thread is there.
        return IgClient.DeliveryStatus.MESSAGE_REQUEST_CHECK
    return IgClient.DeliveryStatus.SEND_BLOCKED


def _remember_client_delivery_error(recipient_id: str, hint: str, *, code: int, body: str) -> None:
    """Store only classified, bounded delivery data for the affected CRM card."""
    try:
        client = IgClient.objects.filter(igsid=recipient_id).first()
        if not client:
            return
        graph_code, graph_subcode = _graph_error_codes(body)
        client.delivery_status = _delivery_status_for_error(code, body)
        client.delivery_error = (hint or "")[:500]
        client.delivery_http_code = code if code > 0 else None
        client.delivery_graph_code = graph_code or None
        client.delivery_graph_subcode = graph_subcode or None
        client.delivery_failed_at = timezone.now()
        client.save(update_fields=[
            "delivery_status",
            "delivery_error",
            "delivery_http_code",
            "delivery_graph_code",
            "delivery_graph_subcode",
            "delivery_failed_at",
            "updated_at",
        ])
        from management.services.ig_funnel_analytics import record_drop_off_for_client

        record_drop_off_for_client(
            client,
            kind="unreachable",
            reason_code=client.delivery_status or "send_blocked",
            occurred_at=client.delivery_failed_at,
            stage=client.stage,
            actor="meta_delivery",
            evidence={
                "http_code": code,
                "graph_code": graph_code,
                "graph_subcode": graph_subcode,
                "delivery_error": (hint or "")[:500],
                "is_recoverable": False,
            },
            is_recoverable=False,
        )
    except DatabaseError:
        raise
    except Exception:
        pass


def _clear_client_delivery_error(recipient_id: str) -> None:
    try:
        client = IgClient.objects.filter(igsid=recipient_id).first()
        if not client or not client.delivery_status:
            return
        client.delivery_status = ""
        client.delivery_error = ""
        client.delivery_http_code = None
        client.delivery_graph_code = None
        client.delivery_graph_subcode = None
        client.delivery_failed_at = None
        client.save(update_fields=[
            "delivery_status",
            "delivery_error",
            "delivery_http_code",
            "delivery_graph_code",
            "delivery_graph_subcode",
            "delivery_failed_at",
            "updated_at",
        ])
    except Exception:
        pass


def _remember_send_error(s: InstagramBotSettings, hint: str, *, code: int | None = None) -> None:
    detail = f"Meta Send API: {hint}"
    if code is not None:
        detail += f" (HTTP {code})"
    try:
        s.last_error = detail[:1000]
        s.save(update_fields=["last_error"])
    except Exception:
        pass


def _clear_send_error(s: InstagramBotSettings) -> None:
    try:
        if (s.last_error or "").startswith("Meta Send API:"):
            s.last_error = ""
            s.save(update_fields=["last_error"])
    except Exception:
        pass


def send_text(
    s: InstagramBotSettings,
    recipient_id: str,
    text: str,
    *,
    permission_boundary_factory=None,
    provider_message_callback=None,
    allow_url_fallback: bool = False,
    alert_link_restriction: bool = True,
    return_receipt: bool = False,
) -> tuple[bool, str, str] | ProviderDeliveryReceipt:
    """Повертає (ok, kind, hint/delivered_text).

    For the definite Meta 508/2534122 link rejection, an explicitly eligible
    customer reply may be retried exactly once after removing URLs. A timeout,
    disconnect, or 5xx remains ambiguous and is never automatically replayed.
    """
    account_id = _provider_account_id(s)
    if not account_id:
        hint = "missing_provider_account_id"
        _remember_send_error(s, hint)
        return False, "permanent", hint
    page_token = get_page_token(s)
    if not page_token:
        hint = "немає provider token (перевірте IG_INSTAGRAM_BOT)"
        _remember_send_error(s, hint)
        return False, "permanent", hint
    degraded_text = ""
    if (
        _contains_customer_url(text)
        and _link_circuit_active(s)
        and allow_url_fallback
    ):
        fallback = _strip_customer_urls(text)
        if not fallback:
            hint = "Instagram тимчасово блокує посилання, а без URL повідомлення порожнє"
            _remember_send_error(s, hint)
            return False, "permanent", hint
        text = fallback
        degraded_text = fallback

    parts = _split_for_send(text)
    if not parts:
        return False, "permanent", "порожня відповідь"
    ok_any = False
    provider_message_id = ""
    for part in parts:
        boundary = (
            permission_boundary_factory()
            if permission_boundary_factory
            else nullcontext(True)
        )
        with boundary as send_allowed:
            if not send_allowed:
                hint = "permission epoch changed before Meta request"
                if ok_any:
                    return False, "unknown", f"часткова доставка; {hint}"
                return False, "cancelled", hint
            # Позначаємо ДО відправки: echo цього чанка прийде асинхронно і не має
            # сприйнятись за повідомлення менеджера (виправляє хибний авто-стоп).
            _mark_bot_sent(recipient_id, part)
            payload = {
                "recipient": {"id": recipient_id},
                "message": {"text": part},
            }
            if provider_transport(s) == LEGACY_PAGE_TRANSPORT:
                payload["messaging_type"] = "RESPONSE"
            body = json.dumps(payload).encode("utf-8")
            code, resp = _provider_http(
                s,
                _provider_url(s, f"/{account_id}/messages"),
                token=page_token,
                data=body,
            )
        if code == 200:
            message_id = _provider_message_id(resp)
            if return_receipt and not message_id:
                # A multi-chunk response is confirmed only if every accepted
                # chunk has its own Meta ID.  Earlier chunks may be delivered,
                # so this must be terminally unknown rather than a retry.
                return ProviderDeliveryReceipt(
                    False, "unknown", "provider_message_id_missing", ""
                )
            if provider_message_callback:
                try:
                    response_payload = json.loads(resp or "{}")
                except (TypeError, ValueError):
                    response_payload = {}
                callback_message_id = str(response_payload.get("message_id") or "").strip()
                if callback_message_id:
                    provider_message_callback(callback_message_id)
            ok_any = True
            provider_message_id = provider_message_id or message_id
            # Реєструємо `message_id` одразу: echo цього чанка прийде асинхронно,
            # і саме по цьому ідентифікатору ми його впізнаємо. Текстовий
            # відпечаток лишається, але він не працює для медіа й не переживає
            # скидання кеша.
            _register_outgoing_message(message_id, recipient_id, kind="text")
            _clear_send_error(s)
            _clear_client_delivery_error(recipient_id)
            continue
        kind, hint = _classify_send_error(code, resp)
        if kind in {"link_restricted", "permanent", "retryable"}:
            _clear_bot_sent(recipient_id, part)
        if kind == "retryable" and ok_any:
            kind = "unknown"
            hint = (
                "часткова доставка; автоматичний повтор може дублювати вже "
                f"доставлені частини: {hint}"
            )
        if kind == "link_restricted":
            rejected_url = _contains_customer_url(part)
            if rejected_url:
                _activate_link_send_circuit(
                    s,
                    resp,
                    emit_alert=alert_link_restriction,
                )
            can_fallback = (
                allow_url_fallback
                and not ok_any
                and len(parts) == 1
                and rejected_url
            )
            fallback = _strip_customer_urls(part) if can_fallback else ""
            fallback_parts = _split_for_send(fallback) if fallback else []
            if len(fallback_parts) == 1:
                fallback_part = fallback_parts[0]
                fallback_boundary = (
                    permission_boundary_factory()
                    if permission_boundary_factory
                    else nullcontext(True)
                )
                with fallback_boundary as fallback_allowed:
                    if not fallback_allowed:
                        return False, "cancelled", "permission epoch changed before Meta fallback request"
                    _mark_bot_sent(recipient_id, fallback_part)
                    fallback_body = json.dumps({
                        "recipient": {"id": recipient_id},
                        "message": {"text": fallback_part},
                    }).encode("utf-8")
                    if provider_transport(s) == LEGACY_PAGE_TRANSPORT:
                        fallback_payload = json.loads(fallback_body)
                        fallback_payload["messaging_type"] = "RESPONSE"
                        fallback_body = json.dumps(fallback_payload).encode("utf-8")
                    fallback_code, fallback_resp = _provider_http(
                        s,
                        _provider_url(s, f"/{account_id}/messages"),
                        token=page_token,
                        data=fallback_body,
                    )
                if fallback_code == 200:
                    fallback_message_id = _provider_message_id(fallback_resp)
                    if return_receipt and not fallback_message_id:
                        return ProviderDeliveryReceipt(
                            False, "unknown", "provider_message_id_missing", ""
                        )
                    provider_message_id = provider_message_id or fallback_message_id
                    if provider_message_callback:
                        try:
                            fallback_response_payload = json.loads(fallback_resp or "{}")
                        except (TypeError, ValueError):
                            fallback_response_payload = {}
                        message_id = str(
                            fallback_response_payload.get("message_id") or ""
                        ).strip()
                        if message_id:
                            provider_message_callback(message_id)
                    _clear_send_error(s)
                    _clear_client_delivery_error(recipient_id)
                    log("warning", "send_link_fallback", f"→ {recipient_id}: URL removed after Meta 508/2534122")
                    if return_receipt:
                        return ProviderDeliveryReceipt(
                            True,
                            "degraded_link_restriction",
                            fallback_part,
                            provider_message_id,
                        )
                    return True, "degraded_link_restriction", fallback_part
                fallback_kind, fallback_hint = _classify_send_error(
                    fallback_code, fallback_resp
                )
                if fallback_kind in {"link_restricted", "permanent", "retryable"}:
                    _clear_bot_sent(recipient_id, fallback_part)
                if fallback_kind == "transient":
                    fallback_kind = "unknown"
                    fallback_hint = f"результат plain-text fallback не підтверджено: {fallback_hint}"
                elif fallback_kind == "link_restricted":
                    fallback_kind = "permanent"
                    fallback_hint = (
                        "Instagram відхилив навіть одноразову plain-text відповідь "
                        f"(code {LINK_SENDING_RESTRICTED_CODE}, subcode {LINK_SENDING_RESTRICTED_SUBCODE})"
                    )
                if fallback_kind == "permanent":
                    _remember_send_error(s, fallback_hint, code=fallback_code)
                    _remember_client_delivery_error(
                        recipient_id,
                        fallback_hint,
                        code=fallback_code,
                        body=fallback_resp,
                    )
                log("error", "send_link_fallback", f"HTTP {fallback_code} [{fallback_kind}] {fallback_hint}")
                return False, fallback_kind, fallback_hint
            kind = "permanent"
            hint = (
                "Instagram тимчасово обмежив надсилання посилань; "
                "безпечний plain-text fallback неможливий"
                if rejected_url
                else "Meta відхилила plain-text відповідь (code 508, subcode 2534122)"
            )
        if kind == "permanent":
            if ok_any:
                kind = "unknown"
                hint = f"часткова доставка; результат останніх чанків не підтверджено: {hint}"
            else:
                _remember_send_error(s, hint, code=code)
                _remember_client_delivery_error(recipient_id, hint, code=code, body=resp)
        elif kind == "transient":
            # A timeout/5xx can happen after Meta accepted the request. There
            # is no provider idempotency key, so retrying would risk a duplicate.
            kind = "unknown"
            hint = f"результат доставки не підтверджено: {hint}"
        log("error", "send", f"HTTP {code} [{kind}] {hint}")
        return False, kind, hint
    if degraded_text:
        if return_receipt:
            return ProviderDeliveryReceipt(
                True,
                "degraded_link_restriction",
                degraded_text,
                provider_message_id,
            )
        return True, "degraded_link_restriction", degraded_text
    if return_receipt:
        return ProviderDeliveryReceipt(True, "", "", provider_message_id)
    return True, "", ""


def send_text_tagged(
    s: InstagramBotSettings,
    recipient_id: str,
    text: str,
    tag: str = "HUMAN_AGENT",
    *,
    human_authored: bool = False,
) -> tuple[bool, str, str]:
    """Send an explicitly human-authored support reply with ``HUMAN_AGENT``.

    Meta documents this tag for human support beyond the normal response
    window. Automated sales, reminder, and shipment jobs must use the regular
    response window or create an operator task instead.
    """
    if tag != "HUMAN_AGENT" or not human_authored:
        return (
            False,
            "policy",
            "HUMAN_AGENT дозволено лише для явно підтвердженої відповіді human support",
        )
    account_id = _provider_account_id(s)
    if not account_id:
        hint = "missing_provider_account_id"
        _remember_send_error(s, hint)
        return False, "permanent", hint
    page_token = get_page_token(s)
    if not page_token:
        hint = "немає page-token"
        _remember_send_error(s, hint)
        return False, "permanent", hint
    parts = _split_for_send(text)
    if not parts:
        return False, "permanent", "порожня відповідь"
    ok_any = False
    for part in parts:
        _mark_bot_sent(recipient_id, part)
        body = json.dumps(
            {
                "recipient": {"id": recipient_id},
                "message": {"text": part},
                "messaging_type": "MESSAGE_TAG",
                "tag": tag,
            }
        ).encode("utf-8")
        code, resp = _provider_http(
            s,
            _provider_url(s, f"/{account_id}/messages"),
            token=page_token,
            data=body,
        )
        if code == 200:
            ok_any = True
            _clear_send_error(s)
            _clear_client_delivery_error(recipient_id)
            continue
        kind, hint = _classify_send_error(code, resp)
        if kind in {"link_restricted", "permanent", "retryable"}:
            _clear_bot_sent(recipient_id, part)
        if kind == "retryable" and ok_any:
            kind = "unknown"
            hint = (
                "часткова доставка; автоматичний повтор може дублювати вже "
                f"доставлені частини: {hint}"
            )
        if kind == "permanent":
            if ok_any:
                kind = "unknown"
                hint = f"часткова доставка; результат останніх чанків не підтверджено: {hint}"
            else:
                _remember_send_error(s, hint, code=code)
                _remember_client_delivery_error(recipient_id, hint, code=code, body=resp)
        elif kind == "transient":
            kind = "unknown"
            hint = f"результат доставки не підтверджено: {hint}"
        log("error", "send_tag", f"HTTP {code} [{kind}] {hint}")
        return False, kind, hint
    return True, "", ""


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
_CHAT_REASONING_PATTERNS = (
    (
        "payment_decision",
        re.compile(r"\b(оплат\w*|плат\w*|paylink|рахунок\w*|счет\w*)\b", re.I),
    ),
    (
        "order_decision",
        re.compile(
            r"\b(замов\w*|заказ\w*|достав\w*|нова\s+пошт\w*|новая\s+почт\w*|"
            r"відділен\w*|отделен\w*|order\w*|status|delivery|deliver\w*|"
            r"ship\w*|tracking|nova\s+poshta|kyiv|kiev)\b",
            re.I,
        ),
    ),
    (
        "size_fit_decision",
        re.compile(
            r"\b(розмір\w*|размер\w*|oversize|оверсайз\w*|посадк\w*|зріст\w*|рост\w*)\b",
            re.I,
        ),
    ),
    (
        "product_decision",
        re.compile(
            r"\b(товар\w*|футболк\w*|худі|худи|лонгслів\w*|колір\w*|цвет\w*|"
            r"ткан\w*|термохром\w*|наявн\w*|налич\w*|цін\w*|цен\w*)\b",
            re.I,
        ),
    ),
)


def select_chat_reasoning_task(
    history: list[dict], images: list[tuple[str, bytes]] | None = None
) -> str:
    """Choose the provider reasoning task from explicit current-turn evidence."""
    if images:
        return "media_analysis"
    latest_user = ""
    for item in reversed(history or []):
        if item.get("role") == "user" and item.get("text"):
            latest_user = str(item["text"])
            break
    for task, pattern in _CHAT_REASONING_PATTERNS:
        if pattern.search(latest_user):
            return task
    return "customer_chat"


def _gemini_failure_kind(exc: Exception) -> str:
    """Map the bounded live-pool error summary to a safe routing class.

    ``gemini_generate`` intentionally keeps its historical ``str | None``
    return contract.  The typed side channel below lets the fallback layer
    distinguish a provider outage from safety, empty-output, or payload errors
    without persisting raw provider text.
    """
    message = str(exc or "").casefold()
    transient_markers = (
        "read_timeout",
        "transport",
        "quota_429",
        "http_408",
        "http_5xx",
        "live дедлайн",
        "live deadline",
    )
    return "provider_outage" if any(marker in message for marker in transient_markers) else "generation_error"


def gemini_generate(
    s: InstagramBotSettings, history: list[dict], images: list[tuple[str, bytes]] | None = None,
    match_hint: str | None = None, memory_note: str | None = None,
    context_note: str | None = None, client=None, media_hint: str | None = None,
    turn_note: str | None = None,
    failure_context: dict | None = None,
) -> str | None:
    """history: [{'role':'user'|'model','text':str}] хронологічно.
    images: список (mime_type, raw_bytes) для ОСТАННЬОГО (поточного) user-ходу."""
    if failure_context is not None:
        failure_context.clear()
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

    # Текст поточної репліки клієнта потрібен маршрутизації інструкцій: тригер
    # `on:size_question` має спрацьовувати від того, що людина щойно спитала, а
    # не від поля в картці.
    latest_user_text = ""
    for item in reversed(history or []):
        if item.get("role") == "user" and item.get("text"):
            latest_user_text = str(item["text"])
            break
    sys_text = assemble_system_instruction(
        s,
        client=client,
        memory_note=memory_note,
        context_note=context_note,
        match_hint=match_hint,
        media_hint=media_hint,
        turn_note=turn_note,
        turn_text=latest_user_text,
    )

    payload = {
        "contents": contents,
        # Reasoning level is applied centrally from the task policy. The output
        # budget remains reserved for a concise customer-facing answer.
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 4096,
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
    # GEMINI_API/2 → позичання GEMINI_API5/6; selected chat model is primary,
    # then the validated fallback chain.
    # Якщо адмін обрав CUSTOM-ключ — він пробується першим (manual_key).
    manual_key = None
    if s.gemini_source == InstagramBotSettings.CredSource.CUSTOM:
        manual_key = (s.custom_gemini_key or "").strip() or None
    from management.services.call_ai_analysis import (
        gemini_generate_text, CallAIAnalysisError,
    )
    from management.services.gemini_keys import normalize_chat_model
    import time as _time

    def _cb(msg):
        # Реальний час перебору ключів/моделей у консолі бота.
        log("info", "gemini_try", msg)

    effective_model = normalize_chat_model(s.gemini_model)
    reasoning_task = select_chat_reasoning_task(history, images)
    log("info", "gemini_start",
        f"генерую відповідь (chat/{effective_model}; task={reasoning_task}; "
        f"кастом-ключ: {'так' if manual_key else 'ні'})")
    _t0 = _time.monotonic()
    try:
        out = gemini_generate_text(
            payload,
            role="chat",
            manual_key=manual_key,
            log_cb=_cb,
            model_override=effective_model,
            reasoning_task=reasoning_task,
        )
    except CallAIAnalysisError as exc:
        if failure_context is not None:
            failure_context["kind"] = _gemini_failure_kind(exc)
        log("error", "gemini", f"({_time.monotonic() - _t0:.1f}с) {str(exc)[:300]}")
        return None
    except Exception as exc:
        if failure_context is not None:
            failure_context["kind"] = "generation_error"
        log("error", "gemini", f"({_time.monotonic() - _t0:.1f}с) {repr(exc)}")
        return None
    text = (out.get("parsed") or "").strip()
    if not text:
        if failure_context is not None:
            failure_context["kind"] = "empty_response"
        log("warning", "gemini_empty", f"порожня відповідь ({_time.monotonic() - _t0:.1f}с)")
        return None
    try:
        s.last_gemini_model = str(out.get("model") or effective_model)[:80]
        meta = out.get("meta") or {}
        usage = out.get("usage") or {}
        s.last_gemini_key = str(meta.get("key") or "")[:80]
        s.last_gemini_at = timezone.now()
        s.last_gemini_reasoning_task = str(meta.get("reasoning_task") or reasoning_task)[:64]
        s.last_gemini_reasoning_level = str(meta.get("reasoning_level") or "")[:16]
        s.last_gemini_policy_version = str(meta.get("reasoning_policy_version") or "")[:32]
        s.last_gemini_thoughts_tokens = max(
            0, int(meta.get("thoughts_tokens") or usage.get("thoughtsTokenCount") or 0)
        )
        s.last_gemini_candidates_tokens = max(
            0, int(meta.get("candidates_tokens") or usage.get("candidatesTokenCount") or 0)
        )
        s.save(update_fields=[
            "last_gemini_model", "last_gemini_key", "last_gemini_at",
            "last_gemini_reasoning_task", "last_gemini_reasoning_level",
            "last_gemini_policy_version", "last_gemini_thoughts_tokens",
            "last_gemini_candidates_tokens", "updated_at",
        ])
    except Exception:
        pass
    log("info", "gemini_ok",
        f"{out.get('model')} / {(out.get('meta') or {}).get('key')} за {_time.monotonic() - _t0:.1f}с")
    return text


def _prompt_section(source: str, loader) -> str:
    """Получить один блок контекста промпта; сбой не тихий (F-AI-001).

    Раньше каждый источник был обёрнут в `except Exception: pass`, и при сбое
    бот уходил в Gemini без каталога, без цен и без правил доставки — то есть
    уверенно отвечал по общим знаниям модели. Ни warning, ни error в логе.
    Худшая комбинация: ошибка тихая, последствие денежное.

    Поведение сохранено — промпт всё равно собирается, — но отказ становится
    видимым и называет источник.
    """
    try:
        return loader() or ""
    except Exception as exc:
        log("error", "prompt_context", f"{source}: {exc!r}")
        return ""


def _objection_lifecycle_note(client) -> str:
    if client is None:
        return ""
    from management.services.ig_objections import objection_prompt_note

    return objection_prompt_note(client)


def assemble_system_instruction(
    s,
    *,
    client=None,
    memory_note: str | None = None,
    context_note: str | None = None,
    match_hint: str | None = None,
    media_hint: str | None = None,
    turn_note: str | None = None,
    turn_text: str = "",
) -> str:
    """Собрать system_instruction из всех источников.

    Вынесено из `gemini_generate`, чтобы промпт можно было проверять тестами.
    IMP-026: свойства *ответа* модели непроверяемы (в тестах он замокан
    константой), а свойства *промпта* — проверяемы и детерминированы.
    """
    sys_text = (s.system_prompt or "").strip()
    sys_text = (sys_text + "\n\n" + CANONICAL_PROMPT_AUTHORITY_POLICY).strip()
    live = _bounded_prompt_source(
        s.knowledge_base or "",
        limit=MAX_LIVE_DIRECTIVE_CHARS,
        split_pattern=r"\n\s*\n",
        separator="\n\n",
        source_name="оперативних директив",
    )
    if live:
        sys_text += "\n\n[ОПЕРАТИВНІ ДИРЕКТИВИ — застосовуй у межах порядку істини вище]\n" + live
    sys_text += _context_sections(client, turn_text=turn_text or "")
    sys_text = sys_text.strip()
    # Протокол оплати ([PAYLINK]+[PRODUCT], без вигаданих URL) + правило точності.
    sys_text = (
        (sys_text + "\n\n" + PAYMENT_PROTOCOL_NOTE).strip() if sys_text else PAYMENT_PROTOCOL_NOTE
    )
    sys_text = (sys_text + "\n\n" + ANTI_HALLUCINATION_NOTE).strip()
    sys_text = (sys_text + "\n\n" + automation_guardrails(client)).strip()
    state_note = client_state_note(client)
    if state_note:
        sys_text = (sys_text + "\n\n" + state_note).strip()
    # Факти про готовність замовлення — до генерації, а не після. Раніше система
    # дізнавалась про брак фасону/розміру вже після відповіді моделі й тому
    # писала клієнту сама. Тепер модель бачить той самий стан і питає своїми
    # словами.
    readiness_note = _prompt_section("checkout_readiness", lambda: _checkout_readiness_note(client))
    if readiness_note:
        sys_text = (sys_text + "\n\n" + readiness_note).strip()
    shown_note = _prompt_section("shown_products", lambda: shown_products_note(client))
    if shown_note:
        sys_text = (sys_text + "\n\n" + shown_note).strip()
    # Історія вибору товару: не «який товар зараз», а «як ми до нього дійшли».
    # Два переходи через відсутність вимагають іншої реакції, ніж два переходи
    # за смаком, і модель має бачити різницю.
    journal_note = _prompt_section("funnel_journal", lambda: _funnel_journal_note(client))
    if journal_note:
        sys_text = (sys_text + "\n\n" + journal_note).strip()
    objection_note = _prompt_section(
        "objection_lifecycle",
        lambda: _objection_lifecycle_note(client),
    )
    if objection_note:
        sys_text = (sys_text + "\n\n" + objection_note).strip()
    if memory_note:
        sys_text = (sys_text + "\n\n" + memory_note).strip()
    if context_note:
        sys_text = (sys_text + "\n\n" + context_note).strip()
    if match_hint:
        sys_text = (sys_text + "\n\n" + match_hint).strip()
    if media_hint:
        sys_text = (sys_text + "\n\n" + media_hint).strip()
    if turn_note:
        sys_text = (sys_text + "\n\n" + turn_note).strip()
    return sys_text


def build_prompt_snapshot(client=None, *, turn_text: str = "") -> str:
    """The system instruction as it would be assembled for this client right now.

    `turn_text` дозволяє побачити промпт саме для конкретної репліки клієнта —
    інакше превʼю не покаже тригерні інструкції, і адміністратор вирішить, що
    вони не працюють.
    """
    from management.models import InstagramBotSettings
    from management.services import bot_memory

    settings_obj = InstagramBotSettings.load()
    memory_note = None
    context_note = None
    if getattr(client, "pk", None):
        try:
            memory_note = bot_memory.memory_note(client)
            context_note = bot_memory.client_context_note(client)
        except Exception:
            memory_note = None
            context_note = None
    return assemble_system_instruction(
        settings_obj,
        client=client,
        memory_note=memory_note,
        context_note=context_note,
        turn_note=None,
        turn_text=turn_text,
    )


def _coherent_state_lines(client) -> list[str]:
    """Стан діалогу очима арбітра, а не окремих полів картки.

    F-STATE-001: шість машин стану без арбітра, і клієнт #59 суперечив собі
    одночасно в пʼяти представленнях. Промпт брав стадію напряму з поля, тому
    отримував той самий суперечливий зріз. Тепер джерело одне —
    `resolve_client_state`, з явним приоритетом: повернення грошей вище
    підтвердженої оплати, оплата вище аналізу діалогу.

    Сервісне звернення (обмін, повернення) свідомо описується як **паралельна
    гілка**, а не як стадія: воронка не обнуляється від того, що людина міняє
    розмір.
    """
    try:
        from management.services.ig_client_state import resolve_client_state

        state = resolve_client_state(client)
    except Exception as exc:  # noqa: BLE001 - без арбітра лишаємось на полі
        log("warning", "state_arbiter", repr(exc))
        return [f"стадія: {getattr(client, 'stage', '')}"]

    lines = [f"стадія: {state.stage_label or state.stage} ({state.funnel_progress}% воронки)"]
    if state.payment_reversed:
        lines.append(
            "УВАГА: оплату повернено або скасовано. Людина більше не покупець за цим "
            "замовленням — не дякуй за покупку і не обіцяй доставку. Якщо клієнт "
            "питає про гроші, скажи, що передаєш менеджеру, і додай [MANAGER]."
        )
    elif state.is_buyer:
        source = {"provider": "підтверджено платіжною системою",
                  "manager": "підтверджено менеджером"}.get(state.payment_source, "")
        lines.append(f"клієнт уже купував{f' ({source})' if source else ''}; покупок: {state.purchases}")
    if state.side_flow:
        described = state.side_flow_label or state.side_flow
        if state.requested_size:
            described = f"{described} на розмір {state.requested_size}"
        if state.side_flow_status:
            described = f"{described}, статус: {state.side_flow_status}"
        lines.append(
            f"паралельна гілка: {described}. Це сервіс, не продаж: доведи цю справу "
            "до кінця й не пропонуй нових товарів і знижок, поки вона відкрита."
        )
    return lines


_LANGUAGE_LABELS = {"uk": "українська", "ru": "російська", "en": "англійська"}


def _language_state_lines(client) -> list[str]:
    """Мова — фактами про останні повідомлення, а не однією директивою.

    Прод, клієнт #2: `language='ru'`, `_lang_votes=['ru','ru','uk']`, при тому що
    людина писала українською. Модель отримувала «мова діалогу: ru» і слухалась.
    Одне збережене поле виявилось сильнішим за очевидний текст перед очима.

    Тепер у промпт іде і збережена мова, і те, чим клієнт користується
    насправді, і — якщо є — його пряме прохання. Модель бачить розбіжність і
    може її вирішити; раніше вона про неї навіть не знала.
    """
    stored = str(getattr(client, "language", "") or "").strip().lower()
    lines = []
    recent: list[str] = []
    try:
        from management.models import InstagramBotMessage
        from management.services.bot_sales_classifier import detect_language

        rows = (
            InstagramBotMessage.objects.filter(
                client=client, role=InstagramBotMessage.Role.USER
            )
            .order_by("-id")
            .values_list("text", flat=True)[:5]
        )
        for text in rows:
            detected = detect_language(text or "")
            if detected:
                recent.append(detected)
    except Exception:
        recent = []

    if stored:
        lines.append(f"збережена мова діалогу: {_LANGUAGE_LABELS.get(stored, stored)}")
    if recent:
        latest = recent[0]
        labels = ", ".join(_LANGUAGE_LABELS.get(code, code) for code in recent)
        lines.append(f"мова останніх повідомлень клієнта (від найновішого): {labels}")
        if stored and latest != stored:
            lines.append(
                f"РОЗБІЖНІСТЬ: збережено {_LANGUAGE_LABELS.get(stored, stored)}, а клієнт "
                f"щойно писав {_LANGUAGE_LABELS.get(latest, latest)}. Відповідай мовою "
                "останнього повідомлення клієнта — вона важливіша за збережене значення."
            )
    requested = _requested_language(client)
    if requested:
        lines.append(
            f"КЛІЄНТ ПРЯМО ПОПРОСИВ відповідати {_LANGUAGE_LABELS.get(requested, requested)} мовою — "
            "це найвищий пріоритет. Якщо до цього ти писала іншою, коротко визнай це "
            "своїми словами й далі тримайся тільки цієї мови."
        )
    if not lines:
        lines.append("мова діалогу: ще не визначена, відповідай мовою повідомлення клієнта")
    return lines


def _requested_language(client) -> str:
    context = getattr(client, "sales_context", None)
    if not isinstance(context, dict):
        return ""
    request = context.get("language_request")
    if isinstance(request, dict):
        code = str(request.get("language") or "").strip().lower()
        return code if code in _LANGUAGE_LABELS else ""
    return ""


def _checkout_readiness_note(client) -> str:
    """Блок [СТАН ОФОРМЛЕННЯ] — факти для моделі, а не текст для клієнта."""
    if not getattr(client, "pk", None):
        return ""
    from management.services.ig_checkout_readiness import readiness_prompt_note

    return readiness_prompt_note(client)


def _funnel_journal_note(client) -> str:
    """Блок [ІСТОРІЯ ВИБОРУ ТОВАРУ] — переходи між товарами з причинами."""
    if not getattr(client, "pk", None):
        return ""
    from management.services.ig_funnel_journal import journal_prompt_note

    return journal_prompt_note(client)


SHOWN_PRODUCTS_CONTEXT_KEY = "shown_products"
SHOWN_PRODUCTS_LIMIT = 4


def record_shown_products(client, sender_id: str, selection, delivery) -> list[dict]:
    """Запам'ятати, які товари й у якому порядку ми щойно показали фото.

    Без цього «давай першу» не має відповіді в принципі. У переписці клієнта #5
    бот надіслав дві картинки, а в історію потрапили два однакові рядки
    «Менеджер: (зображення менеджера)» — без назв, без id, без порядку, ще й
    позначені як чужі. Далі на «Давай первую» модель могла тільки вгадувати, і
    описала товар, якого на першій картинці не було.

    Пишемо у двох місцях, бо в них різні задачі: рядок історії робить факт
    відправки видимим у переписці (і дає echo що впізнавати), а
    `sales_context` дає моделі коротку таблицю «позиція → товар» для промпта.
    """
    items = list(getattr(selection, "items", ()) or ())
    if not items:
        return []
    try:
        sent_count = int(getattr(delivery, "sent_count", 0) or 0)
    except (TypeError, ValueError):
        sent_count = 0
    if sent_count <= 0:
        return []
    delivered = items[:sent_count][:SHOWN_PRODUCTS_LIMIT]
    provider_ids = list(getattr(delivery, "provider_message_ids", ()) or ())

    shown: list[dict] = []
    for index, item in enumerate(delivered):
        shown.append({
            "position": index + 1,
            "product_id": int(getattr(item, "product_id", 0) or 0),
            "title": str(getattr(item, "title", "") or "")[:200],
            "url": str(getattr(item, "url", "") or "")[:500],
            "provider_message_id": str(provider_ids[index]) if index < len(provider_ids) else "",
        })

    # Рядок історії: наші картинки більше не зникають із переписки.
    for entry in shown:
        try:
            InstagramBotMessage.objects.create(
                sender_id=sender_id,
                client=client,
                role=InstagramBotMessage.Role.MODEL,
                text=f"(фото товару: {entry['title']})",
                status=InstagramBotMessage.Status.DONE,
                source="catalog_media",
                attachments=json.dumps([entry["url"]], ensure_ascii=False),
                provider_message_id=entry["provider_message_id"],
                processed_at=timezone.now(),
            )
        except Exception as exc:  # noqa: BLE001
            log("warning", "shown_products_row", repr(exc))

    if getattr(client, "pk", None):
        try:
            context = dict(getattr(client, "sales_context", {}) or {})
            context[SHOWN_PRODUCTS_CONTEXT_KEY] = {
                "at": timezone.now().isoformat(),
                "items": [
                    {k: v for k, v in entry.items() if k in ("position", "product_id", "title")}
                    for entry in shown
                ],
            }
            client.sales_context = context
            client.save(update_fields=["sales_context", "updated_at"])
        except Exception as exc:  # noqa: BLE001
            log("warning", "shown_products_context", repr(exc))
    log("info", "shown_products", f"{sender_id}: " + ", ".join(
        f"{entry['position']}={entry['product_id']}" for entry in shown
    ))
    return shown


def shown_products_note(client) -> str:
    """Службовий блок: що саме бачить клієнт на надісланих фото."""
    context = getattr(client, "sales_context", None)
    if not isinstance(context, dict):
        return ""
    state = context.get(SHOWN_PRODUCTS_CONTEXT_KEY)
    if not isinstance(state, dict):
        return ""
    items = [entry for entry in (state.get("items") or []) if isinstance(entry, dict)]
    if not items:
        return ""
    lines = [
        "[НАДІСЛАНІ ФОТО — службове]",
        "Порядок фото, які клієнт бачить у чаті (остання відправка):",
    ]
    for entry in items:
        lines.append(
            f"  {entry.get('position')}) {entry.get('title')} (id={entry.get('product_id')})"
        )
    lines.append(
        "Якщо клієнт каже «першу», «другу», «оту» або відповідає на фото — це саме "
        "ці товари в цьому порядку. Не вгадуй і не підставляй інший товар: "
        "візьми id зі списку вище й постав [PRODUCT:<id>]."
    )
    return "\n".join(lines)


def notify_size_gap(client) -> bool:
    """Сказати менеджеру, що клієнт просить розмір, якого немає.

    Бот у такій ситуації обіцяє «уточню в менеджера і повернусь». Обіцянка має
    бути правдивою, тому тут іде реальне повідомлення. Дедуп на добу за
    (клієнт, товар, фасон, розмір): повторні згадки того самого розміру в
    діалозі не мають перетворюватись на потік однакових алертів.
    """
    if not getattr(client, "pk", None):
        return False
    from management.services.ig_checkout_readiness import checkout_readiness

    state = checkout_readiness(client)
    size = str((state.get("size") or {}).get("requested_unavailable") or "").strip()
    if not size:
        return False
    product = state.get("product") or {}
    fit = str((state.get("fit") or {}).get("selected") or "") or "-"
    # Позначаємо факт відсутності на картці ДО перевірки дедупу: менеджера
    # турбуємо раз на добу, а причина переходу між товарами потрібна щоразу.
    try:
        from management.services.ig_funnel_journal import remember_stock_gap

        remember_stock_gap(
            client,
            product_id=product.get("id"),
            size=size,
            published=bool(product.get("published", True)),
        )
    except Exception as exc:  # noqa: BLE001
        log("warning", "stock_gap_mark", repr(exc))
    key = f"ig_size_gap:{client.pk}:{product.get('id')}:{fit}:{size}"
    if cache.get(key):
        return False
    cache.set(key, 1, 24 * 3600)
    who = client.username or client.display_name or client.igsid
    notify_manager(
        f"📏 IG: клієнт {who} просить розмір {size}, якого немає в наявності.\n"
        f"Товар: {product.get('title') or product.get('id')}"
        f"{f' (фасон {fit})' if fit != '-' else ''}.\n"
        f"Доступні: {', '.join((state.get('size') or {}).get('available') or []) or '—'}.\n"
        "Бот сказав клієнту, що ви уточните можливість і повернетесь з відповіддю."
    )
    log("info", "size_gap", f"{client.igsid}: {product.get('id')} {fit} {size}")
    return True


def customer_turn_note(client, text: str) -> str:
    """Факти саме про це повідомлення клієнта — насамперед посилання на товар.

    Клієнт #5 надіслав `https://twocomms.shop/product/classic-tshirt/` зі словами
    «Вот я за этот вариант», а бот далі говорив про попередній товар: URL не
    читався ніде. Це найточніше можливе висловлення вибору, і воно просто
    втрачалось.
    """
    if not str(text or "").strip():
        return ""
    try:
        from management.services.ig_checkout_readiness import product_reference_from_text

        reference = product_reference_from_text(text)
    except Exception as exc:  # noqa: BLE001
        log("warning", "turn_note", repr(exc))
        return ""

    lines: list[str] = []
    if reference.get("found"):
        current_id = int(getattr(client, "current_product_id", 0) or 0) if client is not None else 0
        lines.append(
            f"клієнт надіслав посилання на наш товар: {reference.get('title')} "
            f"(id={reference.get('product_id')})"
        )
        if current_id and current_id != int(reference.get("product_id") or 0):
            lines.append(
                f"це ІНШИЙ товар, ніж закріплений раніше (id={current_id}). Якщо клієнт "
                "обирає саме його — підтвердь зміну своїми словами й постав "
                f"[PRODUCT:{reference.get('product_id')}]; попередній товар більше не "
                "обговорюй, поки клієнт сам про нього не спитає."
            )
        else:
            lines.append(
                f"якщо це його вибір — постав [PRODUCT:{reference.get('product_id')}]."
            )
    elif reference.get("reason") == "multiple_products":
        titles = ", ".join(
            f"{item.get('title')} (id={item.get('product_id')})"
            for item in reference.get("candidates") or []
        )
        lines.append(
            f"клієнт надіслав посилання на кілька товарів: {titles}. Спитай, який із них "
            "потрібен, і поки не став [PRODUCT]."
        )
    elif reference.get("reason") == "unpublished_or_unknown":
        lines.append(
            "клієнт надіслав посилання на наш сайт, але такого товару зараз немає в "
            "публікації. Скажи це чесно, не вигадуй наявність, і запропонуй разом "
            "підібрати схоже з каталогу."
        )
    if not lines:
        return ""
    return "[ПРО ЦЕ ПОВІДОМЛЕННЯ — службове]\n" + "\n".join(lines)


def client_state_note(client) -> str:
    """Состояние диалога и записанные сигналы — фактами, а не догадкой.

    F-AI-006 был прямым вопросом заказчика: 987 сигналов пишутся и **не читаются**
    при генерации. Проверено grep'ом по всем пяти файлам сборки промпта — ни
    одного обращения к `IgConversationSignal`.

    Значение сигнала не показываем: на проде `value` пуст в 149 из 150 записей,
    а `payload` — в 150 из 150. Показываем тип и давность, потому что это всё,
    что реально есть.
    """
    if not getattr(client, "pk", None):
        return ""
    from django.utils import timezone as _tz

    from management.ig_bot_models import IgConversationSignal

    lines = _coherent_state_lines(client)
    lines.extend(_language_state_lines(client))
    if client.current_size:
        lines.append(f"обраний розмір: {client.current_size}")
    if int(getattr(client, "purchases_count", 0) or 0) > 0:
        lines.append(f"постійний клієнт, покупок: {client.purchases_count}")
    try:
        from management.services.ig_funnel_reset import current_message_floor
        from management.services.ig_post_sale import open_service_case

        case = open_service_case(client)
        if case is not None:
            described = case.get_case_type_display()
            if case.requested_size:
                described = f"{described} на розмір {case.requested_size}"
            lines.append(
                f"відкрите сервісне звернення: {described} "
                f"({case.get_status_display()})"
            )
        floor = current_message_floor(client)
        now = _tz.now()
        signals = (
            IgConversationSignal.objects.filter(client=client, message_id__gte=floor)
            .exclude(signal_type=IgConversationSignal.Type.MANAGER_TAKEOVER)
            .order_by("-created_at")[:10]
        )
        signal_lines = []
        for signal in signals:
            hours = max(0, int((now - signal.created_at).total_seconds() // 3600))
            signal_lines.append(f"  • {signal.signal_type} — {hours} год тому")
    except Exception:
        signal_lines = []
    body = "[СТАН ДІАЛОГУ — службове, не переказуй клієнту]\n" + "\n".join(lines)
    if signal_lines:
        body += "\n[СИГНАЛИ КЛІЄНТА]\n" + "\n".join(signal_lines)
    return body


MAX_BRAND_KNOWLEDGE_CHARS = 3200
MAX_LIVE_DIRECTIVE_CHARS = 2800
MAX_QUICK_LINK_CHARS = 1600


def _bounded_prompt_source(
    value: str,
    *,
    limit: int,
    split_pattern: str,
    separator: str,
    source_name: str,
) -> str:
    """Fit editable prompt text by complete semantic blocks only.

    A character slice can leave a fabricated-looking price, URL or instruction
    tail in the prompt. Paragraphs are the unit for free text; links are one
    line each. If the first block itself is too large it is omitted in full,
    which is safer than silently changing its meaning.
    """
    text = str(value or "").strip()
    if not text or len(text) <= limit:
        return text
    blocks = [block.strip() for block in re.split(split_pattern, text) if block.strip()]
    if not blocks:
        return ""

    kept: list[str] = []
    used = 0
    dropped = 0
    for index, block in enumerate(blocks):
        cost = len(block) + (len(separator) if kept else 0)
        if used + cost > limit:
            dropped = len(blocks) - index
            break
        kept.append(block)
        used += cost

    if not dropped:
        return separator.join(kept)
    notice = f"…({source_name}: {dropped} блок(ів) не вмістилися в бюджет)"
    return separator.join([*kept, notice]) if kept else notice


def _context_sections(client, turn_text: str = "") -> str:
    """База знаний + каталог + playbook-инструкции и ссылки.

    Каждый источник независим: падение одного не должно лишать промпт
    остальных, поэтому блоки собираются по отдельности.
    """
    parts: list[str] = []

    def _brand_knowledge() -> str:
        from management.services.bot_knowledge import get_brand_knowledge

        kb = _bounded_prompt_source(
            get_brand_knowledge(),
            limit=MAX_BRAND_KNOWLEDGE_CHARS,
            split_pattern=r"\n\s*\n",
            separator="\n\n",
            source_name="бази знань",
        )
        return "\n\n[БАЗА ЗНАНЬ ПРО БРЕНД]\n" + kb if kb else ""

    def _catalog() -> str:
        from management.services.bot_catalog import get_catalog_context

        # Full rows stay available for catalog/media workflows. Sales replies get
        # the compact form with every purchasable configuration preserved.
        catalog = get_catalog_context(compact=True)
        return "\n\n" + catalog if catalog else ""

    def _playbook() -> str:
        from management.services.bot_playbooks import active_instruction_block

        # `turn_text` вмикає тригерні інструкції (`on:size_question` тощо).
        # Без нього інструкція з тригером не підмішується — і це правильно:
        # «клієнт питає про розмір зараз» і «в картці лежить objection=size з
        # минулого тижня» — різні речі, а раніше вони були однією.
        instr = active_instruction_block(client, turn_text=turn_text or "")
        return "\n\n[ДОДАТКОВІ PLAYBOOK-ІНСТРУКЦІЇ]\n" + instr if instr else ""

    def _quick_links() -> str:
        from management.models import BotQuickLink

        links = _bounded_prompt_source(
            BotQuickLink.active_block(),
            limit=MAX_QUICK_LINK_CHARS,
            split_pattern=r"\n+",
            separator="\n",
            source_name="швидких посилань",
        )
        return (
            "\n\n[ДОСТУПНІ ПОСИЛАННЯ — надсилай доречне за запитом]\n" + links
            if links
            else ""
        )

    parts.append(_prompt_section("brand_knowledge", _brand_knowledge))
    parts.append(_prompt_section("catalog", _catalog))
    parts.append(_prompt_section("playbook", _playbook))
    parts.append(_prompt_section("quick_links", _quick_links))
    return "".join(parts)


def _switch_reason_for_turn(client, text: str, product_id) -> str:
    """Чому клієнт міняє товар — за фактами цього ходу, не за здогадкою.

    Порядок перевірок = порядок надійності факту. Посилання на сайт і вибір
    позиції з надісланих фото — це однозначні дії клієнта; відсутність розміру
    знає розрахунок готовності. Якщо жоден факт не підходить, лишається
    «клієнт сам обрав», і це теж правда, просто менш детальна.
    """
    from management.services.ig_funnel_journal import SwitchReason, resolve_switch_reason

    try:
        product_id = int(product_id or 0)
    except (TypeError, ValueError):
        product_id = 0

    stock_reason = resolve_switch_reason(client, getattr(client, "current_product_id", None))
    if stock_reason:
        return stock_reason
    try:
        from management.services.ig_checkout_readiness import product_reference_from_text

        reference = product_reference_from_text(text)
        if reference.get("found") and int(reference.get("product_id") or 0) == product_id:
            return SwitchReason.CUSTOMER_LINK
    except Exception:  # noqa: BLE001
        pass
    context = getattr(client, "sales_context", None)
    if isinstance(context, dict) and product_id:
        shown = context.get(SHOWN_PRODUCTS_CONTEXT_KEY)
        if isinstance(shown, dict):
            for entry in shown.get("items") or []:
                if isinstance(entry, dict) and int(entry.get("product_id") or 0) == product_id:
                    return SwitchReason.PHOTO_PICK
    return SwitchReason.CUSTOMER_CHOICE


def _pin_control_product(client, product_id, *, switch_reason: str = "") -> bool:
    """Закрепить товар для детерминированной оплаты (F-AI-002).

    Собственный комментарий в коде объяснял, что pin нужен, «щоб подальша
    оплата формувалась детерміновано саме на нього». При тихом сбое ломалось
    именно то свойство, ради которого код написан: платёжная ссылка могла
    сформироваться на другой товар. Поэтому сбой обязан быть виден.
    """
    from management.services import bot_orders

    try:
        return bool(
            bot_orders.pin_product(client, product_id, switch_reason=switch_reason)
        )
    except Exception as exc:
        log("error", "pin_product", f"{getattr(client, 'igsid', '')}: {exc!r}")
        return False


def _inbound_log_detail(source: str, sender_id: str, text: str, extra: str) -> str:
    """Строка лога о входящем сообщении БЕЗ его текста (F-SEC-009).

    Раньше сюда писалось `text[:140]`, то есть телефон, адрес отделения и
    имя клиента оседали в `InstagramBotLog.detail` — таблице, которую видит
    в том числе внешний Meta-reviewer, и которая не покрыта маскированием
    PII. Диагностическая ценность записи сохраняется: видно источник,
    отправителя, факт наличия текста и его объём.
    """
    length = len(text or "")
    return f"[{source}] {sender_id}: {length} симв.{extra}"


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


def _recover_current_message_media(row, limit: int = 8) -> list[dict] | None:
    """Recover current-turn media from normalized and raw Instagram evidence.

    Meta may emit a follow-up ``ig_post``/story event with a provider ``mid``
    different from the normalized message row. The payment-review service owns
    the bounded exact-mid/timestamp join; the reply worker reuses that same
    contract so a paused/active conversation sees identical media evidence.
    """
    try:
        from management.services.ig_payment_review import (
            _augment_messages_with_raw_media,
            _existing_media,
            classify_media_items,
        )

        raw = {
            "id": getattr(row, "pk", 0),
            "mid": getattr(row, "mid", "") or "",
            "text": getattr(row, "text", "") or "",
            "attachments": getattr(row, "attachments", "") or "",
            "role": getattr(row, "role", "") or "user",
            "created_at": getattr(row, "created_at", None),
        }
        # Normalized attachment URLs are the common path. Avoid scanning up to
        # 240 raw webhook events for every message; fall back to the bounded raw
        # join only when the normalized row has no usable media.
        normalized_media = _existing_media(str(raw.get("attachments") or ""))
        if normalized_media:
            augmented = [raw]
            augmented[0]["media"] = normalized_media
        else:
            augmented = _augment_messages_with_raw_media(getattr(row, "client", None), [raw])
        if not augmented:
            return []
        item = augmented[0]
        media = item.get("media") if isinstance(item.get("media"), list) else []
        payment_context = bool(re.search(
            r"\b(оплат\w*|платіж\w*|платеж\w*|чек\w*|квитанц\w*|receipt|paid)\b",
            str(item.get("text") or ""),
            re.IGNORECASE,
        ))
        classified = classify_media_items(
            str(item.get("text") or ""),
            media,
            payment_context=payment_context,
        )[:limit]
        for media_item in classified:
            media_item["message_id"] = getattr(row, "pk", 0)
            if str(getattr(row, "role", "") or "").casefold() == InstagramBotMessage.Role.MANAGER:
                media_item.update({
                    "role": "manager_reference",
                    "intent": "manager_reference",
                    "actionable": False,
                    "payment_evidence": False,
                    "catalog_match_allowed": False,
                })
        return classified
    except Exception as exc:
        log("warning", "media_recovery", repr(exc))
        return None


def _collect_media_images(media: list[dict] | None, limit: int = 3) -> list[tuple[str, bytes]]:
    """Download bounded media URLs for Gemini; roles remain in ``media``."""
    images: list[tuple[str, bytes]] = []
    seen = set()
    for item in media or []:
        url = str(item.get("url") or "") if isinstance(item, dict) else ""
        if not url or url in seen:
            continue
        seen.add(url)
        image = download_image(url)
        if image:
            images.append(image)
        if len(images) >= limit:
            break
    return images


def _catalog_match_media(media: list[dict] | None) -> list[dict]:
    """Return only media explicitly authorized for catalog vision."""
    return [
        item for item in (media or [])
        if isinstance(item, dict)
        and item.get("role") == "product"
        and item.get("catalog_match_allowed") is True
    ]


def _media_context_hint(media: list[dict] | None) -> str | None:
    """Render evidence-bound media semantics for the customer-facing prompt."""
    rows = []
    labels = {
        "product": "зображення товару/поста каталогу",
        "receipt": "можливий чек/доказ платежу (не підтвердження provider payment)",
        "custom_reference": "референс для custom print",
        "other": "невизначене зображення",
        "manager_reference": "зображення від менеджера",
    }
    for item in media or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "other")
        rows.append(
            f"- {labels.get(role, role)}; intent={item.get('intent') or 'unknown'}; "
            f"source_message_id={item.get('message_id') or 'unknown'}; "
            f"catalog_match_allowed={'yes' if item.get('catalog_match_allowed') else 'no'}"
        )
    if not rows:
        return None
    return (
        "[MEDIA EVIDENCE — службове, клієнт цього не бачить]\n"
        "Розділяй питання про товар, purchase candidate, custom print і payment evidence. "
        "Чек/скриншот не є provider-paid без підтвердження платіжного ledger.\n"
        + "\n".join(rows)
    )


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
            from management.services.ig_catalog_pricing import resolve_product_pricing

            pricing = resolve_product_pricing(p)
            url = f"https://twocomms.shop/product/{p.slug}/"
            if pricing["display"]:
                price_note = f"{pricing['display']} грн"
                price_instruction = (
                    "Назви цю точну ціну"
                    if pricing["exact"]
                    else "Назви діапазон і уточни колір/матеріал та фасон перед точною ціною"
                )
            else:
                price_note = "ціна залежить від конфігурації"
                price_instruction = (
                    "Не називай базову ціну; уточни колір/матеріал та фасон/опції"
                )
            return (
                f"[ЗБІГ ТОВАРУ ЗА ФОТО — впевненість {int(conf * 100)}%] Клієнт прислав "
                f"фото/пост, і це товар з каталогу: «{p.title}» — {price_note}, {url}. "
                f"{price_instruction}; за потреби дай посилання. Веди до покупки."
            )
    return (
        "[ФОТО БЕЗ ВПЕВНЕНОГО ЗБІГУ] Клієнт прислав фото/пост, але точно зіставити з "
        "каталогом не вдалось. Чемно уточни деталі (тип, колір, принт) або запропонуй "
        "переглянути каталог. НЕ вигадуй товар, ціну чи наявність."
    )


def _maybe_pin_from_match(client, match: dict | None) -> bool:
    """Закріплює товар за клієнтом, якщо матчинг фото впевнений (≥ поріг).
    Так пересланий пост одразу «прив'язує» товар для майбутньої оплати."""
    if not client or not match:
        return False
    try:
        from management.services.bot_vision import MATCH_THRESHOLD
    except Exception:
        MATCH_THRESHOLD = 0.6
    pid = match.get("product_id")
    try:
        conf = float(match.get("confidence") or 0)
    except Exception:
        conf = 0.0
    if not pid or conf < MATCH_THRESHOLD:
        return False
    try:
        from management.services import bot_orders

        ok = bot_orders.pin_product(client, pid)
        if ok:
            try:
                client.current_product_confidence = conf
                client.save(update_fields=["current_product_confidence", "updated_at"])
            except Exception:
                pass
        return ok
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Профіль клієнта (IG Graph) — ім'я / username / аватар
# ---------------------------------------------------------------------------
def _profile_global_error_key(s: InstagramBotSettings) -> str:
    return f"ig_profile_global_error:{_provider_owner_id(s)}"


def fetch_ig_profile(s: InstagramBotSettings, igsid: str) -> dict:
    """Тягне профіль співрозмовника через Graph (name/username/profile_pic).
    Порожній dict, якщо немає токена або помилка."""
    if not _provider_account_id(s) or not igsid:
        return {}
    page_token = get_page_token(s)
    if not page_token:
        return {}
    code, body = _provider_http(
        s,
        _provider_url(s, f"/{igsid}", {"fields": "name,username,profile_pic"}),
        token=page_token,
        timeout=HTTP_TIMEOUT,
    )
    if code != 200:
        graph_code, graph_subcode = _graph_error_codes(body)
        if code == 403 or graph_code in {10, 200} or graph_subcode == ADVANCED_ACCESS_SUBCODE:
            cache.set(
                _profile_global_error_key(s),
                "permission_denied",
                PROFILE_PERMISSION_COOLDOWN,
            )
        return {}
    try:
        data = json.loads(body)
    except Exception:
        return {}
    cache.delete(_profile_global_error_key(s))
    return {
        "name": data.get("name") or "",
        "username": data.get("username") or "",
        "profile_pic": data.get("profile_pic") or "",
    }


def _localize_avatar(igsid: str, url: str) -> str:
    """Качає аватар і зберігає у себе (media/ig_avatars/<igsid>.jpg), повертає
    локальний URL. Так аватар не «протухає» й рендериться з нашого домену.
    Порожній рядок — якщо не вдалось завантажити."""
    if not igsid or not url:
        return ""
    img = download_image(url)
    if not img:
        return ""
    _mime, raw = img
    try:
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        path = f"ig_avatars/{igsid}.jpg"
        if default_storage.exists(path):
            default_storage.delete(path)
        saved = default_storage.save(path, ContentFile(raw))
        return default_storage.url(saved)
    except Exception as exc:
        log("warning", "avatar_store", repr(exc))
        return ""


def ensure_profile(s: InstagramBotSettings, client, force: bool = False) -> bool:
    """Підвантажує профіль у картку (ім'я/username/аватар) і локалізує аватарку.

    Оновлюється: якщо профіль ще не тягнули, або застарів (>7 днів), або немає
    локальної копії аватара (легасі-картки). На невдачі — короткий кулдаун."""
    from datetime import timedelta

    if not client:
        return False
    if cache.get(_profile_global_error_key(s)):
        return False
    has_identity = bool(client.display_name or client.username)
    avatar_resolved = bool(client.avatar_local or not client.profile_pic_url)
    fresh = bool(
        client.profile_fetched_at
        and (timezone.now() - client.profile_fetched_at) < timedelta(days=7)
        and (has_identity or bool(client.avatar_local))
        and avatar_resolved
    )
    if fresh and not force:
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
    pic = (prof.get("profile_pic") or "")
    if pic:
        client.profile_pic_url = pic[:600]
        local = _localize_avatar(client.igsid, pic)
        if local:
            client.avatar_local = local[:300]
    client.profile_fetched_at = timezone.now()
    client.profile_sync_attempted_at = client.profile_fetched_at
    client.profile_sync_failures = 0
    client.profile_sync_next_at = None
    client.profile_sync_error_kind = ""
    client.save(update_fields=[
        "display_name", "username", "profile_pic_url", "avatar_local",
        "profile_fetched_at", "profile_sync_attempted_at",
        "profile_sync_failures", "profile_sync_next_at",
        "profile_sync_error_kind", "updated_at",
    ])
    return True


def _record_profile_sync_result(client: IgClient, *, success: bool, error_kind: str = "") -> None:
    """Persist profile retry state after provider I/O without holding a DB lock."""
    now = timezone.now()
    with transaction.atomic():
        locked = IgClient.objects.select_for_update().get(pk=client.pk)
        locked.profile_sync_attempted_at = now
        if success:
            locked.profile_sync_failures = 0
            locked.profile_sync_next_at = None
            locked.profile_sync_error_kind = ""
        else:
            failures = min(int(locked.profile_sync_failures or 0) + 1, 16)
            if error_kind == "permission_denied":
                delay_seconds = PROFILE_PERMISSION_COOLDOWN
            else:
                delay_seconds = min(15 * 60 * (2 ** (failures - 1)), 24 * 60 * 60)
            locked.profile_sync_failures = failures
            locked.profile_sync_next_at = now + timedelta(seconds=delay_seconds)
            locked.profile_sync_error_kind = (error_kind or "provider_error")[:32]
        locked.save(update_fields=[
            "profile_sync_attempted_at",
            "profile_sync_failures",
            "profile_sync_next_at",
            "profile_sync_error_kind",
            "updated_at",
        ])


def refresh_profiles_batch(
    s: InstagramBotSettings,
    *,
    limit: int = PROFILE_REFRESH_BATCH,
    force: bool = False,
) -> dict[str, int | str]:
    """Refresh a bounded batch of IG profiles with a daemon-wide cooldown.

    Profile enrichment is deliberately independent from message polling and
    chat rendering. A failed Graph/profile-picture request is isolated to one
    client and never blocks ingress or customer replies.
    """
    empty = {"checked": 0, "updated": 0, "failed": 0}
    if not s or not _provider_account_id(s):
        return {**empty, "state": "missing_provider_account_id"}
    if not get_page_token(s):
        return {**empty, "state": "no_token"}
    global_error_key = _profile_global_error_key(s)
    global_error = cache.get(global_error_key)
    if global_error:
        return {**empty, "state": str(global_error)}
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = PROFILE_REFRESH_BATCH
    now = timezone.now()
    stale_cutoff = now - timedelta(days=7)
    candidates_qs = IgClient.objects.filter(hidden_at__isnull=True).filter(
        Q(profile_fetched_at__isnull=True)
        | Q(profile_fetched_at__lt=stale_cutoff)
        | Q(display_name="", username="")
        | Q(avatar_local="", profile_pic_url__gt="")
    )
    if not force:
        candidates_qs = candidates_qs.filter(
            Q(profile_sync_next_at__isnull=True)
            | Q(profile_sync_next_at__lte=now)
        )
    candidates = candidates_qs.order_by(
        "profile_sync_next_at", "profile_fetched_at", "id"
    )[: min(400, max(limit * 4, limit))]
    updated = 0
    checked = 0
    failed = 0
    state = "ok"
    for client in candidates:
        if checked >= limit:
            break
        if not force and cache.get(f"ig_profile_cd:{client.igsid}"):
            continue
        checked += 1
        try:
            refreshed = ensure_profile(s, client, force=force)
            if refreshed:
                updated += 1
            else:
                failed += 1
        except Exception as exc:
            refreshed = False
            failed += 1
            log("warning", "profile_refresh", f"{client.igsid}: {exc!r}")
        global_error = cache.get(global_error_key)
        _record_profile_sync_result(
            client,
            success=refreshed,
            error_kind=str(global_error or "provider_error"),
        )
        if global_error:
            state = str(global_error)
            break
    return {
        "checked": checked,
        "updated": updated,
        "failed": failed,
        "state": state,
    }


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------
def allowed_sender_ids(s: InstagramBotSettings) -> set[str]:
    raw = s.allowed_senders or ""
    return {p.strip() for p in raw.replace(",", " ").replace("\n", " ").split() if p.strip()}


def _is_allowed(s: InstagramBotSettings, sender_id: str) -> bool:
    ids = allowed_sender_ids(s)
    return True if not ids else sender_id in ids


def _promote_manual_refresh_message(
    existing: InstagramBotMessage,
    *,
    current_settings: InstagramBotSettings,
    client: IgClient,
    sender_id: str,
    text: str,
    source: str,
    attachments: list[str],
    received_at: datetime | None,
    force_observed: bool = False,
) -> str:
    """Promote a matching history row when its delayed live webhook arrives."""
    if (
        source != "webhook"
        or existing.source != "manual_refresh"
        or existing.sender_id != sender_id
        or existing.client_id != client.pk
        or existing.role != InstagramBotMessage.Role.USER
        or existing.status != InstagramBotMessage.Status.DONE
        or existing.attempts
        or existing.processing_started_at is not None
        or existing.send_state
        or existing.send_started_at is not None
        or existing.send_completed_at is not None
        or not current_settings.is_enabled
        or not _is_allowed(current_settings, sender_id)
        or _client_blocked(client)
    ):
        return False
    provider_time = received_at or existing.provider_created_at
    if provider_time is None:
        return False
    if existing.provider_created_at is not None and received_at is not None:
        try:
            if abs((received_at - existing.provider_created_at).total_seconds()) > 1:
                return False
        except (TypeError, ValueError):
            return False
    if current_settings.reply_after and provider_time <= current_settings.reply_after:
        return False
    incoming_text = (text or "").strip()
    existing_text = (existing.text or "").strip()
    if incoming_text and existing_text not in {"", "(медіа)", "(зображення)"}:
        if incoming_text != existing_text:
            return ""
    update_fields = []
    if incoming_text and incoming_text != existing.text:
        existing.text = incoming_text
        update_fields.append("text")
    if attachments:
        try:
            stored = json.loads(existing.attachments or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            stored = []
        merged = list(dict.fromkeys([
            str(value).strip()
            for value in [*attachments, *(stored if isinstance(stored, list) else [])]
            if str(value).strip()
        ]))
        merged_json = json.dumps(merged)
        if merged_json != existing.attachments:
            existing.attachments = merged_json
            update_fields.append("attachments")
    if existing.provider_created_at is None:
        existing.provider_created_at = provider_time
        update_fields.append("provider_created_at")
    has_newer_conversation_event = (
        InstagramBotMessage.objects.filter(
            client_id=client.pk,
        )
        .exclude(pk=existing.pk)
        .annotate(event_at=Coalesce("provider_created_at", "created_at"))
        .filter(
            Q(event_at__gt=provider_time)
            | Q(event_at=provider_time)
        )
        .exists()
    )
    if force_observed or has_newer_conversation_event:
        if update_fields:
            existing.save(update_fields=update_fields)
        return "observed"
    existing.source = "webhook"
    existing.status = InstagramBotMessage.Status.PENDING
    existing.provider_created_at = provider_time
    existing.processed_at = None
    existing.processing_started_at = None
    existing.save(update_fields=list(dict.fromkeys([
        *update_fields,
        "source", "status", "provider_created_at", "processed_at",
        "processing_started_at",
    ])))
    return "promoted"


# ---------------------------------------------------------------------------
# Черга: постановка вхідних
# ---------------------------------------------------------------------------
def enqueue_inbound(
    s: InstagramBotSettings, *, sender_id: str, text: str, mid: str,
    source: str = "webhook", attachments: list[str] | None = None,
    received_at: datetime | None = None,
    persistence_only: bool = False,
) -> bool:
    """Кладе вхідне в чергу (pending). Повертає True, якщо додано нове."""
    text = (text or "").strip()
    sender_id = (sender_id or "").strip()
    mid = (mid or "").strip()
    attachments = attachments or []
    if not _SENDER_ID_RE.fullmatch(sender_id):
        return False
    if mid and not _valid_message_id(mid):
        return False
    if not text and not attachments:
        return False  # ні тексту, ні зображення
    if sender_id == s.ig_user_id:
        return False
    if not _is_allowed(s, sender_id):
        log("info", "skip_not_allowed", f"[{source}] {sender_id} поза білим списком")
        return False
    from management.services import bot_followups, bot_sales_classifier
    from management.services.ig_reply_boundary import pause_reply_boundary

    explicit_opt_out = bot_sales_classifier.is_explicit_opt_out(text)
    permission_transition = pause_reply_boundary() if explicit_opt_out else nullcontext()
    client = IgClient.get_or_create_for_sender(sender_id)
    # Клієнт написав знову — саме момент перевірити, чи не висить пауза від
    # менеджера, який давно пішов. Інакше повідомлення тихо стане `observed`,
    # і людина вирішить, що її ігнорують.
    try:
        maybe_release_stale_takeover(client)
    except Exception as exc:  # noqa: BLE001
        log("warning", "takeover_release", repr(exc))
    try:
        # Opt-out follows the same lock order as send/pause: permission file
        # lock first, then database rows. Normal ingress takes no global lock.
        with permission_transition, transaction.atomic():
            current_settings = InstagramBotSettings.objects.select_for_update().get(pk=s.pk)
            # Серіалізуємо ingress із hide: або вхідне повністю оброблено до
            # приховування, або приховування вже виграло і жодного side effect
            # (черги, CRM, classifier, follow-up) не буде.
            client = IgClient.objects.select_for_update().get(pk=client.pk)
            if client.hidden_at:
                log("info", "skip_hidden", f"[{source}] {sender_id}: прихований клієнт")
                return False
            existing = (
                InstagramBotMessage.objects.select_for_update().filter(mid=mid).first()
                if mid
                else None
            )
            provider_event_at = received_at or (
                existing.provider_created_at if existing is not None else None
            )
            stale_explicit_opt_out = bool(
                explicit_opt_out
                and provider_event_at
                and client.opted_in_at
                and client.opted_in_at >= provider_event_at
            )
            after_resume_cutoff = bool(
                not provider_event_at
                or not current_settings.reply_after
                or provider_event_at > current_settings.reply_after
            )
            reply_eligible = bool(
                current_settings.is_enabled
                and after_resume_cutoff
                and _is_allowed(current_settings, sender_id)
                and not _client_blocked(client)
                and not stale_explicit_opt_out
            )
            promoted = False
            observed_only = False
            if existing is not None:
                promotion_state = _promote_manual_refresh_message(
                    existing,
                    current_settings=current_settings,
                    client=client,
                    sender_id=sender_id,
                    text=text,
                    source=source,
                    attachments=attachments,
                    received_at=received_at,
                    force_observed=stale_explicit_opt_out,
                )
                if not promotion_state:
                    return False
                msg = existing
                promoted = promotion_state == "promoted"
                observed_only = promotion_state == "observed"
                reply_eligible = promoted
            else:
                try:
                    with transaction.atomic():
                        msg = InstagramBotMessage.objects.create(
                            sender_id=sender_id,
                            client=client,
                            role=InstagramBotMessage.Role.USER,
                            text=text or "(зображення)",
                            mid=mid or None,
                            status=(
                                InstagramBotMessage.Status.PENDING
                                if reply_eligible
                                else InstagramBotMessage.Status.DONE
                            ),
                            source=source,
                            attachments=json.dumps(attachments) if attachments else "",
                            provider_created_at=received_at,
                            processed_at=None if reply_eligible else timezone.now(),
                        )
                except IntegrityError:
                    existing = (
                        InstagramBotMessage.objects.select_for_update().filter(mid=mid).first()
                        if mid
                        else None
                    )
                    if existing is None:
                        raise
                    provider_event_at = received_at or existing.provider_created_at
                    stale_explicit_opt_out = bool(
                        explicit_opt_out
                        and provider_event_at
                        and client.opted_in_at
                        and client.opted_in_at >= provider_event_at
                    )
                    promotion_state = _promote_manual_refresh_message(
                        existing,
                        current_settings=current_settings,
                        client=client,
                        sender_id=sender_id,
                        text=text,
                        source=source,
                        attachments=attachments,
                        received_at=received_at,
                        force_observed=stale_explicit_opt_out,
                    )
                    if not promotion_state:
                        return False
                    msg = existing
                    promoted = promotion_state == "promoted"
                    observed_only = promotion_state == "observed"
                    reply_eligible = promoted
            if not observed_only:
                client.touch_inbound()
                from management.services.ig_funnel_analytics import (
                    record_client_step_event_in_transaction,
                )
                from management.ig_bot_models import IgFunnelStepEvent

                inbound_at = msg.provider_created_at or msg.created_at or timezone.now()
                record_client_step_event_in_transaction(
                    client,
                    event_type=IgFunnelStepEvent.Type.CONVERSATION_STARTED,
                    event_key=f"ig-inbound:{msg.pk}",
                    occurred_at=inbound_at,
                    stage=client.stage,
                    actor="customer",
                    evidence={
                        "message_id": msg.pk,
                        "mid": msg.mid or "",
                        "source": source,
                    },
                )
            # Consent is a routing barrier, not best-effort CRM enrichment. If
            # later classification fails, an explicit stop must already be
            # durable and impossible to reach Gemini or customer transport.
            if explicit_opt_out and not stale_explicit_opt_out:
                opted_out_at = timezone.now()
                client.opted_out_at = opted_out_at
                client.opt_out_message_id = msg.pk
                client.bot_paused = True
                client.reply_permission_epoch = int(client.reply_permission_epoch or 0) + 1
                client.paused_reason = "opt_out"
                client.paused_at = client.paused_at or opted_out_at
                client.save(update_fields=[
                    "opted_out_at",
                    "opt_out_message_id",
                    "bot_paused",
                    "reply_permission_epoch",
                    "paused_reason",
                    "paused_at",
                    "updated_at",
                ])
                from management.services.ig_funnel_analytics import (
                    record_drop_off_for_client_in_transaction,
                )
                record_drop_off_for_client_in_transaction(
                    client,
                    kind="opt_out",
                    reason_code="explicit_opt_out",
                    occurred_at=opted_out_at,
                    stage=client.stage,
                    actor="customer",
                    evidence={
                        "message_id": msg.pk,
                    },
                    is_recoverable=False,
                )
                if msg.status == InstagramBotMessage.Status.PENDING:
                    msg.status = InstagramBotMessage.Status.DONE
                    msg.processed_at = opted_out_at
                    msg.save(update_fields=["status", "processed_at"])
                reply_eligible = False
                try:
                    bot_followups.cancel_pending(client, reason="opt_out")
                except DatabaseError:
                    raise
                except Exception:
                    pass
            if observed_only:
                from management.services.bot_conversation_analysis import schedule_analysis

                analysis_message = (
                    InstagramBotMessage.objects.filter(client_id=client.pk)
                    .exclude(status=InstagramBotMessage.Status.FAILED)
                    .order_by("-pk")
                    .first()
                ) or msg
                schedule_analysis(client, analysis_message, trigger="webhook_inbound")
            elif persistence_only:
                from management.services.bot_conversation_analysis import schedule_analysis

                if promoted:
                    interaction_type = (
                        msg.analysis_snapshots.filter(analysis_model="rules")
                        .order_by("-id")
                        .values_list("interaction_type", flat=True)
                        .first()
                    )
                    if interaction_type in {"explicit_no_buy", "spam_abuse"}:
                        from management.services.ig_funnel_analytics import (
                            record_drop_off_for_client_in_transaction,
                        )

                        drop_kind = "spam" if interaction_type == "spam_abuse" else "explicit_refusal"
                        record_drop_off_for_client_in_transaction(
                            client,
                            kind=drop_kind,
                            reason_code=interaction_type,
                            occurred_at=msg.provider_created_at or msg.created_at,
                            stage=client.stage,
                            actor="customer",
                            evidence={
                                "message_id": msg.pk,
                            },
                            is_recoverable=False,
                        )
                    terminal_followup_reasons = {
                        "explicit_no_buy": "explicit_no_buy",
                        "opt_out": "opt_out",
                        "spam_abuse": "spam_abuse",
                        "paid_order_waiting": "already_converted",
                    }
                    if interaction_type in terminal_followup_reasons:
                        bot_followups.cancel_pending(
                            client,
                            reason=terminal_followup_reasons[interaction_type],
                        )
                    if interaction_type in {
                        "reaction_only",
                        "explicit_no_buy",
                        "opt_out",
                        "spam_abuse",
                    }:
                        msg.status = InstagramBotMessage.Status.DONE
                        msg.processed_at = timezone.now()
                        msg.save(update_fields=["status", "processed_at"])
                        reply_eligible = False
                schedule_analysis(client, msg, trigger="webhook_inbound")
            else:
                try:
                    if promoted:
                        rules_snapshot = msg.analysis_snapshots.filter(
                            analysis_model="rules"
                        ).order_by("-id").first()
                        classified = {
                            "interaction_type": getattr(rules_snapshot, "interaction_type", "")
                        }
                    else:
                        classified = bot_sales_classifier.classify_message(
                            client,
                            message=msg,
                            media_context=_recover_current_message_media(msg),
                        )
                    interaction_type = classified.get("interaction_type")
                    if interaction_type in {"explicit_no_buy", "spam_abuse"}:
                        from management.services.ig_funnel_analytics import (
                            record_drop_off_for_client_in_transaction,
                        )

                        drop_kind = "spam" if interaction_type == "spam_abuse" else "explicit_refusal"
                        record_drop_off_for_client_in_transaction(
                            client,
                            kind=drop_kind,
                            reason_code=interaction_type,
                            occurred_at=msg.provider_created_at or msg.created_at,
                            stage=client.stage,
                            actor="customer",
                            evidence={
                                "message_id": msg.pk,
                            },
                            is_recoverable=False,
                        )
                    terminal_followup_reasons = {
                        "explicit_no_buy": "explicit_no_buy",
                        "opt_out": "opt_out",
                        "spam_abuse": "spam_abuse",
                        "paid_order_waiting": "already_converted",
                    }
                    if interaction_type in terminal_followup_reasons:
                        bot_followups.cancel_pending(
                            client,
                            reason=terminal_followup_reasons[interaction_type],
                        )
                    no_reply_interactions = {
                        "reaction_only",
                        "explicit_no_buy",
                        "opt_out",
                        "spam_abuse",
                    }
                    if (
                        interaction_type in no_reply_interactions
                        and msg.status == InstagramBotMessage.Status.PENDING
                    ):
                        msg.status = InstagramBotMessage.Status.DONE
                        msg.processed_at = timezone.now()
                        msg.save(update_fields=["status", "processed_at"])
                        reply_eligible = False
                    elif reply_eligible:
                        bot_followups.schedule_after_inbound(client)
                except DatabaseError:
                    raise
                except Exception:
                    pass
    except IntegrityError:
        return False  # вже у черзі/оброблено (mid unique)
    inbound_at = timezone.now()
    InstagramBotSettings.objects.filter(pk=s.pk).update(last_inbound_at=inbound_at)
    s.last_inbound_at = inbound_at
    extra = f" (+{len(attachments)} фото)" if attachments else ""
    event = "queued" if msg.status == InstagramBotMessage.Status.PENDING else "observed"
    log("info", event, _inbound_log_detail(source, sender_id, text, extra))
    return True


# ---------------------------------------------------------------------------
# Воркер: обробка черги
# ---------------------------------------------------------------------------
def _build_history(sender_id: str) -> list[dict]:
    from management.services.ig_funnel_reset import current_message_floor

    client_id = (
        InstagramBotMessage.objects.filter(sender_id=sender_id)
        .exclude(client_id__isnull=True)
        .order_by("-id")
        .values_list("client_id", flat=True)
        .first()
    )
    floor = current_message_floor(client_id) if client_id else 1
    rows = list(
        InstagramBotMessage.objects.filter(sender_id=sender_id)
        .filter(id__gte=floor)
        .exclude(status=InstagramBotMessage.Status.FAILED)
        .annotate(event_at=Coalesce("provider_created_at", "created_at"))
        .order_by("-event_at", "-id")[:HISTORY_LIMIT]
    )
    rows.reverse()
    hist = []
    for r in rows:
        t = (r.text or "").strip()
        if t:
            if r.role == InstagramBotMessage.Role.MANAGER:
                hist.append({"role": "model", "text": "Менеджер: " + t})
            elif r.role in (InstagramBotMessage.Role.USER, InstagramBotMessage.Role.MODEL):
                hist.append({"role": r.role, "text": t})
    return hist


def _claim_next() -> InstagramBotMessage | None:
    """Atomically claim the oldest row from the freshest active conversation."""
    row = (
        InstagramBotMessage.objects.filter(
            role=InstagramBotMessage.Role.USER,
            status=InstagramBotMessage.Status.PENDING,
            client__hidden_at__isnull=True,
        )
        .annotate(
            conversation_priority_at=Coalesce(
                "client__last_message_at",
                "provider_created_at",
                "created_at",
            )
        )
        .order_by("-conversation_priority_at", "sender_id", "id")
        .first()
    )
    if not row:
        return None
    claimed_at = timezone.now()
    claimed = InstagramBotMessage.objects.filter(
        id=row.id, status=InstagramBotMessage.Status.PENDING
    ).update(
        status=InstagramBotMessage.Status.PROCESSING,
        attempts=row.attempts + 1,
        processing_started_at=claimed_at,
    )
    if claimed == 1:
        row.status = InstagramBotMessage.Status.PROCESSING
        row.attempts += 1
        row.processing_started_at = claimed_at
        return row
    return None  # гонка — забрав хтось інший


STALE_PROCESSING_SECONDS = 300  # повідомлення «зависло» у processing довше — реанімуємо


def reclaim_stale_processing(max_age_seconds: int = STALE_PROCESSING_SECONDS) -> int:
    """Повертає в чергу повідомлення, що «зависли» у processing довше за поріг.

    Причини зависання: демона вбили під час обробки (status лишився processing і
    рядок ніколи не переклеймиться), або виклик Gemini тривав надто довго. Без
    цього бот може заморозитись назовсім. attempts<MAX → знову pending, інакше
    failed. Повертає к-сть повернутих у чергу."""
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(seconds=max_age_seconds)
    stale = list(
        InstagramBotMessage.objects.select_related("client").filter(
            role=InstagramBotMessage.Role.USER,
            status=InstagramBotMessage.Status.PROCESSING,
            processing_started_at__lt=cutoff,
        ).order_by("id")[:50]
    )
    requeued = 0
    for row in stale:
        # Короткі locks тільки для рішення. Gemini/Meta I/O тут немає.
        # Порядок lock-ів збігається з Hide та lease: спершу клієнт, потім row.
        with transaction.atomic():
            client = None
            if row.client_id:
                client = IgClient.objects.select_for_update().filter(pk=row.client_id).first()
                if client and client_automation_busy(client):
                    continue
            locked = InstagramBotMessage.objects.select_for_update().filter(
                id=row.id,
                role=InstagramBotMessage.Role.USER,
                status=InstagramBotMessage.Status.PROCESSING,
                processing_started_at__lt=cutoff,
            ).first()
            if not locked:
                continue
            if locked.send_state in {"sending", "sent", "unknown"}:
                locked.status = InstagramBotMessage.Status.FAILED
                locked.send_state = "unknown"
                locked.processed_at = timezone.now()
                locked.save(update_fields=["status", "send_state", "processed_at"])
                log(
                    "error",
                    "send_unknown",
                    f"{locked.sender_id}: stale row crossed Meta send boundary; automatic retry disabled",
                )
                continue
            if locked.attempts >= MAX_ATTEMPTS:
                locked.status = InstagramBotMessage.Status.FAILED
                locked.processed_at = timezone.now()
                locked.save(update_fields=["status", "processed_at"])
                log("error", "stale_failed", f"{locked.sender_id}: завис у processing, спроби вичерпано")
            else:
                locked.status = InstagramBotMessage.Status.PENDING
                locked.processing_started_at = None
                locked.save(update_fields=["status", "processing_started_at"])
                log("warning", "stale_requeue", f"{locked.sender_id}: завис у processing → повертаю в чергу")
                requeued += 1
    return requeued


def _own_processing_claim(row: InstagramBotMessage):
    """Return a conditional update queryset for exactly this worker claim."""
    claim = InstagramBotMessage.objects.filter(
        pk=row.pk,
        status=InstagramBotMessage.Status.PROCESSING,
    )
    if row.processing_started_at:
        return claim.filter(processing_started_at=row.processing_started_at)
    return claim.filter(processing_started_at__isnull=True)


def _skip_blocked_row(row: InstagramBotMessage, client: IgClient) -> bool:
    processed_at = timezone.now()
    if _own_processing_claim(row).update(
        status=InstagramBotMessage.Status.DONE,
        processed_at=processed_at,
    ):
        row.status = InstagramBotMessage.Status.DONE
        row.processed_at = processed_at
        log("info", "paused_skip", f"{row.sender_id}: на паузі ({client.paused_reason or 'manual'})")
    return False


def _skip_observed_row(row: InstagramBotMessage, *, reason: str) -> bool:
    processed_at = timezone.now()
    if _own_processing_claim(row).update(
        status=InstagramBotMessage.Status.DONE,
        processed_at=processed_at,
    ):
        row.status = InstagramBotMessage.Status.DONE
        row.processed_at = processed_at
        log("info", "observed_skip", f"{row.sender_id}: {reason}")
    return False


def client_automation_busy(client: IgClient | None, *, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    return bool(
        client
        and client.automation_lease_token
        and client.automation_lease_until
        and client.automation_lease_until > now
    )


def _lease_client_automation(
    client_id: int | None, *, token: str = ""
) -> tuple[IgClient | None, str, str]:
    """Atomically acquire or renew the short lease shared by all bot sends.

    Returns ``(client, token, state)`` where state is one of ``acquired``,
    ``renewed``, ``blocked``, ``busy``, ``token_lost`` or ``missing``. The
    transaction contains only the state transition, never external I/O.
    """
    if not client_id:
        return None, "", "missing"
    with transaction.atomic():
        client = IgClient.objects.select_for_update().filter(pk=client_id).first()
        if not client:
            return None, "", "missing"
        if _client_blocked(client):
            return client, "", "blocked"
        now = timezone.now()
        if token:
            if client.automation_lease_token != token:
                return client, "", "token_lost"
            client.automation_lease_until = now + AUTOMATION_LEASE_TTL
            client.save(update_fields=["automation_lease_until", "updated_at"])
            return client, token, "renewed"
        if client_automation_busy(client, now=now):
            return client, "", "busy"
        lease_token = secrets.token_hex(16)
        client.automation_lease_token = lease_token
        client.automation_lease_until = now + AUTOMATION_LEASE_TTL
        client.save(update_fields=[
            "automation_lease_token", "automation_lease_until", "updated_at",
        ])
        return client, lease_token, "acquired"


def acquire_client_automation_lease(client_id: int | None) -> tuple[IgClient | None, str]:
    """Lease one client for a bot send; returns no token when it is unavailable."""
    client, token, state = _lease_client_automation(client_id)
    return (client, token) if state == "acquired" else (None, "")


def renew_client_automation_lease(client_id: int | None, token: str) -> IgClient | None:
    """Renew a held client lease immediately before a send boundary."""
    client, _token, state = _lease_client_automation(client_id, token=token)
    return client if state == "renewed" else None


def _requeue_for_active_lease(row: InstagramBotMessage) -> bool:
    if _own_processing_claim(row).update(
        status=InstagramBotMessage.Status.PENDING,
        processed_at=None,
        processing_started_at=None,
    ):
        row.status = InstagramBotMessage.Status.PENDING
        row.processed_at = None
        row.processing_started_at = None
        log("info", "lease_busy", f"{row.sender_id}: інший worker ще обробляє клієнта")
    else:
        log("info", "claim_lost", f"{row.sender_id}: row уже належить іншому worker-у")
    return False


def _acquire_client_automation_lease(
    row: InstagramBotMessage,
) -> tuple[IgClient | None, str]:
    if not row.client_id:
        return None, ""
    client, token, state = _lease_client_automation(row.client_id)
    if state == "acquired":
        # Reclaim may have won just before we acquired the client lease. Do not
        # let this stale Python object send after its DB row returned to pending.
        if not _own_processing_claim(row).exists():
            release_client_automation_lease(client.id, token)
            log("info", "claim_lost", f"{row.sender_id}: row вже повернуто в чергу")
            return None, ""
        row.client = client  # не використовуємо застарілий relation-cache після claim.
        return client, token
    if state == "blocked" and client:
        _skip_blocked_row(row, client)
    elif state in {"busy", "token_lost"}:
        _requeue_for_active_lease(row)
    else:
        processed_at = timezone.now()
        if _own_processing_claim(row).update(
            status=InstagramBotMessage.Status.DONE,
            processed_at=processed_at,
        ):
            row.status = InstagramBotMessage.Status.DONE
            row.processed_at = processed_at
            log("warning", "client_missing", f"{row.sender_id}: картку клієнта не знайдено")
    return None, ""


def _renew_client_automation_lease(row: InstagramBotMessage, token: str) -> bool:
    """Refresh a short lease before each automation boundary, never over I/O."""
    if not row.client_id:
        return True
    client, _token, state = _lease_client_automation(row.client_id, token=token)
    if state == "renewed":
        row.client = client
        return True
    if state == "blocked" and client:
        return _skip_blocked_row(row, client)
    return _requeue_for_active_lease(row)


def _catalog_media_selection_for_control(control: dict, client):
    """Resolve an explicit SHOW_PRODUCTS control into trusted catalog media."""
    if not isinstance(control, dict) or "show_products" not in control:
        return None
    from management.services.ig_catalog_media import parse_product_ids, select_catalog_media

    raw = control.get("show_products")
    product_ids = parse_product_ids(raw)
    if product_ids is None and raw is True:
        current_id = getattr(client, "current_product_id", None)
        product_ids = (int(current_id),) if current_id else ()
    if not product_ids:
        return select_catalog_media(())
    return select_catalog_media(product_ids)


def release_client_automation_lease(client_id: int | None, token: str) -> None:
    if not client_id or not token:
        return
    IgClient.objects.filter(pk=client_id, automation_lease_token=token).update(
        automation_lease_token="", automation_lease_until=None
    )


def _release_client_automation_lease(client_id: int | None, token: str) -> None:
    """Backward-compatible internal alias for the inbound worker."""
    release_client_automation_lease(client_id, token)


def _process_one(s: InstagramBotSettings, row: InstagramBotMessage) -> bool:
    client, lease_token = _acquire_client_automation_lease(row)
    if row.client_id and not client:
        return False
    try:
        return _process_one_unlocked(s, row, lease_token)
    finally:
        _release_client_automation_lease(row.client_id, lease_token)


def _process_one_unlocked(s: InstagramBotSettings, row: InstagramBotMessage, lease_token: str = "") -> bool:
    from management.services.ig_reply_boundary import reply_execution_boundary

    with reply_execution_boundary(s.pk, row.client_id) as permission:
        if not permission:
            return _skip_observed_row(row, reason="reply_paused")
        return _process_one_inside_reply_boundary(s, row, lease_token, permission)


def _process_one_inside_reply_boundary(
    s: InstagramBotSettings,
    row: InstagramBotMessage,
    lease_token: str = "",
    permission=None,
) -> bool:
    fallback_manager_handoff = False
    used_ai_failure_fallback = False
    outage_recovery_required = False
    outage_recovery_job = None
    gemini_failure: dict = {}
    if not InstagramBotSettings.objects.filter(pk=s.pk, is_enabled=True).exists():
        return _skip_observed_row(row, reason="global_reply_paused")
    if row.client_id:
        try:
            from management.services import bot_followups, bot_sales_classifier

            classified = bot_sales_classifier.ensure_rule_classification(
                row.client,
                row,
                media_context=_recover_current_message_media(row),
            )
            if classified is not None:
                interaction_type = classified.get("interaction_type")
                terminal_followup_reasons = {
                    "explicit_no_buy": "explicit_no_buy",
                    "opt_out": "opt_out",
                    "spam_abuse": "spam_abuse",
                    "paid_order_waiting": "already_converted",
                }
                if interaction_type in terminal_followup_reasons:
                    bot_followups.cancel_pending(
                        row.client,
                        reason=terminal_followup_reasons[interaction_type],
                    )
                if interaction_type in {
                    "reaction_only",
                    "explicit_no_buy",
                    "opt_out",
                    "spam_abuse",
                }:
                    processed_at = timezone.now()
                    consumed = _own_processing_claim(row).update(
                        status=InstagramBotMessage.Status.DONE,
                        processed_at=processed_at,
                    )
                    if consumed:
                        row.status = InstagramBotMessage.Status.DONE
                        row.processed_at = processed_at
                        log(
                            "info",
                            "classified_skip",
                            f"{row.sender_id}: {interaction_type}",
                        )
                    return bool(consumed)
                bot_followups.schedule_after_inbound(row.client)
        except DatabaseError:
            raise
        except Exception as exc:
            log("warning", "deferred_classification", repr(exc))
    if not row.attachments:
        try:
            from management.services.bot_sales_classifier import is_reaction_only

            if is_reaction_only(row.text):
                processed_at = timezone.now()
                updated = _own_processing_claim(row).update(
                    status=InstagramBotMessage.Status.DONE,
                    processed_at=processed_at,
                )
                if updated:
                    row.status = InstagramBotMessage.Status.DONE
                    row.processed_at = processed_at
                    log("info", "reaction_observed", f"{row.sender_id}: реакція без auto-reply")
                    return True
                return False
        except Exception:
            pass
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
        if not _renew_client_automation_lease(row, lease_token):
            return False
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
            if not _renew_client_automation_lease(row, lease_token):
                return False
            history = _build_history(row.sender_id)
            if not history:
                history = [{"role": "user", "text": row.text}]
            # Recover raw ig_post/story media as well as normalized attachments.
            # This keeps active and paused/manager-led conversations on the
            # same evidence path; receipts are passed to Gemini for context but
            # are never sent to catalog matching.
            recovered_media = _recover_current_message_media(row)
            media_recovery_failed = recovered_media is None
            media = recovered_media or []
            images = _collect_media_images(media)
            if not images and not media_recovery_failed:
                images = _collect_images(row.attachments)
            if not _renew_client_automation_lease(row, lease_token):
                return False
            # Якщо є фото/пост — матчимо з каталогом і даємо моделі підказку.
            match_hint = None
            product_media = _catalog_match_media(media)
            product_images = _collect_media_images(product_media) if media else (
                [] if media_recovery_failed else images
            )
            if product_images and _match_allowed(row.sender_id):
                try:
                    from management.services import bot_vision

                    match = bot_vision.match(product_images)
                    if not _renew_client_automation_lease(row, lease_token):
                        return False
                    match_hint = _match_hint_text(match)
                    # Впевнений матчинг → закріплюємо товар за клієнтом.
                    if row.client_id and _should_pin_product_media(media):
                        _maybe_pin_from_match(row.client, match)
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
                memory_note=mem_note, context_note=ctx_note, client=row.client if row.client_id else None,
                media_hint=_media_context_hint(media),
                turn_note=customer_turn_note(
                    row.client if row.client_id else None, row.text
                ),
                failure_context=gemini_failure,
            )
    else:
        if (row.text or "").strip() != s.trigger_text:
            row.status = InstagramBotMessage.Status.DONE
            row.processed_at = timezone.now()
            row.save(update_fields=["status", "processed_at"])
            log("info", "ignored", f"{row.sender_id}: не тригер")
            return False
        reply = s.reply_text

    if not _renew_client_automation_lease(row, lease_token):
        return False

    if not InstagramBotSettings.objects.filter(pk=s.pk, is_enabled=True).exists():
        return _skip_observed_row(row, reason="global_reply_paused_before_send")

    # Керуючі теги моделі: [MANAGER] (ескалація), [STAGE:x] (воронка) тощо.
    control = {}
    if reply:
        reply, control = _extract_control(reply)
    needs_manager = bool(control.get("manager"))
    if reply and row.client_id:
        checked_reply, control, price_quote = _extract_authoritative_price_claim(
            row.client,
            reply,
            control,
        )
        if checked_reply is None:
            # Never send a customer-facing amount that could not be tied to the
            # selected catalog configuration.  Keep the message in a safe
            # holding state and let the normal manager escalation path handle it.
            needs_manager = True
            control["manager"] = True
            log("warning", "price_claim_gate", f"{row.sender_id}: unverified exact price claim")
            reply = _paylink_fallback(row.client)
        else:
            reply = checked_reply
            if price_quote is not None:
                control["_funnel_price_quote"] = price_quote
        if control.get("options") and _control_option_values(control) is None:
            needs_manager = True
            control["manager"] = True
            log("warning", "option_control_gate", f"{row.sender_id}: malformed option controls")
            reply = _paylink_fallback(row.client)

    # Закріплюємо товар, якщо модель явно вказала [PRODUCT:id] — щоб подальша
    # оплата формувалась детерміновано саме на нього.
    # Тег [PRODUCT:id] — це твердження моделі про те, який товар зараз
    # обговорюється, і воно достатнє саме по собі. Раніше пін вимагав ще й
    # «слова про покупку» або відповідної стадії, тому в переписці, де клієнт
    # передумав і назвав інший товар, `current_product_id` лишався старим —
    # звідси «не змінював товар назад». Опублікованість товару перевіряє
    # `bot_orders.pin_product`, тому вигаданий id тут не закріпиться.
    if reply and row.client_id and _control_product_id(control):
        _pin_control_product(
            row.client,
            _control_product_id(control),
            switch_reason=_switch_reason_for_turn(
                row.client, row.text, _control_product_id(control)
            ),
        )

    # Фіксуємо все, що модель дізналась цим ходом ([FIT:...], [SIZE:...],
    # [QTY:...]), навіть якщо посилання ще не створюється. Інакше уточнення
    # фасону губилось, і наступного ходу його знову бракувало — це і був
    # механізм нескінченного «підкажіть фасон».
    if reply and row.client_id:
        try:
            saved = persist_control_selection(
                row.client,
                control,
                source_message_id=row.pk,
            )
            if saved:
                log("info", "selection_saved", f"{row.sender_id}: {', '.join(saved)}")
        except Exception as exc:
            log("warning", "selection_saved", repr(exc))
        price_quote = _validated_price_quote(row.client, control)
        if price_quote is not None:
            control["_funnel_price_quote"] = price_quote
        elif "price_quoted" in control:
            log("warning", "price_quote_gate", f"{row.sender_id}: invalid exact price marker")
        # Якщо потрібного розміру немає, бот каже клієнту, що уточнить у менеджера.
        # Значить менеджер мусить справді про це дізнатись — інакше обіцянка
        # порожня, а клієнт чекає відповіді, якої ніхто не готує.
        try:
            notify_size_gap(row.client)
        except Exception as exc:
            log("warning", "size_gap_notify", repr(exc))

    # [SPAM] — модель розпізнала спам/провокацію: рахуємо страйк (на 3-й — пауза).
    if reply and row.client_id and control.get("spam"):
        try:
            _register_spam(row.client)
        except Exception:
            pass

    # Формування посилання на оплату (guard «обіцяв → надішли або не обіцяй»):
    # finalize_paylink гарантує, що клієнт НЕ лишиться з обіцянкою без лінку —
    # на успіх додає реальний URL (вирізаючи вигаданий моделлю), на невдачу
    # прибирає висяче обіцяння й кличе менеджера.
    if reply and row.client_id:
        reply = finalize_paylink(
            reply,
            control,
            row.client,
            row.sender_id,
            trigger_text=row.text,
        )

    # Persisted invoice identity is the payment-delivery source of truth.  The
    # provider may return a generic pageUrl that does not contain monobank/mbnk,
    # so hostname heuristics alone are not sufficient here.
    payment_deal = _invoice_deal_for_reply(row.client, reply) if row.client_id else None

    if not reply and s.ai_enabled:
        if _defer_for_gemini_cooldown(row, s):
            return False
        try:
            from management.services.bot_reply_fallback import (
                build_ai_failure_fallback,
                is_generic_provider_outage,
            )

            provider_outage = gemini_failure.get("kind") == "provider_outage"
            reply, fallback_manager_handoff = build_ai_failure_fallback(
                row,
                provider_outage=provider_outage,
            )
            if reply:
                used_ai_failure_fallback = True
                outage_recovery_required = bool(
                    row.client_id and is_generic_provider_outage(
                        row,
                        failure_kind=gemini_failure.get("kind", ""),
                    )
                )
                log(
                    "warning",
                    "gemini_fallback",
                    f"{row.sender_id}: deterministic fallback after provider failure",
                )
        except Exception as exc:
            log("error", "gemini_fallback", repr(exc))

    if not reply:
        # невдача генерації — ретрай або failed
        if row.attempts >= MAX_ATTEMPTS:
            row.status = InstagramBotMessage.Status.FAILED
            row.save(update_fields=["status"])
            log("error", "give_up", f"{row.sender_id}: не вдалося згенерувати після {row.attempts} спроб")
            from management.services.ig_alerts import alert_dedupe_key

            notify_manager(
                f"⚠️ IG бот не зміг згенерувати відповідь клієнту {row.sender_id} "
                f"(3 спроби). Питання: {row.text[:300]}",
                dedupe_key=alert_dedupe_key(
                    "generation_failed", client_id=row.client_id,
                    entity_id=row.pk, window_minutes=0,
                ),
                event_type="generation_failed",
                client=row.client if row.client_id else None,
            )
        else:
            row.status = InstagramBotMessage.Status.PENDING
            row.processing_started_at = None
            row.save(update_fields=["status", "processing_started_at"])
        return False

    if outage_recovery_required:
        try:
            from management.services.ig_ai_reply_recovery import schedule_recovery

            # The holding response promises an automatic follow-up. Persist its
            # recovery intent before the non-idempotent Meta send boundary.
            outage_recovery_job = schedule_recovery(row, activate=False)
        except Exception as exc:
            row.status = InstagramBotMessage.Status.FAILED
            row.send_state = "failed"
            row.processed_at = timezone.now()
            row.save(update_fields=["status", "send_state", "processed_at"])
            log("error", "recovery_schedule", repr(exc))
            notify_manager(
                f"⚠️ IG: не вдалося створити recovery для повідомлення #{row.pk}; "
                "відповідь клієнту не надсилалась, потрібна ручна перевірка.",
                dedupe_key=f"ig-ai-recovery-schedule:{row.pk}",
                event_type="ai_reply_recovery_schedule_failed",
                client=row.client if row.client_id else None,
            )
            return False

    from management.services.ig_reply_boundary import customer_send_boundary

    # Product discovery uses a separate media transport. A provider partial or
    # unknown result must never erase the useful text reply or be replayed
    # blindly; the durable message remains visible for operator reconciliation.
    catalog_media_selection = _catalog_media_selection_for_control(control, row.client)
    if catalog_media_selection and not control.get("paylink"):
        if not control.get("catalog_link"):
            reply = _strip_customer_urls(reply)
        try:
            from management.services.ig_catalog_media import (
                CatalogMediaDeliveryState,
                send_catalog_media,
            )

            catalog_media_delivery = send_catalog_media(
                s,
                row.sender_id,
                catalog_media_selection,
                permission_boundary_factory=lambda: customer_send_boundary(
                    s.pk, row.client_id, permission
                ),
            )
            if catalog_media_delivery.state in {
                CatalogMediaDeliveryState.PARTIAL,
                CatalogMediaDeliveryState.AMBIGUOUS,
                CatalogMediaDeliveryState.FAILED,
            }:
                log(
                    "warning",
                    "catalog_media_delivery",
                    f"{row.sender_id}: {catalog_media_delivery.state} "
                    f"{catalog_media_delivery.error}",
                )
            # Фіксуємо порядок показаного одразу після відправки: далі клієнт
            # може сказати «давай першу», і це має бути фактом, а не догадкою.
            if row.client_id:
                record_shown_products(
                    row.client,
                    row.sender_id,
                    catalog_media_selection,
                    catalog_media_delivery,
                )
        except Exception as exc:
            log("warning", "catalog_media_delivery", repr(exc))

    # Останнє продовження lease прямо перед Meta Send API. Поки send триває,
    # hide не поверне помилковий success: UI отримає чесний retryable-конфлікт.
    if not _renew_client_automation_lease(row, lease_token):
        return False
    # The global lock is held only across the claim/revalidation.  Each Meta
    # chunk below takes its own short send boundary, so slow generation and
    # unrelated chunks never block a stop for the whole response.
    with customer_send_boundary(s.pk, row.client_id, permission) as send_allowed:
        if not send_allowed:
            return _skip_observed_row(row, reason="permission_epoch_changed")
        send_started_at = timezone.now()
        if not _own_processing_claim(row).update(
            send_state="sending", send_started_at=send_started_at, send_completed_at=None,
        ):
            log("warning", "claim_lost", f"{row.sender_id}: send claim lost before Meta request")
            return False
        row.send_state = "sending"
        row.send_started_at = send_started_at
        row.send_completed_at = None
    delivery = send_text(
        s,
        row.sender_id,
        reply,
        permission_boundary_factory=lambda: customer_send_boundary(
            s.pk, row.client_id, permission
        ),
        # A normal product/catalog answer remains useful without a URL. A
        # generated payment link does not: silently stripping it would make a
        # false promise, so payment delivery stays fail-closed for a manager.
        allow_url_fallback=_allows_linkless_fallback(reply, control, row.client),
        # A blocked payment link produces its own manager task with the exact
        # invoice.  It is the one actionable alert for that failed send, so do
        # not also emit the generic link-circuit Telegram alert.
        alert_link_restriction=not bool(
            payment_deal is not None or _PAY_URL_RE.search(reply)
        ),
        return_receipt=True,
    )
    ok, kind, hint, provider_message_id, receipt_present = _delivery_receipt(delivery)
    if ok and receipt_present and not provider_message_id:
        # The Send API may have accepted the request before returning a malformed
        # success body. Its delivery is therefore unknown and must not be replayed.
        ok = False
        kind = "unknown"
        hint = "provider_message_id_missing"
    if kind == "cancelled":
        if outage_recovery_job is not None:
            try:
                from management.services.ig_ai_reply_recovery import terminalize_prepared_recovery

                terminalize_prepared_recovery(
                    outage_recovery_job,
                    reason="holding_send_cancelled_before_receipt",
                    ambiguous=False,
                )
            except Exception as exc:
                log("error", "recovery_terminalize", repr(exc))
        cancelled_at = timezone.now()
        if _own_processing_claim(row).update(
            send_state="cancelled",
            processed_at=cancelled_at,
        ):
            row.send_state = "cancelled"
            row.processed_at = cancelled_at
        return _skip_observed_row(row, reason="permission_epoch_changed")
    if not ok:
        if outage_recovery_job is not None:
            try:
                from management.services.ig_ai_reply_recovery import terminalize_prepared_recovery

                terminalize_prepared_recovery(
                    outage_recovery_job,
                    reason=f"holding_send_{kind}:{hint}",
                    ambiguous=kind == "unknown",
                )
            except Exception as exc:
                log("error", "recovery_terminalize", repr(exc))
        if kind == "permanent":
            # Перманентна помилка (напр. #200 немає Advanced Access) — ретраї
            # безглузді. Падаємо одразу з чіткою причиною.
            row.status = InstagramBotMessage.Status.FAILED
            row.send_state = "failed"
            row.processed_at = timezone.now()
            row.save(update_fields=["status", "send_state", "processed_at"])
            log("error", "send_blocked", f"{row.sender_id}: {hint}")
            payment_review_queued = False
            if row.client_id and (payment_deal is not None or _PAY_URL_RE.search(reply)):
                try:
                    payment_review_queued = _queue_payment_link_delivery_review(
                        row.client,
                        reply,
                        hint,
                        deal=payment_deal,
                    )
                except Exception as exc:
                    log("error", "payment_link_delivery_review", repr(exc))
            # Системну причину (одна на всіх) не спамимо — алерт раз на годину.
            # Для платіжного повідомлення окреме завдання вже є actionable
            # алертом; другий загальний текст про ту саму невдачу лише спамить.
            if not payment_review_queued and not cache.get("ig_bot_perm_alert"):
                cache.set("ig_bot_perm_alert", 1, 3600)
                graph_subcode = (
                    ADVANCED_ACCESS_SUBCODE if _is_advanced_access_hint(hint) else 0
                )
                from management.services.ig_alerts import alert_dedupe_key

                notify_manager(
                    _permanent_send_alert_text(hint, graph_subcode=graph_subcode),
                    dedupe_key=alert_dedupe_key(
                        "permanent_send_blocked", client_id=row.client_id,
                        entity_id=row.pk, window_minutes=60,
                    ),
                    event_type="permanent_send_blocked",
                    client=row.client if row.client_id else None,
                )
        elif kind == "unknown":
            # Never replay a request whose provider result is ambiguous.
            row.status = InstagramBotMessage.Status.FAILED
            row.send_state = "unknown"
            row.processed_at = timezone.now()
            row.save(update_fields=["status", "send_state", "processed_at"])
            log("error", "send_unknown", f"{row.sender_id}: {hint}; automatic retry disabled")
            from management.services.ig_alerts import alert_dedupe_key

            notify_manager(
                f"⚠️ IG бот: результат доставки клієнту {row.sender_id} не підтверджено. "
                "Автоматичний повтор вимкнено, перевірте Meta Inbox.",
                dedupe_key=alert_dedupe_key(
                    "delivery_unknown", client_id=row.client_id, entity_id=row.pk,
                ),
                event_type="delivery_unknown",
                client=row.client if row.client_id else None,
            )
        elif row.attempts >= MAX_ATTEMPTS:
            row.status = InstagramBotMessage.Status.FAILED
            row.send_state = "failed"
            row.processed_at = timezone.now()
            row.save(update_fields=["status", "send_state", "processed_at"])
            log("error", "give_up", f"{row.sender_id}: не вдалося відправити після {row.attempts} спроб ({hint})")
            from management.services.ig_alerts import alert_dedupe_key

            notify_manager(
                f"⚠️ IG бот не зміг відповісти клієнту {row.sender_id} після {row.attempts} спроб. "
                f"Причина: {hint}. Питання: {row.text[:300]}",
                dedupe_key=alert_dedupe_key(
                    "send_gave_up", client_id=row.client_id, entity_id=row.pk,
                ),
                event_type="send_gave_up",
                client=row.client if row.client_id else None,
            )
        elif kind == "retryable":
            _activate_send_rate_limit_backoff(s)
            row.status = InstagramBotMessage.Status.PENDING
            row.processing_started_at = None
            row.save(update_fields=["status", "processing_started_at"])
        else:
            row.status = InstagramBotMessage.Status.PENDING
            row.processing_started_at = None
            row.save(update_fields=["status", "processing_started_at"])
        return False

    if kind == "degraded_link_restriction" and hint:
        reply = hint

    # успіх: фіксуємо відповідь у локальній історії
    processed_at = timezone.now()
    claimed = _own_processing_claim(row).update(
        status=InstagramBotMessage.Status.DONE,
        send_state="sent",
        send_completed_at=processed_at,
        processed_at=processed_at,
    )
    if not claimed:
        # The provider already received the message; never run the row again.
        log("warning", "claim_lost_after_send", f"{row.sender_id}: Meta send succeeded")
        return True
    row.status = InstagramBotMessage.Status.DONE
    row.send_state = "sent"
    row.send_completed_at = processed_at
    row.processed_at = processed_at
    recovery_activation_error = ""
    with transaction.atomic():
        reply_message = InstagramBotMessage.objects.create(
            sender_id=row.sender_id,
            client=row.client,
            role=InstagramBotMessage.Role.MODEL,
            text=reply,
            status=InstagramBotMessage.Status.DONE,
            source=row.source,
            provider_message_id=provider_message_id[:255],
            processed_at=processed_at,
        )
        if row.client_id:
            from management.models import IgClient
            from management.services.ig_funnel_analytics import (
                record_first_bot_reply_in_transaction,
            )

            locked_client = IgClient.objects.select_for_update().get(pk=row.client_id)
            locked_client.last_bot_reply_at = processed_at
            locked_client.save(update_fields=["last_bot_reply_at", "updated_at"])
            record_first_bot_reply_in_transaction(
                locked_client,
                occurred_at=processed_at,
                reply_message_id=reply_message.pk,
                source_message_id=row.pk,
            )
            price_quote = control.get("_funnel_price_quote")
            if isinstance(price_quote, dict):
                from management.models import IgFunnelStepEvent
                from management.services.ig_funnel_analytics import (
                    record_client_step_event_in_transaction,
                )

                record_client_step_event_in_transaction(
                    locked_client,
                    event_type=IgFunnelStepEvent.Type.PRICE_QUOTED,
                    event_key=f"ig-price-quoted:{reply_message.pk}",
                    occurred_at=processed_at,
                    stage=locked_client.stage,
                    actor="bot",
                    evidence={
                        **price_quote,
                        "reply_message_id": reply_message.pk,
                        "source_message_id": row.pk,
                    },
                )
            proposal_pk = control.get("_funnel_proposal_pk")
            proposal_id = control.get("_funnel_proposal_id")
            if proposal_pk or proposal_id:
                from management.models import IgCheckoutProposal, IgFunnelStepEvent
                from management.services.ig_funnel_analytics import (
                    record_episode_step_event_in_transaction,
                )

                proposal_lookup = {"pk": proposal_pk} if proposal_pk else {
                    "public_id": proposal_id
                }
                proposal = (
                    IgCheckoutProposal.objects.select_related("commercial_episode")
                    .filter(client_id=locked_client.pk, **proposal_lookup)
                    .first()
                )
                if proposal is not None:
                    record_episode_step_event_in_transaction(
                        proposal.commercial_episode,
                        event_type=IgFunnelStepEvent.Type.PAYLINK_ISSUED,
                        event_key=f"ig-paylink-issued:{proposal.pk}",
                        occurred_at=processed_at,
                        stage=IgClient.Stage.CHECKOUT,
                        actor="bot",
                        evidence={
                            "proposal_id": proposal.pk,
                            "proposal_public_id": str(proposal.public_id),
                            "reply_message_id": reply_message.pk,
                            "source_message_id": row.pk,
                            "quoted_total": str(proposal.quoted_total),
                        },
                    )
        if outage_recovery_job is not None:
            try:
                from management.services.ig_ai_reply_recovery import schedule_recovery

                # The holding receipt and its activation commit with the
                # history row. A worker crash afterwards can additionally
                # reconcile a prepared job from this confirmed receipt.
                schedule_recovery(row, holding_message=reply_message)
            except Exception as exc:
                recovery_activation_error = repr(exc)
    if recovery_activation_error:
        # The holding response has already been delivered. Do not invent a
        # manager handoff, but retain an explicit operational signal.
        log("error", "recovery_schedule", recovery_activation_error)
        notify_manager(
            f"⚠️ IG: не вдалося створити recovery для повідомлення #{row.pk}; "
            "потрібна ручна перевірка.",
            dedupe_key=f"ig-ai-recovery-schedule:{row.pk}",
            event_type="ai_reply_recovery_schedule_failed",
            client=row.client if row.client_id else None,
        )
    if row.client_id:
        try:
            from management.services.ig_objections import record_reply_attempt

            record_reply_attempt(row.client, reply_message, control, reply)
        except Exception as exc:
            # Objection analytics is secondary to the durable provider receipt.
            log("warning", "objection_attempt", repr(exc))
    s.replies_count = (s.replies_count or 0) + 1
    s.last_reply_at = timezone.now()
    s.save(update_fields=["replies_count", "last_reply_at"])
    log("success", "reply_sent", f"→ {row.sender_id}: {reply[:240]}")
    # Періодично оновлюємо стислу пам'ять про клієнта.
    if row.client_id:
        post_send_client = renew_client_automation_lease(row.client_id, lease_token)
        if not post_send_client:
            return True
        row.client = post_send_client
        try:
            from management.services.bot_memory import maybe_update_memory

            maybe_update_memory(row.client)
        except Exception:
            pass
        post_send_client = renew_client_automation_lease(row.client_id, lease_token)
        if not post_send_client:
            return True
        row.client = post_send_client
        # Просування воронки за тегом [STAGE:x].
        _apply_stage(row.client, control.get("stage"))
        try:
            from management.services import bot_followups

            row.client.refresh_from_db()
            if fallback_manager_handoff:
                _apply_stage(row.client, IgClient.Stage.LEAD_TO_MANAGER)
                bot_followups.cancel_pending(
                    row.client,
                    reason="ai_fallback_manager_handoff",
                )
            elif used_ai_failure_fallback:
                bot_followups.cancel_pending(
                    row.client,
                    reason="ai_fallback_safe_reply",
                )
            else:
                # IMP-048: без `deal=` платёжная ветка добивки была недостижима,
                # и выбор вида задачи зависел от `set_stage`, обёрнутого в
                # try/except, — то есть от того, записалась ли стадия.
                current_deal = None
                try:
                    from management.models import IgDeal

                    current_deal = (
                        IgDeal.objects.filter(client=row.client)
                        .exclude(status=IgDeal.Status.CANCELLED)
                        .order_by("-id")
                        .first()
                    )
                except Exception:
                    current_deal = None
                bot_followups.schedule_after_bot_reply(
                    row.client,
                    reply=reply,
                    control=control,
                    deal=current_deal,
                )
        except Exception as exc:
            log("warning", "followup_schedule", repr(exc))
        # [ORDER] або safety-net: оплачений клієнт надіслав контактні дані, а
        # модель не виставила тег — все одно намагаємось зібрати дані й створити заказ.
        from management.services.bot_payment_truth import client_has_verified_payment

        if control.get("order") or (
            _looks_like_contact_info(row.text)
            and client_has_verified_payment(row.client)
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
        # Найчастіший алерт у системі — і донедавна найменш корисний: у ньому був
        # лише IGSID, тому менеджер шукав клієнта руками, хоча `client_id` уже
        # відомий. Тепер ім'я, посилання на картку і дедуп із вікном: та сама
        # ескалація по тому самому клієнту не повторюється щогодини, але через
        # годину повернеться, якщо питання досі відкрите.
        from management.services.ig_alerts import (
            alert_dedupe_key,
            client_admin_url,
            format_alert,
        )

        who = ""
        if row.client_id:
            who = row.client.username or row.client.display_name or ""
        notify_manager(
            format_alert(
                "🔔 IG Direct — клієнту потрібен менеджер.",
                lines=[
                    f"Клієнт: {who or row.sender_id}",
                    f"Питання: {row.text[:400]}",
                ],
                url=client_admin_url(row.client_id),
                url_label="Картка:",
            ),
            dedupe_key=alert_dedupe_key(
                "escalation", client_id=row.client_id, window_minutes=60,
                text=row.text or "",
            ),
            event_type="escalation",
            client=row.client if row.client_id else None,
        )
        log("warning", "escalation", f"{row.sender_id}: викликано менеджера")
    return True


def process_pending(s: InstagramBotSettings | None = None, max_items: int = 15) -> int:
    s = s or InstagramBotSettings.load()
    if not s.is_enabled:
        return 0
    if _send_rate_limit_backoff_active(s):
        return 0
    if _gemini_backoff_active(s):
        return 0
    # Реанімація «зависань» у processing (вбитий демон / надто довгий виклик).
    try:
        reclaim_stale_processing()
    except Exception as exc:
        log("warning", "reclaim", repr(exc))
    handled = 0
    for _ in range(max_items):
        row = _claim_next()
        if not row:
            break
        try:
            processed = _process_one(s, row)
            if processed:
                handled += 1
            elif InstagramBotMessage.objects.filter(
                pk=row.pk,
                status=InstagramBotMessage.Status.PENDING,
            ).exists():
                # Do not reclaim the same oldest row repeatedly in one drain.
                # A later daemon cycle observes provider backoff and retries.
                break
        except Exception as exc:
            log("error", "process", repr(exc))
            # Після успішного Meta Send рядок уже позначено done. Не можна
            # повертати його в pending через пізній збій CRM/телеметрії — це
            # призведе до дубльованої відповіді клієнту.
            if row.send_state == "sending":
                _own_processing_claim(row).update(
                    status=InstagramBotMessage.Status.FAILED,
                    send_state="unknown",
                    processed_at=timezone.now(),
                )
            else:
                _own_processing_claim(row).update(
                    status=InstagramBotMessage.Status.PENDING,
                    processing_started_at=None,
                )
            break
    return handled


def pending_count() -> int:
    return InstagramBotMessage.objects.filter(
        role=InstagramBotMessage.Role.USER,
        status=InstagramBotMessage.Status.PENDING,
        client__hidden_at__isnull=True,
    ).count()


def unique_senders_count() -> int:
    """Кількість активних співрозмовників у роботі бота.

    Приховані картки не є частиною робочої черги чи overview-метрики.
    """
    return IgClient.objects.filter(hidden_at__isnull=True).count()


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
    if not isinstance(payload, dict):
        return
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        messaging = entry.get("messaging")
        if isinstance(messaging, list):
            for event in messaging:
                if not isinstance(event, dict):
                    continue
                raw_message = event.get("message")
                message = dict(raw_message) if isinstance(raw_message, dict) else {}
                raw_referral = event.get("referral")
                postback = event.get("postback")
                postback_referral = postback.get("referral") if isinstance(postback, dict) else None
                message["_event_created_at"] = _provider_event_datetime(
                    event.get("timestamp") or entry.get("time")
                )
                sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
                recipient = event.get("recipient") if isinstance(event.get("recipient"), dict) else {}
                ref = raw_referral if isinstance(raw_referral, dict) else (
                    postback_referral if isinstance(postback_referral, dict) else {}
                )
                yield (
                    sender.get("id", ""),
                    recipient.get("id", ""),
                    message,
                    ref,
                )
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict) or change.get("field") != "messages":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            raw_message = value.get("message")
            message = dict(raw_message) if isinstance(raw_message, dict) else {}
            message["_event_created_at"] = _provider_event_datetime(
                value.get("timestamp") or entry.get("time")
            )
            sender = value.get("sender") if isinstance(value.get("sender"), dict) else {}
            recipient = value.get("recipient") if isinstance(value.get("recipient"), dict) else {}
            ref = value.get("referral") if isinstance(value.get("referral"), dict) else {}
            yield (sender.get("id", ""), recipient.get("id", ""), message, ref)


def _provider_event_datetime(raw) -> datetime | None:
    try:
        value = float(raw)
        if value > 10_000_000_000:
            value /= 1000.0
        return datetime.fromtimestamp(value, tz=dt_timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


_WEBHOOK_EVENT_KEYS = frozenset({
    "sender", "recipient", "timestamp", "message", "postback", "referral",
    "reaction", "read", "delivery", "attachments", "is_echo", "is_deleted",
    "is_unsupported", "optin", "account_linking", "standby",
})
_WEBHOOK_MESSAGE_KEYS = frozenset({
    "mid", "text", "attachments", "is_echo", "is_deleted", "is_unsupported",
    "reply_to", "quick_reply", "nfm_reply", "story", "referral",
})


def _webhook_observation_summary(payload: dict) -> str:
    """Return bounded evidence counters for valid and ignored webhook shapes."""
    counts: dict[str, int] = {}
    unknown_fields = 0
    malformed = 0

    def bump(kind: str, amount: int = 1) -> None:
        counts[kind] = counts.get(kind, 0) + amount

    if not isinstance(payload, dict) or not isinstance(payload.get("entry"), list):
        return "malformed=1"
    for entry in payload["entry"]:
        if not isinstance(entry, dict):
            malformed += 1
            continue
        messaging = entry.get("messaging")
        if messaging is not None and not isinstance(messaging, list):
            malformed += 1
        for event in messaging if isinstance(messaging, list) else []:
            if not isinstance(event, dict):
                malformed += 1
                continue
            unknown_fields += len(set(event) - _WEBHOOK_EVENT_KEYS)
            message = event.get("message")
            if isinstance(message, dict):
                unknown_fields += len(set(message) - _WEBHOOK_MESSAGE_KEYS)
                if message.get("is_echo"):
                    bump("echo")
                elif message.get("is_deleted"):
                    bump("delete")
                elif message.get("is_unsupported"):
                    bump("unsupported")
                else:
                    bump("message")
            elif isinstance(event.get("postback"), dict):
                bump("postback")
            elif isinstance(event.get("reaction"), dict):
                bump("reaction")
            elif any(key in event for key in ("read", "delivery", "optin", "account_linking")):
                bump("control")
            else:
                bump("unknown")
        changes = entry.get("changes")
        if changes is not None and not isinstance(changes, list):
            malformed += 1
        for change in changes if isinstance(changes, list) else []:
            if not isinstance(change, dict):
                malformed += 1
                continue
            unknown_fields += len(set(change) - {"field", "value"})
            field = str(change.get("field") or "unknown")
            if field == "messages" and isinstance(change.get("value"), dict):
                bump("message")
            elif field in {"messaging_postbacks", "postbacks"}:
                bump("postback")
            elif field in {"message_reactions", "reactions"}:
                bump("reaction")
            else:
                bump("unknown_change")
    if unknown_fields:
        bump("unknown_fields", unknown_fields)
    if malformed:
        bump("malformed", malformed)
    return ",".join(f"{key}={counts[key]}" for key in sorted(counts))[:255]


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
        note=_webhook_observation_summary(payload),
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
    "image", "share", "ig_reel", "reel", "story_mention", "story", "video", "audio", "file", "link",
}
MEDIA_MAX = 3


def _extract_media_urls(msg: dict) -> list[str]:
    """Збирає завантажувані URL з повідомлення: вкладення будь-якого медіа-типу
    (а не лише image) + відповідь на сторіс (reply_to.story.url). Дедуп, cap.

    download_image() сам відсіє не-image (відео/файл), тож їх URL безпечні.
    """
    urls: list[str] = []
    for att in _attachment_items(msg) or []:
        for media_type, url, _title in _attachment_media_candidates(att):
            if media_type.lower() in MEDIA_ATTACH_TYPES:
                urls.append(url)
    story = (msg.get("reply_to") or {}).get("story") or {}
    if story.get("url"):
        urls.append(story["url"])
    out: list[str] = []
    for u in urls:
        if u and u not in out:
            out.append(u)
    return out[:MEDIA_MAX]


def _polled_recipient_id(message: dict, page_id: str) -> str:
    """Return the customer participant for either side of a conversation."""
    sender = str((message.get("from") or {}).get("id") or "").strip()
    if sender and sender != str(page_id or "") and _SENDER_ID_RE.fullmatch(sender):
        return sender
    recipient_block = message.get("to") or {}
    if not isinstance(recipient_block, dict):
        return ""
    recipients = recipient_block.get("data") or []
    if not isinstance(recipients, list):
        return ""
    for recipient in recipients:
        if not isinstance(recipient, dict):
            continue
        candidate = str((recipient or {}).get("id") or "").strip()
        if (
            candidate
            and candidate != str(page_id or "")
            and _SENDER_ID_RE.fullmatch(candidate)
        ):
            return candidate
    return ""


def _persist_polled_message(
    s: InstagramBotSettings,
    message: dict,
    *,
    observed_only: bool = False,
) -> bool:
    """Persist a provider message without triggering classification or reply.

    This path is used for backfilled pages and page-side messages. It is
    idempotent by Meta message id and deliberately never enters the customer
    reply queue, so recovery cannot send historical responses.
    """
    mid = str(message.get("id") or "").strip()
    if not _valid_message_id(mid):
        return False
    page_id = str(s.ig_user_id or s.page_id or "").strip()
    sender = str((message.get("from") or {}).get("id") or "").strip()
    customer_id = _polled_recipient_id(message, page_id)
    if not customer_id:
        return False
    text = str(message.get("message") or "").strip()
    attachments = _extract_media_urls(message)
    if not text and not attachments:
        text = "(медіа)"
    is_page_side = bool(sender and sender == page_id)
    role = InstagramBotMessage.Role.USER
    if is_page_side:
        role = (
            InstagramBotMessage.Role.MODEL
            if text and cache.get(_bot_sent_key(customer_id, text))
            else InstagramBotMessage.Role.MANAGER
        )
    try:
        client = IgClient.get_or_create_for_sender(customer_id)
        row, created = InstagramBotMessage.objects.get_or_create(
            mid=mid,
            defaults={
                "sender_id": customer_id,
                "client": client,
                "role": role,
                "text": text,
                "status": InstagramBotMessage.Status.DONE,
                "source": "poll_history" if observed_only else "poll",
                "attachments": json.dumps(attachments) if attachments else "",
                "provider_created_at": _parse_ig_time(
                    message.get("created_time", "")
                ),
                "processed_at": timezone.now(),
            },
        )
        if not created:
            return True
        provider_created_at = row.provider_created_at
        if role == InstagramBotMessage.Role.USER:
            if provider_created_at and (
                not client.last_message_at
                or provider_created_at > client.last_message_at
            ):
                updates = {
                    "last_message_at": provider_created_at,
                    "updated_at": timezone.now(),
                }
                if not client.first_contact_at:
                    updates["first_contact_at"] = provider_created_at
                IgClient.objects.filter(pk=client.pk).update(**updates)
        try:
            from management.services.bot_conversation_analysis import schedule_analysis

            schedule_analysis(
                client,
                row,
                trigger="poll_history" if observed_only else "poll_backfill",
            )
        except DatabaseError:
            raise
        except Exception:
            pass
        return True
    except IntegrityError:
        return False


def _handle_polled_page_side(
    s: InstagramBotSettings,
    message: dict,
    *,
    historical: bool,
) -> bool:
    """Persist a page-side message with conservative provenance semantics."""
    page_id = str(s.ig_user_id or s.page_id or "").strip()
    customer_id = _polled_recipient_id(message, page_id)
    if not customer_id:
        return False
    text = str(message.get("message") or "").strip()
    if not text and not _extract_media_urls(message):
        return _persist_polled_message(s, message, observed_only=True)
    if historical or (text and cache.get(_bot_sent_key(customer_id, text))):
        return _persist_polled_message(s, message, observed_only=True)
    try:
        _handle_echo(
            customer_id,
            text,
            attachments=_echo_media_items(message),
            mid=str(message.get("id") or "").strip(),
            received_at=_parse_ig_time(message.get("created_time", "")),
            persistence_only=True,
        )
    except Exception as exc:
        log("warning", "poll_manager_message", repr(exc))
        return False
    return InstagramBotMessage.objects.filter(mid=message.get("id")).exists()


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


def handle_webhook_payload(
    s: InstagramBotSettings, payload: dict, *, persistence_only: bool = False
) -> int:
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
                _handle_echo(
                    recipient_id,
                    msg.get("text", ""),
                    attachments=_echo_media_items(msg),
                    mid=msg.get("mid", ""),
                    received_at=msg.get("_event_created_at"),
                    persistence_only=persistence_only,
                )
            except Exception as exc:
                log("warning", "echo", repr(exc))
                if persistence_only:
                    raise
            continue
        sender_id = str(sender_id or "").strip()
        message_mid = str(msg.get("mid") or "").strip()
        if not _SENDER_ID_RE.fullmatch(sender_id):
            log("warning", "invalid_sender_id", f"[{len(sender_id)} chars]")
            continue
        if message_mid and not _valid_message_id(message_mid):
            log("warning", "invalid_message_id", f"[{len(message_mid)} chars]")
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
            received_at=msg.get("_event_created_at"),
            persistence_only=persistence_only,
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


def _valid_message_id(value) -> bool:
    return bool(
        isinstance(value, str)
        and 0 < len(value.strip()) <= 255
        and all(ord(char) >= 32 and ord(char) != 127 for char in value)
    )


def _poll_offset_cache_key(s: InstagramBotSettings) -> str:
    return f"ig_bot_poll_offset:{_provider_owner_id(s)}"


def _poll_conversation_order(s: InstagramBotSettings, conv_ids: list[str]) -> tuple[list[str], int]:
    if not conv_ids:
        return [], 0
    raw_offset = cache.get(_poll_offset_cache_key(s))
    try:
        offset = int(raw_offset or 0) % len(conv_ids)
    except (TypeError, ValueError):
        offset = 0
    return conv_ids[offset:] + conv_ids[:offset], offset


def _poll_cursor_map(conv_ids: list[str]) -> dict[str, IgPollCursor]:
    existing = {
        cursor.conversation_id: cursor
        for cursor in IgPollCursor.objects.filter(conversation_id__in=conv_ids)
    }
    missing = [
        IgPollCursor(conversation_id=conversation_id)
        for conversation_id in conv_ids
        if conversation_id not in existing
    ]
    if missing:
        IgPollCursor.objects.bulk_create(missing, ignore_conflicts=True)
        existing = {
            cursor.conversation_id: cursor
            for cursor in IgPollCursor.objects.filter(conversation_id__in=conv_ids)
        }
    return existing


def _poll_failure_delay(reason: str, failure_count: int) -> int:
    failure_count = max(1, min(int(failure_count or 1), 16))
    if reason == "meta_rate_limit":
        return min(5 * 60 * (2 ** (failure_count - 1)), POLL_FAILURE_BACKOFF_MAX)
    if reason in {"http_403", "http_404"}:
        return min(60 * 60 * failure_count, POLL_FAILURE_BACKOFF_MAX)
    return min(60 * (2 ** (failure_count - 1)), POLL_FAILURE_BACKOFF_MAX)


def _mark_poll_cursor_failure(cursor: IgPollCursor, reason: str) -> None:
    cursor.failure_count = min(int(cursor.failure_count or 0) + 1, 16)
    cursor.last_error = str(reason or "provider_error")[:80]
    cursor.next_attempt_at = timezone.now() + timedelta(
        seconds=_poll_failure_delay(cursor.last_error, cursor.failure_count)
    )
    cursor.save(update_fields=[
        "failure_count", "last_error", "next_attempt_at", "updated_at",
    ])


def _mark_poll_cursor_success(
    cursor: IgPollCursor,
    *,
    instagram_login: bool,
) -> None:
    cursor.failure_count = 0
    cursor.last_error = ""
    cursor.next_attempt_at = None
    update_fields = ["failure_count", "last_error", "next_attempt_at", "updated_at"]
    if instagram_login:
        cursor.synced_provider_updated_at = cursor.provider_updated_at
        update_fields.append("synced_provider_updated_at")
    cursor.save(update_fields=update_fields)


def _polled_message_key(message: dict) -> tuple[datetime, str]:
    return (
        _parse_ig_time(message.get("created_time", ""))
        or datetime.min.replace(tzinfo=dt_timezone.utc),
        message["id"],
    )


def _polled_message_is_historical(
    created: datetime | None,
    *,
    reply_after: datetime | None,
    instagram_login: bool,
    now: datetime,
) -> bool:
    if reply_after and created and created <= reply_after:
        return True
    return bool(
        instagram_login
        and created
        and created <= now - POLL_REPLY_WINDOW
    )


def _validate_polled_page(
    envelope,
    s: InstagramBotSettings | None = None,
) -> tuple[list[dict], str]:
    if not isinstance(envelope, dict):
        raise ValueError("malformed envelope")
    messages_block = envelope.get("messages")
    if messages_block is None:
        messages_block = {}
    if not isinstance(messages_block, dict):
        raise ValueError("malformed messages")
    messages = messages_block.get("data", [])
    if not isinstance(messages, list):
        raise ValueError("malformed message data")
    if (
        s is not None
        and provider_transport(s) == INSTAGRAM_LOGIN_TRANSPORT
    ):
        messages = messages[:POLL_INSTAGRAM_MESSAGE_LIMIT]
    for message in messages:
        if not isinstance(message, dict) or not _valid_message_id(message.get("id")):
            raise ValueError("malformed message id")
        created_time = message.get("created_time")
        if not isinstance(created_time, str) or _parse_ig_time(created_time) is None:
            raise ValueError("malformed message time")
        sender = message.get("from")
        if not isinstance(sender, dict):
            raise ValueError("malformed message sender")
        sender_id = sender.get("id")
        if (
            not isinstance(sender_id, str)
            or not _SENDER_ID_RE.fullmatch(sender_id.strip())
        ):
            raise ValueError("malformed sender id")
        recipients = message.get("to")
        if recipients is not None:
            if not isinstance(recipients, dict) or not isinstance(recipients.get("data"), list):
                raise ValueError("malformed recipients")
            for recipient in recipients["data"]:
                recipient_id = recipient.get("id") if isinstance(recipient, dict) else None
                if (
                    not isinstance(recipient_id, str)
                    or not _SENDER_ID_RE.fullmatch(recipient_id.strip())
                ):
                    raise ValueError("malformed recipient id")
        text = message.get("message")
        if text is not None and not isinstance(text, str):
            raise ValueError("malformed message text")
        attachments = _attachment_items(message)
        if attachments is None:
            raise ValueError("malformed attachments")
        for item in attachments:
            if item.get("payload") is not None and not isinstance(item.get("payload"), dict):
                raise ValueError("malformed attachments")
            for value in item.values():
                if not isinstance(value, dict):
                    continue
                for url_key in ("url", "file_url", "preview_url"):
                    if value.get(url_key) is not None and not isinstance(value.get(url_key), str):
                        raise ValueError("malformed attachments")
    paging = messages_block.get("paging")
    if paging is None:
        paging = {}
    if not isinstance(paging, dict):
        raise ValueError("malformed message paging")
    next_url = paging.get("next") or ""
    valid_page_url = (
        _valid_provider_conversation_page_url(s, next_url)
        if s is not None and isinstance(next_url, str)
        else _valid_conversation_page_url(next_url)
    )
    if next_url and (not isinstance(next_url, str) or not valid_page_url):
        raise ValueError("untrusted message paging URL")
    return messages, next_url


def _fetch_polled_conversation(
    s: InstagramBotSettings,
    conversation_id: str,
    page_token: str,
    *,
    cursor_at: datetime | None,
    cursor_id: str,
    deadline: float,
    request_limit: int,
) -> dict:
    instagram_login = provider_transport(s) == INSTAGRAM_LOGIN_TRANSPORT
    message_limit = POLL_INSTAGRAM_MESSAGE_LIMIT if instagram_login else 50
    page_url = _provider_url(
        s,
        f"/{conversation_id}",
        {
            "fields": (
                f"messages.limit({message_limit})"
                "{message,from,to,created_time,id,attachments}"
            )
        },
    )
    all_messages: list[dict] = []
    visited_pages: set[str] = set()
    requests_used = 0
    for _page in range(POLL_MESSAGE_MAX_PAGES):
        if requests_used >= request_limit or time.monotonic() >= deadline:
            return {
                "messages": all_messages,
                "requests": requests_used,
                "complete": False,
                "budget_exhausted": True,
                "reason": "poll_budget",
            }
        if page_url in visited_pages:
            return {
                "messages": all_messages,
                "requests": requests_used,
                "complete": False,
                "budget_exhausted": False,
                "reason": "page_cycle",
            }
        visited_pages.add(page_url)
        remaining_seconds = max(1, int(deadline - time.monotonic()))
        timeout = min(POLL_MESSAGE_TIMEOUT, remaining_seconds)
        code, body = _provider_http(
            s,
            page_url,
            token=page_token,
            timeout=timeout,
        )
        requests_used += 1
        if code != 200:
            return {
                "messages": all_messages,
                "requests": requests_used,
                "complete": False,
                "budget_exhausted": False,
                "reason": _classify_poll_provider_failure(code, body),
            }
        try:
            messages, next_url = _validate_polled_page(json.loads(body), s)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return {
                "messages": all_messages,
                "requests": requests_used,
                "complete": False,
                "budget_exhausted": False,
                "reason": f"malformed:{exc}",
            }
        all_messages.extend(messages)
        if cursor_at and any(
            _polled_message_key(message) <= (cursor_at, cursor_id)
            for message in messages
        ):
            return {
                "messages": all_messages,
                "requests": requests_used,
                "complete": True,
                "budget_exhausted": False,
                "reason": "cursor_reached",
            }
        if instagram_login:
            # Instagram Login exposes details for only the 20 most recent
            # messages. Older message IDs may exist, but requesting their
            # details returns a provider "deleted" error. The first validated
            # window is therefore the complete readable history boundary.
            return {
                "messages": all_messages,
                "requests": requests_used,
                "complete": True,
                "budget_exhausted": False,
                "reason": "instagram_latest_window",
            }
        if not next_url:
            return {
                "messages": all_messages,
                "requests": requests_used,
                "complete": True,
                "budget_exhausted": False,
                "reason": "complete",
            }
        if next_url in visited_pages:
            return {
                "messages": all_messages,
                "requests": requests_used,
                "complete": False,
                "budget_exhausted": False,
                "reason": "page_cycle",
            }
        page_url = next_url
    return {
        # Keep already fetched pages available for persistence. The cursor is
        # still left untouched by poll_ingest until the conversation is fully
        # traversed, so a later cycle can safely continue recovery.
        "messages": all_messages,
        "requests": requests_used,
        "complete": False,
        "budget_exhausted": False,
        "reason": "page_cap",
    }


def poll_ingest(s: InstagramBotSettings) -> dict:
    """Читає інбокс IG і кладе нові вхідні в чергу. Лише коли receive_via_poll."""
    if not s.receive_via_poll:
        return {"ok": True, "enqueued": 0, "skipped": True}
    if not _provider_account_id(s):
        return {"ok": False, "error": "missing_provider_account_id"}
    page_token = get_page_token(s)
    if not page_token:
        return {"ok": False, "error": "no_page_token"}
    conv_ids = get_conv_ids_cached(s)
    if conv_ids is None:
        return {
            "ok": True,
            "enqueued": 0,
            "conversations": 0,
            "refresh_pending": True,
            "degraded": True,
        }
    if not conv_ids:
        _clear_ingress_degradation(s, "poll")
        return {"ok": True, "enqueued": 0, "conversations": 0}
    if s.last_error:
        s.last_error = ""
        s.save(update_fields=["last_error"])
    reply_after = s.reply_after or s.last_started_at
    enq = 0
    instagram_login = provider_transport(s) == INSTAGRAM_LOGIN_TRANSPORT
    cursor_by_id = _poll_cursor_map(conv_ids)
    now = timezone.now()
    due_conv_ids: list[str] = []
    conversations_excluded = 0
    conversations_unmapped = 0
    conversations_deferred = 0
    conversations_unchanged = 0
    for cid in conv_ids:
        cursor = cursor_by_id[cid]
        if instagram_login and cursor.excluded_at:
            conversations_excluded += 1
            continue
        if instagram_login and not cursor.participant_igsid:
            conversations_unmapped += 1
            continue
        if instagram_login and cursor.next_attempt_at and cursor.next_attempt_at > now:
            conversations_deferred += 1
            continue
        if (
            instagram_login
            and cursor.last_message_id
            and cursor.provider_updated_at
            and cursor.synced_provider_updated_at
            and cursor.synced_provider_updated_at >= cursor.provider_updated_at
        ):
            conversations_unchanged += 1
            continue
        due_conv_ids.append(cid)
    ordered_conv_ids, start_offset = _poll_conversation_order(s, due_conv_ids)
    deadline = time.monotonic() + POLL_MAX_SECONDS
    requests_used = 0
    conversations_checked = 0
    budget_exhausted = False
    degraded = False
    failure_counts: dict[str, int] = {}
    for cid in ordered_conv_ids:
        if requests_used >= POLL_MAX_REQUESTS or time.monotonic() >= deadline:
            budget_exhausted = True
            break
        conversations_checked += 1
        cursor = cursor_by_id[cid]
        cursor_at = cursor.last_message_at
        cursor_id = cursor.last_message_id or ""
        fetched = _fetch_polled_conversation(
            s,
            cid,
            page_token,
            cursor_at=cursor_at,
            cursor_id=cursor_id,
            deadline=deadline,
            request_limit=POLL_MAX_REQUESTS - requests_used,
        )
        requests_used += fetched["requests"]
        if not fetched["complete"]:
            # A partial traversal must not advance the cursor, but a validated
            # live inbound must still enter the idempotent queue. Persisting it
            # as observed-only would consume its unique Meta id and the next
            # complete cycle could never make it reply-eligible.
            partial_unique = {
                message["id"]: message for message in fetched.get("messages", [])
            }
            page_id = str(s.ig_user_id or s.page_id or "").strip()
            for message in sorted(partial_unique.values(), key=_polled_message_key):
                created = _parse_ig_time(message.get("created_time", ""))
                sender = (message.get("from") or {}).get("id", "")
                is_page_side = bool(page_id and sender == page_id)
                is_before_reply_boundary = _polled_message_is_historical(
                    created,
                    reply_after=reply_after,
                    instagram_login=instagram_login,
                    now=now,
                )
                if is_page_side:
                    _handle_polled_page_side(
                        s,
                        message,
                        historical=is_before_reply_boundary,
                    )
                    continue
                if is_before_reply_boundary:
                    _persist_polled_message(s, message, observed_only=True)
                    continue
                message_text = str(message.get("message") or "").strip()
                message_attachments = _extract_media_urls(message)
                if not message_text and not message_attachments:
                    _persist_polled_message(s, message, observed_only=True)
                    continue
                if enqueue_inbound(
                    s,
                    sender_id=sender,
                    text=message_text,
                    mid=message["id"],
                    source="poll",
                    attachments=message_attachments,
                    received_at=created,
                ):
                    enq += 1
            failure_reason = str(fetched["reason"])
            failure_counts[failure_reason] = failure_counts.get(failure_reason, 0) + 1
            if instagram_login:
                _mark_poll_cursor_failure(cursor, failure_reason)
            repeated_isolated_failure = bool(
                instagram_login
                and failure_reason in {"http_403", "http_404"}
                and cursor.failure_count >= 2
            )
            if (
                not instagram_login
                or failure_reason not in {"http_403", "http_404"}
                or repeated_isolated_failure
            ):
                degraded = True
                _record_ingress_degradation(
                    s,
                    "poll",
                    state="message_poll_failed",
                    reason=(
                        "repeated_conversation_inaccessible"
                        if repeated_isolated_failure
                        else failure_reason
                    ),
                )
            if fetched["budget_exhausted"]:
                budget_exhausted = True
                break
            continue

        unique: dict[str, dict] = {}
        for message in fetched["messages"]:
            unique[message["id"]] = message

        ordered = sorted(unique.values(), key=_polled_message_key)
        page_id = str(s.ig_user_id or s.page_id or "").strip()
        conversation_handled = True
        for message in ordered:
            mid = message["id"]
            created = _parse_ig_time(message.get("created_time", ""))
            if cursor_at and _polled_message_key(message) <= (cursor_at, cursor_id):
                continue
            sender = (message.get("from") or {}).get("id", "")
            if not sender:
                continue
            is_page_side = bool(page_id and sender == page_id)
            is_before_reply_boundary = _polled_message_is_historical(
                created,
                reply_after=reply_after,
                instagram_login=instagram_login,
                now=now,
            )
            if is_page_side:
                conversation_handled = bool(
                    _handle_polled_page_side(
                        s,
                        message,
                        historical=is_before_reply_boundary,
                    )
                ) and conversation_handled
                continue
            if is_before_reply_boundary:
                conversation_handled = bool(
                    _persist_polled_message(s, message, observed_only=True)
                ) and conversation_handled
                continue
            message_text = str(message.get("message") or "").strip()
            message_attachments = _extract_media_urls(message)
            if not message_text and not message_attachments:
                conversation_handled = bool(
                    _persist_polled_message(s, message, observed_only=True)
                ) and conversation_handled
                continue
            added = enqueue_inbound(
                s,
                sender_id=sender,
                text=message_text,
                mid=mid,
                source="poll",
                attachments=message_attachments,
                received_at=created,
            )
            enq += int(added)
            conversation_handled = bool(
                added or InstagramBotMessage.objects.filter(mid=mid).exists()
            ) and conversation_handled

        if ordered and conversation_handled:
            newest = max(ordered, key=_polled_message_key)
            newest_at, newest_id = _polled_message_key(newest)
            cursor.last_message_at = newest_at if newest_at != datetime.min.replace(tzinfo=dt_timezone.utc) else cursor.last_message_at
            cursor.last_message_id = newest_id
            cursor.save(update_fields=["last_message_at", "last_message_id", "updated_at"])
            _mark_poll_cursor_success(cursor, instagram_login=instagram_login)
        elif not ordered:
            _mark_poll_cursor_success(cursor, instagram_login=instagram_login)
        elif ordered:
            degraded = True
            if instagram_login:
                _mark_poll_cursor_failure(cursor, "persistence_failed")
            _record_ingress_degradation(
                s,
                "poll",
                state="message_poll_failed",
                reason="persistence_failed",
            )
    if conversations_checked < len(ordered_conv_ids):
        budget_exhausted = True
    next_offset = (
        (start_offset + conversations_checked) % len(ordered_conv_ids)
        if ordered_conv_ids
        else 0
    )
    if budget_exhausted and ordered_conv_ids:
        cache.set(_poll_offset_cache_key(s), next_offset, CONV_CACHE_TTL)
    else:
        cache.delete(_poll_offset_cache_key(s))
    for reason, count in sorted(failure_counts.items()):
        log("warning", "poll_messages", f"{reason}: {count} conversation(s) deferred")
    isolated_failure_count = sum(
        failure_counts.get(reason, 0) for reason in ("http_403", "http_404")
    )
    if (
        instagram_login
        and conversations_checked >= 2
        and isolated_failure_count == conversations_checked
    ):
        degraded = True
        _record_ingress_degradation(
            s,
            "poll",
            state="message_poll_failed",
            reason="all_conversations_inaccessible",
        )
    if (
        not degraded
        and isolated_failure_count == 0
        and (instagram_login or not budget_exhausted)
    ):
        _clear_ingress_degradation(s, "poll")
    return {
        "ok": True,
        "enqueued": enq,
        "conversations": len(conv_ids),
        "conversations_checked": conversations_checked,
        "conversations_due": len(due_conv_ids),
        "conversations_excluded": conversations_excluded,
        "conversations_unmapped": conversations_unmapped,
        "conversations_deferred": conversations_deferred,
        "conversations_unchanged": conversations_unchanged,
        "requests_used": requests_used,
        "budget_exhausted": budget_exhausted,
        "degraded": degraded,
    }


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
    from management.services.ig_reply_boundary import pause_reply_boundary

    with pause_reply_boundary():
        with transaction.atomic():
            s = InstagramBotSettings.objects.select_for_update().get(
                pk=InstagramBotSettings.load().pk
            )
            was = s.is_enabled
            s.is_enabled = True
            s.reply_permission_epoch = int(s.reply_permission_epoch or 0) + 1
            s.last_started_at = timezone.now()
            s.reply_after = timezone.now()
            s.last_error = ""
            s.save(update_fields=[
                "is_enabled", "reply_permission_epoch", "last_started_at",
                "reply_after", "last_error",
            ])
    if not was:
        log("success", "start", "Бот запущено, очікую повідомлення.")
    return s


def stop_bot() -> InstagramBotSettings:
    from management.models import IgFollowUpTask
    from management.services.ig_reply_boundary import pause_reply_boundary

    now = timezone.now()
    with pause_reply_boundary():
        with transaction.atomic():
            s = InstagramBotSettings.objects.select_for_update().get(
                pk=InstagramBotSettings.load().pk
            )
            was = s.is_enabled
            s.is_enabled = False
            s.reply_permission_epoch = int(s.reply_permission_epoch or 0) + 1
            s.last_stopped_at = now
            s.save(update_fields=["is_enabled", "reply_permission_epoch", "last_stopped_at"])
            InstagramBotMessage.objects.filter(
                role=InstagramBotMessage.Role.USER,
                status__in=[
                    InstagramBotMessage.Status.PENDING,
                    InstagramBotMessage.Status.PROCESSING,
                ],
            ).exclude(send_state="sending").update(
                status=InstagramBotMessage.Status.DONE,
                processed_at=now,
                processing_started_at=None,
            )
            IgFollowUpTask.objects.filter(status=IgFollowUpTask.Status.PENDING).exclude(
                kind=IgFollowUpTask.Kind.MANAGER_TASK,
                reason="followup_delivery_review",
            ).update(
                status=IgFollowUpTask.Status.CANCELLED,
                skip_reason="global_reply_stopped",
                updated_at=now,
            )
            IgClient.objects.filter(next_followup_at__isnull=False).update(
                next_followup_at=None
            )
    if was:
        log("warning", "stop", "Бот зупинено.")
    return s


def meta_capability_status(s: InstagramBotSettings) -> dict[str, object]:
    """Expose independent Meta facts without implying public delivery access."""
    return {
        "transport": provider_transport(s),
        "provider_account_id": _provider_account_id(s),
        "local_allowlist": "restricted" if allowed_sender_ids(s) else "all_allowed",
        "token_configured": provider_token_configured(s),
        "token_source": (
            "IG_INSTAGRAM_BOT"
            if provider_transport(s) == INSTAGRAM_LOGIN_TRANSPORT
            else "legacy"
        ),
        "token_permission": "unknown",
        "account_access": "unknown",
        "recipient_delivery": "per_recipient",
    }


def ingress_status(s: InstagramBotSettings, *, now=None) -> dict[str, object]:
    """Report bounded local evidence for inbound availability.

    This status path must never call Graph. Webhook health is configuration
    truth; polling health is based on configured credentials and a recent
    completed poll recorded by the worker.
    """
    now = now or timezone.now()
    webhook = webhook_signature_status()
    webhook_rejections = webhook_rejection_status()
    if webhook_rejections:
        webhook = {
            **webhook,
            "healthy": False,
            "state": "rejections_degraded",
            "rejections": webhook_rejections,
        }
    degradation = _current_ingress_degradation(s)
    discovery = conversation_discovery_status(s, now=now)
    if not s.receive_via_poll:
        polling = {"configured": False, "healthy": False, "state": "disabled"}
    elif not provider_token_configured(s):
        polling = {"configured": True, "healthy": False, "state": "missing_token"}
    elif degradation:
        polling = {
            "configured": True,
            "healthy": False,
            "state": "degraded",
            "degradation": degradation,
        }
    elif str(s.last_error or "").startswith("polling:"):
        polling = {
            "configured": True,
            "healthy": False,
            "state": "degraded",
            "error": str(s.last_error)[len("polling:"):][:240],
        }
    elif not s.last_poll_at:
        polling = {"configured": True, "healthy": False, "state": "not_observed"}
    else:
        age = max(0.0, (now - s.last_poll_at).total_seconds())
        max_age = max(90, int(s.poll_interval_seconds or 3) * 10)
        healthy = age <= max_age
        polling = {
            "configured": True,
            "healthy": healthy,
            "state": "healthy" if healthy else "stale",
            "age_seconds": round(age, 1),
        }
    polling["discovery"] = discovery
    healthy = bool(webhook.get("healthy") or polling.get("healthy"))
    return {
        "healthy": healthy,
        "state": "available" if healthy else "unavailable",
        "webhook": webhook,
        "polling": polling,
    }


def status_snapshot() -> dict:
    from management.services.ig_maintenance import maintenance_status
    from management.services.ig_reply_boundary import reply_barrier_telemetry

    s = InstagramBotSettings.load()
    maintenance = maintenance_status()
    now = timezone.now()
    hb = s.heartbeat_at
    db_heartbeat_age = (now - hb).total_seconds() if hb else None
    db_heartbeat_fresh = bool(db_heartbeat_age is not None and db_heartbeat_age < 90)
    dhb = cache.get("ig_bot_daemon_hb")
    try:
        if isinstance(dhb, dict):
            dhb = dhb.get("at")
        daemon_heartbeat_age = time.time() - float(dhb) if dhb else None
    except (TypeError, ValueError):
        daemon_heartbeat_age = None
    daemon_online = bool(daemon_heartbeat_age is not None and daemon_heartbeat_age < 45)
    ingress = ingress_status(s, now=now)
    if maintenance["active"]:
        state = "maintenance"
    elif not s.is_enabled:
        state = "disabled"
    elif daemon_online and not ingress["healthy"]:
        state = "ingress_degraded"
    elif daemon_online:
        state = "running"
    elif db_heartbeat_fresh:
        state = "worker_error"
    else:
        state = "enabled_but_worker_missing"
    try:
        notification_pending = IgBotNotification.objects.filter(
            status__in=[IgBotNotification.Status.PENDING, IgBotNotification.Status.SENDING]
        ).count()
        notification_failed = IgBotNotification.objects.filter(
            status=IgBotNotification.Status.FAILED
        ).count()
        notification_unknown = IgBotNotification.objects.filter(
            status=IgBotNotification.Status.UNKNOWN
        ).count()
        notification_dead_letter = IgBotNotification.objects.filter(
            status=IgBotNotification.Status.DEAD_LETTER
        ).count()
    except Exception:
        notification_pending = None
        notification_failed = None
        notification_unknown = None
        notification_dead_letter = None
    try:
        analysis_pending = IgConversationAnalysisJob.objects.filter(
            status__in=[
                IgConversationAnalysisJob.Status.PENDING,
                IgConversationAnalysisJob.Status.PROCESSING,
            ]
        ).count()
        analysis_failed = IgConversationAnalysisJob.objects.filter(
            status=IgConversationAnalysisJob.Status.FAILED
        ).count()
    except Exception:
        analysis_pending = None
        analysis_failed = None
    try:
        from management.services.gemini_keys import (
            ALL_KEYS,
            key_project_groups,
            normalize_chat_model,
        )

        effective_model = normalize_chat_model(s.gemini_model)
        project_groups = key_project_groups()
        project_mapping_count = len(project_groups)
        project_mapping_complete = all(alias in project_groups for alias in ALL_KEYS)
    except Exception:
        effective_model = s.gemini_model
        project_mapping_count = 0
        project_mapping_complete = False
    return {
        "is_enabled": s.is_enabled,
        # Backwards-compatible alias: only the daemon heartbeat proves a
        # worker is alive. A fresh DB timestamp alone is not liveness proof.
        "alive": daemon_online,
        "daemon_online": daemon_online,
        "running": bool(
            s.is_enabled and daemon_online and ingress["healthy"] and not maintenance["active"]
        ),
        "state": state,
        "ingress": ingress,
        "recovery_expected": bool(s.is_enabled and not daemon_online and not maintenance["active"]),
        "maintenance": maintenance,
        "db_heartbeat_fresh": db_heartbeat_fresh,
        "db_heartbeat_age_seconds": round(db_heartbeat_age, 1) if db_heartbeat_age is not None else None,
        "daemon_heartbeat_age_seconds": round(daemon_heartbeat_age, 1) if daemon_heartbeat_age is not None else None,
        "heartbeat_at": hb.isoformat() if hb else "",
        "last_inbound_at": s.last_inbound_at.isoformat() if s.last_inbound_at else "",
        "last_reply_at": s.last_reply_at.isoformat() if s.last_reply_at else "",
        "replies_count": s.replies_count,
        "pending": pending_count(),
        "notification_pending": notification_pending,
        "notification_failed": notification_failed,
        "notification_unknown": notification_unknown,
        "notification_dead_letter": notification_dead_letter,
        "analysis_pending": analysis_pending,
        "analysis_failed": analysis_failed,
        "analysis_reconcile_cursor": s.analysis_reconcile_cursor,
        "analysis_reconcile_after": s.analysis_reconcile_after.isoformat(),
        "analysis_backfill_enabled": s.analysis_backfill_enabled,
        "analysis_backfill_allowed": bool(
            s.analysis_backfill_enabled and project_mapping_complete
        ),
        "unique_senders": unique_senders_count(),
        "allow_all": not bool(allowed_sender_ids(s)),
        "last_error": s.last_error,
        "direct_source": s.direct_source,
        "provider_transport": provider_transport(s),
        "provider_account_id": _provider_account_id(s),
        "provider_token_configured": provider_token_configured(s),
        "gemini_source": s.gemini_source,
        "ai_enabled": s.ai_enabled,
        "gemini_model": s.gemini_model,
        "gemini_effective_model": effective_model,
        "gemini_project_mapping_count": project_mapping_count,
        "gemini_project_mapping_complete": project_mapping_complete,
        "last_gemini_model": s.last_gemini_model,
        "last_gemini_key": s.last_gemini_key,
        "last_gemini_at": s.last_gemini_at.isoformat() if s.last_gemini_at else "",
        "last_gemini_reasoning_task": s.last_gemini_reasoning_task,
        "last_gemini_reasoning_level": s.last_gemini_reasoning_level,
        "last_gemini_policy_version": s.last_gemini_policy_version,
        "last_gemini_thoughts_tokens": s.last_gemini_thoughts_tokens,
        "last_gemini_candidates_tokens": s.last_gemini_candidates_tokens,
        "receive_via_poll": s.receive_via_poll,
        "app_secret_set": bool(app_secret()),
        "webhook_signature": webhook_signature_status(),
        "meta_capability": meta_capability_status(s),
        "meta_rate_limits": meta_rate_limit_status(),
        "trigger_text": s.trigger_text,
        "reply_text": s.reply_text,
        "poll_interval_seconds": s.poll_interval_seconds,
        "reply_barrier": reply_barrier_telemetry(),
    }
