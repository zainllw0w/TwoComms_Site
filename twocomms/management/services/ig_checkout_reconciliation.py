"""Bounded repair for interrupted assisted-checkout state transitions."""
from __future__ import annotations

from django.db import transaction
from django.db.models import Case, Exists, IntegerField, OuterRef, Q, When
from django.utils import timezone

from management.models import IgCheckoutInventoryReservation, IgCheckoutProposal, IgLifecycleEvent
from management.services.ig_inventory import release_expired_proposal_inventory, release_proposal_inventory
from orders.fulfillment_truth import (
    NOVA_POSHTA_DELIVERY_SUCCESS_CODES,
    nova_poshta_order_fulfillment_confirmed,
)


def reconcile_ig_checkout(*, limit=100, pull_ambiguous=True, dry_run=False):
    """Repair persisted truth after a worker/request dies mid-transition.

    The function is deliberately bounded and idempotent. Provider pull is
    attempted only for rows explicitly marked ambiguous by invoice creation
    or by a retryable promo-ledger consumption failure.
    """
    limit = max(1, min(int(limit), 500))
    now = timezone.now()
    result = {
        "released_reservations": 0,
        "expired_proposals": 0,
        "bound_attempts": 0,
        "payment_events": 0,
        "ttn_events": 0,
        "delivery_events": 0,
        "ambiguous_checked": 0,
        "ambiguous_pending": 0,
        "missing_attribution": 0,
        "errors": 0,
    }

    expired = IgCheckoutProposal.objects.filter(
        expires_at__lte=now,
        status__in=[
            IgCheckoutProposal.Status.READY,
            IgCheckoutProposal.Status.VIEWED,
            IgCheckoutProposal.Status.DETAILS_LOCKED,
        ],
    ).order_by("expires_at", "pk")[:limit]
    for proposal in expired:
        if dry_run:
            result["expired_proposals"] += 1
            continue
        try:
            with transaction.atomic():
                from management.models import IgDeal
                from orders.models import PaymentAttempt

                attempt = None
                if proposal.payment_attempt_id:
                    attempt = PaymentAttempt.objects.select_for_update().filter(
                        pk=proposal.payment_attempt_id,
                    ).first()
                locked_deal = IgDeal.objects.select_for_update().get(pk=proposal.deal_id)
                locked = IgCheckoutProposal.objects.select_for_update().get(pk=proposal.pk)
                if locked.expires_at > timezone.now() or locked.status not in {
                    locked.Status.READY,
                    locked.Status.VIEWED,
                    locked.Status.DETAILS_LOCKED,
                }:
                    continue
                if locked.status == locked.Status.DETAILS_LOCKED:
                    if attempt is None or locked.payment_attempt_id != attempt.pk:
                        # The attempt appeared after the candidate query. A later
                        # run will lock it before the deal/proposal graph.
                        continue
                    event_state = dict(getattr(attempt, "event_state", None) or {})
                    if (
                        attempt is None
                        or attempt.status != PaymentAttempt.Status.INITIATED
                        or attempt.monobank_invoice_id
                        or attempt.invoice_url
                        or event_state.get("invoice_creation_lease")
                        or event_state.get("invoice_creation_ambiguous")
                    ):
                        continue
                    attempt.status = PaymentAttempt.Status.EXPIRED
                    attempt.error_reason = "proposal_expired_before_provider_claim"
                    attempt.last_status_at = timezone.now()
                    attempt.save(update_fields=[
                        "status", "error_reason", "last_status_at", "updated",
                    ])
                    from management.services.ig_checkout_payment import release_attempt_promo

                    release_attempt_promo(
                        attempt,
                        reason="proposal_expired_before_provider_claim",
                    )
                locked.status = locked.Status.EXPIRED
                if locked_deal.active_checkout_proposal_id == locked.pk:
                    locked_deal.active_checkout_proposal = None
                    locked_deal.save(update_fields=["active_checkout_proposal", "updated_at"])
                locked.save(update_fields=["status", "updated_at"])
                result["released_reservations"] += release_proposal_inventory(
                    locked,
                    reason="proposal_expired",
                )
                result["expired_proposals"] += 1
        except Exception:
            result["errors"] += 1

    expired_reservations = IgCheckoutInventoryReservation.objects.filter(
        state=IgCheckoutInventoryReservation.State.ACTIVE,
        expires_at__lte=now,
    ).filter(
        Q(proposal__payment_attempt__isnull=True)
        | Q(proposal__payment_attempt__status__in=["failed", "cancelled", "expired"])
        | Q(proposal__status__in=["cancelled", "expired", "revoked", "superseded"])
    ).order_by("expires_at", "pk")[:limit]
    result["released_reservations"] += (
        len(expired_reservations)
        if dry_run
        else release_expired_proposal_inventory(limit=limit)
    )

    from management.services.ig_lifecycle import RECOVERABLE_CANCELLATION_REASONS

    payment_event_exists = IgLifecycleEvent.objects.filter(
        proposal_id=OuterRef("pk"),
        kind=IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
    ).exclude(
        state=IgLifecycleEvent.State.CANCELLED,
        last_error__in=RECOVERABLE_CANCELLATION_REASONS,
    )
    ttn_event_exists = IgLifecycleEvent.objects.filter(
        proposal_id=OuterRef("pk"),
        kind=IgLifecycleEvent.Kind.TTN_CREATED,
    ).exclude(
        state=IgLifecycleEvent.State.CANCELLED,
        last_error__in=RECOVERABLE_CANCELLATION_REASONS,
    )
    delivery_event_exists = IgLifecycleEvent.objects.filter(
        proposal_id=OuterRef("pk"),
        kind=IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
    ).exclude(
        state=IgLifecycleEvent.State.CANCELLED,
        last_error__in=RECOVERABLE_CANCELLATION_REASONS,
    )
    proposals = list(
        IgCheckoutProposal.objects.select_related(
            "payment_attempt", "payment_attempt__order", "deal", "client"
        )
        .filter(payment_attempt__isnull=False)
        .annotate(
            has_payment_event=Exists(payment_event_exists),
            has_ttn_event=Exists(ttn_event_exists),
            has_delivery_event=Exists(delivery_event_exists),
        )
        .filter(
            Q(
                payment_attempt__order_id__isnull=False,
                status__in=[
                    IgCheckoutProposal.Status.DETAILS_LOCKED,
                    IgCheckoutProposal.Status.INVOICE_CREATED,
                ],
            )
            | Q(
                payment_attempt__order_id__isnull=False,
                status=IgCheckoutProposal.Status.PAID,
                has_payment_event=False,
            )
            | Q(
                payment_attempt__event_state__promo_consumption_pending=True,
            )
            | (
                Q(
                    payment_attempt__order_id__isnull=False,
                    status=IgCheckoutProposal.Status.PAID,
                )
                & (
                    (
                        Q(has_ttn_event=False)
                        & Q(payment_attempt__order__tracking_number__isnull=False)
                        & ~Q(payment_attempt__order__tracking_number="")
                    )
                    | Q(
                        has_delivery_event=False,
                        payment_attempt__order__status="done",
                        payment_attempt__order__tracking_status_code__in=NOVA_POSHTA_DELIVERY_SUCCESS_CODES,
                        payment_attempt__order__tracking_terminal_at__isnull=False,
                    )
                )
            )
            | Q(payment_attempt__event_state__invoice_creation_ambiguous=True)
        )
        # Repairable rows must be considered before permanent ambiguity. A
        # bounded worker should not let an old provider-timeout row starve a
        # paid order whose Instagram linkage can be completed immediately.
        .order_by(
            Case(
                When(
                    payment_attempt__event_state__invoice_creation_ambiguous=True,
                    then=1,
                ),
                default=0,
                output_field=IntegerField(),
            ),
            "updated_at",
            "pk",
        )[:limit]
    )
    for proposal in proposals:
        attempt = proposal.payment_attempt
        try:
            ambiguous = bool(
                attempt
                and (attempt.event_state or {}).get("invoice_creation_ambiguous")
            )
            if dry_run:
                if ambiguous:
                    result["ambiguous_pending"] += 1
                order = attempt.order if attempt and attempt.order_id else None
                if proposal.status == proposal.Status.PAID and order is not None:
                    if (
                        str(order.tracking_number or "").strip()
                        and not proposal.has_ttn_event
                    ):
                        result["ttn_events"] += 1
                    if (
                        nova_poshta_order_fulfillment_confirmed(order)
                        and not proposal.has_delivery_event
                    ):
                        result["delivery_events"] += 1
                continue
            promo_consumption_pending = bool(
                (attempt.event_state or {}).get("promo_consumption_pending")
            )
            if (
                pull_ambiguous
                and (ambiguous or promo_consumption_pending)
                and attempt.monobank_invoice_id
            ):
                if ambiguous:
                    result["ambiguous_checked"] += 1
                from storefront.views.monobank import _apply_payment_attempt_status, _resolve_attempt_invoice_status

                status, payload = _resolve_attempt_invoice_status(attempt, attempt.monobank_invoice_id)
                if status:
                    _apply_payment_attempt_status(attempt, status, payload=payload, source="ig_reconcile")
                    attempt.refresh_from_db()
                    proposal.refresh_from_db()
            elif ambiguous:
                # A timeout before the response may leave no provider invoice
                # id. It is unsafe to create a second invoice automatically.
                result["ambiguous_pending"] += 1

            if attempt.order_id and proposal.status != proposal.Status.PAID:
                from management.services.ig_checkout_payment import bind_verified_payment

                bind_verified_payment(attempt.pk, attempt.order)
                result["bound_attempts"] += 1
                proposal.refresh_from_db()

            if proposal.status == proposal.Status.PAID and attempt.order_id:
                from management.services.ig_lifecycle import ensure_lifecycle_event

                order = attempt.order
                event, created = ensure_lifecycle_event(
                    order,
                    IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
                    payload={
                        "attempt_id": attempt.pk,
                        "attempt_reference": attempt.reference,
                        "amount": str(attempt.paid_amount or attempt.payment_amount),
                        "currency": proposal.currency,
                    },
                )
                if event is None:
                    result["missing_attribution"] += 1
                elif created:
                    result["payment_events"] += 1

                tracking_number = str(order.tracking_number or "").strip()
                if tracking_number and not proposal.has_ttn_event:
                    event, created = ensure_lifecycle_event(
                        order,
                        IgLifecycleEvent.Kind.TTN_CREATED,
                        payload={
                            "tracking_number": tracking_number,
                            "order_number": order.order_number,
                        },
                    )
                    if event is None:
                        result["missing_attribution"] += 1
                    elif created:
                        result["ttn_events"] += 1

                if (
                    nova_poshta_order_fulfillment_confirmed(order)
                    and not proposal.has_delivery_event
                ):
                    event, created = ensure_lifecycle_event(
                        order,
                        IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
                        payload={
                            "status_code": str(order.tracking_status_code),
                            "status": str(
                                order.shipment_status or ""
                            )[:300],
                            "tracking_number": str(order.tracking_number or ""),
                            "tracking_terminal_at": order.tracking_terminal_at.isoformat(),
                        },
                    )
                    if event is None:
                        result["missing_attribution"] += 1
                    elif created:
                        result["delivery_events"] += 1
        except Exception:
            result["errors"] += 1
    return result
