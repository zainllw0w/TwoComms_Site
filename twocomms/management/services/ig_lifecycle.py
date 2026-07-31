"""Durable Instagram post-sale lifecycle events.

The order, payment, and Nova Poshta integrations own business truth.  This
module only projects committed truth into one idempotent Direct message.  It
never treats Telegram delivery or an AI response as evidence of payment,
shipment, or delivery.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from management.models import IgCheckoutProposal, IgLifecycleEvent, IgOrderAttribution

logger = logging.getLogger("management.ig_lifecycle")

RESPONSE_WINDOW = timedelta(hours=23)
LEASE_DURATION = timedelta(minutes=5)
NP_TRACKING_URL = "https://novaposhta.ua/tracking/?cargo_number="


def _locale(value: str | None) -> str:
    code = str(value or "uk").lower().replace("_", "-").split("-", 1)[0]
    return code if code in {"uk", "ru", "en"} else "uk"


def _tracking_digest(value: str) -> str:
    return hashlib.sha256(str(value or "").strip().encode("utf-8")).hexdigest()[:24]


def _context_for_order(order):
    """Return the exact proposal/client/deal/episode/attribution context."""
    attribution = IgOrderAttribution.objects.select_related(
        "client", "deal"
    ).filter(order_id=order.pk).first()
    proposal = IgCheckoutProposal.objects.select_related(
        "client", "deal", "commercial_episode", "payment_attempt"
    ).filter(payment_attempt__order_id=order.pk).first()
    if attribution is None or proposal is None:
        return None
    if attribution.client_id != proposal.client_id or attribution.deal_id != proposal.deal_id:
        logger.warning(
            "IG lifecycle context mismatch for order %s: attribution=%s proposal=%s",
            order.pk,
            attribution.pk,
            proposal.pk,
        )
        return None
    episode = proposal.commercial_episode
    return {
        "attribution": attribution,
        "proposal": proposal,
        "client": proposal.client,
        "deal": proposal.deal,
        "episode": episode,
    }


def _event_key(order, kind, payload):
    if kind == IgLifecycleEvent.Kind.PAYMENT_VERIFIED:
        return f"payment:{payload['attempt_id']}:verified"
    if kind == IgLifecycleEvent.Kind.TTN_CREATED:
        return f"ttn:{order.pk}:{_tracking_digest(payload['tracking_number'])}"
    return f"delivered:{order.pk}:{payload['status_code']}"


def _message(event: IgLifecycleEvent) -> str:
    locale = _locale(event.locale)
    payload = event.payload or {}
    order = event.order
    if event.kind == IgLifecycleEvent.Kind.PAYMENT_VERIFIED:
        amount = payload.get("amount") or ""
        recipient = str(order.full_name or "").strip()
        phone = str(order.phone or "").strip()
        city = str(order.city or "").strip()
        office = str(order.np_office or "").strip()
        copies = {
            "uk": (
                f"Дякуємо, оплату отримано. Замовлення #{order.order_number} готуємо для {recipient}. "
                f"Доставка: {city}, {office}. Телефон для зв'язку: {phone}. "
                "Я надішлю ТТН сюди, щойно її буде створено."
            ),
            "ru": (
                f"Спасибо, оплату получили. Заказ #{order.order_number} готовим для {recipient}. "
                f"Доставка: {city}, {office}. Телефон для связи: {phone}. "
                "Я пришлю ТТН сюда, как только она будет создана."
            ),
            "en": (
                f"Thank you, payment received. Order #{order.order_number} is being prepared for {recipient}. "
                f"Delivery: {city}, {office}. Contact phone: {phone}. "
                "I will send the tracking number here as soon as it is created."
            ),
        }
        if amount:
            copies["uk"] += f" Сума: {amount} грн."
            copies["ru"] += f" Сумма: {amount} грн."
            copies["en"] += f" Amount: {amount} UAH."
        return copies[locale]
    if event.kind == IgLifecycleEvent.Kind.TTN_CREATED:
        ttn = str(payload.get("tracking_number") or "").strip()
        track_url = f"{NP_TRACKING_URL}{ttn}"
        copies = {
            "uk": f"Ваше замовлення #{order.order_number} підготовлено до відправлення.\nТТН: {ttn}\nВідстежити: {track_url}",
            "ru": f"Ваш заказ #{order.order_number} подготовлен к отправке.\nТТН: {ttn}\nОтследить: {track_url}",
            "en": f"Your order #{order.order_number} is ready for shipment.\nTracking number: {ttn}\nTrack it: {track_url}",
        }
        return copies[locale]
    copies = {
        "uk": "Дякуємо, що обрали TwoComms. Чи все добре із замовленням і чи вам сподобались речі? Якщо маєте хвилину, відмітьте @twocomms в Instagram або надішліть короткий чесний відгук. Це дуже допомагає нам розвиватися.",
        "ru": "Спасибо, что выбрали TwoComms. Все ли хорошо с заказом и понравились ли вам вещи? Если будет минутка, отметьте @twocomms в Instagram или отправьте короткий честный отзыв. Это очень помогает нам развиваться.",
        "en": "Thank you for choosing TwoComms. Did everything arrive correctly, and did you like the order? If you have a minute, tag @twocomms in an Instagram story or send a short honest review. It really helps us grow.",
    }
    return copies[locale]


@transaction.atomic
def ensure_lifecycle_event(order, kind, *, payload=None, due_at=None):
    """Create one event from committed order truth, or return the existing one."""
    context = _context_for_order(order)
    if context is None:
        return None, False
    payload = dict(payload or {})
    key = _event_key(order, kind, payload)
    event, created = IgLifecycleEvent.objects.get_or_create(
        event_key=key,
        defaults={
            "kind": kind,
            "client": context["client"],
            "deal": context["deal"],
            "proposal": context["proposal"],
            "order": order,
            "commercial_episode": context["episode"],
            "attribution": context["attribution"],
            "locale": _locale(getattr(context["client"], "language", "uk")),
            "payload": payload,
            "due_at": due_at or timezone.now(),
        },
    )
    return event, created


def _response_window_open(client, now):
    last_message_at = getattr(client, "last_message_at", None)
    return bool(last_message_at and now <= last_message_at + RESPONSE_WINDOW)


def _queue_manager_task(event: IgLifecycleEvent) -> None:
    """Persist one actionable, deterministic task for an out-of-window event."""
    from management.models import IgFollowUpTask

    reason = f"ig_lifecycle:{event.event_key}"
    IgFollowUpTask.objects.get_or_create(
        client=event.client,
        deal=event.deal,
        kind=IgFollowUpTask.Kind.MANAGER_TASK,
        reason=reason,
        defaults={
            "due_at": timezone.now(),
            "status": IgFollowUpTask.Status.PENDING,
            "level": 0,
            "message_text": _message(event),
            "meta_window_deadline": timezone.now(),
        },
    )


def _cancel_event(event_id: int, reason: str) -> str:
    with transaction.atomic():
        event = IgLifecycleEvent.objects.select_for_update().get(pk=event_id)
        if event.state in {
            IgLifecycleEvent.State.SENT,
            IgLifecycleEvent.State.CANCELLED,
        }:
            return event.state
        event.state = IgLifecycleEvent.State.CANCELLED
        event.lease_token = ""
        event.lease_expires_at = None
        event.last_error = reason[:1000]
        event.save(update_fields=[
            "state", "lease_token", "lease_expires_at", "last_error", "updated_at",
        ])
        return event.state


def _delivery_result(result):
    """Normalize legacy tuples and optional structured provider receipts."""
    provider_message_id = str(getattr(result, "provider_message_id", "") or "")
    if isinstance(result, tuple):
        if len(result) >= 4:
            ok, kind, hint, provider_message_id = result[:4]
        else:
            ok, kind, hint = result
    else:
        ok = bool(getattr(result, "ok", False))
        kind = str(getattr(result, "kind", "unknown") or "unknown")
        hint = str(getattr(result, "hint", "") or "")
    return bool(ok), str(kind or "unknown"), str(hint or ""), str(provider_message_id or "")


def dispatch_lifecycle_event(event_id: int) -> str:
    """Lease and deliver one event; return its durable state value."""
    now = timezone.now()
    lease = secrets.token_hex(24)
    with transaction.atomic():
        event = (
            IgLifecycleEvent.objects.select_for_update()
            .select_related("client", "order")
            .filter(pk=event_id)
            .first()
        )
        if event is None:
            return "missing"
        if event.state == IgLifecycleEvent.State.SENT:
            return event.state
        if event.state in {
            IgLifecycleEvent.State.CANCELLED,
            IgLifecycleEvent.State.MANAGER_REVIEW,
            IgLifecycleEvent.State.AMBIGUOUS,
            IgLifecycleEvent.State.FAILED,
        }:
            return event.state
        if event.due_at > now:
            return event.state
        if event.state == IgLifecycleEvent.State.PROCESSING and event.lease_expires_at and event.lease_expires_at > now:
            return event.state
        event.state = IgLifecycleEvent.State.PROCESSING
        event.lease_token = lease
        event.lease_expires_at = now + LEASE_DURATION
        event.attempts += 1
        event.last_error = ""
        event.save(update_fields=["state", "lease_token", "lease_expires_at", "attempts", "last_error", "updated_at"])

    try:
        from management.models import InstagramBotSettings
        from management.services.instagram_bot import send_text
        from management.services.ig_reply_boundary import (
            customer_send_boundary,
            reply_execution_boundary,
        )

        settings = InstagramBotSettings.load()
        with reply_execution_boundary(settings.pk, event.client_id) as permission:
            if not permission:
                if permission.reason == "global_reply_paused":
                    with transaction.atomic():
                        owned = IgLifecycleEvent.objects.select_for_update().get(pk=event_id)
                        if owned.lease_token == lease:
                            owned.state = IgLifecycleEvent.State.WAITING_WINDOW
                            owned.lease_token = ""
                            owned.lease_expires_at = None
                            owned.last_error = permission.reason
                            owned.due_at = now + timedelta(minutes=15)
                            owned.save(update_fields=[
                                "state", "lease_token", "lease_expires_at", "last_error", "due_at", "updated_at",
                            ])
                    return IgLifecycleEvent.State.WAITING_WINDOW
                return _cancel_event(event_id, permission.reason or "customer_send_not_allowed")

            if not _response_window_open(event.client, now):
                with transaction.atomic():
                    owned = IgLifecycleEvent.objects.select_for_update().get(pk=event_id)
                    if owned.lease_token != lease:
                        return owned.state
                    owned.state = IgLifecycleEvent.State.WAITING_WINDOW
                    owned.lease_token = ""
                    owned.lease_expires_at = None
                    owned.last_error = "standard_response_window_closed"
                    next_window = getattr(event.client, "last_message_at", None)
                    owned.due_at = max(
                        now + timedelta(minutes=15),
                        (next_window + RESPONSE_WINDOW) if next_window else now + timedelta(hours=6),
                    )
                    owned.save(update_fields=["state", "lease_token", "lease_expires_at", "last_error", "due_at", "updated_at"])
                _queue_manager_task(event)
                try:
                    from management.services.instagram_bot import notify_manager

                    notify_manager(
                        f"IG lifecycle event requires operator response: {event.kind} for order #{event.order.order_number}",
                        dedupe_key=f"ig-lifecycle:{event.event_key}",
                        event_type="ig_lifecycle_manager_review",
                        client=event.client,
                    )
                except Exception:
                    logger.exception("Unable to create manager review for lifecycle event %s", event_id)
                return IgLifecycleEvent.State.WAITING_WINDOW

            result = send_text(
                settings,
                event.client.igsid,
                _message(event),
                permission_boundary_factory=lambda: customer_send_boundary(
                    settings.pk, event.client_id, permission
                ),
                return_receipt=True,
            )
            ok, kind, hint, provider_message_id = _delivery_result(result)
    except Exception as exc:  # provider call is outside the transaction
        ok, kind, hint, provider_message_id = False, "unknown", repr(exc), ""

    needs_manager_review = (not ok and kind in {"unknown", "transient", "permanent"})
    with transaction.atomic():
        owned = IgLifecycleEvent.objects.select_for_update().get(pk=event_id)
        if owned.lease_token != lease:
            return owned.state
        owned.lease_token = ""
        owned.lease_expires_at = None
        if ok and provider_message_id:
            owned.state = IgLifecycleEvent.State.SENT
            owned.provider_message_id = provider_message_id[:128]
            owned.completed_at = timezone.now()
            owned.last_error = ""
        elif ok:
            owned.state = IgLifecycleEvent.State.AMBIGUOUS
            owned.last_error = "provider_message_id_missing"
            owned.due_at = timezone.now() + timedelta(hours=6)
        elif kind == "retryable" and owned.attempts < 3:
            owned.state = IgLifecycleEvent.State.PENDING
            owned.due_at = timezone.now() + timedelta(minutes=2 ** owned.attempts)
            owned.last_error = f"{kind}:{hint}"[:1000]
        elif kind in {"unknown", "transient"}:
            owned.state = IgLifecycleEvent.State.AMBIGUOUS
            owned.last_error = f"{kind}:{hint}"[:1000]
            owned.due_at = timezone.now() + timedelta(hours=6)
        else:
            owned.state = IgLifecycleEvent.State.FAILED
            owned.last_error = f"{kind}:{hint}"[:1000]
        owned.save(update_fields=[
            "state", "lease_token", "lease_expires_at", "provider_message_id",
            "completed_at", "last_error", "due_at", "updated_at",
        ])
        final_state = owned.state
    if needs_manager_review or final_state in {
        IgLifecycleEvent.State.AMBIGUOUS,
        IgLifecycleEvent.State.FAILED,
    }:
        _queue_manager_task(event)
        try:
            from management.services.instagram_bot import notify_manager

            notify_manager(
                f"IG lifecycle event needs review: {event.kind} for order #{event.order.order_number}",
                dedupe_key=f"ig-lifecycle:{event.event_key}",
                event_type="ig_lifecycle_manager_review",
                client=event.client,
            )
        except Exception:
            logger.exception("Unable to alert manager for lifecycle event %s", event_id)
    return final_state


def dispatch_due_lifecycle_events(limit: int = 50) -> int:
    """Bounded recovery hook for cron/daemon workers after request loss."""
    now = timezone.now()
    event_ids = list(
        IgLifecycleEvent.objects.filter(
            due_at__lte=now,
        ).filter(
            Q(state__in=[
                IgLifecycleEvent.State.PENDING,
                IgLifecycleEvent.State.WAITING_WINDOW,
            ])
            | Q(
                state=IgLifecycleEvent.State.PROCESSING,
                lease_expires_at__isnull=False,
                lease_expires_at__lte=now,
            )
        ).order_by("due_at", "id").values_list("id", flat=True)[:limit]
    )
    delivered = 0
    for event_id in event_ids:
        if dispatch_lifecycle_event(event_id) == IgLifecycleEvent.State.SENT:
            delivered += 1
    return delivered
