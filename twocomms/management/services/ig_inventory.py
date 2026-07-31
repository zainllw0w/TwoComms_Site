"""MariaDB-safe inventory reservations for assisted checkout invoices."""
from __future__ import annotations

import hashlib

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone


def _fingerprint(proposal, item):
    return hashlib.sha256(
        f"ig-inventory:v1:{proposal.pk}:{proposal.revision}:{item.pk}".encode()
    ).hexdigest()


@transaction.atomic
def reserve_proposal_inventory(proposal, *, expires_at=None):
    from management.models import IgCheckoutInventoryReservation
    from productcolors.models import ProductColorVariant

    proposal = type(proposal).objects.select_for_update().get(pk=proposal.pk)
    expiry = expires_at or proposal.expires_at
    items = list(proposal.items.select_for_update().order_by("pk"))

    required_by_variant = {}
    for item in items:
        if item.color_variant_id:
            required_by_variant[item.color_variant_id] = (
                required_by_variant.get(item.color_variant_id, 0)
                + int(item.quantity or 0)
            )
    variants = {
        row.pk: row
        for row in ProductColorVariant.objects.select_for_update()
        .filter(pk__in=sorted(required_by_variant))
        .order_by("pk")
    }
    now = timezone.now()
    for variant_id, required in required_by_variant.items():
        variant = variants.get(variant_id)
        if variant is None:
            raise ValueError("insufficient_reserved_stock")
        reserved = (
            IgCheckoutInventoryReservation.objects.filter(
                color_variant_id=variant_id,
                state=IgCheckoutInventoryReservation.State.ACTIVE,
                expires_at__gt=now,
            )
            .exclude(proposal_id=proposal.pk)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        if int(reserved) + required > int(variant.stock or 0):
            raise ValueError("insufficient_reserved_stock")

    reservations = []
    for item in items:
        fingerprint = _fingerprint(proposal, item)
        existing = IgCheckoutInventoryReservation.objects.select_for_update().filter(
            reservation_fingerprint=fingerprint,
        ).first()
        if existing is not None:
            if existing.state == IgCheckoutInventoryReservation.State.ACTIVE:
                existing.expires_at = expiry
                existing.save(update_fields=["expires_at", "updated_at"])
            continue
        reservations.append(IgCheckoutInventoryReservation(
            proposal=proposal,
            item=item,
            product_id=item.product_id,
            color_variant_id=item.color_variant_id,
            quantity=item.quantity,
            reservation_fingerprint=fingerprint,
            expires_at=expiry,
        ))
    if reservations:
        IgCheckoutInventoryReservation.objects.bulk_create(reservations)
    return reservations


@transaction.atomic
def release_proposal_inventory(proposal, *, reason="released"):
    from management.models import IgCheckoutInventoryReservation

    now = timezone.now()
    return IgCheckoutInventoryReservation.objects.filter(
        proposal=proposal,
        state=IgCheckoutInventoryReservation.State.ACTIVE,
    ).update(
        state=IgCheckoutInventoryReservation.State.RELEASED,
        released_at=now,
        release_reason=str(reason or "released")[:128],
        updated_at=now,
    )


@transaction.atomic
def release_attempt_inventory(attempt, *, reason="payment_terminal"):
    """Release only a proposal-backed attempt; retail attempts are untouched."""
    from orders.models import PaymentAttempt

    locked = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
    if locked.order_id or locked.status not in {
        PaymentAttempt.Status.FAILED,
        PaymentAttempt.Status.EXPIRED,
        PaymentAttempt.Status.CANCELLED,
    }:
        return 0
    try:
        proposal = locked.instagram_checkout_proposal
    except Exception:
        return 0
    return release_proposal_inventory(proposal, reason=reason)


@transaction.atomic
def consume_proposal_inventory(proposal, *, order=None):
    from management.models import IgCheckoutInventoryReservation
    from productcolors.models import ProductColorVariant

    now = timezone.now()
    reservations = list(
        IgCheckoutInventoryReservation.objects.select_for_update()
        .filter(
            proposal=proposal,
            state__in=[
                IgCheckoutInventoryReservation.State.ACTIVE,
                IgCheckoutInventoryReservation.State.RELEASED,
            ],
        )
        .order_by("pk")
    )
    if not reservations:
        return 0
    consumed_by_variant = {}
    for reservation in reservations:
        if reservation.color_variant_id:
            consumed_by_variant[reservation.color_variant_id] = (
                consumed_by_variant.get(reservation.color_variant_id, 0)
                + int(reservation.quantity or 0)
            )
    variants = {
        row.pk: row
        for row in ProductColorVariant.objects.select_for_update()
        .filter(pk__in=sorted(consumed_by_variant))
        .order_by("pk")
    }
    for variant_id, quantity in consumed_by_variant.items():
        variant = variants.get(variant_id)
        if variant is None or int(variant.stock or 0) < quantity:
            raise ValueError("reserved_stock_changed")
        variant.stock = int(variant.stock) - quantity
        variant.save(update_fields=["stock"])
    updates = {"state": IgCheckoutInventoryReservation.State.CONSUMED, "consumed_at": now, "updated_at": now}
    if order is not None:
        # The reservation model intentionally has no order FK in 0116; the
        # payment attempt/proposal remains the durable ownership link.
        updates["release_reason"] = f"order:{order.pk}"[:128]
    return IgCheckoutInventoryReservation.objects.filter(
        pk__in=[reservation.pk for reservation in reservations],
        state__in=[
            IgCheckoutInventoryReservation.State.ACTIVE,
            IgCheckoutInventoryReservation.State.RELEASED,
        ],
    ).update(**updates)


@transaction.atomic
def release_expired_proposal_inventory(*, limit=500):
    from management.models import IgCheckoutInventoryReservation
    from django.db.models import Q

    now = timezone.now()
    ids = list(IgCheckoutInventoryReservation.objects.filter(
        state=IgCheckoutInventoryReservation.State.ACTIVE,
        expires_at__lte=now,
    ).filter(
        Q(proposal__payment_attempt__isnull=True)
        | Q(proposal__payment_attempt__status__in=["failed", "cancelled", "expired"])
        | Q(proposal__status__in=["cancelled", "expired", "revoked", "superseded"])
    ).order_by("expires_at", "pk").values_list("pk", flat=True)[:limit])
    if not ids:
        return 0
    return IgCheckoutInventoryReservation.objects.filter(
        pk__in=ids,
        state=IgCheckoutInventoryReservation.State.ACTIVE,
        expires_at__lte=now,
    ).update(
        state=IgCheckoutInventoryReservation.State.RELEASED,
        released_at=now,
        release_reason="expired",
        updated_at=now,
    )
