"""W2 / IMP-010 — платёж по замещённой ссылке не теряется (F-PAY-001).

Механика дефекта: при смене товара или типа оплаты система обнуляет
`deal.invoice_id`, но инвойс в Monobank остаётся оплачиваемым. Если клиент
откроет старую ссылку и заплатит, webhook придёт, `handle_webhook_invoice`
не найдёт сделку по `invoice_id`, вернёт False — и деньги получены, а сделки
и заказа нет, менеджер не уведомлён.

Инвариант: замещённый `invoice_id` сохраняется в истории сделки, платёж
по нему опознаётся, и менеджер об этом узнаёт.
"""
from unittest.mock import patch

from django.test import TestCase

from management.models import IgClient, IgDeal


class SupersedeInvoiceTests(TestCase):
    def setUp(self):
        self.client_card = IgClient.objects.create(
            igsid="8000000001", username="invoice_client"
        )
        self.deal = IgDeal.objects.create(
            client=self.client_card,
            amount="900.00",
            pay_type=IgDeal.PayType.ONLINE_FULL,
            invoice_id="mono-invoice-old",
            invoice_url="https://pay.mbnk.biz/old",
            status=IgDeal.Status.AWAITING_PAYMENT,
        )

    def test_supersede_records_history_and_clears_invoice(self):
        from management.services.bot_payments import supersede_invoice

        fields = supersede_invoice(self.deal)
        self.deal.save(update_fields=[*fields, "updated_at"])

        self.deal.refresh_from_db()
        self.assertEqual(self.deal.invoice_id, "")
        self.assertEqual(self.deal.invoice_url, "")
        self.assertIn("mono-invoice-old", self.deal.superseded_invoice_ids)

    def test_history_has_no_duplicates_and_keeps_order(self):
        from management.services.bot_payments import supersede_invoice

        supersede_invoice(self.deal)
        supersede_invoice(self.deal)
        self.deal.invoice_id = "mono-invoice-second"
        supersede_invoice(self.deal)

        self.assertEqual(
            self.deal.superseded_invoice_ids,
            ["mono-invoice-old", "mono-invoice-second"],
        )

    def test_empty_invoice_is_not_recorded(self):
        from management.services.bot_payments import supersede_invoice

        self.deal.invoice_id = ""
        self.deal.invoice_url = ""

        supersede_invoice(self.deal)

        self.assertEqual(self.deal.superseded_invoice_ids, [])

    def test_supersede_materializes_bounded_invoice_lifecycle(self):
        from management.models import IgDealInvoiceLifecycle
        from management.services.bot_payments import supersede_invoice

        fields = supersede_invoice(self.deal)
        self.deal.save(update_fields=[*fields, "updated_at"])

        lifecycle = IgDealInvoiceLifecycle.objects.get(invoice_id="mono-invoice-old")
        self.assertEqual(lifecycle.deal_id, self.deal.pk)
        self.assertIsNotNone(lifecycle.superseded_at)
        self.assertEqual(lifecycle.status, IgDealInvoiceLifecycle.Status.OPEN)

    def test_legacy_materialization_is_idempotent(self):
        from management.models import IgDealInvoiceLifecycle
        from management.services.bot_payments import (
            _materialize_superseded_invoice_lifecycles,
        )

        self.deal.superseded_invoice_ids = ["mono-invoice-legacy"]
        self.deal.save(update_fields=["superseded_invoice_ids", "updated_at"])

        _materialize_superseded_invoice_lifecycles()
        _materialize_superseded_invoice_lifecycles()

        self.assertEqual(
            IgDealInvoiceLifecycle.objects.filter(
                invoice_id="mono-invoice-legacy", deal=self.deal
            ).count(),
            1,
        )


class WebhookForSupersededInvoiceTests(TestCase):
    def setUp(self):
        self.client_card = IgClient.objects.create(
            igsid="8000000002", username="webhook_client"
        )
        self.deal = IgDeal.objects.create(
            client=self.client_card,
            amount="900.00",
            pay_type=IgDeal.PayType.ONLINE_FULL,
            invoice_id="mono-invoice-current",
            status=IgDeal.Status.AWAITING_PAYMENT,
            superseded_invoice_ids=["mono-invoice-old"],
        )

    def test_webhook_for_superseded_invoice_finds_the_deal(self):
        from management.services.bot_payments import handle_webhook_invoice

        self.client_card.username = "private.invoice-alert@example.com"
        self.client_card.save(update_fields=["username", "updated_at"])
        with patch(
            "management.services.bot_payments.poll_deal_status", return_value="success"
        ) as poll, patch(
            "management.services.instagram_bot.notify_manager"
        ) as notify:
            handled = handle_webhook_invoice("mono-invoice-old")

        self.assertTrue(
            handled, "платёж по старой ссылке должен быть опознан, а не потерян"
        )
        self.assertTrue(poll.called)
        self.assertTrue(
            notify.called,
            "менеджер должен узнать о платеже по замещённой ссылке",
        )
        alert = notify.call_args.args[0]
        self.assertNotIn(self.client_card.username, alert)
        self.assertNotIn("mono-invoice-old", alert)
        self.assertIn(f"Клієнт ID: {self.client_card.pk}", alert)
        self.assertIn(f"Угода ID: {self.deal.pk}", alert)

    def test_current_invoice_still_wins_and_does_not_alert(self):
        from management.services.bot_payments import handle_webhook_invoice

        with patch(
            "management.services.bot_payments.poll_deal_status", return_value="success"
        ) as poll, patch(
            "management.services.instagram_bot.notify_manager"
        ) as notify:
            handled = handle_webhook_invoice("mono-invoice-current")

        self.assertTrue(handled)
        self.assertTrue(poll.called)
        self.assertFalse(
            notify.called,
            "обычный платёж по актуальному инвойсу не требует разбора",
        )

    def test_unknown_invoice_still_returns_false(self):
        from management.services.bot_payments import handle_webhook_invoice

        with patch("management.services.instagram_bot.notify_manager"):
            self.assertFalse(handle_webhook_invoice("mono-invoice-never-existed"))

    def test_superseded_lookup_is_not_a_substring_match(self):
        """`old` не должен совпасть с `mono-invoice-older`."""
        from management.services.bot_payments import handle_webhook_invoice

        with patch("management.services.bot_payments.poll_deal_status"), patch(
            "management.services.instagram_bot.notify_manager"
        ):
            self.assertFalse(handle_webhook_invoice("mono-invoice-ol"))

    @patch("management.services.bot_payments.apply_payment_status")
    @patch(
        "storefront.views.monobank._monobank_api_request",
        return_value={"status": "success", "invoiceId": "mono-invoice-old"},
    )
    def test_superseded_poll_uses_old_invoice_without_applying_to_replacement(
        self, provider, apply_status
    ):
        from management.models import IgDealInvoiceLifecycle
        from management.services.bot_payments import poll_deal_status, supersede_invoice

        self.deal.invoice_id = "mono-invoice-old"
        self.deal.save(update_fields=["invoice_id", "updated_at"])
        fields = supersede_invoice(self.deal)
        self.deal.save(update_fields=[*fields, "updated_at"])

        status = poll_deal_status(
            self.deal,
            invoice_id="mono-invoice-old",
            apply=False,
        )

        self.assertEqual(status, "success")
        provider.assert_called_once()
        self.assertEqual(provider.call_args.kwargs["params"], {"invoiceId": "mono-invoice-old"})
        apply_status.assert_not_called()
        self.assertEqual(
            IgDealInvoiceLifecycle.objects.get(invoice_id="mono-invoice-old").status,
            IgDealInvoiceLifecycle.Status.PAID,
        )
