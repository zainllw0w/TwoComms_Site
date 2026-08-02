"""Один мутатор стадії з явною таблицею переходів і чесним регресом.

IMP-032. До цього стадію писали 15 різних місць прямим присвоєнням
`client.stage = ...`, і `set_stage` глотала помилку запису події
(`except Exception: pass`). Наслідок F-STATE-004: 5 із 15 переходів не лишали
жодного сліду в таймлайні, тому питання «як клієнт опинився на цій стадії»
відповіді не мало.

Що тут вирішується і чого не було раніше.

**Напрямок переходу.** Раніше будь-який шар міг відкинути клієнта назад, і це
виглядало як помилка даних. Тепер рух назад можливий, але вимагає причини й
пишеться як `regress` — заказник прямо просив, щоб повернення по воронці було
видно й зафіксовано. Приклад законного регресу: гроші повернули, значить людина
більше не «оплачено».

**Хто має право.** Платіжні й фулфілмент-стадії (`paid`, `order_created`, `done`)
не може ставити модель — тільки перевірений факт від провайдера чи замовлення.
Це вже було в `_apply_stage` через `MODEL_HARD_STAGES`, але жило в іншому файлі
й тільки для тегів моделі; тут правило стає загальним.

**Термінальність.** `spam` і `cold` — не кінець воронки, а її пауза: клієнт може
повернутись, і тоді стадія має піднятись. А `done` після повернення грошей —
навпаки, більше не `done`.

Модуль навмисно не знає, *чому* саме змінюється стадія — причину передає
викликач. Це те саме рішення, що в журналі вибору: факти постачає той, хто їх
знає.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Стадії, які може ставити тільки перевірений факт (оплата провайдера,
# створене/виконане замовлення), але не модель і не аналіз діалогу.
FACT_ONLY_STAGES = frozenset({"paid", "order_created", "done"})

# Стадії поза лінійною воронкою: сюда можна прийти з будь-якого місця й
# повернутись назад, коли клієнт знову виходить на звʼязок.
SIDE_STAGES = frozenset({"lead_manager", "spam", "cold"})


@dataclass(frozen=True)
class StageTransition:
    """Результат спроби змінити стадію."""

    changed: bool
    from_stage: str
    to_stage: str
    direction: str = ""      # forward | regress | lateral
    refused: str = ""        # причина відмови, якщо changed=False


def _order() -> list[str]:
    from management.models import IgClient

    return [item.value for item in IgClient.FUNNEL_ORDER]


def stage_rank(stage: str) -> int:
    """Позиція стадії у воронці; -1 для стадій поза нею."""
    try:
        return _order().index(str(stage or ""))
    except ValueError:
        return -1


def direction_of(from_stage: str, to_stage: str) -> str:
    """forward / regress / lateral — без звернення до БД."""
    if from_stage == to_stage:
        return ""
    old_rank, new_rank = stage_rank(from_stage), stage_rank(to_stage)
    if old_rank < 0 or new_rank < 0:
        return "lateral"
    return "forward" if new_rank > old_rank else "regress"


def apply_stage(
    client,
    to_stage: str,
    *,
    reason: str,
    actor: str = "system",
    allow_regress: bool = False,
    fact_verified: bool = False,
) -> StageTransition:
    """Єдина точка зміни стадії.

    `reason` обовʼязковий: стадія без причини — це саме та ситуація, через яку
    неможливо було відповісти «як клієнт тут опинився».

    `allow_regress` вимагається явно. Рух назад — законна подія (повернення
    грошей, скасування), але вона не має траплятись випадково через те, що
    якийсь шар перерахував стадію з неповними даними.

    `fact_verified` потрібен для платіжних/фулфілмент-стадій: їх ставить лише
    перевірений факт, а не модель і не аналіз діалогу.
    """
    from management.models import IgClient

    if not client or not getattr(client, "pk", None):
        return StageTransition(False, "", str(to_stage or ""), refused="no_client")
    to_stage = str(to_stage or "")
    valid = {item.value for item in IgClient.Stage}
    if to_stage not in valid:
        return StageTransition(False, str(client.stage or ""), to_stage, refused="unknown_stage")
    if not str(reason or "").strip():
        return StageTransition(False, str(client.stage or ""), to_stage, refused="reason_required")

    from_stage = str(client.stage or "")
    if from_stage == to_stage:
        return StageTransition(False, from_stage, to_stage, refused="same_stage")

    if to_stage in FACT_ONLY_STAGES and not fact_verified:
        return StageTransition(False, from_stage, to_stage, refused="fact_required")

    direction = direction_of(from_stage, to_stage)
    if direction == "regress" and not allow_regress:
        return StageTransition(False, from_stage, to_stage, direction, refused="regress_not_allowed")

    # Повернення з бічної стадії (`cold`, `spam`, `lead_manager`) у воронку —
    # це не регрес: клієнт просто знову в діалозі.
    try:
        client.set_stage(to_stage, reason=f"{actor}:{reason}"[:255])
    except Exception as exc:  # noqa: BLE001
        logger.warning("stage transition failed for client %s: %r", client.pk, exc)
        return StageTransition(False, from_stage, to_stage, direction, refused="write_failed")
    return StageTransition(True, from_stage, to_stage, direction)


def regress_stage(client, to_stage: str, *, reason: str, actor: str = "system") -> StageTransition:
    """Явний відкат назад по воронці. Причина обовʼязкова.

    Головний сценарій — повернення або реверс платежу: людина перестала бути
    «оплачено», і CRM має це показувати. Раніше стадія лишалась `paid`, а поруч
    зʼявлялась псевдо-стадія `payment_reversed`, якої немає в переліку —
    F-STATE-003.
    """
    return apply_stage(
        client,
        to_stage,
        reason=reason,
        actor=actor,
        allow_regress=True,
        fact_verified=True,
    )
