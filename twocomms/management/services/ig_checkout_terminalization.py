"""Atomic local terminalization for assisted checkout payment attempts.

Local expiry and a customer checkout-session reset are operational facts. They
must release scarce local reservations, but they are not provider payment
evidence. A later signed/pulled Monobank success therefore remains stronger and
is still handled by the existing payment materializer and late-stock review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from management.models import IgCheckoutProposal
from management.services.ig_checkout_payment import project_terminal_payment
from management.services.ig_inventory import release_attempt_inventory
from orders.models import PaymentAttempt
from orders.promo_reservations import release_payment_attempt_promo


logger = logging.getLogger("management.ig_checkout_terminalization")

LEGACY_NULL_EXPIRY_AGE = timedelta(hours=24)
ACTIVE_ATTEMPT_STATUSES = frozenset(
    {
        PaymentAttempt.Status.INITIATED,
        PaymentAttempt.Status.PROCESSING,
    }
)
LOCAL_TERMINAL_SOURCES = frozenset(
    {
        "system_expiry",
        "checkout_session_reset",
    }
)
LOCAL_TERMINAL_STATUSES = frozenset(
    {
        PaymentAttempt.Status.EXPIRED,
        PaymentAttempt.Status.CANCELLED,
    }
)


@dataclass(frozen=True)
class AttemptTerminalizationResult:
    attempt_id: int
    outcome: str
    terminal_status: str = ""
    released_inventory: int = 0
    released_promo: bool = False
    payment_event_id: int | None = None


def _attempt_is_due(attempt, *, now, legacy_null_expiry_age) -> bool:
    if attempt.invoice_expires_at is not None:
        return attempt.invoice_expires_at <= now
    return attempt.created <= now - legacy_null_expiry_age


@transaction.atomic
def terminalize_payment_attempt(
    attempt_id: int,
    *,
    terminal_status: str,
    reason: str,
    source: str,
    now=None,
    require_due: bool = False,
    legacy_null_expiry_age: timedelta = LEGACY_NULL_EXPIRY_AGE,
) -> AttemptTerminalizationResult:
    """Apply one local terminal transition and release reservations atomically.

    The PaymentAttempt row is the first lock for every path. Existing release
    helpers re-lock the same row in nested savepoints and then lock their own
    reservation rows, preserving the established MariaDB lock order.
    """

    now = now or timezone.now()
    terminal_status = str(terminal_status or "").strip()
    source = str(source or "").strip()
    reason = str(reason or terminal_status or "payment_terminal")[:128]
    if terminal_status not in LOCAL_TERMINAL_STATUSES:
        raise ValueError("unsupported local payment-attempt terminal status")
    if source not in LOCAL_TERMINAL_SOURCES:
        raise ValueError("unsupported local payment-attempt terminal source")
    if legacy_null_expiry_age <= timedelta(0):
        raise ValueError("legacy null-expiry age must be positive")

    attempt = (
        PaymentAttempt.objects.select_for_update()
        .select_related("order")
        .get(pk=attempt_id)
    )
    if attempt.order_id or attempt.status in {
        PaymentAttempt.Status.PAID,
        PaymentAttempt.Status.PREPAID,
        PaymentAttempt.Status.CONVERTED,
    }:
        return AttemptTerminalizationResult(attempt.pk, "protected_payment")
    if attempt.status not in ACTIVE_ATTEMPT_STATUSES:
        return AttemptTerminalizationResult(
            attempt.pk,
            "already_terminal",
            terminal_status=attempt.status,
        )
    if (attempt.event_state or {}).get("invoice_creation_ambiguous"):
        return AttemptTerminalizationResult(attempt.pk, "provider_ambiguous")
    if require_due and not _attempt_is_due(
        attempt,
        now=now,
        legacy_null_expiry_age=legacy_null_expiry_age,
    ):
        return AttemptTerminalizationResult(attempt.pk, "not_due")

    proposal_id = (
        IgCheckoutProposal.objects.filter(payment_attempt_id=attempt.pk)
        .values_list("pk", flat=True)
        .first()
    )
    snapshot = attempt.cart_snapshot if isinstance(attempt.cart_snapshot, dict) else {}
    is_assisted = bool(
        proposal_id or snapshot.get("checkout_surface") == "instagram_proposal"
    )

    event_state = dict(attempt.event_state or {})
    event_state["terminalization"] = {
        "version": 1,
        "status": terminal_status,
        "reason": reason,
        "source": source,
        "observed_at": now.isoformat(),
    }
    attempt.status = terminal_status
    attempt.error_reason = reason[:500]
    attempt.last_status_at = now
    attempt.event_state = event_state
    attempt.save(
        update_fields=[
            "status",
            "error_reason",
            "last_status_at",
            "event_state",
            "updated",
        ]
    )

    payment_event = None
    if proposal_id:
        payment_event = project_terminal_payment(
            attempt.pk,
            status=terminal_status,
            payload={
                "reason": reason,
                "boundary": "local_terminalization_v1",
            },
            source=source,
        )
    released_inventory = (
        int(release_attempt_inventory(attempt, reason=reason) or 0)
        if is_assisted
        else 0
    )
    released_promo = bool(release_payment_attempt_promo(attempt, reason=reason))
    return AttemptTerminalizationResult(
        attempt.pk,
        "terminalized",
        terminal_status=terminal_status,
        released_inventory=released_inventory,
        released_promo=released_promo,
        payment_event_id=getattr(payment_event, "pk", None),
    )


def expire_due_assisted_attempts(
    *,
    now=None,
    limit: int = 100,
    dry_run: bool = False,
    legacy_null_expiry_age: timedelta = LEGACY_NULL_EXPIRY_AGE,
) -> dict[str, int]:
    """Expire a bounded batch owned by the existing checkout reconciler.

    Explicit invoice deadlines are due immediately. Only historical rows with a
    NULL deadline use the 24-hour age fallback. Provider-ambiguous attempts are
    intentionally left for reconciliation/manager review.
    """

    now = now or timezone.now()
    limit = max(1, min(int(limit), 500))
    if legacy_null_expiry_age <= timedelta(0):
        raise ValueError("legacy null-expiry age must be positive")
    legacy_cutoff = now - legacy_null_expiry_age
    candidate_ids = list(
        PaymentAttempt.objects.filter(
            instagram_checkout_proposal__isnull=False,
            order__isnull=True,
            status__in=ACTIVE_ATTEMPT_STATUSES,
        )
        # JSON missing-key semantics differ between SQLite and MariaDB. Make
        # the allowed states explicit instead of relying on ``NOT key=true``.
        .filter(
            Q(event_state__invoice_creation_ambiguous__isnull=True)
            | Q(event_state__invoice_creation_ambiguous=False)
        )
        .filter(
            Q(invoice_expires_at__lte=now)
            | Q(invoice_expires_at__isnull=True, created__lte=legacy_cutoff)
        )
        .order_by("invoice_expires_at", "created", "pk")
        .values_list("pk", flat=True)[:limit]
    )
    result = {
        "due_attempts": len(candidate_ids),
        "expired_attempts": len(candidate_ids) if dry_run else 0,
        "released_inventory": 0,
        "released_promos": 0,
        "skipped_attempts": 0,
        "errors": 0,
    }
    if dry_run:
        return result

    for attempt_id in candidate_ids:
        try:
            outcome = terminalize_payment_attempt(
                attempt_id,
                terminal_status=PaymentAttempt.Status.EXPIRED,
                reason="invoice_expired",
                source="system_expiry",
                now=now,
                require_due=True,
                legacy_null_expiry_age=legacy_null_expiry_age,
            )
        except Exception:
            result["errors"] += 1
            logger.exception(
                "Failed to terminalize due assisted payment attempt %s",
                attempt_id,
            )
            continue
        if outcome.outcome != "terminalized":
            result["skipped_attempts"] += 1
            continue
        result["expired_attempts"] += 1
        result["released_inventory"] += outcome.released_inventory
        result["released_promos"] += int(outcome.released_promo)
    return result
