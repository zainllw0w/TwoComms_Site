"""Тести Фази 5: єдиний ledger винагороди + розморозка."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from orders.models import WholesaleInvoice
from management.models import ManagerEarningsLedger, ManagerCommissionAccrual
from management.services import ledger

User = get_user_model()


def _paid_invoice(user, number, amount="1000.00"):
    return WholesaleInvoice.objects.create(
        invoice_number=number, company_name="ТОВ", contact_phone="+380000000000",
        delivery_address="Київ", total_amount=Decimal(amount), order_details={},
        created_by=user, review_status="approved", is_approved=True,
        payment_status="pending", monobank_invoice_id="m-" + number,
    )


@override_settings(MONOBANK_ACQUIRING_TOKEN="acq", MONOBANK_TOKEN="store")
class LedgerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="lmgr", password="x")
        cls.manager.userprofile.manager_commission_percent = Decimal("10")
        cls.manager.userprofile.save()

    def test_commission_creates_frozen_ledger_entry(self):
        from management.services.invoice_payments import apply_payment_status
        inv = _paid_invoice(self.manager, "LED-1")
        apply_payment_status(inv, "success", amount_minor=100000)
        accr = ManagerCommissionAccrual.objects.get(invoice=inv)
        entry = ManagerEarningsLedger.objects.get(
            source_type=ManagerEarningsLedger.SourceType.INVOICE_COMMISSION,
            source_id=str(inv.id),
        )
        self.assertEqual(entry.status, ManagerEarningsLedger.Status.FROZEN)
        self.assertEqual(entry.amount, accr.amount)
        self.assertEqual(entry.available_at, accr.frozen_until)

    def test_release_due_flips_to_available(self):
        from management.services.invoice_payments import apply_payment_status
        inv = _paid_invoice(self.manager, "LED-2")
        apply_payment_status(inv, "success", amount_minor=100000)
        entry = ManagerEarningsLedger.objects.get(source_id=str(inv.id))
        # Перемотуємо available_at у минуле.
        entry.available_at = timezone.now() - timedelta(minutes=1)
        entry.save(update_fields=["available_at"])
        result = ledger.release_due()
        self.assertEqual(result["released"], 1)
        entry.refresh_from_db()
        self.assertEqual(entry.status, ManagerEarningsLedger.Status.AVAILABLE)

    def test_release_cancels_refunded(self):
        from management.services.invoice_payments import apply_payment_status
        inv = _paid_invoice(self.manager, "LED-3")
        apply_payment_status(inv, "success", amount_minor=100000)
        entry = ManagerEarningsLedger.objects.get(source_id=str(inv.id))
        entry.available_at = timezone.now() - timedelta(minutes=1)
        entry.save(update_fields=["available_at"])
        inv.payment_status = "refunded"
        inv.returned_at = timezone.now()
        inv.save(update_fields=["payment_status", "returned_at"])
        result = ledger.release_due()
        self.assertEqual(result["skipped_cancelled"], 1)
        entry.refresh_from_db()
        self.assertEqual(entry.status, ManagerEarningsLedger.Status.CANCELLED)

    def test_release_command_runs(self):
        from management.services.invoice_payments import apply_payment_status
        inv = _paid_invoice(self.manager, "LED-4")
        apply_payment_status(inv, "success", amount_minor=100000)
        entry = ManagerEarningsLedger.objects.get(source_id=str(inv.id))
        entry.available_at = timezone.now() - timedelta(minutes=1)
        entry.save(update_fields=["available_at"])
        call_command("release_frozen_commissions")
        entry.refresh_from_db()
        self.assertEqual(entry.status, ManagerEarningsLedger.Status.AVAILABLE)
