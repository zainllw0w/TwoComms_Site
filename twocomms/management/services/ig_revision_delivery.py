"""Transport-neutral drain adapter for dormant revision delivery effects."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable, Mapping

from django.db import connection

from management.models import IgRevisionDeliveryEffect
from management.services.ig_revision_outbox import (
    cancel_unstarted_effect,
    claim_next_effect,
    finish_effect,
    mark_provider_started,
)


_FINAL_CAS_STOP_CODES = frozenset({
    "client_blocked", "client_erasure_changed", "client_missing",
    "client_opted_out", "client_permission_changed", "effect_binding_invalid",
    "fact_binding_unavailable", "manager_takeover", "offer_binding_unavailable",
    "pending_inbound", "publication_changed", "revision_namespace_unavailable",
    "revision_not_current", "revision_snapshot_invalid", "settings_disabled",
    "settings_permission_changed",
})


@dataclass(frozen=True)
class ProviderPartResult:
    provider_namespace: str
    http_status: int | None = None
    provider_message_id: str = ""
    outcome: str = "response"
    explicit_rejection_code: str = "provider_rejected"
    response_digest: str = ""


@dataclass(frozen=True)
class SentPart:
    effect_id: int
    part_index: int
    provider_message_id: str


@dataclass(frozen=True)
class GroupDrainResult:
    state: str
    sent_parts: tuple[SentPart, ...] = ()
    attempted: int = 0
    reason: str = ""
    fallback_ready: bool = False


def _provider_result(value, *, default_namespace: str) -> ProviderPartResult:
    if isinstance(value, ProviderPartResult):
        return value
    if not isinstance(value, Mapping):
        return ProviderPartResult(
            provider_namespace=default_namespace,
            outcome="exception",
        )
    return ProviderPartResult(
        provider_namespace=str(value.get("provider_namespace") or ""),
        http_status=value.get("http_status"),
        provider_message_id=str(value.get("provider_message_id") or ""),
        outcome=str(value.get("outcome") or "response"),
        explicit_rejection_code=str(
            value.get("explicit_rejection_code") or "provider_rejected"
        ),
        response_digest=str(value.get("response_digest") or ""),
    )


def _cancel_revision_unstarted(
    revision_id: int,
    revision_token: str,
    *,
    reason: str,
) -> None:
    effect_ids = list(
        IgRevisionDeliveryEffect.objects.filter(
            revision_id=revision_id,
            state=IgRevisionDeliveryEffect.State.PLANNED,
        ).values_list("id", flat=True)
    )
    for effect_id in effect_ids:
        cancel_unstarted_effect(
            effect_id,
            revision_token,
            reason=reason,
        )


def _group_state(revision_id: int, group: str) -> GroupDrainResult:
    rows = list(
        IgRevisionDeliveryEffect.objects.filter(
            revision_id=revision_id, group=group
        ).order_by("part_index", "id")
    )
    sent = tuple(
        SentPart(row.pk, row.part_index, row.provider_message_id)
        for row in rows if row.state == row.State.SENT
    )
    states = {row.state for row in rows}
    states_enum = IgRevisionDeliveryEffect.State
    if not rows:
        state = "empty"
    elif states_enum.UNKNOWN in states:
        state = "unknown"
    elif states_enum.PROVIDER_STARTED in states:
        state = "provider_started"
    elif states_enum.DEFINITE_FAILED in states:
        state = "definite_failed"
    elif states <= {states_enum.SENT, states_enum.CANCELLED, states_enum.SUPERSEDED}:
        state = "sent" if sent else "cancelled"
    else:
        state = "pending"
    reason = next((row.failure_code for row in rows if row.failure_code), "")
    return GroupDrainResult(state, sent, reason=reason)


def drain_group(
    revision_id: int,
    revision_token: str,
    group: str,
    transport_callback: Callable[[dict], ProviderPartResult | Mapping],
    *,
    fact_checker=None,
    offer_checker=None,
) -> GroupDrainResult:
    """Deliver planned parts once each, invoking transport outside transactions.

    ``transport_callback`` receives a fresh copy read from the canonical DB row
    after provider-start CAS.  It must perform exactly one physical request and
    return a typed receipt; it must not split, retry, or fall back internally.
    """
    if connection.in_atomic_block:
        return GroupDrainResult("blocked", reason="caller_transaction_active")
    attempted = 0
    while True:
        stop_reason = (
            IgRevisionDeliveryEffect.objects.filter(
                revision_id=revision_id,
                state__in=(
                    IgRevisionDeliveryEffect.State.CANCELLED,
                    IgRevisionDeliveryEffect.State.SUPERSEDED,
                ),
                failure_code__in=_FINAL_CAS_STOP_CODES,
            ).values_list("failure_code", flat=True).first()
        )
        if stop_reason:
            _cancel_revision_unstarted(
                revision_id, revision_token, reason=stop_reason
            )
            current = _group_state(revision_id, group)
            return GroupDrainResult(
                current.state,
                current.sent_parts,
                attempted,
                stop_reason,
            )
        claim = claim_next_effect(revision_id, revision_token, group)
        if not claim.token:
            current = _group_state(revision_id, group)
            return GroupDrainResult(
                current.state,
                current.sent_parts,
                attempted,
                claim.reason or current.reason,
            )
        started = mark_provider_started(
            claim.effect.pk,
            claim.token,
            revision_token,
            fact_checker=fact_checker,
            offer_checker=offer_checker,
        )
        if started.reason != "provider_started":
            _cancel_revision_unstarted(
                revision_id,
                revision_token,
                reason=started.reason or "final_cas_failed",
            )
            current = _group_state(revision_id, group)
            return GroupDrainResult(
                current.state,
                current.sent_parts,
                attempted,
                started.reason or "final_cas_failed",
            )

        canonical = IgRevisionDeliveryEffect.objects.filter(
            pk=claim.effect.pk,
            state=IgRevisionDeliveryEffect.State.PROVIDER_STARTED,
        ).values("payload", "provider_namespace").first()
        if canonical is None:
            result = ProviderPartResult(
                provider_namespace=claim.effect.provider_namespace,
                outcome="exception",
            )
        else:
            payload = copy.deepcopy(canonical["payload"])
            attempted += 1
            try:
                raw_result = transport_callback(payload)
            except Exception:
                result = ProviderPartResult(
                    provider_namespace=canonical["provider_namespace"],
                    outcome="exception",
                )
            else:
                result = _provider_result(
                    raw_result,
                    default_namespace=canonical["provider_namespace"],
                )
        finished = finish_effect(
            claim.effect.pk,
            claim.token,
            provider_namespace=result.provider_namespace,
            http_status=result.http_status,
            provider_message_id=result.provider_message_id,
            transport_outcome=result.outcome,
            explicit_rejection_code=result.explicit_rejection_code,
            response_digest=result.response_digest,
        )
        state = getattr(finished.effect, "state", "unknown")
        if state == IgRevisionDeliveryEffect.State.SENT:
            continue
        fallback_ready = bool(
            state == IgRevisionDeliveryEffect.State.DEFINITE_FAILED
            and IgRevisionDeliveryEffect.objects.filter(
                revision_id=revision_id,
                activation_group=finished.effect.group,
                activation_part_index=finished.effect.part_index,
                activation_failure_code=finished.effect.failure_code,
                state=IgRevisionDeliveryEffect.State.PLANNED,
            ).exists()
        )
        current = _group_state(revision_id, group)
        return GroupDrainResult(
            current.state,
            current.sent_parts,
            attempted,
            finished.effect.failure_code,
            fallback_ready,
        )


__all__ = [
    "GroupDrainResult", "ProviderPartResult", "SentPart", "drain_group",
]
