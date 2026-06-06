"""
Адмін-центр: повний життєвий цикл накладних менеджерів.

Док: twocomms/Management Implementations/04_INVOICE_MONOBANK_PAYMENTS.md,
     twocomms/Management Implementations/06_ADMIN_CENTER_UI_UX.md

Чистий шар деривації статусу + збірка payload для шаблону/drawer. Жодних
грошових мутацій тут не відбувається — лише читання й представлення.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Q
from django.utils import timezone


# Похідні стани життєвого циклу (code, label, tone).
# tone: ok | warn | bad | watch | neutral — для бейджів у UI.
LIFECYCLE = {
    "draft": ("Чернетка", "neutral"),
    "review": ("На перевірці", "watch"),
    "rejected": ("Відхилено", "bad"),
    "approved": ("Підтверджена", "ok"),
    "link_created": ("Посилання створено", "watch"),
    "link_copied": ("Посилання скопійовано", "watch"),
    "awaiting_payment": ("Очікує оплату", "watch"),
    "paid_frozen": ("Оплачено · заморожено", "ok"),
    "paid_released": ("Оплачено · доступно", "ok"),
    "payment_failed": ("Помилка оплати", "bad"),
    "refunded": ("Повернення", "bad"),
}

# Порядок для фільтр-чіпів адмінки.
FILTER_ORDER = [
    "review",
    "approved",
    "link_created",
    "awaiting_payment",
    "paid_frozen",
    "paid_released",
    "payment_failed",
    "refunded",
    "rejected",
]


def derive_lifecycle(invoice, accrual=None, *, now=None) -> str:
    """Визначає похідний стан накладної з review_status + payment_status + полів."""
    now = now or timezone.now()
    review = invoice.review_status
    payment = invoice.payment_status

    if review == "draft":
        return "draft"
    if review == "pending":
        return "review"
    if review == "rejected":
        return "rejected"

    # review == approved (або інше «підтверджене»)
    if payment == "paid":
        frozen_until = getattr(accrual, "frozen_until", None) if accrual else None
        if frozen_until and frozen_until > now:
            return "paid_frozen"
        return "paid_released"
    if payment == "refunded" or invoice.returned_at:
        return "refunded"
    if payment == "failed":
        return "payment_failed"
    if payment == "pending":
        # Посилання сформоване й (зазвичай) надіслане клієнту → очікуємо оплату.
        return "awaiting_payment"
    # not_paid
    if invoice.payment_url:
        # Скопійоване посилання = вже надіслане клієнту → очікуємо оплату.
        if invoice.payment_link_copied_at:
            return "awaiting_payment"
        return "link_created"
    return "approved"


def _frozen_progress(accrual, *, now=None) -> dict | None:
    """Повертає дані countdown заморозки для оплаченої накладної."""
    if not accrual or not getattr(accrual, "frozen_until", None):
        return None
    now = now or timezone.now()
    frozen_until = accrual.frozen_until
    created = accrual.created_at or now
    total = (frozen_until - created).total_seconds()
    left = (frozen_until - now).total_seconds()
    if total <= 0:
        pct = 100
    else:
        pct = int(max(0, min(100, (1 - left / total) * 100)))
    days_left = max(0, int((frozen_until.date() - timezone.localdate()).days)) if left > 0 else 0
    return {
        "frozen_until": timezone.localtime(frozen_until).strftime("%d.%m.%Y"),
        "frozen_until_iso": frozen_until.isoformat(),
        "days_left": days_left,
        "progress_pct": pct,
        "released": left <= 0,
        "amount": str(accrual.amount),
    }


def _manager_name(user) -> str:
    if not user:
        return "—"
    try:
        prof = user.userprofile
        name = (getattr(prof, "full_name", "") or "").strip()
        if name:
            return name
    except Exception:
        pass
    return user.get_full_name() or user.username


def build_invoice_row(invoice, accrual=None, *, now=None) -> dict:
    """Збирає рядок для таблиці/картки накладної."""
    now = now or timezone.now()
    code = derive_lifecycle(invoice, accrual, now=now)
    label, tone = LIFECYCLE.get(code, (code, "neutral"))
    frozen = _frozen_progress(accrual, now=now) if code in ("paid_frozen", "paid_released") else None

    return {
        "id": invoice.id,
        "number": invoice.invoice_number,
        "manager_id": invoice.created_by_id,
        "manager": _manager_name(invoice.created_by),
        "company": invoice.company_name,
        "amount": str(invoice.total_amount),
        "units": invoice.units_count,
        "lifecycle": code,
        "lifecycle_label": label,
        "lifecycle_tone": tone,
        "review_status": invoice.review_status,
        "payment_status": invoice.payment_status,
        "payment_url": invoice.payment_url or "",
        "monobank_invoice_id": invoice.monobank_invoice_id or "",
        "created_at": timezone.localtime(invoice.created_at).strftime("%d.%m.%Y %H:%M") if invoice.created_at else "",
        "reviewed_at": timezone.localtime(invoice.reviewed_at).strftime("%d.%m.%Y %H:%M") if invoice.reviewed_at else "",
        "reviewed_by": _manager_name(invoice.reviewed_by) if invoice.reviewed_by_id else "",
        "reject_reason": invoice.review_reject_reason or "",
        "link_created_at": timezone.localtime(invoice.payment_link_created_at).strftime("%d.%m.%Y %H:%M") if invoice.payment_link_created_at else "",
        "link_copied_at": timezone.localtime(invoice.payment_link_copied_at).strftime("%d.%m.%Y %H:%M") if invoice.payment_link_copied_at else "",
        "paid_at": timezone.localtime(invoice.paid_at).strftime("%d.%m.%Y %H:%M") if invoice.paid_at else "",
        "paid_amount": (str(Decimal(invoice.payment_amount_minor) / 100) if invoice.payment_amount_minor else ""),
        "refund_amount": str(invoice.refund_amount) if invoice.refund_amount is not None else "",
        "refund_reason": invoice.refund_reason or "",
        "frozen": frozen,
        "commission_amount": str(accrual.amount) if accrual else "",
        "commission_percent": str(accrual.percent) if accrual else "",
        "download_url": f"/invoices/{invoice.id}/download/",
        "is_pending": invoice.review_status == "pending",
    }


def build_invoices_payload(*, status=None, manager_id=None, query=None, limit=300) -> dict:
    """Будує payload вкладки «Накладні» з фільтрами та лічильниками."""
    from orders.models import WholesaleInvoice
    from management.models import ManagerCommissionAccrual

    now = timezone.now()

    base_qs = WholesaleInvoice.objects.filter(created_by__isnull=False).exclude(
        review_status="draft"
    ).select_related("created_by", "created_by__userprofile", "reviewed_by")

    if manager_id:
        base_qs = base_qs.filter(created_by_id=manager_id)
    if query:
        base_qs = base_qs.filter(
            Q(invoice_number__icontains=query)
            | Q(company_name__icontains=query)
            | Q(created_by__username__icontains=query)
        )

    invoices = list(base_qs.order_by("-created_at")[: max(1, int(limit))])

    # Підтягуємо нарахування одним запитом.
    invoice_ids = [inv.id for inv in invoices]
    accr_map = {}
    if invoice_ids:
        for accr in ManagerCommissionAccrual.objects.filter(invoice_id__in=invoice_ids):
            accr_map[accr.invoice_id] = accr

    rows = []
    counts = {code: 0 for code in LIFECYCLE}
    for inv in invoices:
        accr = accr_map.get(inv.id)
        row = build_invoice_row(inv, accr, now=now)
        counts[row["lifecycle"]] = counts.get(row["lifecycle"], 0) + 1
        rows.append(row)

    # Фільтрація по похідному статусу робиться після деривації.
    if status and status in LIFECYCLE:
        rows = [r for r in rows if r["lifecycle"] == status]

    filter_chips = []
    for code in FILTER_ORDER:
        label, tone = LIFECYCLE[code]
        filter_chips.append({
            "code": code,
            "label": label,
            "tone": tone,
            "count": counts.get(code, 0),
        })

    return {
        "rows": rows,
        "filter_chips": filter_chips,
        "total": len(rows),
        "active_status": status or "",
        "active_manager": manager_id or "",
        "active_query": query or "",
    }
