"""Менеджер пулів Gemini-ключів.

Розподіл навантаження за ролями з пріоритетним каскадом «основний → страховка →
позичання у менш пріоритетної ролі», цепочки моделей (gen-3 для чату/менеджменту,
2.5 для grounding чекера) та облік квот.

Ключові факти (підтверджені живими тестами + офіційні доки Gemini):
  * Квота рахується НА ПРОЕКТ (не на ключ); денний RPD скидається опівночі
    America/Los_Angeles (PT). Тож 429 уводить у кулдаун весь КЛЮЧ (усі моделі).
  * 503 (overloaded) — модель перевантажена на будь-якому ключі → короткий
    overload-кеш на МОДЕЛЬ, пробуємо наступну модель цепочки.
  * Google Search grounding безкоштовний лише на gemini-2.5-flash.

Ручні ключі (InstagramBotSettings.custom_gemini_key, LeadCheckerSettings.
gemini_api_key) обробляються на рівні викликаючого коду — вони пріоритетніші за пул.
"""
from __future__ import annotations

import datetime
import logging
import os
import re
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from management.models import GeminiKeyState

logger = logging.getLogger("management.gemini_keys")

PT = ZoneInfo("America/Los_Angeles")

# Пули ключів за ролями: own (основні) + borrow (позичання у менш пріоритетної ролі).
DEFAULT_ROLE_KEY_POOLS = {
    "chat": {"own": ["GEMINI_API", "GEMINI_API2"], "borrow": ["GEMINI_API5", "GEMINI_API6"]},
    "management": {"own": ["GEMINI_API3", "GEMINI_API4"], "borrow": ["GEMINI_API5", "GEMINI_API6"]},
    "checker": {"own": ["GEMINI_API5", "GEMINI_API6"], "borrow": []},
}

# Цепочки моделей за ролями. Чат/менеджмент НІКОЛИ не нижче gen-3.
# Чекер може опускатись до 2.5 (єдина роль) — там працює безкоштовний grounding.
DEFAULT_ROLE_MODEL_CHAINS = {
    "chat": ["gemini-3.5-flash", "gemini-3.1-pro-preview", "gemini-3.1-flash-lite"],
    "management": ["gemini-3.5-flash", "gemini-3.1-pro-preview", "gemini-3.1-flash-lite"],
    "checker": ["gemini-3.5-flash", "gemini-2.5-flash"],
}

ATTEMPTS_PER_MODEL = {"chat": 3, "management": 3, "checker": 2}

# Моделі з безкоштовною квотою генерації. 429 на НИХ = вичерпана денна квота
# проекту → кулдаун усього КЛЮЧА. 429 на інших (pro-preview тощо) = модель платна
# → це model-level skip, ключ НЕ чіпаємо.
FREE_QUOTA_MODELS = {
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
}

# Безкоштовний Google Search grounding доступний лише на цих моделях.
FREE_GROUNDING_MODELS = {"gemini-2.5-flash", "gemini-2.5-flash-lite"}


def is_key_level_429(model: str, grounded: bool) -> bool:
    """Чи означає 429 на (model, grounded) вичерпання квоти КЛЮЧА (проекту).

    True → кулдаун ключа. False → модель просто платна/недоступна free для цієї
    фічі → пропускаємо лише модель, ключ лишаємо доступним.
    """
    if grounded:
        return model in FREE_GROUNDING_MODELS
    return model in FREE_QUOTA_MODELS

ALL_KEYS = ["GEMINI_API", "GEMINI_API2", "GEMINI_API3", "GEMINI_API4", "GEMINI_API5", "GEMINI_API6"]

MODEL_OVERLOAD_SECONDS = 300   # 503 → модель «перевантажена» ~5 хв
DEFAULT_MINUTE_COOLDOWN = 60   # per-minute 429 без retryDelay
TOPUP_COOLDOWN_SECONDS = 6 * 3600  # платний проект без коштів

# In-process кеш перевантажених моделей: {model: datetime_until_utc}.
_model_overload: dict[str, datetime.datetime] = {}

_RETRY_RE = re.compile(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"')


# ---------------------------------------------------------------------------
# Конфіг (з можливістю override через settings)
# ---------------------------------------------------------------------------
def role_key_pools() -> dict:
    return getattr(settings, "GEMINI_ROLE_KEY_POOLS", None) or DEFAULT_ROLE_KEY_POOLS


def role_model_chains() -> dict:
    return getattr(settings, "GEMINI_ROLE_MODEL_CHAINS", None) or DEFAULT_ROLE_MODEL_CHAINS


def attempts_per_model(role: str) -> int:
    return int(ATTEMPTS_PER_MODEL.get(role, 2))


# ---------------------------------------------------------------------------
# Час / скидання квоти
# ---------------------------------------------------------------------------
def next_midnight_pt(now: datetime.datetime | None = None) -> datetime.datetime:
    """Наступна північ America/Los_Angeles у UTC — момент скидання денної квоти."""
    now = now or timezone.now()
    now_pt = now.astimezone(PT)
    tomorrow = (now_pt + datetime.timedelta(days=1)).date()
    midnight_pt = datetime.datetime.combine(tomorrow, datetime.time.min, tzinfo=PT)
    return midnight_pt.astimezone(datetime.timezone.utc)


def parse_429(body: str) -> tuple[str, int]:
    """Класифікує 429 → (scope, seconds).

    scope: 'topup' (платний без коштів), 'minute' (RPM), 'day' (RPD/grounding).
    Для 'day' seconds ігнорується (кулдаун до next_midnight_pt).
    """
    text = body or ""
    low = text.lower()
    compact = low.replace("_", "").replace(" ", "")
    if "prepayment" in low or "creditsaredepleted" in compact or "billingaccount" in compact:
        return ("topup", TOPUP_COOLDOWN_SECONDS)
    if "perminute" in compact:
        m = _RETRY_RE.search(text)
        return ("minute", int(float(m.group(1))) + 1 if m else DEFAULT_MINUTE_COOLDOWN)
    if "perday" in compact:
        return ("day", 0)
    # Типове free-tier повідомлення без явного quotaId — денна квота.
    if "planandbilling" in compact or "freetier" in compact or "currentquota" in compact:
        return ("day", 0)
    m = _RETRY_RE.search(text)
    if m:
        return ("minute", int(float(m.group(1))) + 1)
    return ("day", 0)


# ---------------------------------------------------------------------------
# Стан ключів
# ---------------------------------------------------------------------------
def _key_value(key_name: str) -> str:
    return (os.environ.get(key_name, "") or "").strip()


def _roll_day(st: GeminiKeyState, now: datetime.datetime) -> None:
    today = now.astimezone(PT).date()
    if st.day_date != today:
        st.day_date = today
        st.requests_today = 0


def is_available(key_name: str, now: datetime.datetime | None = None) -> bool:
    now = now or timezone.now()
    st = GeminiKeyState.get(key_name)
    if not st.cooldown_until:
        return True
    return st.cooldown_until <= now


def mark_success(key_name: str, now: datetime.datetime | None = None) -> GeminiKeyState:
    now = now or timezone.now()
    st = GeminiKeyState.get(key_name)
    _roll_day(st, now)
    st.cooldown_until = None
    st.cooldown_scope = ""
    st.last_status = "ok"
    st.last_ok_at = now
    st.requests_today = (st.requests_today or 0) + 1
    st.save()
    return st


def mark_429(key_name: str, scope: str, seconds: int,
             now: datetime.datetime | None = None, error: str = "") -> GeminiKeyState:
    now = now or timezone.now()
    st = GeminiKeyState.get(key_name)
    _roll_day(st, now)
    if scope == "day":
        st.cooldown_until = next_midnight_pt(now)
    else:
        st.cooldown_until = now + datetime.timedelta(seconds=max(1, int(seconds)))
    st.cooldown_scope = scope
    st.last_status = f"429:{scope}"
    st.last_429_at = now
    if error:
        st.last_error = error[:500]
    st.save()
    return st


def mark_model_overloaded(model: str, seconds: int = MODEL_OVERLOAD_SECONDS,
                          now: datetime.datetime | None = None) -> None:
    now = now or timezone.now()
    _model_overload[model] = now + datetime.timedelta(seconds=max(1, int(seconds)))


def is_model_overloaded(model: str, now: datetime.datetime | None = None) -> bool:
    now = now or timezone.now()
    until = _model_overload.get(model)
    return bool(until and until > now)


def clear_model_overload() -> None:
    _model_overload.clear()


# ---------------------------------------------------------------------------
# Підбір (key, model) комбінацій
# ---------------------------------------------------------------------------
def iter_attempts(role: str):
    """Генерує (key_name, key_value, model) у порядку пріоритету.

    Порядок: own-ключі (основний першим) → borrow-ключі; для кожного доступного
    ключа — моделі цепочки ролі (крім перевантажених). Стан перечитується ліниво,
    тож якщо викликач під час ітерації поставить ключ у кулдаун (mark_429), решта
    моделей цього ключа пропускаються (квота на проект — спільна).
    """
    pool = role_key_pools().get(role, {"own": [], "borrow": []})
    models = role_model_chains().get(role, ["gemini-2.5-flash"])
    ordered_keys = list(pool.get("own", [])) + list(pool.get("borrow", []))
    for key_name in ordered_keys:
        kv = _key_value(key_name)
        if not kv:
            continue
        for model in models:
            now = timezone.now()
            if not is_available(key_name, now):
                break  # ключ у кулдауні → пропускаємо решту його моделей
            if is_model_overloaded(model, now):
                continue  # модель перевантажена → наступна модель цього ключа
            yield (key_name, kv, model)


def has_available_key(role: str, now: datetime.datetime | None = None) -> bool:
    now = now or timezone.now()
    pool = role_key_pools().get(role, {"own": [], "borrow": []})
    for key_name in list(pool.get("own", [])) + list(pool.get("borrow", [])):
        if _key_value(key_name) and is_available(key_name, now):
            return True
    return False


def soonest_cooldown(role: str, now: datetime.datetime | None = None) -> datetime.datetime | None:
    now = now or timezone.now()
    pool = role_key_pools().get(role, {"own": [], "borrow": []})
    times = []
    for key_name in list(pool.get("own", [])) + list(pool.get("borrow", [])):
        if not _key_value(key_name):
            continue
        st = GeminiKeyState.get(key_name)
        if st.cooldown_until and st.cooldown_until > now:
            times.append(st.cooldown_until)
    return min(times) if times else None


# ---------------------------------------------------------------------------
# Статус для UI
# ---------------------------------------------------------------------------
def primary_role_of(key_name: str) -> str:
    for role, pool in role_key_pools().items():
        if key_name in pool.get("own", []):
            return role
    for role, pool in role_key_pools().items():
        if key_name in pool.get("borrow", []):
            return role
    return ""


def pool_status(now: datetime.datetime | None = None) -> list[dict]:
    now = now or timezone.now()
    today_pt = now.astimezone(PT).date()
    out = []
    for key_name in ALL_KEYS:
        st = GeminiKeyState.get(key_name)
        available = (not st.cooldown_until) or st.cooldown_until <= now
        secs = 0
        if not available and st.cooldown_until:
            secs = max(0, int((st.cooldown_until - now).total_seconds()))
        requests_today = st.requests_today if st.day_date == today_pt else 0
        out.append({
            "key_name": key_name,
            "present": bool(_key_value(key_name)),
            "role": primary_role_of(key_name),
            "available": available,
            "cooldown_until": st.cooldown_until.isoformat() if st.cooldown_until else None,
            "cooldown_scope": st.cooldown_scope,
            "seconds_remaining": secs,
            "requests_today": requests_today,
            "last_status": st.last_status,
            "needs_topup": (st.cooldown_scope == "topup") and not available,
            "last_ok_at": st.last_ok_at.isoformat() if st.last_ok_at else None,
        })
    return out
