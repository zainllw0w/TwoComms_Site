"""Э2.8 — свіжі повідомлення не мають морити старі голодом.

**Що саме ламалось.** `_claim_next()` і `due_turn_for_claim()` сортують за
`-conversation_priority_at` / `-window_started_at`, тобто найсвіжіше першим. Для
інтерактивності це вірний вибір, і його не треба скасовувати. Але при
безперервному потоці нових повідомлень старий pending-рядок може лишатись нижче
голови черги **необмежено довго**: ніякої верхньої межі очікування не існувало.

**Чому це дорожче, ніж здається.** Голодують саме дорогі діалоги. Клієнт, який
написав раніше і чекає, з більшою ймовірністю в середині воронки — товар уже
обраний, він чекає відповідь про розмір або посилання на оплату. Свіжий потік —
переважно перші дотики. Тобто механізм систематично віддає перевагу холодним
клієнтам над гарячими.

**Звідки взято потолок віку, і чому саме він.** Потолок не вигаданий, він
виведений з `customer_notice_threshold_seconds()` — моменту, раніше якого
технічний текст клієнту шкідливий (Э-Б). Логіка: якщо рядок чекає довше цього
порогу, клієнт вже перейшов у зону, де система сама вважає доречним сказати «є
технічна затримка». Морити його голодом ДАЛІ цього моменту — строго гірше, ніж
відповісти. Тому один і той самий бюджет ходу задає і момент вибачення, і момент,
коли справедливість перемагає інтерактивність. Незалежне число тут розійшлось би
з бюджетом при першій же правці таймауту — саме та помилка, через яку вікно
живості демона було меншим за бюджет ходу (Э2.10).

**Що НЕ робить цей модуль.** Він не обходить takeover, opt-out, приховування
клієнта і межу вікна Meta: він лише впорядковує кандидатів, які і без нього мають
право на обробку. Він також не змінює single-flight на клієнта — за це відповідає
наявна аренда `automation_lease_*`.
"""
from __future__ import annotations

# Ранг стадії воронки для розв'язання рівного віку. Пункт вимагає: при рівному
# віці клієнт на `checkout` дорожчий за клієнта на `new`. Спам і холодні —
# найнижчі, бо для них швидкість відповіді нічого не вирішує.
_STAGE_RANK = {
    "payment_pending": 90,
    "checkout": 85,
    "product_matched": 75,
    "paid": 70,
    "order_created": 65,
    "qualifying": 55,
    "lead_manager": 50,
    "new": 40,
    "done": 20,
    "cold": 10,
    "spam": 0,
}
DEFAULT_STAGE_RANK = 40


def stage_rank(stage) -> int:
    """Ранг стадії; невідома стадія отримує ранг `new`, а не нуль.

    Нуль для невідомого означав би «ніколи не піднімати», і одна нова стадія в
    enum-і тихо створила б клас клієнтів, яких черга не піднімає за віком.
    """
    return int(_STAGE_RANK.get(str(stage or "").strip(), DEFAULT_STAGE_RANK))


def stage_rank_cases():
    """`Case`-вираз рангу стадії для сортування на боці БД."""
    from django.db.models import Case, IntegerField, Value, When

    whens = [
        When(client__stage=name, then=Value(rank))
        for name, rank in _STAGE_RANK.items()
    ]
    return Case(*whens, default=Value(DEFAULT_STAGE_RANK), output_field=IntegerField())


def age_ceiling_seconds() -> float:
    """Скільки рядок має право чекати, перш ніж вік переможе свіжість.

    Виведено з бюджету ходу, а не задано окремо — обґрунтування в docstring
    модуля. Нижня межа 60 с страхує від конфігурації, у якій бюджет
    підозріло малий: потолок менший за хвилину зробив би чергу майже FIFO і
    прибрав би інтерактивність, якої пункт не скасовує.
    """
    try:
        from management.services.ig_turn_budget import (
            customer_notice_threshold_seconds,
        )

        return max(60.0, float(customer_notice_threshold_seconds()))
    except Exception:
        return 60.0


def starvation_enabled() -> bool:
    """Э2.8 «Откат»: флаг на алгоритм сортування."""
    try:
        from management.services.ig_provider_incidents import flag

        return flag("IG_QUEUE_AGE_CEILING", True)
    except Exception:
        return True


def queue_age_report(*, now=None) -> dict:
    """Базова метрика віку черги (read-only, знімається ДО правки і після).

    Повертає p50/p95/p99, максимум і число випадків голодування — рядків, які
    чекають довше потолка. Без цього числа «стало краще» недоказуемо.
    """
    from django.db.models.functions import Coalesce
    from django.utils import timezone

    from management.models import InstagramBotMessage

    now = now or timezone.now()
    ceiling = age_ceiling_seconds()
    rows = list(
        InstagramBotMessage.objects.filter(
            role=InstagramBotMessage.Role.USER,
            status=InstagramBotMessage.Status.PENDING,
            client__hidden_at__isnull=True,
        )
        .annotate(queued_at=Coalesce("provider_created_at", "created_at"))
        .values_list("queued_at", flat=True)
    )
    ages = sorted(
        max(0.0, (now - queued_at).total_seconds()) for queued_at in rows if queued_at
    )

    def pct(fraction: float) -> float:
        if not ages:
            return 0.0
        index = min(len(ages) - 1, int(round(fraction * (len(ages) - 1))))
        return round(ages[index], 3)

    starving = [age for age in ages if age > ceiling]
    return {
        "pending": len(ages),
        "age_ceiling_seconds": round(ceiling, 3),
        "p50_seconds": pct(0.50),
        "p95_seconds": pct(0.95),
        "p99_seconds": pct(0.99),
        "max_seconds": round(ages[-1], 3) if ages else 0.0,
        "starving": len(starving),
        "starving_max_seconds": round(max(starving), 3) if starving else 0.0,
    }
