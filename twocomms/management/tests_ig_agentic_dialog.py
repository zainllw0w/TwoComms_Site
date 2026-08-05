# -*- coding: utf-8 -*-
"""Діалог веде модель, а не скрипт: перевірка на живому прод-інциденті 02.08.2026.

Кожен тест тут відтворює конкретний хід із двох реальних переписок, які й стали
причиною цієї роботи.

Клієнт #2 (`lesiakolt`), 11:03–11:04:
    — Дай нове посилання, будь ласка
    — Подскажите, пожалуйста, какой фасон выбираете: классический или оверсайз?
    — Чому ти відповідаєш російською?
    — Подскажите, пожалуйста, какой фасон выбираете: классический или оверсайз?

Клієнт #5 (`zainllw0w`), 06:24–06:32:
    — Давай ее хочу купить, дай ссылку
    — Выбранный вариант сейчас недоступен в нужном количестве…
    — Покажи на оверсайз размерную сетку
    — Выбранный вариант сейчас недоступен в нужном количестве…
    — https://twocomms.shop/product/classic-tshirt/  Вот я за этот вариант
    — Выбранный вариант сейчас недоступен в нужном количестве…
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, InstagramBotMessage
from fable5.models import GarmentFlow, GarmentFlowCategory
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption, ProductStatus


def _client(igsid="agentic-dialog"):
    return IgClient.get_or_create_for_sender(igsid)


class LanguageTruthTests(TestCase):
    """Мова: детектор більше не вигадує «російську» за замовчуванням."""

    def test_neutral_ukrainian_message_is_not_declared_russian(self):
        from management.services.bot_sales_classifier import detect_language

        # Дослівне повідомлення клієнта #2, після якого бот перейшов на російську.
        self.assertEqual(detect_language("Дай нове посилання, будь ласка"), "uk")

    def test_undecidable_message_returns_empty_instead_of_guessing(self):
        from management.services.bot_sales_classifier import detect_language

        for value in ("ок", "+", "ага"):
            with self.subTest(value=value):
                self.assertEqual(detect_language(value), "")

    def test_russian_specific_letters_are_still_recognized(self):
        from management.services.bot_sales_classifier import detect_language

        self.assertEqual(detect_language("Ещё вопрос про размеры"), "ru")

    def test_undecidable_message_keeps_the_stored_conversation_language(self):
        from management.services.bot_sales_classifier import _sticky_language

        client = _client("sticky-keeps")
        client.language = "uk"
        self.assertEqual(_sticky_language(client, ""), "uk")

    def test_direct_complaint_about_language_switches_immediately(self):
        from management.services.bot_sales_classifier import detect_language_request

        # Клієнт #2: скарга на російську означає прохання перейти на українську.
        self.assertEqual(
            detect_language_request("Чому ти відповідаєш російською?"), "uk"
        )
        self.assertEqual(detect_language_request("пиши українською"), "uk")
        self.assertEqual(detect_language_request("давай по-русски"), "ru")
        self.assertEqual(detect_language_request("can you reply in english?"), "en")

    def test_print_wording_is_not_mistaken_for_a_language_request(self):
        from management.services.bot_sales_classifier import detect_language_request

        self.assertEqual(detect_language_request("хочу футболку з англійським написом"), "")

    def test_explicit_request_survives_a_later_neutral_message(self):
        from management.services.bot_sales_classifier import (
            _record_language_request,
            _sticky_language,
        )

        client = _client("sticky-request")
        client.language = "ru"
        _record_language_request(client, "uk")
        # «ок» саме по собі не є згодою повернутись на попередню мову.
        self.assertEqual(_sticky_language(client, "ru"), "uk")

    def test_language_state_reaches_the_prompt_as_a_fact_not_a_directive(self):
        from management.services import instagram_bot as bot

        client = _client("prompt-language")
        client.language = "ru"
        client.save(update_fields=["language", "updated_at"])
        InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Дай нове посилання, будь ласка",
        )

        lines = "\n".join(bot._language_state_lines(client))

        self.assertIn("РОЗБІЖНІСТЬ", lines)
        self.assertIn("українська", lines)


class CheckoutReadinessNoteTests(TestCase):
    """Модель дізнається про брак даних ДО генерації, а не після."""

    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="agentic-shirts")
        self.product = Product.objects.create(
            title="Класична футболка",
            slug="classic-tshirt",
            category=self.category,
            price=880,
            status=ProductStatus.PUBLISHED,
        )
        ProductFitOption.objects.create(
            product=self.product, code="classic", label="Класичний", is_active=True,
        )
        ProductFitOption.objects.create(
            product=self.product, code="oversize", label="Оверсайз", is_active=True,
        )
        black = Color.objects.create(name="Чорний", primary_hex="#111111")
        self.variant = ProductColorVariant.objects.create(
            product=self.product, color=black, stock=0, slug="black",
        )
        self.client_row = _client("readiness-note")
        self.client_row.current_product = self.product
        self.client_row.save(update_fields=["current_product", "updated_at"])

    def test_generic_option_axis_is_explicitly_missing_until_selected(self):
        from management.services.ig_checkout_readiness import checkout_readiness

        flow = GarmentFlow.objects.create(
            code="tshirt-material-options",
            name="T-shirt options",
            axes=[{
                "code": "material",
                "label": "Матеріал",
                "options": [
                    {"code": "cotton", "label": "Бавовна", "default": True},
                    {"code": "thermo", "label": "Термохром", "price_delta": 360},
                ],
            }],
        )
        GarmentFlowCategory.objects.create(flow=flow, category=self.category)
        self.client_row.sales_context = {
            "assisted_checkout_selection": {
                "product_id": self.product.pk,
                "fit_option_code": "classic",
            }
        }
        self.client_row.save(update_fields=["sales_context", "updated_at"])

        state = checkout_readiness(self.client_row)

        self.assertEqual(state["options"]["missing"], ["material"])
        self.assertFalse(state["can_issue_link"])
        self.assertEqual(
            [choice["code"] for choice in state["options"]["axes"][0]["choices"]],
            ["cotton", "thermo"],
        )

    def test_generic_option_axis_with_no_sellable_choices_blocks_checkout(self):
        from management.services.ig_checkout_readiness import checkout_readiness

        flow = GarmentFlow.objects.create(
            code="tshirt-material-disabled",
            name="Disabled material",
            axes=[{
                "code": "material",
                "label": "Матеріал",
                "options": [],
            }],
        )
        GarmentFlowCategory.objects.create(flow=flow, category=self.category)
        self.client_row.current_size = "M"
        self.client_row.sales_context = {
            "assisted_checkout_selection": {
                "product_id": self.product.pk,
                "fit_option_code": "classic",
            }
        }
        self.client_row.save(update_fields=["current_size", "sales_context", "updated_at"])

        state = checkout_readiness(self.client_row)

        self.assertIn("material", state["options"]["missing"])
        self.assertIn("option:material", state["missing"])
        self.assertFalse(state["can_issue_link"])

    @patch("fable5.services.product_option_context", side_effect=RuntimeError("catalog unavailable"))
    def test_option_context_failure_blocks_checkout_instead_of_using_base_price(self, _context):
        from management.services.ig_checkout_readiness import checkout_readiness

        self.client_row.current_size = "M"
        self.client_row.sales_context = {
            "assisted_checkout_selection": {
                "product_id": self.product.pk,
                "fit_option_code": "classic",
            }
        }
        self.client_row.save(update_fields=["current_size", "sales_context", "updated_at"])

        state = checkout_readiness(self.client_row)

        self.assertIn("options_unavailable", state["missing"])
        self.assertFalse(state["can_issue_link"])

    def test_missing_fit_is_stated_with_available_options(self):
        from management.services.ig_checkout_readiness import readiness_prompt_note

        note = readiness_prompt_note(self.client_row)

        self.assertIn("фасон: не обрано", note)
        self.assertIn("classic", note)
        self.assertIn("oversize", note)
        self.assertIn("бракує", note)

    def test_note_forbids_repeating_the_previous_question_verbatim(self):
        from management.services.ig_checkout_readiness import readiness_prompt_note

        note = readiness_prompt_note(self.client_row)

        self.assertIn("Не повторюй", note)

    def test_zero_stock_product_is_not_reported_as_unavailable(self):
        from management.services.ig_checkout_readiness import checkout_readiness

        state = checkout_readiness(self.client_row)

        self.assertTrue(state["has_product"])
        self.assertEqual([option["variant_id"] for option in state["color"]["options"]],
                         [self.variant.pk])

    def test_ready_configuration_authorizes_the_link(self):
        from management.services.ig_checkout_readiness import checkout_readiness

        self.client_row.current_size = "M"
        self.client_row.sales_context = {
            "assisted_checkout_selection": {
                "product_id": self.product.pk,
                "fit_option_code": "classic",
            }
        }
        self.client_row.save(update_fields=["current_size", "sales_context", "updated_at"])

        state = checkout_readiness(self.client_row)

        self.assertEqual(state["missing"], [])
        self.assertTrue(state["can_issue_link"])

    def test_single_adjusted_variant_price_reaches_prompt_before_generation(self):
        from management.services.ig_checkout_readiness import (
            checkout_readiness,
            readiness_prompt_note,
        )

        self.variant.price_override = 1450
        self.variant.save(update_fields=["price_override"])
        self.client_row.current_size = "M"
        self.client_row.sales_context = {
            "assisted_checkout_selection": {
                "product_id": self.product.pk,
                "fit_option_code": "classic",
            }
        }
        self.client_row.save(update_fields=["current_size", "sales_context", "updated_at"])

        state = checkout_readiness(self.client_row)
        note = readiness_prompt_note(self.client_row, readiness=state)

        self.assertEqual(state["product"]["price"], "1450.00")
        self.assertTrue(state["product"]["price_exact"])
        self.assertEqual(state["color"]["selected_variant_id"], self.variant.pk)
        self.assertIn("точна ціна конфігурації: 1450.00 грн", note)

    @patch(
        "management.services.ig_catalog_pricing.resolve_product_pricing",
        return_value={"display": "", "exact": False},
    )
    def test_unresolved_variant_price_never_falls_back_to_product_base(self, _pricing):
        from management.services.ig_checkout_readiness import (
            checkout_readiness,
            readiness_prompt_note,
        )

        state = checkout_readiness(self.client_row)
        note = readiness_prompt_note(self.client_row, readiness=state)

        self.assertEqual(state["product"]["price"], "")
        self.assertFalse(state["product"]["price_exact"])
        self.assertIn("ціна конфігурації не визначена", note)
        self.assertNotIn("880 грн", note)

    def test_unavailable_requested_size_is_told_honestly_with_a_next_step(self):
        from fable5.models import SizeGrid, VariantSizeRule
        from management.services.ig_checkout_readiness import readiness_prompt_note

        VariantSizeRule.objects.create(
            variant=self.variant, fit_code="classic", size="M", is_enabled=False,
        )
        self.client_row.current_size = "M"
        self.client_row.sales_context = {
            "assisted_checkout_selection": {
                "product_id": self.product.pk,
                "fit_option_code": "classic",
            }
        }
        self.client_row.save(update_fields=["current_size", "sales_context", "updated_at"])

        note = readiness_prompt_note(self.client_row)

        # Факт і напрямок дії є; конкретні слова — робота моделі.
        self.assertIn("менеджер", note.lower())

    def test_prompt_carries_the_readiness_block(self):
        from management.models import InstagramBotSettings
        from management.services import instagram_bot as bot

        settings_obj = InstagramBotSettings.load()
        text = bot.assemble_system_instruction(settings_obj, client=self.client_row)

        self.assertIn("[СТАН ОФОРМЛЕННЯ", text)


class CustomerProductLinkTests(TestCase):
    """Посилання на товар від клієнта — це вибір, а не шум."""

    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="link-shirts")
        self.classic = Product.objects.create(
            title="Класична футболка",
            slug="classic-tshirt",
            category=self.category,
            price=880,
            status=ProductStatus.PUBLISHED,
        )
        self.other = Product.objects.create(
            title="Reality Bends",
            slug="reality-bends",
            category=self.category,
            price=880,
            status=ProductStatus.PUBLISHED,
        )
        self.client_row = _client("customer-link")

    def test_exact_storefront_url_resolves_to_the_published_product(self):
        from management.services.ig_checkout_readiness import product_reference_from_text

        reference = product_reference_from_text(
            "https://twocomms.shop/product/classic-tshirt/\n\nВот я за этот вариант"
        )

        self.assertTrue(reference["found"])
        self.assertEqual(reference["product_id"], self.classic.pk)

    def test_localized_url_with_query_and_fragment_still_resolves(self):
        from management.services.ig_checkout_readiness import product_reference_from_text

        reference = product_reference_from_text(
            "https://twocomms.shop/ru/product/classic-tshirt/?utm_source=ig#size"
        )

        self.assertTrue(reference["found"])
        self.assertEqual(reference["product_id"], self.classic.pk)

    def test_lookalike_host_is_refused(self):
        from management.services.ig_checkout_readiness import product_reference_from_text

        reference = product_reference_from_text(
            "https://twocomms.shop.evil.test/product/classic-tshirt/"
        )

        self.assertFalse(reference["found"])

    def test_two_different_products_ask_instead_of_guessing(self):
        from management.services.ig_checkout_readiness import product_reference_from_text

        reference = product_reference_from_text(
            "https://twocomms.shop/product/classic-tshirt/ "
            "https://twocomms.shop/product/reality-bends/"
        )

        self.assertFalse(reference["found"])
        self.assertEqual(reference["reason"], "multiple_products")

    def test_turn_note_flags_the_product_change_for_the_model(self):
        from management.services import instagram_bot as bot

        self.client_row.current_product = self.other
        self.client_row.save(update_fields=["current_product", "updated_at"])

        note = bot.customer_turn_note(
            self.client_row, "https://twocomms.shop/product/classic-tshirt/ Вот я за этот"
        )

        self.assertIn("ІНШИЙ товар", note)
        self.assertIn(f"[PRODUCT:{self.classic.pk}]", note)


class SelectionMemoryTests(TestCase):
    """Факт, названий одного ходу, лишається відомим наступного."""

    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="memory-shirts")
        self.product = Product.objects.create(
            title="Худі",
            slug="memory-hoodie",
            category=self.category,
            price=1912,
            status=ProductStatus.PUBLISHED,
        )
        ProductFitOption.objects.create(
            product=self.product, code="classic", label="Класичний", is_active=True,
        )
        self.client_row = _client("selection-memory")
        self.client_row.current_product = self.product
        self.client_row.save(update_fields=["current_product", "updated_at"])

    def test_fit_tag_without_paylink_is_persisted(self):
        from management.services import instagram_bot as bot

        changed = bot.persist_control_selection(
            self.client_row, {"fit": "classic"},
        )

        self.client_row.refresh_from_db()
        self.assertIn("fit", changed)
        self.assertEqual(
            self.client_row.sales_context["assisted_checkout_selection"]["fit_option_code"],
            "classic",
        )

    def test_size_and_quantity_tags_are_persisted(self):
        from management.services import instagram_bot as bot

        bot.persist_control_selection(
            self.client_row, {"size": "m", "qty": "2"},
        )

        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.current_size, "M")
        self.assertEqual(self.client_row.current_qty, 2)

    def test_arbitrary_option_tag_is_persisted_with_selection(self):
        from management.services import instagram_bot as bot

        changed = bot.persist_control_selection(
            self.client_row,
            {"options": ["material=thermo"]},
        )

        self.client_row.refresh_from_db()
        self.assertIn("option:material", changed)
        self.assertEqual(
            self.client_row.sales_context["assisted_checkout_selection"]["option_values"],
            {"material": "thermo"},
        )

    def test_conflicting_tags_are_not_persisted(self):
        from management.services import instagram_bot as bot

        changed = bot.persist_control_selection(
            self.client_row, {"fit": "classic", "_invalid": True},
        )

        self.assertEqual(changed, [])
        self.client_row.refresh_from_db()
        self.assertNotIn(
            "assisted_checkout_selection", self.client_row.sales_context or {},
        )


class RepeatPurchaseTests(TestCase):
    """Той, хто вже купував, має право купити знову."""

    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="repeat-shirts")
        self.product = Product.objects.create(
            title="Футболка для повторної покупки",
            slug="repeat-tshirt",
            category=self.category,
            price=880,
            status=ProductStatus.PUBLISHED,
        )
        self.client_row = _client("repeat-purchase")
        self.client_row.current_product = self.product
        self.client_row.current_size = "M"
        self.client_row.save(update_fields=[
            "current_product", "current_size", "updated_at",
        ])

    def _completed_paid_deal(self):
        from orders.models import Order
        from management.models import IgDeal

        order = Order.objects.create(
            order_number="TWC-REPEAT-1",
            full_name="Тест Тестович",
            phone="380500000000",
            city="Київ",
            np_office="1",
            total_sum=Decimal("880.00"),
            payment_status="paid",
        )
        return IgDeal.objects.create(
            client=self.client_row,
            status=IgDeal.Status.ORDER_CREATED,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("880.00"),
            order=order,
        )

    def test_completed_previous_purchase_does_not_block_a_new_link(self):
        from management.services import instagram_bot as bot

        self._completed_paid_deal()
        self.client_row.stage = IgClient.Stage.PAID
        self.client_row.save(update_fields=["stage", "updated_at"])

        allowed = bot.payment_link_allowed(
            self.client_row,
            {"paylink": "full", "product": self.product.pk},
            "Хочу ще одну, оформлюємо",
        )

        self.assertTrue(allowed)

    def test_paid_deal_without_an_order_still_blocks_a_duplicate_invoice(self):
        from management.models import IgDeal
        from management.services import instagram_bot as bot

        IgDeal.objects.create(
            client=self.client_row,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("880.00"),
        )

        allowed = bot.payment_link_allowed(
            self.client_row,
            {"paylink": "full", "product": self.product.pk},
            "Оформлюємо замовлення",
        )

        self.assertFalse(allowed)


class NoScriptedRepliesTests(TestCase):
    """У коді не лишилось заготовлених питань до клієнта."""

    def test_copy_table_contains_only_facts_about_a_real_link(self):
        from management.services.instagram_bot import _ASSISTED_CHECKOUT_COPY

        for locale, values in _ASSISTED_CHECKOUT_COPY.items():
            with self.subTest(locale=locale):
                self.assertEqual(
                    sorted(values.keys()), ["proposal", "proposal_with_summary"],
                )

    def test_configuration_gap_is_classified_not_answered(self):
        from management.services.instagram_bot import _is_configuration_gap

        self.assertTrue(_is_configuration_gap({"error": "missing_configuration"}))
        self.assertTrue(_is_configuration_gap({"error": "insufficient_stock"}))
        self.assertFalse(_is_configuration_gap({"error": "no_product"}))
        self.assertFalse(_is_configuration_gap({}))


class SizeGapEscalationTests(TestCase):
    """Обіцянка «уточню в менеджера» має бути правдивою."""

    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="gap-shirts")
        self.product = Product.objects.create(
            title="Футболка з вимкненим розміром",
            slug="gap-tshirt",
            category=self.category,
            price=880,
            status=ProductStatus.PUBLISHED,
        )
        ProductFitOption.objects.create(
            product=self.product, code="classic", label="Класичний", is_active=True,
        )
        black = Color.objects.create(name="Чорний", primary_hex="#111111")
        self.variant = ProductColorVariant.objects.create(
            product=self.product, color=black, stock=0, slug="black",
        )
        from fable5.models import VariantSizeRule

        VariantSizeRule.objects.create(
            variant=self.variant, fit_code="classic", size="M", is_enabled=False,
        )
        self.client_row = _client("size-gap")
        self.client_row.current_product = self.product
        self.client_row.current_size = "M"
        self.client_row.sales_context = {
            "assisted_checkout_selection": {
                "product_id": self.product.pk,
                "fit_option_code": "classic",
            }
        }
        self.client_row.save(update_fields=[
            "current_product", "current_size", "sales_context", "updated_at",
        ])

    @patch("management.services.instagram_bot.notify_manager")
    def test_missing_size_reaches_the_manager_once_per_day(self, mock_notify):
        from django.core.cache import cache
        from management.services import instagram_bot as bot

        cache.clear()

        self.assertTrue(bot.notify_size_gap(self.client_row))
        self.assertFalse(bot.notify_size_gap(self.client_row))
        self.assertEqual(mock_notify.call_count, 1)
        message = mock_notify.call_args.args[0]
        self.assertIn("M", message)
        self.assertIn(self.product.title, message)

    @patch("management.services.instagram_bot.notify_manager")
    def test_available_size_does_not_bother_the_manager(self, mock_notify):
        from django.core.cache import cache
        from management.services import instagram_bot as bot

        cache.clear()
        self.client_row.current_size = "L"
        self.client_row.save(update_fields=["current_size", "updated_at"])

        self.assertFalse(bot.notify_size_gap(self.client_row))
        mock_notify.assert_not_called()


class WebhookSecretCoverageTests(TestCase):
    """Обидва наші app secret приймаються; чужий підпис — ні."""

    def test_both_configured_app_secrets_verify_a_webhook(self):
        import hashlib
        import hmac
        from unittest.mock import patch as _patch

        from management.services import instagram_bot as bot

        body = b'{"object":"instagram","entry":[]}'
        with _patch.dict(
            "os.environ",
            {"IG_APP_SECRET": "ig-secret-value", "META_APP_SECRET": "meta-secret-value"},
            clear=False,
        ):
            self.assertEqual(len(bot.webhook_secrets()), 2)
            for secret in ("ig-secret-value", "meta-secret-value"):
                header = "sha256=" + hmac.new(
                    secret.encode(), body, hashlib.sha256
                ).hexdigest()
                self.assertTrue(bot.verify_signature(body, header), secret)

    def test_foreign_secret_is_still_rejected(self):
        import hashlib
        import hmac
        from unittest.mock import patch as _patch

        from management.services import instagram_bot as bot

        body = b'{"object":"instagram","entry":[]}'
        with _patch.dict(
            "os.environ",
            {"IG_APP_SECRET": "ig-secret-value", "META_APP_SECRET": "meta-secret-value"},
            clear=False,
        ):
            header = "sha256=" + hmac.new(
                b"attacker-secret", body, hashlib.sha256
            ).hexdigest()
            self.assertFalse(bot.verify_signature(body, header))


class CatalogBudgetTests(TestCase):
    """Каталог не має обрізати товари, про які клієнт питає."""

    def test_budget_fits_a_full_production_sized_catalog(self):
        from management.services.bot_catalog import MAX_CHARS

        # На проді при лімiті 16 000 каталог важив 15 977 і в промпт потрапляли
        # 48 товарів із 71. Найстаріші (базові моделі id=1..3) відрізало, і бот
        # казав клієнту, що однотонної класики «немає в наявності».
        self.assertGreaterEqual(MAX_CHARS, 32000)

    def test_zero_stock_is_described_as_made_to_order_not_as_absent(self):
        from management.services.bot_catalog import get_catalog_context

        category = Category.objects.create(name="Футболки", slug="budget-shirts")
        Product.objects.create(
            title="Футболка без обліку залишку",
            slug="budget-tshirt",
            category=category,
            price=880,
            status=ProductStatus.PUBLISHED,
        )
        catalog = get_catalog_context(force=True)

        self.assertIn("під замовлення", catalog)
        self.assertNotIn("stock=0", catalog)

    def test_every_published_product_reaches_the_prompt(self):
        from management.services.bot_catalog import get_catalog_context

        category = Category.objects.create(name="Каталог", slug="budget-full")
        for index in range(40):
            Product.objects.create(
                title=f"Товар з довгою назвою для перевірки бюджету {index}",
                slug=f"budget-item-{index}",
                category=category,
                price=880 + index,
                status=ProductStatus.PUBLISHED,
            )

        catalog = get_catalog_context(force=True)

        self.assertEqual(catalog.count("• id="), 40)
        self.assertNotIn("не вміщено", catalog)


class OwnEchoRecognitionTests(TestCase):
    """Наше власне echo не має вмикати takeover.

    Прод, 02.08.2026: бот надіслав каруселлю два фото, Meta повернула echo, і
    система порахувала їх повідомленнями менеджера — увімкнула `manager_takeover`,
    поставила клієнта на паузу, з'їла вже згенерований текст відповіді. Клієнт #5
    і клієнт #2 обидва отримали фото без підпису й далі мовчання; наступні
    повідомлення пішли в `observed`. На той момент у takeover висіло 57 клієнтів
    із 289, і зняти це можна було лише руками.
    """

    def setUp(self):
        self.client_row = _client("own-echo")

    def test_media_echo_with_our_message_id_is_ignored(self):
        from management.models import IgClient
        from management.services import instagram_bot as bot
        from management.services.ig_outgoing_registry import register_outgoing

        message_id = "aWdfZAG1faXRlbTo6our-media-1"
        register_outgoing(message_id, recipient_id=self.client_row.igsid, kind="media")

        bot._handle_echo(
            self.client_row.igsid,
            "",
            attachments=[{"url": "https://twocomms.shop/media/products/x.webp"}],
            mid=message_id,
        )

        fresh = IgClient.objects.get(pk=self.client_row.pk)
        self.assertFalse(fresh.manager_takeover)
        self.assertFalse(fresh.bot_paused)
        self.assertFalse(
            InstagramBotMessage.objects.filter(
                client=fresh, role=InstagramBotMessage.Role.MANAGER
            ).exists()
        )

    def test_real_manager_media_still_triggers_takeover(self):
        from management.models import IgClient
        from management.services import instagram_bot as bot

        bot._handle_echo(
            self.client_row.igsid,
            "",
            attachments=[{"url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=1"}],
            mid="aWdfZAG1faXRlbTo6manager-media-1",
        )

        fresh = IgClient.objects.get(pk=self.client_row.pk)
        self.assertTrue(fresh.manager_takeover)
        self.assertTrue(fresh.bot_paused)
        self.assertTrue(
            InstagramBotMessage.objects.filter(
                client=fresh, role=InstagramBotMessage.Role.MANAGER
            ).exists()
        )

    def test_text_echo_of_our_reply_is_ignored_by_message_id(self):
        from management.models import IgClient
        from management.services import instagram_bot as bot
        from management.services.ig_outgoing_registry import register_outgoing

        message_id = "aWdfZAG1faXRlbTo6our-text-1"
        register_outgoing(message_id, recipient_id=self.client_row.igsid, kind="text")

        bot._handle_echo(self.client_row.igsid, "Ось ваше посилання", mid=message_id)

        self.assertFalse(IgClient.objects.get(pk=self.client_row.pk).manager_takeover)


class StaleTakeoverReleaseTests(TestCase):
    """Пауза від менеджера не має тривати вічно."""

    def setUp(self):
        self.client_row = _client("stale-takeover")

    def _put_in_takeover(self, hours_ago):
        moment = timezone.now() - timezone.timedelta(hours=hours_ago)
        self.client_row.manager_takeover = True
        self.client_row.bot_paused = True
        self.client_row.paused_reason = "manager_takeover"
        self.client_row.paused_at = moment
        self.client_row.last_manager_message_at = moment
        self.client_row.save(update_fields=[
            "manager_takeover", "bot_paused", "paused_reason",
            "paused_at", "last_manager_message_at", "updated_at",
        ])

    @patch("management.services.instagram_bot.notify_manager")
    def test_long_silent_takeover_is_released(self, mock_notify):
        from management.models import IgClient
        from management.services import instagram_bot as bot

        self._put_in_takeover(30)

        self.assertTrue(bot.maybe_release_stale_takeover(self.client_row))
        fresh = IgClient.objects.get(pk=self.client_row.pk)
        self.assertFalse(fresh.manager_takeover)
        self.assertFalse(fresh.bot_paused)
        mock_notify.assert_called_once()

    @patch("management.services.instagram_bot.notify_manager")
    def test_active_manager_conversation_is_not_interrupted(self, mock_notify):
        from management.models import IgClient
        from management.services import instagram_bot as bot

        self._put_in_takeover(2)

        self.assertFalse(bot.maybe_release_stale_takeover(self.client_row))
        self.assertTrue(IgClient.objects.get(pk=self.client_row.pk).manager_takeover)
        mock_notify.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    def test_opted_out_client_is_never_auto_resumed(self, mock_notify):
        from management.models import IgClient
        from management.services import instagram_bot as bot

        self._put_in_takeover(48)
        self.client_row.opted_out_at = timezone.now() - timezone.timedelta(hours=40)
        self.client_row.save(update_fields=["opted_out_at", "updated_at"])

        self.assertFalse(bot.maybe_release_stale_takeover(self.client_row))
        self.assertTrue(IgClient.objects.get(pk=self.client_row.pk).manager_takeover)
        mock_notify.assert_not_called()


class ShownProductsMemoryTests(TestCase):
    """«Давай першу» має розв'язуватись фактом, а не вгадуванням."""

    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="shown-shirts")
        self.first = Product.objects.create(
            title="Футболка класична",
            slug="shown-classic",
            category=self.category,
            price=788,
            status=ProductStatus.PUBLISHED,
        )
        self.second = Product.objects.create(
            title="Футболка «Без жодних сумнівів»",
            slug="shown-doubts",
            category=self.category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        self.client_row = _client("shown-products")

    def _selection_and_delivery(self):
        from management.services.ig_catalog_media import (
            CatalogMediaDelivery,
            CatalogMediaDeliveryState,
            CatalogMediaItem,
            CatalogMediaSelection,
            CatalogMediaState,
        )

        items = (
            CatalogMediaItem(
                url="https://twocomms.shop/media/products/classic.webp",
                title=self.first.title,
                alt=self.first.title,
                product_id=self.first.pk,
                mime_type="image/webp",
                size_bytes=1024,
            ),
            CatalogMediaItem(
                url="https://twocomms.shop/media/products/doubts.webp",
                title=self.second.title,
                alt=self.second.title,
                product_id=self.second.pk,
                mime_type="image/webp",
                size_bytes=2048,
            ),
        )
        selection = CatalogMediaSelection(state=CatalogMediaState.READY, items=items)
        delivery = CatalogMediaDelivery(
            CatalogMediaDeliveryState.SENT,
            sent_count=2,
            attempted_count=2,
            provider_message_ids=("mid-shown-1", "mid-shown-2"),
        )
        return selection, delivery

    def test_shown_order_is_persisted_with_product_ids(self):
        from management.services import instagram_bot as bot

        selection, delivery = self._selection_and_delivery()
        shown = bot.record_shown_products(
            self.client_row, self.client_row.igsid, selection, delivery
        )

        self.assertEqual([entry["position"] for entry in shown], [1, 2])
        self.assertEqual(
            [entry["product_id"] for entry in shown], [self.first.pk, self.second.pk]
        )
        self.client_row.refresh_from_db()
        stored = self.client_row.sales_context["shown_products"]["items"]
        self.assertEqual(stored[0]["product_id"], self.first.pk)

    def test_sent_photos_appear_in_the_transcript_as_ours(self):
        from management.services import instagram_bot as bot

        selection, delivery = self._selection_and_delivery()
        bot.record_shown_products(
            self.client_row, self.client_row.igsid, selection, delivery
        )

        rows = InstagramBotMessage.objects.filter(
            client=self.client_row, source="catalog_media"
        ).order_by("id")
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows[0].role, InstagramBotMessage.Role.MODEL)
        self.assertEqual(rows[0].provider_message_id, "mid-shown-1")
        self.assertIn(self.first.title, rows[0].text)

    def test_partial_delivery_records_only_what_was_sent(self):
        from management.services import instagram_bot as bot
        from management.services.ig_catalog_media import (
            CatalogMediaDelivery,
            CatalogMediaDeliveryState,
        )

        selection, _ = self._selection_and_delivery()
        delivery = CatalogMediaDelivery(
            CatalogMediaDeliveryState.PARTIAL,
            sent_count=1,
            attempted_count=2,
            provider_message_ids=("mid-shown-1",),
        )

        shown = bot.record_shown_products(
            self.client_row, self.client_row.igsid, selection, delivery
        )

        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0]["product_id"], self.first.pk)

    def test_prompt_lists_shown_photos_in_order(self):
        from management.services import instagram_bot as bot

        selection, delivery = self._selection_and_delivery()
        bot.record_shown_products(
            self.client_row, self.client_row.igsid, selection, delivery
        )
        self.client_row.refresh_from_db()

        note = bot.shown_products_note(self.client_row)

        self.assertIn("1) Футболка класична", note)
        self.assertIn(f"id={self.first.pk}", note)
        self.assertIn("2) Футболка «Без жодних сумнівів»", note)
        self.assertIn("першу", note)


class PhotoProtocolTests(TestCase):
    """Фото — відповідь на конкретний запит, а не спосіб почати розмову."""

    def test_protocol_requires_text_before_photos(self):
        from management.services.instagram_bot import PAYMENT_PROTOCOL_NOTE

        self.assertIn("ПОРЯДОК ПОКАЗУ ФОТО", PAYMENT_PROTOCOL_NOTE)
        self.assertIn("Спершу з'ясуй текстом", PAYMENT_PROTOCOL_NOTE)

    def test_protocol_defines_what_a_plain_tshirt_means(self):
        from management.services.instagram_bot import PAYMENT_PROTOCOL_NOTE

        self.assertIn("класична", PAYMENT_PROTOCOL_NOTE)
        self.assertIn("логотипом на груді", PAYMENT_PROTOCOL_NOTE)

    def test_protocol_offers_link_or_screenshot_instead_of_guessing(self):
        from management.services.instagram_bot import PAYMENT_PROTOCOL_NOTE

        self.assertIn("скриншот", PAYMENT_PROTOCOL_NOTE)
