"""Durable Instagram Direct fulfillment notifications for assigned orders.

The assignment projection is the only source of current ownership.  This
worker deliberately creates a new event for every assignment version so an
unlink/relink cannot replay a message to the previous customer.
"""
from __future__ import annotations

import logging
import threading
import uuid
from contextlib import contextmanager
from datetime import timedelta

from django.db import close_old_connections, transaction
from django.db.models import F, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

LEASE_SECONDS = 300
RETRY_MINUTES = 15
RESPONSE_WINDOW = timedelta(hours=23)
SUPERSEDED_ERROR = "superseded by current order fulfillment state"
_CANONICAL_LIFECYCLE_ASSIGNMENT_SOURCES = frozenset(
    {
        "provider_auto",
        "checkout_auto",
        "manager_payment_review",
    }
)


def _locale(client) -> str:
    language = str(getattr(client, "language", "") or "").lower()
    if language.startswith("en"):
        return "en"
    if language.startswith("ru"):
        return "ru"
    return "uk"


def _message(kind: str, locale: str, order, tracking: str) -> str:
    number = order.order_number or str(order.pk)
    tracking_url = f"https://novaposhta.ua/tracking/?cargo_number={tracking}"
    if kind == "ttn_assigned":
        if locale == "en":
            return (
                f"Your order #{number} has been shipped. Nova Poshta tracking number: "
                f"{tracking}. Track it here: {tracking_url}"
            )
        if locale == "ru":
            return (
                f"Ваш заказ №{number} отправлен. Номер ТТН Новой Почты: {tracking}. "
                f"Отследить: {tracking_url}"
            )
        return (
            f"Ваше замовлення №{number} відправлено. Номер ТТН Нової Пошти: {tracking}. "
            f"Відстежити: {tracking_url}"
        )
    if locale == "en":
        return (
            f"Thank you for your order #{number}! We hope you enjoy it. "
            "Could you leave a review and tag @twocomms in a story with your T-shirt? "
            "Send us the story link or a screenshot in Direct and we will give you "
            "10% off your next order."
        )
    if locale == "ru":
        return (
            f"Спасибо за заказ №{number}! Надеемся, вам понравится. "
            "Будем благодарны за отзыв и отметку @twocomms в сторис с футболкой. "
            "Пришлите ссылку или скрин в Direct — дадим 10% скидки на следующий заказ."
        )
    return (
        f"Дякуємо за замовлення №{number}! Сподіваємося, вам сподобається. "
        "Будемо вдячні за відгук і відмітку @twocomms у сторіс з футболкою. "
        "Якщо відмітите нас і надішлете посилання або скрін у Direct, дамо "
        "10% знижки на наступне замовлення."
    )


def _uses_canonical_lifecycle(assignment) -> bool:
    """Return whether the assignment has the full assisted-checkout context.

    The assignment source alone is not sufficient: legacy provider and
    manager-review links use the same source values but have no checkout
    proposal, so their fulfillment messages must remain on this worker.
    """
    if str(getattr(assignment, "source", "") or "") not in _CANONICAL_LIFECYCLE_ASSIGNMENT_SOURCES:
        return False

    from management.models import IgCheckoutProposal, IgOrderAttribution

    proposal = (
        IgCheckoutProposal.objects.filter(payment_attempt__order_id=assignment.order_id)
        .values("client_id", "deal_id")
        .first()
    )
    if not proposal or proposal["client_id"] != assignment.client_id:
        return False
    return IgOrderAttribution.objects.filter(
        order_id=assignment.order_id,
        client_id=proposal["client_id"],
        deal_id=proposal["deal_id"],
    ).exists()


def _cancel_redundant_events(assignment, *, now):
    from management.ig_bot_models import IgOrderCustomerEvent

    active_states = (
        IgOrderCustomerEvent.State.PENDING,
        IgOrderCustomerEvent.State.FAILED,
        IgOrderCustomerEvent.State.WAITING_WINDOW,
        IgOrderCustomerEvent.State.PROCESSING,
    )
    return IgOrderCustomerEvent.objects.filter(
        assignment_id=assignment.pk,
        state__in=active_states,
    ).update(
        state=IgOrderCustomerEvent.State.CANCELLED,
        lease_token="",
        lease_expires_at=None,
        last_error="canonical Instagram lifecycle event owns this automated checkout",
        due_at=now,
        updated_at=now,
    )


def _event_specs(assignment, *, now):
    order = assignment.order
    client = assignment.client
    locale = _locale(client)
    tracking = str(order.tracking_number or "").strip()
    if tracking and order.status not in {"done", "cancelled"}:
        yield {
            "kind": "ttn_assigned",
            "event_key": f"ig-assignment:{assignment.pk}:v{assignment.version}:ttn:{tracking}",
            "message": _message("ttn_assigned", locale, order, tracking),
            "payload": {"tracking_number": tracking, "tracking_url": f"https://novaposhta.ua/tracking/?cargo_number={tracking}"},
        }
    if order.status == "done":
        yield {
            "kind": "delivered_review",
            "event_key": f"ig-assignment:{assignment.pk}:v{assignment.version}:delivered-review",
            "message": _message("delivered_review", locale, order, tracking),
            "payload": {"order_number": order.order_number or str(order.pk)},
        }


def ensure_assignment_events(assignment, *, now=None):
    """Materialize all currently eligible durable events for one assignment."""
    from management.ig_bot_models import IgOrderCustomerEvent

    now = now or timezone.now()
    if not assignment.client_id or assignment.unassigned_at is not None:
        return []
    if _uses_canonical_lifecycle(assignment):
        _cancel_redundant_events(assignment, now=now)
        return []
    if assignment.version == 1 and assignment.last_reason_code == "legacy_attribution":
        return []
    created = []
    for spec in _event_specs(assignment, now=now):
        event, was_created = IgOrderCustomerEvent.objects.get_or_create(
            event_key=spec["event_key"],
            defaults={
                "assignment": assignment,
                "assignment_version": assignment.version,
                "order": assignment.order,
                "client": assignment.client,
                "kind": spec["kind"],
                "locale": _locale(assignment.client),
                "message_snapshot": spec["message"],
                "payload": spec["payload"],
                "due_at": now,
            },
        )
        if was_created:
            created.append(event)
    return created


def _claim_event(event_id, *, now):
    from management.ig_bot_models import IgOrderCustomerEvent

    token = uuid.uuid4().hex
    with transaction.atomic():
        event = IgOrderCustomerEvent.objects.select_for_update().select_related(
            "assignment", "order", "client"
        ).get(pk=event_id)
        if event.state in {
            IgOrderCustomerEvent.State.SENT,
            IgOrderCustomerEvent.State.CANCELLED,
            IgOrderCustomerEvent.State.MANAGER_REVIEW,
            IgOrderCustomerEvent.State.AMBIGUOUS,
        }:
            return None
        if event.due_at > now:
            return None
        if event.state == IgOrderCustomerEvent.State.PROCESSING and event.lease_expires_at and event.lease_expires_at > now:
            return None
        event.state = IgOrderCustomerEvent.State.PROCESSING
        event.attempts += 1
        event.lease_token = token
        event.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        event.last_error = ""
        event.save(update_fields=["state", "attempts", "lease_token", "lease_expires_at", "last_error", "updated_at"])
        return event


def _finish(
    event,
    *,
    token,
    state,
    now,
    error="",
    due_at=None,
    provider_message_id="",
):
    from management.ig_bot_models import IgOrderCustomerEvent

    updated = IgOrderCustomerEvent.objects.filter(pk=event.pk, lease_token=token).update(
        state=state,
        lease_token="",
        lease_expires_at=None,
        last_error=(error or "")[:1000],
        due_at=due_at or now,
        provider_message_id=str(provider_message_id or "")[:128],
        completed_at=now if state == IgOrderCustomerEvent.State.SENT else None,
        updated_at=now,
    )
    return bool(updated)


def _active_opt_out(client) -> bool:
    return bool(
        client.opted_out_at
        and (not client.opted_in_at or client.opted_in_at < client.opted_out_at)
    )


def _inside_response_window(client, *, now) -> bool:
    return bool(
        client.last_message_at
        and now <= client.last_message_at + RESPONSE_WINDOW
    )


def _matches_current_fulfillment(event, order) -> bool:
    """Return whether the durable snapshot still matches the live order."""
    tracking = str(getattr(order, "tracking_number", "") or "").strip()
    if event.kind == "ttn_assigned":
        event_tracking = str((event.payload or {}).get("tracking_number") or "").strip()
        return bool(
            order.status not in {"done", "cancelled"}
            and tracking
            and event_tracking == tracking
        )
    if event.kind == "delivered_review":
        return order.status == "done"
    return False


@contextmanager
def _event_send_boundary(
    event,
    *,
    token,
    settings_id,
    permission,
    now,
    boundary_state,
):
    """Revalidate and lock current ownership immediately around Meta I/O."""
    from management.ig_bot_models import IgOrderAssignment, IgOrderCustomerEvent
    from management.services.ig_reply_boundary import customer_send_boundary
    from orders.models import Order

    with customer_send_boundary(settings_id, event.client_id, permission) as permitted:
        if not permitted:
            yield False
            return
        with transaction.atomic():
            current_event = (
                IgOrderCustomerEvent.objects.select_for_update()
                .filter(
                    pk=event.pk,
                    lease_token=token,
                    state=IgOrderCustomerEvent.State.PROCESSING,
                )
                .first()
            )
            assignment = (
                IgOrderAssignment.objects.select_for_update()
                .select_related("client")
                .filter(pk=event.assignment_id)
                .first()
            )
            order = (
                Order.objects.select_for_update()
                .filter(pk=event.order_id)
                .first()
            )
            client = assignment.client if assignment else None
            fulfillment_current = bool(
                current_event
                and order
                and _matches_current_fulfillment(current_event, order)
            )
            if current_event and order and not fulfillment_current:
                boundary_state["superseded"] = True
            current = bool(
                current_event
                and assignment
                and fulfillment_current
                and assignment.client_id == event.client_id
                and assignment.unassigned_at is None
                and assignment.version == event.assignment_version
                and client
                and not client.hidden_at
                and not client.is_blocked
                and not _active_opt_out(client)
                and _inside_response_window(client, now=now)
            )
            yield current


def deliver_event(event_id, *, send=True, now=None):
    """Claim and optionally deliver one event; safe to retry after crashes."""
    from management.ig_bot_models import IgOrderCustomerEvent
    from management.models import InstagramBotSettings

    now = now or timezone.now()
    settings_obj = InstagramBotSettings.load()
    if not settings_obj.is_enabled:
        return "paused"
    event = _claim_event(event_id, now=now)
    if event is None:
        return "skipped"
    token = event.lease_token
    event = (
        IgOrderCustomerEvent.objects.select_related("assignment", "order", "client")
        .get(pk=event.pk)
    )
    assignment = event.assignment
    client = event.client
    if (
        not assignment.client_id
        or assignment.client_id != client.pk
        or assignment.unassigned_at is not None
        or assignment.version != event.assignment_version
    ):
        _finish(event, token=token, state=IgOrderCustomerEvent.State.CANCELLED, now=now, error="assignment is no longer current")
        return "cancelled"
    if not _matches_current_fulfillment(event, event.order):
        _finish(
            event,
            token=token,
            state=IgOrderCustomerEvent.State.CANCELLED,
            now=now,
            error=SUPERSEDED_ERROR,
        )
        return "cancelled"
    if client.hidden_at or client.is_blocked or _active_opt_out(client):
        _finish(event, token=token, state=IgOrderCustomerEvent.State.CANCELLED, now=now, error="client hidden or opted out")
        return "cancelled"
    if client.bot_paused or client.manager_takeover:
        _finish(event, token=token, state=IgOrderCustomerEvent.State.WAITING_WINDOW, now=now, due_at=now + timedelta(minutes=RETRY_MINUTES), error="manager currently owns the conversation")
        return "paused"
    if not send:
        _finish(event, token=token, state=IgOrderCustomerEvent.State.PENDING, now=now)
        return "planned"
    if not _inside_response_window(client, now=now):
        _finish(
            event,
            token=token,
            state=IgOrderCustomerEvent.State.MANAGER_REVIEW,
            now=now,
            error="standard response window is closed",
        )
        return "manager_review"
    from management.services import instagram_bot
    from management.services.ig_reply_boundary import capture_reply_permission

    permission = capture_reply_permission(settings_obj.pk, client.pk)
    provider_message_ids = []
    boundary_state = {"superseded": False}

    ok, kind, hint = instagram_bot.send_text(
        settings_obj,
        client.igsid,
        event.message_snapshot,
        permission_boundary_factory=lambda: _event_send_boundary(
            event,
            token=token,
            settings_id=settings_obj.pk,
            permission=permission,
            now=now,
            boundary_state=boundary_state,
        ),
        provider_message_callback=lambda message_id: provider_message_ids.append(
            str(message_id)
        ),
        allow_url_fallback=True,
    )
    provider_message_id = ",".join(provider_message_ids)
    if ok and provider_message_id:
        finished = _finish(
            event,
            token=token,
            state=IgOrderCustomerEvent.State.SENT,
            now=now,
            provider_message_id=provider_message_id,
        )
        return "sent" if finished else "ambiguous"
    if ok:
        _finish(
            event,
            token=token,
            state=IgOrderCustomerEvent.State.AMBIGUOUS,
            now=now,
            error="Meta returned success without a provider message_id",
        )
        return "ambiguous"
    if kind in {"unknown", "transient"}:
        _finish(
            event,
            token=token,
            state=IgOrderCustomerEvent.State.AMBIGUOUS,
            now=now,
            error=hint,
            provider_message_id=provider_message_id,
        )
        return "ambiguous"
    if kind == "cancelled":
        error = SUPERSEDED_ERROR if boundary_state["superseded"] else hint
        _finish(event, token=token, state=IgOrderCustomerEvent.State.CANCELLED, now=now, error=error)
        return "cancelled"
    if kind in {"permanent", "policy", "link_restricted"}:
        _finish(event, token=token, state=IgOrderCustomerEvent.State.MANAGER_REVIEW, now=now, error=hint)
        return "manager_review"
    _finish(event, token=token, state=IgOrderCustomerEvent.State.FAILED, now=now, due_at=now + timedelta(minutes=RETRY_MINUTES), error=hint)
    return "failed"


def reconcile_order_customer_events(*, order_id=None, limit=100, send=True, now=None):
    """Materialize and process eligible assignment notifications."""
    from management.ig_bot_models import IgOrderAssignment, IgOrderCustomerEvent

    now = now or timezone.now()
    assignments = IgOrderAssignment.objects.filter(
        client__isnull=False,
        unassigned_at__isnull=True,
    ).select_related("order", "client")
    if order_id is not None:
        assignments = assignments.filter(order_id=order_id)
    stats = {
        "created": 0,
        "sent": 0,
        "failed": 0,
        "cancelled": 0,
        "ambiguous": 0,
        "manager_review": 0,
        "paused": 0,
        "skipped": 0,
    }
    materialized = 0
    for assignment in assignments.order_by("id").iterator(chunk_size=200):
        created = len(ensure_assignment_events(assignment, now=now))
        stats["created"] += created
        if created:
            materialized += 1
            if materialized >= limit:
                break

    active_events = IgOrderCustomerEvent.objects.exclude(
        state__in=(
            IgOrderCustomerEvent.State.SENT,
            IgOrderCustomerEvent.State.CANCELLED,
            IgOrderCustomerEvent.State.MANAGER_REVIEW,
            IgOrderCustomerEvent.State.AMBIGUOUS,
        )
    )
    if order_id is not None:
        active_events = active_events.filter(order_id=order_id)
    stale_fulfillment_ids = []
    for event in active_events.select_related("order").iterator(chunk_size=200):
        if not _matches_current_fulfillment(event, event.order):
            stale_fulfillment_ids.append(event.pk)
    if stale_fulfillment_ids:
        stats["cancelled"] += IgOrderCustomerEvent.objects.filter(
            pk__in=stale_fulfillment_ids,
        ).exclude(
            state__in=(
                IgOrderCustomerEvent.State.SENT,
                IgOrderCustomerEvent.State.CANCELLED,
                IgOrderCustomerEvent.State.MANAGER_REVIEW,
                IgOrderCustomerEvent.State.AMBIGUOUS,
            )
        ).update(
            state=IgOrderCustomerEvent.State.CANCELLED,
            lease_token="",
            lease_expires_at=None,
            last_error=SUPERSEDED_ERROR,
            due_at=now,
            updated_at=now,
        )
    ineligible = active_events.filter(
        Q(assignment__client_id__isnull=True)
        | Q(assignment__unassigned_at__isnull=False)
        | ~Q(assignment__client_id=F("client_id"))
        | ~Q(assignment__version=F("assignment_version"))
        | Q(client__hidden_at__isnull=False)
        | Q(client__is_blocked=True)
        | (
            Q(client__opted_out_at__isnull=False)
            & (
                Q(client__opted_in_at__isnull=True)
                | Q(client__opted_in_at__lt=F("client__opted_out_at"))
            )
        )
    )
    stats["cancelled"] += ineligible.update(
        state=IgOrderCustomerEvent.State.CANCELLED,
        lease_token="",
        lease_expires_at=None,
        last_error="assignment or customer is no longer eligible",
        due_at=now,
        updated_at=now,
    )

    expired_processing = active_events.filter(
        state=IgOrderCustomerEvent.State.PROCESSING,
    ).filter(
        Q(lease_expires_at__isnull=True) | Q(lease_expires_at__lte=now)
    )
    stats["ambiguous"] += expired_processing.update(
        state=IgOrderCustomerEvent.State.AMBIGUOUS,
        lease_token="",
        lease_expires_at=None,
        last_error="processing lease expired; delivery outcome requires manager review",
        due_at=now,
        updated_at=now,
    )

    if not send:
        return stats

    events = IgOrderCustomerEvent.objects.filter(
        state__in=(IgOrderCustomerEvent.State.PENDING, IgOrderCustomerEvent.State.FAILED, IgOrderCustomerEvent.State.WAITING_WINDOW),
        due_at__lte=now,
    ).order_by("due_at", "id")
    if order_id is not None:
        events = events.filter(order_id=order_id)
    for event in events[:limit]:
        result = deliver_event(event.pk, send=send, now=now)
        stats[result] = stats.get(result, 0) + 1
    return stats


def kick_order_fulfillment(order_id):
    """Best-effort post-commit wake-up; durable reconciliation remains retryable."""
    def run():
        close_old_connections()
        try:
            reconcile_order_customer_events(order_id=order_id, limit=10, send=True)
        except Exception:
            logger.exception("Instagram fulfillment reconciliation failed for order %s", order_id)
        finally:
            close_old_connections()

    try:
        threading.Thread(target=run, name=f"ig-fulfillment-{order_id}", daemon=True).start()
    except Exception:
        logger.exception("Could not start Instagram fulfillment worker for order %s", order_id)
