"""Versioned, evidence-based routing for Instagram Gemini work.

The router deliberately consumes *structured facts* produced by the ingress,
commerce and media layers.  It does not promote a turn merely because a word
such as ``price`` or ``size`` appeared in free text.  The resulting immutable
decision is safe to persist before any provider request and can therefore be
explained after a fallback, deadline or worker restart.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from django.utils import timezone


POLICY_VERSION = "gemini-routing-v2.1"
AUTHORITY_SNAPSHOT_VERSION = "ig-authority-v1"


class TaskClass(StrEnum):
    NO_MODEL = "no_model"
    ORDINARY_LIVE = "ordinary_live"
    COMPLEX_LIVE = "complex_live"
    DURABLE_ANALYSIS = "durable_analysis"


class RoutingMode(StrEnum):
    ADAPTIVE = "adaptive"
    PINNED = "pinned"


ORDINARY_CHAIN = (
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
)
COMPLEX_CHAIN = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
)
ANALYSIS_CHAIN = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
)
ANALYSIS_ESCALATION_CHAIN = ("gemini-3.7-flash",)

_ALLOWED_LIVE_MODELS = frozenset(ORDINARY_CHAIN)
_NO_MODEL_REASONS = frozenset({
    "authoritative_reply",
    "postback",
    "provider_native_ugc",
    "media_unavailable",
})


@dataclass(frozen=True)
class TurnFacts:
    """Bounded facts known before the customer-facing provider call."""

    deterministic_action: str = ""
    has_image: bool = False
    has_audio: bool = False
    unresolved_catalog_candidates: int = 0
    personalized_fit_required: bool = False
    product_or_recipient_switch: bool = False
    custom_print_brief: bool = False
    conflicting_intent: bool = False
    ambiguous_ad_referral: bool = False
    comparison_required: bool = False
    commercial_risk: str = "low"
    reasoning_task_hint: str = ""


@dataclass(frozen=True)
class RoutingDecision:
    lane: str
    task_class: TaskClass
    reason_codes: tuple[str, ...]
    authority_snapshot_version: str
    requires_media_reasoning: bool
    commercial_risk: str
    model_chain: tuple[str, ...]
    deadline_ms: int
    policy_version: str = POLICY_VERSION
    reasoning_task: str = "customer_chat"
    routing_mode: RoutingMode = RoutingMode.ADAPTIVE

    def as_dict(self) -> dict:
        return {
            "lane": self.lane,
            "task_class": self.task_class.value,
            "reason_codes": list(self.reason_codes),
            "authority_snapshot_version": self.authority_snapshot_version,
            "requires_media_reasoning": self.requires_media_reasoning,
            "commercial_risk": self.commercial_risk,
            "model_chain": list(self.model_chain),
            "deadline_ms": self.deadline_ms,
            "policy_version": self.policy_version,
            "reasoning_task": self.reasoning_task,
            "routing_mode": self.routing_mode.value,
        }


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def active_pin(settings_obj, *, now=None) -> str:
    """Return a valid, unexpired emergency chat pin without mutating settings."""
    if settings_obj is None:
        return ""
    if str(getattr(settings_obj, "gemini_routing_mode", "") or "") != RoutingMode.PINNED:
        return ""
    pinned_until = getattr(settings_obj, "pinned_until", None)
    now = now or timezone.now()
    if pinned_until is None or pinned_until <= now:
        return ""
    model = str(getattr(settings_obj, "pinned_chat_model", "") or "").strip()
    return model if model in _ALLOWED_LIVE_MODELS else ""


def _apply_pin(chain: tuple[str, ...], settings_obj, *, now=None) -> tuple[tuple[str, ...], RoutingMode]:
    pinned = active_pin(settings_obj, now=now)
    if not pinned:
        return chain, RoutingMode.ADAPTIVE
    return _unique((pinned, *chain)), RoutingMode.PINNED


def classify_live_turn(facts: TurnFacts, *, settings_obj=None, now=None) -> RoutingDecision:
    """Classify one live turn from structured evidence, never raw keywords."""
    deterministic = str(facts.deterministic_action or "").strip()
    if deterministic:
        reason = deterministic if deterministic in _NO_MODEL_REASONS else "authoritative_reply"
        return RoutingDecision(
            lane="live",
            task_class=TaskClass.NO_MODEL,
            reason_codes=(reason,),
            authority_snapshot_version=AUTHORITY_SNAPSHOT_VERSION,
            requires_media_reasoning=False,
            commercial_risk=str(facts.commercial_risk or "low"),
            model_chain=(),
            deadline_ms=0,
            reasoning_task="no_model",
        )

    complex_reasons: list[str] = []
    if facts.has_image:
        complex_reasons.append("image_reasoning")
    if facts.has_audio:
        complex_reasons.append("audio_reasoning")
    if int(facts.unresolved_catalog_candidates or 0) > 1:
        complex_reasons.append("ambiguous_catalog")
    for enabled, reason in (
        (facts.personalized_fit_required, "personalized_fit"),
        (facts.product_or_recipient_switch, "branch_switch"),
        (facts.custom_print_brief, "custom_print"),
        (facts.conflicting_intent, "conflicting_intent"),
        (facts.ambiguous_ad_referral, "ambiguous_referral"),
        (facts.comparison_required, "comparison"),
    ):
        if enabled:
            complex_reasons.append(reason)

    if complex_reasons:
        chain, mode = _apply_pin(COMPLEX_CHAIN, settings_obj, now=now)
        task = str(facts.reasoning_task_hint or "").strip()
        if task not in {
            "media_analysis", "catalog_match", "product_decision",
            "size_fit_decision", "payment_decision", "order_decision",
        }:
            task = "media_analysis" if facts.has_image or facts.has_audio else "product_decision"
        return RoutingDecision(
            lane="live",
            task_class=TaskClass.COMPLEX_LIVE,
            reason_codes=_unique(complex_reasons),
            authority_snapshot_version=AUTHORITY_SNAPSHOT_VERSION,
            requires_media_reasoning=bool(facts.has_image or facts.has_audio),
            commercial_risk=str(facts.commercial_risk or "medium"),
            model_chain=chain,
            deadline_ms=45_000,
            reasoning_task=task,
            routing_mode=mode,
        )

    chain, mode = _apply_pin(ORDINARY_CHAIN, settings_obj, now=now)
    return RoutingDecision(
        lane="live",
        task_class=TaskClass.ORDINARY_LIVE,
        reason_codes=("backend_facts_ready",),
        authority_snapshot_version=AUTHORITY_SNAPSHOT_VERSION,
        requires_media_reasoning=False,
        commercial_risk=str(facts.commercial_risk or "low"),
        model_chain=chain,
        deadline_ms=35_000,
        reasoning_task="customer_chat",
        routing_mode=mode,
    )


def durable_analysis_decision(*, reason_codes: Iterable[str] = ()) -> RoutingDecision:
    return RoutingDecision(
        lane="analysis",
        task_class=TaskClass.DURABLE_ANALYSIS,
        reason_codes=_unique(reason_codes) or ("material_change",),
        authority_snapshot_version=AUTHORITY_SNAPSHOT_VERSION,
        requires_media_reasoning=False,
        commercial_risk="medium",
        model_chain=ANALYSIS_CHAIN,
        deadline_ms=75_000,
        reasoning_task="customer_intelligence",
    )


def analysis_escalation_chain(
    *,
    schema_valid: bool,
    low_confidence: bool,
    high_value: bool,
    conflict_or_missing_fact: bool,
    already_escalated: bool,
    capacity_available: bool,
) -> tuple[str, ...]:
    """Return the one-pass 3.7 escalation hook for durable analysis.

    A 3.6 outage is intentionally absent from the inputs: unavailability alone
    must never spend scarce 3.7 analysis quota.
    """
    if all((
        schema_valid,
        low_confidence,
        high_value,
        conflict_or_missing_fact,
        not already_escalated,
        capacity_available,
    )):
        return ANALYSIS_ESCALATION_CHAIN
    return ()


def persist_decision(message, decision: RoutingDecision) -> None:
    """Persist the immutable route before provider I/O; telemetry is fail-soft."""
    if message is None or not getattr(message, "pk", None):
        return
    payload = decision.as_dict()
    fields = {
        "gemini_task_class": payload["task_class"],
        "gemini_routing_reason_codes": payload["reason_codes"],
        "gemini_routing_policy_version": payload["policy_version"],
        "gemini_routing_model_chain": payload["model_chain"],
        "gemini_routing_deadline_ms": payload["deadline_ms"],
        "gemini_routing_lane": payload["lane"],
        "gemini_routing_authority_version": payload["authority_snapshot_version"],
        "gemini_routing_requires_media": payload["requires_media_reasoning"],
        "gemini_routing_commercial_risk": payload["commercial_risk"],
        "gemini_routing_mode": payload["routing_mode"],
    }
    try:
        updated = type(message).objects.filter(
            pk=message.pk,
            gemini_routing_policy_version="",
        ).update(**fields)
    except Exception:
        return
    if not updated:
        return
    for field, value in fields.items():
        setattr(message, field, value)
