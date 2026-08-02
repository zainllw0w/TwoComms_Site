"""Shipment journal for one Instagram order, in both directions.

An exchange is one purchase and several parcels. The project had nowhere to say
that: ``Order.tracking_number`` is a single scalar with no history, and
``IgPostSaleCase`` had no tracking fields at all. On production that produced a
customer with three real parcels (original, return, replacement) of which only
one existed in the database, and two lived as digits inside chat messages.
"""
from __future__ import annotations

import re

from django.db import transaction

TRACKING_RE = re.compile(r"^\d{8,20}$")


def normalize_tracking(value) -> str:
    """Return a clean Nova Poshta number, or "" when it is not one.

    Refuses to guess: a 14-digit number inside a sentence can be a phone, an
    order id or a card fragment, so anything that is not a bare digit sequence of
    plausible length is rejected rather than silently stored.
    """
    text = re.sub(r"[\s\-]+", "", str(value or ""))
    return text if TRACKING_RE.match(text) else ""


def _open_exchange_case(order):
    """The unresolved exchange/return case this order currently belongs to."""
    from management.ig_bot_models import IgPostSaleCase
    from management.services.ig_post_sale import TERMINAL_CASE_STATUSES

    return (
        IgPostSaleCase.objects.filter(order_id=order.pk)
        .exclude(status__in=TERMINAL_CASE_STATUSES)
        .order_by("-updated_at", "-id")
        .first()
    )


@transaction.atomic
def record_order_field_shipment(order_id, *, previous_tracking=None):
    """Materialize the order's current tracking number into the journal.

    Also backfills the previous number when it was never recorded, so an order
    that existed before this journal keeps its first parcel instead of starting
    history from the replacement.
    """
    from management.ig_bot_models import IgOrderShipment
    from orders.models import Order

    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return None

    previous = normalize_tracking(previous_tracking)
    if previous:
        _ensure_shipment(
            order,
            previous,
            direction=IgOrderShipment.Direction.OUTBOUND,
            purpose=IgOrderShipment.Purpose.INITIAL,
        )

    current = normalize_tracking(order.tracking_number)
    if not current:
        # Clearing the field is not a reason to forget what was sent.
        return None

    existing = IgOrderShipment.objects.filter(
        order_id=order.pk,
        tracking_number=current,
        direction=IgOrderShipment.Direction.OUTBOUND,
    ).first()
    if existing is not None:
        return existing

    earlier_outbound = (
        IgOrderShipment.objects.filter(
            order_id=order.pk,
            direction=IgOrderShipment.Direction.OUTBOUND,
        )
        .order_by("created_at", "id")
        .last()
    )
    if earlier_outbound is None:
        purpose = IgOrderShipment.Purpose.INITIAL
        case = None
    else:
        case = _open_exchange_case(order)
        # A manager re-issuing a tracking number by mistake is a correction, not
        # an exchange. The open service case is what makes it an exchange.
        purpose = (
            IgOrderShipment.Purpose.EXCHANGE_REPLACEMENT
            if case is not None
            else IgOrderShipment.Purpose.CORRECTION
        )
    return IgOrderShipment.objects.create(
        order_id=order.pk,
        post_sale_case=case,
        tracking_number=current,
        direction=IgOrderShipment.Direction.OUTBOUND,
        purpose=purpose,
        supersedes=earlier_outbound,
        source=IgOrderShipment.Source.ORDER_FIELD,
    )


def _ensure_shipment(order, tracking, *, direction, purpose, **extra):
    from management.ig_bot_models import IgOrderShipment

    existing = IgOrderShipment.objects.filter(
        order_id=order.pk, tracking_number=tracking, direction=direction
    ).first()
    if existing is not None:
        return existing
    return IgOrderShipment.objects.create(
        order_id=order.pk,
        tracking_number=tracking,
        direction=direction,
        purpose=purpose,
        **extra,
    )


def order_shipment_rows(order) -> list[dict]:
    """Journal of one order as a readable timeline."""
    from management.ig_bot_models import IgOrderShipment

    if order is None or not getattr(order, "pk", None):
        return []
    labels = dict(IgOrderShipment.Purpose.choices)
    direction_labels = dict(IgOrderShipment.Direction.choices)
    payer_labels = dict(IgOrderShipment.Payer.choices)
    rows = []
    for shipment in IgOrderShipment.objects.filter(order_id=order.pk).order_by(
        "created_at", "id"
    ):
        purpose_label = str(labels.get(shipment.purpose, ""))
        if shipment.reuses_outbound_tracking:
            # Иначе одинаковый номер в двух строках читается как дубль ввода.
            purpose_label = f"{purpose_label} (швидке повернення тією ж ТТН)"
        rows.append({
            "id": shipment.pk,
            "order_number": order.order_number or str(order.pk),
            "tracking_number": shipment.tracking_number,
            "payer": shipment.payer,
            "payer_label": str(payer_labels.get(shipment.payer, "")),
            "reuses_outbound_tracking": shipment.reuses_outbound_tracking,
            "tracking_url": (
                "https://novaposhta.ua/tracking/?cargo_number="
                f"{shipment.tracking_number}"
            ),
            "direction": shipment.direction,
            "direction_label": str(direction_labels.get(shipment.direction, "")),
            "purpose": shipment.purpose,
            "purpose_label": purpose_label,
            "post_sale_case_id": shipment.post_sale_case_id,
            "supersedes_id": shipment.supersedes_id,
            "source": shipment.source,
            "evidence_message_id": shipment.evidence_message_id,
            "note": shipment.note,
            "created_at": shipment.created_at.isoformat(),
            "notified_at": (
                shipment.notified_at.isoformat() if shipment.notified_at else ""
            ),
        })
    return rows
