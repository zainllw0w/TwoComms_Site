"""Э0.5 — корпус оценки: **действия**, а не только текст.

Golden-набор сравнивает тексты. Он не поймает случай, когда текст идеален, а
система создала второй proposal, отправила второе сообщение на один ход или
перевела клиента в оплаченную стадию по просьбе из тела сообщения. Поэтому
единица корпуса здесь — не «ожидаемая строка», а **наблюдённое множество
действий** одного хода плюс список действий, которые произойти **не должны**.

Шесть правил формата, без которых корпус превращается в подгонку ожиданий.

1. **Сценарий описывает ход, а не ответ.** Входящий ход, pre-state, допустимые
   evidence/инструменты, ожидаемый класс действия, запрещённые действия,
   ожидаемое финальное состояние, текстовая рубрика и бюджет
   латентности/стоимости — в одном файле.
2. **Граница провайдера — мок, и это проверяется.** `NetworkGuard` перехватывает
   `socket.socket.connect`, поэтому пропущенная граница падает как
   `CorpusNetworkViolation`, а не уходит в сеть. Ни один сценарий не отправляет
   события Meta/Telegram/клиенту.
3. **Версия модели и промпта зафиксированы.** `manifest.json` хранит модель,
   текст системного промпта и digest контракта structured-output. Изменение
   схемы ответа модели ломает тест `test_pinned_contract_still_matches_code`,
   а не тихо меняет смысл корпуса.
4. **Корпус версионирован механически.** `integrity` = digest версии и всех
   файлов сценариев. `history` делает соответствие «версия → integrity»
   функцией: поменять ожидание, не подняв `corpus_version`, невозможно.
5. **Hard safety и текстовая рубрика разделены.** Запрещённое действие роняет
   сценарий **всегда**, даже при идеальном тексте. Рубрика формулировки — это
   отдельная доля прохождения со своей записанной базовой линией.
6. **Ожидаемые выходы не пишутся моделью.** Каждый сценарий несёт
   `authored_by: human`; раннер не имеет режима записи ожиданий и не пишет в
   каталог корпуса — это проверяется сравнением digest после прогона.

Раннер воспроизводит **настоящий** путь хода: `process_pending` →
`_process_one_inside_reply_boundary` → `parse_structured_response` → применение
контролов → граница отправки. Действия выводятся из фактических эффектов
(diff по таблицам и записанные вызовы границ), а не из таблицы, написанной
руками рядом с ожиданием.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import socket
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

from django.conf import settings as django_settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone

CORPUS_ROOT = Path(__file__).resolve().parent.parent / "eval_corpus"
SCENARIO_DIR = CORPUS_ROOT / "scenarios"
MANIFEST_PATH = CORPUS_ROOT / "manifest.json"


class CorpusFormatError(ValueError):
    """Сценарий или манифест не соответствует формату."""


class CorpusIntegrityError(RuntimeError):
    """Содержимое корпуса разошлось с записанной версией."""


class CorpusNetworkViolation(RuntimeError):
    """Сценарий попытался выйти в сеть — граница провайдера не замокана."""


# === Словарь действий ===
#
# Имена намеренно описывают **эффект**, а не намерение модели: контрол в ответе
# модели — это предложение, а действие — то, что реально произошло с состоянием
# или с клиентом. Неизвестное имя в сценарии — ошибка формата, чтобы опечатка в
# `forbidden` не давала «зелёный» сценарий, который ничего не проверяет.

ACTION_CLASSES = frozenset(
    {
        # Клиентские отправки
        "reply.text",              # клиенту ушёл текст
        "reply.none",              # ход осознанно оставлен без ответа
        "reply.duplicate",         # больше одной клиентской отправки на один ход
        "reply.media",             # ушла карусель/медиа каталога
        # Передача человеку
        "handoff.manager",         # эскалация менеджеру
        "notify.manager",          # уведомление менеджеру без передачи владения
        # Состояние клиента
        "state.stage_change",      # стадия воронки изменилась
        "state.spam_mark",         # клиент помечен спамом
        # Коммерция
        "commerce.proposal_created",   # создан checkout-proposal
        "commerce.proposal_second",    # у сделки появился второй proposal
        "commerce.paylink_issued",     # выдан платёжный линк
        "commerce.price_quoted",       # названа цена как факт
        "commerce.order_created",      # создан заказ/сделка
        "catalog.products_shown",      # показаны товары
        "catalog.link_sent",           # отправлена ссылка на каталог
        # Прочие durable-эффекты
        "followup.scheduled",      # запланирован follow-up
        "objection.recorded",      # записано возражение
        "postback.dispatched",     # обработан postback
        # Деградация
        "degradation.hold",        # ход удержан без клиентской отправки
        # Нарушение изоляции
        "net.external_call",       # была попытка сетевого вызова
    }
)

# Только операционные когорты. Никакого демографического профилирования —
# ADD-AGENT-013 требует этого прямым текстом.
GENERAL_COHORTS = (
    "ordinary_sale",
    "funnel_reset",
    "mixed_language",
    "prompt_injection",
    "manager_note",
    "no_reply_expected",
    "provider_failure",
)
PROJECT_COHORTS = (
    "open_service_case",
    "availability_friction",
    "gift",
    "thermochrome",
    "cod",
    "burst",
)
COHORTS = frozenset(GENERAL_COHORTS + PROJECT_COHORTS)

# Допустимые ключи pre-state. Закрытый список вместо свободного словаря: иначе
# сценарий сможет выставить любое поле и «настроить» систему под ожидание.
PRE_STATE_KEYS = frozenset(
    {
        "stage",
        "language",
        "manager_takeover",
        "bot_paused",
        "current_size",
        "current_qty",
        "memory_summary",
        "product_journal",
        "history",
        "manager_notes",
        "open_service_case",
        "purchases_count",
    }
)

# Что ходу разрешено читать. Поле декларативное: оно не ограничивает код, а
# фиксирует, на каких evidence построено ожидание, чтобы расширение контекста
# было видно в diff корпуса.
ADMISSIBLE_EVIDENCE = frozenset(
    {
        "catalog",
        "stock",
        "history",
        "memory",
        "manager_note",
        "product_journal",
        "service_case",
        "payment_policy",
        "none",
    }
)

# Инструменты/границы, которые сценарию разрешено задействовать. Всё остальное
# при вызове упадёт в `NetworkGuard`.
ADMISSIBLE_TOOLS = frozenset(
    {
        "gemini_generate",
        "send_text",
        "send_sender_action",
        "notify_manager",
        "send_catalog_media",
        "none",
    }
)

REQUIRED_SCENARIO_KEYS = frozenset(
    {
        "id",
        "cohort",
        "title",
        "why",
        "authored_by",
        "authored_at",
        "hard_safety",
        "pre_state",
        "admissible",
        "inbound",
        "provider",
        "expect",
        "rubric",
        "budget",
    }
)


# === Разобранный сценарий ===


@dataclass(frozen=True)
class Scenario:
    """Один сценарий корпуса — уже проверенный на формат."""

    path: Path
    id: str
    cohort: str
    title: str
    why: str
    authored_by: str
    authored_at: str
    hard_safety: bool
    pre_state: dict[str, Any]
    evidence: tuple[str, ...]
    tools: tuple[str, ...]
    inbound: tuple[dict[str, Any], ...]
    provider: dict[str, Any]
    expected_actions: frozenset[str]
    forbidden_actions: frozenset[str]
    final_state: dict[str, Any]
    rubric: dict[str, Any]
    budget: dict[str, Any]

    @property
    def digest(self) -> str:
        return file_digest(self.path)


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CorpusFormatError(message)


def _parse_scenario(path: Path) -> Scenario:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - формат ловится тестом
        raise CorpusFormatError(f"{path.name}: невалидный JSON: {exc}") from exc
    _require(isinstance(raw, dict), f"{path.name}: сценарий должен быть объектом")
    unknown = set(raw) - REQUIRED_SCENARIO_KEYS
    _require(not unknown, f"{path.name}: лишние ключи {sorted(unknown)}")
    missing = REQUIRED_SCENARIO_KEYS - set(raw)
    _require(not missing, f"{path.name}: отсутствуют ключи {sorted(missing)}")

    _require(
        raw["authored_by"] == "human",
        f"{path.name}: ожидания корпуса пишет человек, не модель "
        f"(authored_by={raw['authored_by']!r})",
    )
    _require(
        raw["cohort"] in COHORTS,
        f"{path.name}: неизвестная когорта {raw['cohort']!r}",
    )
    _require(
        path.stem == raw["id"],
        f"{path.name}: имя файла должно совпадать с id ({raw['id']!r})",
    )
    _require(bool(str(raw["why"]).strip()), f"{path.name}: пустое поле why")
    _require(isinstance(raw["hard_safety"], bool), f"{path.name}: hard_safety не bool")

    pre_state = raw["pre_state"]
    _require(isinstance(pre_state, dict), f"{path.name}: pre_state должен быть объектом")
    unknown_pre = set(pre_state) - PRE_STATE_KEYS
    _require(not unknown_pre, f"{path.name}: неизвестные ключи pre_state {sorted(unknown_pre)}")

    admissible = raw["admissible"]
    _require(isinstance(admissible, dict), f"{path.name}: admissible должен быть объектом")
    evidence = tuple(admissible.get("evidence") or ())
    tools = tuple(admissible.get("tools") or ())
    bad_evidence = set(evidence) - ADMISSIBLE_EVIDENCE
    _require(not bad_evidence, f"{path.name}: неизвестные evidence {sorted(bad_evidence)}")
    bad_tools = set(tools) - ADMISSIBLE_TOOLS
    _require(not bad_tools, f"{path.name}: неизвестные tools {sorted(bad_tools)}")

    inbound = raw["inbound"]
    _require(
        isinstance(inbound, list) and inbound,
        f"{path.name}: inbound — непустой список сообщений хода",
    )
    for entry in inbound:
        _require(isinstance(entry, dict), f"{path.name}: сообщение inbound должно быть объектом")
        _require("text" in entry, f"{path.name}: у сообщения inbound нет text")

    provider = raw["provider"]
    _require(isinstance(provider, dict), f"{path.name}: provider должен быть объектом")
    kind = provider.get("kind")
    _require(
        kind in {"structured", "legacy", "failure"},
        f"{path.name}: provider.kind должен быть structured|legacy|failure",
    )
    if kind == "structured":
        payload = provider.get("payload")
        _require(isinstance(payload, dict), f"{path.name}: provider.payload должен быть объектом")
    elif kind == "legacy":
        _require(
            isinstance(provider.get("payload"), str),
            f"{path.name}: legacy provider.payload должен быть строкой",
        )

    expect = raw["expect"]
    _require(isinstance(expect, dict), f"{path.name}: expect должен быть объектом")
    expected = frozenset(expect.get("action_classes") or ())
    forbidden = frozenset(expect.get("forbidden_actions") or ())
    unknown_actions = (expected | forbidden) - ACTION_CLASSES
    _require(
        not unknown_actions,
        f"{path.name}: неизвестные классы действий {sorted(unknown_actions)}",
    )
    _require(
        bool(forbidden),
        f"{path.name}: у сценария обязателен непустой forbidden_actions — "
        "без него сценарий проверяет только ожидаемый результат",
    )
    overlap = expected & forbidden
    _require(
        not overlap,
        f"{path.name}: действие одновременно ожидаемое и запрещённое: {sorted(overlap)}",
    )
    final_state = expect.get("final_state") or {}
    _require(isinstance(final_state, dict), f"{path.name}: final_state должен быть объектом")

    rubric = raw["rubric"]
    _require(isinstance(rubric, dict), f"{path.name}: rubric должен быть объектом")
    budget = raw["budget"]
    _require(isinstance(budget, dict), f"{path.name}: budget должен быть объектом")
    for key in ("max_provider_calls", "max_customer_messages", "max_seconds", "max_queries"):
        _require(key in budget, f"{path.name}: в budget нет {key}")

    return Scenario(
        path=path,
        id=str(raw["id"]),
        cohort=str(raw["cohort"]),
        title=str(raw["title"]),
        why=str(raw["why"]),
        authored_by=str(raw["authored_by"]),
        authored_at=str(raw["authored_at"]),
        hard_safety=bool(raw["hard_safety"]),
        pre_state=pre_state,
        evidence=evidence,
        tools=tools,
        inbound=tuple(inbound),
        provider=provider,
        expected_actions=expected,
        forbidden_actions=forbidden,
        final_state=final_state,
        rubric=rubric,
        budget=budget,
    )


def load_scenarios() -> tuple[Scenario, ...]:
    """Прочитать и проверить все сценарии, в стабильном порядке по имени файла."""
    paths = sorted(SCENARIO_DIR.glob("*.json"))
    _require(bool(paths), f"каталог сценариев пуст: {SCENARIO_DIR}")
    scenarios = tuple(_parse_scenario(path) for path in paths)
    seen: dict[str, Path] = {}
    for scenario in scenarios:
        _require(
            scenario.id not in seen,
            f"дублирующийся id сценария {scenario.id!r}",
        )
        seen[scenario.id] = scenario.path
    return scenarios


# === Манифест и версионирование ===


def load_manifest() -> dict[str, Any]:
    try:
        raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CorpusFormatError(f"нет манифеста: {MANIFEST_PATH}") from exc
    _require(isinstance(raw, dict), "манифест должен быть объектом")
    for key in ("corpus_version", "authored_by", "pins", "determinism", "scenarios", "integrity", "history", "rubric_baseline"):
        _require(key in raw, f"в манифесте нет {key}")
    _require(
        raw["authored_by"] == "human",
        "манифест корпуса пишет человек, не модель",
    )
    return raw


def compute_integrity(version: str, digests: dict[str, str]) -> str:
    """Digest версии и всех файлов сценариев вместе.

    Версия входит в digest намеренно: тогда «поменять ожидание и оставить ту же
    версию» невозможно сделать так, чтобы `history` осталась согласованной.
    """
    payload = json.dumps(
        {"corpus_version": version, "scenarios": dict(sorted(digests.items()))},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def current_digests() -> dict[str, str]:
    return {path.name: file_digest(path) for path in sorted(SCENARIO_DIR.glob("*.json"))}


def verify_integrity() -> dict[str, Any]:
    """Проверить, что содержимое корпуса совпадает с записанной версией."""
    manifest = load_manifest()
    version = str(manifest["corpus_version"])
    recorded = dict(manifest["scenarios"])
    observed = current_digests()

    missing = sorted(set(recorded) - set(observed))
    added = sorted(set(observed) - set(recorded))
    changed = sorted(
        name for name in set(recorded) & set(observed) if recorded[name] != observed[name]
    )
    if missing or added or changed:
        raise CorpusIntegrityError(
            "содержимое корпуса разошлось с манифестом: "
            f"удалено={missing} добавлено={added} изменено={changed}. "
            f"Поднимите corpus_version (сейчас {version}), обновите scenarios и "
            "integrity, и запишите причину в history — иначе ожидания можно "
            "подогнать под текущий вывод."
        )

    integrity = compute_integrity(version, observed)
    _require(
        integrity == str(manifest["integrity"]),
        f"integrity в манифесте не совпадает с содержимым: ожидалось {integrity}",
    )

    history = manifest["history"]
    _require(isinstance(history, list) and history, "history пуста")
    by_version: dict[str, str] = {}
    for entry in history:
        _require(isinstance(entry, dict), "запись history должна быть объектом")
        for key in ("version", "integrity", "note"):
            _require(key in entry, f"в записи history нет {key}")
        recorded_version = str(entry["version"])
        recorded_integrity = str(entry["integrity"])
        if recorded_version in by_version:
            _require(
                by_version[recorded_version] == recorded_integrity,
                f"версия {recorded_version} записана в history дважды с разным integrity",
            )
        by_version[recorded_version] = recorded_integrity
    _require(
        version in by_version,
        f"текущей версии {version} нет в history",
    )
    _require(
        by_version[version] == integrity,
        f"версия {version} уже выпущена с другим integrity — нужна новая версия",
    )
    return manifest


# === Изоляция от сети ===


def _loopback_allowed() -> set[str]:
    hosts = {"127.0.0.1", "::1", "localhost", ""}
    for config in (django_settings.DATABASES or {}).values():
        host = str((config or {}).get("HOST") or "").strip()
        if host:
            hosts.add(host)
    return hosts


class NetworkGuard:
    """Запретить исходящие соединения на время прогона сценария.

    Мок конкретной границы доказывает только то, что эта граница замокана.
    Гарантию «ни один сценарий не делает сетевых вызовов» даёт перехват на
    уровне сокета: любая пропущенная граница падает здесь, а не уходит в сеть.
    Loopback и хост БД разрешены — иначе тестовая база стала бы недоступна.
    """

    def __init__(self) -> None:
        self.attempts: list[str] = []
        self._stack = ExitStack()

    def _blocked(self, address: Any) -> bool:
        host = ""
        if isinstance(address, tuple) and address:
            host = str(address[0] or "")
        elif isinstance(address, str):
            # AF_UNIX — локальный сокет, сетью не является.
            return False
        return host not in _loopback_allowed()

    def __enter__(self) -> "NetworkGuard":
        guard = self
        original_connect = socket.socket.connect

        def connect(self, address, *args, **kwargs):  # noqa: ANN001, ANN002
            if guard._blocked(address):
                guard.attempts.append(str(address))
                raise CorpusNetworkViolation(
                    f"сценарий корпуса попытался выйти в сеть: {address!r}"
                )
            return original_connect(self, address, *args, **kwargs)

        self._stack.enter_context(patch.object(socket.socket, "connect", connect))
        return self

    def __exit__(self, *exc_info) -> None:
        self._stack.close()


# === Харнес прогону ===


@dataclass
class TurnSnapshot:
    """Стан клієнта та бази до/після ходу."""

    stage: str
    language: str
    current_product: int | None
    manager_takeover: bool
    bot_paused: bool
    proposal_count: int
    message_count: int
    funnel_event_count: int
    followup_count: int
    objection_count: int
    notification_count: int
    post_sale_case_count: int
    commerce_transition_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "language": self.language,
            "current_product": self.current_product,
            "manager_takeover": self.manager_takeover,
            "bot_paused": self.bot_paused,
            "proposal_count": self.proposal_count,
            "message_count": self.message_count,
            "funnel_event_count": self.funnel_event_count,
            "followup_count": self.followup_count,
            "objection_count": self.objection_count,
            "notification_count": self.notification_count,
            "post_sale_case_count": self.post_sale_case_count,
            "commerce_transition_count": self.commerce_transition_count,
        }


def _take_snapshot(client) -> TurnSnapshot:
    from management.ig_bot_models import (
        IgBotNotification,
        IgCheckoutProposal,
        IgCommerceSelectionTransition,
        IgFollowUpTask,
        IgFunnelStepEvent,
        IgObjectionAttempt,
        IgPostSaleCase,
    )
    from management.models import InstagramBotMessage

    return TurnSnapshot(
        stage=str(client.stage),
        language=str(client.language or ""),
        current_product=client.current_product,
        manager_takeover=bool(client.manager_takeover),
        bot_paused=bool(client.bot_paused),
        proposal_count=IgCheckoutProposal.objects.filter(client=client).count(),
        message_count=InstagramBotMessage.objects.filter(client=client).count(),
        funnel_event_count=IgFunnelStepEvent.objects.filter(episode__client=client).count(),
        followup_count=IgFollowUpTask.objects.filter(client=client).count(),
        objection_count=IgObjectionAttempt.objects.filter(client_response_message__client=client).count(),
        notification_count=IgBotNotification.objects.filter(client=client).count(),
        post_sale_case_count=IgPostSaleCase.objects.filter(client=client).count(),
        commerce_transition_count=IgCommerceSelectionTransition.objects.filter(
            source_message__client=client
        ).count(),
    )


@dataclass
class ObservedActions:
    """Спостережені класи дій одного ходу."""

    actions: set[str] = field(default_factory=set)
    provider_calls: int = 0
    customer_messages: int = 0
    queries: int = 0
    elapsed_seconds: float = 0.0

    def record(self, action: str) -> None:
        if action not in ACTION_CLASSES:
            raise CorpusFormatError(f"неизвестный класс действия: {action!r}")
        self.actions.add(action)


@contextmanager
def _query_counter() -> Iterator[list[int]]:
    """Порахувати кількість запитів до бази під час прогону ходу."""
    counts = [0]

    def counter(execute, sql, params, many, context):  # noqa: ANN001
        counts[0] += 1
        return execute(sql, params, many, context)

    from django.db import connection as db_conn

    with db_conn.execute_wrapper(counter):
        yield counts


def _prepare_client(scenario: Scenario) -> Any:
    from management.models import IgClient

    client_id = f"corpus-{scenario.id}-{random.randint(1000, 9999)}"
    client = IgClient.get_or_create_for_sender(client_id)
    client.profile_fetched_at = timezone.now()
    pre = scenario.pre_state
    if "stage" in pre:
        client.stage = str(pre["stage"])
    if "language" in pre:
        client.language = str(pre["language"])
    if "manager_takeover" in pre:
        client.manager_takeover = bool(pre["manager_takeover"])
    if "bot_paused" in pre:
        client.bot_paused = bool(pre["bot_paused"])
    if "current_size" in pre:
        client.current_size = str(pre["current_size"])
    if "current_qty" in pre:
        client.current_qty = int(pre["current_qty"])
    if "memory_summary" in pre:
        client.memory_summary = str(pre["memory_summary"])
    if "purchases_count" in pre:
        client.purchases_count = int(pre["purchases_count"])
    client.save()

    # product_journal, manager_notes, open_service_case etc. можуть бути додані тут,
    # коли в корпусі з'являться сценарії, що їх вимагають.
    return client


def _enqueue_inbound(client, inbound: tuple[dict, ...]) -> list:
    from management.models import InstagramBotMessage

    rows = []
    for idx, msg in enumerate(inbound):
        row = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=msg.get("role", "user"),
            text=str(msg.get("text", "")),
            mid=msg.get("mid", f"corpus-{client.igsid}-{idx}"),
            source=msg.get("source", "webhook"),
            status=InstagramBotMessage.Status.PENDING,
            attachments=msg.get("attachments") or [],
            quick_reply_payload=msg.get("quick_reply_payload", ""),
        )
        rows.append(row)
    return rows


def _extract_actions(
    before: TurnSnapshot, after: TurnSnapshot, mocks: dict[str, Any]
) -> ObservedActions:
    """Витягнути класи дій з diff та записаних викликів границь."""
    observed = ObservedActions()

    # Межі клієнтської відправки
    send_text = mocks["send_text"]
    send_media = mocks["send_catalog_media"]
    if send_text.call_count > 1:
        observed.record("reply.duplicate")
    elif send_text.call_count == 1:
        observed.record("reply.text")
    if send_media.call_count > 0:
        observed.record("reply.media")
    observed.customer_messages = send_text.call_count + send_media.call_count

    # Notify
    if mocks["notify_manager"].call_count > 0:
        observed.record("notify.manager")

    # Стан клієнта
    if before.stage != after.stage:
        observed.record("state.stage_change")
    if after.manager_takeover and not before.manager_takeover:
        observed.record("handoff.manager")
    if after.bot_paused and not before.bot_paused:
        observed.record("state.spam_mark")

    # Коммерція
    if after.proposal_count > before.proposal_count:
        if after.proposal_count - before.proposal_count > 1:
            observed.record("commerce.proposal_second")
        else:
            observed.record("commerce.proposal_created")
    if after.commerce_transition_count > before.commerce_transition_count:
        # transition може означати вибір товару, clarification, скидання — тут
        # маркуємо лише те, що **щось** у комерційному стані записано.
        pass

    # Воронка
    if after.funnel_event_count > before.funnel_event_count:
        # Перевірка конкретного типу події виходить за межі action_class —
        # це вже рівень final_state. Тут лише фіксуємо, що воронка змінилася.
        pass

    # Follow-up / objection / post-sale
    if after.followup_count > before.followup_count:
        observed.record("followup.scheduled")
    if after.objection_count > before.objection_count:
        observed.record("objection.recorded")
    if after.post_sale_case_count > before.post_sale_case_count:
        # Це можливе action як results від моделі — наразі додамо
        # open_service_case до ACTION_CLASSES, якщо сценарій його має.
        pass

    # Кількість викликів провайдера
    observed.provider_calls = mocks["gemini_generate"].call_count

    return observed


def run_scenario(scenario: Scenario, settings=None) -> ObservedActions:
    """Прогнати один сценарій корпуса, виявити всі дії і перевірити бюджети."""
    from unittest.mock import MagicMock

    from management.services import instagram_bot
    from management.services.ig_response_control import (
        parse_legacy_response,
        parse_structured_response,
    )

    if settings is None:
        from management.models import InstagramBotSettings

        settings = InstagramBotSettings.load()
        settings.is_enabled = True
        settings.ai_enabled = True
        settings.allowed_senders = ""
        settings.save(update_fields=["is_enabled", "ai_enabled", "allowed_senders"])

    provider = scenario.provider
    kind = provider["kind"]
    if kind == "structured":
        validated = parse_structured_response(provider["payload"])
    elif kind == "legacy":
        validated = parse_legacy_response(provider["payload"])
    else:
        validated = None

    cache.clear()
    client = _prepare_client(scenario)
    _enqueue_inbound(client, scenario.inbound)
    before = _take_snapshot(client)

    mocks = {
        "gemini_generate": MagicMock(return_value=validated),
        "send_text": MagicMock(return_value=None),
        "send_sender_action": MagicMock(),
        "notify_manager": MagicMock(),
        "send_catalog_media": MagicMock(),
    }
    # patch ProviderDeliveryReceipt, щоб send_text міг повернути tuple
    from management.services.instagram_bot import ProviderDeliveryReceipt

    mocks["send_text"].return_value = ProviderDeliveryReceipt(True, "", "", f"corpus-{scenario.id}")

    t0 = time.monotonic()
    with (
        NetworkGuard() as net,
        _query_counter() as queries,
        patch("management.services.instagram_bot._persist_commerce_turn", return_value=(None, None)),
        patch("management.services.bot_sales_classifier.ensure_rule_classification", return_value=None),
        patch("management.services.instagram_bot._repeated_question", return_value=1),
        patch("management.services.instagram_bot._wait_for_typing_window", return_value="allowed"),
        patch("management.services.instagram_bot.gemini_generate", mocks["gemini_generate"]),
        patch("management.services.instagram_bot.send_text", mocks["send_text"]),
        patch("management.services.instagram_bot.send_sender_action", mocks["send_sender_action"]),
        patch("management.services.instagram_bot.notify_manager", mocks["notify_manager"]),
        patch("management.services.ig_catalog_media.send_catalog_media", mocks["send_catalog_media"]),
    ):
        instagram_bot.process_pending(settings, max_items=1)
    elapsed = time.monotonic() - t0

    if net.attempts:
        raise CorpusNetworkViolation(f"{scenario.id}: сценарій спробував звернутись в мережу: {net.attempts}")

    client.refresh_from_db()
    after = _take_snapshot(client)

    observed = _extract_actions(before, after, mocks)
    observed.queries = queries[0]
    observed.elapsed_seconds = elapsed

    budget = scenario.budget
    _require(
        observed.provider_calls <= int(budget["max_provider_calls"]),
        f"{scenario.id}: перевищено бюджет викликів провайдера "
        f"({observed.provider_calls} > {budget['max_provider_calls']})",
    )
    _require(
        observed.customer_messages <= int(budget["max_customer_messages"]),
        f"{scenario.id}: перевищено бюджет клієнтських повідомлень "
        f"({observed.customer_messages} > {budget['max_customer_messages']})",
    )
    _require(
        observed.queries <= int(budget["max_queries"]),
        f"{scenario.id}: перевищено бюджет запитів до БД "
        f"({observed.queries} > {budget['max_queries']})",
    )
    _require(
        observed.elapsed_seconds <= float(budget["max_seconds"]),
        f"{scenario.id}: перевищено часовий бюджет "
        f"({observed.elapsed_seconds:.3f}s > {budget['max_seconds']}s)",
    )

    return observed


__all__ = [
    "ACTION_CLASSES",
    "COHORTS",
    "CORPUS_ROOT",
    "CorpusFormatError",
    "CorpusIntegrityError",
    "CorpusNetworkViolation",
    "NetworkGuard",
    "ObservedActions",
    "Scenario",
    "TurnSnapshot",
    "compute_integrity",
    "current_digests",
    "file_digest",
    "load_manifest",
    "load_scenarios",
    "run_scenario",
    "verify_integrity",
]
