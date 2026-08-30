"""Hedged-виклик: усі ключі найкращої моделі паралельно, перший успіх виграє.

**Production-дефект, який це виправляє.** 28.08 клієнт спитав про футболки.
Телеметрія ходу:

    GEMINI_API2 / 3.7  read_timeout  17.4s   candidate_index=1
    GEMINI_API  / 3.7  read_timeout  10.4s   candidate_index=2
    GEMINI_API2 / 3.6  succeeded     10.4s   candidate_index=7

Індексів 3–6 не існує: **чотири ключі на 3.7 не пробувались взагалі**. Дві
послідовні спроби з'їли 28.9 с із 35 с дедлайну (16.5 + 8.2 + сам виклик), і
`CHAT_PRIMARY_ATTEMPT_LIMIT = 2` вивів цикл на слабшу 3.6. Клієнт отримав
відповідь гіршою моделью, хоча чотири ключі найкращої навіть не спитали.

**Чому послідовний перебір тут принципово не працює.** `read_timeout` — це не
«ключ зламаний», це «модель зараз повільна». Але дізнатись, чи повільна вона на
ВСІХ ключах, послідовно неможливо: кожна перевірка коштує 8–17 с, і бюджет ходу
закінчується раніше за перебір.

**Рішення — hedged requests зі сходинковим старом.** Перший ключ стартує одразу.
Якщо через `HEDGE_STAGGER` відповіді немає — стартує другий, і так далі, максимум
`MAX_IN_FLIGHT` одночасно. Перший успіх повертається негайно, решта хвилі
скасовується. Ключова властивість: **якщо перший ключ відповідає швидко (типовий
випадок), другий не стартує взагалі** — тобто в нормальному режимі витрата квоти
не зростає ані на один запит.

Арифметика для 6 ключів, stagger 1.5 с, timeout 12 с на запит:
останній стартує на 7.5 с, найпізніша відповідь — 19.5 с, залишок бюджету на
fallback ≈ 15 с. Проти 28.9 с на дві спроби зараз.

**Що це НЕ робить:** не шле окремих тестових запитів, не «перевіряє ключі», не
тримає фонових пробів. Кожен виклик тут — це реальна спроба відповісти клієнту.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# Скільки запитів одночасно в повітрі. Три — компроміс: помітно швидше за
# послідовний перебір і при цьому не «всі шість одразу» на кожному ході.
MAX_IN_FLIGHT = 3
# Пауза перед запуском наступного кандидата. Менше — швидше знайдемо робочий
# ключ, але більше зайвих запитів; більше — економніше, але повільніше.
# 1.5 с обрано за фактом: успішні відповіді 3.7 у телеметрії — 2.4–10.4 с, тобто
# швидкий ключ встигає виграти до старту другого лише інколи. Тому додатково діє
# адаптивний stagger нижче.
HEDGE_STAGGER_SECONDS = 1.5
# Якщо скорборд знає типову латентність пари, чекаємо саме її (з запасом), а не
# фіксовану константу: для швидкого ключа хедж не потрібен взагалі.
ADAPTIVE_STAGGER_FACTOR = 1.25
MAX_ADAPTIVE_STAGGER_SECONDS = 6.0
# Верхня межа одного hedged-виклику. Довше тримати немає сенсу: у телеметрії всі
# успіхи 3.7 вкладаються в 11 с.
HEDGE_CALL_TIMEOUT = (4.0, 12.0)


@dataclass
class HedgeOutcome:
    """Результат однієї спроби в хвилі. Записується в телеметрію з головного потоку."""

    key_name: str
    model: str
    candidate_index: int
    started_at: float
    latency_ms: int = 0
    result: object = None
    error: BaseException | None = None
    skipped_reason: str = ""

    @property
    def succeeded(self) -> bool:
        return self.result is not None and self.error is None


@dataclass
class HedgeWave:
    """Підсумок хвилі: переможець (якщо є) і всі спроби для аудиту."""

    winner: HedgeOutcome | None
    outcomes: list
    elapsed_seconds: float


def _stagger_for(key_name: str, model: str, previous_expected_ms: int) -> float:
    """Скільки чекати перед запуском наступного кандидата.

    Якщо ми знаємо, що попередній кандидат зазвичай відповідає за 2 с, немає
    сенсу стартувати другий через 1.5 с — краще дати першому дописати. Якщо
    історії немає, працює фіксований stagger.
    """
    if previous_expected_ms <= 0:
        return HEDGE_STAGGER_SECONDS
    adaptive = (previous_expected_ms / 1000.0) * ADAPTIVE_STAGGER_FACTOR
    return max(HEDGE_STAGGER_SECONDS, min(MAX_ADAPTIVE_STAGGER_SECONDS, adaptive))


def run_hedged(
    candidates: list,
    *,
    call_one,
    deadline_monotonic: float,
    expected_latency_ms=None,
    max_in_flight: int = MAX_IN_FLIGHT,
    aborts_wave=None,
    after_outcome_recorded=None,
    before_provider_gate=None,
    after_provider_gate=None,
) -> HedgeWave:
    """Виконати хвилю hedged-викликів; повернути першого, хто відповів.

    `call_one(key_name, key_value, model, timeout) -> result` виконує ЧИСТИЙ
    HTTP-виклик і кидає типізоване виключення при відказі. Він не має торкатись
    БД: усі записи телеметрії робить викликаючий шар з головного потоку, бо
    Django-конекшени не поділяються між потоками.

    `expected_latency_ms(key_name, model) -> int` — підказка скорборда для
    адаптивного stagger. Необов'язкова.

    `aborts_wave(exc) -> bool` — чи є цей відказ **термінальним для моделі**, а не
    для ключа. HTTP 404 «модель не існує для цього проєкту» або 403 не зникнуть
    від спроби іншим ключем: продовжувати хвилю означало б спалити квоту на
    відомий заздалегідь результат. Такий відказ гасить усю хвилю одразу.
    """
    if not candidates:
        return HedgeWave(None, [], 0.0)

    started = time.monotonic()
    winner_lock = threading.Lock()
    winner: dict = {"outcome": None}
    stop = threading.Event()
    aborted: dict = {"reason": ""}
    outcomes: list = []
    outcomes_lock = threading.Lock()
    provider_started: set[int] = set()

    def remaining() -> float:
        return deadline_monotonic - time.monotonic()

    def worker(index: int, key_name: str, key_value: str, model: str, delay: float):
        # Чекаємо свою сходинку. Якщо за цей час хтось відповів або хвиля згасла —
        # не стартуємо взагалі: саме це не дає витрачати квоту в нормальному режимі.
        if delay > 0 and stop.wait(delay):
            with outcomes_lock:
                outcomes.append(
                    HedgeOutcome(
                        key_name, model, index, time.monotonic(),
                        skipped_reason=aborted["reason"] or "winner_found",
                    )
                )
            return
        if stop.is_set():
            with outcomes_lock:
                outcomes.append(
                    HedgeOutcome(
                        key_name, model, index, time.monotonic(),
                        skipped_reason=aborted["reason"] or "winner_found",
                    )
                )
            return
        budget = remaining()
        if budget <= HEDGE_CALL_TIMEOUT[0]:
            with outcomes_lock:
                outcomes.append(
                    HedgeOutcome(
                        key_name, model, index, time.monotonic(),
                        skipped_reason="deadline",
                    )
                )
            return
        read_budget = max(1.0, min(HEDGE_CALL_TIMEOUT[1], budget - HEDGE_CALL_TIMEOUT[0]))
        timeout = (min(HEDGE_CALL_TIMEOUT[0], budget * 0.25), read_budget)
        # Serialize the final provider boundary with winner publication. A
        # delayed worker that passed its first Event check cannot slip a second
        # quota-consuming call into the tiny window after another key wins.
        if before_provider_gate is not None:
            before_provider_gate(index)
        gate_started = False
        with winner_lock:
            # A successful worker records its outcome before publishing the
            # winner. If it is preempted in that tiny gap, a staggered worker
            # must promote the already-observed success instead of spending a
            # second quota call.
            if winner["outcome"] is None and not stop.is_set():
                with outcomes_lock:
                    observed_success = next(
                        (item for item in outcomes if item.succeeded),
                        None,
                    )
                if observed_success is not None:
                    winner["outcome"] = observed_success
                    stop.set()
            if stop.is_set():
                with outcomes_lock:
                    outcomes.append(
                        HedgeOutcome(
                            key_name,
                            model,
                            index,
                            time.monotonic(),
                            skipped_reason=aborted["reason"] or "winner_found",
                        )
                    )
            else:
                provider_started.add(index)
                gate_started = True
        if after_provider_gate is not None:
            after_provider_gate(index, gate_started)
        if not gate_started:
            return
        call_started = time.monotonic()
        outcome = HedgeOutcome(key_name, model, index, call_started)
        try:
            outcome.result = call_one(key_name, key_value, model, timeout)
        except BaseException as exc:  # noqa: BLE001 - класифікує викликаючий шар
            outcome.error = exc
        outcome.latency_ms = int((time.monotonic() - call_started) * 1000)
        with outcomes_lock:
            outcomes.append(outcome)
        if after_outcome_recorded is not None:
            after_outcome_recorded(outcome)
        if outcome.succeeded:
            with winner_lock:
                if winner["outcome"] is None:
                    winner["outcome"] = outcome
                    # Скасовуємо решту хвилі: другий успіх нікому не потрібен.
                    stop.set()
            return
        if outcome.error is not None and aborts_wave is not None:
            try:
                terminal = bool(aborts_wave(outcome.error))
            except Exception:
                terminal = False
            if terminal:
                with winner_lock:
                    if winner["outcome"] is None and not aborted["reason"]:
                        aborted["reason"] = "model_terminal"
                        stop.set()
                return
        # Останній кандидат хвилі впав, і чекати більше нікого: знімаємо
        # очікування, щоб викликаючий шар одразу пішов на fallback-модель.
        with outcomes_lock:
            finished = sum(1 for item in outcomes if not item.skipped_reason)
            skipped = sum(1 for item in outcomes if item.skipped_reason)
        if finished + skipped >= len(candidates):
            with winner_lock:
                if winner["outcome"] is None:
                    stop.set()

    delays: list = []
    cumulative = 0.0
    for position, (key_name, _value, model) in enumerate(candidates):
        if position == 0:
            delays.append(0.0)
            continue
        previous_key, _pv, previous_model = candidates[position - 1]
        hint = 0
        if expected_latency_ms is not None:
            try:
                hint = int(expected_latency_ms(previous_key, previous_model) or 0)
            except Exception:
                hint = 0
        cumulative += _stagger_for(previous_key, previous_model, hint)
        delays.append(cumulative)

    workers = max(1, min(int(max_in_flight), len(candidates)))
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ig-hedge")
    dispatched = []
    try:
        for index, ((key_name, key_value, model), delay) in enumerate(
            zip(candidates, delays), start=1
        ):
            pool.submit(worker, index, key_name, key_value, model, delay)
            dispatched.append((index, key_name, model))
        # Чекаємо ПЕРШОГО успіху, а не завершення всієї хвилі. Це і є суть
        # хеджування: якщо один ключ висить повні 12 с, а інший відповів за 2 с,
        # клієнт мусить отримати відповідь за 2 с. Інакше hedged-виклик
        # вироджується в найповільнішого кандидата і сенсу не має.
        stop.wait(timeout=max(0.0, remaining()))
    finally:
        # Не блокуємось на «відсталих»: їхні HTTP-виклики доживуть самі й
        # завершаться по власному timeout. Ми лише не чекаємо на них.
        pool.shutdown(wait=False)

    with outcomes_lock:
        collected = list(outcomes)
    seen = {item.candidate_index for item in collected}
    for index, key_name, model in dispatched:
        if index in seen:
            continue
        # Кандидат був відправлений, але ми не дочекались його результату.
        # Це НЕ відказ: ми просто не знаємо, чим би він закінчився, і саме так
        # це має бути записано — інакше скорборд порахує його провалом.
        collected.append(
            HedgeOutcome(
                key_name, model, index, time.monotonic(),
                skipped_reason=(
                    "winner_found"
                    if winner["outcome"] is not None
                    and index not in provider_started
                    else "abandoned_after_winner"
                )
                if winner["outcome"] is not None
                else "abandoned_unfinished",
            )
        )

    return HedgeWave(
        winner["outcome"],
        sorted(collected, key=lambda item: item.candidate_index),
        time.monotonic() - started,
    )
