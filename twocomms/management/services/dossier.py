"""
Повне досьє менеджера для адмін-центру (одне джерело для drawer-картки).

Збирає: рівень+умови, винагороду (баланс/заморозка/доступно), останні
оплачені накладні, статус договору/Дія/онбордингу, MOSAIC, заявки на
виплату. Викликається lazy по кліку (не тяжіти список менеджерів).

Док: Management Implementations/06 (карточка менеджера) + 07 + 03.
"""
from __future__ import annotations

from decimal import Decimal

from django.utils import timezone


def _name(user) -> str:
    try:
        n = (user.userprofile.full_name or "").strip()
        if n:
            return n
    except Exception:
        pass
    return user.get_full_name() or user.username


def build_manager_dossier(user) -> dict:
    from management.services.manager_levels import get_current_level, get_level_display_name
    from management.services.payouts import get_manager_payout_summary
    from management.services.activity_tracking import get_last_seen_map, compute_online_state
    from management.services.compensation import get_active_compensation
    from management.models import (
        ManagerCommissionAccrual, ManagerPayoutRequest, NightlyScoreSnapshot,
        ManagerOnboardingConsent, ManagerPersonalData, ManagerDocument, ManagerWeeklyReview,
    )
    from orders.models import WholesaleInvoice

    profile = getattr(user, "userprofile", None)
    now = timezone.now()

    # Рівень та умови.
    level = get_current_level(user)
    level_code = level.level if level else ""
    level_label = get_level_display_name(level.level) if level else "Без рівня"

    # Онлайн.
    last_seen = get_last_seen_map([user]).get(user.id)
    online_state = compute_online_state(last_seen) if last_seen else {"online": False, "last_seen_label": "Немає даних"}

    # Винагорода.
    pay = get_manager_payout_summary(user)

    # Заморожені позиції (деталізація).
    frozen_items = []
    for accr in (ManagerCommissionAccrual.objects.filter(owner=user, frozen_until__gt=now)
                 .select_related("invoice").order_by("frozen_until")[:50]):
        fu = timezone.localtime(accr.frozen_until)
        days_left = max(0, (fu.date() - timezone.localdate()).days)
        frozen_items.append({
            "amount": str(accr.amount),
            "frozen_until": fu.strftime("%d.%m.%Y"),
            "days_left": days_left,
            "invoice": getattr(accr.invoice, "invoice_number", "") if accr.invoice_id else "",
        })

    # Останні оплачені накладні.
    recent_paid = []
    paid_qs = (WholesaleInvoice.objects.filter(created_by=user, payment_status="paid")
               .order_by("-paid_at", "-created_at")[:8])
    accr_by_inv = {a.invoice_id: a for a in ManagerCommissionAccrual.objects.filter(invoice__in=paid_qs)}
    for inv in paid_qs:
        accr = accr_by_inv.get(inv.id)
        frozen_until = None
        days_left = None
        released = True
        if accr and accr.frozen_until:
            fu = timezone.localtime(accr.frozen_until)
            frozen_until = fu.strftime("%d.%m.%Y")
            days_left = max(0, (fu.date() - timezone.localdate()).days)
            released = accr.frozen_until <= now
        recent_paid.append({
            "id": inv.id,
            "number": inv.invoice_number,
            "company": inv.company_name,
            "amount": str(inv.total_amount),
            "paid_at": timezone.localtime(inv.paid_at).strftime("%d.%m.%Y") if inv.paid_at else "",
            "commission": str(accr.amount) if accr else "",
            "frozen_until": frozen_until,
            "days_left": days_left,
            "released": released,
        })

    # MOSAIC (shadow).
    snap = NightlyScoreSnapshot.objects.filter(owner=user).order_by("-snapshot_date").first()
    mosaic = {
        "score": float(snap.mosaic_score) if snap else None,
        "confidence": float(snap.score_confidence) if snap else None,
        "date": snap.snapshot_date.strftime("%d.%m.%Y") if snap else "",
    }

    # Договір / Дія / онбординг.
    consent = ManagerOnboardingConsent.objects.filter(owner=user).order_by("-created_at").first()
    pii = ManagerPersonalData.objects.filter(owner=user).first()
    diia_signed = bool(
        ManagerDocument.objects.filter(owner=user, signature_provider="diia",
                                       status=ManagerDocument.Status.SIGNED).exists()
    )
    docs = [
        {
            "id": d.id,
            "kind": d.get_doc_kind_display(),
            "status": d.status,
            "status_label": d.get_status_display(),
            "signed_at": timezone.localtime(d.signed_at).strftime("%d.%m.%Y") if d.signed_at else "",
            "access_blocking": d.access_blocking,
        }
        for d in ManagerDocument.objects.filter(owner=user).order_by("-created_at")[:10]
    ]
    contract = {
        "onboarding_signed": bool(consent),
        "consent_version": consent.rules_version if consent else "",
        "consent_at": timezone.localtime(consent.created_at).strftime("%d.%m.%Y") if consent else "",
        "diia_signed": diia_signed,
        "pii_present": bool(pii),
        "access_status": getattr(profile, "access_status", "active"),
        "documents": docs,
    }

    # Поточні умови винагороди (target / fallback).
    comp = get_active_compensation(user)
    compensation = {
        "monthly_base": str(comp.monthly_base_amount) if comp else "",
        "weekly_base": str(comp.weekly_base_amount) if comp else "",
        "commission_percent": str(comp.commission_percent) if comp else (str(getattr(profile, "manager_commission_percent", 0)) if profile else "0"),
        "frozen_days": comp.frozen_days if comp else 14,
        "source": "settings" if comp else "fallback",
    }

    # Заявки на виплату.
    payout_requests = [
        {
            "id": r.id,
            "amount": str(r.amount),
            "status": r.status,
            "status_label": r.get_status_display(),
            "created_at": timezone.localtime(r.created_at).strftime("%d.%m.%Y %H:%M"),
        }
        for r in ManagerPayoutRequest.objects.filter(owner=user).order_by("-created_at")[:10]
    ]

    # Тижневі рішення, що очікують.
    pending_reviews = [
        {
            "id": r.id,
            "week_start": r.week_start.strftime("%d.%m"),
            "week_end": r.week_end.strftime("%d.%m"),
            "base": str(r.calculated_weekly_base),
            "paid_invoices": r.kpi_paid_invoices,
            "units": r.kpi_units,
        }
        for r in ManagerWeeklyReview.objects.filter(owner=user, admin_decision="").order_by("-week_start")[:8]
    ]

    started_at = getattr(profile, "manager_started_at", None) or getattr(profile, "cooperation_started_at", None)
    days_worked = None
    if started_at:
        try:
            days_worked = max(0, (timezone.localdate() - started_at).days)
        except Exception:
            days_worked = None

    return {
        "manager": {
            "id": user.id,
            "name": _name(user),
            "username": user.username,
            "position": (getattr(profile, "manager_position", "") or "").strip(),
            "level_code": level_code,
            "level_label": level_label,
            "weekly_salary": level.weekly_salary_uah if level else 0,
            "commission_percent": str(level.commission_percent) if level else "0",
            "salary_start_date": level.salary_start_date.isoformat() if level and level.salary_start_date else "",
            "started_at": started_at.isoformat() if started_at else "",
            "days_worked": days_worked,
            "online": online_state["online"],
            "last_seen_label": online_state["last_seen_label"],
        },
        "payouts": {
            "balance": str(pay["balance"]),
            "available": str(pay["available"]),
            "frozen": str(pay["frozen_amount"]),
            "reserved": str(pay["reserved_amount"]),
            "paid_total": str(pay["paid_total"]),
            "frozen_items": frozen_items,
        },
        "recent_paid_invoices": recent_paid,
        "mosaic": mosaic,
        "contract": contract,
        "compensation": compensation,
        "payout_requests": payout_requests,
        "pending_reviews": pending_reviews,
    }
