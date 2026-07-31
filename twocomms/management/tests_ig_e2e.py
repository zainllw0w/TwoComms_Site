"""Phase 10 / Task 25 — сквозний e2e потік IG-бота (без мережі, з моками).

Перевіряє зчеплення фаз: шер поста → черга з медіа; угода+proposal →
PaymentAttempt → provider verification → канонічне Instagram-замовлення.
"""
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import urlparse

from django.test import TestCase

from management.models import IgClient, IgDeal, InstagramBotMessage, InstagramBotSettings
from management.services import bot_orders
from management.services import instagram_bot as bot
from orders.models import Order, PaymentAttempt
from orders.nova_poshta_checkout import (
    build_city_choice_token,
    build_warehouse_choice_token,
)


class EndToEndFlowTests(TestCase):
    def setUp(self):
        s = InstagramBotSettings.load()
        s.is_enabled = True
        s.allowed_senders = ""
        s.save()
        self.s = s
        from storefront.models import Category, Product, ProductStatus

        cat = Category.objects.create(name="Худі", slug="hudi-e2e")
        self.product = Product.objects.create(
            title="Худі Kharkiv", slug="hk-e2e", category=cat, price=950,
            status=ProductStatus.PUBLISHED,
        )

    def test_shared_post_enqueues_with_media_and_creates_client(self):
        payload = {"entry": [{"messaging": [{
            "sender": {"id": "e2e1"},
            "message": {"mid": "e2em1", "attachments": [
                {"type": "share", "payload": {"url": "https://cdn/post.jpg"}}
            ]},
        }]}]}
        self.assertEqual(bot.handle_webhook_payload(self.s, payload), 1)
        m = InstagramBotMessage.objects.get(mid="e2em1")
        self.assertIn("post.jpg", m.attachments)
        self.assertTrue(IgClient.objects.filter(igsid="e2e1").exists())

    @patch("storefront.views.monobank._monobank_api_request")
    def test_full_payment_to_order(self, mock_api):
        c = IgClient.get_or_create_for_sender("e2e2")
        # 1) Бот формує first-party proposal. Monobank тут ще не викликається.
        res = bot_orders.create_deal_and_link(c, pay_type="full", product_id=self.product.id, size="M")
        self.assertTrue(res["ok"])
        deal = IgDeal.objects.get(client=c)
        self.assertEqual(deal.invoice_id, "")
        self.assertIn("/offer/a/", res["proposal_url"])
        mock_api.assert_not_called()
        self.assertEqual(deal.amount, Decimal("950"))

        # 2) Клієнт відкриває offer, вводить підписані дані НП і лише тоді
        # стандартний PaymentAttempt створює один invoice Monobank.
        entry = self.client.get(urlparse(res["proposal_url"]).path)
        checkout_path = entry["Location"]
        self.client.get(checkout_path)
        city_token = build_city_choice_token({
            "label": "Київ",
            "settlement_ref": "settlement-e2e",
            "city_ref": "city-e2e",
        })
        warehouse_token = build_warehouse_choice_token({
            "label": "Відділення 1",
            "ref": "warehouse-e2e",
            "kind": "branch",
            "city_ref": "city-e2e",
        })
        mock_api.return_value = {"invoiceId": "e2einv", "pageUrl": "https://pay/e2e"}
        with patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service"
        ) as fb, patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value=True,
        ):
            fb.return_value.send_add_payment_info_event.return_value = True
            payment = self.client.post(
                checkout_path,
                data={
                    "full_name": "Іван Іванов",
                    "phone": "0931112233",
                    "email": "ivan@example.com",
                    "city": "Київ",
                    "np_settlement_ref": "settlement-e2e",
                    "np_city_ref": "city-e2e",
                    "np_city_token": city_token,
                    "np_office": "Відділення 1",
                    "np_warehouse_ref": "warehouse-e2e",
                    "np_warehouse_token": warehouse_token,
                },
            )
        self.assertEqual(payment["Location"], "https://pay/e2e")
        mock_api.assert_called_once()

        # 3) Тільки provider-verified PaymentAttempt матеріалізує Order.
        attempt = PaymentAttempt.objects.get(monobank_invoice_id="e2einv")
        from storefront.views.monobank import _apply_payment_attempt_status

        order, created = _apply_payment_attempt_status(
            attempt,
            "success",
            payload={"status": "success", "amount": 95000, "paidAmount": 95000},
            source="test",
        )
        self.assertTrue(created)
        self.assertIsNotNone(order)

        # 4) Instagram truth is bound to the exact canonical order.
        deal.refresh_from_db()
        self.assertEqual(deal.status, IgDeal.Status.ORDER_CREATED)
        self.assertIsNotNone(deal.order_id)
        order = deal.order
        self.assertEqual(order.sale_source, "Instagram")
        self.assertEqual(order.source, "manual")
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.total_sum, Decimal("950"))
        self.assertEqual(order.items.count(), 1)
        c.refresh_from_db()
        self.assertEqual(c.stage, IgClient.Stage.ORDER_CREATED)
        self.assertEqual(c.purchases_count, 1)
