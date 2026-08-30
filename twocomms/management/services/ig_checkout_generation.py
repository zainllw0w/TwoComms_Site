"""Generation-scoped Assisted Checkout V2 provider and winner boundaries."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from management.services.ig_checkout_payment import (
    CheckoutPaymentError,
    _capture_attempt_tracking,
    _enqueue_invoice_created_alert_best_effort,
    _invoice_payload,
    _revalidate_frozen_proposal,
    _send_add_payment_info_if_missing,
    _snapshot,
    _validate_payload,
    release_attempt_promo,
)
from management.services.ig_checkout_policy import (
    GENERATION_TTL_SECONDS,
    PREPAY_200_AMOUNT,
    PROVIDER_VALIDITY_SECONDS,
    payment_choice_for_post,
)
from management.services.ig_inventory import (
    release_generation_inventory,
    reserve_proposal_inventory,
)
from orders.checkout_series import (
    assisted_checkout_v2_mode,
    build_checkout_series_identity,
)
from orders.models import PaymentAttempt


def _event(generation, kind, suffix, *, payload=None):
    from management.models import IgCheckoutInvoiceGenerationEvent

    return IgCheckoutInvoiceGenerationEvent.objects.get_or_create(
        event_key=(
            f"checkout-generation:{generation.pk}:{kind}:{suffix}"
        )[:180],
        defaults={
            "generation": generation,
            "proposal_id": generation.proposal_id,
            "payment_attempt_id": generation.payment_attempt_id,
            "kind": kind,
            "payload": payload if isinstance(payload, dict) else {},
        },
    )[0]


def generation_for_attempt(attempt_id):
    from management.models import IgCheckoutInvoiceGeneration

    return (
        IgCheckoutInvoiceGeneration.objects.select_related("proposal", "proposal__deal")
        .filter(payment_attempt_id=attempt_id)
        .first()
    )


def _lock_generation_graph(attempt_id):
    """Canonical Deal -> Proposal -> Generation -> Attempt lock order."""
    from management.models import (
        IgCheckoutInvoiceGeneration,
        IgCheckoutProposal,
        IgDeal,
    )

    locator = (
        IgCheckoutInvoiceGeneration.objects.filter(payment_attempt_id=attempt_id)
        .values("pk", "proposal_id", "proposal__deal_id")
        .first()
    )
    if locator is None:
        return None
    deal = IgDeal.objects.select_for_update().get(pk=locator["proposal__deal_id"])
    proposal = IgCheckoutProposal.objects.select_for_update().select_related(
        "client", "commercial_episode"
    ).get(pk=locator["proposal_id"], deal_id=deal.pk)
    generation = IgCheckoutInvoiceGeneration.objects.select_for_update().get(
        pk=locator["pk"], proposal_id=proposal.pk
    )
    attempt = PaymentAttempt.objects.select_for_update().get(
        pk=attempt_id,
        checkout_series_key=generation.series_key,
        checkout_generation=generation.generation,
    )
    generation._state.fields_cache["payment_attempt"] = attempt
    return deal, proposal, generation, attempt


def _attempt_fingerprint(
    proposal,
    generation_number,
    payment_choice,
    *,
    values,
):
    delivery = values["delivery"]
    payload = {
        "version": 2,
        "proposal": str(proposal.public_id),
        "revision": proposal.revision,
        "generation": generation_number,
        "payment_choice": payment_choice,
        "recipient": {
            "full_name": values["full_name"],
            "phone": values["phone"],
            "email": values["email"].lower(),
        },
        "delivery": {
            "settlement_ref": delivery.settlement_ref,
            "city_ref": delivery.city_ref,
            "warehouse_ref": delivery.warehouse_ref,
        },
        "promo": values["promo_code"],
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _clear_current_generation(proposal, generation, *, terminal_status):
    if proposal.current_invoice_generation_id != generation.pk:
        return
    proposal.current_invoice_generation = None
    if proposal.payment_attempt_id == generation.payment_attempt_id:
        proposal.payment_attempt = None
        proposal.details_locked_at = None
    if proposal.winner_invoice_generation_id:
        return
    proposal.status = (
        proposal.Status.VIEWED if proposal.viewed_at else proposal.Status.READY
    )
    proposal.save(
        update_fields=[
            "current_invoice_generation",
            "payment_attempt",
            "details_locked_at",
            "status",
            "updated_at",
        ]
    )


def _terminalize_locked_generation(
    proposal,
    generation,
    attempt,
    *,
    state,
    attempt_status,
    reason,
    now,
):
    generation.state = state
    generation.active_slot = None
    generation.terminal_at = now
    generation.review_reason = str(reason or "")[:96]
    generation.save(
        update_fields=[
            "state", "active_slot", "terminal_at", "review_reason", "updated_at",
        ]
    )
    if attempt.order_id is None and not attempt.checkout_winner_claimed:
        attempt.status = attempt_status
        attempt.error_reason = str(reason or attempt_status)[:500]
        attempt.last_status_at = now
        attempt.save(
            update_fields=["status", "error_reason", "last_status_at", "updated"]
        )
    _clear_current_generation(proposal, generation, terminal_status=state)
    released = release_generation_inventory(generation, reason=reason)
    released_promo = release_attempt_promo(attempt, reason=reason)
    _event(
        generation,
        "terminalized",
        f"{state}:{attempt.pk}",
        payload={
            "state": state,
            "reason": str(reason or "")[:96],
            "released_inventory": int(released or 0),
            "released_promo": bool(released_promo),
        },
    )


@transaction.atomic
def _prepare_generation(proposal, *, request, payload, grant_id=""):
    from management.models import (
        IgCheckoutInvoiceGeneration,
        IgCheckoutProposal,
        IgDeal,
    )

    deal = IgDeal.objects.select_for_update().get(pk=proposal.deal_id)
    locked = IgCheckoutProposal.objects.select_for_update().select_related(
        "client", "commercial_episode"
    ).get(pk=proposal.pk, deal_id=deal.pk)
    if not locked.assisted_checkout_v2:
        raise CheckoutPaymentError("unavailable", "V2 checkout is unavailable.")
    now = timezone.now()
    if locked.expires_at <= now or locked.status in {
        locked.Status.PAID,
        locked.Status.REVOKED,
        locked.Status.SUPERSEDED,
    }:
        raise CheckoutPaymentError("expired", "Срок действия предложения истек.")
    if locked.winner_invoice_generation_id:
        winner = IgCheckoutInvoiceGeneration.objects.select_for_update().filter(
            pk=locked.winner_invoice_generation_id,
            proposal_id=locked.pk,
        ).first()
        if winner and winner.payment_attempt_id:
            attempt = PaymentAttempt.objects.select_for_update().get(
                pk=winner.payment_attempt_id
            )
            if attempt.invoice_url:
                return locked, winner, attempt, None, True
        raise CheckoutPaymentError("unavailable", "Оплата вже обробляється.")

    if locked.current_invoice_generation_id:
        current = IgCheckoutInvoiceGeneration.objects.select_for_update().get(
            pk=locked.current_invoice_generation_id,
            proposal_id=locked.pk,
        )
        attempt = (
            PaymentAttempt.objects.select_for_update().get(
                pk=current.payment_attempt_id
            )
            if current.payment_attempt_id
            else None
        )
        if attempt is not None and attempt.invoice_url and current.expires_at > now:
            return locked, current, attempt, None, True
        if current.state in {
            current.State.PROVIDER_INFLIGHT,
            current.State.PROVIDER_AMBIGUOUS,
        }:
            raise CheckoutPaymentError(
                "provider_ambiguous",
                "Платіж уже передано банку. Не створюйте новий рахунок.",
            )
        if current.active_slot == 1 and current.expires_at > now:
            raise CheckoutPaymentError(
                "in_progress", "Платіж уже створюється. Зачекайте кілька секунд."
            )
        if attempt is not None and current.active_slot == 1:
            _terminalize_locked_generation(
                locked,
                current,
                attempt,
                state=current.State.EXPIRED,
                attempt_status=PaymentAttempt.Status.EXPIRED,
                reason="generation_expired",
                now=now,
            )

    # Disabling rollout stops creation of new provider generations while all
    # callbacks/reconciliation for existing rows continue to work below.
    if assisted_checkout_v2_mode() != "enforced":
        raise CheckoutPaymentError(
            "unavailable", "Створення нового рахунку тимчасово призупинено."
        )

    _revalidate_frozen_proposal(locked)
    try:
        payment_choice = payment_choice_for_post(
            locked,
            payload.get("payment_choice"),
        )
    except ValueError as exc:
        raise CheckoutPaymentError(
            "payment_choice",
            "Оберіть доступний спосіб оплати.",
            field="payment_choice",
        ) from exc
    values = _validate_payload(locked, payload, user=request.user)
    if (
        payment_choice
        == IgCheckoutInvoiceGeneration.PaymentChoice.PREPAY_200_COD
        and values["order_payable"] > Decimal(PREPAY_200_AMOUNT)
    ):
        payment_amount = Decimal(PREPAY_200_AMOUNT)
        attempt_pay_type = PaymentAttempt.PayType.PREPAY_200
    else:
        payment_choice = IgCheckoutInvoiceGeneration.PaymentChoice.FULL
        payment_amount = values["order_payable"]
        attempt_pay_type = PaymentAttempt.PayType.ONLINE_FULL

    generation_number = int(
        IgCheckoutInvoiceGeneration.objects.filter(proposal_id=locked.pk)
        .aggregate(value=Max("generation"))["value"]
        or 0
    ) + 1
    identity = build_checkout_series_identity(
        locked.public_id,
        generation=generation_number,
    )
    expires_at = min(
        locked.expires_at,
        now + timedelta(seconds=GENERATION_TTL_SECONDS),
    )
    generation = IgCheckoutInvoiceGeneration.objects.create(
        proposal=locked,
        generation=generation_number,
        series_key=identity.series_key,
        proposal_revision=locked.revision,
        active_slot=1,
        state=IgCheckoutInvoiceGeneration.State.PROVIDER_INFLIGHT,
        payment_choice=payment_choice,
        payment_amount=payment_amount,
        policy_evidence_message_id=locked.payment_policy_evidence_message_id,
        policy_evidence_kind=locked.payment_policy_evidence_kind,
        policy_evidence_digest=locked.payment_policy_evidence_digest,
        provider_call_token=secrets.token_hex(32),
        expires_at=expires_at,
        provider_started_at=now,
    )
    if not request.session.session_key:
        request.session.save()
    attempt = PaymentAttempt.objects.create(
        fingerprint=_attempt_fingerprint(
            locked,
            generation_number,
            payment_choice,
            values=values,
        ),
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key,
        full_name=values["full_name"],
        phone=values["phone"],
        email=values["email"],
        city=values["delivery"].city,
        np_office=values["delivery"].np_office,
        np_settlement_ref=values["delivery"].settlement_ref,
        np_city_ref=values["delivery"].city_ref,
        np_warehouse_ref=values["delivery"].warehouse_ref,
        pay_type=attempt_pay_type,
        status=PaymentAttempt.Status.PROCESSING,
        cart_snapshot={
            **_snapshot(locked),
            "checkout_generation_id": generation.pk,
            "checkout_series_key": identity.series_key,
        },
        gross_amount=locked.catalog_total,
        discount_amount=(
            Decimal(locked.negotiated_discount or 0)
            + values["promo_discount"]
        ),
        payable_amount=values["order_payable"],
        payment_amount=payment_amount,
        promo_code=values["promo"],
        event_state={
            **values["promo_event_state"],
            "checkout_generation_id": generation.pk,
            "provider_call_token": generation.provider_call_token,
        },
        invoice_expires_at=expires_at,
        checkout_series_key=identity.series_key,
        checkout_generation=generation_number,
    )
    tracking = _capture_attempt_tracking(request, attempt)
    if grant_id:
        tracking["ig_checkout_grant_id"] = str(grant_id)[:64]
        tracking["ig_checkout_generation_id"] = generation.pk
        attempt.tracking_payload = tracking
        attempt.save(update_fields=["tracking_payload", "updated"])
    generation.payment_attempt = attempt
    generation.save(update_fields=["payment_attempt", "updated_at"])
    locked.current_invoice_generation = generation
    locked.payment_attempt = attempt
    locked.status = locked.Status.DETAILS_LOCKED
    locked.details_locked_at = now
    locked.save(
        update_fields=[
            "current_invoice_generation", "payment_attempt", "status",
            "details_locked_at", "updated_at",
        ]
    )
    deal.np_full_name = values["full_name"]
    deal.np_phone = values["phone"]
    deal.np_city = values["delivery"].city
    deal.np_office = values["delivery"].np_office
    deal.np_settlement_ref = values["delivery"].settlement_ref
    deal.np_city_ref = values["delivery"].city_ref
    deal.np_warehouse_ref = values["delivery"].warehouse_ref
    deal.np_warehouse_kind = values["delivery"].warehouse_kind
    deal.delivery_status = deal.DeliveryStatus.VALIDATED
    deal.delivery_source = "instagram_checkout_v2"
    deal.status = deal.Status.AWAITING_PAYMENT
    deal.payment_status = "unpaid"
    deal.save(
        update_fields=[
            "np_full_name", "np_phone", "np_city", "np_office",
            "np_settlement_ref", "np_city_ref", "np_warehouse_ref",
            "np_warehouse_kind", "delivery_status", "delivery_source",
            "status", "payment_status", "updated_at",
        ]
    )
    reserve_proposal_inventory(
        locked,
        generation=generation,
        expires_at=expires_at,
    )
    _event(
        generation,
        "created",
        str(attempt.pk),
        payload={
            "generation": generation_number,
            "payment_choice": payment_choice,
            "expires_at": expires_at.isoformat(),
        },
    )
    _event(generation, "provider_started", str(attempt.pk))
    return locked, generation, attempt, values, False


@transaction.atomic
def _persist_provider_success(
    attempt_id,
    *,
    invoice_id,
    invoice_url,
    invoice_payload,
    creation,
):
    graph = _lock_generation_graph(attempt_id)
    if graph is None:
        raise CheckoutPaymentError("provider_ambiguous", "Generation ownership missing.")
    deal, proposal, generation, attempt = graph
    if generation.provider_invoice_id:
        if generation.provider_invoice_id != str(invoice_id):
            raise CheckoutPaymentError("provider_ambiguous", "Invoice identity conflict.")
        return proposal, generation, attempt
    now = timezone.now()
    generation.provider_invoice_id = str(invoice_id)[:128]
    generation.state = generation.State.INVOICE_CREATED
    generation.provider_completed_at = now
    generation.save(
        update_fields=[
            "provider_invoice_id", "state", "provider_completed_at", "updated_at",
        ]
    )
    event_state = dict(attempt.event_state or {})
    event_state.pop("invoice_creation_ambiguous", None)
    attempt.monobank_invoice_id = generation.provider_invoice_id
    attempt.invoice_url = str(invoice_url)[:600]
    attempt.invoice_payload = {
        "request": invoice_payload,
        "create": creation,
    }
    attempt.invoice_expires_at = generation.expires_at
    attempt.event_state = event_state
    attempt.status = PaymentAttempt.Status.PROCESSING
    attempt.last_status_at = now
    attempt.save(
        update_fields=[
            "monobank_invoice_id", "invoice_url", "invoice_payload",
            "invoice_expires_at", "event_state", "status", "last_status_at",
            "updated",
        ]
    )
    proposal.current_invoice_generation = generation
    proposal.payment_attempt = attempt
    proposal.status = proposal.Status.INVOICE_CREATED
    proposal.save(
        update_fields=[
            "current_invoice_generation", "payment_attempt", "status", "updated_at",
        ]
    )
    _event(
        generation,
        "provider_succeeded",
        generation.provider_invoice_id,
        payload={"provider_invoice_id": generation.provider_invoice_id},
    )
    return proposal, generation, attempt


@transaction.atomic
def _persist_provider_failure(attempt_id, *, ambiguous, reason):
    graph = _lock_generation_graph(attempt_id)
    if graph is None:
        return
    _deal, proposal, generation, attempt = graph
    now = timezone.now()
    if ambiguous:
        generation.state = generation.State.PROVIDER_AMBIGUOUS
        generation.review_reason = "provider_creation_ambiguous"
        generation.save(update_fields=["state", "review_reason", "updated_at"])
        event_state = dict(attempt.event_state or {})
        event_state["invoice_creation_ambiguous"] = True
        attempt.event_state = event_state
        attempt.error_reason = f"invoice_creation_ambiguous:{reason}"[:500]
        attempt.last_status_at = now
        attempt.save(
            update_fields=["event_state", "error_reason", "last_status_at", "updated"]
        )
        _event(generation, "provider_ambiguous", str(attempt.pk))
        return
    _terminalize_locked_generation(
        proposal,
        generation,
        attempt,
        state=generation.State.FAILED,
        attempt_status=PaymentAttempt.Status.FAILED,
        reason="invoice_creation_failed",
        now=now,
    )
    _event(generation, "provider_failed", str(attempt.pk))


def create_or_reuse_generation_invoice(
    proposal,
    *,
    request,
    payload,
    grant_id="",
):
    """Create one 25-minute invoice; provider I/O is outside transactions."""
    locked, generation, attempt, values, reused = _prepare_generation(
        proposal,
        request=request,
        payload=payload,
        grant_id=grant_id,
    )
    if reused:
        if attempt.invoice_url:
            _send_add_payment_info_if_missing(attempt, request)
            return attempt, attempt.invoice_url, True
        raise CheckoutPaymentError(
            "in_progress", "Платіж уже створюється. Зачекайте кілька секунд."
        )
    invoice_payload = _invoice_payload(
        request,
        attempt,
        locked,
        payment_amount=attempt.payment_amount,
        promo_discount=values["promo_discount"],
    )
    invoice_payload["validity"] = int(PROVIDER_VALIDITY_SECONDS)
    try:
        from storefront.views.monobank import _monobank_api_request

        creation = _monobank_api_request(
            "POST",
            "/api/merchant/invoice/create",
            json_payload=invoice_payload,
        )
        result = (
            creation.get("result")
            if isinstance(creation.get("result"), dict)
            else creation
        )
        invoice_id = result.get("invoiceId") or result.get("invoice_id")
        invoice_url = result.get("pageUrl") or result.get("invoiceUrl")
        if not invoice_id or not invoice_url:
            raise RuntimeError("Monobank returned an invalid invoice")
        locked, generation, attempt = _persist_provider_success(
            attempt.pk,
            invoice_id=invoice_id,
            invoice_url=invoice_url,
            invoice_payload=invoice_payload,
            creation=creation,
        )
    except CheckoutPaymentError:
        raise
    except Exception as exc:
        ambiguous = bool(getattr(exc, "ambiguous", True))
        _persist_provider_failure(
            attempt.pk,
            ambiguous=ambiguous,
            reason=str(exc),
        )
        if ambiguous:
            raise CheckoutPaymentError(
                "provider_ambiguous",
                "Не вдалося підтвердити відповідь банку. Не повторюйте оплату.",
            ) from exc
        raise CheckoutPaymentError(
            "provider_error",
            "Не вдалося створити платіж. Спробуйте ще раз пізніше.",
        ) from exc

    _send_add_payment_info_if_missing(attempt, request)
    _enqueue_invoice_created_alert_best_effort(locked, attempt)
    request.session["monobank_invoice_id"] = str(invoice_id)
    request.session["monobank_pending_attempt_id"] = attempt.pk
    request.session["monobank_attempt_id"] = attempt.pk
    request.session["ig_checkout_proposal_id"] = str(locked.public_id)
    request.session.modified = True
    return attempt, attempt.invoice_url, False


def terminalize_generation_attempt(
    attempt_id,
    *,
    terminal_status,
    reason,
    now=None,
    require_due=False,
):
    """Generation-scoped local/provider terminalization without proposal death."""
    now = now or timezone.now()
    with transaction.atomic():
        graph = _lock_generation_graph(attempt_id)
        if graph is None:
            return None
        _deal, proposal, generation, attempt = graph
        if attempt.order_id or generation.winner_slot == 1:
            return {"outcome": "protected_payment", "attempt_id": attempt.pk}
        if require_due and generation.expires_at > now:
            return {"outcome": "not_due", "attempt_id": attempt.pk}
        if generation.state == generation.State.PROVIDER_AMBIGUOUS:
            return {"outcome": "provider_ambiguous", "attempt_id": attempt.pk}
        state = (
            generation.State.EXPIRED
            if terminal_status == PaymentAttempt.Status.EXPIRED
            else generation.State.CANCELLED
            if terminal_status == PaymentAttempt.Status.CANCELLED
            else generation.State.FAILED
        )
        _terminalize_locked_generation(
            proposal,
            generation,
            attempt,
            state=state,
            attempt_status=terminal_status,
            reason=reason,
            now=now,
        )
        return {"outcome": "terminalized", "attempt_id": attempt.pk}
