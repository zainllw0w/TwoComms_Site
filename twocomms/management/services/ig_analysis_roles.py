"""Роль автора як структурна межа: доказ менеджера ≠ намір клієнта.

`NEW-ANALYSIS-002` (Э3.5). Транскрипт аналізу навмисно містить рядки
`role=manager`, і рядки менеджера теж планують аналіз. Тому модель має повне
право *побачити* нотатку менеджера — але не має права перетворити її на
висловлений намір клієнта. Раніше межі не існувало структурно: `_normalize()`
перевіряв лише те, що цитата існує в тексті процитованого повідомлення, і
зберігав `source_role` як довідкове поле. Enum `MANAGER_OBSERVATION` виставляв
лише детермінований rules-шлях (`bot_sales_classifier`), а AI-шлях не виставляв
його ніколи. Через це нотатка менеджера «клієнт точно купить, оформлюю» могла
стати `product_interest` / `payment_pending` / `collaboration` з probability
0.99, і CRM-фільтри та follow-up, які виключають лише enum, її не бачили.

Головна ідея: висновок про клієнта дозволений лише тоді, коли він **атрибутований
клієнту**. Це не евристика по тексту, а перевірка ролі автора кожного доказу:

    доказ від user     → customer_fact       → може нести намір клієнта
    доказ від manager  → manager_observation → операційний контекст, не намір
    доказ від model    → bot_statement       → власні слова бота, не намір
    системна істина    → system_context      → оплата/замовлення, не намір

Два виключення, без яких «виправлення» саме почало б брехати:

1. `verified_payment` + висновок про оплату — це системна істина CRM, а не слова
   менеджера в чаті. Понижувати її через відсутність цитати клієнта означало б
   затирати власну істину (та сама помилка, що описана у F-SCORE-003).
2. Клієнт міг надіслати лише медіа або реакцію. Такий контент належить клієнту,
   але процитувати його неможливо, тому `evidence` буде порожнім не через
   порушення ролі. Оголошувати такий діалог `information_only` означало б
   стверджувати факт («клієнт лише цікавився»), якого дані не підтверджують.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings as django_settings

from management.models import IgConversationAnalysisSnapshot, InstagramBotMessage


# Версія детермінованих правил межі ролей. Пишеться у `rules_version` знімка,
# щоб читач міг відрізнити знімок, нормалізований з перевіркою ролі, від
# історичного, зробленого до цього етапу.
ROLE_BOUNDARY_POLICY_VERSION = "manager-evidence-boundary.1"

CLAIM_SCOPE_CUSTOMER = "customer_fact"
CLAIM_SCOPE_MANAGER = "manager_observation"
CLAIM_SCOPE_BOT = "bot_statement"
CLAIM_SCOPE_SYSTEM = "system_context"

# Коди невизначеності беруться ЛИШЕ з допустимого набору моделі
# (`_ANALYSIS_V2_UNCERTAINTY_CODES`): Analysis V2 валідує їх при записі, тому
# новий вільний код зламав би shadow-запис.
UNCERTAINTY_MANAGER_EVIDENCE = "manager_evidence_not_customer_intent"
UNCERTAINTY_EVIDENCE_UNVERIFIED = "evidence_unverified"

_TYPES = IgConversationAnalysisSnapshot.InteractionType
_BANDS = IgConversationAnalysisSnapshot.Band

# Типи, які самі по собі нічого не стверджують про намір клієнта: їм доказ
# клієнта не потрібен, і межа ролей їх не торкається.
NON_CUSTOMER_CLAIM_TYPES = frozenset({
    _TYPES.UNKNOWN,
    _TYPES.MANAGER_OBSERVATION,
    # «Не відповідає» — це твердження про відсутність повідомлення клієнта.
    # Вимагати для нього цитату клієнта самосуперечливо.
    _TYPES.NO_REPLY,
})

# Висновки, які тримає системна істина оплати/замовлення, а не чат.
AUTHORITY_BACKED_TYPES = frozenset({_TYPES.PAID_ORDER_WAITING})

REASON_NOT_CUSTOMER_CLAIM = "not_customer_claim"
REASON_AUTHORITY_BACKED = "authority_backed"
REASON_CUSTOMER_EVIDENCE = "customer_evidence"
REASON_MANAGER_ONLY_EVIDENCE = "manager_only_evidence"
REASON_NON_CUSTOMER_EVIDENCE = "non_customer_evidence"
REASON_MANAGER_ONLY_WINDOW = "manager_only_window"
REASON_NO_CUSTOMER_CONTENT = "no_customer_content"
REASON_CUSTOMER_QUOTE_UNVERIFIED = "customer_quote_unverified"


def flag(name: str, default: bool = True) -> bool:
    """Прочитати feature-флаг етапу з Django settings (керується .env)."""
    value = getattr(django_settings, name, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def role_boundary_enforced() -> bool:
    return flag("IG_ANALYSIS_MANAGER_EVIDENCE_BOUNDARY", True)


def claim_scope_for_role(role) -> str:
    normalized = str(role or "").strip().casefold()
    if normalized == InstagramBotMessage.Role.USER:
        return CLAIM_SCOPE_CUSTOMER
    if normalized == InstagramBotMessage.Role.MANAGER:
        return CLAIM_SCOPE_MANAGER
    if normalized == InstagramBotMessage.Role.MODEL:
        return CLAIM_SCOPE_BOT
    return CLAIM_SCOPE_SYSTEM


@dataclass(frozen=True, slots=True)
class RoleCoverage:
    """Покриття висновку доказами в розрізі ролі автора повідомлення."""

    customer_message_ids: tuple[int, ...] = ()
    manager_message_ids: tuple[int, ...] = ()
    bot_message_ids: tuple[int, ...] = ()
    system_message_ids: tuple[int, ...] = ()

    @property
    def has_customer_evidence(self) -> bool:
        return bool(self.customer_message_ids)

    @property
    def has_manager_evidence(self) -> bool:
        return bool(self.manager_message_ids)

    @property
    def has_non_customer_evidence(self) -> bool:
        return bool(
            self.manager_message_ids
            or self.bot_message_ids
            or self.system_message_ids
        )

    @property
    def is_empty(self) -> bool:
        return not (
            self.customer_message_ids
            or self.manager_message_ids
            or self.bot_message_ids
            or self.system_message_ids
        )

    def as_payload(self) -> dict:
        """Проєкція покриття для API/UI без вільного тексту клієнта."""
        return {
            "customer_message_ids": list(self.customer_message_ids),
            "manager_message_ids": list(self.manager_message_ids),
            "bot_message_ids": list(self.bot_message_ids),
            "customer_evidence_count": len(self.customer_message_ids),
            "manager_evidence_count": len(self.manager_message_ids),
            "bot_evidence_count": len(self.bot_message_ids),
            "has_customer_evidence": self.has_customer_evidence,
        }


def evidence_role_coverage(evidence) -> RoleCoverage:
    """Розкласти список доказів по ролі автора, не довіряючи загальному рядку."""
    buckets: dict[str, list[int]] = {
        CLAIM_SCOPE_CUSTOMER: [],
        CLAIM_SCOPE_MANAGER: [],
        CLAIM_SCOPE_BOT: [],
        CLAIM_SCOPE_SYSTEM: [],
    }
    for item in evidence if isinstance(evidence, list) else ():
        if not isinstance(item, dict):
            continue
        try:
            message_id = int(item.get("message_id") or 0)
        except (TypeError, ValueError):
            continue
        if message_id <= 0:
            continue
        scope = claim_scope_for_role(item.get("source_role"))
        if message_id not in buckets[scope]:
            buckets[scope].append(message_id)
    return RoleCoverage(
        customer_message_ids=tuple(buckets[CLAIM_SCOPE_CUSTOMER]),
        manager_message_ids=tuple(buckets[CLAIM_SCOPE_MANAGER]),
        bot_message_ids=tuple(buckets[CLAIM_SCOPE_BOT]),
        system_message_ids=tuple(buckets[CLAIM_SCOPE_SYSTEM]),
    )


def annotate_evidence_claim_scope(evidence) -> list[dict]:
    """Позначити кожен доказ типізованою межею замість спільного рядка.

    `source_role` уже зберігався, але читач мусив сам вирішувати, що з ним
    робити — і фактично не робив нічого. `claim_scope` робить межу явною в
    самих даних: одна цитата менеджера у змішаному транскрипті більше не
    «розчиняється» у списку доказів наміру клієнта.
    """
    result = []
    for item in evidence if isinstance(evidence, list) else ():
        if not isinstance(item, dict):
            continue
        result.append({
            **item,
            "claim_scope": claim_scope_for_role(item.get("source_role")),
        })
    return result


@dataclass(frozen=True, slots=True)
class WindowRoles:
    """Які ролі взагалі присутні у вікні аналізу."""

    has_customer_message: bool = False
    has_manager_message: bool = False
    has_bot_message: bool = False


def window_roles(by_id) -> WindowRoles:
    """Роль авторів транскрипту, який бачила модель.

    Потрібно окремо від покриття доказів: порожній `evidence` не є порушенням
    ролі — модель просто не дала цитати, що вже фіксується кодом
    `evidence_unverified`, і детермінований user-чек (наприклад, явний запит
    кастомного принту) підтверджує клієнта без цитати. Але якщо у вікні
    взагалі немає повідомлення клієнта, висновок про клієнта не може бути
    йому атрибутований за побудовою.
    """
    customer = manager = bot = False
    for item in (by_id or {}).values():
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        if role == "user":
            customer = True
        elif role == "manager":
            manager = True
        elif role == "model":
            bot = True
    return WindowRoles(
        has_customer_message=customer,
        has_manager_message=manager,
        has_bot_message=bot,
    )


@dataclass(frozen=True, slots=True)
class RoleBoundaryOutcome:
    interaction_type: str
    score_band: str
    purchase_probability: object
    confidence: object
    uncertainties: tuple[str, ...]
    reason: str
    coverage: RoleCoverage

    @property
    def changed(self) -> bool:
        return self.reason in {
            REASON_MANAGER_ONLY_EVIDENCE,
            REASON_NON_CUSTOMER_EVIDENCE,
            REASON_MANAGER_ONLY_WINDOW,
            REASON_NO_CUSTOMER_CONTENT,
        }

    @property
    def is_manager_observation(self) -> bool:
        return self.interaction_type == _TYPES.MANAGER_OBSERVATION


def apply_source_role_boundary(
    *,
    interaction_type: str,
    score_band: str,
    purchase_probability=None,
    confidence=None,
    uncertainties=(),
    coverage: RoleCoverage,
    window: WindowRoles | None = None,
    verified_payment: bool = False,
) -> RoleBoundaryOutcome:
    """Звести висновок до того, що підтверджує роль автора доказів."""
    codes = list(uncertainties or ())
    window = window or WindowRoles()

    def outcome(reason, *, interaction="", band="", zeroed=False, extra_code=""):
        extended = list(codes)
        if extra_code and extra_code not in extended:
            extended.append(extra_code)
        return RoleBoundaryOutcome(
            interaction_type=interaction or interaction_type,
            score_band=band or score_band,
            purchase_probability=(
                Decimal("0.0000") if zeroed else purchase_probability
            ),
            confidence=Decimal("0.0000") if zeroed else confidence,
            uncertainties=tuple(dict.fromkeys(extended)),
            reason=reason,
            coverage=coverage,
        )

    if not role_boundary_enforced():
        return outcome("")
    if interaction_type in NON_CUSTOMER_CLAIM_TYPES:
        return outcome(REASON_NOT_CUSTOMER_CLAIM)
    if verified_payment and (
        interaction_type in AUTHORITY_BACKED_TYPES or score_band == _BANDS.PAID
    ):
        # Оплата підтверджена самою системою. Це не слова менеджера в чаті, і
        # вимога цитати клієнта тут понизила б власну істину CRM.
        return outcome(REASON_AUTHORITY_BACKED)
    if coverage.has_customer_evidence:
        return outcome(REASON_CUSTOMER_EVIDENCE)
    if coverage.has_manager_evidence:
        # Висновок прямо атрибутований тексту менеджера — це спостереження
        # менеджера, а не намір клієнта. Типізуємо явно, щоб кожен існуючий
        # enum-фільтр (CRM, follow-up, UGC, counts) почав його виключати.
        return outcome(
            REASON_MANAGER_ONLY_EVIDENCE,
            interaction=_TYPES.MANAGER_OBSERVATION,
            band=_BANDS.COLD,
            zeroed=True,
            extra_code=UNCERTAINTY_MANAGER_EVIDENCE,
        )
    if coverage.has_non_customer_evidence:
        # Власні слова бота (або системний рядок) — теж не намір клієнта, але
        # називати їх спостереженням менеджера було б неправдою. Той самий
        # результат уже дає Analysis V2 для model-only доказу.
        return outcome(
            REASON_NON_CUSTOMER_EVIDENCE,
            interaction=_TYPES.INFORMATION_ONLY,
            band=_BANDS.COLD,
            zeroed=True,
            extra_code=UNCERTAINTY_EVIDENCE_UNVERIFIED,
        )
    if not window.has_customer_message:
        # Клієнта у вікні немає взагалі: висновок про нього неатрибутовний за
        # побудовою. Якщо у вікні є менеджер — це його спостереження.
        if window.has_manager_message:
            return outcome(
                REASON_MANAGER_ONLY_WINDOW,
                interaction=_TYPES.MANAGER_OBSERVATION,
                band=_BANDS.COLD,
                zeroed=True,
                extra_code=UNCERTAINTY_MANAGER_EVIDENCE,
            )
        return outcome(
            REASON_NO_CUSTOMER_CONTENT,
            interaction=_TYPES.INFORMATION_ONLY,
            band=_BANDS.COLD,
            zeroed=True,
            extra_code=UNCERTAINTY_EVIDENCE_UNVERIFIED,
        )
    # Клієнт у вікні є, але модель не дала жодної перевіреної цитати. Це не
    # порушення ролі, а невірифікований доказ: медіа-хід узагалі неможливо
    # процитувати, а детермінований user-чек (явний запит кастомного принту)
    # підтверджує клієнта без цитати. Пониження типу тут стверджувало б факт
    # («клієнт лише цікавився»), якого дані не підтверджують.
    return outcome(
        REASON_CUSTOMER_QUOTE_UNVERIFIED,
        extra_code=UNCERTAINTY_EVIDENCE_UNVERIFIED,
    )


def manifest_role_coverage(manifest) -> RoleCoverage:
    """Покриття ролей за evidence manifest Analysis V2.

    Manifest уже несе `source_role` для кожного message_id, тому legacy-знімок
    і V2-результат зводяться до однієї структури і не можуть розійтися в
    трактуванні ролі автора.
    """
    return evidence_role_coverage([
        {
            "message_id": row.get("message_id"),
            "source_role": row.get("source_role"),
        }
        for row in manifest if isinstance(row, dict)
    ])


def snapshot_role_coverage(snapshot) -> RoleCoverage:
    """Покриття ролей уже збереженого знімка (читається з `evidence`)."""
    return evidence_role_coverage(getattr(snapshot, "evidence", None))


def snapshot_is_manager_observation(snapshot) -> bool:
    return bool(
        snapshot is not None
        and getattr(snapshot, "interaction_type", "") == _TYPES.MANAGER_OBSERVATION
    )


def snapshot_carries_customer_intent(snapshot) -> bool:
    """Чи має знімок право нести намір клієнта у поточних читачах CRM.

    Історичні знімки (до `ROLE_BOUNDARY_POLICY_VERSION`) могли отримати
    customer-facing enum на доказі менеджера, тому read-шлях перевіряє покриття
    ролей ще раз, а не лише enum.
    """
    if snapshot is None:
        return False
    if snapshot_is_manager_observation(snapshot):
        return False
    interaction_type = str(getattr(snapshot, "interaction_type", "") or "")
    if interaction_type in NON_CUSTOMER_CLAIM_TYPES:
        return True
    return snapshot_role_coverage(snapshot).has_customer_evidence
