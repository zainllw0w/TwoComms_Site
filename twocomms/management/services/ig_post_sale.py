"""Evidence-bound exchange and return cases for Instagram purchases."""
from __future__ import annotations

import re

from django.db import transaction

from management.ig_bot_models import IgPostSaleCase
from management.models import InstagramBotMessage


EXCHANGE_RE = re.compile(
    r"\b(?:обмін\w*|обмен\w*|обміняти|обменять|поміняти|поменять|"
    r"замін(?:а|и|у|ою|ити|ювати)\w*|замен(?:а|ы|у|ой|ить|ять)\w*)\b",
    re.I,
)
RETURN_RE = re.compile(r"\b(?:повернен\w*|возврат\w*|повернути|вернуть)\b", re.I)
FIT_RE = re.compile(r"\b(oversize|оверсайз|regular|регуляр|classic|класик\w*)\b", re.I)
SIZE_RE = re.compile(r"\b(3xl|2xl|xxxl|xxl|xl|xs|s|m|l)\b", re.I)
TARGET_SIZE_RE = re.compile(
    r"(?:\bна|\bto)\s+(?:розмір\s+|размер\s+)?(3xl|2xl|xxxl|xxl|xl|xs|s|m|l)\b",
    re.I,
)


def detect_post_sale_type(text: str) -> str:
    value = str(text or "")
    if EXCHANGE_RE.search(value):
        return IgPostSaleCase.CaseType.EXCHANGE
    if RETURN_RE.search(value):
        return IgPostSaleCase.CaseType.RETURN
    return ""


def _extract_details(text: str) -> dict:
    value = str(text or "")
    sizes = [match.group(1).upper() for match in SIZE_RE.finditer(value)]
    target = TARGET_SIZE_RE.search(value)
    fit = FIT_RE.search(value)
    requested_size = target.group(1).upper() if target else (sizes[1] if len(sizes) > 1 else "")
    source_size = sizes[0] if sizes and not (target and len(sizes) == 1) else ""
    return {
        "source_fit": fit.group(1)[:64] if fit else "",
        "source_size": source_size[:32],
        "requested_size": requested_size[:32],
        "reason": value[:500],
    }


def _attributed_orders(client):
    from management.ig_bot_models import IgOrderAttribution

    return list(
        IgOrderAttribution.objects.filter(client=client)
        .select_related("order")
        .order_by("-created_at", "-id")[:3]
    )


@transaction.atomic
def open_post_sale_case(client, message, *, order=None):
    """Create exactly one case from explicit customer evidence.

    A linked order is inferred only when this client has exactly one durable
    Instagram attribution. Multiple purchases remain unresolved until a
    manager/customer identifies the intended order.
    """
    if not isinstance(message, InstagramBotMessage):
        return None
    if message.role != InstagramBotMessage.Role.USER or message.client_id != client.pk:
        return None
    case_type = detect_post_sale_type(message.text)
    if not case_type:
        return None

    existing = IgPostSaleCase.objects.select_for_update().filter(source_message=message).first()
    if existing:
        return existing

    active = (
        IgPostSaleCase.objects.select_for_update()
        .filter(
            client=client,
            case_type=case_type,
            status__in=[IgPostSaleCase.Status.NEEDS_DETAILS, IgPostSaleCase.Status.OPEN],
        )
        .order_by("-updated_at", "-id")
        .first()
    )
    if active:
        details = _extract_details(message.text)
        evidence_ids = list(active.evidence_message_ids or [])
        if message.pk not in evidence_ids:
            evidence_ids.append(message.pk)
        active.evidence_message_ids = evidence_ids[-20:]
        for field in ("source_fit", "source_size", "requested_size"):
            value = details.get(field)
            if value:
                setattr(active, field, value)
        active.reason = "\n".join(
            part for part in (active.reason, details.get("reason")) if part
        )[-500:]
        active.save(update_fields=[
            "evidence_message_ids", "source_fit", "source_size",
            "requested_size", "reason", "updated_at",
        ])
        return active

    attribution = None
    if order is None:
        attributions = _attributed_orders(client)
        if len(attributions) == 1:
            attribution = attributions[0]
            order = attribution.order
    else:
        from management.ig_bot_models import IgOrderAttribution

        attribution = IgOrderAttribution.objects.filter(client=client, order=order).first()

    episode = None
    if attribution is not None:
        episode = getattr(attribution, "commercial_episode", None)
    if episode is None and order is not None:
        episode = getattr(order, "instagram_commercial_episode", None)

    details = _extract_details(message.text)
    return IgPostSaleCase.objects.create(
        client=client,
        order=order,
        commercial_episode=episode,
        source_message=message,
        case_type=case_type,
        status=(IgPostSaleCase.Status.OPEN if order is not None else IgPostSaleCase.Status.NEEDS_DETAILS),
        evidence_message_ids=[message.pk],
        **details,
    )
