"""
Створення замовлення (orders.Order) з угоди IG-бота (management.IgDeal).

Викликається ПІСЛЯ підтвердженої оплати (рішення Q2). Ідемпотентно: одна угода →
одне замовлення. Дані Нової Пошти зберігаються текстом (Q3=a), ТТН оформлює
менеджер. Спільного сервісу створення замовлень у проєкті не було (логіка
дублювалась у checkout/monobank-в'ю) — це перша переюзабельна точка для бота.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone


def _ensure_purchase_action(order, deal_id):
    from storefront.utm_tracking import ensure_order_purchase_action

    return ensure_order_purchase_action(
        order,
        metadata={
            'source': 'instagram_deal',
            'ig_deal_id': deal_id,
        },
    )


def create_order_from_deal(deal, *, created_by=None):
    """Створює Order + OrderItem з оплаченої угоди. Повертає Order.
    Якщо замовлення для угоди вже є — повертає його (ідемпотентність)."""
    if deal.order_id:
        from management.ig_bot_models import IgPaymentConfirmationReview, IgPaymentProjection
        from management.services.ig_order_links import (
            authoritative_manager_decision,
            create_order_attribution,
        )
        from management.services.bot_payment_truth import verified_payment_deals

        projection = IgPaymentProjection.objects.filter(deal_id=deal.pk).first()
        review = IgPaymentConfirmationReview.objects.filter(
            deal_id=deal.pk,
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
        ).order_by("-id").first()
        decision = authoritative_manager_decision(review) if review else None
        provider_verified = bool(
            projection and projection.truth in {"confirmed", "partially_refunded"}
        )
        legacy_verified = bool(
            projection is None
            and verified_payment_deals(deal.__class__.objects.filter(pk=deal.pk)).exists()
        )
        if not provider_verified and not legacy_verified and not decision:
            raise ValueError(
                "IG order requires provider-confirmed payment or source-qualified manager decision"
            )
        create_order_attribution(
            deal.order,
            client=deal.client,
            deal=deal,
            review=review if decision else None,
            manager_decision=decision,
            creation_mode=(
                "provider_auto" if provider_verified
                else "manager_review" if decision
                else "provider_auto" if legacy_verified
                else "linked_existing"
            ),
            payment_source=(
                "provider_projection" if provider_verified
                else "manager_verified" if decision
                else "provider_attempt" if legacy_verified
                else "unknown"
            ),
            created_by=created_by,
        )
        if provider_verified or legacy_verified:
            _ensure_purchase_action(deal.order, deal.pk)
        return deal.order

    from orders.models import Order, OrderItem

    is_prepay = deal.pay_type == deal.PayType.PREPAY_200
    payment_status = "prepaid" if is_prepay else "paid"

    full_name = (
        deal.np_full_name
        or deal.client.display_name
        or deal.client.username
        or "IG клієнт"
    )
    phone = deal.np_phone or deal.client.phone or ""

    with transaction.atomic():
        # The projection is InnoDB even where the legacy deal table is MyISAM.
        # Lock it first so a concurrent reversal and order materialization are
        # serialized around the same authoritative payment truth.
        from management.models import IgPaymentProjection
        from management.services.bot_payment_truth import (
            VERIFIED_PAYMENT_TRUTHS,
            verified_payment_deals,
        )
        from management.ig_bot_models import IgPaymentConfirmationReview
        from management.services.ig_order_links import (
            authoritative_manager_decision,
            create_order_attribution,
        )

        projection = IgPaymentProjection.objects.select_for_update().filter(
            deal_id=deal.pk
        ).first()
        projection_verified = projection and projection.truth in VERIFIED_PAYMENT_TRUTHS
        legacy_verified = (
            projection is None
            and verified_payment_deals(deal.__class__.objects.filter(pk=deal.pk)).exists()
        )
        manual_review = IgPaymentConfirmationReview.objects.select_for_update().filter(
            deal_id=deal.pk,
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
        ).first()
        manual_decision = authoritative_manager_decision(manual_review) if manual_review else None
        if not projection_verified and not legacy_verified and not manual_decision:
            raise ValueError(
                "IG order requires provider-confirmed payment or source-qualified manager decision"
            )
        manager_only = bool(manual_decision and not projection_verified and not legacy_verified)
        if manager_only:
            # A receipt/manager decision authorizes order preparation only; it
            # must never materialize as paid provider revenue.
            payment_status = "unpaid"

        locked = deal.__class__.objects.select_for_update().get(pk=deal.pk)
        if locked.order_id:
            if projection_verified or legacy_verified:
                _ensure_purchase_action(locked.order, locked.pk)
            deal.order_id = locked.order_id
            deal.status = locked.status
            return locked.order
        locked_items = list(locked.items.all())
        if not locked_items:
            raise ValueError("IG deal requires at least one item")
        calculated_total = sum(
            (Decimal(item.line_total or 0) for item in locked_items),
            Decimal("0"),
        ).quantize(Decimal("0.01"))
        declared_total = Decimal(locked.amount or 0).quantize(Decimal("0.01"))
        if calculated_total != declared_total:
            raise ValueError("IG deal total does not match item line totals")

        order = Order(
            full_name=full_name[:200],
            phone=phone[:32],
            city=(deal.np_city or "")[:100],
            np_office=(deal.np_office or "")[:200],
            np_settlement_ref=(deal.np_settlement_ref or "")[:36],
            np_city_ref=(deal.np_city_ref or "")[:36],
            np_warehouse_ref=(deal.np_warehouse_ref or "")[:36],
            pay_type=deal.pay_type,
            payment_status=payment_status,
            status="new",
            source="manual",
            sale_source="Instagram",
            created_by=created_by,
            payment_provider=(
                "monobank" if projection_verified
                else "legacy_provider_transition" if legacy_verified
                else ""
            ),
            payment_invoice_id=deal.invoice_id or "",
            payment_payload={
                "provider_payment_confirmed": bool(projection_verified),
                "manager_payment_verified": bool(manual_decision),
                "legacy_payment_transition": bool(legacy_verified),
                "instagram_deal_id": locked.pk,
            },
            total_sum=deal.amount or Decimal("0"),
        )
        order.save()

        items = []
        for it in locked_items:
            items.append(
                OrderItem(
                    order=order,
                    product=it.product,
                    color_variant=it.color_variant,
                    title=it.title,
                    size=it.size or "",
                    fit_option_code=it.fit_option_code or "",
                    fit_option_label=it.fit_option_label or "",
                    option_values=it.option_values or {},
                    option_labels=it.option_labels or {},
                    qty=it.qty,
                    unit_price=it.unit_price,
                    line_total=it.line_total,
                    is_custom=(it.product_id is None),
                )
            )
        if items:
            OrderItem.objects.bulk_create(items)

        create_order_attribution(
            order,
            client=locked.client,
            deal=locked,
            review=manual_review if manual_decision else None,
            manager_decision=manual_decision,
            creation_mode=(
                "provider_auto" if projection_verified
                else "manager_review" if manual_decision
                else "provider_auto" if legacy_verified
                else "linked_existing"
            ),
            payment_source=(
                "provider_projection" if projection_verified
                else "manager_verified" if manual_decision
                else "provider_attempt" if legacy_verified
                else "unknown"
            ),
            created_by=created_by,
        )

        if projection_verified or legacy_verified:
            _ensure_purchase_action(order, locked.pk)

        locked.order = order
        locked.status = locked.Status.ORDER_CREATED
        locked.order_truth_updated_at = timezone.now()
        locked.save(update_fields=[
            "order",
            "status",
            "order_truth_updated_at",
            "updated_at",
        ])
        deal.order_id = order.id
        deal.status = locked.Status.ORDER_CREATED
        deal.order_truth_updated_at = locked.order_truth_updated_at

    # Client summary is projected from payment truth. Legacy projectionless
    # rows retain the old one-time behavior only during migration transition.
    try:
        from management.models import IgClient

        c = deal.client
        update_fields = ["current_product", "updated_at"]
        if projection is None:
            c.purchases_count = (c.purchases_count or 0) + 1
            c.total_spent = (c.total_spent or Decimal("0")) + (deal.amount or Decimal("0"))
            flags = dict(c.conversion_flags or {})
            flags["is_buyer"] = True
            c.conversion_flags = flags
            update_fields.extend(["purchases_count", "total_spent", "conversion_flags"])
        c.current_product = None
        c.save(update_fields=update_fields)
        c.set_stage(IgClient.Stage.ORDER_CREATED, reason="order")
    except Exception:
        pass

    try:
        from management.services.bot_conversation_analysis import (
            schedule_client_truth_analysis,
        )

        schedule_client_truth_analysis(deal.client, trigger="order_truth")
    except Exception:
        # Periodic reconciliation repairs a missed best-effort order trigger.
        pass

    return order
