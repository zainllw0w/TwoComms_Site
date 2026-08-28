"""Скорборд здоров'я кандидатів: знання замість перевірок (ЭА.12 + Э-HEDGE).

Головна ідея, яка відрізняє це від «перевіряти ключі»: **жодного окремого
тестового запиту**. Кожен реальний хід клієнта вже дає нам факт — цей ключ на цій
моделі відповів за N мілісекунд або впав з таким класом відказу. Ці факти вже
пишуться в `GeminiRequestAttempt` (ЭА.1). Скорборд лише читає їх і відповідає на
одне питання: **у якому порядку пробувати кандидатів прямо зараз**.

Чому це важливо саме для безкоштовних ключів. Якщо писати 20–30 людей одночасно,
будь-яка схема «спочатку перевіримо, потім відповімо» витратить квоту на
перевірки, а не на клієнтів. Тому:

* нуль додаткових викликів провайдера — скорборд живе на вже існуючій телеметрії;
* нуль запитів у гарячому шляху — знімок кешується на кілька секунд і
  перевикористовується всіма ходами;
* деградація завжди безпечна: немає даних — беремо базовий порядок пулу.

Що скорборд НЕ робить: не вирішує, яку модель використати (це політика
`model_chain`), не відкриває circuit (це `gemini_keys`), не витрачає квоту.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.core.cache import cache
from django.utils import timezone

# Вікно, за яке беруться факти. Коротше — швидше реагує на деградацію; довше —
# стабільніше. 20 хвилин: достатньо, щоб побачити quota-вікно 429, і достатньо
# мало, щоб вчорашній збій не впливав на сьогоднішній порядок.
SCOREBOARD_WINDOW = datetime.timedelta(minutes=20)
# Знімок кешується: у гарячому шляху ходу не має бути жодного зайвого запиту.
SNAPSHOT_TTL_SECONDS = 8
SNAPSHOT_CACHE_KEY = "ig_gemini_scoreboard_v1"
# Скільки останніх спроб на пару (ключ, модель) враховувати.
MAX_SAMPLES_PER_PAIR = 8
# Класи відказу, які означають «ключ живий, а модель зараз повільна». Вони НЕ
# мають опускати ключ у хвіст: наступного разу той самий ключ може відповісти
# швидко, і саме через це в production система дарма стрибала на слабшу модель.
_MODEL_SLOWNESS_KINDS = frozenset({"read_timeout", "http_408", "http_5xx", "transport"})
# Класи, які означають проблему саме з ключем/проєктом.
_KEY_FAULT_KINDS = frozenset({"quota_429", "invalid_key", "permission_denied"})


@dataclass(frozen=True)
class PairHealth:
    """Здоров'я однієї пари (ключ, модель) за фактами реальних ходів."""

    key_name: str
    model: str
    successes: int = 0
    slow_failures: int = 0
    key_faults: int = 0
    latency_p50_ms: int = 0
    last_success_at: datetime.datetime | None = None
    last_failure_at: datetime.datetime | None = None

    @property
    def attempts(self) -> int:
        return self.successes + self.slow_failures + self.key_faults

    @property
    def success_ratio(self) -> float:
        return self.successes / self.attempts if self.attempts else 0.0

    @property
    def rank(self) -> tuple:
        """Ключ сортування: спочатку надійність, потім швидкість.

        Кандидат без жодного факту отримує нейтральну оцінку — він не карається
        за відсутність історії, інакше нові ключі ніколи б не пробувались.
        """
        if not self.attempts:
            return (1, 0.0, 0)
        # Проблема саме з ключем — найгірше: він не відповість і зараз.
        if self.key_faults and not self.successes:
            return (3, 0.0, self.latency_p50_ms or 10**6)
        return (
            0 if self.successes else 2,
            -self.success_ratio,
            self.latency_p50_ms or 10**6,
        )


def _percentile(values: list, fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return int(ordered[index])


def _collect(role: str, window: datetime.timedelta) -> dict:
    """Прочитати факти з телеметрії. Один запит, без звернень до провайдера."""
    from management.models import GeminiRequestAttempt

    since = timezone.now() - window
    rows = (
        GeminiRequestAttempt.objects.filter(role=role, created_at__gte=since)
        .exclude(outcome="not_attempted")
        .order_by("-id")
        .values_list(
            "key_name", "model", "outcome", "failure_kind", "latency_ms", "created_at"
        )[:400]
    )
    buckets: dict = {}
    for key_name, model, outcome, failure_kind, latency_ms, created_at in rows:
        pair = (str(key_name or ""), str(model or ""))
        bucket = buckets.setdefault(
            pair,
            {
                "successes": 0,
                "slow_failures": 0,
                "key_faults": 0,
                "latencies": [],
                "last_success_at": None,
                "last_failure_at": None,
                "samples": 0,
            },
        )
        if bucket["samples"] >= MAX_SAMPLES_PER_PAIR:
            continue
        bucket["samples"] += 1
        if str(outcome) == "succeeded":
            bucket["successes"] += 1
            bucket["latencies"].append(int(latency_ms or 0))
            if bucket["last_success_at"] is None:
                bucket["last_success_at"] = created_at
            continue
        kind = str(failure_kind or "")
        if kind in _KEY_FAULT_KINDS:
            bucket["key_faults"] += 1
        elif kind in _MODEL_SLOWNESS_KINDS:
            bucket["slow_failures"] += 1
        else:
            bucket["slow_failures"] += 1
        if bucket["last_failure_at"] is None:
            bucket["last_failure_at"] = created_at
    return buckets


def snapshot(role: str = "chat", *, force: bool = False) -> dict:
    """Знімок здоров'я пар. Кешується, тому гарячий хід не платить за нього."""
    cache_key = f"{SNAPSHOT_CACHE_KEY}:{role}"
    if not force:
        try:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass
    try:
        buckets = _collect(role, SCOREBOARD_WINDOW)
    except Exception:
        # Немає телеметрії — немає й порядку. Деградація до базового пулу.
        return {}
    health = {}
    for (key_name, model), bucket in buckets.items():
        health[(key_name, model)] = PairHealth(
            key_name=key_name,
            model=model,
            successes=bucket["successes"],
            slow_failures=bucket["slow_failures"],
            key_faults=bucket["key_faults"],
            latency_p50_ms=_percentile(bucket["latencies"], 0.5),
            last_success_at=bucket["last_success_at"],
            last_failure_at=bucket["last_failure_at"],
        )
    try:
        cache.set(cache_key, health, SNAPSHOT_TTL_SECONDS)
    except Exception:
        pass
    return health


def order_candidates(candidates: list, *, role: str = "chat") -> list:
    """Переставити кандидатів за свіжим здоров'ям, зберігши повний склад.

    Жоден кандидат не викидається: наша задача — швидше знайти той, що відповість,
    а не вирішити за провайдера, хто зламаний. Ключ, який щойно віддав 429, просто
    їде в хвіст і буде спробований, якщо решта не відповіла.
    """
    if not candidates:
        return []
    health = snapshot(role)
    if not health:
        return list(candidates)

    def sort_key(item):
        key_name, _value, model = item
        pair = health.get((key_name, model))
        return pair.rank if pair is not None else PairHealth(key_name, model).rank

    return sorted(candidates, key=sort_key)


def expected_latency_ms(key_name: str, model: str, *, role: str = "chat") -> int:
    """Очікувана латентність пари або 0, якщо фактів немає."""
    pair = snapshot(role).get((str(key_name), str(model)))
    return int(pair.latency_p50_ms) if pair else 0


def model_is_answering(model: str, *, role: str = "chat") -> bool | None:
    """Чи відповідає ця модель хоч одним ключем у вікні скорборда.

    `None` означає «немає даних», і це НЕ те саме, що «не відповідає»: на
    відсутності фактів жодне рішення про downgrade не приймається.
    """
    health = snapshot(role)
    if not health:
        return None
    relevant = [pair for pair in health.values() if pair.model == str(model)]
    if not relevant:
        return None
    return any(pair.successes for pair in relevant)


def healthy_key_count(model: str, *, role: str = "chat") -> int:
    """Скільки ключів нещодавно успішно відповіли цією моделью."""
    return sum(
        1
        for pair in snapshot(role).values()
        if pair.model == str(model) and pair.successes
    )


def invalidate(role: str = "chat") -> None:
    try:
        cache.delete(f"{SNAPSHOT_CACHE_KEY}:{role}")
    except Exception:
        pass
