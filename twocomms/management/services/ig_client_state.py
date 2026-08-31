"""One derived read-model for the state of an Instagram conversation.

F-STATE-001: six state machines without an arbiter. Client #59 contradicted
himself in five representations at once — `stage=paid`, `intent=size`,
`objection=size`, `purchases_count=0`, and a snapshot reading
`cold / support_complaint / 0%`.

Wave W3 fixed the symptoms one at a time (`_display_band`,
`_display_interaction_type`). That worked, but every next representation needed
its own patch, which is the signature of a missing abstraction rather than of
several bugs.

This module answers the question once, with an explicit precedence of sources:

1. **terminal negative payment** — a refund or a reversal outranks everything,
   because continuing to call the person a buyer after we returned the money is
   the most expensive kind of wrong;
2. **provider-confirmed payment** — the payment ledger;
3. **manager-confirmed payment or a linked paid order** — CRM truth;
4. **conversation analysis** — the model's opinion, weakest of the four.

Service state (an exchange or a return in flight) is a **side flow**, not a stage:
it runs alongside the funnel and must not reset its progress.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CoherentState:
    """The state of one conversation, resolved once from all sources."""

    is_buyer: bool = False
    payment_source: str = "none"
    payment_reversed: bool = False
    purchases: int = 0
    stage: str = ""
    stage_label: str = ""
    funnel_progress: int = 0
    side_flow: str = ""
    side_flow_label: str = ""
    side_flow_status: str = ""
    requested_size: str = ""
    off_funnel: bool = False
    headline: str = ""
    sources: tuple[str, ...] = field(default_factory=tuple)


_SIDE_FLOW_LABELS = {
    "exchange": "обмін",
    "return": "повернення",
}


def _payment_source(client) -> tuple[str, bool]:
    """Which source proves the purchase, and whether the money came back."""
    from management.services.bot_payment_truth import (
        client_has_confirmed_purchase,
        client_has_terminal_negative_payment,
        client_has_verified_payment,
    )

    if client_has_terminal_negative_payment(client):
        return "reversed", True
    if client_has_verified_payment(client):
        return "provider", False
    if client_has_confirmed_purchase(client):
        return "manager", False
    return "none", False


def _funnel_progress(client, stage: str | None = None) -> int:
    """Percent of the main funnel completed, independent of any side flow."""
    from management.models import IgClient

    order = [item.value for item in IgClient.FUNNEL_ORDER]
    try:
        index = order.index(stage if stage is not None else client.stage)
    except ValueError:
        return 0
    return int(round((index + 1) * 100 / len(order)))


def resolve_client_state(client) -> CoherentState:
    """Resolve the whole state of one conversation.

    Deliberately read-only: an arbiter that mutates state would become the
    seventh machine instead of replacing the need for one.
    """
    if not client or not getattr(client, "pk", None):
        return CoherentState()

    payment_source, reversed_payment = _payment_source(client)
    is_buyer = payment_source in {"provider", "manager"}
    purchases = int(getattr(client, "purchases_count", 0) or 0)
    sources = [f"payment:{payment_source}"]

    effective_stage = str(client.stage or "")
    try:
        from management.models import IgClient

        hard_stages = {
            IgClient.Stage.PAID,
            IgClient.Stage.ORDER_CREATED,
            IgClient.Stage.DONE,
        }
        if not is_buyer and effective_stage in hard_stages:
            from management.services.ig_commercial_episodes import (
                derive_current_episode_stage,
            )

            effective_stage = derive_current_episode_stage(client)
            sources.append("stage:derived_current_episode")
    except Exception:
        # Keep the read model available during a partial rollout.  The caller's
        # hard-stage payment warning still prevents a purchase claim.
        effective_stage = str(client.stage or "")

    side_flow = ""
    side_flow_status = ""
    requested_size = ""
    try:
        from management.services.ig_post_sale import open_service_case

        case = open_service_case(client)
    except Exception:
        case = None
    if case is not None:
        side_flow = str(case.case_type)
        side_flow_status = str(case.get_status_display() or "")
        requested_size = str(case.requested_size or "")
        sources.append(f"service_case:{case.pk}")

    stage_label = ""
    try:
        from management.models import IgClient

        stage_label = str(IgClient.Stage(effective_stage).label)
    except Exception:
        stage_label = effective_stage

    headline_parts = []
    if reversed_payment:
        headline_parts.append("Оплату повернено")
    elif is_buyer:
        headline_parts.append("Оплачено")
    else:
        headline_parts.append(stage_label or "Новий")
    if side_flow:
        described = _SIDE_FLOW_LABELS.get(side_flow, side_flow)
        if requested_size:
            described = f"{described} {requested_size}"
        if side_flow_status:
            described = f"{described} · {side_flow_status.lower()}"
        headline_parts.append(described)

    return CoherentState(
        is_buyer=is_buyer,
        payment_source=payment_source,
        payment_reversed=reversed_payment,
        purchases=purchases,
        stage=effective_stage,
        stage_label=stage_label,
        funnel_progress=_funnel_progress(client, effective_stage),
        side_flow=side_flow,
        side_flow_label=_SIDE_FLOW_LABELS.get(side_flow, ""),
        side_flow_status=side_flow_status,
        requested_size=requested_size,
        # `off_funnel` означает «сейчас идёт обслуживание», а не «воронка
        # обнулена»: прогресс сохраняется, просто внимание в другой ветке.
        off_funnel=bool(side_flow),
        headline=" · ".join(part for part in headline_parts if part),
        sources=tuple(sources),
    )
