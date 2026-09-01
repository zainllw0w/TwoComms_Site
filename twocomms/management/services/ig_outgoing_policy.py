"""Э0.4 — единственное решение о праве отправить исходящее клиенту.

Модуль **чистый**: ни ORM, ни кеша, ни сети, ни `timezone.now()`. Всё, что может
изменить решение, приходит аргументом, поэтому политику можно проверить без
провайдера и без базы. Побочный эффект (durable task, финальная revalidation,
receipt-first) живёт снаружи — см. `ig_outgoing_gate`.

Почему это отдельный объект. Сейчас проверки окна, opt-out, takeover и follow-up
политик разбросаны по потокам, и каждый новый исходящий поток трактует
24-часовое окно по-своему (`02_ANALYSIS.md` → `NEW-POLICY-001`). Один объект
решения убирает расхождение и даёт метрике стабильные коды.

**Критическая поправка к eligibility.** «Человек ответил текстом» — НЕ основание
для обхода окна платформы. Разрешено ровно три основания:

    внутри стандартного окна                              ИЛИ
    доказанный consent по этой теме (если канал даёт его)  ИЛИ
    явно разрешённый провайдером тип сообщения с соблюдением его условий

Второе и третье основание работают только если проверенный контракт провайдера
их объявляет. Непроверенная capability никогда не даёт `allow` — только `block`
или `defer` (правило по умолчанию).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

POLICY_VERSION = "outgoing-policy-v1"

# ---------------------------------------------------------------------------
# Исходы
# ---------------------------------------------------------------------------
ALLOW = "allow"
DEFER = "defer"
BLOCK = "block"
ESCALATE = "escalate"
DECISIONS = frozenset({ALLOW, DEFER, BLOCK, ESCALATE})

# ---------------------------------------------------------------------------
# policy_basis — обязателен для `allow`. Без него нельзя доказать, ПОЧЕМУ
# отправка была разрешена, а значит нельзя разобрать инцидент.
# ---------------------------------------------------------------------------
BASIS_STANDARD_WINDOW = "standard_window"
BASIS_PROVEN_CONSENT = "proven_consent"
BASIS_PROVIDER_ALLOWED_TYPE = "provider_allowed_message_type"
POLICY_BASES = frozenset({
    BASIS_STANDARD_WINDOW,
    BASIS_PROVEN_CONSENT,
    BASIS_PROVIDER_ALLOWED_TYPE,
})

# ---------------------------------------------------------------------------
# message_purpose
# ---------------------------------------------------------------------------
PURPOSE_TRANSACTIONAL = "transactional"
PURPOSE_SERVICE = "service"
PURPOSE_MARKETING = "marketing"
MESSAGE_PURPOSES = frozenset({
    PURPOSE_TRANSACTIONAL,
    PURPOSE_SERVICE,
    PURPOSE_MARKETING,
})

# ---------------------------------------------------------------------------
# channel_app_type — тип приложения и транспорт. Значения совпадают с
# транспортами `instagram_bot`, чтобы адаптер не выдумывал третий словарь.
# ---------------------------------------------------------------------------
APP_TYPE_INSTAGRAM_LOGIN = "instagram_login"
APP_TYPE_LEGACY_PAGE = "legacy_page"

# Версия контракта провайдера, реально прочитанная и зафиксированная аудитом.
# Любая другая строка — непроверенная capability, значит `block`.
VERIFIED_CONTRACT_VERSION = "meta-2026-08"

# Стандартное окно держим на 23 часах, а не на 24: это тот же осознанный запас,
# что в `ig_lifecycle.RESPONSE_WINDOW`, и один источник истины лучше двух чисел.
STANDARD_WINDOW = timedelta(hours=23)


class UnstablePolicyDecision(ValueError):
    """Решение нарушает собственный контракт (например, `allow` без basis)."""


@dataclass(frozen=True, slots=True)
class ProviderMessageType:
    """Тип сообщения, который провайдер разрешает вне стандартного окна.

    Условия применения — часть типа, а не рассуждение вызывающего кода.
    `HUMAN_AGENT` у Meta требует ответа живого человека и ограничен возрастом
    последнего сообщения клиента; поэтому оба ограничения выражены полями.
    """

    name: str
    requires_human_authored: bool = True
    max_age: timedelta | None = None
    purposes: frozenset[str] = frozenset({PURPOSE_TRANSACTIONAL, PURPOSE_SERVICE})


@dataclass(frozen=True, slots=True)
class PlatformContract:
    """Проверенный контракт провайдера для одного типа приложения."""

    channel_app_type: str
    version: str
    standard_window: timedelta
    # Доказанного consent-протокола у Meta Direct для этого приложения нет,
    # поэтому по умолчанию False. Включать только вместе с документом.
    consent_basis_proven: bool = False
    allowed_message_types: tuple[ProviderMessageType, ...] = ()

    def message_type(self, name: str) -> ProviderMessageType | None:
        for candidate in self.allowed_message_types:
            if candidate.name == name:
                return candidate
        return None


# Meta документирует `HUMAN_AGENT` для ответа живого человека за пределами
# стандартного окна. Условия — ответ человека и 7 суток от сообщения клиента;
# автоматические продажи, напоминания и shipment-задачи под него не попадают.
_HUMAN_AGENT = ProviderMessageType(
    name="HUMAN_AGENT",
    requires_human_authored=True,
    max_age=timedelta(days=7),
    purposes=frozenset({PURPOSE_TRANSACTIONAL, PURPOSE_SERVICE}),
)

VERIFIED_PLATFORM_CONTRACTS: dict[tuple[str, str], PlatformContract] = {
    (APP_TYPE_INSTAGRAM_LOGIN, VERIFIED_CONTRACT_VERSION): PlatformContract(
        channel_app_type=APP_TYPE_INSTAGRAM_LOGIN,
        version=VERIFIED_CONTRACT_VERSION,
        standard_window=STANDARD_WINDOW,
        allowed_message_types=(_HUMAN_AGENT,),
    ),
    (APP_TYPE_LEGACY_PAGE, VERIFIED_CONTRACT_VERSION): PlatformContract(
        channel_app_type=APP_TYPE_LEGACY_PAGE,
        version=VERIFIED_CONTRACT_VERSION,
        standard_window=STANDARD_WINDOW,
        allowed_message_types=(_HUMAN_AGENT,),
    ),
}

# ---------------------------------------------------------------------------
# event_kind. Реестр перечисляет только ПЕРЕВЕДЁННЫЕ на политику потоки.
# Незарегистрированный вид события — `block`, а не «наверное можно»: это и есть
# no-send default для ещё не миграированных producers.
# ---------------------------------------------------------------------------
EVENT_KIND_PURPOSE: dict[str, str] = {
    "lifecycle.payment_verified": PURPOSE_TRANSACTIONAL,
    "lifecycle.ttn_created": PURPOSE_TRANSACTIONAL,
    "lifecycle.parcel_arrived": PURPOSE_TRANSACTIONAL,
    "lifecycle.delivered_review_requested": PURPOSE_SERVICE,
}

# ---------------------------------------------------------------------------
# Причины отказа в правах. Строки слева — те, что реально возвращает
# `ig_reply_boundary.capture_reply_permission`; неизвестная строка не
# «пропускается», а даёт `block`.
# ---------------------------------------------------------------------------
PERMISSION_BLOCK_REASONS: dict[str, str] = {
    "opt_out": "customer_opted_out",
    "blocked": "customer_blocked",
    "hidden": "client_hidden",
    "client_missing": "client_missing",
    "sender_not_allowed": "sender_not_allowed",
}
PERMISSION_DEFER_REASONS: dict[str, str] = {
    "client_paused": "client_paused",
    "global_reply_paused": "global_reply_paused",
    "manager_takeover": "manager_takeover",
    "permission_epoch_changed": "permission_epoch_changed",
    "permission_transition_pending": "permission_transition_pending",
}

# `defer` обязан говорить, КОГДА станет можно. Исключение — только те причины,
# где горизонт принципиально неизвестен: снятие паузы делает человек.
DEFER_WITHOUT_HORIZON_REASONS = frozenset(PERMISSION_DEFER_REASONS.values())

# ---------------------------------------------------------------------------
# Реестр кодов причин. Он попадает в метрики и алерты, поэтому каждый код
# описан здесь, а тест сверяет: политика не возвращает кода вне реестра и не
# возвращает код с чужим исходом.
# ---------------------------------------------------------------------------
REASON_CODES: dict[str, tuple[str, str]] = {
    # --- allow -------------------------------------------------------------
    "within_standard_window": (
        ALLOW,
        "Сообщение клиента открыло стандартное окно, и оно ещё не истекло.",
    ),
    "proven_consent_in_scope": (
        ALLOW,
        "Контракт провайдера объявляет consent основанием, и consent по этой "
        "теме доказан и не истёк.",
    ),
    "provider_allowed_message_type": (
        ALLOW,
        "Запрошен явно разрешённый провайдером тип сообщения, и все его "
        "условия соблюдены.",
    ),
    # --- block: непроверенная capability (правило по умолчанию) ------------
    "platform_contract_unverified": (
        BLOCK,
        "Версия контракта провайдера не проверена. Никакой отправки.",
    ),
    "channel_app_type_unverified": (
        BLOCK,
        "Тип приложения/транспорт не входит в проверенные контракты.",
    ),
    "event_kind_unregistered": (
        BLOCK,
        "Поток ещё не переведён на политику: вид события не зарегистрирован.",
    ),
    "message_purpose_unknown": (
        BLOCK,
        "Цель сообщения не входит в таксономию transactional/service/marketing.",
    ),
    "message_purpose_conflicts_event_kind": (
        BLOCK,
        "Заявленная цель не совпадает с целью, закреплённой за видом события: "
        "иначе маркетинг проедет под транзакционным ярлыком.",
    ),
    "marketing_capability_unverified": (
        BLOCK,
        "Маркетинговая/реактивационная рассылка требует подтверждённой политики "
        "провайдера, consent-модели, holdout и frequency cap. Ничего из этого "
        "не проверено.",
    ),
    "evaluation_time_not_aware": (
        BLOCK,
        "Момент оценки без таймзоны: сравнивать окно нельзя.",
    ),
    "provider_message_type_unverified": (
        BLOCK,
        "Запрошенный тип сообщения не объявлен проверенным контрактом.",
    ),
    "provider_message_type_conditions_unmet": (
        BLOCK,
        "Тип сообщения разрешён, но его условия не соблюдены "
        "(не человек, чужая цель или превышен допустимый возраст).",
    ),
    "consent_basis_unverified": (
        BLOCK,
        "Consent предъявлен, но контракт этого канала не объявляет consent "
        "основанием.",
    ),
    "consent_out_of_scope": (
        BLOCK,
        "Consent есть, но по другой теме, без доказательства или уже истёк.",
    ),
    "customer_opted_out": (BLOCK, "Клиент отказался от сообщений."),
    "customer_blocked": (BLOCK, "Клиент заблокирован."),
    "client_hidden": (BLOCK, "Диалог скрыт оператором."),
    "client_missing": (BLOCK, "Строка клиента отсутствует."),
    "sender_not_allowed": (BLOCK, "Отправитель вне белого списка."),
    "permission_reason_unrecognized": (
        BLOCK,
        "Права отказаны причиной, которой нет в реестре: fail-closed.",
    ),
    "window_anchor_missing": (
        BLOCK,
        "Нет ни одного сообщения клиента: окно никогда не открывалось.",
    ),
    # --- defer -------------------------------------------------------------
    "client_paused": (DEFER, "Бот на паузе для этого клиента."),
    "global_reply_paused": (DEFER, "Ответы выключены глобально."),
    "manager_takeover": (DEFER, "Диалог ведёт менеджер."),
    "permission_epoch_changed": (
        DEFER,
        "Права изменились между захватом и проверкой.",
    ),
    "permission_transition_pending": (
        DEFER,
        "Переход прав ещё не зафиксирован.",
    ),
    "quiet_hours": (
        DEFER,
        "Локальное время клиента внутри тихих часов.",
    ),
    "frequency_cap_reached": (
        DEFER,
        "Исчерпан лимит сообщений в окне частоты.",
    ),
    "frequency_min_interval": (
        DEFER,
        "С предыдущей отправки прошло меньше минимального интервала.",
    ),
    # --- escalate ----------------------------------------------------------
    "outside_standard_window": (
        ESCALATE,
        "Окно закрыто, другого основания нет: нужен человек, а не автоотправка.",
    ),
    "open_complaint": (
        ESCALATE,
        "У клиента открытая жалоба: автоответ не должен её опередить.",
    ),
    "case_requires_human": (
        ESCALATE,
        "Открытая заявка требует решения человека.",
    ),
}


@dataclass(frozen=True, slots=True)
class ConsentScope:
    """Тема и срок consent, если канал вообще даёт такое основание."""

    topic: str = ""
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    evidence_message_id: int | None = None


@dataclass(frozen=True, slots=True)
class FrequencyState:
    """Сколько уже отправлено и когда."""

    sent_in_window: int = 0
    max_in_window: int | None = None
    window: timedelta | None = None
    last_sent_at: datetime | None = None
    min_interval: timedelta | None = None


@dataclass(frozen=True, slots=True)
class CaseRiskState:
    """Открытая заявка, жалоба, takeover, opt-out.

    `permission_reason` — строка из `ig_reply_boundary`; политика сама решает,
    временная она или окончательная, чтобы потоки не расходились в трактовке.
    """

    permission_reason: str = ""
    open_complaint: bool = False
    case_requires_human: bool = False


@dataclass(frozen=True, slots=True)
class QuietHours:
    """Тихие часы в ЛОКАЛЬНОМ времени клиента.

    Это вежливость, а не capability провайдера: отсутствие тихих часов
    (`None` в запросе) — не «непроверенная возможность», а отсутствие
    ограничения. Транзакционные сообщения тихие часы не задерживают: клиент,
    который только что оплатил, ждёт подтверждения сейчас.
    """

    start: time
    end: time
    utc_offset: timedelta = timedelta(0)

    def contains(self, moment: datetime) -> bool:
        local = (moment + self.utc_offset).timetz().replace(tzinfo=None)
        if self.start == self.end:
            return False
        if self.start < self.end:
            return self.start <= local < self.end
        return local >= self.start or local < self.end

    def next_end(self, moment: datetime) -> datetime:
        """Ближайший момент выхода из тихих часов, в той же таймзоне."""
        local_moment = moment + self.utc_offset
        candidate = datetime.combine(local_moment.date(), self.end)
        candidate = candidate.replace(tzinfo=local_moment.tzinfo)
        if candidate <= local_moment:
            candidate = datetime.combine(
                local_moment.date() + timedelta(days=1), self.end
            ).replace(tzinfo=local_moment.tzinfo)
        return candidate - self.utc_offset


@dataclass(frozen=True, slots=True)
class OutgoingRequest:
    """Вход решения (расширенный, как в Э0.4).

    `requested_message_type` и `human_authored` — носители третьей ветви
    eligibility. Без них ветвь «явно разрешённый провайдером тип сообщения»
    невыразима, и её условия пришлось бы проверять вызывающему коду, то есть
    ровно там, где потоки и расходятся.
    """

    platform_contract_version: str
    event_kind: str
    message_purpose: str
    channel_app_type: str
    latest_user_provider_ts: datetime | None = None
    consent_scope: ConsentScope | None = None
    frequency_state: FrequencyState = FrequencyState()
    case_risk_state: CaseRiskState = CaseRiskState()
    quiet_hours: QuietHours | None = None
    consent_topic_required: str = ""
    requested_message_type: str = ""
    human_authored: bool = False


@dataclass(frozen=True, slots=True)
class OutgoingDecision:
    """Выход решения. `audit` — только не-PII пары ключ/значение."""

    decision: str
    reason_code: str
    policy_basis: str = ""
    eligible_at: datetime | None = None
    audit: tuple[tuple[str, str], ...] = ()
    policy_version: str = POLICY_VERSION

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise UnstablePolicyDecision(f"unknown decision {self.decision!r}")
        expected = REASON_CODES.get(self.reason_code)
        if expected is None:
            raise UnstablePolicyDecision(
                f"reason_code {self.reason_code!r} is not documented"
            )
        if expected[0] != self.decision:
            raise UnstablePolicyDecision(
                f"reason_code {self.reason_code!r} belongs to {expected[0]!r}, "
                f"not {self.decision!r}"
            )
        if self.decision == ALLOW:
            # Обязательное поле: без основания нельзя доказать, почему
            # отправка была разрешена.
            if self.policy_basis not in POLICY_BASES:
                raise UnstablePolicyDecision(
                    "allow requires a documented policy_basis"
                )
        elif self.policy_basis:
            raise UnstablePolicyDecision(
                "policy_basis explains only an allow; leave it empty otherwise"
            )
        if self.decision == DEFER and self.eligible_at is None:
            if self.reason_code not in DEFER_WITHOUT_HORIZON_REASONS:
                raise UnstablePolicyDecision(
                    f"defer {self.reason_code!r} must state eligible_at"
                )
        if self.decision != DEFER and self.eligible_at is not None:
            raise UnstablePolicyDecision("eligible_at belongs to defer only")

    @property
    def allowed(self) -> bool:
        """`allow` — это только право продолжить, а НЕ факт отправки."""
        return self.decision == ALLOW

    def audit_mapping(self) -> dict[str, str]:
        return dict(self.audit)


def _audit(**values: object) -> tuple[tuple[str, str], ...]:
    """Не-PII снимок входа: только флаги, коды и длительности."""
    return tuple(
        sorted((key, "" if value is None else str(value)) for key, value in values.items())
    )


def _contract(request: OutgoingRequest, contracts) -> PlatformContract | None:
    return contracts.get(
        (request.channel_app_type, request.platform_contract_version)
    )


def _window_age(request: OutgoingRequest, now: datetime) -> timedelta | None:
    anchor = request.latest_user_provider_ts
    if anchor is None:
        return None
    return now - anchor


def _consent_basis(
    request: OutgoingRequest,
    contract: PlatformContract,
    now: datetime,
) -> tuple[bool, str]:
    """(годен, reason_code при отказе). Пустой consent — не отказ, а «нет ветви»."""
    scope = request.consent_scope
    if scope is None or not str(scope.topic or "").strip():
        return False, ""
    if not contract.consent_basis_proven:
        return False, "consent_basis_unverified"
    required = str(request.consent_topic_required or "").strip()
    if (
        not required
        or scope.topic.strip() != required
        or scope.granted_at is None
        or scope.evidence_message_id is None
        or (scope.expires_at is not None and scope.expires_at <= now)
    ):
        return False, "consent_out_of_scope"
    return True, ""


def _provider_type_basis(
    request: OutgoingRequest,
    contract: PlatformContract,
    age: timedelta | None,
) -> tuple[bool, str]:
    """(годен, reason_code при отказе). Пустой запрос типа — «нет ветви»."""
    requested = str(request.requested_message_type or "").strip()
    if not requested:
        return False, ""
    message_type = contract.message_type(requested)
    if message_type is None:
        return False, "provider_message_type_unverified"
    if message_type.requires_human_authored and not request.human_authored:
        return False, "provider_message_type_conditions_unmet"
    if request.message_purpose not in message_type.purposes:
        return False, "provider_message_type_conditions_unmet"
    if message_type.max_age is not None:
        if age is None or age > message_type.max_age:
            return False, "provider_message_type_conditions_unmet"
    return True, ""


def decide_outgoing(
    request: OutgoingRequest,
    *,
    now: datetime,
    contracts: dict[tuple[str, str], PlatformContract] | None = None,
    event_kinds: dict[str, str] | None = None,
) -> OutgoingDecision:
    """Чистое решение: можно ли отправить это исходящее прямо сейчас.

    `allow` НЕ означает отправку. Он означает только «политика не против»:
    durable task, финальная revalidation перед провайдером и receipt-first
    остаются отдельными шагами снаружи.
    """
    # Реестры внедряются аргументом только для тестов: production-значение —
    # дефолт, поэтому вызывающий код не может «расширить» capability на месте.
    contracts = VERIFIED_PLATFORM_CONTRACTS if contracts is None else contracts
    event_kinds = EVENT_KIND_PURPOSE if event_kinds is None else event_kinds
    risk = request.case_risk_state
    audit = _audit(
        policy_version=POLICY_VERSION,
        app_type=request.channel_app_type,
        contract_version=request.platform_contract_version,
        event_kind=request.event_kind,
        purpose=request.message_purpose,
        requested_message_type=request.requested_message_type or "-",
        human_authored=request.human_authored,
        permission_reason=risk.permission_reason or "-",
        open_complaint=risk.open_complaint,
        case_requires_human=risk.case_requires_human,
        has_consent=bool(request.consent_scope and request.consent_scope.topic),
        has_quiet_hours=request.quiet_hours is not None,
    )

    def verdict(
        decision: str,
        reason_code: str,
        *,
        policy_basis: str = "",
        eligible_at: datetime | None = None,
        **extra: object,
    ) -> OutgoingDecision:
        return OutgoingDecision(
            decision=decision,
            reason_code=reason_code,
            policy_basis=policy_basis,
            eligible_at=eligible_at,
            audit=audit + _audit(**extra) if extra else audit,
        )

    # 1. Сначала fail-closed проверки контракта: непроверенная capability не
    # может дойти до основания и «случайно» получить allow.
    if now.tzinfo is None or now.utcoffset() is None:
        return verdict(BLOCK, "evaluation_time_not_aware")
    known_app_types = {key[0] for key in contracts}
    if request.channel_app_type not in known_app_types:
        return verdict(BLOCK, "channel_app_type_unverified")
    contract = _contract(request, contracts)
    if contract is None:
        return verdict(BLOCK, "platform_contract_unverified")
    registered_purpose = event_kinds.get(request.event_kind)
    if registered_purpose is None:
        return verdict(BLOCK, "event_kind_unregistered")
    if request.message_purpose not in MESSAGE_PURPOSES:
        return verdict(BLOCK, "message_purpose_unknown")
    if request.message_purpose != registered_purpose:
        return verdict(BLOCK, "message_purpose_conflicts_event_kind")
    if request.message_purpose == PURPOSE_MARKETING:
        return verdict(BLOCK, "marketing_capability_unverified")

    # 2. Окончательные запреты по клиенту раньше любых оснований.
    reason = str(risk.permission_reason or "").strip()
    if reason:
        blocked = PERMISSION_BLOCK_REASONS.get(reason)
        if blocked:
            return verdict(BLOCK, blocked)
        deferred = PERMISSION_DEFER_REASONS.get(reason)
        if not deferred:
            return verdict(BLOCK, "permission_reason_unrecognized")

    # 3. Риск, который обязан увидеть человек, важнее временной паузы: иначе
    # жалоба будет тихо ждать снятия паузы вместо эскалации.
    if risk.open_complaint:
        return verdict(ESCALATE, "open_complaint")
    if risk.case_requires_human:
        return verdict(ESCALATE, "case_requires_human")

    # 4. Временный отказ прав. Горизонт неизвестен: снимает человек.
    if reason:
        return verdict(DEFER, PERMISSION_DEFER_REASONS[reason])

    age = _window_age(request, now)

    # 5. Заявленный тип сообщения проверяется ВСЕГДА, а не только когда окно
    # закрыто. Иначе внутри окна можно было бы отправить с непроверенным тегом:
    # открытое окно разрешает разговор, но не разрешает произвольный тип
    # сообщения, а провайдер судит именно по типу.
    provider_type_ok = False
    if str(request.requested_message_type or "").strip():
        provider_type_ok, type_reason = _provider_type_basis(request, contract, age)
        if not provider_type_ok:
            return verdict(BLOCK, type_reason)

    # 6. Основание. Ровно три ветви, и ни одна не выводится из «человек ответил».
    # Порядок — от самого простого доказательства к самому узкому.
    basis = ""
    if age is not None and timedelta(0) <= age <= contract.standard_window:
        basis = BASIS_STANDARD_WINDOW
    if not basis:
        consent_ok, consent_reason = _consent_basis(request, contract, now)
        if consent_ok:
            basis = BASIS_PROVEN_CONSENT
        elif consent_reason:
            return verdict(BLOCK, consent_reason)
    if not basis and provider_type_ok:
        basis = BASIS_PROVIDER_ALLOWED_TYPE
    if not basis:
        if age is None:
            return verdict(BLOCK, "window_anchor_missing")
        return verdict(
            ESCALATE,
            "outside_standard_window",
            window_age_seconds=int(age.total_seconds()),
        )

    # 7. Частота и тихие часы сдвигают разрешённую отправку, но не создают
    # основания и не отменяют его.
    frequency = request.frequency_state
    if (
        frequency.max_in_window is not None
        and frequency.sent_in_window >= frequency.max_in_window
    ):
        horizon = (
            frequency.last_sent_at + frequency.window
            if frequency.last_sent_at is not None and frequency.window is not None
            else now + STANDARD_WINDOW
        )
        return verdict(
            DEFER,
            "frequency_cap_reached",
            eligible_at=horizon,
            sent_in_window=frequency.sent_in_window,
            max_in_window=frequency.max_in_window,
        )
    if frequency.last_sent_at is not None and frequency.min_interval is not None:
        earliest = frequency.last_sent_at + frequency.min_interval
        if earliest > now:
            return verdict(DEFER, "frequency_min_interval", eligible_at=earliest)
    quiet = request.quiet_hours
    if (
        quiet is not None
        and request.message_purpose != PURPOSE_TRANSACTIONAL
        and quiet.contains(now)
    ):
        return verdict(DEFER, "quiet_hours", eligible_at=quiet.next_end(now))

    reason_by_basis = {
        BASIS_STANDARD_WINDOW: "within_standard_window",
        BASIS_PROVEN_CONSENT: "proven_consent_in_scope",
        BASIS_PROVIDER_ALLOWED_TYPE: "provider_allowed_message_type",
    }
    return verdict(
        ALLOW,
        reason_by_basis[basis],
        policy_basis=basis,
        window_age_seconds=int(age.total_seconds()) if age is not None else "",
    )


def reason_code_decision(reason_code: str) -> str:
    """Исход, закреплённый за кодом причины (для метрик и алертов)."""
    entry = REASON_CODES.get(str(reason_code or ""))
    return entry[0] if entry else ""


def documented_reason_codes() -> tuple[str, ...]:
    return tuple(sorted(REASON_CODES))


__all__ = [
    "ALLOW",
    "BASIS_PROVEN_CONSENT",
    "BASIS_PROVIDER_ALLOWED_TYPE",
    "BASIS_STANDARD_WINDOW",
    "BLOCK",
    "CaseRiskState",
    "ConsentScope",
    "DEFER",
    "ESCALATE",
    "EVENT_KIND_PURPOSE",
    "FrequencyState",
    "OutgoingDecision",
    "OutgoingRequest",
    "POLICY_VERSION",
    "PURPOSE_MARKETING",
    "PURPOSE_SERVICE",
    "PURPOSE_TRANSACTIONAL",
    "PlatformContract",
    "ProviderMessageType",
    "QuietHours",
    "REASON_CODES",
    "STANDARD_WINDOW",
    "UnstablePolicyDecision",
    "VERIFIED_CONTRACT_VERSION",
    "VERIFIED_PLATFORM_CONTRACTS",
    "decide_outgoing",
    "documented_reason_codes",
    "reason_code_decision",
]
