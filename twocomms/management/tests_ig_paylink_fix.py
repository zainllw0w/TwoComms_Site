"""Фікс продакшен-бага: бот обіцяв посилання на оплату, але не надсилав.

Причина: модель не передавала [PRODUCT:id] (каталог не давав id), а без нього
create_deal_and_link тихо повертав no_items. Фікс: серверне розв'язання товару
з контексту + тригер по фразі-обіцянці, не лише по тегу.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from management.models import IgClient, IgDeal, InstagramBotMessage
from management.services import bot_orders
from management.services import instagram_bot as bot


def _pub_product(title, slug, price=788):
    from storefront.models import Category, Product, ProductStatus

    cat, _ = Category.objects.get_or_create(name="Футболки", slug="tees-plf")
    return Product.objects.create(
        title=title, slug=slug, category=cat, price=price, status=ProductStatus.PUBLISHED
    )


class ResolveProductTests(TestCase):
    def setUp(self):
        self.p = _pub_product("Футболка TWOCOMMS «Череп з дупою»", "skull-rp")
        self.c = IgClient.get_or_create_for_sender("rp1")

    def test_explicit_id(self):
        self.assertEqual(bot_orders.resolve_product_for_payment(self.c, self.p.id).id, self.p.id)

    def test_from_recent_bot_message(self):
        InstagramBotMessage.objects.create(
            sender_id="rp1", client=self.c, role="model",
            text="Оформлюємо «Череп з дупою» за 788 грн?",
        )
        got = bot_orders.resolve_product_for_payment(self.c, None)
        self.assertIsNotNone(got)
        self.assertEqual(got.id, self.p.id)

    def test_none_when_nothing(self):
        self.assertIsNone(bot_orders.resolve_product_for_payment(self.c, None))


class WantsPaylinkTests(SimpleTestCase):
    def test_tag(self):
        w, pt = bot._wants_paylink("ок", {"paylink": "prepay"})
        self.assertTrue(w)
        self.assertEqual(pt, "prepay")

    def test_phrase_prepay(self):
        w, pt = bot._wants_paylink("Зараз сформую посилання на передоплату 200 грн", {})
        self.assertTrue(w)
        self.assertEqual(pt, "prepay")

    def test_phrase_full(self):
        w, pt = bot._wants_paylink("Ось посилання на оплату:", {})
        self.assertTrue(w)
        self.assertEqual(pt, "full")

    def test_no_phrase(self):
        w, pt = bot._wants_paylink("Привіт, що бажаєте обрати?", {})
        self.assertFalse(w)


class CreateDealResolvesProductTests(TestCase):
    @patch("management.services.bot_orders.create_payment_link")
    def test_builds_deal_from_context_product(self, mock_link):
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/z", "invoice_id": "z"}
        p = _pub_product("Футболка «Череп з дупою»", "skull-cd")
        c = IgClient.get_or_create_for_sender("cd1")
        InstagramBotMessage.objects.create(
            sender_id="cd1", client=c, role="model", text="Зупиняємось на «Череп з дупою»",
        )
        res = bot_orders.create_deal_and_link(c, pay_type="prepay", product_id=None)
        self.assertTrue(res["ok"])
        deal = IgDeal.objects.filter(client=c).first()
        self.assertIsNotNone(deal)
        self.assertEqual(deal.items.count(), 1)
        self.assertEqual(deal.items.first().product_id, p.id)
        self.assertEqual(deal.pay_type, IgDeal.PayType.PREPAY_200)

    def test_no_product_no_items_returns_error(self):
        c = IgClient.get_or_create_for_sender("cd2")
        res = bot_orders.create_deal_and_link(c, pay_type="full", product_id=None)
        self.assertFalse(res["ok"])
