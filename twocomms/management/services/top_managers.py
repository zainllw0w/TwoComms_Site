"""
Топ-менеджери за період: за оплаченими накладними, за обробленими
клієнтами, за рейтингом MOSAIC. Період: today / week / month / all.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone


PERIODS = [
    ("today", "Сьогодні"),
    ("week", "Тиждень"),
    ("month", "Місяць"),
    ("all", "За весь час"),
]


def _range(period: str):
    now = timezone.now()
    if period == "today":
        start = timezone.make_aware(timezone.datetime.combine(timezone.localdate(), timezone.datetime.min.time()))
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now - timedelta(days=30)
    else:
        start = None
    return start, now


def _name(user_id, name_map):
    return name_map.get(user_id, f"#{user_id}")


def build_top_managers(period: str = "week", limit: int = 5) -> dict:
    from django.contrib.auth import get_user_model
    from orders.models import WholesaleInvoice
    from management.models import Client, NightlyScoreSnapshot
    from management.services.roster import manager_roster_queryset

    User = get_user_model()
    if period not in {p[0] for p in PERIODS}:
        period = "week"
    start, now = _range(period)

    managers = manager_roster_queryset(include_staff=False)
    manager_ids = list(managers.values_list("id", flat=True))
    name_map = {
        u.id: (u.get_full_name() or u.username)
        for u in User.objects.filter(id__in=manager_ids)
    }

    # За оплаченими накладними (кількість + сума).
    inv_q = WholesaleInvoice.objects.filter(created_by_id__in=manager_ids, payment_status="paid")
    if start:
        inv_q = inv_q.filter(paid_at__gte=start)
    by_invoices = list(
        inv_q.values("created_by_id")
        .annotate(
            cnt=Count("id"),
            total=Coalesce(Sum("total_amount"), Decimal("0"),
                           output_field=models.DecimalField(max_digits=12, decimal_places=2)),
        )
        .order_by("-cnt", "-total")[:limit]
    )
    top_invoices = [
        {"id": r["created_by_id"], "name": _name(r["created_by_id"], name_map),
         "value": r["cnt"], "extra": f'{r["total"]} грн'}
        for r in by_invoices
    ]

    # За обробленими клієнтами.
    cl_q = Client.objects.filter(owner_id__in=manager_ids).exclude(call_result="no_answer")
    if start:
        cl_q = cl_q.filter(updated_at__gte=start)
    by_clients = list(
        cl_q.values("owner_id").annotate(cnt=Count("id")).order_by("-cnt")[:limit]
    )
    top_processed = [
        {"id": r["owner_id"], "name": _name(r["owner_id"], name_map), "value": r["cnt"], "extra": "клієнтів"}
        for r in by_clients
    ]

    # За MOSAIC (останній снапшот, період-незалежний).
    mosaic_map = {}
    for row in (NightlyScoreSnapshot.objects.filter(owner_id__in=manager_ids)
                .order_by("owner_id", "-snapshot_date")
                .values("owner_id", "mosaic_score")):
        if row["owner_id"] not in mosaic_map:
            mosaic_map[row["owner_id"]] = float(row["mosaic_score"])
    top_mosaic = sorted(
        [{"id": uid, "name": _name(uid, name_map), "value": round(score), "extra": "MOSAIC"}
         for uid, score in mosaic_map.items()],
        key=lambda x: x["value"], reverse=True,
    )[:limit]

    return {
        "period": period,
        "periods": PERIODS,
        "by_invoices": top_invoices,
        "by_processed": top_processed,
        "by_mosaic": top_mosaic,
    }
