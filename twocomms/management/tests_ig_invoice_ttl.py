"""W4B / IMP-050 — у ссылки на оплату появляется срок жизни.

Блокирующее противоречие, определившее порядок всей волны: заказчик хочет
сообщение «у вас закінчилось посилання», но у ссылки **нет TTL** и истечение
ненаблюдаемо. Сейчас бот говорит «посилання ще активне», не проверив ничего,
а `ensure_invoice` переиспользует любой существующий `invoice_id` независимо от
того, сколько ему дней.

Сначала делаем факт наблюдаемым, потом строим на нём каскад — иначе бот будет
утверждать неправду, а это дороже, чем молчание.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.ig_bot_models import IgClient, IgDeal, IgDealItem


class InvoiceTtlMixin:
    def _deal(self, key, *, amount="990.00"):
        client = IgClient.get_or_create_for_sender(key)
        deal = IgDeal.objects.create(
            client=client,
            status=IgDeal.Status.AWAITING_PAYMENT,
            payment_status="unpaid",
            pay_type=IgDeal.PayType.ONLINE_FULL,
        )
        IgDealItem.objects.create(
            deal=deal, title="Футболка", qty=1, unit_price=Decimal(amount)
        )
        deal.recalc_total()
        deal.refresh_from_db()
        return deal

    def _fake_invoice(self, invoice_id="inv-1"):
        return {
            "result": {
                "invoiceId": invoice_id,
                "pageUrl": f"https://pay.mbnk.biz/{invoice_id}",
            }
        }


class InvoiceValidityTests(InvoiceTtlMixin, TestCase):
    def test_created_invoice_sends_validity_to_the_provider(self):
        from management.services import bot_payments

        deal = self._deal("ttl-validity")

        with patch(
            "storefront.views.monobank._monobank_api_request",
            return_value=self._fake_invoice(),
        ) as api:
            result = bot_payments.create_payment_link(deal)

        self.assertTrue(result["ok"], result)
        payload = api.call_args.kwargs["json_payload"]
        self.assertEqual(payload["validity"], bot_payments.INVOICE_VALIDITY_SECONDS)

    def test_created_invoice_records_its_expiry(self):
        from management.services import bot_payments

        deal = self._deal("ttl-expiry-recorded")
        before = timezone.now()

        with patch(
            "storefront.views.monobank._monobank_api_request",
            return_value=self._fake_invoice(),
        ):
            bot_payments.create_payment_link(deal)

        deal.refresh_from_db()
        self.assertIsNotNone(deal.invoice_expires_at)
        expected = before + timedelta(
            seconds=bot_payments.INVOICE_VALIDITY_SECONDS
        )
        self.assertLess(abs((deal.invoice_expires_at - expected).total_seconds()), 60)

    def test_live_invoice_is_reused(self):
        from management.services import bot_payments

        deal = self._deal("ttl-reuse-live")
        deal.invoice_id = "inv-live"
        deal.invoice_url = "https://pay.mbnk.biz/inv-live"
        deal.invoice_expires_at = timezone.now() + timedelta(hours=5)
        deal.save(update_fields=[
            "invoice_id", "invoice_url", "invoice_expires_at", "updated_at",
        ])

        with patch("storefront.views.monobank._monobank_api_request") as api:
            result = bot_payments.create_payment_link(deal)

        self.assertTrue(result.get("reused"))
        self.assertEqual(api.call_count, 0)

    def test_expired_invoice_is_not_reused(self):
        """Главный дефект: переиспользовалась любая ссылка, даже мёртвая."""
        from management.services import bot_payments

        deal = self._deal("ttl-reuse-expired")
        deal.invoice_id = "inv-dead"
        deal.invoice_url = "https://pay.mbnk.biz/inv-dead"
        deal.invoice_expires_at = timezone.now() - timedelta(minutes=1)
        deal.save(update_fields=[
            "invoice_id", "invoice_url", "invoice_expires_at", "updated_at",
        ])

        with patch(
            "storefront.views.monobank._monobank_api_request",
            return_value=self._fake_invoice("inv-fresh"),
        ) as api:
            result = bot_payments.create_payment_link(deal)

        self.assertEqual(api.call_count, 1)
        self.assertFalse(result.get("reused"))
        deal.refresh_from_db()
        self.assertEqual(deal.invoice_id, "inv-fresh")

    def test_replacing_an_expired_invoice_keeps_its_id_in_history(self):
        """Иначе оплата по старой ссылке снова станет «потерянным платежом»."""
        from management.services import bot_payments

        deal = self._deal("ttl-history")
        deal.invoice_id = "inv-dead"
        deal.invoice_url = "https://pay.mbnk.biz/inv-dead"
        deal.invoice_expires_at = timezone.now() - timedelta(minutes=1)
        deal.save(update_fields=[
            "invoice_id", "invoice_url", "invoice_expires_at", "updated_at",
        ])

        with patch(
            "storefront.views.monobank._monobank_api_request",
            return_value=self._fake_invoice("inv-fresh"),
        ):
            bot_payments.create_payment_link(deal)

        deal.refresh_from_db()
        self.assertIn("inv-dead", deal.superseded_invoice_ids)

    def test_invoice_without_a_recorded_expiry_is_treated_as_live(self):
        """Обратная совместимость: у существующих сделок поля ещё нет."""
        from management.services import bot_payments

        deal = self._deal("ttl-legacy-null")
        deal.invoice_id = "inv-legacy"
        deal.invoice_url = "https://pay.mbnk.biz/inv-legacy"
        deal.save(update_fields=["invoice_id", "invoice_url", "updated_at"])

        with patch("storefront.views.monobank._monobank_api_request") as api:
            result = bot_payments.create_payment_link(deal)

        self.assertTrue(result.get("reused"))
        self.assertEqual(api.call_count, 0)


class InvoiceExpiryStateTests(InvoiceTtlMixin, TestCase):
    def test_helper_reports_a_live_link(self):
        from management.services.bot_payments import invoice_link_state

        deal = self._deal("ttl-state-live")
        deal.invoice_id = "inv-live"
        deal.invoice_url = "https://pay.mbnk.biz/inv-live"
        deal.invoice_expires_at = timezone.now() + timedelta(hours=2)

        state = invoice_link_state(deal)

        self.assertEqual(state["status"], "live")
        self.assertFalse(state["expired"])

    def test_helper_reports_an_expired_link(self):
        from management.services.bot_payments import invoice_link_state

        deal = self._deal("ttl-state-expired")
        deal.invoice_id = "inv-dead"
        deal.invoice_url = "https://pay.mbnk.biz/inv-dead"
        deal.invoice_expires_at = timezone.now() - timedelta(hours=2)

        state = invoice_link_state(deal)

        self.assertEqual(state["status"], "expired")
        self.assertTrue(state["expired"])

    def test_helper_reports_absence_of_a_link(self):
        from management.services.bot_payments import invoice_link_state

        state = invoice_link_state(self._deal("ttl-state-none"))

        self.assertEqual(state["status"], "none")
        self.assertFalse(state["expired"])

    def test_helper_reports_unknown_for_a_legacy_link(self):
        """Честнее «неизвестно», чем «активно» без основания."""
        from management.services.bot_payments import invoice_link_state

        deal = self._deal("ttl-state-unknown")
        deal.invoice_id = "inv-legacy"
        deal.invoice_url = "https://pay.mbnk.biz/inv-legacy"

        state = invoice_link_state(deal)

        self.assertEqual(state["status"], "unknown")
        self.assertFalse(state["expired"])

    def test_paid_deal_link_state_is_not_expired(self):
        from management.services.bot_payments import invoice_link_state

        deal = self._deal("ttl-state-paid")
        deal.invoice_id = "inv-paid"
        deal.invoice_url = "https://pay.mbnk.biz/inv-paid"
        deal.invoice_expires_at = timezone.now() - timedelta(hours=2)
        deal.status = IgDeal.Status.PAID
        deal.payment_status = "paid"

        state = invoice_link_state(deal)

        self.assertEqual(state["status"], "paid")
        self.assertFalse(state["expired"])
