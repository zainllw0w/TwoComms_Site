"""Політика Telegram-алертів: не спам, з посиланнями, без загублених подій.

Скарга заказника: «сразу спам из 10 штук». Виміряно по коду:
`drain_manager_notifications(limit=10)` викликається в циклі демона кожні
1.5 секунди і всередині не має ні задержки, ні лічильника — тобто до 20
повідомлень за прохід, поки черга не спорожніє.

Три різні дефекти, які складались у цю картину.

**Потік без обмежень.** Обмеження існували лише в трьох точках із 31, і всі
пер-подієві. Глобального ліміту на **потік** не було, тому відновлення cron
платежів (`poll_pending_deals(limit=50)`) або lifecycle-воркер
(`limit=50`) вистрілювали пачкою.

**Дедуп, який одночасно спамить і губить.** 12 точок із 31 не передавали
`dedupe_key` і отримували `generic:sha256(text)`. Рядки `IgBotNotification`
не видаляються нічим, TTL немає. Наслідок двосторонній: різні клієнти дають
різний текст (пачка), а повтор того самого тексту не дійде **ніколи** — навіть
через місяць. Ключ мусить містити сущність і вікно часу, а не лише текст.

**Алерт без посилання.** Посилання в адмінку було у 2 повідомленнях із 31.
Найчастіше — ескалація «клієнту потрібен менеджер» — містило лише IGSID, тому
менеджер мусив шукати клієнта руками, хоча `client_id` був відомий рядком вище.

Модуль свідомо складається з чистих функцій політики: їх можна перевірити
тестами без черги, БД і Telegram. Інтеграція — на боці `notify_manager`.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Скільки алертів за хвилину допустимо. Шість — це «раз на десять секунд»:
# менеджер устигає читати, а справжній інцидент усе одно доїде за пару хвилин.
DEFAULT_MAX_PER_MINUTE = 6
FLOW_CACHE_KEY = "ig_alert_flow"
# Текст Telegram обрізаємо тим самим лімітом, що й раніше.
MAX_ALERT_CHARS = 3500


def management_base_url() -> str:
    from django.conf import settings

    return str(
        getattr(settings, "MANAGEMENT_BASE_URL", "") or "https://management.twocomms.shop"
    ).rstrip("/")


def client_admin_url(client_id) -> str:
    """Посилання на картку клієнта в CRM бота."""
    try:
        client_id = int(client_id)
    except (TypeError, ValueError):
        return ""
    return f"{management_base_url()}/bot/?client={client_id}" if client_id > 0 else ""


def deal_admin_url(deal_id) -> str:
    try:
        deal_id = int(deal_id)
    except (TypeError, ValueError):
        return ""
    return f"{management_base_url()}/bot/?deal={deal_id}" if deal_id > 0 else ""


def payment_review_admin_url(review_id) -> str:
    try:
        review_id = int(review_id)
    except (TypeError, ValueError):
        return ""
    return f"{management_base_url()}/bot/?payment_review={review_id}" if review_id > 0 else ""


def alert_dedupe_key(
    event_type: str,
    *,
    client_id=None,
    entity_id=None,
    window_minutes: int = 0,
    text: str = "",
) -> str:
    """Стабільний ключ дедупу з сущністю і, за потреби, вікном часу.

    Вікно — головна відмінність від колишнього `generic:sha256(text)`. Без нього
    повторна подія не доходила ніколи: рядок зі статусом `sent` глушив усі
    наступні спроби, а прибиральника в системи немає. З вікном алерт про ту саму
    проблему повертається наступного вікна, але не частіше.
    """
    parts = [str(event_type or "generic")[:40]]
    if client_id:
        parts.append(f"c{client_id}")
    if entity_id:
        parts.append(f"e{entity_id}")
    if window_minutes and window_minutes > 0:
        from django.utils import timezone

        bucket = int(timezone.now().timestamp() // (window_minutes * 60))
        parts.append(f"w{bucket}")
    if not client_id and not entity_id:
        digest = hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]
        parts.append(digest)
    return ":".join(parts)[:255]


def format_alert(title: str, *, lines=(), url: str = "", url_label: str = "") -> str:
    """Єдиний формат: заголовок, факти, посилання останнім рядком.

    `parse_mode` у цьому боті не використовується, тому розмітки тут немає
    свідомо — Markdown відрендерився б дослівно. Посилання переживає обрізку:
    якщо текст не влазить, ріжуться факти, а не найкорисніший рядок.
    """
    title = str(title or "").strip()
    body = [str(line).strip() for line in (lines or []) if str(line).strip()]
    tail = ""
    if url:
        tail = f"{url_label.strip()} {url}".strip() if url_label else str(url)

    def assemble(items):
        chunks = [title] if title else []
        chunks.extend(items)
        if tail:
            chunks.append(tail)
        return "\n".join(chunk for chunk in chunks if chunk)

    text = assemble(body)
    while len(text) > MAX_ALERT_CHARS and body:
        body.pop()
        text = assemble(body)
    return text[:MAX_ALERT_CHARS]


def should_send_now(sent_timestamps, *, now: datetime, max_per_minute: int = DEFAULT_MAX_PER_MINUTE) -> bool:
    """Чи можна відправити ще один алерт прямо зараз.

    Чиста функція: приймає мітки попередніх відправок і рішення приймає лише за
    ними. Так політику можна перевірити тестом без черги й кеша.
    """
    if max_per_minute <= 0:
        return True
    window_start = now - timedelta(minutes=1)
    recent = [item for item in (sent_timestamps or []) if item and item >= window_start]
    return len(recent) < max_per_minute


def throttle_gate(
    cache_key: str = FLOW_CACHE_KEY,
    *,
    max_per_minute: int = DEFAULT_MAX_PER_MINUTE,
    now: datetime | None = None,
) -> tuple[bool, int]:
    """Обгортка над `should_send_now` з мітками в кеші.

    Збій кеша не блокує відправку (fail-open): втратити алерт про інцидент
    гірше, ніж надіслати один зайвий. Але збій пишеться в лог, щоб «тихо
    вимкнений троттл» не став ще однією невидимою поломкою.
    """
    from django.utils import timezone

    now = now or timezone.now()
    try:
        raw = cache.get(cache_key) or []
        stamps = [item for item in raw if isinstance(item, datetime)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("ig alert throttle cache read failed: %r", exc)
        return True, 0
    if not should_send_now(stamps, now=now, max_per_minute=max_per_minute):
        oldest = min(stamps) if stamps else now
        retry_after = max(1, int(60 - (now - oldest).total_seconds()))
        return False, retry_after
    try:
        window_start = now - timedelta(minutes=1)
        stamps = [item for item in stamps if item >= window_start]
        stamps.append(now)
        cache.set(cache_key, stamps[-(max_per_minute * 2):], 120)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ig alert throttle cache write failed: %r", exc)
    return True, 0


def summarize_batch(event_type: str, items, *, limit: int = 5) -> str:
    """N однотипних подій — одне повідомлення зі зведенням.

    Потрібно там, де воркер обходить накопичену чергу: відновлення cron
    платежів і lifecycle віддають до 50 подій за прохід, і кожна ставала
    окремим повідомленням у Telegram.
    """
    values = [str(item).strip() for item in (items or []) if str(item).strip()]
    if not values:
        return ""
    head = values[:max(1, limit)]
    rest = len(values) - len(head)
    lines = [f"• {value}" for value in head]
    if rest > 0:
        lines.append(f"• і ще {rest}")
    return "\n".join(lines)
