"""Atomic local terminalization for assisted checkout payment attempts.

Local expiry and a checkout-session reset are operational facts. They release
scarce local reservations and retire the customer-visible proposal, but never
mutate provider payment truth. While assisted invoices omit provider validity,
a bounded status backstop checks for a missed webhook after local expiry.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import DatabaseError, transaction
from django.db.models import Case, IntegerField, Q, When
from django.utils import timezone

from management.services.ig_checkout_payment import _lock_attempt_proposal_graph
from management.services.ig_inventory import release_attempt_inventory
from orders.models import PaymentAttempt
from orders.promo_reservations import release_payment_attempt_promo


logger = logging.getLogger("management.ig_checkout_terminalization")

LEGACY_NULL_EXPIRY_AGE = timedelta(hours=24)
LOCAL_PROVIDER_CHECK_WINDOW = timedelta(hours=24)
LOCAL_PROVIDER_CHECK_INTERVAL = timedelta(minutes=15)
MAX_DEADLOCK_RETRIES = 3
ACTIVE_ATTEMPT_STATUSES = frozenset(
    {PaymentAttempt.Status.INITIATED, PaymentAttempt.Status.PROCESSING}
)
LOCAL_TERMINAL_SOURCES = frozenset(
    {"system_expiry", "checkout_session_reset"}
)
LOCAL_TERMINAL_STATUSES = frozenset(
    {PaymentAttempt.Status.EXPIRED, PaymentAttempt.Status.CANCELLED}
)
SAFE_BROWSER_CLEAR_OUTCOMES = frozenset(
    {"terminalized", "already_terminal", "protected_payment"}
)


@dataclass(frozen=True)
class AttemptTerminalizationResult:
    attempt_id: int
    outcome: str
    terminal_status: str = ""
    released_inventory: int = 0
    released_promo: bool = False
    operational_event_key: str = ""


def _attempt_is_due(attempt, *, now, legacy_null_expiry_age) -> bool:
    if attempt.invoice_expires_at is not None:
        return attempt.invoice_expires_at <= now
    return attempt.created <= now - legacy_null_expiry_age


def _provider_validity_declared(attempt) -> bool:
    envelope = attempt.invoice_payload if isinstance(attempt.invoice_payload, dict) else {}
    request_payload = envelope.get("request")
    return bool(
        isinstance(request_payload, dict)
        and request_payload.get("validity") not in (None, "", 0, "0")
    )


def _is_retryable_mariadb_lock_error(exc: BaseException) -> bool:
    values = getattr(exc, "args", ()) or ()
    code = values[0] if values else None
    text = " ".join(str(value) for value in values).casefold()
    return code in {1205, 1213} or "deadlock" in text or "lock wait timeout" in text


def _parse_timestamp(value, *, fallback):
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except (TypeError, ValueError):
        return fallback
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@transaction.atomic
def _terminalize_payment_attempt_once(
    attempt_id: int,
    *,
    terminal_status: str,
    reason: str,
    source: str,
    now,
    require_due: bool,
    legacy_null_expiry_age: timedelta,
) -> AttemptTerminalizationResult:
    # Canonical graph order: Deal -> Proposal -> PaymentAttempt. A typed orphan
    # has no graph and therefore locks only its PaymentAttempt row.
    attempt, deal, proposal = _lock_attempt_proposal_graph(attempt_id)
    if attempt.order_id or attempt.status in {
        PaymentAttempt.Status.PAID,
        PaymentAttempt.Status.PREPAID,
        PaymentAttempt.Status.CONVERTED,
    }:
        return AttemptTerminalizationResult(attempt.pk, "protected_payment")
    if attempt.status not in ACTIVE_ATTEMPT_STATUSES:
        return AttemptTerminalizationResult(
            attempt.pk, "already_terminal", terminal_status=attempt.status
        )
    if (attempt.event_state or {}).get("invoice_creation_ambiguous"):
        return AttemptTerminalizationResult(attempt.pk, "provider_ambiguous")
    if require_due and not _attempt_is_due(
        attempt, now=now, legacy_null_expiry_age=legacy_null_expiry_age
    ):
        return AttemptTerminalizationResult(attempt.pk, "not_due")

    snapshot = attempt.cart_snapshot if isinstance(attempt.cart_snapshot, dict) else {}
    is_assisted = bool(
        proposal is not None
        or snapshot.get("checkout_surface") == "instagram_proposal"
    )
    event_key = (
        f"attempt:{attempt.pk}:local:{source}:{terminal_status}:"
        f"{int(now.timestamp())}"
    )[:180]
    needs_provider_backstop = bool(
        is_assisted
        and attempt.monobank_invoice_id
        and not _provider_validity_declared(attempt)
    )
    local_event = {
        "version": 2,
        "event_key": event_key,
        "status": terminal_status,
        "reason": reason,
        "source": source,
        "observed_at": now.isoformat(),
        "provider_truth_changed": False,
        "provider_check_state": "pending" if needs_provider_backstop else "not_required",
        "provider_check_attempts": 0,
        "provider_next_check_at": now.isoformat() if needs_provider_backstop else None,
        "provider_check_until": (
            (now + LOCAL_PROVIDER_CHECK_WINDOW).isoformat()
            if needs_provider_backstop
            else None
        ),
    }
    event_state = dict(attempt.event_state or {})
    history = list(event_state.get("local_terminalization_events") or [])
    history.append(local_event)
    event_state["local_terminalization_events"] = history[-8:]
    event_state["local_terminalization"] = local_event
    event_state.pop("terminalization", None)
    attempt.status = terminal_status
    attempt.error_reason = reason[:500]
    attempt.last_status_at = now
    attempt.event_state = event_state
    attempt.save(
        update_fields=[
            "status", "error_reason", "last_status_at", "event_state", "updated"
        ]
    )

    if proposal is not None:
        from management.models import IgCheckoutProposal

        proposal.status = (
            IgCheckoutProposal.Status.EXPIRED
            if terminal_status == PaymentAttempt.Status.EXPIRED
            else IgCheckoutProposal.Status.CANCELLED
        )
        proposal.save(update_fields=["status", "updated_at"])
        if deal is not None and deal.active_checkout_proposal_id == proposal.pk:
            deal.active_checkout_proposal = None
            deal.save(update_fields=["active_checkout_proposal", "updated_at"])

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
        operational_event_key=event_key,
    )


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
    """Apply one local transition with bounded MariaDB deadlock retry."""

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

    for retry_index in range(MAX_DEADLOCK_RETRIES):
        try:
            return _terminalize_payment_attempt_once(
                attempt_id,
                terminal_status=terminal_status,
                reason=reason,
                source=source,
                now=now,
                require_due=require_due,
                legacy_null_expiry_age=legacy_null_expiry_age,
            )
        except DatabaseError as exc:
            if (
                not _is_retryable_mariadb_lock_error(exc)
                or retry_index + 1 >= MAX_DEADLOCK_RETRIES
            ):
                raise
            time.sleep(0.01 * (2**retry_index))
    raise RuntimeError("unreachable terminalization retry state")


@transaction.atomic
def record_local_provider_check(attempt_id: int, *, status: str = "", now=None):
    """Advance the bounded missed-webhook backstop without changing truth."""

    now = now or timezone.now()
    attempt, _deal, proposal = _lock_attempt_proposal_graph(attempt_id)
    event_state = dict(attempt.event_state or {})
    local = dict(event_state.get("local_terminalization") or {})
    if not local or local.get("provider_check_state") not in {"pending", "checking"}:
        return "not_local_pending"
    check_until = _parse_timestamp(local.get("provider_check_until"), fallback=now)
    local["provider_check_attempts"] = int(local.get("provider_check_attempts") or 0) + 1
    local["provider_last_check_at"] = now.isoformat()
    local["provider_last_status"] = str(status or "")[:32]
    if now >= check_until:
        local["provider_check_state"] = "exhausted"
        local["provider_next_check_at"] = None
    elif status in {
        "success", "failure", "rejected", "cancelled", "canceled", "expired", "reversed"
    }:
        local["provider_check_state"] = "resolved"
        local["provider_next_check_at"] = None
    else:
        local["provider_check_state"] = "pending"
        local["provider_next_check_at"] = (
            now + LOCAL_PROVIDER_CHECK_INTERVAL
        ).isoformat()
    event_state["local_terminalization"] = local
    history = list(event_state.get("local_terminalization_events") or [])
    if history and history[-1].get("event_key") == local.get("event_key"):
        history[-1] = local
        event_state["local_terminalization_events"] = history[-8:]
    attempt.event_state = event_state
    attempt.save(update_fields=["event_state", "updated"])
    if local["provider_check_state"] == "exhausted":
        from management.models import IgFollowUpTask

        if proposal is not None:
            IgFollowUpTask.objects.get_or_create(
                event_key=f"local-invoice-status-review:{attempt.pk}",
                defaults={
                    "client": proposal.client,
                    "deal": proposal.deal,
                    "due_at": now,
                    "status": IgFollowUpTask.Status.SKIPPED,
                    "kind": IgFollowUpTask.Kind.MANAGER_TASK,
                    "reason": "local_invoice_status_review",
                    "trigger": IgFollowUpTask.Trigger.EVENT,
                    "event_occurred_at": now,
                    "event_payload": {
                        "proposal_id": proposal.pk,
                        "attempt_id": attempt.pk,
                    },
                    "skip_reason": "human_agent_required",
                    "message_text": (
                        "Не вдалося підтвердити фінальний статус локально "
                        "закритого IG invoice протягом 24 годин."
                    ),
                },
            )
    return local["provider_check_state"]


def expire_due_assisted_attempts(
    *,
    now=None,
    limit: int = 100,
    dry_run: bool = False,
    legacy_null_expiry_age: timedelta = LEGACY_NULL_EXPIRY_AGE,
) -> dict[str, int]:
    """Expire a bounded batch owned by the existing checkout reconciler."""

    now = now or timezone.now()
    limit = max(1, min(int(limit), 500))
    if legacy_null_expiry_age <= timedelta(0):
        raise ValueError("legacy null-expiry age must be positive")
    legacy_cutoff = now - legacy_null_expiry_age
    candidate_ids = list(
        PaymentAttempt.objects.filter(
            Q(instagram_checkout_proposal__isnull=False)
            | Q(cart_snapshot__checkout_surface="instagram_proposal"),
            order__isnull=True,
            status__in=ACTIVE_ATTEMPT_STATUSES,
        )
        .filter(
            Q(event_state__invoice_creation_ambiguous__isnull=True)
            | Q(event_state__invoice_creation_ambiguous=False)
        )
        .filter(
            Q(invoice_expires_at__lte=now)
            | Q(invoice_expires_at__isnull=True, created__lte=legacy_cutoff)
        )
        .annotate(
            expiry_priority=Case(
                When(invoice_expires_at__isnull=False, then=0),
                default=1,
                output_field=IntegerField(),
            )
        )
        .order_by("expiry_priority", "invoice_expires_at", "created", "pk")
        .values_list("pk", flat=True)
        .distinct()[:limit]
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
                "Failed to terminalize due assisted payment attempt %s", attempt_id
            )
            continue
        if outcome.outcome != "terminalized":
            result["skipped_attempts"] += 1
            continue
        result["expired_attempts"] += 1
        result["released_inventory"] += outcome.released_inventory
        result["released_promos"] += int(outcome.released_promo)
    return result
