from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from management.models import ManagerCommissionAccrual, ManagerPayoutRequest


def get_manager_payout_summary(user) -> dict:
    zero = Decimal("0")
    money_field = models.DecimalField(max_digits=12, decimal_places=2)
    now = timezone.now()

    accruals_qs = ManagerCommissionAccrual.objects.filter(owner=user)
    reserved_qs = ManagerPayoutRequest.objects.filter(
        owner=user,
        status__in=[ManagerPayoutRequest.Status.PROCESSING, ManagerPayoutRequest.Status.APPROVED],
    )

    total_accrued = accruals_qs.aggregate(
        total=Coalesce(Sum("amount"), zero, output_field=money_field),
    )["total"] or zero
    frozen_amount = accruals_qs.filter(frozen_until__gt=now).aggregate(
        total=Coalesce(Sum("amount"), zero, output_field=money_field),
    )["total"] or zero
    paid_total = ManagerPayoutRequest.objects.filter(
        owner=user,
        status=ManagerPayoutRequest.Status.PAID,
    ).aggregate(
        total=Coalesce(Sum("amount"), zero, output_field=money_field),
    )["total"] or zero
    reserved_amount = reserved_qs.aggregate(
        total=Coalesce(Sum("amount"), zero, output_field=money_field),
    )["total"] or zero

    balance = total_accrued - paid_total
    available = balance - frozen_amount - reserved_amount
    if available < 0:
        available = zero

    active_request = reserved_qs.order_by("-created_at").first()

    return {
        "balance": balance,
        "available": available,
        "frozen_amount": frozen_amount,
        "reserved_amount": reserved_amount,
        "paid_total": paid_total,
        "active_request": active_request,
        "has_active_request": bool(active_request),
    }
