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
            c, pay_type="prepay", product_id=None, payment_amount=Decimal("350.00")
        )
        self.assertTrue(res["ok"])
        deal = IgDeal.objects.filter(client=c).first()
        self.assertIsNotNone(deal)
        self.assertEqual(deal.items.count(), 1)
        self.assertEqual(deal.items.first().product_id, p.id)
        self.assertEqual(deal.pay_type, IgDeal.PayType.PREPAYMENT)
        self.assertEqual(deal.requested_payment_amount, Decimal("350.00"))

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
    @patch("management.services.bot_orders.create_deal_and_link")
    def test_success_appends_real_url_and_strips_fake(self, mock_link, _mock_notify):
        real = "https://pay.mbnk.biz/REALOK"
        mock_link.return_value = {"ok": True, "invoice_url": real, "invoice_id": "z"}
        reply = "Супер! Ось посилання на оплату: https://pay.mbnk.biz/FAKE000"
        out = bot.finalize_paylink(reply, {"paylink": "full", "product": 1}, self.c, "fz1")
        self.assertIn(real, out)
        self.assertNotIn("FAKE000", out)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_deal_and_link")
    def test_failure_removes_dangling_promise_and_escalates(self, mock_link, mock_notify):
        mock_link.return_value = {"ok": False, "error": "no_product"}
        reply = "Дякую! Зараз сформую посилання на оплату і скину сюди 🙌"
        out = bot.finalize_paylink(reply, {"paylink": "prepay", "product": 1}, self.c, "fz1")
        self.assertNotIn("посилання на оплат", out.lower())
        mock_notify.assert_called_once()
        self.c.refresh_from_db()
        self.assertEqual(self.c.stage, IgClient.Stage.LEAD_TO_MANAGER)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_deal_and_link")
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
        self.assertEqual(mock_link.call_args.kwargs["payment_amount"], Decimal("350.00"))

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_deal_and_link")
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

    @patch("management.services.bot_orders.create_deal_and_link")
    def test_no_paylink_returns_unchanged(self, mock_link):
        reply = "Привіт! Що бажаєте обрати? 😊"
        out = bot.finalize_paylink(reply, {}, self.c, "fz1")
        self.assertEqual(out, reply)
        mock_link.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_deal_and_link")
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
        self.assertEqual(mock_link.call_args.kwargs["product_id"], product.pk)
        self.assertEqual(mock_link.call_args.kwargs["negotiated_price"], Decimal("790.00"))

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_deal_and_link")
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
            mock_link.call_args.kwargs["items"],
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
    @patch("management.services.bot_orders.create_deal_and_link")
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
