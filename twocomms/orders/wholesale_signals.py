"""
Сигнали для оптових накладних менеджерів (окремо від orders/signals.py).

Винесено в окремий модуль, щоб підключати ТІЛЬКИ ці ресівери в
OrdersConfig.ready(), не активуючи Order-нотифікації з orders/signals.py
(вони навмисно шлються вручну з view і їх дублювання небажане).

Док: twocomms/Management Implementations/04_INVOICE_MONOBANK_PAYMENTS.md (4.7)
"""
import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import WholesaleInvoice

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=WholesaleInvoice)
def track_wholesale_invoice_payment(sender, instance, **kwargs):
    """Детект переходу payment_status -> 'paid' (для нарахування комісії)."""
    if not getattr(instance, 'pk', None):
        return
    try:
        old_instance = WholesaleInvoice.objects.only('payment_status').get(pk=instance.pk)
    except WholesaleInvoice.DoesNotExist:
        return
    instance._mgmt_just_paid = (old_instance.payment_status != 'paid' and instance.payment_status == 'paid')


@receiver(post_save, sender=WholesaleInvoice)
def award_manager_commission_for_paid_wholesale_invoice(sender, instance, created, **kwargs):
    """При оплаті накладної створює заморожене нарахування комісії (ідемпотентно)."""
    just_paid = bool(getattr(instance, '_mgmt_just_paid', False) or (created and instance.payment_status == 'paid'))
    if not just_paid:
        return

    manager = getattr(instance, 'created_by', None)
    if not manager:
        return

    try:
        from management.models import ManagerCommissionAccrual
    except Exception:
        return

    # Відсоток і період заморозки: цільове джерело — ManagerCompensationSettings
    # (актуальний запис), фолбек — UserProfile.manager_commission_percent / 14 днів.
    try:
        from management.services.compensation import resolve_commission_terms
        percent, frozen_days = resolve_commission_terms(manager)
    except Exception:
        try:
            prof = manager.userprofile
            percent = Decimal(str(getattr(prof, 'manager_commission_percent', None) or 0))
        except Exception:
            percent = Decimal('0')
        frozen_days = 14

    # База комісії — фактично оплачена сума (payment_amount_minor), якщо відома,
    # інакше total_amount.
    base_amount = Decimal('0')
    amount_minor = getattr(instance, 'payment_amount_minor', None)
    if amount_minor:
        try:
            base_amount = Decimal(amount_minor) / Decimal('100')
        except Exception:
            base_amount = Decimal('0')
    if base_amount <= 0:
        try:
            base_amount = Decimal(str(getattr(instance, 'total_amount', 0) or 0))
        except Exception:
            base_amount = Decimal('0')

    if percent < 0:
        percent = Decimal('0')
    if base_amount < 0:
        base_amount = Decimal('0')

    amount = (base_amount * percent / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if amount < 0:
        amount = Decimal('0')

    paid_at = getattr(instance, 'paid_at', None) or timezone.now()
    frozen_until = paid_at + timedelta(days=int(frozen_days or 14))

    try:
        ManagerCommissionAccrual.objects.get_or_create(
            invoice=instance,
            defaults={
                'owner': manager,
                'base_amount': base_amount,
                'percent': percent,
                'amount': amount,
                'frozen_until': frozen_until,
            },
        )
    except Exception as exc:
        logger.warning(
            'Failed to create commission accrual for WholesaleInvoice %s: %s',
            getattr(instance, 'pk', None), exc, exc_info=True,
        )
