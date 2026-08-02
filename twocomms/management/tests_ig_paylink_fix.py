"""Фікс продакшен-бага: бот обіцяв посилання на оплату, але не надсилав.

Причина: модель не передавала [PRODUCT:id] (каталог не давав id), а без нього
create_deal_and_link тихо повертав no_items. Фікс: серверне розв'язання товару
з контексту + тригер по фразі-обіцянці, не лише по тегу.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from management.models import (
    IgCheckoutAccessToken,
    IgCheckoutProposal,
    IgClient,
    IgDeal,
    InstagramBotMessage,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
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

    @patch("management.services.bot_orders.gemini_generate_text")
    def test_from_recent_bot_message(self, mock_gen):
        InstagramBotMessage.objects.create(
            sender_id="rp1", client=self.c, role="model",
            text="Оформлюємо «Череп з дупою» за 788 грн?",
        )
        mock_gen.return_value = {"parsed": '{"product_id": %d, "confidence": 0.9}' % self.p.id}
        got = bot_orders.resolve_product_for_payment(self.c, None)
        self.assertIsNotNone(got)
        self.assertEqual(got.id, self.p.id)

    @patch("management.services.bot_orders.gemini_generate_text")
    def test_low_confidence_returns_none(self, mock_gen):
        InstagramBotMessage.objects.create(
            sender_id="rp1", client=self.c, role="model", text="Можливо щось підберемо?",
        )
        mock_gen.return_value = {"parsed": '{"product_id": %d, "confidence": 0.3}' % self.p.id}
        self.assertIsNone(bot_orders.resolve_product_for_payment(self.c, None))

    def test_none_when_nothing(self):
        self.assertIsNone(bot_orders.resolve_product_for_payment(self.c, None))

    def test_switching_product_clears_previous_checkout_configuration(self):
        previous = self.p
        replacement = _pub_product("Худі для нового вибору", "new-pinned-product")
        self.c.current_product = previous
        self.c.current_size = "S"
        self.c.current_color = "black"
        self.c.current_qty = 3
        self.c.sales_context = {
            "assisted_checkout_selection": {
                "product_id": previous.pk,
                "fit_option_code": "classic",
                "color_variant_id": 12,
            },
            "keep_me": True,
        }
        self.c.save()

        self.assertTrue(bot_orders.pin_product(self.c, replacement.pk))

        self.c.refresh_from_db()
        self.assertEqual(self.c.current_product_id, replacement.pk)
        self.assertEqual(self.c.current_size, "")
        self.assertEqual(self.c.current_color, "")
        self.assertEqual(self.c.current_qty, 1)
        self.assertNotIn("assisted_checkout_selection", self.c.sales_context)
        self.assertTrue(self.c.sales_context["keep_me"])


class WantsPaylinkTests(SimpleTestCase):
    def test_tag(self):
        w, pt = bot._wants_paylink("ок", {"paylink": "prepay"})
        self.assertTrue(w)
        self.assertEqual(pt, "prepay")

    def test_phrase_prepay(self):
        w, pt = bot._wants_paylink("Зараз сформую посилання на передоплату 350 грн", {})
        self.assertTrue(w)
        self.assertEqual(pt, "prepay")

    def test_phrase_full(self):
        w, pt = bot._wants_paylink("Ось посилання на оплату:", {})
        self.assertTrue(w)
        self.assertEqual(pt, "full")

    def test_no_phrase(self):
        w, pt = bot._wants_paylink("Привіт, що бажаєте обрати?", {})
        self.assertFalse(w)

    def test_personal_offer_promise_is_not_allowed_to_drop_the_url(self):
        w, pt = bot._wants_paylink(
            "Ось ваше персональне посилання для оформлення та оплати замовлення: 👇",
            {},
        )
        self.assertTrue(w)
        self.assertEqual(pt, "full")

    def test_explicit_customer_link_request_triggers_checkout_without_model_tag(self):
        w, pt = bot._wants_paylink(
            "Чудово, зараз усе підготую.",
            {},
            trigger_text="Дай посилання",
        )
        self.assertTrue(w)
        self.assertEqual(pt, "full")

    def test_customer_refusal_does_not_trigger_checkout(self):
        w, _pt = bot._wants_paylink(
            "Хорошо, учту.",
            {},
            trigger_text="Ссылка на оплату не нужна",
        )

        self.assertFalse(w)

    def test_positive_send_promise_is_not_mistaken_for_refusal(self):
        w, pt = bot._wants_paylink("Надсилаю посилання на оплату.", {})

        self.assertTrue(w)
        self.assertEqual(pt, "full")


class CreateDealResolvesProductTests(TestCase):
    @patch("management.services.bot_orders.resolve_product_for_payment")
    @patch("management.services.bot_orders.create_payment_link")
    def test_builds_deal_from_context_product(self, mock_link, mock_resolve):
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/z", "invoice_id": "z"}
        p = _pub_product("Футболка «Череп з дупою»", "skull-cd")
        mock_resolve.return_value = p
        c = IgClient.get_or_create_for_sender("cd1")
        InstagramBotMessage.objects.create(
            sender_id=c.igsid, client=c, role="manager",
            text="Передоплата за це замовлення 350 грн",
        )
        InstagramBotMessage.objects.create(
            sender_id=c.igsid, client=c, role="user", text="Так, сплачу 350 грн",
        )
        res = bot_orders.create_deal_and_link(
            c, pay_type="prepay", product_id=None, size="M", payment_amount=Decimal("350.00")
        )
        self.assertTrue(res["ok"])
        deal = IgDeal.objects.filter(client=c).first()
        self.assertIsNotNone(deal)
        self.assertEqual(deal.items.count(), 1)
        self.assertEqual(deal.items.first().product_id, p.id)
        self.assertEqual(deal.pay_type, IgDeal.PayType.PREPAYMENT)
        self.assertEqual(deal.requested_payment_amount, Decimal("350.00"))

    @patch("management.services.bot_orders.resolve_product_for_payment")
    @patch("management.services.bot_orders.create_payment_link")
    def test_prepay_uses_catalog_price_when_no_negotiated_price_is_supplied(
        self, mock_link, mock_resolve
    ):
        """A prepayment amount is not itself a negotiated unit price."""
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/z2", "invoice_id": "z2"}
        product = _pub_product("Футболка без знижки", "catalog-prepay")
        mock_resolve.return_value = product
        client = IgClient.get_or_create_for_sender("catalog-prepay-client")
        InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role="manager",
            text="Передоплата за замовлення 350 грн",
        )
        InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role="user",
            text="Так, сплачу 350 грн",
        )

        result = bot_orders.create_deal_and_link(
            client,
            pay_type="prepay",
            product_id=None,
            size="M",
            payment_amount=Decimal("350.00"),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            IgDeal.objects.get(client=client).items.first().unit_price,
            Decimal("788.00"),
        )

    def test_no_product_no_items_returns_error(self):
        c = IgClient.get_or_create_for_sender("cd2")
        res = bot_orders.create_deal_and_link(c, pay_type="full", product_id=None)
        self.assertFalse(res["ok"])


# ===========================================================================
# Task 1 — Guard «обіцяв лінк → зобов'язаний прислати, або не обіцяти».
# Найважливіший фікс: якщо бот пообіцяв посилання, але воно НЕ сформувалось,
# клієнт НЕ повинен бачити висяче обіцяння без лінку (симптом «скинув, але не
# скинув і чекає оплату»). А якщо лінк сформовано — реальний URL присутній,
# вигаданий моделлю прибраний.
# ===========================================================================
class StripInventedPayUrlsTests(SimpleTestCase):
    def test_removes_fake_monobank_url_keeps_real(self):
        real = "https://pay.mbnk.biz/REAL123"
        text = f"Ось оплата https://pay.mbnk.biz/FAKE999 і ще {real}"
        out = bot._strip_invented_pay_urls(text, keep_url=real)
        self.assertNotIn("FAKE999", out)
        self.assertIn(real, out)

    def test_keeps_product_url(self):
        text = "Дивись тут https://twocomms.shop/product/skull/"
        out = bot._strip_invented_pay_urls(text, keep_url="")
        self.assertEqual(out, text)

    def test_removes_all_pay_urls_when_no_keep(self):
        text = "Тримай https://send.monobank.ua/abc оплату"
        out = bot._strip_invented_pay_urls(text, keep_url="")
        self.assertNotIn("monobank.ua/abc", out)


class RewriteFailedPaylinkTests(SimpleTestCase):
    def test_drops_promise_sentence_keeps_rest(self):
        reply = "Гарний вибір! Зараз сформую посилання на оплату."
        out = bot._rewrite_failed_paylink(reply)
        self.assertNotIn("посилання на оплат", out.lower())
        self.assertIn("Гарний вибір", out)

    def test_only_promise_uses_fallback(self):
        reply = "Ось пряме посилання на передоплату 🙌"
        out = bot._rewrite_failed_paylink(reply)
        self.assertEqual(out, bot.PAYLINK_FALLBACK_TEXT)

    def test_strips_invented_url(self):
        reply = "Тримай посилання на оплату: https://pay.mbnk.biz/FAKE"
        out = bot._rewrite_failed_paylink(reply)
        self.assertNotIn("FAKE", out)


class FinalizePaylinkTests(TestCase):
    def setUp(self):
        self.c = IgClient.get_or_create_for_sender("fz1")
        # Simulate the classifier's persisted purchase candidate. A generated
        # paylink phrase alone must not pass the production gate.
        self.c.intent = IgClient.Intent.PAYMENT
        self.c.stage = IgClient.Stage.CHECKOUT
        self.c.save(update_fields=["intent", "stage", "updated_at"])

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_success_appends_real_url_and_strips_fake(self, mock_link, _mock_notify):
        real = "https://pay.mbnk.biz/REALOK"
        mock_link.return_value = {"ok": True, "invoice_url": real, "invoice_id": "z"}
        reply = "Супер! Ось посилання на оплату: https://pay.mbnk.biz/FAKE000"
        out = bot.finalize_paylink(reply, {"paylink": "full", "product": 1}, self.c, "fz1")
        self.assertIn(real, out)
        self.assertNotIn("FAKE000", out)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_first_party_offer_has_clear_checkout_copy(self, mock_link, _mock_notify):
        offer_url = "https://twocomms.shop/offer/a/opaque-token/"
        mock_link.return_value = {
            "ok": True,
            "invoice_url": offer_url,
            "proposal_url": offer_url,
        }

        out = bot.finalize_paylink(
            "Готово, зараз надішлю посилання на оплату.",
            {"paylink": "full", "product": 1},
            self.c,
            self.c.igsid,
        )

        self.assertIn(offer_url, out)
        self.assertIn("Перевірте товари", out)
        self.assertIn("25 хвилин", out)
        self.assertIn("email", out.lower())
        self.assertNotIn("monobank", out.lower())
        self.assertNotIn("посилання на оплату", out.lower())

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_deal_and_link")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_finalize_paylink_never_uses_legacy_direct_invoice_factory(
        self, proposal_link, legacy_link, _mock_notify
    ):
        offer_url = "https://twocomms.shop/offer/a/proposal-token/"
        proposal_link.return_value = {
            "ok": True,
            "invoice_url": offer_url,
            "proposal_url": offer_url,
        }

        out = bot.finalize_paylink(
            "Готово, зараз надішлю посилання.",
            {"paylink": "full", "product": 1},
            self.c,
            self.c.igsid,
        )

        self.assertIn(offer_url, out)
        proposal_link.assert_called_once()
        legacy_link.assert_not_called()

    def test_delivery_review_resolves_first_party_offer_to_its_deal(self):
        deal = IgDeal.objects.create(
            client=self.c,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("950.00"),
            requested_payment_amount=Decimal("950.00"),
        )
        episode = ensure_episode_for_deal(deal)
        proposal = IgCheckoutProposal.objects.create_current(
            deal=deal,
            commercial_episode=episode,
            catalog_total=Decimal("950.00"),
            quoted_total=Decimal("950.00"),
            requested_payment_amount=Decimal("950.00"),
            items_digest="b" * 64,
        )
        raw, _token = IgCheckoutAccessToken.issue(proposal=proposal)

        resolved = bot._invoice_deal_for_reply(
            self.c,
            f"Перевірте пропозицію: https://twocomms.shop/offer/a/{raw}/",
        )

        self.assertEqual(resolved.pk, deal.pk)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_missing_fit_returns_a_question_without_manager_handoff(self, mock_link, mock_notify):
        mock_link.return_value = {"ok": False, "error": "missing_fit_option"}

        out = bot.finalize_paylink(
            "Оформлюю замовлення.",
            {"paylink": "full", "product": 1},
            self.c,
            self.c.igsid,
        )

        self.assertIn("фасон", out.lower())
        self.assertIn("класич", out.lower())
        self.assertIn("оверсайз", out.lower())
        mock_notify.assert_not_called()
        self.c.refresh_from_db()
        self.assertEqual(self.c.stage, IgClient.Stage.CHECKOUT)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_link_request_without_control_uses_persisted_product_size_and_quantity(
        self, mock_link, mock_notify
    ):
        product = _pub_product("Худі Reality Bends", "reality-bends-persisted")
        self.c.current_product = product
        self.c.current_size = "S"
        self.c.current_qty = 2
        self.c.language = "ru"
        self.c.stage = IgClient.Stage.PAYMENT_PENDING
        self.c.save(update_fields=[
            "current_product", "current_size", "current_qty", "language", "stage", "updated_at",
        ])
        offer_url = "https://twocomms.shop/offer/a/real-production-shape/"
        mock_link.return_value = {"ok": True, "invoice_url": offer_url}

        out = bot.finalize_paylink(
            "Ось ваше персональне посилання для оформлення:",
            {},
            self.c,
            self.c.igsid,
            trigger_text="Дай посилання",
        )

        self.assertIn(offer_url, out)
        self.assertEqual(
            mock_link.call_args.kwargs["item_specs"],
            [{
                "product_id": product.pk,
                "qty": 2,
                "size": "S",
                "fit_option_code": "",
                "color_variant_id": None,
            }],
        )
        mock_notify.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    def test_real_missing_fit_returns_question_instead_of_linkless_promise(self, mock_notify):
        from storefront.models import ProductFitOption

        product = _pub_product("Худі з двома фасонами", "missing-fit-real-validator")
        ProductFitOption.objects.create(
            product=product, code="classic", label="Класичний", is_active=True,
        )
        ProductFitOption.objects.create(
            product=product, code="oversize", label="Оверсайз", is_active=True,
        )
        self.c.current_product = product
        self.c.current_size = "S"
        self.c.language = "ru"
        self.c.stage = IgClient.Stage.PAYMENT_PENDING
        self.c.save(update_fields=[
            "current_product", "current_size", "language", "stage", "updated_at",
        ])

        out = bot.finalize_paylink(
            "Ось ваше персональне посилання для оформлення та оплати:",
            {},
            self.c,
            self.c.igsid,
            trigger_text="Дай посилання",
        )

        self.assertIn("фасон", out.lower())
        self.assertIn("класс", out.lower())
        self.assertIn("оверсайз", out.lower())
        self.assertNotIn("посилання", out.lower())
        self.assertFalse(IgCheckoutProposal.objects.filter(client=self.c).exists())
        mock_notify.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_explicit_fit_answer_continues_pending_checkout_without_model_tags(
        self, mock_link, mock_notify
    ):
        from storefront.models import ProductFitOption

        product = _pub_product("Худі для продовження", "fit-continuation")
        ProductFitOption.objects.create(
            product=product, code="classic", label="Класичний", is_active=True,
        )
        ProductFitOption.objects.create(
            product=product, code="oversize", label="Оверсайз", is_active=True,
        )
        self.c.current_product = product
        self.c.current_size = "S"
        self.c.language = "uk"
        self.c.stage = IgClient.Stage.PAYMENT_PENDING
        self.c.save(update_fields=[
            "current_product", "current_size", "language", "stage", "updated_at",
        ])
        offer_url = "https://twocomms.shop/offer/a/fit-continuation-token/"
        mock_link.return_value = {"ok": True, "invoice_url": offer_url}

        out = bot.finalize_paylink(
            "Дякую, зафіксувала вибір.",
            {},
            self.c,
            self.c.igsid,
            trigger_text="Класичний",
        )

        self.assertIn(offer_url, out)
        self.assertEqual(
            mock_link.call_args.kwargs["item_specs"][0]["fit_option_code"],
            "classic",
        )
        mock_notify.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_color_answer_continues_checkout_with_persisted_fit(self, mock_link, mock_notify):
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import ProductFitOption

        product = _pub_product("Худі з вибором кольору", "color-continuation")
        ProductFitOption.objects.create(
            product=product, code="classic", label="Класичний", is_active=True,
        )
        pink = Color.objects.create(name="Рожевий", primary_hex="#ff88aa")
        black = Color.objects.create(name="Чорний", primary_hex="#111111")
        pink_variant = ProductColorVariant.objects.create(product=product, color=pink, stock=3)
        ProductColorVariant.objects.create(product=product, color=black, stock=3)
        self.c.current_product = product
        self.c.current_size = "S"
        self.c.current_color = "Рожевий"
        self.c.language = "uk"
        self.c.stage = IgClient.Stage.PAYMENT_PENDING
        self.c.sales_context = {
            "assisted_checkout_selection": {
                "product_id": product.pk,
                "fit_option_code": "classic",
            }
        }
        self.c.save(update_fields=[
            "current_product", "current_size", "current_color", "language", "stage",
            "sales_context", "updated_at",
        ])
        offer_url = "https://twocomms.shop/offer/a/color-continuation-token/"
        mock_link.return_value = {"ok": True, "invoice_url": offer_url}

        out = bot.finalize_paylink(
            "Чудово, колір зафіксовано.",
            {},
            self.c,
            self.c.igsid,
            trigger_text="Рожевий",
        )

        self.assertIn(offer_url, out)
        self.assertEqual(
            mock_link.call_args.kwargs["item_specs"][0]["color_variant_id"],
            pink_variant.pk,
        )
        self.assertEqual(
            mock_link.call_args.kwargs["item_specs"][0]["fit_option_code"],
            "classic",
        )
        mock_notify.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_russian_color_answer_matches_ukrainian_catalog_variant(
        self, mock_link, mock_notify
    ):
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import ProductFitOption

        product = _pub_product("Худі з локалізованим кольором", "localized-color-continuation")
        ProductFitOption.objects.create(
            product=product, code="classic", label="Класичний", is_active=True,
        )
        pink = Color.objects.create(name="Рожевий", primary_hex="#F7A1B9")
        black = Color.objects.create(name="Чорний", primary_hex="#111111")
        pink_variant = ProductColorVariant.objects.create(
            product=product, color=pink, stock=3, slug="pink",
        )
        ProductColorVariant.objects.create(
            product=product, color=black, stock=3, slug="black",
        )
        self.c.current_product = product
        self.c.current_size = "S"
        self.c.current_color = ""
        self.c.language = "ru"
        self.c.stage = IgClient.Stage.PAYMENT_PENDING
        self.c.sales_context = {
            "assisted_checkout_selection": {
                "product_id": product.pk,
                "fit_option_code": "classic",
            }
        }
        self.c.save(update_fields=[
            "current_product", "current_size", "current_color", "language",
            "stage", "sales_context", "updated_at",
        ])
        offer_url = "https://twocomms.shop/offer/a/localized-color-token/"
        mock_link.return_value = {"ok": True, "invoice_url": offer_url}

        out = bot.finalize_paylink(
            "Отлично, цвет записала.",
            {},
            self.c,
            self.c.igsid,
            trigger_text="Розовый",
        )

        self.assertIn(offer_url, out)
        self.assertEqual(
            mock_link.call_args.kwargs["item_specs"][0]["color_variant_id"],
            pink_variant.pk,
        )
        self.c.refresh_from_db()
        self.assertEqual(
            self.c.sales_context["assisted_checkout_selection"]["color_variant_id"],
            pink_variant.pk,
        )
        mock_notify.assert_not_called()

    def test_color_alias_does_not_match_inside_unrelated_word(self):
        from productcolors.models import Color, ProductColorVariant

        product = _pub_product("Худі з сірим кольором", "gray-word-boundary")
        gray = Color.objects.create(name="Сірий", primary_hex="#777777")
        ProductColorVariant.objects.create(
            product=product, color=gray, stock=3, slug="gray",
        )

        resolved = bot._current_color_variant_id(
            self.c,
            product.pk,
            1,
            trigger_text="У меня есть сертификат",
        )

        self.assertIsNone(resolved)

    def test_negated_color_is_not_selected(self):
        from productcolors.models import Color, ProductColorVariant

        product = _pub_product("Худі без рожевого", "negated-pink")
        pink = Color.objects.create(name="Рожевий", primary_hex="#F18CAD")
        ProductColorVariant.objects.create(
            product=product, color=pink, stock=3, slug="pink",
        )

        resolved = bot._current_color_variant_id(
            self.c,
            product.pk,
            1,
            trigger_text="Только не розовый",
        )

        self.assertIsNone(resolved)

    def test_client_wide_color_is_not_reused_without_current_turn_confirmation(self):
        from productcolors.models import Color, ProductColorVariant

        product = _pub_product("Нове худі", "stale-color-new-product")
        black = Color.objects.create(name="Чорний", primary_hex="#111111")
        ProductColorVariant.objects.create(
            product=product, color=black, stock=3, slug="black",
        )
        self.c.current_color = "black"
        self.c.save(update_fields=["current_color", "updated_at"])

        resolved = bot._current_color_variant_id(
            self.c,
            product.pk,
            1,
            trigger_text="Классический",
        )

        self.assertIsNone(resolved)

    @patch("management.services.instagram_bot.notify_manager")
    def test_unavailable_color_answer_reports_stock_instead_of_dropping_checkout(
        self, mock_notify
    ):
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import ProductFitOption

        product = _pub_product("Худі з відсутнім кольором", "unavailable-color-answer")
        ProductFitOption.objects.create(
            product=product, code="classic", label="Класичний", is_active=True,
        )
        pink = Color.objects.create(name="Рожевий", primary_hex="#F39AB6")
        ProductColorVariant.objects.create(
            product=product, color=pink, stock=0, slug="pink",
        )
        self.c.current_product = product
        self.c.current_size = "S"
        self.c.current_color = ""
        self.c.language = "ru"
        self.c.stage = IgClient.Stage.PAYMENT_PENDING
        self.c.sales_context = {
            "assisted_checkout_selection": {
                "product_id": product.pk,
                "fit_option_code": "classic",
            }
        }
        self.c.save(update_fields=[
            "current_product", "current_size", "current_color", "language",
            "stage", "sales_context", "updated_at",
        ])

        out = bot.finalize_paylink(
            "Отлично, цвет записала.",
            {},
            self.c,
            self.c.igsid,
            trigger_text="Розовый",
        )

        self.assertIn("недоступ", out.lower())
        self.assertFalse(IgCheckoutProposal.objects.filter(client=self.c).exists())
        mock_notify.assert_not_called()

    @patch("management.services.instagram_bot._conversation_payment_amount")
    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_prepayment_type_survives_fit_clarification(
        self, mock_link, mock_notify, mock_payment_amount
    ):
        product = _pub_product("Худі з передоплатою", "prepay-fit-continuation")
        self.c.current_product = product
        self.c.current_size = "S"
        self.c.language = "ru"
        self.c.stage = IgClient.Stage.PAYMENT_PENDING
        self.c.save(update_fields=[
            "current_product", "current_size", "language", "stage", "updated_at",
        ])
        mock_payment_amount.return_value = Decimal("350.00")
        mock_link.side_effect = [
            {"ok": False, "error": "missing_fit_option"},
            {"ok": True, "invoice_url": "https://twocomms.shop/offer/a/prepay-fit/"},
        ]

        first = bot.finalize_paylink(
            "Формирую ссылку на предоплату.",
            {"paylink": "prepay", "product": product.pk},
            self.c,
            self.c.igsid,
        )
        second = bot.finalize_paylink(
            "Спасибо, фасон зафиксирован.",
            {},
            self.c,
            self.c.igsid,
            trigger_text="Классический",
        )

        self.assertIn("фасон", first.lower())
        self.assertIn("/offer/a/prepay-fit/", second)
        self.assertEqual(mock_link.call_args_list[1].kwargs["pay_type"], "prepay")
        self.assertEqual(
            mock_link.call_args_list[1].kwargs["requested_payment_amount"],
            Decimal("350.00"),
        )
        mock_notify.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    def test_insufficient_stock_names_real_published_in_stock_alternative(self, mock_notify):
        from productcolors.models import Color, ProductColorVariant

        requested = _pub_product("Худі без залишку", "oos-requested")
        alternative = _pub_product("Худі Available Alternative", "oos-alternative")
        pink = Color.objects.create(name="Рожевий", primary_hex="#ff88aa")
        black = Color.objects.create(name="Чорний", primary_hex="#111111")
        unavailable_variant = ProductColorVariant.objects.create(
            product=requested, color=pink, stock=0,
        )
        ProductColorVariant.objects.create(product=alternative, color=black, stock=4)
        self.c.current_product = requested
        self.c.current_size = "S"
        self.c.language = "ru"
        self.c.stage = IgClient.Stage.PAYMENT_PENDING
        self.c.save(update_fields=[
            "current_product", "current_size", "language", "stage", "updated_at",
        ])

        out = bot.finalize_paylink(
            "Формирую персональное предложение.",
            {
                "paylink": "full",
                "product": requested.pk,
                "qty": "1",
                "size": "S",
                "variant": str(unavailable_variant.pk),
            },
            self.c,
            self.c.igsid,
        )

        self.assertIn("недоступ", out.lower())
        self.assertIn(alternative.title, out)
        self.assertFalse(IgCheckoutProposal.objects.filter(client=self.c).exists())
        mock_notify.assert_not_called()

    def test_alternatives_exclude_variants_incompatible_with_requested_fit(self):
        from fable5.models import VariantFitRule
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import ProductFitOption

        requested = _pub_product("Худі без залишку 2", "oos-requested-fit")
        incompatible = _pub_product("Худі тільки оверсайз", "oos-incompatible-fit")
        ProductFitOption.objects.create(
            product=incompatible,
            code="classic",
            label="Класичний",
            is_active=True,
        )
        black = Color.objects.create(name="Чорний", primary_hex="#151515")
        variant = ProductColorVariant.objects.create(
            product=incompatible, color=black, stock=4, slug="black",
        )
        VariantFitRule.objects.create(
            variant=variant,
            fit_code="classic",
            is_enabled=False,
        )

        labels = bot._checkout_alternative_labels(
            [{
                "product_id": requested.pk,
                "qty": 1,
                "size": "S",
                "fit_option_code": "classic",
            }],
            {"item_index": 0},
        )

        self.assertNotIn(incompatible.title, labels)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_failure_removes_dangling_promise_and_escalates(self, mock_link, mock_notify):
        mock_link.return_value = {"ok": False, "error": "no_product"}
        reply = "Дякую! Зараз сформую посилання на оплату і скину сюди 🙌"
        out = bot.finalize_paylink(reply, {"paylink": "prepay", "product": 1}, self.c, "fz1")
        self.assertNotIn("посилання на оплат", out.lower())
        mock_notify.assert_called_once()
        self.c.refresh_from_db()
        self.assertEqual(self.c.stage, IgClient.Stage.LEAD_TO_MANAGER)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_dynamic_prepayment_is_evidence_bound_and_forwarded(self, mock_link, _notify):
        product = _pub_product("Футболка з передоплатою", "dynamic-prepayment", price=950)
        InstagramBotMessage.objects.create(
            sender_id=self.c.igsid, client=self.c, role="manager",
            text="Для цього замовлення передоплата 350 грн",
        )
        InstagramBotMessage.objects.create(
            sender_id=self.c.igsid, client=self.c, role="user",
            text="Так, погоджуюсь на передоплату 350 грн",
        )
        mock_link.return_value = {
            "ok": True,
            "invoice_url": "https://pay/350",
            "invoice_id": "350",
        }

        out = bot.finalize_paylink(
            "Формую посилання на передоплату",
            {"paylink": "prepay", "payment": "350", "product": product.pk},
            self.c,
            self.c.igsid,
        )

        self.assertIn("https://pay/350", out)
        self.assertEqual(mock_link.call_args.kwargs["requested_payment_amount"], Decimal("350.00"))

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_prepayment_without_evidenced_amount_fails_closed(self, mock_link, mock_notify):
        product = _pub_product("Футболка без суми", "missing-prepayment-amount", price=950)

        out = bot.finalize_paylink(
            "Формую посилання на передоплату",
            {"paylink": "prepay", "product": product.pk},
            self.c,
            self.c.igsid,
        )

        self.assertNotIn("посилання на передоплату", out.lower())
        mock_link.assert_not_called()
        mock_notify.assert_called_once()

    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_no_paylink_returns_unchanged(self, mock_link):
        reply = "Привіт! Що бажаєте обрати? 😊"
        out = bot.finalize_paylink(reply, {}, self.c, "fz1")
        self.assertEqual(out, reply)
        mock_link.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_explicit_product_validates_price_before_current_product_is_pinned(self, mock_link, _notify):
        product = _pub_product("Футболка зі знижкою", "explicit-price-product", price=950)
        InstagramBotMessage.objects.create(
            sender_id=self.c.igsid, client=self.c, role="manager",
            text="Можу оформити цю футболку за 790 грн",
        )
        InstagramBotMessage.objects.create(
            sender_id=self.c.igsid, client=self.c, role="user",
            text="Так, оформлюйте",
        )
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/790", "invoice_id": "790"}

        out = bot.finalize_paylink(
            "Формую посилання на оплату",
            {"paylink": "full", "product": product.pk, "price": "790"},
            self.c,
            self.c.igsid,
        )

        self.assertIn("https://pay/790", out)
        self.assertEqual(
            mock_link.call_args.kwargs["item_specs"],
            [{
                "product_id": product.pk,
                "qty": 1,
                "size": "",
                "fit_option_code": "",
                "color_variant_id": None,
            }],
        )
        self.assertEqual(mock_link.call_args.kwargs["negotiated_total"], Decimal("790.00"))

    def test_real_proposal_keeps_explicit_order_total_for_multiple_units(self):
        product = _pub_product(
            "Футболка з погодженою сумою",
            "proposal-explicit-order-total",
            price=950,
        )
        offer = InstagramBotMessage.objects.create(
            sender_id=self.c.igsid,
            client=self.c,
            role="manager",
            text="За дві футболки сума разом 1500 грн",
        )
        accepted = InstagramBotMessage.objects.create(
            sender_id=self.c.igsid,
            client=self.c,
            role="user",
            text="Так, оформлюйте дві",
        )
        decision = bot_orders._conversation_price_decision(
            self.c, product=product, qty=2,
        )
        self.assertEqual(decision["status"], "accepted", decision)
        self.assertEqual(decision["kind"], "order_total", decision)
        self.assertEqual(decision["price"], Decimal("1500.00"), decision)
        self.assertEqual(
            {decision["source_message_id"], decision["acceptance_message_id"]},
            {offer.pk, accepted.pk},
        )

        out = bot.finalize_paylink(
            "Формую персональну пропозицію",
            {
                "paylink": "full",
                "product": product.pk,
                "qty": "2",
                "size": "M",
                "price": "1500",
            },
            self.c,
            self.c.igsid,
        )

        self.assertIn("/offer/a/", out)
        proposal = IgCheckoutProposal.objects.get(client=self.c)
        self.assertEqual(proposal.catalog_total, Decimal("1900.00"))
        self.assertEqual(proposal.quoted_total, Decimal("1500.00"))
        self.assertEqual(proposal.items.get().quantity, 2)
        self.assertEqual(
            set(proposal.items.get().evidence_message_ids),
            {offer.pk, accepted.pk},
        )

    def test_real_proposal_multiplies_explicit_unit_price_for_multiple_units(self):
        product = _pub_product(
            "Футболка з ціною за штуку",
            "proposal-explicit-unit-price",
            price=950,
        )
        offer = InstagramBotMessage.objects.create(
            sender_id=self.c.igsid,
            client=self.c,
            role="manager",
            text="Ціна кожної футболки 790 грн за штуку",
        )
        accepted = InstagramBotMessage.objects.create(
            sender_id=self.c.igsid,
            client=self.c,
            role="user",
            text="Так, беру дві",
        )
        decision = bot_orders._conversation_price_decision(
            self.c, product=product, qty=2,
        )
        self.assertEqual(decision["status"], "accepted", decision)
        self.assertEqual(decision["kind"], "unit_price", decision)
        self.assertEqual(decision["price"], Decimal("790.00"), decision)
        self.assertEqual(
            {decision["source_message_id"], decision["acceptance_message_id"]},
            {offer.pk, accepted.pk},
        )

        out = bot.finalize_paylink(
            "Формую персональну пропозицію",
            {
                "paylink": "full",
                "product": product.pk,
                "qty": "2",
                "size": "M",
                "price": "790",
            },
            self.c,
            self.c.igsid,
        )

        self.assertIn("/offer/a/", out)
        proposal = IgCheckoutProposal.objects.get(client=self.c)
        self.assertEqual(proposal.quoted_total, Decimal("1580.00"))
        self.assertEqual(
            set(proposal.items.get().evidence_message_ids),
            {offer.pk, accepted.pk},
        )

    @patch("management.services.instagram_bot.notify_manager")
    def test_multiple_units_with_ambiguous_price_fail_closed(self, notify_manager):
        product = _pub_product(
            "Футболка з неоднозначною ціною",
            "proposal-ambiguous-multi-unit-price",
            price=950,
        )
        InstagramBotMessage.objects.create(
            sender_id=self.c.igsid,
            client=self.c,
            role="manager",
            text="Ціна футболки 790 грн",
        )
        InstagramBotMessage.objects.create(
            sender_id=self.c.igsid,
            client=self.c,
            role="user",
            text="Так, беру дві",
        )

        out = bot.finalize_paylink(
            "Формую персональну пропозицію",
            {
                "paylink": "full",
                "product": product.pk,
                "qty": "2",
                "size": "M",
                "price": "790",
            },
            self.c,
            self.c.igsid,
        )

        self.assertEqual(out, bot.PAYLINK_FALLBACK_TEXT)
        self.assertFalse(IgCheckoutProposal.objects.filter(client=self.c).exists())
        notify_manager.assert_called_once()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_forwards_separate_item_quantity_size_and_fit_records(self, mock_link, _notify):
        product = _pub_product("Футболка Харків", "paylink-multi-fit", price=950)
        mock_link.return_value = {
            "ok": True,
            "invoice_url": "https://pay/items",
            "invoice_id": "items",
        }

        bot.finalize_paylink(
            "Оформлюю замовлення",
            {
                "paylink": "full",
                "items": [
                    f"{product.pk}|1|XS|oversize",
                    f"{product.pk}|2|S|classic",
                ],
            },
            self.c,
            self.c.igsid,
        )

        self.assertEqual(
            mock_link.call_args.kwargs["item_specs"],
            [
                {
                    "product_id": product.pk,
                    "qty": 1,
                    "size": "XS",
                    "fit_option_code": "oversize",
                    "color_variant_id": None,
                },
                {
                    "product_id": product.pk,
                    "qty": 2,
                    "size": "S",
                    "fit_option_code": "classic",
                    "color_variant_id": None,
                },
            ],
        )

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_checkout_proposal_link")
    def test_malformed_explicit_item_tag_fails_closed(self, mock_link, _notify):
        product = _pub_product("Футболка", "paylink-malformed-item", price=950)

        out = bot.finalize_paylink(
            "Оформлюю замовлення",
            {"paylink": "full", "product": product.pk, "items": ["broken-item"]},
            self.c,
            self.c.igsid,
        )

        self.assertEqual(out, bot.PAYLINK_FALLBACK_TEXT)
        mock_link.assert_not_called()

    def test_mixed_valid_and_malformed_item_tags_fail_closed(self):
        self.assertEqual(
            bot._control_item_specs({"items": ["12|1|XS|classic", "not-a-valid-item"]}),
            [],
        )

    def test_conflicting_singleton_control_tags_are_rejected(self):
        _text, control = bot._extract_control("Готово [PAYLINK:full] [PAYLINK:prepay]")
        self.assertTrue(control.get("_invalid"))

    def test_explicit_invalid_product_does_not_fallback_to_current_product(self):
        current = _pub_product("Поточний товар", "current-explicit-stale")
        self.c.current_product = current
        self.c.save(update_fields=["current_product", "updated_at"])

        self.assertIsNone(bot_orders.resolve_product_for_payment(self.c, product_id=999999))


class PaymentItemControlTests(SimpleTestCase):
    def test_extract_control_preserves_repeated_item_tags(self):
        clean, control = bot._extract_control(
            "Оформлюю [PAYLINK:full] [PRODUCT:12] "
            "[ITEM:12|1|XS|oversize] [ITEM:12|2|S|classic]"
        )

        self.assertEqual(clean, "Оформлюю")
        self.assertEqual(
            control["items"],
            ["12|1|xs|oversize", "12|2|s|classic"],
        )

    def test_explicit_invalid_quantity_fails_closed(self):
        self.assertIsNone(bot._control_positive_int({"qty": "many"}, "qty"))

    def test_product_tag_must_agree_with_every_item(self):
        client = type("Client", (), {
            "pk": None,
            "intent": "payment",
            "stage": "checkout",
            "current_product_id": None,
        })()
        self.assertFalse(bot.payment_link_allowed(
            client,
            {"product": "12", "items": ["13|1|S|classic"]},
            "Беру, оформлюйте",
        ))


# ===========================================================================
# Task 3 — Інжект протоколу [PRODUCT:id] у gemini_generate (migration-free).
# Модель має ставити [PAYLINK:x] + [PRODUCT:<id>] і НЕ вигадувати URL. Це дає
# явний надійний сигнал товару (швидше за модельний резолвер).
# ===========================================================================
class PaymentProtocolInjectionTests(TestCase):
    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_injects_product_protocol_into_system_instruction(self, mock_gen):
        from management.models import InstagramBotSettings

        mock_gen.return_value = {"parsed": "ок", "model": "x", "meta": {"key": "k"}}
        s = InstagramBotSettings.load()
        bot.gemini_generate(s, [{"role": "user", "text": "скільки коштує?"}])
        self.assertTrue(mock_gen.called)
        payload = mock_gen.call_args.args[0]
        sys_text = payload["system_instruction"]["parts"][0]["text"]
        # [PRODUCT: немає у DEFAULT_BOT_SYSTEM_PROMPT — отже додав саме інжект.
        self.assertIn("[PRODUCT:", sys_text)
        self.assertIn("[PAYLINK:", sys_text)
        self.assertIn("[ITEM:", sys_text)
        self.assertIn("кільк", sys_text.lower())
        self.assertIn("розмір", sys_text.lower())
        self.assertIn("крій", sys_text.lower())
        self.assertIn("НЕ вигадуй", sys_text)
        self.assertIn("персональну пропозицію", sys_text.lower())
        self.assertIn("25 хвилин", sys_text.lower())
        self.assertIn("не збирай email", sys_text.lower())


# ===========================================================================
# Task 8 — антигалюцинації: бот не відмовляє в існуванні товару без перевірки.
# ===========================================================================
class AntiHallucinationInjectionTests(TestCase):
    @patch("management.services.call_ai_analysis.gemini_generate_text")
    def test_injects_no_denial_rule_and_temperature(self, mock_gen):
        from management.models import InstagramBotSettings

        mock_gen.return_value = {"parsed": "ок", "model": "x", "meta": {"key": "k"}}
        s = InstagramBotSettings.load()
        bot.gemini_generate(s, [{"role": "user", "text": "є футболка про Харків?"}])
        payload = mock_gen.call_args.args[0]
        sys_text = payload["system_instruction"]["parts"][0]["text"]
        self.assertIn("не стверджуй, що товару немає", sys_text.lower())
        # Температуру знизили для меншої «фантазії».
        self.assertLessEqual(payload["generationConfig"]["temperature"], 0.5)
