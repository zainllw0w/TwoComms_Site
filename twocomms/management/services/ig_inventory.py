"""MariaDB-safe inventory reservations for assisted checkout invoices."""
from __future__ import annotations

import hashlib

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone


class InventoryReservationError(ValueError):
    """A payable proposal cannot be created from an unavailable allocation."""

    def __init__(self, reason):
        self.reason = str(reason or "inventory_unavailable")[:128]
        super().__init__(self.reason)


def _fingerprint(proposal, allocation_key):
    return hashlib.sha256(
        f"ig-inventory:v2:{proposal.pk}:{proposal.revision}:{allocation_key}".encode()
    ).hexdigest()


def _allocation_for_item(item, *, lock=True):
    from management.services.ig_availability import AllocationSpec, resolve_allocation

    return resolve_allocation(
        AllocationSpec(
            product_id=item.product_id,
            color_variant_id=item.color_variant_id,
            size=item.size,
            fit_code=item.fit_code,
            quantity=int(item.quantity or 0),
        ),
        lock=lock,
    )


def _allocation_key(allocation):
    if allocation.source == "warehouse":
        return f"warehouse:stock_item:{allocation.stock_item_id}"
    if allocation.source == "catalog_variant":
        return f"catalog_variant:variant:{allocation.color_variant_id}"
    return "untracked"


@transaction.atomic
def reserve_proposal_inventory(proposal, *, expires_at=None, require_policy=False):
    from management.models import IgCheckoutInventoryReservation
    from fable5.models import ProductInventoryPolicy
    from warehouse.models import StockItem
    from productcolors.models import ProductColorVariant

    proposal = type(proposal).objects.select_for_update().get(pk=proposal.pk)
    expiry = expires_at or proposal.expires_at
    items = list(proposal.items.select_for_update().order_by("pk"))

    groups = {}
    for item in items:
        policy = ProductInventoryPolicy.objects.filter(product_id=item.product_id).first()
        if policy is None:
            if require_policy or not item.color_variant_id:
                continue
            # Legacy callers created reservations before ProductInventoryPolicy
            # existed. Keep that catalog-variant behavior explicit and isolated
            # from the new proposal path, which requires a policy row.
            from management.services.ig_availability import StockAllocation

            allocation = StockAllocation(
                source="catalog_variant",
                color_variant_id=item.color_variant_id,
                quantity=int(item.quantity or 0),
            )
        elif policy.source == ProductInventoryPolicy.Source.UNTRACKED:
            continue
        else:
            decision = _allocation_for_item(item, lock=True)
            if decision.status.value != "allocatable" or decision.allocation is None:
                raise InventoryReservationError(decision.reason)
            allocation = decision.allocation
        key = _allocation_key(allocation)
        group = groups.setdefault(
            (allocation.source, allocation.stock_item_id, allocation.color_variant_id),
            {
                "allocation": allocation,
                "allocation_key": key,
                "items": [],
                "quantity": 0,
            },
        )
        group["items"].append(item)
        group["quantity"] += int(item.quantity or 0)

    now = timezone.now()
    for group in groups.values():
        allocation = group["allocation"]
        required = group["quantity"]
        if allocation.source == "warehouse":
            stock_item = StockItem.objects.select_for_update().filter(
                pk=allocation.stock_item_id,
            ).first()
            available = int(stock_item.quantity or 0) if stock_item else 0
            allocation_filter = {"stock_item_id": allocation.stock_item_id}
        else:
            variant = ProductColorVariant.objects.select_for_update().filter(
                pk=allocation.color_variant_id,
            ).first()
            available = int(variant.stock or 0) if variant else 0
            allocation_filter = {"color_variant_id": allocation.color_variant_id}
        if available <= 0:
            raise InventoryReservationError("insufficient_reserved_stock")
        reserved = (
            IgCheckoutInventoryReservation.objects.filter(
                **allocation_filter,
                state__in=[
                    IgCheckoutInventoryReservation.State.ACTIVE,
                    IgCheckoutInventoryReservation.State.PAID_COMMITTED,
                ],
                expires_at__gt=now,
            )
            .exclude(proposal_id=proposal.pk)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        if int(reserved) + required > available:
            raise InventoryReservationError("insufficient_reserved_stock")

    reservations = []
    for group in groups.values():
        allocation = group["allocation"]
        group_items = group["items"]
        fingerprint = _fingerprint(proposal, group["allocation_key"])
        existing = IgCheckoutInventoryReservation.objects.select_for_update().filter(
            reservation_fingerprint=fingerprint,
        ).first()
        if existing is not None:
            if existing.state == IgCheckoutInventoryReservation.State.ACTIVE:
                existing.expires_at = expiry
                existing.quantity = group["quantity"]
                existing.line_ids = [item.pk for item in group_items]
                existing.save(update_fields=["expires_at", "quantity", "line_ids", "updated_at"])
            continue
        reservations.append(IgCheckoutInventoryReservation(
            proposal=proposal,
            item=group_items[0],
            product_id=group_items[0].product_id,
            color_variant_id=group_items[0].color_variant_id,
            allocation_source=allocation.source,
            stock_item_id=allocation.stock_item_id,
            allocation_key=group["allocation_key"],
            line_ids=[item.pk for item in group_items],
            quantity=group["quantity"],
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
    """Consume legacy catalog reservations; warehouse rows commit only.

    The payment path calls :func:`commit_proposal_inventory` directly. This
    wrapper remains for older callers and preserves its idempotent return value.
    """
    result = commit_proposal_inventory(proposal, order=order)
    # Preserve the legacy helper's persisted value for older reconciliation
    # callers. Verified payment uses commit_proposal_inventory directly and
    # therefore records the new FULFILLED lifecycle state.
    from management.models import IgCheckoutInventoryReservation

    IgCheckoutInventoryReservation.objects.filter(
        proposal=proposal,
        allocation_source__in=["catalog_variant", ""],
        state=IgCheckoutInventoryReservation.State.FULFILLED,
    ).update(state=IgCheckoutInventoryReservation.State.CONSUMED)
    return result


@transaction.atomic
def commit_proposal_inventory(proposal, *, order=None):
    from management.models import IgCheckoutInventoryReservation
    from productcolors.models import ProductColorVariant

    now = timezone.now()
    reservations = list(
        IgCheckoutInventoryReservation.objects.select_for_update()
        .filter(
            proposal=proposal,
            state__in=[IgCheckoutInventoryReservation.State.ACTIVE,
                       IgCheckoutInventoryReservation.State.RELEASED],
        )
        .order_by("pk")
    )
    if not reservations:
        return 0
    consumed_by_variant = {}
    warehouse_rows = []
    for reservation in reservations:
        if reservation.allocation_source == "warehouse":
            warehouse_rows.append(reservation)
        elif reservation.color_variant_id:
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
    if warehouse_rows:
        for reservation in warehouse_rows:
            if reservation.state == IgCheckoutInventoryReservation.State.RELEASED:
                # A payment arriving after expiry is not allowed to create a
                # negative physical balance. Keep it visible for manager review.
                reservation.state = IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW
                reservation.release_reason = "late_payment_overbooked"
                if order is not None:
                    reservation.order_id = order.pk
                reservation.updated_at = now
                reservation.save(update_fields=["state", "release_reason", "order", "updated_at"])
                continue
            reservation.state = IgCheckoutInventoryReservation.State.PAID_COMMITTED
            reservation.paid_committed_at = now
            if order is not None:
                reservation.order_id = order.pk
            reservation.updated_at = now
            reservation.save(update_fields=["state", "paid_committed_at", "order", "updated_at"])

    updates = {
        "state": IgCheckoutInventoryReservation.State.FULFILLED,
        "consumed_at": now,
        "fulfilled_at": now,
        "updated_at": now,
    }
    if order is not None:
        # The reservation model intentionally has no order FK in 0116; the
        # payment attempt/proposal remains the durable ownership link.
        updates["release_reason"] = f"order:{order.pk}"[:128]
    catalog_ids = [reservation.pk for reservation in reservations if reservation.allocation_source != "warehouse"]
    if not catalog_ids:
        return len(warehouse_rows)
    return IgCheckoutInventoryReservation.objects.filter(
        pk__in=catalog_ids,
        state__in=[
            IgCheckoutInventoryReservation.State.ACTIVE,
            IgCheckoutInventoryReservation.State.RELEASED,
        ],
    ).update(**updates)


@transaction.atomic
def fulfill_warehouse_reservation(
    reservation,
    *,
    order,
    order_item=None,
    write_off_request=None,
    user=None,
):
    """Write off one paid warehouse allocation exactly once."""
    from management.models import IgCheckoutInventoryReservation
    from warehouse.models import MovementReason, StockItem
    from warehouse.services.inventory import adjust_stock_item

    locked = IgCheckoutInventoryReservation.objects.select_for_update().get(
        pk=reservation.pk,
    )
    if locked.state == IgCheckoutInventoryReservation.State.FULFILLED:
        return None
    if locked.state != IgCheckoutInventoryReservation.State.PAID_COMMITTED:
        raise InventoryReservationError("inventory_not_paid_committed")
    if locked.allocation_source != "warehouse" or not locked.stock_item_id:
        raise InventoryReservationError("not_warehouse_allocation")
    stock_item = StockItem.objects.select_for_update().get(pk=locked.stock_item_id)
    quantity = int(locked.quantity or 0)
    if int(stock_item.quantity or 0) < quantity:
        locked.state = IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW
        locked.release_reason = "fulfillment_stock_shortfall"
        locked.save(update_fields=["state", "release_reason", "updated_at"])
        raise InventoryReservationError("fulfillment_stock_shortfall")
    movement = adjust_stock_item(
        stock_item=stock_item,
        delta=-quantity,
        user=user,
        reason=MovementReason.ORDER_WRITE_OFF,
        comment=f"Instagram reservation {locked.pk}",
        order=order,
        write_off_request=write_off_request,
    )
    now = timezone.now()
    locked.state = IgCheckoutInventoryReservation.State.FULFILLED
    locked.order = order
    locked.order_item = order_item
    locked.write_off_request = write_off_request
    locked.stock_movement = movement
    locked.fulfilled_at = now
    locked.consumed_at = locked.consumed_at or now
    locked.save(update_fields=[
        "state", "order", "order_item", "write_off_request", "stock_movement",
        "fulfilled_at", "consumed_at", "updated_at",
    ])
    return movement


def fulfill_order_inventory_reservations(order, *, write_off_request=None, user=None):
    """Attach warehouse write-off movements to paid IG allocations.

    The warehouse UI creates movements first. This adapter binds those exact
    movements to the corresponding paid reservations and is idempotent on
    repeated Telegram/admin callbacks. If no movement exists yet, it performs
    the guarded write-off itself.
    """
    from management.models import IgCheckoutInventoryReservation
    from django.contrib.contenttypes.models import ContentType
    from warehouse.models import StockItem, StockMovement, WriteOffRequest

    if (
        write_off_request is not None
        and write_off_request.status == WriteOffRequest.STATUS_CANCELLED
    ):
        return 0
    try:
        with transaction.atomic():
            stock_item_ct = ContentType.objects.get_for_model(StockItem)
            reservations = list(
                IgCheckoutInventoryReservation.objects.select_for_update().filter(
                    order=order,
                    allocation_source="warehouse",
                    state=IgCheckoutInventoryReservation.State.PAID_COMMITTED,
                ).order_by("pk")
            )
            fulfilled = 0
            for reservation in reservations:
                movement = None
                if write_off_request is not None:
                    movement_queryset = StockMovement.objects.select_for_update().filter(
                        order=order,
                        write_off_request=write_off_request,
                        content_type=stock_item_ct,
                        delta__lt=0,
                    )
                    movement = movement_queryset.filter(
                        object_id=reservation.stock_item_id,
                        delta=-int(reservation.quantity),
                    ).order_by("-pk").first()
                    if movement is None and movement_queryset.exists():
                        raise InventoryReservationError("warehouse_writeoff_mismatch")
                if movement is None:
                    try:
                        movement = fulfill_warehouse_reservation(
                            reservation,
                            order=order,
                            write_off_request=write_off_request,
                            user=user,
                        )
                    except InventoryReservationError as exc:
                        exc.reservation_id = reservation.pk
                        raise
                    if movement is None:
                        continue
                now = timezone.now()
                IgCheckoutInventoryReservation.objects.filter(
                    pk=reservation.pk,
                    state=IgCheckoutInventoryReservation.State.PAID_COMMITTED,
                ).update(
                    state=IgCheckoutInventoryReservation.State.FULFILLED,
                    order=order,
                    write_off_request=write_off_request,
                    stock_movement=movement,
                    fulfilled_at=now,
                    consumed_at=now,
                    updated_at=now,
                )
                fulfilled += 1
            return fulfilled
    except InventoryReservationError as exc:
        # Mark the shortage inside the current transaction. Callers already
        # inside a larger atomic block receive ``reservation_id`` and repeat
        # this update after that outer rollback, so the marker remains durable.
        if (
            exc.reason == "fulfillment_stock_shortfall"
            and getattr(exc, "reservation_id", None)
        ):
            IgCheckoutInventoryReservation.objects.filter(
                pk=exc.reservation_id,
                state=IgCheckoutInventoryReservation.State.PAID_COMMITTED,
            ).update(
                state=IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
                release_reason="fulfillment_stock_shortfall",
                updated_at=timezone.now(),
            )
        raise


@transaction.atomic
def restore_order_inventory_reservations(write_off_request):
    """Clear a reversed write-off link so the paid reservation can be retried."""
    from management.models import IgCheckoutInventoryReservation

    return IgCheckoutInventoryReservation.objects.filter(
        write_off_request=write_off_request,
        state__in=[
            IgCheckoutInventoryReservation.State.PAID_COMMITTED,
            IgCheckoutInventoryReservation.State.FULFILLED,
        ],
    ).update(
        state=IgCheckoutInventoryReservation.State.PAID_COMMITTED,
        write_off_request=None,
        stock_movement=None,
        order_item=None,
        fulfilled_at=None,
        consumed_at=None,
        updated_at=timezone.now(),
    )


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
