"""Э0.7 — SLO пути клиента: одна метрика, которой судится весь roadmap.

**Зачем отдельный модуль, а не ещё одна панель здоровья.** Все прежние метрики
были покомпонентными: heartbeat демона, состояние ключей Gemini, счётчики
инцидентов. Каждая из них могла быть зелёной одновременно с тем, что клиент не
получил ответа вообще. Поэтому здесь считается не «работает ли компонент», а
«дошёл ли до клиента корректный финальный исход».

**Различение, без которого метрика будет врать.** Есть два РАЗНЫХ понятия, и
смешивать их нельзя:

``terminal_disposition``
    процесс завершился. Это наблюдение о СИСТЕМЕ. `unknown`-доставка — валидный
    terminal_disposition: система знает, что больше ничего не сделает.

``correct_final_outcome``
    клиент получил корректный результат. Это наблюдение о КЛИЕНТЕ. `unknown`
    сюда не входит НИКОГДА: неизвестная доставка — это не доставка.

Если считать их вместе, метрика покажет благополучие ровно в тот момент, когда
провайдер молчит и никто не знает, дошло ли сообщение.

**Почему числитель — только `delivered`, и почему это не занижение.** Соблазн
велик: добавить в числитель `no_send_needed` («мы правильно промолчали»), и
метрика сразу станет красивой. Именно этого делать нельзя. Система сама решает,
нужен ли ответ; если её решение попадает в числитель, то баг, который глушит
ВСЕ ответы, поднимет метрику до 100%. Метрика, которую можно улучшить, перестав
отвечать клиентам, хуже отсутствия метрики. Поэтому подавление ответа всегда
УХУДШАЕТ основной показатель, а `no_send_needed` показывается отдельной долей —
как объяснение разрыва, а не как успех.

**Почему `unclassified` — отдельная корзина, а не «прочее».** Ход, закрытый без
типизированной причины (историческая строка до миграции `terminal_reason`, либо
новая ветка рантайма, которая причину не пишет), нельзя ни считать успехом, ни
тихо приписать к «ответ не требовался». Пустая причина — это отсутствие знания,
и оно должно быть видно оператору цифрой. Если рантайм перестанет писать
причину, `unclassified` вырастет, и метрику станет нельзя защищать — это и есть
свойство фальсифицируемости.

**Что здесь считается «блокировкой политикой».** Реального типизированного поля
«почему не отправили» на ходе нет (см. `POLICY_REASON_NOT_RECORDED`). Но часть
блокировок восстанавливается из durable `InstagramBotMessage.send_state`:
`cancelled` — сменилась epoch разрешения (пауза/перехват менеджером),
`duplicate` — подавлен повтор. Эти две ветки рантайм пишет в БД, поэтому они
вынимаются из `no_reply_needed` и НЕ выглядят как «ответ не требовался».

**Три трассы, три единицы наблюдения.** Одно агрегированное число по всем путям
запрещено пунктом: пути имеют разную цену ошибки и разные знаменатели.

============= ============================ ===============================
путь          единица (строка знаменателя)  что значит «дошло»
============= ============================ ===============================
sales_reply   `IgCustomerTurn`              квитанция провайдера на ответ
human_handoff `IgBotNotification` (клиент)  человек реально получил алерт
lifecycle_    `IgLifecycleEvent`            post-purchase сообщение доставлено
event
============= ============================ ===============================

Модуль строго read-only: ни одной записи, ни одной миграции, ни одного нового
поля. Это проекция над данными, которые рантайм уже пишет.
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings as django_settings
from django.db.models import Count
from django.utils import timezone

from management.models import (
    IgBotNotification,
    IgClient,
    IgCustomerTurn,
    IgLifecycleEvent,
    IgTurnMessage,
)

REPORT_TIMEZONE = "Europe/Kyiv"
DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 90

# --- Пути -------------------------------------------------------------------
PATH_SALES_REPLY = "sales_reply"
PATH_HUMAN_HANDOFF = "human_handoff"
PATH_LIFECYCLE_EVENT = "lifecycle_event"
PATHS = (PATH_SALES_REPLY, PATH_HUMAN_HANDOFF, PATH_LIFECYCLE_EVENT)

# --- Общий словарь исходов --------------------------------------------------
# Один словарь на все три пути. Это не косметика: пункт требует, чтобы UI, отчёт
# и решение о выкате давали ОДИНАКОВЫЕ числитель и знаменатель. Разные наборы
# корзин по путям — это три источника истины, то есть три разных числа.
OUTCOME_DELIVERED = "delivered"
OUTCOME_DELIVERED_THEN_ESCALATED = "delivered_then_escalated"
OUTCOME_NO_SEND_NEEDED = "no_send_needed"
OUTCOME_SUPPRESSED_DUPLICATE = "suppressed_duplicate"
OUTCOME_POLICY_BLOCKED = "policy_blocked"
OUTCOME_HUMAN_CASE = "human_case"
OUTCOME_UNKNOWN = "unknown"
OUTCOME_FAILED = "failed"
OUTCOME_EVIDENCE_LOST = "evidence_lost"
OUTCOME_ABANDONED = "abandoned"
OUTCOME_SUPERSEDED = "superseded"
OUTCOME_UNCLASSIFIED = "unclassified"
OUTCOME_OPEN_WITHIN_SLA = "open_within_sla"
OUTCOME_OVERDUE = "overdue"

# Терминальные корзины: процесс больше ничего не сделает сам.
TERMINAL_OUTCOMES = (
    OUTCOME_DELIVERED,
    OUTCOME_DELIVERED_THEN_ESCALATED,
    OUTCOME_NO_SEND_NEEDED,
    OUTCOME_SUPPRESSED_DUPLICATE,
    OUTCOME_POLICY_BLOCKED,
    OUTCOME_HUMAN_CASE,
    OUTCOME_UNKNOWN,
    OUTCOME_FAILED,
    OUTCOME_EVIDENCE_LOST,
    OUTCOME_ABANDONED,
    OUTCOME_SUPERSEDED,
    OUTCOME_UNCLASSIFIED,
)
# Ещё живые корзины. `overdue` живая по состоянию, но это уже нарушенный SLO.
OPEN_OUTCOMES = (OUTCOME_OPEN_WITHIN_SLA, OUTCOME_OVERDUE)
ALL_OUTCOMES = TERMINAL_OUTCOMES + OPEN_OUTCOMES

# Единственная корзина числителя `correct_final_outcome`. Список, а не одна
# строка, чтобы расширение было видно ревьюеру как правка контракта.
CORRECT_OUTCOMES = (OUTCOME_DELIVERED,)

# Корзины, где клиенту сообщение и не причиталось. Они исключаются ТОЛЬКО из
# вспомогательного `answer_rate_when_owed`, но остаются в основном знаменателе.
NOT_OWED_OUTCOMES = (
    OUTCOME_NO_SEND_NEEDED,
    OUTCOME_SUPPRESSED_DUPLICATE,
    OUTCOME_SUPERSEDED,
)

# Явная метка того, что причина блокировки нигде не записана. Не «other»:
# оператор должен отличать «политика сработала по такой-то причине» от «мы не
# знаем, почему не отправили».
POLICY_REASON_NOT_RECORDED = "not_recorded"

# --- Когорты ----------------------------------------------------------------
# Когорта — это ЦЕНА ошибки для клиента, а не сегмент маркетинга. Регрессия в
# `money_in_flight` и `paid` блокирует выкат политики; в `prospect` — нет.
#
# Осознанная неточность, которую нельзя прятать: когорта берётся из ТЕКУЩЕЙ
# стадии `IgClient`, а не из стадии на момент хода. Стадия на момент хода нигде
# не привязана к ходу (`IgClientStageEvent` пишется по клиенту и времени, без
# ссылки на ход), поэтому это единственный доступный durable признак. В отчёте
# оговорка выводится рядом с цифрами.
COHORT_MONEY_IN_FLIGHT = "money_in_flight"
COHORT_PAID = "paid"
COHORT_HANDOFF = "handoff"
COHORT_PROSPECT = "prospect"
COHORTS = (COHORT_MONEY_IN_FLIGHT, COHORT_PAID, COHORT_HANDOFF, COHORT_PROSPECT)
# Когорты, регрессия в которых останавливает выкат новой автоматики.
CRITICAL_COHORTS = (COHORT_MONEY_IN_FLIGHT, COHORT_PAID)

# --- Человеческие кейсы -----------------------------------------------------
# Типы алертов, в которых КОНКРЕТНЫЙ клиент заблокирован и ждёт человека. Набор
# перечислен явно, а не выведен «по вхождению review»: инфраструктурные алерты
# (`ig_daemon_stalled`, `catalog_build_failed`, `ig_task_failure`) не относятся к
# пути клиента, и их попадание в знаменатель разбавило бы метрику до
# бессмысленности. Дополнительная защита — требование непустого `client_id`.
HUMAN_CASE_EVENT_TYPES = frozenset({
    "escalation",
    "takeover",
    "payment_review",
    "payment_link_delivery_review",
    "payment_reversed_review",
    "orphan_provider_payment_review",
    "superseded_invoice_payment",
    "paylink_failed",
    "paylink_price_gate",
    "paylink_prepay_gate",
    "paylink_item_gate",
    "paylink_no_candidate",
    "paylink_inventory_unavailable",
    "shipment_human_review",
    "discount_approval",
    "ugc_reward_review",
    "data_deletion_request",
    "delivery_validation_review",
    "inventory_overbooked_review",
    "ambiguous_order_status",
    "size_gap",
    "ig_lifecycle_window_review",
    "ig_lifecycle_permission_review",
    "ig_lifecycle_delivery_review",
})

# --- «Быстрый неверный ответ — не успех» ------------------------------------
# Пункт требует зафиксировать это правилом, а не намерением. Доказательство
# неверного ответа берётся durable: если сразу после доставленного ответа по
# этому же клиенту открылся человеческий кейс из набора ниже, значит ответ
# проблему клиента не закрыл. Такой ход уходит в отдельную корзину
# `delivered_then_escalated`: он остаётся в знаменателе, но НЕ в числителе.
#
# Набор узкий сознательно. `takeover` здесь нет: перехват менеджером — штатная
# практика продаж, а не признак ошибки бота. Есть только то, что означает
# «ответ был не тот» или «ответа фактически не было».
CORRECTION_EVIDENCE_EVENT_TYPES = frozenset({
    "escalation",
    "ai_reply_fallback",
    "generation_failed",
    "payment_link_delivery_review",
    "delivery_validation_review",
    "ambiguous_order_status",
    "size_gap",
})
# Окно, в котором открытый кейс считается следствием именно этого ответа.
CORRECTION_WINDOW = timedelta(minutes=30)

# --- SLA --------------------------------------------------------------------
# SLA пути продаж ВЫВОДИТСЯ из объявленного бюджета хода, а не задаётся здесь
# независимым числом. Независимое число разошлось бы с реальным дедлайном при
# первой же правке таймаута — ровно та ошибка, из-за которой окно живости демона
# оказалось меньше бюджета хода (Э2.10).
SALES_SLA_BUDGET_MULTIPLIER = 3.0
SALES_SLA_FLOOR_SECONDS = 180.0
# Алерт менеджеру — не клиентский путь по скорости, но человек, узнавший о
# заблокированном клиенте через час, для клиента равен неузнавшему.
HANDOFF_SLA_SECONDS = 900.0
# Lifecycle-сообщение привязано к событию (оплата, ТТН, получение). Сутки —
# верхняя граница осмысленности: «ваш заказ оплачен» через два дня бесполезно.
LIFECYCLE_SLA_SECONDS = 86400.0

# Минимальная выборка, ниже которой вывод НЕ делается. Без этого порога один
# неудачный ход в тихий день выглядит как двукратная деградация.
MIN_SAMPLE_PER_PATH = 30

# --- Бюджет ошибок ----------------------------------------------------------
# Пороги, при нарушении которых приостанавливается выкат НОВОЙ автоматической
# политики. Существующая поддержка клиентов не останавливается никогда: гейт
# возвращает `blocks_customer_support=False` как явную часть контракта, чтобы
# «бюджет исчерпан» нельзя было прочитать как «выключить бота».
ERROR_BUDGET_MIN_CORRECT_RATE = 0.90
ERROR_BUDGET_MAX_UNKNOWN_SHARE = 0.02
ERROR_BUDGET_MAX_OVERDUE_SHARE = 0.02
ERROR_BUDGET_MAX_UNCLASSIFIED_SHARE = 0.05
# Допустимое падение основной метрики в критической когорте относительно
# базового замера. Абсолютные проценты, не относительные.
ERROR_BUDGET_MAX_COHORT_REGRESSION = 0.05


def flag(name: str, default: bool = True) -> bool:
    """Feature-флаг этапа из Django settings (управляется .env)."""
    value = getattr(django_settings, name, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def sales_sla_seconds() -> float:
    """SLA пути продаж, выведенный из бюджета хода."""
    try:
        from management.services.ig_turn_budget import declared_turn_budget_seconds

        declared = float(declared_turn_budget_seconds())
    except Exception:
        declared = 0.0
    return max(SALES_SLA_FLOOR_SECONDS, declared * SALES_SLA_BUDGET_MULTIPLIER)


def sla_seconds(path: str) -> float:
    if path == PATH_SALES_REPLY:
        return sales_sla_seconds()
    if path == PATH_HUMAN_HANDOFF:
        return HANDOFF_SLA_SECONDS
    return LIFECYCLE_SLA_SECONDS


def _ratio(numerator: int, denominator: int):
    """Доля или `None`. Именно `None`, а не 0.0, когда знаменатель пуст.

    Ноль в пустом знаменателе — это ложь того же класса, что и `unknown` в
    числителе: он выглядит как измеренная катастрофа там, где измерения не было.
    """
    denominator = int(denominator or 0)
    if denominator <= 0:
        return None
    return round(int(numerator or 0) / denominator, 6)


def percentiles(values) -> dict:
    """p50 отдельно от p95/p99 — их нельзя показывать одним числом.

    Пункт требует разделения именно потому, что медиана в этом пути почти всегда
    выглядит хорошо: подавляющее большинство ходов либо отвечается за секунды,
    либо не отвечается вовсе. Вся боль клиента живёт в хвосте, и агрегат её
    прячет. Метод — nearest-rank без интерполяции: интерполяция на маленькой
    выборке придумывает значение, которого не было ни у одного клиента.
    """
    ordered = sorted(float(value) for value in values if value is not None)
    if not ordered:
        return {"count": 0, "p50": None, "p95": None, "p99": None, "max": None}

    def rank(q: float) -> float:
        index = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
        return round(ordered[index], 3)

    return {
        "count": len(ordered),
        "p50": rank(0.50),
        "p95": rank(0.95),
        "p99": rank(0.99),
        "max": round(ordered[-1], 3),
    }


def _empty_buckets() -> dict:
    """Все корзины всегда присутствуют, включая нулевые.

    Отсутствующий ключ в одном месте и присутствующий в другом — это уже два
    разных знаменателя в UI и в отчёте.
    """
    return {name: 0 for name in ALL_OUTCOMES}


def _cohort_for(stage: str, purchases_count: int) -> str:
    stage = str(stage or "")
    if stage in {IgClient.Stage.CHECKOUT, IgClient.Stage.PAYMENT_PENDING}:
        return COHORT_MONEY_IN_FLIGHT
    if stage in {
        IgClient.Stage.PAID,
        IgClient.Stage.ORDER_CREATED,
        IgClient.Stage.DONE,
    } or int(purchases_count or 0) > 0:
        return COHORT_PAID
    if stage == IgClient.Stage.LEAD_TO_MANAGER:
        return COHORT_HANDOFF
    return COHORT_PROSPECT


def _summarize(
    *,
    path: str,
    unit: str,
    buckets: dict,
    latencies: list,
    cohort_buckets: dict,
    policy_reasons: dict,
    extra_guardrails: dict | None = None,
) -> dict:
    """Одна функция, считающая ВСЕ доли по всем путям.

    Это и есть механизм требования «одинаковые числитель и знаменатель в UI, в
    отчёте и в решении о выкате». Ни команда, ни панель, ни гейт не считают
    ничего сами — они читают то, что вернула эта функция. Три реализации одной
    формулы неизбежно разойдутся; одна реализация разойтись не может.
    """
    total = sum(buckets.values())
    terminal = sum(buckets[name] for name in TERMINAL_OUTCOMES)
    correct = sum(buckets[name] for name in CORRECT_OUTCOMES)
    not_owed = sum(buckets[name] for name in NOT_OWED_OUTCOMES)
    owed = terminal - not_owed

    cohorts = {}
    for cohort in COHORTS:
        cohort_bucket = cohort_buckets.get(cohort) or _empty_buckets()
        cohort_terminal = sum(cohort_bucket[name] for name in TERMINAL_OUTCOMES)
        cohort_correct = sum(cohort_bucket[name] for name in CORRECT_OUTCOMES)
        cohorts[cohort] = {
            "denominator_terminal": cohort_terminal,
            "correct_numerator": cohort_correct,
            "correct_final_outcome_rate": _ratio(cohort_correct, cohort_terminal),
            "unknown": cohort_bucket[OUTCOME_UNKNOWN],
            "unknown_share": _ratio(cohort_bucket[OUTCOME_UNKNOWN], cohort_terminal),
            "overdue": cohort_bucket[OUTCOME_OVERDUE],
        }

    guardrails = {
        # Все guardrail-доли считаются от ТОГО ЖЕ знаменателя, что и основная
        # метрика. Иначе их нельзя складывать с ней в одном решении.
        "no_send_needed_share": _ratio(buckets[OUTCOME_NO_SEND_NEEDED], terminal),
        "unknown_share": _ratio(buckets[OUTCOME_UNKNOWN], terminal),
        "unclassified_share": _ratio(buckets[OUTCOME_UNCLASSIFIED], terminal),
        "policy_blocked_share": _ratio(buckets[OUTCOME_POLICY_BLOCKED], terminal),
        "human_case_share": _ratio(buckets[OUTCOME_HUMAN_CASE], terminal),
        "delivered_then_escalated_share": _ratio(
            buckets[OUTCOME_DELIVERED_THEN_ESCALATED], terminal
        ),
        "overdue_share": _ratio(buckets[OUTCOME_OVERDUE], total),
    }
    if extra_guardrails:
        guardrails.update(extra_guardrails)

    return {
        "path": path,
        "unit": unit,
        "sla_seconds": round(sla_seconds(path), 3),
        "buckets": buckets,
        "denominator_total": total,
        "denominator_terminal": terminal,
        "denominator_owed": owed,
        # Наблюдение о СИСТЕМЕ: процесс завершился. `unknown` входит сюда.
        "terminal_disposition": {
            "definition": "строки в терминальной корзине / все строки пути за окно",
            "numerator": terminal,
            "denominator": total,
            "rate": _ratio(terminal, total),
        },
        # Наблюдение о КЛИЕНТЕ: результат получен. `unknown` не входит никогда.
        "correct_final_outcome": {
            "definition": (
                "строки с квитанцией провайдера и без последующего "
                "человеческого кейса / все терминальные строки пути"
            ),
            "numerator": correct,
            "denominator": terminal,
            "rate": _ratio(correct, terminal),
        },
        # Вспомогательная доля: тот же числитель, знаменатель без корзин, где
        # сообщение клиенту и не причиталось. Показывается рядом, чтобы разрыв
        # между двумя числами был виден, а не выбирался по вкусу.
        "answer_rate_when_owed": {
            "definition": "тот же числитель / терминальные строки минус "
            + ", ".join(NOT_OWED_OUTCOMES),
            "numerator": correct,
            "denominator": owed,
            "rate": _ratio(correct, owed),
        },
        "latency_to_terminal_seconds": percentiles(latencies),
        "policy_blocks_by_reason": dict(sorted(policy_reasons.items())),
        "cohorts": cohorts,
        "guardrails": guardrails,
        "sample_sufficient": terminal >= MIN_SAMPLE_PER_PATH,
        "invariants": bucket_invariants(
            buckets, total, terminal, policy_reason_total=sum(policy_reasons.values())
        ),
    }


def bucket_invariants(
    buckets: dict, total: int, terminal: int, policy_reason_total=None
) -> dict:
    """Проверяемые инварианты корзин — их проверяет тест, а не комментарий.

    Смысл именно в том, чтобы «молча потерянная категория» была невозможна:
    сумма корзин обязана совпасть со знаменателем, набор ключей — с объявленным
    словарём, а числитель — быть подмножеством терминальных корзин.
    """
    keys_match = set(buckets) == set(ALL_OUTCOMES)
    open_count = sum(buckets.get(name, 0) for name in OPEN_OUTCOMES)
    return {
        "bucket_keys_match_vocabulary": keys_match,
        "buckets_sum_equals_denominator": sum(buckets.values()) == total,
        "terminal_plus_open_equals_total": terminal + open_count == total,
        "policy_reasons_sum_equals_policy_bucket": (
            policy_reason_total is None
            or policy_reason_total == buckets.get(OUTCOME_POLICY_BLOCKED, 0)
        ),
        "correct_is_subset_of_terminal": (
            sum(buckets.get(name, 0) for name in CORRECT_OUTCOMES) <= terminal
        ),
        "unknown_excluded_from_correct": OUTCOME_UNKNOWN not in CORRECT_OUTCOMES,
        "no_negative_buckets": all(int(value) >= 0 for value in buckets.values()),
    }


def _correction_evidence_by_client(since, until) -> dict:
    """Времена открытия человеческих кейсов, доказывающих неверный ответ.

    Один запрос на всё окно. Верхняя граница расширена на `CORRECTION_WINDOW`:
    кейс, открытый через десять минут после последнего хода окна, относится
    именно к этому ходу, и обрезать его границей отчёта означало бы прятать
    ровно те случаи, ради которых правило существует.
    """
    grouped = defaultdict(list)
    rows = (
        IgBotNotification.objects.filter(
            event_type__in=CORRECTION_EVIDENCE_EVENT_TYPES,
            client_id__isnull=False,
            created_at__gte=since,
            created_at__lt=until + CORRECTION_WINDOW,
        )
        .values_list("client_id", "created_at")
        .iterator(chunk_size=2000)
    )
    for client_id, created_at in rows:
        grouped[int(client_id)].append(created_at)
    for values in grouped.values():
        values.sort()
    return grouped


def _send_states_by_turn(since, until) -> dict:
    """Durable `send_state` всех строк каждого хода за окно — ОДИН запрос.

    Без этого пришлось бы для каждого хода спрашивать его строки отдельно, то
    есть N+1 по сообщениям. Фильтр идёт по `turn__window_started_at`, а не по
    списку id: список id растёт вместе с выборкой и превращает «один запрос» в
    гигантский `IN`, который MariaDB на боевых объёмах не переживает.

    Возвращается множество состояний на ход, а не одно значение: у burst-а
    несколько строк, и решает не «последняя», а наличие решающего состояния.
    """
    grouped = defaultdict(set)
    rows = (
        IgTurnMessage.objects.filter(
            turn__window_started_at__gte=since,
            turn__window_started_at__lt=until,
        )
        .values_list("turn_id", "message__send_state")
        .iterator(chunk_size=2000)
    )
    for turn_id, send_state in rows:
        grouped[int(turn_id)].add(str(send_state or ""))
    return grouped


def _sales_bucket(
    *,
    claim_state: str,
    terminal_reason: str,
    window_started_at,
    processed_at,
    send_states: set,
    escalated: bool,
    sla: float,
    now,
) -> tuple:
    """Корзина одного хода. Возвращает `(корзина, причина_блокировки|"")`.

    Источник истины — типизированный `terminal_reason`: он durable и его пишет
    рантайм. `send_state` используется ТОЛЬКО чтобы расщепить `no_reply_needed`,
    в котором рантайм смешал три разных исхода: «ответ не нужен», «сменилась
    epoch разрешения» (пауза/перехват) и «подавлен дубль». Смешивание не
    косметическое: блокировка политикой, посчитанная как «ответ не требовался»,
    делает метрику слепой к самому опасному сценарию — боту, которому запретили
    отвечать, и никто этого не увидел.
    """
    reasons = IgCustomerTurn.TerminalReason
    reason = str(terminal_reason or "")

    if reason == reasons.REPLIED:
        if escalated:
            return OUTCOME_DELIVERED_THEN_ESCALATED, ""
        return OUTCOME_DELIVERED, ""
    if reason == reasons.SEND_UNKNOWN:
        return OUTCOME_UNKNOWN, ""
    if reason == reasons.FAILED:
        return OUTCOME_FAILED, ""
    if reason == reasons.ROW_MISSING:
        # Строка хода исчезла: доказательства исхода нет физически. Это не
        # «не требовалось» и не успех — это потерянное evidence.
        return OUTCOME_EVIDENCE_LOST, ""
    if reason == reasons.LEASE_EXPIRED:
        return OUTCOME_ABANDONED, ""
    if reason == reasons.SUPERSEDED:
        return OUTCOME_SUPERSEDED, ""
    if reason == reasons.NO_REPLY_NEEDED:
        if "cancelled" in send_states:
            return OUTCOME_POLICY_BLOCKED, "permission_epoch_changed"
        if "duplicate" in send_states:
            return OUTCOME_SUPPRESSED_DUPLICATE, ""
        if "failed" in send_states:
            # Рантайм закрыл ход как «ответ не нужен», а строка помечена
            # провалом отправки. Это противоречие, и оно должно быть видно.
            return OUTCOME_FAILED, ""
        return OUTCOME_NO_SEND_NEEDED, ""
    if reason:
        # Новое значение `TerminalReason`, о котором эта проекция не знает.
        # Тихо приписать его к любой существующей корзине — значит соврать.
        return OUTCOME_UNCLASSIFIED, ""

    if claim_state == IgCustomerTurn.ClaimState.PROCESSED:
        # Ход закрыт без типизированной причины: историческая строка либо ветка
        # рантайма, которая причину не пишет. Отдельная корзина обязательна.
        return OUTCOME_UNCLASSIFIED, ""
    if claim_state == IgCustomerTurn.ClaimState.SUPERSEDED:
        return OUTCOME_SUPERSEDED, ""

    age = (now - window_started_at).total_seconds() if window_started_at else 0.0
    if age > sla:
        return OUTCOME_OVERDUE, ""
    return OUTCOME_OPEN_WITHIN_SLA, ""


def sales_reply_trace(*, since, until, now) -> dict:
    """Трасса продажного ответа: `inbound → решение → отправка → квитанция`.

    Единица знаменателя — логический ход клиента (`IgCustomerTurn`), а не строка
    сообщения. Строка была бы неверным знаменателем: burst из трёх сообщений —
    это одно ожидание клиента и один причитающийся ответ, и знаменатель по
    строкам занизил бы метрику втрое на самых активных клиентах.

    Событием считается `window_started_at` — момент, когда клиент начал ход.
    Терминальным моментом — `processed_at`. Латентность считается только для
    ходов, у которых есть оба времени.
    """
    sla = sales_sla_seconds()
    escalations = _correction_evidence_by_client(since, until)
    send_states_by_turn = _send_states_by_turn(since, until)

    buckets = _empty_buckets()
    cohort_buckets = {cohort: _empty_buckets() for cohort in COHORTS}
    policy_reasons: dict = defaultdict(int)
    latencies: list = []
    unclassified_no_reply = 0

    rows = (
        IgCustomerTurn.objects.filter(
            window_started_at__gte=since,
            window_started_at__lt=until,
        )
        .values_list(
            "id",
            "client_id",
            "claim_state",
            "terminal_reason",
            "window_started_at",
            "processed_at",
            "client__stage",
            "client__purchases_count",
        )
        .iterator(chunk_size=2000)
    )
    for (
        turn_id,
        client_id,
        claim_state,
        terminal_reason,
        window_started_at,
        processed_at,
        stage,
        purchases_count,
    ) in rows:
        send_states = send_states_by_turn.get(int(turn_id), set())
        terminal_at = processed_at or window_started_at
        escalated = False
        if terminal_reason == IgCustomerTurn.TerminalReason.REPLIED and terminal_at:
            moments = escalations.get(int(client_id or 0)) or []
            if moments:
                left = bisect_right(moments, terminal_at)
                right = bisect_left(moments, terminal_at + CORRECTION_WINDOW)
                escalated = right > left
        bucket, policy_reason = _sales_bucket(
            claim_state=claim_state,
            terminal_reason=terminal_reason,
            window_started_at=window_started_at,
            processed_at=processed_at,
            send_states=send_states,
            escalated=escalated,
            sla=sla,
            now=now,
        )
        buckets[bucket] += 1
        cohort_buckets[_cohort_for(stage, purchases_count)][bucket] += 1
        if bucket == OUTCOME_POLICY_BLOCKED:
            policy_reasons[policy_reason or POLICY_REASON_NOT_RECORDED] += 1
        if bucket == OUTCOME_NO_SEND_NEEDED:
            # Причина «почему не отправили» здесь не записана нигде: рантайм
            # пишет её только в текстовую строку лога `observed_skip`, без
            # ссылки на ход и с сырым IGSID. Считаем размер незнания отдельным
            # числом — но СОЗНАТЕЛЬНО не в `policy_blocks_by_reason`: разбивка,
            # сумма которой не совпадает со своей корзиной, это ровно та
            # небрежность, которую пункт запрещает.
            unclassified_no_reply += 1
        if processed_at and window_started_at:
            latencies.append((processed_at - window_started_at).total_seconds())

    return _summarize(
        path=PATH_SALES_REPLY,
        unit="IgCustomerTurn",
        buckets=buckets,
        latencies=latencies,
        cohort_buckets=cohort_buckets,
        policy_reasons=policy_reasons,
        extra_guardrails={
            "policy_reason_not_recorded": unclassified_no_reply,
        },
    )


# Статусы алерта → корзина. Таблица, а не цепочка `if`: набор статусов задан
# `IgBotNotification.Status`, и любое новое значение обязано появиться здесь
# явно, иначе попадёт в `unclassified` и будет видно.
_HANDOFF_BUCKET_BY_STATUS = {
    IgBotNotification.Status.SENT: OUTCOME_DELIVERED,
    # Оператор закрыл кейс руками — человек его точно увидел.
    IgBotNotification.Status.RESOLVED: OUTCOME_DELIVERED,
    IgBotNotification.Status.UNKNOWN: OUTCOME_UNKNOWN,
    IgBotNotification.Status.FAILED: OUTCOME_FAILED,
    IgBotNotification.Status.DEAD_LETTER: OUTCOME_FAILED,
}


def human_handoff_trace(*, since, until, now) -> dict:
    """Трасса срочной поддержки и передачи человеку.

    **Почему единица — алерт, а не ход клиента.** Для клиента, которого система
    передала человеку, корректный финальный исход означает одно: человек об этом
    узнал. Ход при этом может быть закрыт как `no_reply_needed` и выглядеть
    безупречно, тогда как Telegram-алерт умер в `dead_letter`, и клиент ждёт
    менеджера, который ничего не знает. Именно этот разрыв прежние метрики не
    видели: доставка алерта считалась инфраструктурой, а не путём клиента.

    Знаменатель — только клиент-скоупные алерты из `HUMAN_CASE_EVENT_TYPES`.
    Инфраструктурные алерты (демон, каталог, задачи) в путь клиента не входят.
    """
    sla = HANDOFF_SLA_SECONDS
    buckets = _empty_buckets()
    cohort_buckets = {cohort: _empty_buckets() for cohort in COHORTS}
    latencies: list = []

    rows = (
        IgBotNotification.objects.filter(
            event_type__in=HUMAN_CASE_EVENT_TYPES,
            client_id__isnull=False,
            created_at__gte=since,
            created_at__lt=until,
        )
        .values_list(
            "status",
            "created_at",
            "sent_at",
            "client__stage",
            "client__purchases_count",
        )
        .iterator(chunk_size=2000)
    )
    for status, created_at, sent_at, stage, purchases_count in rows:
        bucket = _HANDOFF_BUCKET_BY_STATUS.get(status)
        if bucket is None:
            age = (now - created_at).total_seconds() if created_at else 0.0
            bucket = OUTCOME_OVERDUE if age > sla else OUTCOME_OPEN_WITHIN_SLA
        buckets[bucket] += 1
        cohort_buckets[_cohort_for(stage, purchases_count)][bucket] += 1
        if sent_at and created_at:
            latencies.append((sent_at - created_at).total_seconds())

    return _summarize(
        path=PATH_HUMAN_HANDOFF,
        unit="IgBotNotification",
        buckets=buckets,
        latencies=latencies,
        cohort_buckets=cohort_buckets,
        policy_reasons={},
    )


# `IgLifecycleEvent.State` уже типизирует ровно ту лестницу, которую требует
# пункт: разрешённая отправка / блокировка политикой / человеческий кейс /
# квитанция или unknown. Поэтому здесь не выводится ничего нового — состояния
# просто переводятся в общий словарь исходов.
_LIFECYCLE_BUCKET_BY_STATE = {
    IgLifecycleEvent.State.SENT: OUTCOME_DELIVERED,
    # Вне 24-часового окна Meta — это блокировка политикой платформы, а не сбой.
    IgLifecycleEvent.State.WAITING_WINDOW: OUTCOME_POLICY_BLOCKED,
    IgLifecycleEvent.State.MANAGER_REVIEW: OUTCOME_HUMAN_CASE,
    IgLifecycleEvent.State.AMBIGUOUS: OUTCOME_UNKNOWN,
    IgLifecycleEvent.State.FAILED: OUTCOME_FAILED,
    IgLifecycleEvent.State.CANCELLED: OUTCOME_NO_SEND_NEEDED,
}
_LIFECYCLE_POLICY_REASON_BY_STATE = {
    IgLifecycleEvent.State.WAITING_WINDOW: "meta_window_closed",
}


def lifecycle_event_trace(*, since, until, now) -> dict:
    """Трасса lifecycle-события клиента (post-purchase путь).

    Это вторая по важности метрика плана: доля post-delivery сообщений, дошедших
    до клиента. По трассировке она близка к нулю при полностью написанной
    инфраструктуре, поэтому здесь важно, чтобы `waiting_window` и `ambiguous`
    НЕ попадали в успех: именно они дали бы ложную картину «инфраструктура
    работает».
    """
    sla = LIFECYCLE_SLA_SECONDS
    buckets = _empty_buckets()
    cohort_buckets = {cohort: _empty_buckets() for cohort in COHORTS}
    policy_reasons: dict = defaultdict(int)
    latencies: list = []

    rows = (
        IgLifecycleEvent.objects.filter(
            created_at__gte=since,
            created_at__lt=until,
        )
        .values_list(
            "state",
            "created_at",
            "completed_at",
            "client__stage",
            "client__purchases_count",
        )
        .iterator(chunk_size=2000)
    )
    for state, created_at, completed_at, stage, purchases_count in rows:
        bucket = _LIFECYCLE_BUCKET_BY_STATE.get(state)
        if bucket is None:
            age = (now - created_at).total_seconds() if created_at else 0.0
            bucket = OUTCOME_OVERDUE if age > sla else OUTCOME_OPEN_WITHIN_SLA
        buckets[bucket] += 1
        cohort_buckets[_cohort_for(stage, purchases_count)][bucket] += 1
        policy_reason = _LIFECYCLE_POLICY_REASON_BY_STATE.get(state)
        if policy_reason:
            policy_reasons[policy_reason] += 1
        if completed_at and created_at:
            latencies.append((completed_at - created_at).total_seconds())

    return _summarize(
        path=PATH_LIFECYCLE_EVENT,
        unit="IgLifecycleEvent",
        buckets=buckets,
        latencies=latencies,
        cohort_buckets=cohort_buckets,
        policy_reasons=policy_reasons,
    )


def _harm_guardrails(*, since, until) -> dict:
    """Guardrail-метрики вреда: показатель не должен расти ЗА СЧЁТ клиента.

    Без них правило «условие остановки, если основной показатель растёт за счёт
    вреда» невыполнимо: доставленных сообщений можно нагнать спамом, и основная
    метрика вырастет. Поэтому рядом всегда стоят opt-out и подтверждённые
    технические запреты доставки.
    """
    opt_outs = IgClient.objects.filter(
        opted_out_at__gte=since, opted_out_at__lt=until
    ).count()
    blocked = {
        str(row["delivery_status"] or POLICY_REASON_NOT_RECORDED): int(row["total"])
        for row in IgClient.objects.filter(
            delivery_failed_at__gte=since, delivery_failed_at__lt=until
        )
        .values("delivery_status")
        .annotate(total=Count("id"))
        .order_by()
    }
    return {
        "opt_outs_in_window": opt_outs,
        "clients_with_confirmed_delivery_block": dict(sorted(blocked.items())),
    }


def slo_report(*, days: int = DEFAULT_WINDOW_DAYS, now=None) -> dict:
    """Единственный источник чисел SLO. UI, отчёт и гейт читают только это.

    Read-only: ни одной записи. Никакого PII: только идентификаторы-счётчики,
    без IGSID, токенов, ссылок на приватные медиа и текста клиента.
    """
    now = now or timezone.now()
    days = max(1, min(int(days or DEFAULT_WINDOW_DAYS), MAX_WINDOW_DAYS))
    since = now - timedelta(days=days)
    tz = ZoneInfo(REPORT_TIMEZONE)

    paths = {
        PATH_SALES_REPLY: sales_reply_trace(since=since, until=now, now=now),
        PATH_HUMAN_HANDOFF: human_handoff_trace(since=since, until=now, now=now),
        PATH_LIFECYCLE_EVENT: lifecycle_event_trace(since=since, until=now, now=now),
    }
    return {
        "window": {
            "days": days,
            "since_utc": since.isoformat(),
            "until_utc": now.isoformat(),
            "since_local": since.astimezone(tz).isoformat(),
            "until_local": now.astimezone(tz).isoformat(),
            "timezone": REPORT_TIMEZONE,
        },
        "definitions": {
            "terminal_disposition": (
                "наблюдение о системе: процесс завершился. unknown входит."
            ),
            "correct_final_outcome": (
                "наблюдение о клиенте: результат получен. unknown НЕ входит "
                "никогда; ответ, за которым сразу открылся человеческий кейс, "
                "тоже не считается успехом."
            ),
            "primary_metric": "correct_final_outcome.rate по каждому пути",
            "min_sample_per_path": MIN_SAMPLE_PER_PATH,
            "cohort_caveat": (
                "когорта берётся из текущей стадии IgClient: стадия на момент "
                "хода нигде не привязана к ходу"
            ),
            "event_timestamps": {
                PATH_SALES_REPLY: "window_started_at → processed_at",
                PATH_HUMAN_HANDOFF: "created_at → sent_at",
                PATH_LIFECYCLE_EVENT: "created_at → completed_at",
            },
        },
        "paths": paths,
        "guardrails": _harm_guardrails(since=since, until=now),
        "flags": {
            "IG_SLO_CUSTOMER_PATH": flag("IG_SLO_CUSTOMER_PATH", True),
            "IG_SLO_POLICY_ROLLOUT_GATE": flag("IG_SLO_POLICY_ROLLOUT_GATE", True),
        },
    }


def slo_panel_payload(*, days: int = DEFAULT_WINDOW_DAYS, now=None) -> dict:
    """То же самое, что читает отчёт, — для панели в админке.

    Функция намеренно не считает ничего своего и не переименовывает ключи. Как
    только панель начнёт агрегировать сама, появится третий источник числа, и
    требование пункта «одинаковые числитель и знаменатель в UI, в отчёте и в
    решении о выкате» будет нарушено незаметно.
    """
    return slo_report(days=days, now=now)


def policy_rollout_gate(report: dict, *, baseline: dict | None = None) -> dict:
    """Бюджет ошибок: можно ли выкатывать НОВУЮ автоматическую политику.

    Два свойства этого гейта важнее его порогов.

    1. Он останавливает только выкат новой автоматики. Существующую поддержку
       клиентов он не останавливает никогда — `blocks_customer_support` всегда
       `False` и присутствует в ответе явно, чтобы «бюджет исчерпан» нельзя было
       прочитать как «выключить бота». Выключенный бот — это гарантированное
       молчание вместо вероятной ошибки, то есть замена риска на ущерб.
    2. При недостаточной выборке он не разрешает выкат «по умолчанию». Решение
       становится `insufficient_sample`: отсутствие данных — это не зелёный свет.
    """
    reasons: list = []
    insufficient: list = []
    baseline_paths = (baseline or {}).get("paths") or {}

    for path in PATHS:
        path_report = (report.get("paths") or {}).get(path) or {}
        if not path_report.get("sample_sufficient"):
            insufficient.append(path)
            continue
        correct = path_report.get("correct_final_outcome") or {}
        rate = correct.get("rate")
        if rate is not None and rate < ERROR_BUDGET_MIN_CORRECT_RATE:
            reasons.append(f"{path}: correct_final_outcome {rate} < {ERROR_BUDGET_MIN_CORRECT_RATE}")
        guardrails = path_report.get("guardrails") or {}
        for key, limit in (
            ("unknown_share", ERROR_BUDGET_MAX_UNKNOWN_SHARE),
            ("overdue_share", ERROR_BUDGET_MAX_OVERDUE_SHARE),
            ("unclassified_share", ERROR_BUDGET_MAX_UNCLASSIFIED_SHARE),
        ):
            value = guardrails.get(key)
            if value is not None and value > limit:
                reasons.append(f"{path}: {key} {value} > {limit}")

        baseline_cohorts = (baseline_paths.get(path) or {}).get("cohorts") or {}
        for cohort in CRITICAL_COHORTS:
            current = (path_report.get("cohorts") or {}).get(cohort) or {}
            previous = baseline_cohorts.get(cohort) or {}
            current_rate = current.get("correct_final_outcome_rate")
            previous_rate = previous.get("correct_final_outcome_rate")
            if current_rate is None or previous_rate is None:
                continue
            drop = previous_rate - current_rate
            if drop > ERROR_BUDGET_MAX_COHORT_REGRESSION:
                reasons.append(
                    f"{path}/{cohort}: регрессия {round(drop, 6)} > "
                    f"{ERROR_BUDGET_MAX_COHORT_REGRESSION}"
                )

    if reasons:
        decision = "blocked"
    elif insufficient:
        decision = "insufficient_sample"
    else:
        decision = "allowed"

    return {
        "decision": decision,
        "allow_new_automatic_policy": decision == "allowed",
        # Инвариант контракта, а не значение по умолчанию.
        "blocks_customer_support": False,
        "reasons": reasons,
        "insufficient_sample_paths": insufficient,
        "thresholds": {
            "min_correct_rate": ERROR_BUDGET_MIN_CORRECT_RATE,
            "max_unknown_share": ERROR_BUDGET_MAX_UNKNOWN_SHARE,
            "max_overdue_share": ERROR_BUDGET_MAX_OVERDUE_SHARE,
            "max_unclassified_share": ERROR_BUDGET_MAX_UNCLASSIFIED_SHARE,
            "max_cohort_regression": ERROR_BUDGET_MAX_COHORT_REGRESSION,
            "min_sample_per_path": MIN_SAMPLE_PER_PATH,
        },
    }
