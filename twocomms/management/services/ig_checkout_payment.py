"""Server-side payment adapter for Instagram checkout proposals.

The proposal is the commercial snapshot.  This module only turns a validated,
first-submit recipient into the existing ``PaymentAttempt`` contract; it never
accepts a client-supplied amount or cart.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from orders.models import PaymentAttempt
from orders.nova_poshta_checkout import NovaPoshtaSelectionError, resolve_delivery_selection
from orders.nova_poshta_documents import normalize_checkout_phone
from storefront.models import PromoCode

logger = logging.getLogger("management.ig_checkout_payment")


class CheckoutPaymentError(ValueError):
    """A safe, user-facing validation or lifecycle error."""

    def __init__(self, code: str, message: str, *, field: str = ""):
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message


def _clean(value, limit=255):
    return " ".join(str(value or "").split())[:limit]


def _fingerprint(proposal, *, full_name, phone, email, delivery, promo_code):
    payload = {
        "version": 1,
        "proposal": str(proposal.public_id),
        "revision": proposal.revision,
        "recipient": {
            "full_name": full_name,
            "phone": phone,
            "email": email.lower(),
        },
        "delivery": {
            "city": delivery.city,
            "office": delivery.np_office,
            "settlement_ref": delivery.settlement_ref,
            "city_ref": delivery.city_ref,
            "warehouse_ref": delivery.warehouse_ref,
        },
        "promo": promo_code,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _proposal_basket(proposal, *, promo_discount=Decimal("0.00")):
    basket = []
    for item in proposal.items.all():
        basket.append({
            "name": _clean(item.product_title, 128),
            "qty": int(item.quantity or 1),
            "sum": int((Decimal(item.quoted_line_total) * 100).to_integral_value()),
            "unit": "шт",
        })
    total_discount = Decimal(proposal.negotiated_discount or 0) + promo_discount
    if total_discount > 0:
        basket.append({
            "name": "Знижка",
            "qty": 1,
            "sum": -int((total_discount * 100).to_integral_value()),
            "unit": "шт",
        })
    return basket[:30]


def _invoice_payload(request, attempt, proposal, *, payment_amount, promo_discount):
    description = f"Оплата замовлення {attempt.reference} на суму {payment_amount:.2f} грн."
    public_base = getattr(settings, "MONOBANK_PUBLIC_BASE_URL", "").rstrip("/")
    if public_base:
        return_url = f"{public_base}{reverse('monobank_return')}?attemptId={attempt.pk}"
        webhook_url = f"{public_base}{reverse('monobank_webhook')}"
    else:
        return_url = request.build_absolute_uri(f"{reverse('monobank_return')}?attemptId={attempt.pk}")
        webhook_url = request.build_absolute_uri(reverse("monobank_webhook"))
    merchant_info = {
        "reference": attempt.reference,
        "destination": description,
        "basketOrder": _proposal_basket(proposal, promo_discount=promo_discount),
    }
    if attempt.email:
        # Monobank accepts receipt addresses in merchantPaymInfo.  The field
        # is optional, so checkout still works when the customer skips email.
        merchant_info["customerEmails"] = [attempt.email]
    return {
        "amount": int((payment_amount * 100).to_integral_value()),
        "ccy": 980,
        "merchantPaymInfo": merchant_info,
        "redirectUrl": return_url,
        "webHookUrl": webhook_url,
    }


def _validate_payload(proposal, payload):
    full_name = _clean(payload.get("full_name"), 200)
    if len(full_name.split()) < 2:
        raise CheckoutPaymentError("full_name", "Вкажіть ім'я та прізвище.", field="full_name")

    raw_phone = _clean(payload.get("phone"), 32)
    phone = normalize_checkout_phone(raw_phone)
    if not phone:
        raise CheckoutPaymentError(
            "phone", "Вкажіть коректний український номер телефону.", field="phone"
        )

    email = _clean(payload.get("email"), 254)
    if email:
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CheckoutPaymentError("email", "Перевірте email для чека.", field="email") from exc

    try:
        delivery = resolve_delivery_selection(payload)
    except NovaPoshtaSelectionError as exc:
        raise CheckoutPaymentError(exc.field, exc.message, field=exc.field) from exc

    promo_code = _clean(payload.get("promo_code"), 32).upper()
    promo = None
    promo_discount = Decimal("0.00")
    if promo_code:
        if not proposal.allow_promo:
            raise CheckoutPaymentError("promo_unavailable", "Промокод для этого предложения недоступен.", field="promo_code")
        promo = PromoCode.objects.select_for_update().filter(code__iexact=promo_code).first()
        if promo is None or not promo.can_be_used():
            raise CheckoutPaymentError("promo_invalid", "Промокод недействителен или уже использован.", field="promo_code")
        if promo.one_time_per_user:
            raise CheckoutPaymentError("promo_requires_account", "Этот промокод доступен только в личном кабинете.", field="promo_code")
        promo_discount = min(
            Decimal(str(promo.calculate_discount(proposal.requested_payment_amount))),
            Decimal(proposal.requested_payment_amount),
        )

    payable = max(Decimal(proposal.requested_payment_amount) - promo_discount, Decimal("0.00"))
    if payable <= 0:
        raise CheckoutPaymentError("invalid_amount", "Сумма заказа должна быть больше нуля.")
    return {
        "full_name": full_name,
        "phone": phone,
        "email": email,
        "delivery": delivery,
        "promo": promo,
        "promo_code": promo_code,
        "promo_discount": promo_discount,
        "payable": payable,
    }


def _snapshot(proposal):
    items = []
    for item in proposal.items.all():
        if not item.product_id:
            raise CheckoutPaymentError("item_unavailable", "Один из товаров больше недоступен.")
        items.append({
            "product_id": item.product_id,
            "title": item.product_title,
            "qty": int(item.quantity or 1),
            "size": item.size or "",
            "fit_option_code": item.fit_code or "",
            "fit_option_label": item.fit_label or "",
            "color_variant_id": item.color_variant_id,
            "option_values": item.option_values or {},
            "option_labels": item.option_labels or {},
            "unit_price": str(item.quoted_unit_price),
            "line_total": str(item.quoted_line_total),
        })
    if not items:
        raise CheckoutPaymentError("empty_items", "В предложении нет товаров.")
    # This metadata is server-owned and travels with the frozen attempt.  The
    # generic PaymentAttempt materializer uses it to preserve the commercial
    # source on the canonical Order without coupling orders back to IG models.
    return {
        "cart": items,
        "custom_print_lead_ids": [],
        "checkout_surface": "instagram_proposal",
        "sale_source": "Instagram",
        "proposal_id": str(proposal.public_id),
    }


@transaction.atomic
def lock_proposal_details(proposal, *, payload, request):
    """Validate and persist first-submit-wins recipient data."""
    from management.models import IgCheckoutProposal

    locked = IgCheckoutProposal.objects.select_for_update().select_related(
        "payment_attempt", "deal", "client", "commercial_episode"
    ).get(pk=proposal.pk)
    now = timezone.now()
    if locked.expires_at <= now:
        raise CheckoutPaymentError("expired", "Срок действия предложения истек.")
    if locked.status in {
        locked.Status.PAID,
        locked.Status.INVOICE_CREATED,
        locked.Status.DETAILS_LOCKED,
    } and locked.payment_attempt_id:
        attempt = locked.payment_attempt
        if attempt.invoice_url:
            return locked, attempt, None, True
        if attempt.status in {PaymentAttempt.Status.INITIATED, PaymentAttempt.Status.PROCESSING}:
            raise CheckoutPaymentError("in_progress", "Платеж уже создается. Подождите несколько секунд.")
    if locked.status not in {locked.Status.READY, locked.Status.VIEWED}:
        raise CheckoutPaymentError("unavailable", "Это предложение больше нельзя оплатить.")

    values = _validate_payload(locked, payload)
    if not request.session.session_key:
        request.session.save()
    fingerprint = _fingerprint(
        locked,
        full_name=values["full_name"],
        phone=values["phone"],
        email=values["email"],
        delivery=values["delivery"],
        promo_code=values["promo_code"],
    )
    existing = PaymentAttempt.objects.select_for_update().filter(fingerprint=fingerprint).first()
    if existing:
        if existing.invoice_url:
            locked.payment_attempt = existing
            locked.status = locked.Status.INVOICE_CREATED
            locked.save(update_fields=["payment_attempt", "status", "updated_at"])
            return locked, existing, values, True
        raise CheckoutPaymentError("in_progress", "Платеж уже создается. Подождите несколько секунд.")

    attempt = PaymentAttempt.objects.create(
        fingerprint=fingerprint,
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key,
        full_name=values["full_name"],
        phone=values["phone"],
        email=values["email"] or None,
        city=values["delivery"].city,
        np_office=values["delivery"].np_office,
        np_settlement_ref=values["delivery"].settlement_ref,
        np_city_ref=values["delivery"].city_ref,
        np_warehouse_ref=values["delivery"].warehouse_ref,
        pay_type=PaymentAttempt.PayType.ONLINE_FULL,
        cart_snapshot=_snapshot(locked),
        gross_amount=locked.catalog_total,
        discount_amount=Decimal(locked.negotiated_discount or 0) + values["promo_discount"],
        payable_amount=values["payable"],
        payment_amount=values["payable"],
        promo_code=values["promo"],
    )
    locked.payment_attempt = attempt
    locked.status = locked.Status.DETAILS_LOCKED
    locked.details_locked_at = now
    locked.deal.np_full_name = values["full_name"]
    locked.deal.np_phone = values["phone"]
    locked.deal.np_city = values["delivery"].city
    locked.deal.np_office = values["delivery"].np_office
    locked.deal.np_settlement_ref = values["delivery"].settlement_ref
    locked.deal.np_city_ref = values["delivery"].city_ref
    locked.deal.np_warehouse_ref = values["delivery"].warehouse_ref
    locked.deal.np_warehouse_kind = values["delivery"].warehouse_kind
    locked.deal.delivery_status = locked.deal.DeliveryStatus.VALIDATED
    locked.deal.delivery_source = "instagram_checkout"
    locked.deal.status = locked.deal.Status.AWAITING_PAYMENT
    locked.deal.payment_status = "unpaid"
    locked.deal.save(update_fields=[
        "np_full_name", "np_phone", "np_city", "np_office", "np_settlement_ref",
        "np_city_ref", "np_warehouse_ref", "np_warehouse_kind", "delivery_status",
        "delivery_source", "status", "payment_status", "updated_at",
    ])
    locked.save(update_fields=["payment_attempt", "status", "details_locked_at", "updated_at"])
    return locked, attempt, values, False


def create_or_reuse_invoice(proposal, *, request, payload):
    """Create one standard Monobank invoice for a proposal."""
    from storefront.views.monobank import _monobank_api_request

    locked, attempt, values, reused = lock_proposal_details(proposal, payload=payload, request=request)
    if reused and attempt.invoice_url:
        return attempt, attempt.invoice_url, True
    if values is None:
        raise CheckoutPaymentError("in_progress", "Платеж уже создается. Подождите несколько секунд.")

    invoice_payload = _invoice_payload(
        request,
        attempt,
        locked,
        payment_amount=values["payable"],
        promo_discount=values["promo_discount"],
    )
    try:
        creation = _monobank_api_request(
            "POST", "/api/merchant/invoice/create", json_payload=invoice_payload
        )
        result = creation.get("result") if isinstance(creation.get("result"), dict) else creation
        invoice_id = result.get("invoiceId") or result.get("invoice_id")
        invoice_url = result.get("pageUrl") or result.get("invoiceUrl")
        if not invoice_id or not invoice_url:
            raise RuntimeError("Monobank returned an invalid invoice")
    except Exception as exc:
        PaymentAttempt.objects.filter(pk=attempt.pk).update(
            status=PaymentAttempt.Status.FAILED,
            error_reason=str(exc)[:500],
            last_status_at=timezone.now(),
        )
        from management.models import IgCheckoutProposal
        locked.refresh_from_db()
        locked.status = IgCheckoutProposal.Status.READY
        locked.payment_attempt = None
        locked.details_locked_at = None
        locked.save(update_fields=["status", "payment_attempt", "details_locked_at", "updated_at"])
        raise CheckoutPaymentError("provider_error", "Не удалось создать платеж. Попробуйте еще раз.") from exc

    tracking = {}
    try:
        from storefront.utm_tracking import build_order_tracking_context
        tracking = build_order_tracking_context(request, attempt) or {}
    except Exception:
        logger.warning("Unable to build IG checkout tracking context", exc_info=True)
    tracking["external_id"] = tracking.get("external_id") or (
        f"user:{request.user.pk}" if request.user.is_authenticated else f"session:{request.session.session_key}"
    )
    tracking["add_payment_event_id"] = attempt.add_payment_event_id
    now = timezone.now()
    PaymentAttempt.objects.filter(pk=attempt.pk).update(
        monobank_invoice_id=str(invoice_id)[:128],
        invoice_url=str(invoice_url)[:600],
        invoice_payload={"request": invoice_payload, "create": creation},
        tracking_payload=tracking,
        invoice_expires_at=min(locked.expires_at, now + timedelta(hours=24)),
        status=PaymentAttempt.Status.PROCESSING,
        last_status_at=now,
    )
    from management.models import IgCheckoutProposal
    locked.refresh_from_db()
    locked.status = IgCheckoutProposal.Status.INVOICE_CREATED
    locked.save(update_fields=["status", "updated_at"])
    request.session["monobank_invoice_id"] = str(invoice_id)
    request.session["monobank_pending_attempt_id"] = attempt.pk
    request.session["monobank_attempt_id"] = attempt.pk
    request.session["ig_checkout_proposal_id"] = str(locked.public_id)
    request.session.modified = True

    try:
        from orders.facebook_conversions_service import get_facebook_conversions_service
        get_facebook_conversions_service().send_add_payment_info_event(
            order=attempt,
            payment_amount=float(values["payable"]),
            event_id=attempt.add_payment_event_id,
            source_url=request.build_absolute_uri(),
        )
    except Exception:
        logger.warning("Failed to send IG AddPaymentInfo for attempt %s", attempt.pk, exc_info=True)
    try:
        from orders.telegram_notifications import TelegramNotifier
        TelegramNotifier().send_payment_attempt_notification(attempt)
    except Exception:
        logger.warning("Failed to send IG payment attempt notification %s", attempt.pk, exc_info=True)
    attempt.refresh_from_db()
    return attempt, attempt.invoice_url, False


@transaction.atomic
def bind_verified_payment(attempt_id, order):
    """Bind a verified PaymentAttempt/Order to proposal and Instagram truth."""
    from management.models import (
        IgCheckoutProposal,
        IgDeal,
        IgLifecycleEvent,
        IgClient,
        IgPaymentEvent,
        IgPaymentProjection,
        provider_evidence_signature,
    )
    from management.services.ig_order_links import create_order_attribution

    proposal = (
        IgCheckoutProposal.objects.select_for_update()
        .select_related("deal", "client", "commercial_episode", "payment_attempt")
        .filter(payment_attempt_id=attempt_id)
        .first()
    )
    if proposal is None:
        return None
    attempt = proposal.payment_attempt
    deal = IgDeal.objects.select_for_update().get(pk=proposal.deal_id)
    now = timezone.now()

    # The generic PaymentAttempt converter has already verified the provider
    # result. Persist that evidence into the IG append-only projection so CRM
    # aggregates and later reconciliation use the same trusted boundary.
    paid_amount = Decimal(attempt.paid_amount or attempt.payment_amount or 0).quantize(Decimal("0.01"))
    evidence_payload = {
        "attempt_id": attempt.pk,
        "attempt_reference": attempt.reference,
        "invoice_id": attempt.monobank_invoice_id,
        "status": "success",
        "amount": str(paid_amount),
    }
    payload_digest = hashlib.sha256(
        json.dumps(evidence_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    source = "provider_attempt"
    signature = provider_evidence_signature(
        deal_id=deal.pk,
        client_id=deal.client_id,
        provider="monobank",
        source=source,
        invoice_id=attempt.monobank_invoice_id,
        provider_status="success",
        payload_digest=payload_digest,
    )
    evidence_payload["signature"] = signature
    payment_event, _ = IgPaymentEvent.objects.get_or_create(
        event_key=f"attempt:{attempt.pk}:verified",
        defaults={
            "deal": deal,
            "client": deal.client,
            "provider": "monobank",
            "source": source,
            "invoice_id": attempt.monobank_invoice_id[:128],
            "provider_status": "success",
            "provider_modified_at": attempt.last_status_at or now,
            "gross_amount": paid_amount,
            "final_amount": paid_amount,
            "refunded_amount": Decimal("0.00"),
            "amount_valid": True,
            "currency": proposal.currency or "UAH",
            "evidence": evidence_payload,
            "payload_digest": payload_digest,
        },
    )
    projection, _ = IgPaymentProjection.objects.get_or_create(
        deal=deal,
        defaults={"client": deal.client},
    )
    projection.client = deal.client
    projection.truth = IgDeal.PaymentTruth.CONFIRMED
    projection.gross_amount = paid_amount
    projection.refunded_amount = Decimal("0.00")
    projection.paid_at = projection.paid_at or deal.paid_at or now
    projection.provider_modified_at = attempt.last_status_at or now
    projection.last_event = payment_event
    projection.needs_reconciliation = False
    projection.reconciled_at = now
    projection.save()
    attribution = create_order_attribution(
        order,
        client=proposal.client,
        deal=deal,
        creation_mode="provider_auto",
        payment_source="provider_attempt",
    )
    # ``IgCheckoutProposal.save`` requires a converted attempt before it will
    # accept the paid state.  The Order is already durably materialized by the
    # provider adapter, so this is the final conversion marker rather than a
    # second payment transition.
    if attempt.status != PaymentAttempt.Status.CONVERTED:
        attempt.status = PaymentAttempt.Status.CONVERTED
        attempt.save(update_fields=["status", "updated"])
    deal.order_id = order.pk
    deal.status = deal.Status.ORDER_CREATED
    deal.payment_status = "prepaid" if attempt.pay_type == PaymentAttempt.PayType.PREPAY_200 else "paid"
    deal.payment_truth = deal.PaymentTruth.CONFIRMED
    deal.paid_amount = attempt.paid_amount or attempt.payment_amount
    deal.paid_at = deal.paid_at or now
    deal.payment_truth_updated_at = now
    deal.save(update_fields=[
        "order", "status", "payment_status", "payment_truth", "paid_amount", "paid_at",
        "payment_truth_updated_at", "updated_at",
    ])
    proposal.status = proposal.Status.PAID
    proposal.paid_at = proposal.paid_at or now
    proposal.save(update_fields=["status", "paid_at", "updated_at"])
    event, _created = IgLifecycleEvent.objects.get_or_create(
        event_key=f"payment:{attempt.pk}:verified",
        defaults={
            "kind": IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            "client": proposal.client,
            "deal": deal,
            "proposal": proposal,
            "order": order,
            "commercial_episode": proposal.commercial_episode,
            "attribution": attribution,
            "locale": proposal.locale,
            "payload": {
                "attempt_id": attempt.pk,
                "attempt_reference": attempt.reference,
                "amount": str(attempt.paid_amount or attempt.payment_amount),
                "currency": proposal.currency,
            },
        },
    )
    # The durable event is committed with payment truth; only then may the
    # Instagram adapter call Meta. Replays claim the same event idempotently.
    from management.services.ig_lifecycle import dispatch_lifecycle_event

    transaction.on_commit(lambda event_id=event.pk: dispatch_lifecycle_event(event_id))
    try:
        proposal.client.set_stage(IgClient.Stage.ORDER_CREATED, reason="instagram_checkout_paid")
    except Exception:
        logger.warning("Failed to advance IG client stage for proposal %s", proposal.pk, exc_info=True)
    try:
        from management.services.bot_payment_truth import recalculate_client_payment_aggregates

        recalculate_client_payment_aggregates(proposal.client)
    except Exception:
        logger.warning("Failed to refresh IG payment aggregates for proposal %s", proposal.pk, exc_info=True)
    try:
        from management.services.ig_commercial_episodes import sync_episode_payment

        sync_episode_payment(deal=deal)
    except Exception:
        logger.warning("Failed to refresh IG episode payment for deal %s", deal.pk, exc_info=True)
    return event
