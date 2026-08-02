"""Regression tests for W4 customer-facing payment and shipment copy."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from django.test import SimpleTestCase, TestCase

from management.models import IgClient
from management.services import bot_orders
from management.services import instagram_bot as bot
from management.services.ig_order_fulfillment import _message


class ShipmentCopyTests(SimpleTestCase):
    def setUp(self):
        self.order = SimpleNamespace(order_number="TWC-W4-01", pk=1)

    def test_ttn_copy_sets_delivery_expectations_without_payment_or_exchange_claims(self):
        expected = {
            "uk": (("вже в дорозі", "1-3 робочі дні"), ("оплачен", "обмін", "розмір")),
            "ru": (("уже в пути", "1-3 рабочих дня"), ("оплачен", "обмен", "размер")),
            "en": (("on its way", "1-3 business days"), ("paid", "payment", "exchange", "size")),
        }

        for locale, (required, forbidden) in expected.items():
            with self.subTest(locale=locale):
                text = _message(
                    "ttn_assigned",
                    locale,
                    self.order,
                    "20400000000000",
                ).lower()
                for phrase in required:
                    self.assertIn(phrase, text)
                for phrase in forbidden:
                    self.assertNotIn(phrase, text)

    def test_exchange_shipped_copy_confirms_replacement_without_payment_claims(self):
        expected = {
            "uk": (
                (
                    "підтверджена",
                    "вже в дорозі",
                    "розмір m",
                    "нова ттн",
                    "1-3 робочі дні",
                ),
                ("оплат", "сплачен", "доплач", "не підійде"),
            ),
            "ru": (
                (
                    "подтверждена",
                    "уже в пути",
                    "размер m",
                    "новый номер ттн",
                    "1-3 рабочих дня",
                ),
                ("оплат", "доплач", "не подойдет"),
            ),
            "en": (
                (
                    "confirmed",
                    "already on its way",
                    "size m",
                    "new nova poshta tracking number",
                    "1-3 business days",
                ),
                ("paid", "payment", "pay", "doesn't fit"),
            ),
        }

        for locale, (required, forbidden) in expected.items():
            with self.subTest(locale=locale):
                text = _message(
                    "exchange_shipped",
                    locale,
                    self.order,
                    "20400000000001",
                    exchange_size="M",
                ).lower()
                for phrase in forbidden:
                    self.assertNotIn(phrase, text)
                for phrase in required:
                    self.assertIn(phrase, text)
                self.assertIn(
                    "https://novaposhta.ua/tracking/?cargo_number=20400000000001",
                    text,
                )

    def test_exchange_shipped_copy_without_size_keeps_shipment_facts(self):
        expected = {
            "uk": (
                (
                    "заміна підтверджена",
                    "вже в дорозі",
                    "нова ттн",
                    "1-3 робочі дні",
                ),
                ("розмір", "оплат", "сплачен", "доплач"),
            ),
            "ru": (
                (
                    "замена подтверждена",
                    "уже в пути",
                    "новый номер ттн",
                    "1-3 рабочих дня",
                ),
                ("размер", "оплат", "доплач"),
            ),
            "en": (
                (
                    "exchange is confirmed",
                    "already on its way",
                    "new nova poshta tracking number",
                    "1-3 business days",
                ),
                ("size", "paid", "payment", "pay"),
            ),
        }

        for locale, (required, forbidden) in expected.items():
            with self.subTest(locale=locale):
                text = _message(
                    "exchange_shipped",
                    locale,
                    self.order,
                    "20400000000002",
                    exchange_size="",
                ).lower()
                for phrase in forbidden:
                    self.assertNotIn(phrase, text)
                for phrase in required:
                    self.assertIn(phrase, text)
                self.assertIn(
                    "https://novaposhta.ua/tracking/?cargo_number=20400000000002",
                    text,
                )


class OfferCopyTests(SimpleTestCase):
    def test_order_summary_is_localized_without_losing_commercial_facts(self):
        summary = {
            "items": [
                {
                    "title": "Reality Bends",
                    "size": "M",
                    "quantity": 2,
                }
            ],
            "quoted_total": "1580.00",
        }

        expected = {
            "uk": ("Замовлення", "розмір M", "2 шт.", "1580 грн", "скрин"),
            "ru": ("Заказ", "размер M", "2 шт.", "1580 грн", "скрин"),
            "en": ("Order", "size M", "2 pcs", "1580 UAH", "screenshot"),
        }
        for locale, phrases in expected.items():
            with self.subTest(locale=locale):
                text = bot._checkout_offer_details(locale, summary)
                for phrase in phrases:
                    self.assertIn(phrase, text)

    def test_empty_summary_does_not_invent_order_details(self):
        self.assertEqual(bot._checkout_offer_details("uk", {}), "")


class CheckoutProposalSummaryTests(SimpleTestCase):
    @patch("management.models.IgCheckoutAccessToken.issue")
    @patch("management.services.bot_orders.create_checkout_proposal")
    def test_link_result_exposes_only_frozen_proposal_facts(self, create_proposal, issue):
        item = SimpleNamespace(
            product_title="Reality Bends",
            size="M",
            quantity=2,
        )
        proposal = SimpleNamespace(
            public_id=uuid.uuid4(),
            quoted_total=Decimal("1580.00"),
            items=SimpleNamespace(all=lambda: [item]),
        )
        create_proposal.return_value = proposal
        issue.return_value = (
            "w4-frozen-token",
            SimpleNamespace(expires_at=SimpleNamespace(isoformat=lambda: "2026-08-02T12:00:00+00:00")),
        )

        result = bot_orders.create_checkout_proposal_link(
            SimpleNamespace(),
            item_specs=[{"product_id": 1, "size": "M", "qty": 2}],
        )

        self.assertEqual(
            result["order_summary"],
            {
                "items": [
                    {"title": "Reality Bends", "size": "M", "quantity": 2}
                ],
                "quoted_total": "1580.00",
            },
        )


class FinalizeOfferCopyTests(TestCase):
    def setUp(self):
        self.client_record = IgClient.get_or_create_for_sender("w4-offer-copy")
        self.client_record.intent = IgClient.Intent.PAYMENT
        self.client_record.stage = IgClient.Stage.CHECKOUT
        self.client_record.language = "uk"
        self.client_record.save(
            update_fields=["intent", "stage", "language", "updated_at"]
        )

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_successful_offer_includes_exact_order_summary(self, create_link, _notify):
        create_link.return_value = {
            "ok": True,
            "invoice_url": "https://twocomms.shop/offer/a/w4-token/",
            "proposal_url": "https://twocomms.shop/offer/a/w4-token/",
            "order_summary": {
                "items": [
                    {"title": "Reality Bends", "size": "M", "quantity": 2}
                ],
                "quoted_total": str(Decimal("1580.00")),
            },
        }

        text = bot.finalize_paylink(
            "Готово, зараз надішлю посилання на оплату.",
            {"paylink": "full", "product": 1},
            self.client_record,
            self.client_record.igsid,
        )

        self.assertIn("Reality Bends", text)
        self.assertIn("розмір M", text)
        self.assertIn("1580 грн", text)
        self.assertIn("Monobank", text)
        self.assertIn("нічого надсилати не треба", text)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_offer_copy_is_not_repeated_when_model_already_used_it(
        self, create_link, _notify
    ):
        create_link.return_value = {
            "ok": True,
            "invoice_url": "https://twocomms.shop/offer/a/w4-repeat/",
        }

        text = bot.finalize_paylink(
            "Перевірте товари в персональній пропозиції TwoComms. "
            "Зараз надішлю посилання на оплату.",
            {"paylink": "full", "product": 1},
            self.client_record,
            self.client_record.igsid,
        )

        self.assertEqual(text.count("Перевірте товари"), 1)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_failed_offer_uses_the_client_language(self, create_link, _notify):
        create_link.return_value = {"ok": False, "error": "provider_error"}
        self.client_record.language = "ru"
        self.client_record.save(update_fields=["language", "updated_at"])

        text = bot.finalize_paylink(
            "Вот ссылка на оплату.",
            {"paylink": "full", "product": 1},
            self.client_record,
            self.client_record.igsid,
        )

        self.assertIn("Уточню детали", text)
        self.assertNotIn("Уточню деталі", text)
