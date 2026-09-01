"""Э0.4 — обвязка вокруг чистой политики: флаг, метрика, журнал расхождений.

Разделение осознанное. `ig_outgoing_policy` не знает ни про базу, ни про кеш,
ни про текущее время, поэтому его можно проверить без провайдера. Здесь живёт
всё, что политика знать не должна: чтение флага, счётчики по `reason_code` и
`policy_basis`, запись расхождения со старой проверкой.

Три режима, и по умолчанию — выключено:

* `off`     — политика вообще не вычисляется, поведение потока не меняется;
* `shadow`  — политика вычисляется и попадает в метрику, решает по-прежнему
              старая проверка (включение метрики без риска для клиента);
* `enforce` — решает политика; старые проверки остаются как финальная
              revalidation перед провайдером.

Даже в `enforce` `allow` НЕ отправляет: он только разрешает потоку дойти до
durable claim, финальной revalidation и receipt-first. Это разные шаги, и они
остаются снаружи политики.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache

from management.services.ig_outgoing_policy import (
    ALLOW,
    BLOCK,
    DEFER,
    ESCALATE,
    OutgoingDecision,
    OutgoingRequest,
    decide_outgoing,
)

logger = logging.getLogger("management.ig_outgoing_gate")

MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODE_ENFORCE = "enforce"
MODES = frozenset({MODE_OFF, MODE_SHADOW, MODE_ENFORCE})

_REASON_COUNTER_PREFIX = "ig_outgoing_policy:reason:"
_BASIS_COUNTER_PREFIX = "ig_outgoing_policy:basis:"
_DIVERGENCE_COUNTER_PREFIX = "ig_outgoing_policy:divergence:"
COUNTER_TTL_SECONDS = 7 * 24 * 3600


def configured_mode() -> str:
    """Режим из настроек. Любое неизвестное значение читается как `off`."""
    value = str(getattr(settings, "IG_OUTGOING_POLICY_MODE", MODE_OFF) or MODE_OFF)
    value = value.strip().casefold()
    return value if value in MODES else MODE_OFF


def policy_enabled() -> bool:
    return configured_mode() != MODE_OFF


def policy_enforced() -> bool:
    return configured_mode() == MODE_ENFORCE


def _bump(key: str) -> None:
    try:
        if not cache.add(key, 1, COUNTER_TTL_SECONDS):
            cache.incr(key)
    except Exception:  # noqa: BLE001 - метрика не может ломать отправку
        pass


def record_outcome(decision: OutgoingDecision, *, mode: str) -> None:
    """Метрика Э0.4: распределение исходов по `reason_code` и `policy_basis`."""
    _bump(f"{_REASON_COUNTER_PREFIX}{mode}:{decision.reason_code}")
    _bump(f"{_BASIS_COUNTER_PREFIX}{mode}:{decision.policy_basis or 'none'}")


def record_divergence(decision: OutgoingDecision, legacy_decision: str, *, mode: str) -> None:
    _bump(f"{_DIVERGENCE_COUNTER_PREFIX}{mode}:{legacy_decision}:{decision.decision}")
    logger.info(
        "ig outgoing policy divergence mode=%s legacy=%s policy=%s reason=%s basis=%s audit=%s",
        mode,
        legacy_decision,
        decision.decision,
        decision.reason_code,
        decision.policy_basis or "-",
        decision.audit_mapping(),
    )


def evaluate(
    request: OutgoingRequest,
    *,
    now,
    legacy_decision: str = "",
) -> tuple[OutgoingDecision | None, bool]:
    """Вернуть (решение, надо-ли-ему-подчиняться).

    `off` не вычисляет ничего и возвращает `(None, False)`: ни одного
    дополнительного запроса и ни одной записи, пока флаг выключен.
    В `shadow` решение вычислено и посчитано, но подчиняться ему нельзя —
    включение это отдельный шаг с фиксацией метрики.
    """
    mode = configured_mode()
    if mode == MODE_OFF:
        return None, False
    try:
        decision = decide_outgoing(request, now=now)
    except Exception:  # noqa: BLE001 - политика не имеет права ронять поток
        logger.exception("ig outgoing policy evaluation failed")
        return None, False
    record_outcome(decision, mode=mode)
    if legacy_decision and legacy_decision != decision.decision:
        record_divergence(decision, legacy_decision, mode=mode)
    return decision, mode == MODE_ENFORCE


def outgoing_policy_telemetry() -> dict[str, object]:
    """Небольшой операционный срез для management-статуса."""
    result: dict[str, object] = {"mode": configured_mode()}
    reasons: dict[str, int] = {}
    bases: dict[str, int] = {}
    divergences: dict[str, int] = {}
    try:
        from management.services.ig_outgoing_policy import REASON_CODES

        mode = configured_mode()
        for reason_code in REASON_CODES:
            value = int(cache.get(f"{_REASON_COUNTER_PREFIX}{mode}:{reason_code}") or 0)
            if value:
                reasons[reason_code] = value
        for basis in ("standard_window", "proven_consent", "provider_allowed_message_type", "none"):
            value = int(cache.get(f"{_BASIS_COUNTER_PREFIX}{mode}:{basis}") or 0)
            if value:
                bases[basis] = value
        for legacy in (ALLOW, DEFER, BLOCK, ESCALATE):
            for policy in (ALLOW, DEFER, BLOCK, ESCALATE):
                if legacy == policy:
                    continue
                key = f"{_DIVERGENCE_COUNTER_PREFIX}{mode}:{legacy}:{policy}"
                value = int(cache.get(key) or 0)
                if value:
                    divergences[f"{legacy}->{policy}"] = value
    except Exception:  # noqa: BLE001
        pass
    result["reason_codes"] = reasons
    result["policy_basis"] = bases
    result["divergence"] = divergences
    return result


__all__ = [
    "MODES",
    "MODE_ENFORCE",
    "MODE_OFF",
    "MODE_SHADOW",
    "configured_mode",
    "evaluate",
    "outgoing_policy_telemetry",
    "policy_enabled",
    "policy_enforced",
    "record_divergence",
    "record_outcome",
]
