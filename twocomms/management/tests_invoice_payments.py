"""Тести Фази 3: оплата накладних через Monobank acquiring (mono_hrefs)."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from orders.models import WholesaleInvoice
from management.models import ManagerCommissionAccrual, ManagerCompensationSettings
from management.services import invoice_payments
from management.services.compensation import resolve_commission_terms

User = get_user_model()


def _invoice(user, **extra):
    defaults = dict(
        invoice_number=extra.pop("number", "INV-1"),
        company_name="ТОВ Тест",
        contact_phone="+380000000000",
        delivery_address="Київ",
        total_amount=Decimal("1000.00"),
        order_details={},
        created_by=user,
        review_status="approved",
        is_approved=True,
        payment_status="not_paid",
    )
    defaults.update(extra)
    return WholesaleInvoice.objects.create(**defaults)


@override_settings(
    MONOBANK_ACQUIRING_TOKEN="acq-token",
    MONOBANK_TOKEN="store-token",
    MONOBANK_PUBLIC_BASE_URL="https://twocomms.shop",
    MANAGEMENT_BASE_URL="https://management.twocomms.shop",
)
class CreatePaymentLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="mgr", password="x")

    def test_payload_has_webhook_redirect_and_uses_acquiring_token(self):
        inv = _invoice(self.manager, number="INV-PAY-1")
        captured = {}

        def fake_request(method, endpoint, json_payload=None, params=None, token=None):
            captured["method"] = method
            captured["endpoint"] = endpoint
            captured["payload"] = json_payload
            captured["token"] = token
            return {"invoiceId": "mono-123", "pageUrl": "https://pay.mono/abc"}

        with patch("storefront.views.monobank._monobank_api_request", side_effect=fake_request):
            url, mono_id = invoice_payments.create_payment_link(inv)

        self.assertEqual(url, "https://pay.mono/abc")
        self.assertEqual(mono_id, "mono-123")
        self.assertEqual(captured["token"], "acq-token")  # окремий токен
        self.assertEqual(captured["payload"]["amount"], 100000)  # 1000 грн → копійки
        self.assertEqual(captured["payload"]["webHookUrl"], "https://twocomms.shop/payments/monobank/webhook/")
        self.assertIn("https://management.twocomms.shop/invoices/payment-return/", captured["payload"]["redirectUrl"])
        self.assertEqual(captured["payload"]["merchantPaymInfo"]["reference"], f"MGMT-INV-{inv.id}")


@override_settings(MONOBANK_ACQUIRING_TOKEN="acq-token", MONOBANK_TOKEN="store-token")
class ApplyStatusAndCommissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="mgr2", password="x")
        cls.manager.userprofile.manager_commission_percent = Decimal("10")
        cls.manager.userprofile.save()

    def test_paid_sets_fields_and_creates_commission_once(self):
        inv = _invoice(self.manager, number="INV-PAID-1", payment_status="pending",
                       monobank_invoice_id="mono-xyz")
        changed = invoice_payments.apply_payment_status(inv, "success", amount_minor=100000)
        self.assertTrue(changed)
        inv.refresh_from_db()
        self.assertEqual(inv.payment_status, "paid")
        self.assertIsNotNone(inv.paid_at)
        self.assertEqual(inv.payment_amount_minor, 100000)
        accr = ManagerCommissionAccrual.objects.get(invoice=inv)
        self.assertEqual(accr.amount, Decimal("100.00"))  # 10% від 1000
        self.assertEqual(accr.percent, Decimal("10"))
        # Ідемпотентність: повторне застосування не дублює.
        self.assertFalse(invoice_payments.apply_payment_status(inv, "success", amount_minor=100000))
        self.assertEqual(ManagerCommissionAccrual.objects.filter(invoice=inv).count(), 1)

    def test_commission_uses_compensation_settings_and_frozen_days(self):
        ManagerCompensationSettings.objects.create(
            owner=self.manager, monthly_base_amount=Decimal("0"), commission_percent=Decimal("20"),
            frozen_days=7, effective_from=date.today() - timedelta(days=1),
        )
        percent, frozen_days = resolve_commission_terms(self.manager)
        self.assertEqual(percent, Decimal("20"))
        self.assertEqual(frozen_days, 7)

        inv = _invoice(self.manager, number="INV-PAID-2", payment_status="pending", monobank_invoice_id="m2")
        invoice_payments.apply_payment_status(inv, "success", amount_minor=50000)  # 500 грн факт
        accr = ManagerCommissionAccrual.objects.get(invoice=inv)
        self.assertEqual(accr.base_amount, Decimal("500.00"))  # база = фактично оплачено
        self.assertEqual(accr.amount, Decimal("100.00"))  # 20% від 500
        # заморозка ~7 днів від paid_at
        inv.refresh_from_db()
        delta_days = (accr.frozen_until - inv.paid_at).days
        self.assertEqual(delta_days, 7)

    def test_failure_keeps_monobank_id_for_polling(self):
        inv = _invoice(self.manager, number="INV-FAIL-1", payment_status="pending",
                       payment_url="https://pay.mono/x", monobank_invoice_id="m3")
        invoice_payments.apply_payment_status(inv, "expired")
        inv.refresh_from_db()
        self.assertEqual(inv.payment_status, "failed")
        self.assertEqual(inv.monobank_invoice_id, "m3")  # не обнуляємо

    def test_sync_pulls_status(self):
        inv = _invoice(self.manager, number="INV-SYNC-1", payment_status="pending", monobank_invoice_id="m4")
        with patch("storefront.views.monobank._monobank_api_request",
                   return_value={"invoiceId": "m4", "status": "success", "amount": 100000}):
            status = invoice_payments.sync_invoice_payment(inv)
        self.assertEqual(status, "success")
        inv.refresh_from_db()
        self.assertEqual(inv.payment_status, "paid")

    def test_poll_command_confirms_pending(self):
        from django.core.management import call_command
        inv = _invoice(self.manager, number="INV-POLL-1", payment_status="pending",
                       monobank_invoice_id="mpoll", payment_link_created_at=timezone.now())
        with patch("storefront.views.monobank._monobank_api_request",
                   return_value={"invoiceId": "mpoll", "status": "success", "amount": 100000}):
            call_command("poll_wholesale_invoice_payments")
        inv.refresh_from_db()
        self.assertEqual(inv.payment_status, "paid")
        self.assertEqual(ManagerCommissionAccrual.objects.filter(invoice=inv).count(), 1)


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop"],
    MONOBANK_ACQUIRING_TOKEN="acq-token",
)
class CreatePaymentEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="mgr3", password="x")
        cls.manager.userprofile.is_manager = True
        cls.manager.userprofile.save()

    def test_endpoint_creates_link(self):
        inv = _invoice(self.manager, number="INV-EP-1")
        self.client.force_login(self.manager)
        with patch("storefront.views.monobank._monobank_api_request",
                   return_value={"invoiceId": "mono-ep", "pageUrl": "https://pay.mono/ep"}):
            resp = self.client.post(
                f"/invoices/api/{inv.id}/create-payment/",
                data="{}", content_type="application/json",
                HTTP_HOST="management.twocomms.shop", secure=True,
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["payment_url"], "https://pay.mono/ep")
        inv.refresh_from_db()
        self.assertEqual(inv.payment_status, "pending")
        self.assertEqual(inv.monobank_reference, f"MGMT-INV-{inv.id}")
        self.assertIsNotNone(inv.payment_link_created_at)
