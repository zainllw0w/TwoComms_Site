"""Э7.3 / Э1.6 — яке саме посилання просить клієнт, і чому воно завжди кнопкою.

Регресія з прогону на власному акаунті: на «дай посилання» після розмови про
оплату бот надіслав посилання на САЙТ, голим URL у тексті. Тут закріплені обидва
правила: ціль виводиться зі стану (а при неоднозначності — питається), і жодне
рішення з URL не існує без карточки.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from management.models import IgClient, IgDeal
from management.services import ig_link_intent as intent
from management.services import ig_message_templates as tpl


class LinkRequestClassificationTests(SimpleTestCase):
    def test_payment_context_names_the_target(self):
        for text in (
            "дай посилання на оплату",
            "скинь ссылку на оплату пожалуйста",
            "can you send the payment link",
            "де рахунок? дай лінк",
        ):
            with self.subTest(text=text):
                request = intent.classify_request(text)
                self.assertTrue(request.asked)
                self.assertEqual(request.target, intent.TARGET_PAYMENT)

    def test_site_context_names_the_target(self):
        request = intent.classify_request("скинь посилання на сайт")
        self.assertTrue(request.asked)
        self.assertEqual(request.target, intent.TARGET_SITE)

    def test_bare_link_request_leaves_the_target_unnamed(self):
        """Саме цей випадок бот раніше вгадував — і вгадував неправильно."""
        for text in ("дай посилання", "скинь ссылку", "send me the link"):
            with self.subTest(text=text):
                request = intent.classify_request(text)
                self.assertTrue(request.asked)
                self.assertEqual(request.target, "")
                self.assertIn("target_unnamed", request.reason_codes)

    def test_refusal_is_not_a_request(self):
        for text in (
            "посилання не потрібне",
            "ссылку не надо",
            "do not send the link",
        ):
            with self.subTest(text=text):
                self.assertFalse(intent.classify_request(text).asked)

    def test_text_without_a_link_reference_is_not_a_request(self):
        self.assertFalse(intent.classify_request("скільки коштує худі?").asked)
        self.assertFalse(intent.classify_request("").asked)


class PaymentLinkResolutionTests(TestCase):
    def setUp(self):
        self.client_row = IgClient.get_or_create_for_sender("link-intent-1")
        self.request = intent.classify_request("дай посилання на оплату")

    def _deal(self, **kwargs):
        defaults = {
            "client": self.client_row,
            "status": IgDeal.Status.QUOTED,
            "amount": Decimal("950.00"),
            "requested_payment_amount": Decimal("950.00"),
        }
        defaults.update(kwargs)
        return IgDeal.objects.create(**defaults)

    def test_live_invoice_is_returned_as_a_button(self):
        deal = self._deal(
            invoice_id="inv-live",
            invoice_url="https://pay.mbnk.biz/inv-live",
            invoice_expires_at=timezone.now() + timedelta(minutes=20),
        )
        resolution = intent.resolve(self.request, deal=deal)

        self.assertEqual(resolution.kind, intent.KIND_PAYMENT)
        self.assertEqual(resolution.url, "https://pay.mbnk.biz/inv-live")
        self.assertIsInstance(resolution.card, tpl.ButtonTemplate)
        button = resolution.card.buttons[0]
        self.assertEqual(button.kind, tpl.BUTTON_WEB_URL)
        self.assertEqual(button.url, "https://pay.mbnk.biz/inv-live")

    def test_expired_invoice_is_never_handed_out(self):
        """Мертвий URL — це 404 у клієнта. Замість нього пропонується перевипуск."""
        deal = self._deal(
            invoice_id="inv-dead",
            invoice_url="https://pay.mbnk.biz/inv-dead",
            invoice_expires_at=timezone.now() - timedelta(minutes=5),
        )
        resolution = intent.resolve(self.request, deal=deal)

        self.assertEqual(resolution.kind, intent.KIND_REISSUE)
        self.assertEqual(resolution.url, "")
        self.assertNotIn("inv-dead", str(resolution.card))
        self.assertEqual(resolution.card.buttons[0].kind, tpl.BUTTON_POSTBACK)

    def test_invoice_with_unknown_ttl_is_not_guessed_alive(self):
        deal = self._deal(
            invoice_id="inv-unknown",
            invoice_url="https://pay.mbnk.biz/inv-unknown",
            invoice_expires_at=None,
        )
        resolution = intent.resolve(self.request, deal=deal)

        self.assertEqual(resolution.kind, intent.KIND_NOT_ISSUED)
        self.assertEqual(resolution.url, "")
        self.assertIn("invoice_unknown", resolution.reason_codes)

    def test_paid_deal_offers_no_link_at_all(self):
        deal = self._deal(status=IgDeal.Status.PAID, invoice_id="x", invoice_url="y")
        resolution = intent.resolve(self.request, deal=deal)

        self.assertEqual(resolution.kind, intent.KIND_ALREADY_PAID)
        self.assertEqual(resolution.url, "")

    def test_no_deal_says_the_link_does_not_exist_yet(self):
        resolution = intent.resolve(self.request, deal=None)

        self.assertEqual(resolution.kind, intent.KIND_NOT_ISSUED)
        self.assertEqual(resolution.url, "")
        self.assertTrue(resolution.note)


class AmbiguousLinkTests(TestCase):
    def setUp(self):
        self.client_row = IgClient.get_or_create_for_sender("link-intent-2")
        self.request = intent.classify_request("дай посилання")

    def test_more_than_one_plausible_target_asks_one_question(self):
        """Замість ставки на одну ціль — одне питання з кнопками."""
        deal = IgDeal.objects.create(
            client=self.client_row,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("1090.00"),
            invoice_id="inv-live",
            invoice_url="https://pay.mbnk.biz/inv-live",
            invoice_expires_at=timezone.now() + timedelta(minutes=20),
        )
        resolution = intent.resolve(
            self.request, deal=deal, product_url="https://twocomms.shop/product/tee/"
        )

        self.assertEqual(resolution.kind, intent.KIND_ASK)
        self.assertEqual(resolution.url, "")
        self.assertIsInstance(resolution.card, tpl.QuickReplyMessage)
        titles = [reply.title for reply in resolution.card.quick_replies]
        self.assertEqual(titles, ["На оплату", "На товар", "На сайт"])
        self.assertIn("ambiguous_target", resolution.reason_codes)

    def test_single_plausible_target_needs_no_question(self):
        """Без інвойсу і без товару лишається лише магазин — питати нема про що."""
        resolution = intent.resolve(self.request, deal=None)

        self.assertEqual(resolution.kind, intent.KIND_SITE)
        self.assertTrue(resolution.url)
        self.assertIn("single_plausible_target", resolution.reason_codes)

    def test_payment_is_not_offered_when_no_invoice_ever_existed(self):
        """Плаузібільність виводиться зі стану: неіснуючої оплати серед варіантів немає."""
        resolution = intent.resolve(
            self.request, deal=None, product_url="https://twocomms.shop/product/tee/"
        )

        self.assertEqual(resolution.kind, intent.KIND_ASK)
        titles = [reply.title for reply in resolution.card.quick_replies]
        self.assertNotIn("На оплату", titles)


class NoBareUrlTests(TestCase):
    """Жодне рішення з URL не існує без карточки — інакше повернеться голий лінк."""

    def test_every_resolution_carrying_a_url_carries_a_card(self):
        client_row = IgClient.get_or_create_for_sender("link-intent-3")
        live = IgDeal.objects.create(
            client=client_row,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("500.00"),
            invoice_id="inv-live",
            invoice_url="https://pay.mbnk.biz/inv-live",
            invoice_expires_at=timezone.now() + timedelta(minutes=20),
        )
        cases = (
            intent.resolve(intent.classify_request("дай посилання на оплату"), deal=live),
            intent.resolve(intent.classify_request("посилання на сайт"), deal=None),
            intent.resolve(
                intent.classify_request("дай посилання на цей товар"),
                deal=None,
                product_url="https://twocomms.shop/product/tee/",
            ),
            intent.resolve(intent.classify_request("дай посилання"), deal=None),
        )
        for resolution in cases:
            with self.subTest(kind=resolution.kind):
                if resolution.url:
                    self.assertIsNotNone(
                        resolution.card,
                        f"{resolution.kind} віддає URL без карточки",
                    )

    def test_language_selection_is_honoured(self):
        for lang, expected in (
            ("ru", "Вот наш магазин."),
            ("en", "Here is our shop."),
            ("uk", "Ось наш магазин."),
        ):
            with self.subTest(lang=lang):
                resolution = intent.resolve(
                    intent.classify_request("посилання на сайт"), deal=None, lang=lang
                )
                self.assertEqual(resolution.card.text, expected)
