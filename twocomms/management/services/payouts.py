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


def build_payouts_overview(*, search: str = "") -> dict:
    """Зведення по виплатах для адмін-борду: список менеджерів з балансами,
    замороженими сумами, активними запитами + загальні підсумки.

    Переиспользується окремою адмін-сторінкою виплат (board)."""
    import re

    from django.contrib.auth import get_user_model  # noqa: F401
    from django.db.models import Count, Max, Min, Q

    from management.models import (
        ManagerCommissionAccrual,
        ManagerPayoutRequest,
    )
    from management.services.roster import manager_roster_queryset

    money_field = models.DecimalField(max_digits=12, decimal_places=2)
    zero = Decimal("0")
    now = timezone.now()

    payout_users = list(
        manager_roster_queryset(include_staff=False)
        .select_related("userprofile")
        .order_by("id")
    )
    search = (search or "").strip().lower()
    if search:
        payout_users = [
            u for u in payout_users
            if search in (u.get_full_name() or "").lower()
            or search in (u.username or "").lower()
            or search in ((getattr(getattr(u, "userprofile", None), "manager_position", "") or "").lower())
        ]

    user_ids = [u.id for u in payout_users]

    accr_rows = ManagerCommissionAccrual.objects.filter(owner_id__in=user_ids).values("owner_id").annotate(
        total=Coalesce(Sum("amount"), zero, output_field=money_field),
        frozen=Coalesce(Sum("amount", filter=Q(frozen_until__gt=now)), zero, output_field=money_field),
        frozen_count=Count("id", filter=Q(frozen_until__gt=now)),
        next_unfreeze_at=Min("frozen_until", filter=Q(frozen_until__gt=now)),
    )
    accr_map = {row["owner_id"]: row for row in accr_rows}

    pay_rows = ManagerPayoutRequest.objects.filter(owner_id__in=user_ids).values("owner_id").annotate(
        paid=Coalesce(Sum("amount", filter=Q(status=ManagerPayoutRequest.Status.PAID)), zero, output_field=money_field),
        reserved=Coalesce(Sum("amount", filter=Q(status__in=[ManagerPayoutRequest.Status.PROCESSING, ManagerPayoutRequest.Status.APPROVED])), zero, output_field=money_field),
        last_paid_at=Max("paid_at", filter=Q(status=ManagerPayoutRequest.Status.PAID)),
    )
    pay_map = {row["owner_id"]: row for row in pay_rows}

    active_reqs = ManagerPayoutRequest.objects.filter(
        owner_id__in=user_ids,
        status__in=[ManagerPayoutRequest.Status.PROCESSING, ManagerPayoutRequest.Status.APPROVED],
    ).select_related("owner").order_by("owner_id", "-created_at")
    active_map = {}
    for r in active_reqs:
        active_map.setdefault(r.owner_id, r)

    frozen_details_map = {}
    for row in (ManagerCommissionAccrual.objects.filter(owner_id__in=user_ids, frozen_until__gt=now)
                .order_by("owner_id", "frozen_until")):
        fu_local = timezone.localtime(row.frozen_until) if row.frozen_until else None
        days_left = None
        if fu_local:
            try:
                days_left = max(0, (fu_local.date() - timezone.localdate()).days)
            except Exception:
                days_left = None
        frozen_details_map.setdefault(row.owner_id, []).append({
            "amount": row.amount,
            "frozen_until": fu_local.strftime("%d.%m.%Y") if fu_local else "—",
            "days_left": days_left,
            "reason": (row.freeze_reason_text or row.note or "Захист 14 днів").strip(),
        })

    def mask_card(raw):
        digits = re.sub(r"\D+", "", (raw or "").strip())
        return ("**** " + digits[-4:]) if len(digits) >= 4 else "—"

    rows = []
    summary = {
        "managers": 0, "balance": zero, "available": zero, "frozen": zero,
        "reserved": zero, "paid_total": zero, "active_requests": 0, "with_available": 0,
    }
    for u in payout_users:
        prof = getattr(u, "userprofile", None)
        a = accr_map.get(u.id) or {}
        p = pay_map.get(u.id) or {}
        total_accrued = a.get("total") or zero
        frozen_amount = a.get("frozen") or zero
        paid_total = p.get("paid") or zero
        reserved_amount = p.get("reserved") or zero
        balance = total_accrued - paid_total
        available = balance - frozen_amount - reserved_amount
        if available < 0:
            available = zero

        next_unfreeze_at = a.get("next_unfreeze_at")
        next_unfreeze_label = None
        if next_unfreeze_at:
            nu = timezone.localtime(next_unfreeze_at)
            try:
                dl = max(0, (nu.date() - timezone.localdate()).days)
            except Exception:
                dl = None
            if dl == 0:
                next_unfreeze_label = "сьогодні"
            elif dl == 1:
                next_unfreeze_label = "за 1 день"
            elif dl is not None:
                next_unfreeze_label = f"за {dl} дн"

        summary["managers"] += 1
        summary["balance"] += balance
        summary["available"] += available
        summary["frozen"] += frozen_amount
        summary["reserved"] += reserved_amount
        summary["paid_total"] += paid_total
        active_req = active_map.get(u.id)
        if active_req:
            summary["active_requests"] += 1
        if available > 0:
            summary["with_available"] += 1

        rows.append({
            "id": u.id,
            "name": u.get_full_name() or u.username,
            "position": (getattr(prof, "manager_position", "") or "").strip() or "—",
            "card_mask": mask_card(getattr(prof, "payment_details", "") if prof else ""),
            "card_raw": (getattr(prof, "payment_details", "") or "").strip() if prof else "",
            "balance": balance,
            "available": available,
            "frozen": frozen_amount,
            "reserved": reserved_amount,
            "frozen_count": a.get("frozen_count") or 0,
            "active_request": active_req,
            "paid_total": paid_total,
            "last_paid_at": p.get("last_paid_at"),
            "next_unfreeze_label": next_unfreeze_label,
            "frozen_items": frozen_details_map.get(u.id, []),
            "avatar_url": (prof.avatar.url if prof and getattr(prof, "avatar", None) else ""),
        })

    # Сортування: спершу ті, у кого є активний запит, далі за доступним балансом
    rows.sort(key=lambda r: (0 if r["active_request"] else 1, -float(r["available"])))

    return {"rows": rows, "summary": summary}
