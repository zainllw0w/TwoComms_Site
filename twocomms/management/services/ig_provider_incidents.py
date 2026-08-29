"""Durable стан деградації провайдера й купірування спаму технічних вибачень.

Головна ідея етапу: система вміла відповідати на питання «чи не повторити
recovery для цього `source_message`?» (і відповідала правильно), але не вміла
відповісти на питання «чи потрібно взагалі надсилати цьому клієнту друге
технічне повідомлення через 30 секунд?». Тому клієнт отримував три однакові
«перепрошую за технічну затримку» за 5 хвилин 53 секунди.

Три поняття закривають цю прогалину:

* `IgProviderIncident` — відкрита деградація провайдера (вікно + fingerprint);
* `IgClientDegradationEpisode` — стан конкретного клієнта в межах інциденту;
* `logical_turn_id` — логічний хід клієнта (одна ціль відповіді).

Одиниця «не більше одного holding» — пара (інцидент, клієнт), НЕ source_message.

Лестниця деградації (єдина для всього етапу):

    L0 норма            модель відповіла в бюджеті ходу      → змістовна відповідь
    L1 повільно         бюджет ще не вичерпано               → typing, БЕЗ тексту
    L2 перший збій      інший кандидат у залишку бюджету     → змістовна відповідь
    L3 деградація       intent детермінований                → відповідь без моделі
    L4 холдинг          intent вимагає відповіді             → РІВНО ОДИН holding
    L5 відновлення      інцидент закрився                    → відповідь БЕЗ вибачення
    L6 вичерпано        recovery не вдався                   → менеджеру, клієнту НІЧОГО
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings as django_settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from management.models import (
    IgClientDegradationEpisode,
    IgProviderIncident,
    InstagramBotMessage,
)


# --- Параметри склейки -------------------------------------------------------
# Вікно склейки: 5 хвилин без нового збою переводить інцидент до закриття.
# Обґрунтування: у production-вікні 12:20–13:20 UTC збої йшли щільними серіями з
# паузами до кількох хвилин, а успішні 3.7-відповіді перемежалися з деградацією.
# Коротше вікно (1 хв) розрізало б один інцидент на кілька і знову дозволило б
# кілька holding; довше (15 хв) склеїло б незалежні проблеми і сховало другу
# реальну деградацію. Величину перевірити на даних ЭА.0 і за потреби змінити тут.
INCIDENT_COALESCE_WINDOW = timedelta(minutes=5)
# `RECOVERING → CLOSED` тільки після K успіхів підряд АБО T секунд без збоїв.
# Один успіх між двома 429 не має закривати інцидент: інакше він дозволив би
# другий holding тому самому клієнту.
RECOVERING_SUCCESS_STREAK = 2
RECOVERING_QUIET_PERIOD = timedelta(seconds=90)
# Денний потолок holding на клієнта незалежно від числа інцидентів.
MAX_HOLDINGS_PER_CLIENT_PER_DAY = 2
# Максимальний час життя курсора відновлення. Після нього — терминальний исход
# (детермінована відповідь або кейс менеджеру), інакше порушується И9:
# «збій провайдера не призводить до молчання каналу довше SLA».
RECOVERY_CURSOR_MAX_LIFETIME = timedelta(minutes=30)

HOLDING_MESSAGE_SOURCE = "ai_holding"

LOW_INTENT_RULE_VERSION = "low-intent-v1"


def flag(name: str, default: bool = True) -> bool:
    """Прочитати feature-флаг етапу з Django settings (керується .env)."""
    value = getattr(django_settings, name, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


# --- Класифікація відказів ---------------------------------------------------
_FAILURE_CLASS_BY_KIND = {
    "quota_429": IgProviderIncident.FailureClass.QUOTA,
    "read_timeout": IgProviderIncident.FailureClass.TIMEOUT,
    "http_408": IgProviderIncident.FailureClass.TIMEOUT,
    "http_5xx": IgProviderIncident.FailureClass.UNAVAILABLE,
    "transport": IgProviderIncident.FailureClass.CONNECT,
    "invalid_payload": IgProviderIncident.FailureClass.INVALID_PAYLOAD,
    "invalid_key": IgProviderIncident.FailureClass.AUTH,
    "permission_denied": IgProviderIncident.FailureClass.AUTH,
    "model_not_found": IgProviderIncident.FailureClass.INVALID_PAYLOAD,
    "empty": IgProviderIncident.FailureClass.EMPTY,
}

# Класи, які не є деградацією доступності провайдера: їх не можна ретраїти і
# вони не повинні відкривати інцидент, що придушує holding для всіх клієнтів.
NON_RETRYABLE_CLASSES = frozenset({
    IgProviderIncident.FailureClass.INVALID_PAYLOAD,
    IgProviderIncident.FailureClass.AUTH,
})


def classify_failure(failure_kind: str = "", http_code=None) -> str:
    """Типізований клас відказу, а не один загальний «збій»."""
    kind = str(failure_kind or "").strip().lower()
    mapped = _FAILURE_CLASS_BY_KIND.get(kind)
    if mapped:
        return mapped
    try:
        code = int(http_code) if http_code else 0
    except (TypeError, ValueError):
        code = 0
    if code == 429:
        return IgProviderIncident.FailureClass.QUOTA
    if code in {401, 403}:
        return IgProviderIncident.FailureClass.AUTH
    if code == 400:
        return IgProviderIncident.FailureClass.INVALID_PAYLOAD
    if code == 408:
        return IgProviderIncident.FailureClass.TIMEOUT
    if 500 <= code < 600:
        return IgProviderIncident.FailureClass.UNAVAILABLE
    return IgProviderIncident.FailureClass.UNKNOWN


def _fingerprint(role: str, failure_class: str) -> str:
    """Область (модель/ключ/проект) свідомо НЕ входить у ключ інциденту.

    Клієнту байдуже, який саме ключ впав; йому важливо, що бот молчить. Якби
    scope входив у ключ, 23 відкази 429 по шести алиасах дали б шість «різних»
    інцидентів і шість holding — тобто рівно той дефект, який ми лікуємо.
    """
    return f"{str(role or 'unknown')[:20]}:{str(failure_class or 'unknown')[:20]}"


def _scope_labels(*, model: str = "", project_group: str = "", key_name: str = "") -> list:
    """Всі відомі області одного збою.

    Записуються ВСІ рівні (project-group, модель, alias), а не найзагальніший:
    при незаданих `GEMINI_KEY_PROJECT_GROUPS` project-group порожня, і без alias
    інцидент по шести ключах виглядав би як одна область. Саме нерозрізненність
    областей робила неможливим доказ «шість страхуючих ключів працюють».
    """
    labels = []
    if project_group:
        labels.append(f"project_group:{str(project_group)[:40]}")
    if model:
        labels.append(f"model:{str(model)[:40]}")
    if key_name:
        labels.append(f"alias:{str(key_name)[:40]}")
    return labels or ["unknown"]


def _severity(failure_count: int, affected_clients: int) -> int:
    score = 1
    if failure_count >= 5 or affected_clients >= 2:
        score = 2
    if failure_count >= 20 or affected_clients >= 5:
        score = 3
    return score


# --- Реєстрація стану провайдера --------------------------------------------
def register_provider_failure(
    *,
    role: str,
    failure_kind: str = "",
    http_code=None,
    model: str = "",
    project_group: str = "",
    key_name: str = "",
    now=None,
) -> IgProviderIncident | None:
    """Відкрити або продовжити інцидент у точці запису провайдерської спроби.

    Одна коротка транзакція без сітьового I/O всередині. Унікальність «один
    активний інцидент на fingerprint» тримає БД через nullable unique-колонку,
    тому два процеси, що реєструють збій одночасно, дають ОДИН інцидент.
    """
    if not flag("IG_PROVIDER_INCIDENT_TRACKING"):
        return None
    now = now or timezone.now()
    failure_class = classify_failure(failure_kind, http_code)
    fingerprint = _fingerprint(role, failure_class)
    scopes_seen = _scope_labels(
        model=model, project_group=project_group, key_name=key_name
    )
    for _attempt in range(2):
        with transaction.atomic():
            incident = (
                IgProviderIncident.objects.select_for_update()
                .filter(active_fingerprint=fingerprint)
                .first()
            )
            if incident is not None:
                # Збій після вікна тишини — це НОВА проблема, а не продовження
                # старої. Інакше два інциденти з різницею в пів години злиплись
                # би в один, і клієнт при реальній новій деградації отримав би
                # молчання замість одного holding.
                last_failure = incident.last_failure_at or incident.opened_at
                if last_failure and last_failure <= now - INCIDENT_COALESCE_WINDOW:
                    _close_locked(
                        incident,
                        now=last_failure,
                        reason="coalesce_window_elapsed",
                        fields=["updated_at"],
                    )
                    incident = None
            if incident is None:
                try:
                    return IgProviderIncident.objects.create(
                        role=str(role or "")[:20],
                        failure_class=failure_class,
                        fingerprint=fingerprint,
                        active_fingerprint=fingerprint,
                        state=IgProviderIncident.State.OPEN,
                        opened_at=now,
                        last_failure_at=now,
                        observed_scopes=scopes_seen,
                        failure_count=1,
                        severity=1,
                    )
                except IntegrityError:
                    # Конкурентний процес щойно відкрив цей самий інцидент.
                    continue
            scopes = list(incident.observed_scopes or [])
            for label in scopes_seen:
                if label not in scopes:
                    scopes.append(label)
            incident.observed_scopes = scopes[:60]
            incident.failure_count = min(4294967295, int(incident.failure_count or 0) + 1)
            incident.last_failure_at = now
            incident.consecutive_success_count = 0
            # Новий збій скасовує відновлення: інцидент знову відкритий.
            incident.state = IgProviderIncident.State.OPEN
            incident.closed_at = None
            incident.close_reason = ""
            incident.severity = _severity(
                incident.failure_count, incident.affected_clients_count
            )
            incident.save(update_fields=[
                "observed_scopes", "failure_count", "last_failure_at",
                "consecutive_success_count", "state", "closed_at", "close_reason",
                "severity", "updated_at",
            ])
            return incident
    return IgProviderIncident.objects.filter(active_fingerprint=fingerprint).first()


def register_provider_success(*, role: str, now=None) -> None:
    """Перший успіх роли переводить у `RECOVERING`, а не одразу в `CLOSED`.

    Одиничний успіх між двома 429 не має закривати інцидент — інакше він
    дозволив би другий holding тому самому клієнту через кілька секунд.
    """
    if not flag("IG_PROVIDER_INCIDENT_TRACKING"):
        return
    now = now or timezone.now()
    active_ids = list(
        IgProviderIncident.objects.filter(
            role=str(role or "")[:20],
            active_fingerprint__isnull=False,
        ).values_list("id", flat=True)[:20]
    )
    for incident_id in active_ids:
        with transaction.atomic():
            incident = (
                IgProviderIncident.objects.select_for_update()
                .filter(pk=incident_id, active_fingerprint__isnull=False)
                .first()
            )
            if incident is None:
                continue
            incident.success_count = min(4294967295, int(incident.success_count or 0) + 1)
            incident.consecutive_success_count = min(
                65535, int(incident.consecutive_success_count or 0) + 1
            )
            if not incident.first_success_after_at:
                incident.first_success_after_at = now
            fields = [
                "success_count", "consecutive_success_count",
                "first_success_after_at", "updated_at",
            ]
            if incident.state == IgProviderIncident.State.OPEN:
                incident.state = IgProviderIncident.State.RECOVERING
                fields.append("state")
            if (
                incident.state == IgProviderIncident.State.RECOVERING
                and incident.consecutive_success_count >= RECOVERING_SUCCESS_STREAK
            ):
                _close_locked(incident, now=now, reason="success_streak", fields=fields)
            else:
                incident.save(update_fields=fields)


def _close_locked(incident: IgProviderIncident, *, now, reason: str, fields: list) -> None:
    incident.state = IgProviderIncident.State.CLOSED
    incident.active_fingerprint = None
    incident.closed_at = now
    incident.close_reason = str(reason or "")[:32]
    for field in ("state", "active_fingerprint", "closed_at", "close_reason"):
        if field not in fields:
            fields.append(field)
    incident.save(update_fields=fields)


def close_stale_incidents(*, now=None) -> int:
    """Закрити інциденти, що «висять» довше вікна склейки після останнього збою.

    Без цього кроку відкритий інцидент придушував би holding нескінченно — це
    порушення И9 (молчання каналу довше SLA), а не економія повідомлень.
    """
    now = now or timezone.now()
    cutoff = now - INCIDENT_COALESCE_WINDOW
    quiet_cutoff = now - RECOVERING_QUIET_PERIOD
    closed = 0
    candidate_ids = list(
        IgProviderIncident.objects.filter(active_fingerprint__isnull=False)
        .values_list("id", flat=True)[:200]
    )
    for incident_id in candidate_ids:
        with transaction.atomic():
            incident = (
                IgProviderIncident.objects.select_for_update()
                .filter(pk=incident_id, active_fingerprint__isnull=False)
                .first()
            )
            if incident is None:
                continue
            last_failure = incident.last_failure_at or incident.opened_at
            stale = bool(last_failure and last_failure <= cutoff)
            quiet_recovered = bool(
                incident.state == IgProviderIncident.State.RECOVERING
                and last_failure
                and last_failure <= quiet_cutoff
            )
            if not stale and not quiet_recovered:
                continue
            _close_locked(
                incident,
                now=now,
                reason="coalesce_window_elapsed" if stale else "quiet_period",
                fields=["updated_at"],
            )
            closed += 1
    return closed


def active_incident(role: str = "chat", *, now=None) -> IgProviderIncident | None:
    """Поточна деградація роли, що реально впливає на відповіді клієнту.

    Класи `invalid_payload` і `auth` не є деградацією доступності: вони не
    зникнуть від очікування і не мають придушувати holding іншим клієнтам.
    """
    if not flag("IG_PROVIDER_INCIDENT_TRACKING"):
        return None
    now = now or timezone.now()
    cutoff = now - INCIDENT_COALESCE_WINDOW
    return (
        IgProviderIncident.objects.filter(
            role=str(role or "")[:20],
            active_fingerprint__isnull=False,
            last_failure_at__gt=cutoff,
        )
        .exclude(failure_class__in=NON_RETRYABLE_CLASSES)
        .order_by("-last_failure_at", "-id")
        .first()
    )


# --- Intent-gate (ЭА.4) ------------------------------------------------------
# Це НЕ класифікатор інтенту через модель — модель як раз недоступна. Це дешеве
# детерміноване правило, що застосовується ТІЛЬКИ до рішення «чи надсилати
# технічний текст». На змістовний шлях (L0–L2) воно не впливає.
def is_low_intent_turn(row, *, logical_turn_id: str = "") -> bool:
    """Хід, що не вимагає ані змістовної, ані технічної відповіді.

    Клієнт, який написав «Добре» і отримав «Перепрошую за технічну затримку.
    Я відновлюю деталі…», отримує повідомлення ГІРШЕ, ніж тишина: воно
    беззмістовне й виглядає як поломка.

    ЭБ.1: саме правило переїхало в `ig_reply_expectation` — одне джерело істини
    на питання «чи чекає клієнт відповіді». Тут лишились сумісна назва (її
    використовують тести й `holding_decision`) і прапорець вимкнення.
    """
    if not flag("IG_LOW_INTENT_HOLDING_GATE"):
        return False
    from management.services.ig_reply_expectation import is_low_intent_text_turn

    return is_low_intent_text_turn(row, logical_turn_id=logical_turn_id)


def expectation_for(row, *, ugc_turn: bool = False, logical_turn_id: str = ""):
    """Очікування відповіді з урахуванням прапорця вимкнення.

    Вимкнений `IG_LOW_INTENT_HOLDING_GATE` повертає нас до старої поведінки:
    будь-який хід вважається таким, що чекає відповіді.
    """
    from management.services.ig_reply_expectation import ReplyExpectation, classify

    if not flag("IG_LOW_INTENT_HOLDING_GATE"):
        return ReplyExpectation(
            waiting=True,
            substantive_reply_owed=True,
            actively_waiting=False,
            reason="gate_disabled",
        )
    return classify(row, ugc_turn=ugc_turn, logical_turn_id=logical_turn_id)



# --- Епізод клієнта і єдина точка рішення про holding (ЭА.3) -----------------
SEND = "send"
SUPPRESS = "suppress"
DEFER = "defer"

# Причини придушення, за яких хід НЕ потребує пізнішої відповіді взагалі.
# Все інше означає «технічний текст не надсилаємо, але відповідь клієнт
# отримає», інакше придушення перетворилось би на молчання каналу (порушення И9).
SUPPRESS_NO_ANSWER_REASONS = frozenset({
    "low_intent_turn",
    "opted_out",
    "hidden_client",
    "client_blocked",
    "manager_takeover",
    "no_client",
    "episode_terminal",
})


@dataclass(frozen=True)
class HoldingDecision:
    """Рішення про технічне повідомлення зі стабільним кодом причини."""

    action: str
    reason: str
    episode_id: int = 0
    incident_id: int = 0

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return self.action == SEND

    @property
    def should_send(self) -> bool:
        return self.action == SEND


def ensure_client_episode(
    row,
    incident: IgProviderIncident,
    *,
    logical_turn_id: str = "",
    now=None,
) -> IgClientDegradationEpisode | None:
    """Один епізод на пару (клієнт, інцидент); новий вхідний лише оновлює watermark."""
    client_id = getattr(row, "client_id", None)
    if not client_id or incident is None:
        return None
    now = now or timezone.now()
    for _attempt in range(2):
        with transaction.atomic():
            episode = (
                IgClientDegradationEpisode.objects.select_for_update()
                .filter(client_id=client_id, incident_id=incident.pk)
                .first()
            )
            if episode is None:
                try:
                    episode = IgClientDegradationEpisode.objects.create(
                        client_id=client_id,
                        incident_id=incident.pk,
                        state=IgClientDegradationEpisode.State.OPEN,
                        first_source_message_id=row.pk,
                        latest_source_message_id=row.pk,
                        logical_turn_id=str(logical_turn_id or "")[:64],
                        inbound_count=1,
                    )
                except IntegrityError:
                    continue
                IgProviderIncident.objects.filter(pk=incident.pk).update(
                    affected_clients_count=models_f_increment(),
                )
                return episode
            fields = ["updated_at"]
            if int(episode.latest_source_message_id or 0) < int(row.pk or 0):
                episode.latest_source_message_id = row.pk
                episode.inbound_count = min(
                    4294967295, int(episode.inbound_count or 0) + 1
                )
                episode.logical_turn_id = str(logical_turn_id or episode.logical_turn_id)[:64]
                fields += ["latest_source_message_id", "inbound_count", "logical_turn_id"]
            episode.save(update_fields=fields)
            return episode
    return IgClientDegradationEpisode.objects.filter(
        client_id=client_id, incident_id=incident.pk
    ).first()


def models_f_increment():
    from django.db.models import F

    return F("affected_clients_count") + 1


def _holdings_today(client_id: int, *, now) -> int:
    from zoneinfo import ZoneInfo

    kyiv = ZoneInfo("Europe/Kyiv")
    local_now = now.astimezone(kyiv)
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return InstagramBotMessage.objects.filter(
        client_id=client_id,
        role=InstagramBotMessage.Role.MODEL,
        source=HOLDING_MESSAGE_SOURCE,
        created_at__gte=day_start,
    ).count()


def holding_decision(
    row,
    *,
    incident: IgProviderIncident | None = None,
    logical_turn_id: str = "",
    budget_remaining_ms: int = 0,
    expectation=None,
    recovery_expected: bool = False,
    ugc_turn: bool = False,
    now=None,
) -> HoldingDecision:
    """Єдина точка рішення: чи має цей хід отримати технічний текст.

    Жоден інший шлях не має права надіслати holding. Рішення повертає
    `send` / `suppress` / `defer` зі стабільним кодом причини — код потрібен для
    метрики хибних придушень і для алертів.

    ЭБ.1 — чотири умови мусять виконатись РАЗОМ, інакше клієнт бачить тишину, а
    відповідь приходить пізніше й без вибачення:

    * `expectation.waiting` — клієнт справді чекає відповіді;
    * `budget_remaining_ms <= 0` — ми вже витратили заявлений бюджет ходу;
    * відкритий інцидент **або** `expectation.actively_waiting` — тобто ми
      прогнозуємо довгу паузу, а не один невдалий виклик;
    * бюджет вибачень (епізод, денний потолок) не витрачений.

    `recovery_expected` каже, що курсор відновлення відповість сам. Тоді
    поодинокий збій НЕ отримує техтексту: вибачення зараз плюс відповідь через
    півхвилини — гірше, ніж просто відповідь через півхвилини.
    """
    if not flag("IG_OUTAGE_HOLDING_COALESCING"):
        return HoldingDecision(SEND, "coalescing_disabled")
    now = now or timezone.now()
    client = getattr(row, "client", None)
    client_id = getattr(row, "client_id", None)
    if not client_id or client is None:
        return HoldingDecision(SUPPRESS, "no_client")
    if getattr(client, "hidden_at", None):
        return HoldingDecision(SUPPRESS, "hidden_client")
    if getattr(client, "is_blocked", False):
        return HoldingDecision(SUPPRESS, "client_blocked")
    if getattr(client, "manager_takeover", False):
        return HoldingDecision(SUPPRESS, "manager_takeover")
    opted_out_at = getattr(client, "opted_out_at", None)
    opted_in_at = getattr(client, "opted_in_at", None)
    if opted_out_at and (not opted_in_at or opted_in_at < opted_out_at):
        return HoldingDecision(SUPPRESS, "opted_out")
    if expectation is None:
        expectation = expectation_for(
            row, ugc_turn=ugc_turn, logical_turn_id=logical_turn_id
        )
    if not expectation.waiting:
        # Розділяємо два різних придушення. Репост історії: змістовну відповідь
        # (подяку) ми винні, тому хід іде у відновлення — але вибачення не
        # надсилаємо ніколи. Реакція чи «Добре»: не винні нічого, і тишина тут
        # правильний исход.
        if expectation.substantive_reply_owed:
            return HoldingDecision(SUPPRESS, "no_reply_expected")
        return HoldingDecision(SUPPRESS, "low_intent_turn")
    # L1: поки бюджет ходу не вичерпано, клієнт бачить індикатор набору, а не
    # текст. Технічний текст раніше бюджету — головна причина шкоди для UX.
    if budget_remaining_ms and int(budget_remaining_ms) > 0:
        return HoldingDecision(DEFER, "budget_not_exhausted")

    incident = incident or active_incident(role="chat", now=now)
    if incident is None:
        # Немає підтвердженої деградації провайдера — це поодинокий збій ходу, і
        # він НЕ прогнозує довгої паузи. Якщо курсор відновлення відповість сам,
        # техтекст лише додає клієнту зайве повідомлення перед справжньою
        # відповіддю. Виключення — клієнт уже перепитав: тоді тишина читається
        # як поломка, і одне коротке повідомлення доречне.
        if recovery_expected and not expectation.actively_waiting:
            return HoldingDecision(SUPPRESS, "isolated_failure_recovery_pending")
        if _holdings_today(client_id, now=now) >= MAX_HOLDINGS_PER_CLIENT_PER_DAY:
            return HoldingDecision(SUPPRESS, "daily_cap_reached")
        return HoldingDecision(SEND, "no_open_incident")

    episode = ensure_client_episode(
        row, incident, logical_turn_id=logical_turn_id, now=now
    )
    if episode is None:
        return HoldingDecision(SUPPRESS, "episode_unavailable")
    if episode.holding_reserved_at or episode.holding_message_id:
        _note_suppressed(episode, "already_sent_in_incident")
        return HoldingDecision(
            SUPPRESS, "already_sent_in_incident", episode.pk, incident.pk
        )
    if episode.state in {
        IgClientDegradationEpisode.State.RECOVERY_PENDING,
        IgClientDegradationEpisode.State.MANUAL,
    }:
        _note_suppressed(episode, "recovery_pending_for_client")
        return HoldingDecision(
            SUPPRESS, "recovery_pending_for_client", episode.pk, incident.pk
        )
    if episode.is_terminal:
        _note_suppressed(episode, "episode_terminal")
        return HoldingDecision(SUPPRESS, "episode_terminal", episode.pk, incident.pk)
    if int(episode.apology_count or 0) >= 1:
        _note_suppressed(episode, "apology_budget_spent")
        return HoldingDecision(
            SUPPRESS, "apology_budget_spent", episode.pk, incident.pk
        )
    if _holdings_today(client_id, now=now) >= MAX_HOLDINGS_PER_CLIENT_PER_DAY:
        _note_suppressed(episode, "daily_cap_reached")
        return HoldingDecision(SUPPRESS, "daily_cap_reached", episode.pk, incident.pk)
    return HoldingDecision(SEND, "first_holding_in_incident", episode.pk, incident.pk)


def _note_suppressed(episode: IgClientDegradationEpisode, reason: str) -> None:
    IgClientDegradationEpisode.objects.filter(pk=episode.pk).update(
        suppressed_count=models_f_suppressed(),
        last_decision=SUPPRESS,
        last_decision_reason=str(reason or "")[:48],
        updated_at=timezone.now(),
    )


def models_f_suppressed():
    from django.db.models import F

    return F("suppressed_count") + 1


def reserve_holding(episode_id: int, *, now=None) -> bool:
    """Зафіксувати перехід `OPEN → HOLDING_SENT` ДО сітьового виклику Meta.

    Outbox-патерн: якщо процес помре під час запиту, повторної спроби надіслати
    друге технічне повідомлення не буде. Receipt дописується після.
    """
    now = now or timezone.now()
    updated = IgClientDegradationEpisode.objects.filter(
        pk=episode_id,
        holding_reserved_at__isnull=True,
        holding_message__isnull=True,
    ).exclude(
        state__in=(
            IgClientDegradationEpisode.State.MANUAL,
            IgClientDegradationEpisode.State.SUPERSEDED,
            IgClientDegradationEpisode.State.CANCELLED,
            IgClientDegradationEpisode.State.RECOVERED,
        )
    ).update(
        state=IgClientDegradationEpisode.State.HOLDING_SENT,
        holding_reserved_at=now,
        last_decision=SEND,
        last_decision_reason="holding_reserved",
        updated_at=now,
    )
    return bool(updated)


def release_holding_reservation(episode_id: int, *, reason: str) -> None:
    """Знята резервація після невдалої відправки, що НЕ перетнула Meta."""
    IgClientDegradationEpisode.objects.filter(
        pk=episode_id, holding_message__isnull=True
    ).update(
        state=IgClientDegradationEpisode.State.OPEN,
        holding_reserved_at=None,
        last_decision=SUPPRESS,
        last_decision_reason=str(reason or "holding_send_failed")[:48],
        updated_at=timezone.now(),
    )


def confirm_holding_sent(episode_id: int, message, *, now=None) -> None:
    """Дописати receipt holding-а і врахувати одне вибачення в епізоді."""
    now = now or timezone.now()
    message_id = getattr(message, "pk", message) or None
    with transaction.atomic():
        episode = (
            IgClientDegradationEpisode.objects.select_for_update()
            .filter(pk=episode_id)
            .first()
        )
        if episode is None:
            return
        if not episode.holding_message_id and message_id:
            episode.holding_message_id = message_id
        episode.holding_sent_at = episode.holding_sent_at or now
        if episode.state == IgClientDegradationEpisode.State.OPEN:
            episode.state = IgClientDegradationEpisode.State.HOLDING_SENT
        episode.apology_count = max(1, int(episode.apology_count or 0))
        episode.last_decision = SEND
        episode.last_decision_reason = "holding_delivered"
        episode.save(update_fields=[
            "holding_message", "holding_sent_at", "state", "apology_count",
            "last_decision", "last_decision_reason", "updated_at",
        ])
        from django.db.models import F

        IgProviderIncident.objects.filter(pk=episode.incident_id).update(
            holding_sent_count=F("holding_sent_count") + 1,
            updated_at=now,
        )


def note_apology_delivered(episode_id: int, *, count: int = 1) -> None:
    """Рахувати вибачення по ФАКТУ надісланого тексту, а не по флагах."""
    if not episode_id:
        return
    from django.db.models import F

    IgClientDegradationEpisode.objects.filter(pk=episode_id).update(
        apology_count=F("apology_count") + max(0, int(count or 0)),
        updated_at=timezone.now(),
    )


def set_episode_state(
    episode_id: int,
    state: str,
    *,
    reason: str = "",
    now=None,
) -> None:
    if not episode_id:
        return
    now = now or timezone.now()
    fields = {
        "state": state,
        "last_decision_reason": str(reason or "")[:48],
        "updated_at": now,
    }
    if state in IgClientDegradationEpisode._TERMINAL_STATES:
        fields["resolved_at"] = now
    IgClientDegradationEpisode.objects.filter(pk=episode_id).update(**fields)


def cancel_episodes_for_client(client_id: int, *, reason: str) -> int:
    """Скасувати незавершені епізоди при takeover / opt-out / hidden / epoch."""
    if not client_id:
        return 0
    now = timezone.now()
    return IgClientDegradationEpisode.objects.filter(
        client_id=client_id,
    ).exclude(
        state__in=(
            IgClientDegradationEpisode.State.RECOVERED,
            IgClientDegradationEpisode.State.MANUAL,
            IgClientDegradationEpisode.State.SUPERSEDED,
            IgClientDegradationEpisode.State.CANCELLED,
        )
    ).update(
        state=IgClientDegradationEpisode.State.CANCELLED,
        last_decision_reason=str(reason or "cancelled")[:48],
        resolved_at=now,
        updated_at=now,
    )


def episode_for_client(client_id: int) -> IgClientDegradationEpisode | None:
    """Актуальний незавершений епізод клієнта, якщо він є."""
    if not client_id:
        return None
    return (
        IgClientDegradationEpisode.objects.filter(client_id=client_id)
        .exclude(
            state__in=(
                IgClientDegradationEpisode.State.RECOVERED,
                IgClientDegradationEpisode.State.MANUAL,
                IgClientDegradationEpisode.State.SUPERSEDED,
                IgClientDegradationEpisode.State.CANCELLED,
            )
        )
        .select_related("incident")
        .order_by("-id")
        .first()
    )


def recovery_failure_is_retryable(recovery_job_id) -> bool:
    """Класи 400 / 401 / 403 / 404 не зникнуть від повтору.

    Раніше recovery витрачав усі три спроби на будь-який відказ, включно з
    некоректним payload-ом: три гарантовано провальні дорогі виклики, після яких
    створювався алерт про виснаження. Клас беремо з телеметрії саме цього job'а —
    вона тепер зберігає `recovery_job_id`.
    """
    if not recovery_job_id:
        return True
    from management.models import GeminiRequestAttempt

    attempt = (
        GeminiRequestAttempt.objects.filter(
            recovery_job_id=int(recovery_job_id), outcome="failed"
        )
        .order_by("-id")
        .values("failure_kind", "http_code")
        .first()
    )
    if not attempt:
        return True
    return classify_failure(
        attempt.get("failure_kind") or "", attempt.get("http_code")
    ) not in NON_RETRYABLE_CLASSES


def incident_blocks_recovery(episode: IgClientDegradationEpisode | None, *, now=None) -> bool:
    """Чи відкладати спробу recovery, бо провайдер усе ще в деградації.

    Recovery планується ВІД СТАНУ ІНЦИДЕНТУ, а не від таймера: під час
    загального quota-інциденту три повних виклики гарантовано провальні й лише
    дорого витрачають пул, після чого створюється алерт про виснаження.
    """
    if not flag("IG_RECOVERY_INCIDENT_SCHEDULING"):
        return False
    if episode is None:
        return False
    now = now or timezone.now()
    incident = getattr(episode, "incident", None)
    if incident is None:
        return False
    if incident.state != IgProviderIncident.State.OPEN:
        return False
    if not incident.active_fingerprint:
        return False
    last_failure = incident.last_failure_at or incident.opened_at
    if last_failure and last_failure <= now - INCIDENT_COALESCE_WINDOW:
        return False
    return True
