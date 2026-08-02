"""Реєстр наших власних вихідних повідомлень — щоб не прийняти їх за менеджера.

Причина існування — прод-інцидент 02.08.2026, клієнт #5. Бот надіслав каруселлю
два фото товарів. Meta повернула echo цих фото, і система порахувала їх
повідомленнями живого менеджера: увімкнула `manager_takeover`, поставила
`bot_paused=True`, погасила чергу клієнта і замовкла. Наступне «Давай первую»
отримало `observed` замість відповіді, і клієнт писав двічі.

Чому старий захист не спрацював: `_bot_sent_key` рахує відпечаток від **тексту**
повідомлення, а в медіа-echo тексту немає взагалі — умова
`if text and cache.get(...)` завжди хибна. Плюс `send_catalog_media` ніколи не
реєструвала відправлене, хоча `message_id` від Meta вже отримувала і викидала.

Надійна ознака «це наше» — `message_id`, який Meta повертає у відповіді Send API
і потім присилає в echo як `message.mid`. Він і став основним ключем. Текстовий
відпечаток лишається другим шаром для сумісності зі старими записами в кеші.

Свідомий вибір: реєстр живе і в кеші (швидко), і в БД (переживає перезапуск і
евікшн). Кеш сам по собі недостатній — F-DEBT-004 уже відзначала, що збій кеша
дає хибний takeover, і саме це тут і сталося б навіть для тексту.
"""
from __future__ import annotations

import hashlib
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Вікно тримаємо широким: echo від Meta приходило через ~58 секунд, але
# затримка не гарантована, а ціна помилки — бот замовкає до ручного втручання.
OUTGOING_TTL_SECONDS = 6 * 3600
_CACHE_PREFIX = "ig_out_mid:"


def _cache_key(message_id: str) -> str:
    digest = hashlib.md5(str(message_id or "").encode("utf-8")).hexdigest()[:20]
    return _CACHE_PREFIX + digest


def register_outgoing(message_id: str, *, recipient_id: str = "", kind: str = "text") -> bool:
    """Запам'ятати, що це повідомлення надіслали ми.

    Викликається одразу після успішного запиту до Meta — по одному на кожен
    надісланий елемент, а не пачкою в кінці. Echo першого фото може прийти ще
    до того, як відправиться друге, і тоді пізня реєстрація не допоможе.
    """
    message_id = str(message_id or "").strip()
    if not message_id:
        return False
    try:
        cache.set(_cache_key(message_id), kind or "text", OUTGOING_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001 - кеш не єдиний шар
        logger.warning("ig outgoing registry cache write failed: %r", exc)
    return True


def is_our_outgoing(message_id: str) -> bool:
    """Чи це message_id надіслали ми (кеш, потім БД)."""
    message_id = str(message_id or "").strip()
    if not message_id:
        return False
    try:
        if cache.get(_cache_key(message_id)):
            return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ig outgoing registry cache read failed: %r", exc)
    # Друга лінія: рядок нашого вихідного повідомлення в історії діалогу.
    # Переживає перезапуск кеша, а саме на кеші й будувався колишній захист.
    try:
        from management.models import InstagramBotMessage

        return InstagramBotMessage.objects.filter(
            provider_message_id=message_id,
            role=InstagramBotMessage.Role.MODEL,
        ).exists()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ig outgoing registry db read failed: %r", exc)
        return False
