"""Одне поняття ходу клієнта для трьох механізмів (Э0.6).

Три різні механізми потребують відповіді на питання «це один логічний хід чи
кілька?»:

* Э2.2 — burst клієнта не має давати кілька відповідей;
* Э2.11 — дублюючий webhook без `mid` не має давати другу строку;
* Э3.6 — provenance відповіді мусить назвати ВСІ вхідні, на які вона відповідає.

Роздільні реалізації дали б три неузгоджені механізми дедуплікації. Найгірший
випадок — burst із двох повідомлень, де одне задубльоване провайдером, — не
обробив би правильно жоден з них.

**Про величину debounce.** Свідомо взято мале фіксоване значення, а НЕ виведене
з поточної метрики `messages-per-turn`: та метрика описує поведінку системи, яка
ще не склеює ходи, і нічого не доводить про оптимальну затримку. Правильний шлях —
почати з малого, зміряти вплив на конверсію і на час до першої відповіді,
коригувати за даними.

Цей модуль **записує** ходи і вміє відповісти, чи хід готовий до обробки, але сам
не змінює порядок обробки черги: перехід воркера на хід як одиницю виконання — це
Э2.2 за окремим флагом. Розділення зроблено свідомо: спочатку поняття стає
вимірюваним, потім змінюється поведінка.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from management.models import (
    IgCustomerTurn,
    IgTurnMessage,
    InstagramBotMessage,
)

# Мале фіксоване вікно склейки. Не виводити з метрики поточної поведінки.
TURN_DEBOUNCE = timedelta(seconds=6)
# Верхня межа очікування. Пряме питання мусить отримати відповідь у розумний час,
# навіть якщо клієнт продовжує друкувати. Точний SLA — Э0.7; поки що записане
# допущення, а не виміряне значення.
MAX_TURN_WAIT = timedelta(seconds=20)


@dataclass(frozen=True)
class TurnAttachment:
    """Результат прив'язки вхідного до ходу."""

    turn: IgCustomerTurn
    created: bool
    attached: bool
    reason: str = ""


def _flag(name: str, default: bool) -> bool:
    from management.services.ig_provider_incidents import flag

    return flag(name, default)


def message_dedupe_key(row: InstagramBotMessage) -> str:
    """Найстійкіша доступна ідентичність повідомлення.

    Порядок навмисний: native `mid` провайдера → provider object id вкладення →
    синтетичний ключ. Підписані media URL одноразові, тому вони НЕ є
    ідентичністю: саме через них повтор того самого вкладення з новим підписом
    давав другу строку (Э2.11).
    """
    mid = str(getattr(row, "mid", "") or "").strip()
    if mid:
        return f"mid:{mid}"
    attachment_id = _provider_attachment_object_id(row)
    if attachment_id:
        return f"object:{attachment_id}"
    synthetic = str(getattr(row, "synthetic_event_key", "") or "").strip()
    if synthetic:
        return f"synthetic:{synthetic}"
    return f"row:{getattr(row, 'pk', '') or ''}"


def _provider_attachment_object_id(row) -> str:
    """Native provider object id вкладення, якщо провайдер його дав."""
    media = getattr(row, "attachment_media", None)
    if not isinstance(media, list):
        return ""
    for item in media:
        if not isinstance(item, dict):
            continue
        for key in ("provider_object_id", "object_id", "attachment_id", "asset_id"):
            value = str(item.get(key) or "").strip()
            if value:
                return value
    return ""


def bypasses_debounce(row: InstagramBotMessage) -> bool:
    """Ходи, які не можна затримувати.

    Натискання кнопки — завершена дія, а не частина набору тексту. Явний opt-out
    і запит менеджера теж не мають чекати: затримка тут це не склейка, а
    ігнорування.
    """
    if str(getattr(row, "quick_reply_payload", "") or "").strip():
        return True
    text = str(getattr(row, "text", "") or "")
    if not text:
        return False
    from management.services.bot_sales_classifier import OPT_OUT_RE, SUPPORT_RE

    return bool(OPT_OUT_RE.search(text) or SUPPORT_RE.search(text))


def _event_at(row: InstagramBotMessage):
    return getattr(row, "provider_created_at", None) or getattr(row, "created_at", None)


def ensure_turn_for_inbound(
    row: InstagramBotMessage,
    *,
    now=None,
) -> TurnAttachment | None:
    """Прив'язати вхідне до відкритого ходу або відкрити новий.

    Дедлайн ходу фіксується від ПЕРШОГО повідомлення і не продовжується
    наступними. Інакше клієнт, який продовжує писати, ніколи не отримав би
    відповіді — і склейка перетворилась би на молчання.
    """
    if not _flag("IG_CUSTOMER_TURNS", True):
        return None
    client_id = getattr(row, "client_id", None)
    if not client_id or getattr(row, "role", "") != InstagramBotMessage.Role.USER:
        return None
    now = now or _event_at(row) or timezone.now()
    dedupe_key = message_dedupe_key(row)
    bypass = bypasses_debounce(row)

    with transaction.atomic():
        existing = (
            IgTurnMessage.objects.select_related("turn")
            .filter(message_id=row.pk)
            .first()
        )
        if existing is not None:
            # Дублюючий webhook того самого рядка. Другої строки не буде.
            return TurnAttachment(existing.turn, False, False, "already_attached")

        open_turn = (
            IgCustomerTurn.objects.select_for_update()
            .filter(
                client_id=client_id,
                claim_state=IgCustomerTurn.ClaimState.OPEN,
                window_deadline__gt=now,
            )
            .order_by("-id")
            .first()
        )
        if open_turn is not None and not open_turn.bypass_debounce:
            keys = list(open_turn.dedupe_keys or [])
            if dedupe_key in keys:
                # Те саме вкладення з новим підписом URL: інший рядок, та сама
                # ідентичність провайдера. Другого повідомлення в ході не буде.
                return TurnAttachment(open_turn, False, False, "duplicate_identity")
            ordinal = int(open_turn.message_count or 0) + 1
            try:
                IgTurnMessage.objects.create(
                    turn=open_turn,
                    message_id=row.pk,
                    ordinal=ordinal,
                    role=row.role,
                )
            except IntegrityError:
                return TurnAttachment(open_turn, False, False, "attach_race")
            keys.append(dedupe_key)
            open_turn.dedupe_keys = keys[:50]
            open_turn.message_count = ordinal
            if bypass:
                # Кнопка або opt-out посеред burst-у: хід більше не чекає.
                open_turn.bypass_debounce = True
            open_turn.save(update_fields=[
                "dedupe_keys", "message_count", "bypass_debounce", "updated_at",
            ])
            return TurnAttachment(open_turn, False, True, "attached")

        deadline = now + (timedelta(0) if bypass else TURN_DEBOUNCE)
        try:
            turn = IgCustomerTurn.objects.create(
                client_id=client_id,
                episode_id=getattr(row.client, "current_commercial_episode_id", None)
                if getattr(row, "client", None) is not None
                else None,
                primary_source_message_id=row.pk,
                window_started_at=now,
                window_deadline=min(deadline, now + MAX_TURN_WAIT),
                dedupe_keys=[dedupe_key],
                message_count=1,
                bypass_debounce=bypass,
            )
        except IntegrityError:
            turn = IgCustomerTurn.objects.filter(primary_source_message_id=row.pk).first()
            if turn is None:
                return None
            return TurnAttachment(turn, False, False, "create_race")
        IgTurnMessage.objects.create(
            turn=turn, message_id=row.pk, ordinal=1, role=row.role
        )
        return TurnAttachment(turn, True, True, "created")


def turn_is_due(turn: IgCustomerTurn, *, now=None) -> bool:
    """Чи готовий хід до обробки."""
    if turn is None or turn.claim_state != IgCustomerTurn.ClaimState.OPEN:
        return False
    now = now or timezone.now()
    if turn.bypass_debounce:
        return True
    return now >= turn.window_deadline


def due_turn_ids(*, limit: int = 10, now=None) -> list:
    now = now or timezone.now()
    from django.db.models import Q

    return list(
        IgCustomerTurn.objects.filter(
            claim_state=IgCustomerTurn.ClaimState.OPEN,
            client__hidden_at__isnull=True,
        )
        .filter(Q(bypass_debounce=True) | Q(window_deadline__lte=now))
        .order_by("window_deadline", "id")
        .values_list("id", flat=True)[: max(1, int(limit))]
    )


def claim_turn(turn_id: int, *, now=None) -> tuple[IgCustomerTurn | None, str]:
    """Атомарний claim ходу; повертає (хід, токен) або (хід, "")."""
    now = now or timezone.now()
    token = secrets.token_hex(16)
    claimed = IgCustomerTurn.objects.filter(
        pk=turn_id, claim_state=IgCustomerTurn.ClaimState.OPEN
    ).update(
        claim_state=IgCustomerTurn.ClaimState.CLAIMED,
        claimed_at=now,
        claim_token=token,
        updated_at=now,
    )
    turn = IgCustomerTurn.objects.filter(pk=turn_id).first()
    return turn, (token if claimed == 1 else "")


def mark_turn_processed(turn_id: int, *, now=None) -> None:
    now = now or timezone.now()
    IgCustomerTurn.objects.filter(pk=turn_id).exclude(
        claim_state=IgCustomerTurn.ClaimState.PROCESSED
    ).update(
        claim_state=IgCustomerTurn.ClaimState.PROCESSED,
        processed_at=now,
        claim_token="",
        updated_at=now,
    )


def turn_message_ids(turn: IgCustomerTurn) -> list:
    """Усі source-повідомлення ходу в порядку надходження (для provenance Э3.6)."""
    return list(
        IgTurnMessage.objects.filter(turn_id=getattr(turn, "pk", turn))
        .order_by("ordinal", "id")
        .values_list("message_id", flat=True)
    )


def messages_per_turn(*, days: int = 7) -> dict:
    """Метрика Э0.6: скільки повідомлень у ході насправді.

    Знаменник — ходи, числитель — повідомлення. Окремо повертається розподіл,
    щоб побачити не тільки середнє: burst-и рідкі, і середнє їх приховує.
    """
    from collections import Counter

    since = timezone.now() - timedelta(days=max(1, int(days)))
    counts = list(
        IgCustomerTurn.objects.filter(created_at__gte=since).values_list(
            "message_count", flat=True
        )
    )
    if not counts:
        return {"turns": 0, "messages": 0, "avg": 0.0, "distribution": {}}
    distribution = dict(sorted(Counter(counts).items()))
    return {
        "turns": len(counts),
        "messages": sum(counts),
        "avg": round(sum(counts) / len(counts), 3),
        "distribution": distribution,
    }
