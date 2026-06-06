"""
Тижневі рішення по базовій винагороді (full/half/custom/none).

Факти KPI рахуються від ВЕРИФІКОВАНИХ оплачених накладних (Monobank),
а не від самозвітів — це закриває грошовий абуз (MOSAIC A1, док 08).

Док: twocomms/Management Implementations/07_COMPENSATION_PAYOUTS.md (7.3)
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone


def week_bounds(ref_date: date) -> tuple[date, date]:
    """Повертає (monday, sunday) тижня, що містить ref_date."""
    monday = ref_date - timedelta(days=ref_date.weekday())
    return monday, monday + timedelta(days=6)


def previous_week_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or timezone.localdate()
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)
    return last_monday, last_monday + timedelta(days=6)


def build_weekly_kpi(user, week_start: date, week_end: date) -> dict:
    """Рахує KPI менеджера за тиждень на основі оплачених накладних."""
    from orders.models import WholesaleInvoice
    from management.models import Client

    start_dt = timezone.make_aware(timezone.datetime.combine(week_start, timezone.datetime.min.time()))
    end_dt = timezone.make_aware(timezone.datetime.combine(week_end, timezone.datetime.max.time()))

    paid_qs = WholesaleInvoice.objects.filter(
        created_by=user, payment_status="paid", paid_at__range=(start_dt, end_dt)
    )
    agg = paid_qs.aggregate(
        cnt=Count("id"),
        units=Sum("units_count"),
        sales=Sum("total_amount"),
    )
    processed_clients = Client.objects.filter(
        owner=user, updated_at__range=(start_dt, end_dt)
    ).exclude(call_result="no_answer").count()

    return {
        "kpi_paid_invoices": agg["cnt"] or 0,
        "kpi_units": int(agg["units"] or 0),
        "kpi_sales_amount": agg["sales"] or Decimal("0.00"),
        "kpi_processed_clients": processed_clients,
    }


def calculated_weekly_base(user) -> Decimal:
    """Тижнева база з актуальних умов винагороди (фолбек на ManagerLevel/0)."""
    from management.services.compensation import get_active_compensation

    comp = get_active_compensation(user)
    if comp:
        return comp.weekly_base_amount
    # Фолбек: ManagerLevel.weekly_salary_uah
    try:
        level = user.manager_level
        return Decimal(str(level.weekly_salary_uah or 0))
    except Exception:
        return Decimal("0.00")


def generate_for_week(week_start: date, week_end: date, *, only_user=None) -> dict:
    """Створює ManagerWeeklyReview (без рішення) для менеджерів за тиждень.

    Ідемпотентно: unique (owner, week_start) → update_or_create залишає вже
    вирішені відгуки незмінними (рішення адміна не перезаписуємо).
    """
    from management.models import ManagerWeeklyReview
    from management.services.roster import manager_roster_queryset

    users = manager_roster_queryset(include_staff=False)
    if only_user is not None:
        users = users.filter(id=only_user)

    created = 0
    updated = 0
    for user in users:
        kpi = build_weekly_kpi(user, week_start, week_end)
        base = calculated_weekly_base(user)
        existing = ManagerWeeklyReview.objects.filter(owner=user, week_start=week_start).first()
        if existing and existing.admin_decision:
            # Рішення вже прийнято — не чіпаємо.
            continue
        if existing:
            for k, v in kpi.items():
                setattr(existing, k, v)
            existing.week_end = week_end
            existing.calculated_weekly_base = base
            existing.save()
            updated += 1
        else:
            ManagerWeeklyReview.objects.create(
                owner=user, week_start=week_start, week_end=week_end,
                calculated_weekly_base=base, **kpi,
            )
            created += 1
    return {"created": created, "updated": updated}


def apply_decision(review, *, decision: str, custom_amount=None, reason: str = "", admin=None):
    """Застосовує рішення адміна: рахує awarded_amount, пише ledger + audit.

    Повертає (ok: bool, error: str|None).
    """
    from decimal import Decimal as D
    from management.models import ManagerWeeklyReview, AdminAuditLog
    from management.services.ledger import record_weekly_base

    decision = (decision or "").strip()
    valid = {c[0] for c in ManagerWeeklyReview.Decision.choices}
    if decision not in valid:
        return False, "Невідоме рішення"

    base = D(str(review.calculated_weekly_base or 0))
    if decision == ManagerWeeklyReview.Decision.FULL:
        awarded = base
    elif decision == ManagerWeeklyReview.Decision.HALF:
        awarded = (base / D("2")).quantize(D("0.01"))
    elif decision == ManagerWeeklyReview.Decision.NONE:
        awarded = D("0.00")
    else:  # custom
        try:
            awarded = D(str(custom_amount)).quantize(D("0.01"))
        except Exception:
            return False, "Невірна сума"
        if awarded < 0:
            return False, "Сума не може бути від'ємною"

    reason = (reason or "").strip()
    if decision != ManagerWeeklyReview.Decision.FULL and not reason:
        return False, "Вкажіть причину рішення (обов'язково, якщо не повна винагорода)"

    before = {
        "admin_decision": review.admin_decision,
        "awarded_amount": str(review.awarded_amount),
    }
    review.admin_decision = decision
    review.awarded_amount = awarded
    review.reason = reason
    review.decided_by = admin
    review.decided_at = timezone.now()
    review.save(update_fields=[
        "admin_decision", "awarded_amount", "reason", "decided_by", "decided_at",
    ])

    # Нараховуємо у ledger (база доступна одразу, без заморозки).
    entry = None
    if awarded > 0:
        entry = record_weekly_base(review)
        if entry:
            review.ledger_entry = entry
            review.save(update_fields=["ledger_entry"])

    try:
        AdminAuditLog.objects.create(
            actor=admin,
            actor_role="staff",
            action="weekly_review_decision",
            entity_type="ManagerWeeklyReview",
            entity_id=str(review.id),
            before=before,
            after={"admin_decision": decision, "awarded_amount": str(awarded)},
            reason=reason,
        )
    except Exception:
        pass

    return True, None
