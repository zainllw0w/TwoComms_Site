"""
Умови винагороди менеджера: поточні налаштування + резолв відсотка/заморозки.

Цільове джерело істини — ManagerCompensationSettings (актуальний запис).
Фолбек — UserProfile.manager_commission_percent і дефолтні 14 днів, щоб не
ламати існуючий сигнал нарахування комісії.

Док: twocomms/Management Implementations/04_INVOICE_MONOBANK_PAYMENTS.md (4.7),
     twocomms/Management Implementations/07_COMPENSATION_PAYOUTS.md
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

DEFAULT_FROZEN_DAYS = 14


def get_active_compensation(user):
    """Повертає чинний ManagerCompensationSettings або None."""
    from management.models import ManagerCompensationSettings

    today = timezone.localdate()
    return (
        ManagerCompensationSettings.objects.filter(owner=user, effective_from__lte=today)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .order_by("-effective_from", "-id")
        .first()
    )


def resolve_commission_terms(user) -> tuple[Decimal, int]:
    """Повертає (percent, frozen_days) для нарахування комісії з фолбеком."""
    comp = get_active_compensation(user)
    if comp:
        try:
            percent = Decimal(str(comp.commission_percent or 0))
        except Exception:
            percent = Decimal("0")
        frozen_days = int(comp.frozen_days or DEFAULT_FROZEN_DAYS)
        return percent, frozen_days

    percent = Decimal("0")
    try:
        percent = Decimal(str(user.userprofile.manager_commission_percent or 0))
    except Exception:
        percent = Decimal("0")
    return percent, DEFAULT_FROZEN_DAYS
