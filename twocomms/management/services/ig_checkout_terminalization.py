"""Atomic local terminalization for assisted checkout payment attempts.

Local expiry and a checkout-session reset are operational facts. They release
scarce local reservations and retire the customer-visible proposal, but never
mutate provider payment truth. While assisted invoices omit provider validity,
a bounded status backstop checks for a missed webhook after local expiry.
"""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

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
LOCAL_PROVIDER_CHECK_LEASE = timedelta(minutes=2)
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
    from management.services.ig_checkout_generation import (
        generation_for_attempt,
        terminalize_generation_attempt,
    )

    if generation_for_attempt(attempt_id) is not None:
        outcome = terminalize_generation_attempt(
            attempt_id,
            terminal_status=terminal_status,
            reason=reason,
            now=now,
            require_due=require_due,
        )
        return AttemptTerminalizationResult(
            attempt_id,
            str((outcome or {}).get("outcome") or "not_found"),
            terminal_status=(
                terminal_status
                if (outcome or {}).get("outcome") == "terminalized"
                else ""
            ),
            released_inventory=int(
                (outcome or {}).get("released_inventory") or 0
            ),
            released_promo=bool((outcome or {}).get("released_promo")),
        )
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
    attempt.provider_recheck_state = (
        PaymentAttempt.ProviderRecheckState.PENDING
        if needs_provider_backstop
        else PaymentAttempt.ProviderRecheckState.NONE
    )
    attempt.provider_recheck_next_at = now if needs_provider_backstop else None
    attempt.provider_recheck_until = (
        now + LOCAL_PROVIDER_CHECK_WINDOW if needs_provider_backstop else None
    )
    attempt.provider_recheck_claim_token = ""
    attempt.provider_recheck_claim_until = None
    attempt.provider_recheck_attempts = 0
    attempt.provider_recheck_last_status = ""
    attempt.save(
        update_fields=[
            "status", "error_reason", "last_status_at", "event_state",
            "provider_recheck_state", "provider_recheck_next_at",
            "provider_recheck_until", "provider_recheck_claim_token",
            "provider_recheck_claim_until", "provider_recheck_attempts",
            "provider_recheck_last_status", "updated",
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


def _sync_local_recheck_json(attempt, *, now):
    event_state = dict(attempt.event_state or {})
    local = dict(event_state.get("local_terminalization") or {})
    if not local:
        return event_state
    local.update(
        {
            "provider_check_state": attempt.provider_recheck_state,
            "provider_check_attempts": int(attempt.provider_recheck_attempts or 0),
            "provider_last_status": attempt.provider_recheck_last_status,
            "provider_last_check_at": now.isoformat(),
            "provider_next_check_at": (
                attempt.provider_recheck_next_at.isoformat()
                if attempt.provider_recheck_next_at
                else None
            ),
            "provider_check_until": (
                attempt.provider_recheck_until.isoformat()
                if attempt.provider_recheck_until
                else None
            ),
        }
    )
    event_state["local_terminalization"] = local
    history = list(event_state.get("local_terminalization_events") or [])
    if history and history[-1].get("event_key") == local.get("event_key"):
        history[-1] = local
        event_state["local_terminalization_events"] = history[-8:]
    return event_state


@transaction.atomic
def _claim_provider_recheck(attempt_id: int, *, now):
    attempt, _deal, proposal = _lock_attempt_proposal_graph(attempt_id)
    is_due = bool(
        (
            attempt.provider_recheck_state
            == PaymentAttempt.ProviderRecheckState.PENDING
            and attempt.provider_recheck_next_at
            and attempt.provider_recheck_next_at <= now
        )
        or (
            attempt.provider_recheck_state
            == PaymentAttempt.ProviderRecheckState.CHECKING
            and attempt.provider_recheck_claim_until
            and attempt.provider_recheck_claim_until <= now
        )
    )
    if not is_due:
        return None
    if attempt.provider_recheck_until and attempt.provider_recheck_until <= now:
        attempt.provider_recheck_state = PaymentAttempt.ProviderRecheckState.EXHAUSTED
        attempt.provider_recheck_next_at = None
        attempt.provider_recheck_claim_token = ""
        attempt.provider_recheck_claim_until = None
        attempt.event_state = _sync_local_recheck_json(attempt, now=now)
        attempt.save(
            update_fields=[
                "provider_recheck_state", "provider_recheck_next_at",
                "provider_recheck_claim_token", "provider_recheck_claim_until",
                "event_state", "updated",
            ]
        )
        _create_exhausted_review(attempt, now=now, proposal=proposal)
        return attempt, ""
    token = secrets.token_hex(24)
    attempt.provider_recheck_state = PaymentAttempt.ProviderRecheckState.CHECKING
    attempt.provider_recheck_claim_token = token
    attempt.provider_recheck_claim_until = now + LOCAL_PROVIDER_CHECK_LEASE
    attempt.provider_recheck_attempts = int(attempt.provider_recheck_attempts or 0) + 1
    attempt.event_state = _sync_local_recheck_json(attempt, now=now)
    attempt.save(
        update_fields=[
            "provider_recheck_state", "provider_recheck_claim_token",
            "provider_recheck_claim_until", "provider_recheck_attempts",
            "event_state", "updated",
        ]
    )
    return attempt, token


def _create_exhausted_review(attempt, *, now, proposal=None):
    from management.models import IgBotNotification, IgCheckoutProposal, IgFollowUpTask

    if proposal is None:
        proposal = (
            IgCheckoutProposal.objects.select_related("client", "deal")
            .filter(payment_attempt_id=attempt.pk)
            .first()
        )
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
                "event_payload": {"proposal_id": proposal.pk, "attempt_id": attempt.pk},
                "skip_reason": "human_agent_required",
                "message_text": (
                    "Не вдалося підтвердити фінальний статус локально "
                    "закритого IG invoice протягом 24 годин."
                ),
            },
        )
        return
    event_state = dict(attempt.event_state or {})
    recovered = _recover_orphan_context(attempt)
    marker = {
        "version": 1,
        "reason": "provider_recheck_exhausted",
        "attempt_id": attempt.pk,
        "observed_at": now.isoformat(),
    }
    event_state["orphan_provider_review"] = marker
    notification, _created = IgBotNotification.objects.get_or_create(
        dedupe_key=f"orphan-provider-recheck-exhausted:{attempt.pk}",
        defaults={
            "client": recovered["client"],
            "event_type": "orphan_provider_recheck_exhausted",
            "payload": {
                "text": (
                    "⚠️ IG payment attempt без proposal: статус invoice не "
                    "підтверджено за 24 години. Потрібна ручна звірка."
                ),
                "chat_id": "",
                "attempt_id": attempt.pk,
                "proposal_id": getattr(recovered["proposal"], "pk", None),
                "deal_id": getattr(recovered["deal"], "pk", None),
                "attempt_reference": attempt.reference,
                "invoice_id": attempt.monobank_invoice_id,
                "payment_amount": str(attempt.payment_amount),
                "requires_human_review": True,
            },
            "status": IgBotNotification.Status.PENDING,
            "next_attempt_at": now,
        },
    )
    marker["notification_id"] = notification.pk
    event_state["orphan_provider_review"] = marker
    PaymentAttempt.objects.filter(pk=attempt.pk).update(event_state=event_state)


def _recover_orphan_context(attempt):
    """Recover exact context only from sanitized typed snapshot identifiers."""

    from management.models import IgCheckoutProposal

    snapshot = attempt.cart_snapshot if isinstance(attempt.cart_snapshot, dict) else {}
    proposal_id = str(snapshot.get("proposal_id") or "").strip()
    if not proposal_id:
        return {"client": None, "proposal": None, "deal": None}
    try:
        proposal = IgCheckoutProposal.objects.select_related("client", "deal").filter(
            public_id=proposal_id
        ).first()
    except (TypeError, ValueError):
        proposal = None
    return {
        "client": proposal.client if proposal is not None else None,
        "proposal": proposal,
        "deal": proposal.deal if proposal is not None else None,
    }
@transaction.atomic
def _finish_provider_recheck(
    attempt_id: int,
    *,
    token: str,
    now,
    status: str,
    resolved: bool,
):
    attempt, _deal, proposal = _lock_attempt_proposal_graph(attempt_id)
    if (
        attempt.provider_recheck_state
        != PaymentAttempt.ProviderRecheckState.CHECKING
        or attempt.provider_recheck_claim_token != token
    ):
        return "lease_lost"
    attempt.provider_recheck_last_status = str(status or "")[:32]
    attempt.provider_recheck_claim_token = ""
    attempt.provider_recheck_claim_until = None
    exhausted = bool(
        attempt.provider_recheck_until
        and now >= attempt.provider_recheck_until
    )
    if resolved:
        attempt.provider_recheck_state = PaymentAttempt.ProviderRecheckState.RESOLVED
        attempt.provider_recheck_next_at = None
    elif exhausted:
        attempt.provider_recheck_state = PaymentAttempt.ProviderRecheckState.EXHAUSTED
        attempt.provider_recheck_next_at = None
    else:
        attempt.provider_recheck_state = PaymentAttempt.ProviderRecheckState.PENDING
        next_at = now + LOCAL_PROVIDER_CHECK_INTERVAL
        attempt.provider_recheck_next_at = min(
            next_at,
            attempt.provider_recheck_until or next_at,
        )
    attempt.event_state = _sync_local_recheck_json(attempt, now=now)
    attempt.save(
        update_fields=[
            "provider_recheck_state", "provider_recheck_next_at",
            "provider_recheck_claim_token", "provider_recheck_claim_until",
            "provider_recheck_last_status", "event_state", "updated",
        ]
    )
    if attempt.provider_recheck_state == PaymentAttempt.ProviderRecheckState.EXHAUSTED:
        _create_exhausted_review(attempt, now=now, proposal=proposal)
    return attempt.provider_recheck_state


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
            | Q(instagram_checkout_generation__isnull=False)
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


@transaction.atomic
def record_orphan_provider_observation(
    attempt_id: int,
    *,
    status: str,
    payload=None,
    source="ig_reconcile",
):
    """Persist provider truth for a typed orphan without creating an Order."""

    from management.services.ig_checkout_payment import _paid_amount_from_provider_payload
    from management.models import IgBotNotification

    attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
    normalized = str(status or "").strip().lower()
    now = timezone.now()
    event_state = dict(attempt.event_state or {})
    event_state["orphan_provider_review"] = {
        "version": 1,
        "reason": "typed_orphan_provider_observation",
        "attempt_id": attempt.pk,
        "provider_status": normalized,
        "observed_at": now.isoformat(),
        "requires_human_review": True,
    }
    history = list(attempt.payment_history or [])
    history.append(
        {
            "ts": now.isoformat(),
            "status": normalized,
            "source": str(source or "ig_reconcile")[:32],
            "payload": {"invoiceId": attempt.monobank_invoice_id},
        }
    )
    attempt.payment_history = history[-30:]
    if normalized == "success":
        paid_amount = _paid_amount_from_provider_payload(attempt, payload)
        attempt.status = (
            PaymentAttempt.Status.PREPAID
            if attempt.pay_type in {
                PaymentAttempt.PayType.PREPAYMENT,
                PaymentAttempt.PayType.PREPAY_200,
            }
            else PaymentAttempt.Status.PAID
        )
        attempt.paid_amount = paid_amount
        attempt.error_reason = "typed_orphan_payment_review"
    else:
        attempt.status = {
            "failure": PaymentAttempt.Status.FAILED,
            "rejected": PaymentAttempt.Status.FAILED,
            "reversed": PaymentAttempt.Status.FAILED,
            "cancelled": PaymentAttempt.Status.CANCELLED,
            "canceled": PaymentAttempt.Status.CANCELLED,
            "expired": PaymentAttempt.Status.EXPIRED,
        }.get(normalized, attempt.status)
        attempt.error_reason = f"provider_{normalized or 'unknown'}"[:500]
        paid_amount = Decimal(attempt.paid_amount or 0)
    recovered = _recover_orphan_context(attempt)
    notification, _created = IgBotNotification.objects.get_or_create(
        dedupe_key=f"orphan-provider-payment-review:{attempt.pk}:{normalized}",
        defaults={
            "client": recovered["client"],
            "event_type": "orphan_provider_payment_review",
            "payload": {
                "text": (
                    "⚠️ IG payment attempt без активного proposal отримав "
                    f"provider status {normalized or 'unknown'}. Потрібна звірка."
                ),
                "chat_id": "",
                "attempt_id": attempt.pk,
                "proposal_id": getattr(recovered["proposal"], "pk", None),
                "deal_id": getattr(recovered["deal"], "pk", None),
                "attempt_reference": attempt.reference,
                "invoice_id": attempt.monobank_invoice_id,
                "provider_status": normalized,
                "paid_amount": str(paid_amount),
                "requires_human_review": True,
            },
            "status": IgBotNotification.Status.PENDING,
            "next_attempt_at": now,
        },
    )
    event_state["orphan_provider_review"]["notification_id"] = notification.pk
    attempt.last_status_at = now
    attempt.event_state = event_state
    provider_update_fields = []
    if not (
        attempt.provider_recheck_state
        == PaymentAttempt.ProviderRecheckState.CHECKING
        and attempt.provider_recheck_claim_token
    ):
        attempt.provider_recheck_state = PaymentAttempt.ProviderRecheckState.RESOLVED
        attempt.provider_recheck_next_at = None
        attempt.provider_recheck_claim_token = ""
        attempt.provider_recheck_claim_until = None
        attempt.provider_recheck_last_status = normalized[:32]
        provider_update_fields = [
            "provider_recheck_state", "provider_recheck_next_at",
            "provider_recheck_claim_token", "provider_recheck_claim_until",
            "provider_recheck_last_status",
        ]
    attempt.save(
        update_fields=[
            "status", "paid_amount", "error_reason", "last_status_at",
            "event_state", "payment_history", *provider_update_fields, "updated",
        ]
    )


def _provider_apply_is_durable(attempt_id: int, *, status: str, has_proposal: bool):
    attempt = PaymentAttempt.objects.filter(pk=attempt_id).first()
    if attempt is None:
        return False
    normalized = str(status or "").strip().lower()
    if not has_proposal:
        from management.models import IgBotNotification

        marker = dict((attempt.event_state or {}).get("orphan_provider_review") or {})
        notification_id = marker.get("notification_id")
        return bool(
            marker.get("provider_status") == normalized
            and notification_id
            and IgBotNotification.objects.filter(
                pk=notification_id,
                dedupe_key=f"orphan-provider-payment-review:{attempt.pk}:{normalized}",
                event_type="orphan_provider_payment_review",
            ).exists()
        )
    from management.models import IgPaymentEvent

    if normalized == "success":
        return bool(
            attempt.order_id
            or (
                attempt.status in {
                    PaymentAttempt.Status.PAID,
                    PaymentAttempt.Status.PREPAID,
                    PaymentAttempt.Status.CONVERTED,
                }
                and IgPaymentEvent.objects.filter(
                    deal__checkout_proposals__payment_attempt_id=attempt.pk,
                    provider_status="success",
                ).exists()
            )
        )
    return IgPaymentEvent.objects.filter(
        deal__checkout_proposals__payment_attempt_id=attempt.pk,
        provider_status=normalized,
    ).exists()


def reconcile_due_assisted_provider_checks(
    *,
    now=None,
    limit: int = 100,
    dry_run: bool = False,
):
    """PaymentAttempt-owned, leased missed-webhook backstop."""

    now = now or timezone.now()
    limit = max(1, min(int(limit), 500))
    due = Q(
        provider_recheck_state=PaymentAttempt.ProviderRecheckState.PENDING,
        provider_recheck_next_at__isnull=False,
        provider_recheck_next_at__lte=now,
    ) | Q(
        provider_recheck_state=PaymentAttempt.ProviderRecheckState.CHECKING,
        provider_recheck_claim_until__lte=now,
    )
    candidate_ids = list(
        PaymentAttempt.objects.filter(due, order__isnull=True)
        .order_by("provider_recheck_next_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    result = {
        "late_status_due": len(candidate_ids),
        "late_status_checked": 0,
        "late_status_pending": len(candidate_ids) if dry_run else 0,
        "late_status_resolved": 0,
        "late_status_exhausted": 0,
        "late_status_errors": 0,
    }
    if dry_run:
        return result

    from management.models import IgCheckoutProposal
    from storefront.views.monobank import (
        _apply_payment_attempt_status,
        _resolve_attempt_invoice_status,
    )

    for attempt_id in candidate_ids:
        claim = _claim_provider_recheck(attempt_id, now=now)
        if claim is None:
            continue
        attempt, token = claim
        if not token:
            result["late_status_exhausted"] += 1
            continue
        status = ""
        try:
            if not attempt.monobank_invoice_id:
                state = _finish_provider_recheck(
                    attempt.pk,
                    token=token,
                    now=now,
                    status="invoice_missing",
                    resolved=False,
                )
                result["late_status_exhausted" if state == "exhausted" else "late_status_pending"] += 1
                continue
            result["late_status_checked"] += 1
            status, payload = _resolve_attempt_invoice_status(
                attempt,
                attempt.monobank_invoice_id,
            )
            normalized = str(status or "").strip().lower()
            if normalized in {"", "processing", "hold"}:
                state = _finish_provider_recheck(
                    attempt.pk,
                    token=token,
                    now=now,
                    status=normalized,
                    resolved=False,
                )
                result["late_status_exhausted" if state == "exhausted" else "late_status_pending"] += 1
                continue
            has_proposal = IgCheckoutProposal.objects.filter(
                payment_attempt_id=attempt.pk
            ).exists()
            if has_proposal:
                _apply_payment_attempt_status(
                    attempt,
                    normalized,
                    payload=payload,
                    source="ig_reconcile",
                )
            else:
                record_orphan_provider_observation(
                    attempt.pk,
                    status=normalized,
                    payload=payload,
                    source="ig_reconcile",
                )
            durable = _provider_apply_is_durable(
                attempt.pk,
                status=normalized,
                has_proposal=has_proposal,
            )
            state = _finish_provider_recheck(
                attempt.pk,
                token=token,
                now=now,
                status=normalized,
                resolved=durable,
            )
            if state == PaymentAttempt.ProviderRecheckState.RESOLVED:
                result["late_status_resolved"] += 1
            elif state == PaymentAttempt.ProviderRecheckState.EXHAUSTED:
                result["late_status_exhausted"] += 1
            else:
                result["late_status_pending"] += 1
        except Exception:
            result["late_status_errors"] += 1
            logger.exception(
                "Assisted provider recheck failed for attempt %s",
                attempt_id,
            )
            try:
                state = _finish_provider_recheck(
                    attempt_id,
                    token=token,
                    now=now,
                    status=status,
                    resolved=False,
                )
                result["late_status_exhausted" if state == "exhausted" else "late_status_pending"] += 1
            except Exception:
                # A hard crash leaves CHECKING until the indexed lease expires.
                pass
    return result
