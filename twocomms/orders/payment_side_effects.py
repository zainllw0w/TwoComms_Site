"""Lease-backed durable payment side-effect intents and bounded delivery."""

from dataclasses import dataclass
from datetime import timedelta
import secrets

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from orders.models import PaymentSideEffectJob


DEFAULT_LEASE_DURATION = timedelta(minutes=5)
BASE_RETRY_DELAY = timedelta(minutes=1)
MAX_RETRY_DELAY = timedelta(hours=1)
_ALLOWED_PAYLOAD_KEYS = frozenset({"previous_status", "pay_type", "source_url"})
_ATTEMPT_KINDS = frozenset(
    {
        PaymentSideEffectJob.Kind.ATTEMPT_ADD_PAYMENT_INFO,
        PaymentSideEffectJob.Kind.ATTEMPT_TELEGRAM_STARTED,
    }
)
_POST_PAYMENT_CHANNELS = (
    "telegram",
    "meta_purchase",
    "tiktok_purchase",
    "receipt_email",
)
_POST_PAYMENT_TERMINAL_STATES = frozenset(
    {"sent", "skipped", "disabled", "unknown", "ambiguous"}
)


@dataclass(frozen=True)
class PaymentSideEffectClaim:
    job_id: int | None
    outcome: str
    lease_token: str = ""


def _normalize_payload(payload):
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("payment side-effect payload must be a mapping")
    unknown = set(payload) - _ALLOWED_PAYLOAD_KEYS
    if unknown:
        raise ValueError(
            "payment side-effect payload contains unsupported keys: "
            + ", ".join(sorted(str(key) for key in unknown))
        )
    normalized = {}
    for key, value in payload.items():
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"payment side-effect payload field {key} must be text")
        normalized[key] = value[:2048] if key == "source_url" else value[:64]
    return normalized


def _validate_subject(kind, payment_attempt_id, order_id):
    has_attempt = payment_attempt_id is not None
    has_order = order_id is not None
    if has_attempt == has_order:
        raise ValueError("payment side-effect job requires exactly one subject")
    if kind in _ATTEMPT_KINDS and not has_attempt:
        raise ValueError(f"payment_attempt is required for {kind}")
    if kind == PaymentSideEffectJob.Kind.ORDER_POST_PAYMENT and not has_order:
        raise ValueError("order is required for order_post_payment")


def enqueue_payment_side_effect(
    *,
    kind,
    event_key,
    payment_attempt_id=None,
    order_id=None,
    payload=None,
    due_at=None,
):
    """Persist one immutable intent and return ``(job, created)``."""
    kind = str(kind or "").strip()
    if kind not in PaymentSideEffectJob.Kind.values:
        raise ValueError(f"unsupported payment side-effect kind: {kind}")
    event_key = str(event_key or "").strip()
    if not event_key or len(event_key) > 180:
        raise ValueError("payment side-effect event_key must contain 1..180 characters")
    _validate_subject(kind, payment_attempt_id, order_id)
    normalized_payload = _normalize_payload(payload)
    defaults = {
        "kind": kind,
        "payment_attempt_id": payment_attempt_id,
        "order_id": order_id,
        "payload": normalized_payload,
        "due_at": due_at or timezone.now(),
    }
    job, created = PaymentSideEffectJob.objects.get_or_create(
        event_key=event_key,
        defaults=defaults,
    )
    if (
        job.kind != kind
        or job.payment_attempt_id != payment_attempt_id
        or job.order_id != order_id
    ):
        raise ValueError("payment side-effect event_key belongs to another intent")
    return job, created


def enqueue_attempt_add_payment_info_side_effect(attempt_id, *, source_url=None):
    """Persist one stable AddPaymentInfo intent."""
    return enqueue_payment_side_effect(
        kind=PaymentSideEffectJob.Kind.ATTEMPT_ADD_PAYMENT_INFO,
        event_key=f"payment-attempt:{int(attempt_id)}:add-payment-info",
        payment_attempt_id=attempt_id,
        payload={"source_url": source_url} if source_url else {},
    )


def enqueue_attempt_invoice_side_effects(attempt_id, *, source_url=None):
    """Persist the two non-provider invoice side effects with stable keys."""
    add_payment_job, add_payment_created = enqueue_attempt_add_payment_info_side_effect(
        attempt_id,
        source_url=source_url,
    )
    telegram_job, telegram_created = enqueue_payment_side_effect(
        kind=PaymentSideEffectJob.Kind.ATTEMPT_TELEGRAM_STARTED,
        event_key=f"payment-attempt:{int(attempt_id)}:telegram-started",
        payment_attempt_id=attempt_id,
    )
    return (
        (add_payment_job, add_payment_created),
        (telegram_job, telegram_created),
    )


def enqueue_order_post_payment_side_effect(
    order_id,
    *,
    previous_status="unpaid",
    pay_type="",
    due_at=None,
):
    """Persist one paid-order intent inside the caller's transaction."""
    return enqueue_payment_side_effect(
        kind=PaymentSideEffectJob.Kind.ORDER_POST_PAYMENT,
        event_key=f"order:{int(order_id)}:post-payment",
        order_id=order_id,
        payload={
            "previous_status": str(previous_status or "unpaid"),
            "pay_type": str(pay_type or ""),
        },
        due_at=due_at,
    )


def _mark_ambiguous(job, *, now, error):
    job.state = PaymentSideEffectJob.State.AMBIGUOUS
    job.lease_token = ""
    job.lease_expires_at = None
    job.last_error = str(error)[:500]
    job.due_at = now
    job.save(
        update_fields=[
            "state",
            "lease_token",
            "lease_expires_at",
            "last_error",
            "due_at",
            "updated_at",
        ]
    )
    return PaymentSideEffectClaim(job.pk, "ambiguous")


def claim_payment_side_effect(
    job_id,
    *,
    now=None,
    lease_duration=DEFAULT_LEASE_DURATION,
):
    """Claim one due job, or return the durable reason it cannot be claimed."""
    now = now or timezone.now()
    lease_token = secrets.token_hex(24)
    with transaction.atomic():
        job = (
            PaymentSideEffectJob.objects.select_for_update()
            .filter(pk=job_id)
            .first()
        )
        if job is None:
            return PaymentSideEffectClaim(None, "missing")
        if job.state == PaymentSideEffectJob.State.DONE:
            return PaymentSideEffectClaim(job.pk, "done")
        if job.state == PaymentSideEffectJob.State.AMBIGUOUS:
            return PaymentSideEffectClaim(job.pk, "ambiguous")
        if job.state == PaymentSideEffectJob.State.PROCESSING:
            if job.lease_expires_at and job.lease_expires_at > now:
                return PaymentSideEffectClaim(job.pk, "leased")
            if job.provider_io_started_at is not None:
                return _mark_ambiguous(
                    job,
                    now=now,
                    error="provider I/O started before lease recovery; outcome requires review",
                )
            if job.lease_expires_at is None:
                return _mark_ambiguous(
                    job,
                    now=now,
                    error="processing lease has no expiry; outcome requires review",
                )
        elif job.provider_io_started_at is not None:
            return _mark_ambiguous(
                job,
                now=now,
                error="provider I/O marker exists before a new lease",
            )
        elif job.due_at > now:
            return PaymentSideEffectClaim(job.pk, "not_due")

        job.state = PaymentSideEffectJob.State.PROCESSING
        job.lease_token = lease_token
        job.lease_expires_at = now + lease_duration
        job.attempts += 1
        job.last_error = ""
        job.save(
            update_fields=[
                "state",
                "lease_token",
                "lease_expires_at",
                "attempts",
                "last_error",
                "updated_at",
            ]
        )
    return PaymentSideEffectClaim(job.pk, "claimed", lease_token)


def mark_payment_side_effect_provider_io_started(job_id, lease_token, *, now=None):
    """Commit the provider boundary immediately before the first network call."""
    now = now or timezone.now()
    updated = PaymentSideEffectJob.objects.filter(
        pk=job_id,
        state=PaymentSideEffectJob.State.PROCESSING,
        lease_token=lease_token,
        provider_io_started_at__isnull=True,
    ).update(provider_io_started_at=now, updated_at=now)
    if updated:
        return True
    return PaymentSideEffectJob.objects.filter(
        pk=job_id,
        state=PaymentSideEffectJob.State.PROCESSING,
        lease_token=lease_token,
        provider_io_started_at__isnull=False,
    ).exists()


def complete_payment_side_effect(job_id, lease_token, *, now=None):
    """Finalize a claimed job only while the caller still owns its lease."""
    now = now or timezone.now()
    updated = PaymentSideEffectJob.objects.filter(
        pk=job_id,
        state=PaymentSideEffectJob.State.PROCESSING,
        lease_token=lease_token,
    ).update(
        state=PaymentSideEffectJob.State.DONE,
        lease_token="",
        lease_expires_at=None,
        last_error="",
        completed_at=now,
        updated_at=now,
    )
    return bool(updated)


def _retry_delay(attempts):
    exponent = max(0, min(int(attempts or 1) - 1, 6))
    seconds = min(
        BASE_RETRY_DELAY.total_seconds() * (2 ** exponent),
        MAX_RETRY_DELAY.total_seconds(),
    )
    return timedelta(seconds=seconds)


def fail_payment_side_effect(job_id, lease_token, error, *, now=None):
    """Release a definitive failure for a later bounded retry."""
    now = now or timezone.now()
    with transaction.atomic():
        job = (
            PaymentSideEffectJob.objects.select_for_update()
            .filter(
                pk=job_id,
                state=PaymentSideEffectJob.State.PROCESSING,
                lease_token=lease_token,
            )
            .first()
        )
        if job is None:
            return False
        job.state = PaymentSideEffectJob.State.FAILED
        job.lease_token = ""
        job.lease_expires_at = None
        job.provider_io_started_at = None
        job.last_error = str(error or "provider delivery failed")[:500]
        job.due_at = now + _retry_delay(job.attempts)
        job.save(
            update_fields=[
                "state",
                "lease_token",
                "lease_expires_at",
                "provider_io_started_at",
                "last_error",
                "due_at",
                "updated_at",
            ]
        )
    return True


def mark_payment_side_effect_ambiguous(job_id, lease_token, error, *, now=None):
    """Stop automatic replay when a provider may already have accepted I/O."""
    now = now or timezone.now()
    updated = PaymentSideEffectJob.objects.filter(
        pk=job_id,
        state=PaymentSideEffectJob.State.PROCESSING,
        lease_token=lease_token,
    ).update(
        state=PaymentSideEffectJob.State.AMBIGUOUS,
        lease_token="",
        lease_expires_at=None,
        last_error=str(error or "provider outcome is ambiguous")[:500],
        due_at=now,
        updated_at=now,
    )
    return bool(updated)


def due_payment_side_effect_job_ids(*, limit, now=None, order_id=None):
    """Return a bounded deterministic batch, including expired worker leases."""
    now = now or timezone.now()
    limit = int(limit)
    if limit <= 0:
        return []
    due = Q(
        state__in=(
            PaymentSideEffectJob.State.PENDING,
            PaymentSideEffectJob.State.FAILED,
        ),
        due_at__lte=now,
    )
    expired = Q(
        state=PaymentSideEffectJob.State.PROCESSING,
        lease_expires_at__lte=now,
    ) | Q(
        state=PaymentSideEffectJob.State.PROCESSING,
        lease_expires_at__isnull=True,
    )
    queryset = PaymentSideEffectJob.objects.filter(due | expired)
    if order_id is not None:
        queryset = queryset.filter(order_id=order_id)
    return list(
        queryset.order_by("due_at", "id").values_list("id", flat=True)[:limit]
    )


def _post_payment_subject_outcome(order):
    payload = order.payment_payload if isinstance(order.payment_payload, dict) else {}
    channels = payload.get("post_payment_channels")
    if not isinstance(channels, dict):
        return None
    states = []
    for channel in _POST_PAYMENT_CHANNELS:
        entry = channels.get(channel)
        if not isinstance(entry, dict):
            return None
        state = str(entry.get("state") or "").strip().lower()
        if state not in _POST_PAYMENT_TERMINAL_STATES:
            return None
        states.append(state)
    if "ambiguous" in states:
        return "ambiguous"
    return "done"


def _subject_terminal_outcome(job):
    if job.kind == PaymentSideEffectJob.Kind.ATTEMPT_ADD_PAYMENT_INFO:
        attempt = job.payment_attempt
        if attempt is None:
            return "ambiguous"
        event_state = attempt.event_state if isinstance(attempt.event_state, dict) else {}
        if event_state.get("fb_capi_add_payment_info"):
            return "done"
        return None
    if job.kind == PaymentSideEffectJob.Kind.ATTEMPT_TELEGRAM_STARTED:
        attempt = job.payment_attempt
        if attempt is None:
            return "ambiguous"
        state = (
            attempt.notification_state
            if isinstance(attempt.notification_state, dict)
            else {}
        )
        if state.get("started_sent"):
            return "done"
        if state.get("started_ambiguous"):
            return "ambiguous"
        return None
    if job.kind == PaymentSideEffectJob.Kind.ORDER_POST_PAYMENT:
        if job.order is None:
            return "ambiguous"
        return _post_payment_subject_outcome(job.order)
    return "ambiguous"


def _reconcile_subject_terminal_outcome(job_id, *, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        job = (
            PaymentSideEffectJob.objects.select_for_update()
            .select_related("payment_attempt", "order")
            .filter(pk=job_id)
            .first()
        )
        if job is None:
            return "missing"
        if job.state == PaymentSideEffectJob.State.DONE:
            return "done"
        if job.state == PaymentSideEffectJob.State.AMBIGUOUS:
            return "ambiguous"
        outcome = _subject_terminal_outcome(job)
        if outcome is None:
            return None
        job.state = (
            PaymentSideEffectJob.State.DONE
            if outcome == "done"
            else PaymentSideEffectJob.State.AMBIGUOUS
        )
        job.lease_token = ""
        job.lease_expires_at = None
        job.last_error = "" if outcome == "done" else "subject delivery is ambiguous"
        job.completed_at = now if outcome == "done" else None
        job.save(
            update_fields=[
                "state",
                "lease_token",
                "lease_expires_at",
                "last_error",
                "completed_at",
                "updated_at",
            ]
        )
    return outcome


def _persist_attempt_notification_outcome(attempt_id, outcome, *, now=None):
    from orders.models import PaymentAttempt

    now = now or timezone.now()
    with transaction.atomic():
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
        state = (
            dict(attempt.notification_state)
            if isinstance(attempt.notification_state, dict)
            else {}
        )
        if outcome == "sent":
            state["started_sent"] = True
            state["started_sent_at"] = now.isoformat()
            state.pop("started_ambiguous", None)
            state.pop("started_ambiguous_at", None)
        elif outcome == "ambiguous":
            state["started_ambiguous"] = True
            state["started_ambiguous_at"] = now.isoformat()
        attempt.notification_state = state
        attempt.save(update_fields=["notification_state", "updated"])


def _process_add_payment_info(job, lease_token, *, now):
    from orders.facebook_conversions_service import get_facebook_conversions_service

    facebook = get_facebook_conversions_service()
    if not facebook.enabled:
        complete_payment_side_effect(job.pk, lease_token, now=now)
        return "done"
    if not mark_payment_side_effect_provider_io_started(job.pk, lease_token, now=now):
        return "leased"
    attempt = job.payment_attempt
    sent = facebook.send_add_payment_info_event(
        order=attempt,
        payment_amount=float(attempt.payment_amount),
        event_id=attempt.add_payment_event_id,
        source_url=job.payload.get("source_url") or None,
    )
    if sent:
        complete_payment_side_effect(job.pk, lease_token, now=now)
        return "done"
    fail_payment_side_effect(job.pk, lease_token, "add_payment_info_failed", now=now)
    return "failed"


def _normalize_delivery_outcome(value):
    outcome = getattr(value, "outcome", None)
    if outcome in {"sent", "failed", "ambiguous"}:
        return outcome
    if value is True:
        return "sent"
    if value is False or value is None:
        return "failed"
    value = str(value)
    return value if value in {"sent", "failed", "ambiguous"} else "failed"


def _process_attempt_telegram(job, lease_token, *, now):
    from orders.telegram_notifications import TelegramNotifier

    if not mark_payment_side_effect_provider_io_started(job.pk, lease_token, now=now):
        return "leased"
    outcome = _normalize_delivery_outcome(
        TelegramNotifier().send_payment_attempt_notification(
            job.payment_attempt,
            return_outcome=True,
        )
    )
    if outcome == "sent":
        _persist_attempt_notification_outcome(job.payment_attempt_id, "sent", now=now)
        complete_payment_side_effect(job.pk, lease_token, now=now)
        return "done"
    if outcome == "ambiguous":
        _persist_attempt_notification_outcome(
            job.payment_attempt_id,
            "ambiguous",
            now=now,
        )
        mark_payment_side_effect_ambiguous(
            job.pk,
            lease_token,
            "telegram_attempt_delivery_ambiguous",
            now=now,
        )
        return "ambiguous"
    fail_payment_side_effect(job.pk, lease_token, "telegram_attempt_failed", now=now)
    return "failed"


def _process_order_post_payment(job, lease_token, *, now):
    from storefront.views.utils import _send_post_payment_events

    if not mark_payment_side_effect_provider_io_started(job.pk, lease_token, now=now):
        return "leased"
    result = _send_post_payment_events(
        job.order_id,
        job.payload.get("previous_status") or "unpaid",
        job.payload.get("pay_type") or job.order.pay_type,
    )
    reconciled = _reconcile_subject_terminal_outcome(job.pk, now=now)
    if reconciled is not None:
        return reconciled
    if _normalize_delivery_outcome(result) == "ambiguous":
        mark_payment_side_effect_ambiguous(
            job.pk,
            lease_token,
            "post_payment_delivery_ambiguous",
            now=now,
        )
        return "ambiguous"
    fail_payment_side_effect(job.pk, lease_token, "post_payment_incomplete", now=now)
    return "failed"


def process_payment_side_effect_job(job_id, *, now=None):
    """Process one durable intent without allowing blind provider replay."""
    now = now or timezone.now()
    reconciled = _reconcile_subject_terminal_outcome(job_id, now=now)
    if reconciled is not None:
        return reconciled
    claim = claim_payment_side_effect(job_id, now=now)
    if claim.outcome != "claimed":
        return claim.outcome
    job = (
        PaymentSideEffectJob.objects.select_related("payment_attempt", "order")
        .filter(pk=job_id)
        .first()
    )
    if job is None:
        return "missing"
    try:
        if job.kind == PaymentSideEffectJob.Kind.ATTEMPT_ADD_PAYMENT_INFO:
            return _process_add_payment_info(job, claim.lease_token, now=now)
        if job.kind == PaymentSideEffectJob.Kind.ATTEMPT_TELEGRAM_STARTED:
            return _process_attempt_telegram(job, claim.lease_token, now=now)
        if job.kind == PaymentSideEffectJob.Kind.ORDER_POST_PAYMENT:
            return _process_order_post_payment(job, claim.lease_token, now=now)
        mark_payment_side_effect_ambiguous(
            job.pk,
            claim.lease_token,
            "unsupported payment side-effect kind",
            now=now,
        )
        return "ambiguous"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        provider_started = PaymentSideEffectJob.objects.filter(
            pk=job.pk,
            state=PaymentSideEffectJob.State.PROCESSING,
            lease_token=claim.lease_token,
            provider_io_started_at__isnull=False,
        ).exists()
        if provider_started:
            mark_payment_side_effect_ambiguous(
                job.pk,
                claim.lease_token,
                f"provider exception after I/O boundary: {error}",
                now=now,
            )
            return "ambiguous"
        if fail_payment_side_effect(
            job.pk,
            claim.lease_token,
            f"delivery failed before provider I/O: {error}",
            now=now,
        ):
            return "failed"
        return "leased"
