"""
Єдиний шар руху коштів менеджера (ManagerEarningsLedger).

Фаза 1 (поточна): ledger пишеться ПАРАЛЕЛЬНО до існуючих
ManagerCommissionAccrual / ManagerPayoutRequest. Баланс виплат поки
рахується по-старому (services/payouts.py). Перемикання балансу на
ledger — окрема фаза після звірки.

Док: twocomms/Management Implementations/07_COMPENSATION_PAYOUTS.md (7.4–7.5)
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger("management.ledger")


def record_commission_frozen(accrual) -> object | None:
    """Створює (ідемпотентно) ledger-запис для замороженої комісії з накладної.

    Ідемпотентність — по (source_type, source_id=invoice_id): повторний виклик
    не дублює запис.
    """
    from management.models import ManagerEarningsLedger

    if not accrual or not accrual.invoice_id:
        return None
    source_id = str(accrual.invoice_id)
    entry, created = ManagerEarningsLedger.objects.get_or_create(
        source_type=ManagerEarningsLedger.SourceType.INVOICE_COMMISSION,
        source_id=source_id,
        defaults={
            "owner": accrual.owner,
            "amount": accrual.amount,
            "status": ManagerEarningsLedger.Status.FROZEN,
            "available_at": accrual.frozen_until,
            "commission_accrual": accrual,
            "reason": f"Комісія з накладної #{getattr(accrual.invoice, 'invoice_number', accrual.invoice_id)}",
        },
    )
    return entry


def record_weekly_base(review) -> object | None:
    """Створює ledger-запис для нарахованої тижневої бази (доступно одразу)."""
    from management.models import ManagerEarningsLedger

    if not review or review.awarded_amount is None:
        return None
    source_id = f"review-{review.id}"
    entry, _ = ManagerEarningsLedger.objects.update_or_create(
        source_type=ManagerEarningsLedger.SourceType.WEEKLY_BASE,
        source_id=source_id,
        defaults={
            "owner": review.owner,
            "amount": review.awarded_amount,
            "status": ManagerEarningsLedger.Status.AVAILABLE,
            "available_at": timezone.now(),
            "reason": f"Базова винагорода за тиждень {review.week_start.isoformat()}",
        },
    )
    return entry


def record_withdrawal(payout) -> object | None:
    """Створює ledger-запис списання при виплаті (від'ємна сума, статус paid)."""
    from management.models import ManagerEarningsLedger

    if not payout:
        return None
    source_id = f"payout-{payout.id}"
    entry, _ = ManagerEarningsLedger.objects.update_or_create(
        source_type=ManagerEarningsLedger.SourceType.WITHDRAWAL,
        source_id=source_id,
        defaults={
            "owner": payout.owner,
            "amount": -Decimal(str(payout.amount or 0)),
            "status": ManagerEarningsLedger.Status.PAID,
            "available_at": timezone.now(),
            "reason": "Виплата винагороди",
        },
    )
    return entry


def release_due(*, now=None) -> dict:
    """Розморожує ledger-записи з available_at <= now (frozen -> available).

    Скасовані/повернені (cancelled) не чіпаємо. Ідемпотентно.
    Повертає {'released': N, 'skipped_cancelled': M}.
    """
    from management.models import ManagerEarningsLedger

    now = now or timezone.now()
    qs = ManagerEarningsLedger.objects.filter(
        status=ManagerEarningsLedger.Status.FROZEN,
        available_at__isnull=False,
        available_at__lte=now,
    )
    released = 0
    skipped = 0
    for entry in qs.select_related("commission_accrual", "commission_accrual__invoice"):
        # Якщо повʼязана накладна повернена — не розморожуємо.
        accr = entry.commission_accrual
        invoice = getattr(accr, "invoice", None) if accr else None
        if invoice and (invoice.payment_status == "refunded" or invoice.returned_at):
            entry.status = ManagerEarningsLedger.Status.CANCELLED
            entry.reason = (entry.reason or "") + " · скасовано (повернення)"
            entry.save(update_fields=["status", "reason"])
            skipped += 1
            continue
        entry.status = ManagerEarningsLedger.Status.AVAILABLE
        entry.save(update_fields=["status"])
        released += 1
    return {"released": released, "skipped_cancelled": skipped}
