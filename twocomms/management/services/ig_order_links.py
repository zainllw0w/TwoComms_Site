from __future__ import annotations

from decimal import Decimal
import hashlib
import hmac
import json
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone


OVERRIDE_REASON_CODES = frozenset({
    "total_mismatch",
    "phone_mismatch",
    "items_mismatch",
    "manual_review",
})


def identity_digest(igsid: str) -> str:
    """Return a non-reversible, secret-bound Instagram identity digest."""
    value = str(igsid or "").strip()
    if not value:
        return ""
    key = str(getattr(settings, "SECRET_KEY", "")).encode("utf-8")
    return hmac.new(key, ("instagram:" + value).encode("utf-8"), hashlib.sha256).hexdigest()


def _reason_code(value, mismatches):
    candidate = str(value or "").strip().lower()
    if candidate in OVERRIDE_REASON_CODES:
        return candidate
    if "items" in mismatches:
        return "items_mismatch"
    if "phone" in mismatches:
        return "phone_mismatch"
    if "total" in mismatches:
        return "total_mismatch"
    return "manual_review"


def authoritative_manager_decision(review):
    from management.ig_bot_models import IgPaymentReviewDecision

    if not review or review.status != review.Status.CONFIRMED:
        return None
    decision = review.decisions.order_by("-id").first()
    if not decision:
        return None
    if decision.decision != IgPaymentReviewDecision.Decision.MANAGER_VERIFIED:
        return None
    if decision.verification_source != "manager":
        return None
    if decision.actor_source not in {
        IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
        IgPaymentReviewDecision.ActorSource.TELEGRAM_USER,
    }:
        return None
    if not str(decision.actor_external_id or "").strip():
        return None
    return decision


def _item_snapshot(items):
    result = []
    for item in items:
        result.append({
            "product_id": item.product_id,
            "color_variant_id": item.color_variant_id,
            "title": item.title,
            "size": item.size or "",
            "fit_option_code": getattr(item, "fit_option_code", "") or "",
            "fit_option_label": getattr(item, "fit_option_label", "") or "",
            "option_values": getattr(item, "option_values", {}) or {},
            "option_labels": getattr(item, "option_labels", {}) or {},
            "qty": item.qty,
            "unit_price": str(item.unit_price),
            "line_total": str(item.line_total),
            "price_source": getattr(item, "price_source", "") or "",
            "price_evidence_message_ids": getattr(item, "price_evidence_message_ids", []) or [],
        })
    return result


def create_order_attribution(
    order,
    *,
    client,
    creation_mode,
    payment_source,
    deal=None,
    review=None,
    manager_decision=None,
    created_by=None,
):
    from management.ig_bot_models import IgOrderAttribution

    deal_items = list(deal.items.all()) if deal is not None else []
    source_items = deal_items or list(order.items.all())
    evidence_ids = []
    price_sources = []
    for item in source_items:
        price_sources.append(getattr(item, "price_source", "") or "")
        evidence_ids.extend(getattr(item, "price_evidence_message_ids", []) or [])
    attribution, _created = IgOrderAttribution.objects.get_or_create(
        order=order,
        defaults={
            "client": client,
            "deal": deal,
            "payment_review": review,
            "manager_decision": manager_decision,
            "creation_mode": creation_mode,
            "payment_source": payment_source,
            "identity_digest": identity_digest(client.igsid),
            "evidence_watermark_message_id": getattr(review, "watermark_message_id", 0) or 0,
            "item_provenance": _item_snapshot(source_items),
            "negotiated_total": getattr(deal, "amount", None) or getattr(order, "total_sum", None),
            "price_source": (
                "mixed"
                if len({value for value in price_sources if value}) > 1
                else next((value for value in price_sources if value), "")
            ),
            "price_evidence_message_ids": sorted({int(value) for value in evidence_ids if str(value).isdigit()}),
            "created_by": created_by,
        },
    )
    if attribution.client_id != client.pk:
        raise ValueError("Замовлення вже прив'язано до іншого Instagram-клієнта")
    return attribution


def _find_order_exact(identifier):
    from orders.models import Order

    value = str(identifier or "").strip()
    if not value:
        raise ValueError("Вкажіть точний номер замовлення")
    return Order.objects.select_for_update().filter(order_number=value).first()


def _commercial_fingerprint(item):
    return (
        int(item.product_id or 0),
        int(item.color_variant_id or 0),
        str(item.title or "").strip().casefold(),
        str(item.size or "").strip().casefold(),
        str(getattr(item, "fit_option_code", "") or "").strip().casefold(),
        json.dumps(
            getattr(item, "option_values", {}) or {},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        int(item.qty or 0),
        str(Decimal(item.unit_price or 0).quantize(Decimal("0.01"))),
    )


@transaction.atomic
def link_existing_order_to_review(review, *, order_identifier, actor, override_reason=""):
    from management.ig_bot_models import (
        IgDeal,
        IgOrderAttribution,
        IgOrderLinkEvent,
        IgPaymentConfirmationReview,
    )

    locked_review = (
        IgPaymentConfirmationReview.objects.select_for_update()
        .select_related("client", "deal", "order")
        .get(pk=review.pk)
    )
    client = locked_review.client
    if client.hidden_at:
        raise ValueError("Прихований клієнт виключений з операцій")
    if locked_review.status != locked_review.Status.CONFIRMED:
        raise ValueError("Перевірка оплати не підтверджена")
    decision = authoritative_manager_decision(locked_review)
    if not decision:
        raise ValueError("Потрібне source-qualified рішення менеджера")

    order = _find_order_exact(order_identifier)
    if not order:
        raise ValueError("Замовлення з таким точним номером не знайдено")
    if locked_review.order_id and locked_review.order_id != order.pk:
        raise ValueError("Перевірку вже прив'язано до іншого замовлення")

    attribution = IgOrderAttribution.objects.select_for_update().filter(order=order).first()
    if attribution and attribution.client_id != client.pk:
        raise ValueError("Замовлення вже прив'язано до іншого Instagram-клієнта")
    if locked_review.deal_id:
        existing_deals = IgDeal.objects.filter(order=order).exclude(pk=locked_review.deal_id)
        if existing_deals.filter(client_id=client.pk).exists():
            raise ValueError("Замовлення вже пов'язано з іншою угодою цього клієнта")
        if existing_deals.exists():
            raise ValueError("Замовлення вже прив'язано до іншого Instagram-клієнта")
    if IgPaymentConfirmationReview.objects.filter(order=order).exclude(client_id=client.pk).exists():
        raise ValueError("Замовлення вже прив'язано до іншого Instagram-клієнта")
    if (
        locked_review.deal_id
        and locked_review.deal.order_id
        and locked_review.deal.order_id != order.pk
    ):
        raise ValueError("Угоду вже прив'язано до іншого замовлення")

    # A repeated exact link is idempotent even when the first attempt used an
    # override reason that is not repeated by the UI/browser retry.
    if locked_review.order_id == order.pk:
        return order

    mismatches = {}
    if locked_review.deal_id:
        expected = Decimal(locked_review.deal.amount or 0)
        actual = Decimal(order.total_sum or 0)
        if expected != actual:
            mismatches["total"] = {"review": str(expected), "order": str(actual)}
        deal_phone = re.sub(r"\D", "", locked_review.deal.np_phone or "")
        order_phone = re.sub(r"\D", "", order.phone or "")
        if deal_phone and order_phone and deal_phone != order_phone:
            mismatches["phone"] = {"mismatch": True}
        deal_items = sorted(_commercial_fingerprint(item) for item in locked_review.deal.items.all())
        order_items = sorted(_commercial_fingerprint(item) for item in order.items.all())
        if deal_items != order_items:
            mismatches["items"] = {
                "review": [list(value) for value in deal_items],
                "order": [list(value) for value in order_items],
            }
    if mismatches and not str(override_reason or "").strip():
        raise ValueError("Дані замовлення не збігаються; потрібна причина override")
    reason_code = _reason_code(override_reason, mismatches)

    if not attribution:
        attribution = create_order_attribution(
            order,
            client=client,
            deal=locked_review.deal,
            review=locked_review,
            manager_decision=decision,
            creation_mode="linked_existing",
            payment_source="manager_verified",
            created_by=actor,
        )
    locked_review.order = order
    locked_review.save(update_fields=["order", "updated_at"])
    if locked_review.deal_id:
        locked_review.deal.order = order
        locked_review.deal.status = IgDeal.Status.ORDER_CREATED
        locked_review.deal.order_truth_updated_at = timezone.now()
        locked_review.deal.save(update_fields=[
            "order", "status", "order_truth_updated_at", "updated_at",
        ])
    IgOrderLinkEvent.objects.get_or_create(
        order=order,
        review=locked_review,
        event_kind="linked",
        defaults={
            "client": client,
            "actor": actor,
            "reason_code": reason_code,
            "mismatch_snapshot": mismatches,
        },
    )
    return order
