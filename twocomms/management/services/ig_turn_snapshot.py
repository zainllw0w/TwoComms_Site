"""Один контекстный снимок вместо N+1 запросов (Э8.5).

**Замер** (SQLite, локально; фикстура — `management/tests_ig_turn_snapshot.py`):
сборка `assemble_system_instruction()` для одного хода — **29 SQL-запросов до
правки, 17 после**. Текст промпта побайтово тот же.

Повторные чтения одной и той же строки, которые и составляли разницу:

    4x management_igpostsalecase        open_service_case
    4x management_igfunnelresetaudit    граница сброса воронки
    3x management_igdeal                client_has_verified_payment
    2x management_igclient              указатель текущего эпизода
    2x management_igpaymentconfirmationreview \
    2x management_igorderassignment      | client_has_confirmed_purchase
    2x management_igorderattribution    /

`management_igfunnelresetaudit` — самый показательный случай: `current_message_floor`
вызывается из истории, языка, памяти и объекций, и каждый раз заново читает границу
сброса, которая **в пределах одного хода не может измениться**.

**Что здесь сделано и чего сознательно не сделано.** Это не переписывание сборки
промпта: изоляция ошибок по блокам (`_prompt_section`) — правильное свойство, и
она сохраняется. Здесь только кэш на время области: значения, которые физически
неизменны внутри неё, читаются один раз.

Областей две, и это главное решение модуля. Ход демона живёт до двух минут, и за
это время оплату может подтвердить вебхук в **другом процессе**. Поэтому платёжная
истина кэшируется только на **сборку промпта** (`prompt_snapshot`), а на весь ход —
лишь то, что ход не может увидеть изменившимся иначе как своей же записью
(`turn_snapshot` + `invalidate`). Подробнее — у `prompt_snapshot` ниже.

Кэш живёт в `ContextVar`, а не в объекте: сборка промпта проходит через десяток
независимых функций, часть из которых не получает клиента параметром. Передавать
снимок через все подписи означало бы менять контракт функций, которые к
производительности отношения не имеют. `ContextVar` безопасен в потоках демона:
новый поток начинает с пустого контекста.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

_EMPTY: dict = {}
# Две области с разным временем жизни: ход демона и одна сборка промпта.
# Почему их две, а не одна — в комментарии к `prompt_snapshot` ниже.
_snapshot: ContextVar[dict] = ContextVar("ig_turn_snapshot", default=_EMPTY)
_prompt: ContextVar[dict] = ContextVar("ig_prompt_snapshot", default=_EMPTY)


@contextmanager
def turn_snapshot():
    """Открыть область одного хода: неизменные значения читаются один раз."""
    token = _snapshot.set({})
    try:
        yield _snapshot.get()
    finally:
        _snapshot.reset(token)


def active() -> bool:
    return _snapshot.get() is not _EMPTY


def cached(key: str, producer):
    """Вернуть значение из снимка хода или посчитать и запомнить.

    Вне области хода вызывает `producer` напрямую — то есть поведение по
    умолчанию не меняется, и любой вызывающий код работает как раньше.
    """
    store = _snapshot.get()
    if store is _EMPTY:
        return producer()
    if key in store:
        return store[key]
    value = producer()
    store[key] = value
    return value


def invalidate(prefix: str = "") -> None:
    """Сбросить часть снимка после записи, меняющей факт внутри хода.

    Нужно там, где ход сам меняет состояние: закрепление товара, создание
    proposal. Без этого снимок отдал бы устаревшее значение уже после записи.

    Чистит **обе** области — ход и сборку промпта, — чтобы имя не обманывало:
    вызывающий просит забыть факт, а не угадывать, в какой из областей он лежит.
    """
    for store in (_snapshot.get(), _prompt.get()):
        if store is _EMPTY:
            continue
        if not prefix:
            store.clear()
            continue
        for key in [name for name in store if name.startswith(prefix)]:
            store.pop(key, None)


def stats() -> dict:
    store = _snapshot.get()
    return {"active": store is not _EMPTY, "entries": len(store) if store else 0}


# --- Область одной сборки промпта -------------------------------------------
#
# Э8.5, уточнение по замеру. План говорил «снимок клиента на ход», но замер
# показал, что **все** повторные чтения происходят внутри одной сборки промпта:
# `open_service_case` — 4 раза, `client_has_confirmed_purchase` — 2,
# `client_has_verified_payment` — 3, указатель эпизода — 2. Ни одного повтора
# между сборкой промпта и остальным ходом нет.
#
# Поэтому платёжная истина кэшируется **на сборку промпта**, а не на ход. Ход
# длится до `declared_turn_budget_seconds()` (~2 минуты), и за это время оплату
# может подтвердить вебхук в **другом процессе** — сигналы ORM такое не увидят.
# Кэш на ход означал бы, что `payment_link_allowed` после генерации ответа
# опирается на устаревшее «оплаты нет» и выдаёт второй инвойс уже оплаченному
# клиенту. Внутри сборки промпта такого риска нет: она только читает, длится
# миллисекунды, и промпт по своей природе — срез одного момента.


@contextmanager
def prompt_snapshot():
    """Открыть область одной сборки промпта."""
    token = _prompt.set({})
    try:
        yield _prompt.get()
    finally:
        _prompt.reset(token)


def prompt_cached(key: str, producer):
    """Как `cached`, но время жизни — одна сборка промпта.

    Вне области сборки вызывает `producer` напрямую: любой другой вызывающий
    код (карточка менеджера, follow-up, аналитика) работает как раньше.
    """
    store = _prompt.get()
    if store is _EMPTY:
        return producer()
    if key in store:
        return store[key]
    value = producer()
    store[key] = value
    return value


def turn_or_prompt_cached(key: str, producer):
    """Кэш в самой широкой из открытых областей.

    Граница эпизода неизменна и внутри хода, и внутри одной сборки промпта.
    Демон открывает ход — и читает её один раз на весь ход. Превью промпта в
    админке или тест хода не открывают, и без этой развилки та же граница
    читалась бы там четыре раза: из истории, языка, памяти и объекций.
    """
    if _snapshot.get() is not _EMPTY:
        return cached(key, producer)
    return prompt_cached(key, producer)
