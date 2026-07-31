"""Atomic current Instagram order ownership and its audit trail.

The immutable payment attribution remains the commercial history.  This
module owns the mutable operational projection used by the manager workspace
and customer-fulfillment workers.
"""

from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone


class OrderAssignmentError(ValueError):
    """Base error for a rejected assignment mutation."""


class AssignmentConflict(OrderAssignmentError):
    """The order has a different active Instagram owner."""


class AssignmentVersionConflict(OrderAssignmentError):
    """The manager action was based on a stale drawer version."""


class AssignmentNotFound(OrderAssignmentError):
    """No current assignment exists for the requested order."""


def _uuid(value):
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _actor_source(actor, requested):
    from management.ig_bot_models import IgOrderAssignmentEvent

    if requested:
        return requested
    return (
        IgOrderAssignmentEvent.ActorSource.MANAGEMENT_USER
        if actor is not None
        else IgOrderAssignmentEvent.ActorSource.AUTOMATION
    )


def _assignment_event_snapshot(assignment, *, reason_code, reason):
    return {
        "assignment_version": assignment.version,
        "source": assignment.source,
        "reason_code": reason_code or "",
        "reason": reason or "",
    }


def _replayed_assignment(operation_id):
    if operation_id is None:
        return None
    from management.ig_bot_models import IgOrderAssignmentEvent

    event = (
        IgOrderAssignmentEvent.objects.select_related("assignment")
        .filter(operation_id=operation_id)
        .first()
    )
    return event.assignment if event else None


def _legacy_owner_conflict(order_id, client_id):
    """Reject stale legacy ownership before the projection is backfilled."""

    from management.ig_bot_models import (
        IgDeal,
        IgOrderAttribution,
        IgPaymentConfirmationReview,
    )

    attribution = (
        IgOrderAttribution.objects.select_for_update()
        .filter(order_id=order_id)
        .first()
    )
    if attribution and attribution.client_id != client_id:
        return True
    if IgDeal.objects.filter(order_id=order_id).exclude(client_id=client_id).exists():
        return True
    if IgPaymentConfirmationReview.objects.filter(order_id=order_id).exclude(client_id=client_id).exists():
        return True
    return False


def current_assignment_for_order(order):
    """Return the active projection, excluding an explicitly unlinked order."""

    from management.ig_bot_models import IgOrderAssignment

    order_id = getattr(order, "pk", order)
    return (
        IgOrderAssignment.objects.select_related("client", "assigned_by")
        .filter(order_id=order_id, client_id__isnull=False, unassigned_at__isnull=True)
        .first()
    )


def _locked_order(order):
    from orders.models import Order

    order_id = getattr(order, "pk", order)
    queryset = Order.objects.select_for_update()
    try:
        return queryset.get(pk=order_id)
    except (Order.DoesNotExist, ValueError, TypeError):
        return queryset.get(order_number=str(order_id).strip())


@transaction.atomic
def link_order_to_client(
    order,
    *,
    client,
    actor=None,
    source=None,
    actor_source=None,
    operation_id=None,
    expected_version=None,
    reason_code="",
    reason="",
):
    """Link one exact order to one Instagram client under a row lock.

    A repeated link to the same current client is intentionally a no-op.  A
    client-supplied operation id replays the original event and never creates a
    second audit row.
    """

    from management.ig_bot_models import (
        IgOrderAssignment,
        IgOrderAssignmentEvent,
    )

    operation_id = _uuid(operation_id)
    source = source or IgOrderAssignment.Source.MANAGER_MANUAL
    actor_source = _actor_source(actor, actor_source)
    locked_order = _locked_order(order)
    replay = _replayed_assignment(operation_id)
    if replay is not None:
        if replay.order_id != locked_order.pk:
            raise OrderAssignmentError("Operation id belongs to another order")
        return replay

    if _legacy_owner_conflict(locked_order.pk, client.pk):
        raise AssignmentConflict("Замовлення вже прив'язано до іншого Instagram-клієнта")

    assignment = (
        IgOrderAssignment.objects.select_for_update()
        .filter(order_id=locked_order.pk)
        .first()
    )
    if assignment is None:
        assignment = IgOrderAssignment.objects.create(
            order=locked_order,
            client=client,
            source=source,
            assigned_by=actor,
            assigned_at=timezone.now(),
            version=1,
            last_reason_code=reason_code or "",
            last_reason=reason or "",
        )
        previous_client_id = None
    else:
        if expected_version is not None and assignment.version != int(expected_version):
            raise AssignmentVersionConflict("Версія прив'язки вже змінилася")
        if assignment.client_id and assignment.client_id != client.pk:
            raise AssignmentConflict("Замовлення вже прив'язано до іншого Instagram-клієнта")
        if assignment.client_id == client.pk and assignment.unassigned_at is None:
            return assignment
        previous_client_id = assignment.client_id
        assignment.client = client
        assignment.source = source
        assignment.assigned_by = actor
        assignment.assigned_at = timezone.now()
        assignment.unassigned_at = None
        assignment.version += 1
        assignment.last_reason_code = reason_code or ""
        assignment.last_reason = reason or ""
        assignment.save(update_fields=[
            "client",
            "source",
            "assigned_by",
            "assigned_at",
            "unassigned_at",
            "version",
            "last_reason_code",
            "last_reason",
            "updated_at",
        ])

    IgOrderAssignmentEvent.objects.create(
        operation_id=operation_id or uuid.uuid4(),
        assignment=assignment,
        order=locked_order,
        kind=(
            IgOrderAssignmentEvent.Kind.AUTO_CONFIRMED
            if actor_source == IgOrderAssignmentEvent.ActorSource.AUTOMATION
            else IgOrderAssignmentEvent.Kind.LINKED
        ),
        from_client_id=previous_client_id,
        to_client=client,
        actor=actor,
        actor_source=actor_source,
        assignment_source=source,
        reason_code=reason_code or "",
        reason=reason or "",
        assignment_version=assignment.version,
        snapshot=_assignment_event_snapshot(
            assignment,
            reason_code=reason_code,
            reason=reason,
        ),
    )
    return assignment


@transaction.atomic
def unlink_order_from_client(
    order,
    *,
    actor=None,
    actor_source=None,
    operation_id=None,
    expected_version=None,
    reason_code="",
    reason="",
):
    """Clear the current owner without deleting projection or audit history."""

    from management.ig_bot_models import (
        IgOrderAssignment,
        IgOrderAssignmentEvent,
    )

    operation_id = _uuid(operation_id)
    actor_source = _actor_source(actor, actor_source)
    locked_order = _locked_order(order)
    replay = _replayed_assignment(operation_id)
    if replay is not None:
        if replay.order_id != locked_order.pk:
            raise OrderAssignmentError("Operation id belongs to another order")
        return replay
    assignment = (
        IgOrderAssignment.objects.select_for_update()
        .filter(order_id=locked_order.pk)
        .first()
    )
    if assignment is None:
        raise AssignmentNotFound("У замовлення немає поточної прив'язки")
    if expected_version is not None and assignment.version != int(expected_version):
        raise AssignmentVersionConflict("Версія прив'язки вже змінилася")
    if assignment.client_id is None or assignment.unassigned_at is not None:
        return assignment
    if not str(reason_code or "").strip() or not str(reason or "").strip():
        raise ValueError("Для відв'язки потрібні код і пояснення причини")

    previous_client_id = assignment.client_id
    assignment.client = None
    assignment.unassigned_at = timezone.now()
    assignment.version += 1
    assignment.last_reason_code = str(reason_code).strip()
    assignment.last_reason = str(reason).strip()
    assignment.save(update_fields=[
        "client",
        "unassigned_at",
        "version",
        "last_reason_code",
        "last_reason",
        "updated_at",
    ])
    IgOrderAssignmentEvent.objects.create(
        operation_id=operation_id or uuid.uuid4(),
        assignment=assignment,
        order=locked_order,
        kind=IgOrderAssignmentEvent.Kind.UNLINKED,
        from_client_id=previous_client_id,
        to_client=None,
        actor=actor,
        actor_source=actor_source,
        assignment_source=assignment.source,
        reason_code=assignment.last_reason_code,
        reason=assignment.last_reason,
        assignment_version=assignment.version,
        snapshot=_assignment_event_snapshot(
            assignment,
            reason_code=assignment.last_reason_code,
            reason=assignment.last_reason,
        ),
    )
    return assignment


def assignment_source_for_attribution(*, creation_mode, payment_source):
    from management.ig_bot_models import IgOrderAssignment

    if str(payment_source or "").startswith("provider_") or creation_mode == "provider_auto":
        return IgOrderAssignment.Source.PROVIDER_AUTO
    if creation_mode in {"checkout_auto", "direct_checkout"}:
        return IgOrderAssignment.Source.CHECKOUT_AUTO
    if creation_mode == "manager_review":
        return IgOrderAssignment.Source.MANAGER_PAYMENT_REVIEW
    return IgOrderAssignment.Source.MANAGER_MANUAL
