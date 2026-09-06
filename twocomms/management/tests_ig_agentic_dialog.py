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

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from management.models import IgClient, IgFollowUpTask, InstagramBotMessage
from product_catalog.models import GarmentFlow, GarmentFlowCategory
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption, ProductStatus


def _client(igsid="agentic-dialog"):
    return IgClient.get_or_create_for_sender(igsid)


class ResponseControlBoundaryTests(SimpleTestCase):
    """The model may propose controls only through a typed, fail-closed boundary."""

    def test_structured_response_projects_valid_controls_for_downstream(self):
        from management.services.ig_response_control import parse_structured_response

        result = parse_structured_response({
            "reply_text": "Готово, покажу варіанти",
            "controls": [
                {"kind": "manager", "value": True},
                {"kind": "stage", "value": "qualifying"},
                {"kind": "paylink", "value": "full"},
                {"kind": "product", "value": 12},
                {"kind": "item", "value": "12|1|M|classic|81"},
                {"kind": "option", "value": "material=thermo"},
                {"kind": "qty", "value": 2},
                {"kind": "size", "value": "M"},
                {"kind": "fit", "value": "classic"},
                {"kind": "color_variant_id", "value": 81},
                {"kind": "price", "value": "1450"},
                {"kind": "price_quoted", "value": 1450},
                {"kind": "payment", "value": 200},
                {"kind": "order", "value": True},
                {"kind": "show_products", "value": [12, 34]},
                {"kind": "catalog_link", "value": True},
            ],
        })

        self.assertTrue(result.valid)
        self.assertEqual(result.reply_text, "Готово, покажу варіанти")
        self.assertEqual(result.control["manager"], True)
        self.assertEqual(result.control["stage"], "qualifying")
        self.assertEqual(result.control["paylink"], "full")
        self.assertEqual(result.control["product"], "12")
        self.assertEqual(result.control["items"], ["12|1|M|classic|81"])
        self.assertEqual(result.control["options"], ["material=thermo"])
        self.assertEqual(result.control["qty"], "2")
        self.assertEqual(result.control["size"], "M")
        self.assertEqual(result.control["fit"], "classic")
        self.assertEqual(result.control["color_variant_id"], "81")
        self.assertEqual(result.control["price"], "1450")
        self.assertEqual(result.control["price_quoted"], "1450")
        self.assertEqual(result.control["payment"], "200")
        self.assertEqual(result.control["order"], True)
        self.assertEqual(result.control["show_products"], "12,34")
        self.assertEqual(result.control["catalog_link"], True)

    def test_structured_response_keeps_optional_follow_candidate_separate(self):
        from management.services.ig_response_control import (
            FollowCtaCandidate,
            parse_structured_response,
        )

        result = parse_structured_response({
            "reply_text": "Дякуємо, оплату отримали.",
            "controls": [{"kind": "stage", "value": "checkout"}],
            "follow_cta": {
                "include": True,
                "text": "Якщо вам близький наш підхід, будемо раді бачити вас серед підписників.",
            },
        })

        self.assertTrue(result.valid)
        self.assertIsInstance(result.follow_cta, FollowCtaCandidate)
        self.assertEqual(
            result.follow_cta.text,
            "Якщо вам близький наш підхід, будемо раді бачити вас серед підписників.",
        )
        self.assertEqual(result.control["stage"], "checkout")

    def test_invalid_optional_follow_candidate_is_discarded_without_poisoning_base(self):
        from management.services.ig_response_control import parse_structured_response

        for candidate in (
            {"include": True, "text": "https://twocomms.shop отримайте 10% зараз"},
            {"include": True, "text": "Підпишіться на t.me/twocomms і залишайтеся з нами."},
            {"include": True, "text": "Деталі є на bit.ly/twocomms-follow, будемо раді вам."},
            {"include": True, "text": "Приєднуйтесь до нас на t\u200b.me/twocomms, будемо раді вам."},
            {"include": True, "text": "Підпишіться та використайте код TWOCOMMS10 при замовленні."},
            {"include": True, "text": "Підпишіться та використайте TWOCOMMS10 при замовленні."},
            {"include": True, "text": "Підпишіться, щоб отримати знижку на наступне замовлення."},
            {"include": True, "text": "Ми бачимо, що ви ще не підписані на нашу сторінку."},
            {"include": True, "text": "Я бачу, що ви ще не підписані на нашу сторінку."},
            {"include": True, "text": "Ви ще не підписані на сторінку, будемо раді вам."},
            {"include": True, "text": "Статус вашої підписки ще не активний, будемо раді вам."},
            {"include": True, "text": "Будемо раді вам серед підписників [FOLLOW:TRUE]."},
            {"include": "yes", "text": "Підпишіться"},
            {"include": True, "text": ""},
            {"include": True, "text": "ok", "extra": "discard"},
        ):
            with self.subTest(candidate=candidate):
                result = parse_structured_response({
                    "reply_text": "Безпечна відповідь",
                    "controls": [{"kind": "manager", "value": True}],
                    "follow_cta": candidate,
                })
                self.assertTrue(result.valid)
                self.assertIsNone(result.follow_cta)
                self.assertEqual(result.control["manager"], True)

    def test_missing_follow_candidate_is_backward_compatible(self):
        from management.services.ig_response_control import parse_structured_response

        result = parse_structured_response({"reply_text": "Готово", "controls": []})

        self.assertTrue(result.valid)
        self.assertIsNone(result.follow_cta)

    def test_validated_response_preserves_legacy_positional_field_order(self):
        from management.services.ig_response_control import ValidatedResponse

        result = ValidatedResponse("Безпечна відповідь", (), False, "legacy_error")

        self.assertFalse(result.valid)
        self.assertEqual(result.error, "legacy_error")
        self.assertIsNone(result.follow_cta)

    def test_structured_result_is_immutable_and_projection_is_copy(self):
        from dataclasses import FrozenInstanceError

        from management.services.ig_response_control import parse_structured_response

        result = parse_structured_response({"reply_text": "ok", "controls": []})
        with self.assertRaises(FrozenInstanceError):
            result.reply_text = "changed"
        projection = result.control
        projection["manager"] = True
        self.assertEqual(result.control, {})

    def test_structured_unknown_control_fails_closed_without_controls(self):
        from management.services.ig_response_control import parse_structured_response

        result = parse_structured_response({
            "reply_text": "Ось відповідь",
            "controls": [{"kind": "handover_now", "value": True}],
        })

        self.assertFalse(result.valid)
        self.assertEqual(result.control, {})
        self.assertEqual(result.controls, ())
        self.assertEqual(result.reply_text, "Ось відповідь")

    def test_structured_controls_are_canonical_positive_proposals_only(self):
        from management.services.ig_response_control import parse_structured_response

        for control in (
            {"kind": "variant", "value": 81},
            {"kind": "manager", "value": False},
            {"kind": "spam", "value": False},
            {"kind": "order", "value": False},
            {"kind": "catalog_link", "value": False},
            {"kind": "opt_in", "value": True},
            {"kind": "consent", "value": True},
        ):
            with self.subTest(control=control):
                result = parse_structured_response({
                    "reply_text": "Безпечна відповідь",
                    "controls": [control],
                })
                self.assertFalse(result.valid)
                self.assertEqual(result.control, {})

    def test_structured_application_limits_fail_closed(self):
        from management.services.ig_response_control import parse_structured_response

        oversized_text = parse_structured_response({
            "reply_text": "x" * 4001,
            "controls": [],
        })
        oversized_controls = parse_structured_response({
            "reply_text": "ok",
            "controls": [
                {"kind": "option", "value": f"axis_{index}=value"}
                for index in range(33)
            ],
        })

        self.assertFalse(oversized_text.valid)
        self.assertFalse(oversized_controls.valid)
        self.assertEqual(oversized_text.control, {})
        self.assertEqual(oversized_controls.control, {})

    def test_structured_malformed_control_and_extra_payload_keys_fail_closed(self):
        from management.services.ig_response_control import parse_structured_response

        for payload in (
            {"reply_text": "x", "controls": [{"kind": "manager"}]},
            {"reply_text": "x", "controls": "[MANAGER]"},
            {"reply_text": "x", "controls": [], "debug": "leak"},
        ):
            with self.subTest(payload=payload):
                result = parse_structured_response(payload)
                self.assertFalse(result.valid)
                self.assertEqual(result.control, {})

    def test_structured_conflicting_singleton_controls_fail_closed(self):
        from management.services.ig_response_control import parse_structured_response

        result = parse_structured_response({
            "reply_text": "Відповідь",
            "controls": [
                {"kind": "paylink", "value": "full"},
                {"kind": "paylink", "value": "prepay"},
            ],
        })

        self.assertFalse(result.valid)
        self.assertEqual(result.control, {})

    def test_structured_duplicate_singleton_controls_fail_closed_even_when_equal(self):
        from management.services.ig_response_control import parse_structured_response

        for kind, value in (("manager", True), ("order", True), ("paylink", "full")):
            with self.subTest(kind=kind):
                result = parse_structured_response({
                    "reply_text": "Відповідь",
                    "controls": [
                        {"kind": kind, "value": value},
                        {"kind": kind, "value": value},
                    ],
                })
                self.assertFalse(result.valid)
                self.assertEqual(result.control, {})

    def test_structured_duplicate_singleton_with_same_value_fails_closed(self):
        from management.services.ig_response_control import parse_structured_response

        for kind, value in (("order", True), ("manager", True), ("stage", "qualifying")):
            with self.subTest(kind=kind):
                result = parse_structured_response({
                    "reply_text": "Безпечна відповідь",
                    "controls": [
                        {"kind": kind, "value": value},
                        {"kind": kind, "value": value},
                    ],
                })
                self.assertFalse(result.valid)
                self.assertEqual(result.control, {})

    def test_legacy_duplicate_singleton_with_same_value_fails_closed(self):
        from management.services.ig_response_control import parse_legacy_response

        for reply in (
            "Відповідь [ORDER] [ORDER]",
            "Відповідь [MANAGER] [MANAGER]",
            "Відповідь [STAGE:qualifying] [STAGE:qualifying]",
        ):
            with self.subTest(reply=reply):
                result = parse_legacy_response(reply)
                self.assertFalse(result.valid)
                self.assertEqual(result.control, {})

    def test_structured_hard_stage_and_invalid_ids_or_numbers_fail_closed(self):
        from management.services.ig_response_control import parse_structured_response

        for control in (
            {"kind": "stage", "value": "paid"},
            {"kind": "stage", "value": "order_created"},
            {"kind": "product", "value": 0},
            {"kind": "color_variant_id", "value": -4},
            {"kind": "qty", "value": 1.5},
            {"kind": "price", "value": "not-a-number"},
        ):
            with self.subTest(control=control):
                result = parse_structured_response({
                    "reply_text": "Відповідь",
                    "controls": [control],
                })
                self.assertFalse(result.valid)
                self.assertEqual(result.control, {})

    def test_structured_reply_text_cannot_carry_control_tokens(self):
        from management.services.ig_response_control import parse_structured_response

        result = parse_structured_response({
            "reply_text": "Оплата [MANAGER] [PAYLINK:full]",
            "controls": [],
        })

        self.assertFalse(result.valid)
        self.assertEqual(result.control, {})
        self.assertNotIn("[MANAGER]", result.reply_text)
        self.assertNotIn("[PAYLINK:full]", result.reply_text)

    def test_legacy_known_uppercase_tags_are_parsed_and_removed(self):
        from management.services.ig_response_control import parse_legacy_response

        result = parse_legacy_response(
            "Готово [MANAGER] [STAGE:qualifying] [PAYLINK:full] "
            "[PRODUCT:12] [ITEM:12|1|M|classic|81] [OPTION:material=thermo] "
            "[QTY:2] [SIZE:M] [FIT:classic] [VARIANT:81] [PRICE:1450] "
            "[PRICE_QUOTED:1450] [PAYMENT:200] [ORDER] [SHOW_PRODUCTS:12,34] "
            "[CATALOG_LINK] [OBJHANDLE:price:value_breakdown]"
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.reply_text, "Готово")
        self.assertEqual(result.control["manager"], True)
        self.assertEqual(result.control["stage"], "qualifying")
        self.assertEqual(result.control["paylink"], "full")
        self.assertEqual(result.control["product"], "12")
        self.assertEqual(result.control["items"], ["12|1|M|classic|81"])
        self.assertEqual(result.control["options"], ["material=thermo"])
        self.assertEqual(result.control["color_variant_id"], "81")
        self.assertEqual(result.control["objhandle"], "price:value_breakdown")

    def test_long_control_shaped_suffix_is_invalid_and_never_leaks(self):
        from management.services.ig_response_control import (
            parse_legacy_response,
            parse_structured_response,
        )

        token = "[PAYLINK:" + ("x" * 300) + "]"
        for result in (
            parse_legacy_response("Готово " + token),
            parse_structured_response({
                "reply_text": "Готово " + token,
                "controls": [],
            }),
        ):
            with self.subTest(error=result.error):
                self.assertFalse(result.valid)
                self.assertEqual(result.control, {})
                self.assertEqual(result.reply_text, "Готово")

    def test_legacy_unknown_lowercase_typo_and_malformed_controls_fail_closed(self):
        from management.services.ig_response_control import parse_legacy_response

        for text in (
            "Відповідь [manager]",
            "Відповідь [MANAGR]",
            "Відповідь [UNSAFE:delete]",
            "Відповідь [PAYLINK:]",
            "Відповідь [STAGE:paid]",
            "Відповідь [PAYLINK:full] [PAYLINK:prepay]",
        ):
            with self.subTest(text=text):
                result = parse_legacy_response(text)
                self.assertFalse(result.valid)
                self.assertEqual(result.control, {})
                self.assertNotRegex(result.reply_text, r"\[[A-Za-z][^\]]*\]")

    def test_legacy_control_shaped_brackets_are_stripped_even_when_invalid(self):
        from management.services.ig_response_control import parse_legacy_response

        result = parse_legacy_response(
            "Пояснення [unknown command] і [manager:yes], але [приклад] лишається"
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.control, {})
        self.assertNotIn("[unknown command]", result.reply_text)
        self.assertNotIn("[manager:yes]", result.reply_text)
        self.assertIn("[приклад]", result.reply_text)

    def test_obfuscated_control_prefixes_fail_closed_and_never_leak(self):
        from management.services.ig_response_control import (
            parse_legacy_response,
            parse_structured_response,
        )

        for token in (
            "[ MANAGER]",
            "[\tPAYLINK:full]",
            "[\u200bMANAGER]",
            "[\u2060ORDER]",
            "[ MANAGER",
        ):
            with self.subTest(token=repr(token)):
                legacy = parse_legacy_response(f"Готово {token}")
                structured = parse_structured_response({
                    "reply_text": f"Готово {token}",
                    "controls": [],
                })
                for result in (legacy, structured):
                    self.assertFalse(result.valid)
                    self.assertEqual(result.control, {})
                    self.assertEqual(result.reply_text, "Готово")

    def test_legacy_repeated_items_are_allowed_but_singleton_conflicts_are_not(self):
        from management.services.ig_response_control import parse_legacy_response

        result = parse_legacy_response(
            "Варіанти [ITEM:12|1|M|classic|81] [ITEM:13|1|S|oversize|82] "
            "[OPTION:material=cotton] [OPTION:lining=fleece]"
        )

        self.assertTrue(result.valid)
        self.assertEqual(len(result.control["items"]), 2)
        self.assertEqual(result.control["options"], ["material=cotton", "lining=fleece"])

    def test_worker_normalization_converges_structured_and_legacy_replies(self):
        from management.services.instagram_bot import _normalize_generated_reply

        structured = {
            "reply_text": "Покажу ціну.",
            "controls": [{"kind": "stage", "value": "qualifying"}],
        }
        legacy = "Покажу ціну. [STAGE:qualifying]"

        self.assertEqual(
            _normalize_generated_reply(structured),
            ("Покажу ціну.", {"stage": "qualifying"}, True),
        )
        self.assertEqual(
            _normalize_generated_reply(legacy),
            ("Покажу ціну.", {"stage": "qualifying"}, True),
        )

    def test_worker_normalization_discards_invalid_controls_before_effects(self):
        from management.services.instagram_bot import _normalize_generated_reply

        text, control, valid = _normalize_generated_reply(
            "Оплата [MANAGR] [PAYLINK:false]"
        )

        self.assertEqual(text, "Оплата")
        self.assertEqual(control, {})
        self.assertFalse(valid)

    def test_worker_normalization_discards_invalid_structured_reply_text(self):
        from management.services.instagram_bot import _normalize_generated_reply

        text, control, valid = _normalize_generated_reply({
            "reply_text": "x" * 4001,
            "controls": [],
        })

        self.assertEqual(text, "")
        self.assertEqual(control, {})
        self.assertFalse(valid)

    def test_worker_normalization_rejects_invalid_reply_text_for_delivery(self):
        from management.services.instagram_bot import _normalize_generated_reply

        for payload in (
            {"reply_text": "x" * 4001, "controls": []},
            {"reply_text": {"secret": "leak"}, "controls": []},
        ):
            with self.subTest(payload_type=type(payload["reply_text"]).__name__):
                self.assertEqual(
                    _normalize_generated_reply(payload),
                    ("", {}, False),
                )


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
                "color_variant_id": self.variant.pk,
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
                "color_variant_id": self.variant.pk,
            }
        }
        self.client_row.save(update_fields=["current_size", "sales_context", "updated_at"])

        state = checkout_readiness(self.client_row)

        self.assertIn("material", state["options"]["missing"])
        self.assertIn("option:material", state["missing"])
        self.assertFalse(state["can_issue_link"])

    @patch("product_catalog.services.product_option_context", side_effect=RuntimeError("catalog unavailable"))
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
        from product_catalog.models import SizeGrid, VariantSizeRule
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

    def test_commerce_turn_note_exposes_bounded_facts_before_gemini(self):
        from management.services import instagram_bot as bot

        note = bot.commerce_turn_note(
            self.client_row,
            "black класичну M, без принта сзади, хочу оплатить",
        )

        self.assertIn("color=black", note)
        self.assertIn("fit=classic", note)
        self.assertIn("size=M", note)
        self.assertIn("back_decoration=none", note)
        self.assertIn("checkout_requested=true", note)

    def test_commerce_turn_note_does_not_turn_size_guide_into_a_payable_fit(self):
        from management.services import instagram_bot as bot

        note = bot.commerce_turn_note(
            self.client_row,
            "Покажи на оверсайз размерную сетку",
        )

        self.assertIn("info=size_guide:oversize", note)
        self.assertNotIn("fit=oversize", note)

    def test_exact_turn_reference_pins_product_before_model_generation(self):
        from management.services import instagram_bot as bot

        self.client_row.current_product = self.other
        self.client_row.save(update_fields=["current_product", "updated_at"])

        request = bot.apply_deterministic_commerce_turn(
            self.client_row,
            f"https://twocomms.shop/product/{self.classic.slug}/ Вот этот",
        )

        self.assertEqual(request.exact_product_id, self.classic.pk)
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.current_product_id, self.classic.pk)


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
        self.assertFalse(_is_configuration_gap({"error": "insufficient_stock"}))
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
        from product_catalog.models import VariantSizeRule

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
                "color_variant_id": self.variant.pk,
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
        self.client_row.username = "private_size_customer"
        self.client_row.save(update_fields=["username", "updated_at"])

        self.assertTrue(bot.notify_size_gap(self.client_row))
        self.assertFalse(bot.notify_size_gap(self.client_row))
        self.assertEqual(mock_notify.call_count, 1)
        self.client_row.refresh_from_db()
        gap = self.client_row.sales_context["_stock_gap"]
        self.assertEqual(gap["product_id"], self.product.pk)
        self.assertEqual(gap["variant_id"], self.variant.pk)
        self.assertEqual(gap["fit_code"], "classic")
        self.assertEqual(gap["option_values"], {"fit": "classic"})
        message = mock_notify.call_args.args[0]
        self.assertNotIn(self.client_row.igsid, message)
        self.assertNotIn(self.client_row.username, message)
        self.assertIn(f"Клієнт ID: {self.client_row.pk}", message)
        self.assertIn(f"?client={self.client_row.pk}", message)

    @patch("management.services.instagram_bot.notify_manager")
    def test_available_size_does_not_bother_the_manager(self, mock_notify):
        from django.core.cache import cache
        from management.services import instagram_bot as bot

        cache.clear()
        self.client_row.current_size = "L"
        self.client_row.save(update_fields=["current_size", "updated_at"])

        self.assertFalse(bot.notify_size_gap(self.client_row))
        mock_notify.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    def test_committed_restock_materializes_only_the_exact_variant_selection(self, _notify):
        from django.core.cache import cache
        from product_catalog.models import VariantSizeRule
        from management.services import instagram_bot as bot
        from management.services.bot_followups import (
            event_followup_fact_guard,
            materialize_restock_inventory_event,
        )

        cache.clear()
        self.assertTrue(bot.notify_size_gap(self.client_row))
        rule = VariantSizeRule.objects.get(
            variant=self.variant, fit_code="classic", size="M"
        )
        rule.is_enabled = True
        rule.stock = 1
        rule.save(update_fields=["is_enabled", "stock", "updated_at"])

        self.assertEqual(
            materialize_restock_inventory_event(
                product_id=self.product.pk,
                variant_id=self.variant.pk,
                size="M",
                fit_code="classic",
                option_values={"fit": "classic"},
                source_revision="test-restock-1",
            ),
            1,
        )
        task = IgFollowUpTask.objects.get(reason="restock_wait", level=1)
        self.assertEqual(task.trigger, IgFollowUpTask.Trigger.EVENT)
        self.assertEqual(task.event_payload["variant_id"], self.variant.pk)
        self.assertEqual(task.event_payload["fit_code"], "classic")
        selected = IgClient.objects.get(pk=self.client_row.pk)
        self.assertEqual(selected.current_product_id, self.product.pk)
        self.assertEqual(selected.current_size, "M")
        self.assertEqual(
            selected.sales_context["assisted_checkout_selection"]["color_variant_id"],
            self.variant.pk,
        )
        allowed, reason = event_followup_fact_guard(task)
        self.assertTrue(allowed, reason)

    @patch("management.services.instagram_bot.notify_manager")
    def test_product_catalog_restock_revision_allows_same_inventory_and_rejects_later_change(
        self, _notify
    ):
        from django.core.cache import cache
        from product_catalog.models import VariantSizeRule
        from management.services import instagram_bot as bot
        from management.services.bot_followups import (
            event_followup_fact_guard,
            materialize_restock_inventory_event,
            variant_inventory_revision,
        )

        cache.clear()
        self.assertTrue(bot.notify_size_gap(self.client_row))
        rule = VariantSizeRule.objects.get(
            variant=self.variant, fit_code="classic", size="M"
        )
        rule.is_enabled = True
        rule.stock = 1
        rule.save(update_fields=["is_enabled", "stock", "updated_at"])
        source_revision = f"product_catalog:{variant_inventory_revision(self.variant.pk)}"

        self.assertEqual(
            materialize_restock_inventory_event(
                product_id=self.product.pk,
                variant_id=self.variant.pk,
                size="M",
                fit_code="classic",
                option_values={"fit": "classic"},
                source_revision=source_revision,
            ),
            1,
        )
        task = IgFollowUpTask.objects.get(reason="restock_wait", level=1)
        allowed, reason = event_followup_fact_guard(task)
        self.assertTrue(allowed, reason)

        rule.stock = 2
        rule.save(update_fields=["stock", "updated_at"])
        allowed, reason = event_followup_fact_guard(task)
        self.assertFalse(allowed)
        self.assertEqual(reason, "restock_revision_changed")

    @patch("management.services.instagram_bot.notify_manager")
    def test_restock_for_another_variant_never_materializes_the_waiting_client(self, _notify):
        from django.core.cache import cache
        from productcolors.models import Color, ProductColorVariant
        from management.services import instagram_bot as bot
        from management.services.bot_followups import materialize_restock_inventory_event

        cache.clear()
        self.assertTrue(bot.notify_size_gap(self.client_row))
        other = ProductColorVariant.objects.create(
            product=self.product,
            color=Color.objects.create(name="Білий", primary_hex="#eeeeee"),
            stock=1,
        )

        self.assertEqual(
            materialize_restock_inventory_event(
                product_id=self.product.pk,
                variant_id=other.pk,
                size="M",
                fit_code="classic",
                option_values={"fit": "classic"},
                source_revision="test-restock-other",
            ),
            0,
        )
        self.assertFalse(IgFollowUpTask.objects.filter(reason="restock_wait").exists())


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
    """Elapsed time and new inbound never release manager ownership."""

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

    def _enqueue_while_paused(self, mid):
        from management.models import IgClient, InstagramBotMessage, InstagramBotSettings
        from management.services import instagram_bot as bot

        settings_obj = InstagramBotSettings.load()
        settings_obj.is_enabled = True
        settings_obj.allowed_senders = ""
        settings_obj.save(update_fields=["is_enabled", "allowed_senders"])
        epoch = self.client_row.reply_permission_epoch
        self.assertTrue(
            bot.enqueue_inbound(
                settings_obj,
                sender_id=self.client_row.igsid,
                text="Підкажіть, будь ласка, ціну?",
                mid=mid,
            )
        )
        message = InstagramBotMessage.objects.get(mid=mid)
        fresh = IgClient.objects.get(pk=self.client_row.pk)
        self.assertEqual(message.status, InstagramBotMessage.Status.DONE)
        self.assertTrue(fresh.manager_takeover)
        self.assertTrue(fresh.bot_paused)
        self.assertEqual(fresh.paused_reason, "manager_takeover")
        self.assertEqual(fresh.reply_permission_epoch, epoch)

    @patch("management.services.instagram_bot.notify_manager")
    def test_long_silent_takeover_is_not_released(self, mock_notify):
        self._put_in_takeover(30)

        self._enqueue_while_paused("manual-only-takeover-30h")

        mock_notify.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    def test_active_manager_conversation_is_not_interrupted(self, mock_notify):
        self._put_in_takeover(2)

        self._enqueue_while_paused("manual-only-takeover-2h")

        mock_notify.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    def test_opted_out_client_is_never_auto_resumed(self, mock_notify):
        self._put_in_takeover(48)
        self.client_row.opted_out_at = timezone.now() - timezone.timedelta(hours=40)
        self.client_row.save(update_fields=["opted_out_at", "updated_at"])

        self._enqueue_while_paused("manual-only-takeover-optout")

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

    def test_shown_products_reject_malformed_provider_message_ids(self):
        from management.services import instagram_bot as bot
        from management.services.ig_catalog_media import (
            CatalogMediaDelivery,
            CatalogMediaDeliveryState,
        )

        selection, _ = self._selection_and_delivery()
        delivery = CatalogMediaDelivery(
            CatalogMediaDeliveryState.SENT,
            sent_count=2,
            attempted_count=2,
            provider_message_ids=(123, "x" * 256),
        )

        bot.record_shown_products(
            self.client_row,
            self.client_row.igsid,
            selection,
            delivery,
        )

        rows = list(
            InstagramBotMessage.objects.filter(
                client=self.client_row,
                source="catalog_media",
            ).order_by("id")
        )
        self.assertEqual(
            [row.provider_message_id for row in rows],
            ["", ""],
        )

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


class StructuredPromptProtocolTests(TestCase):
    def test_migration_default_matches_model_default_byte_for_byte(self):
        import importlib

        from django.db import migrations
        from management.models import DEFAULT_BOT_SYSTEM_PROMPT

        migration = importlib.import_module(
            "management.migrations.0161_optional_follow_cta_prompt"
        )
        alter = next(
            operation
            for operation in migration.Migration.operations
            if isinstance(operation, migrations.AlterField)
            and operation.model_name == "instagrambotsettings"
            and operation.name == "system_prompt"
        )

        self.assertEqual(alter.field.default, DEFAULT_BOT_SYSTEM_PROMPT)

    def test_default_prompt_does_not_keep_legacy_direct_payment_link_promise(self):
        from management.models import DEFAULT_BOT_SYSTEM_PROMPT

        self.assertNotIn(
            "я сформую посилання на оплату сюди",
            DEFAULT_BOT_SYSTEM_PROMPT,
        )
        self.assertIn(
            "персональну пропозицію TwoComms",
            DEFAULT_BOT_SYSTEM_PROMPT,
        )

    def test_default_prompt_has_no_legacy_control_protocol(self):
        from management.models import DEFAULT_BOT_SYSTEM_PROMPT

        for marker in ("[PAYLINK", "[PAYMENT", "[STAGE", "[MANAGER]", "[ORDER]", "[SPAM]"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, DEFAULT_BOT_SYSTEM_PROMPT)
        self.assertIn("JSON", DEFAULT_BOT_SYSTEM_PROMPT)

    def test_runtime_protocol_describes_structured_controls_once(self):
        from management.services.instagram_bot import PAYMENT_PROTOCOL_NOTE

        self.assertIn("reply_text", PAYMENT_PROTOCOL_NOTE)
        self.assertIn("controls", PAYMENT_PROTOCOL_NOTE)
        self.assertNotIn("[PAYLINK", PAYMENT_PROTOCOL_NOTE)

    def test_existing_custom_prompt_gets_runtime_hard_stage_guard(self):
        from types import SimpleNamespace

        from management.services.instagram_bot import assemble_system_instruction

        prompt = assemble_system_instruction(SimpleNamespace(
            system_prompt="CUSTOM OPERATOR PROMPT",
            knowledge_base="",
        ))

        self.assertIn("CUSTOM OPERATOR PROMPT", prompt)
        self.assertIn(
            "Не заявляй і не пропонуй paid, order_created або done",
            prompt,
        )

    def test_prompt_cleanup_preserves_operator_text_and_is_idempotent(self):
        import importlib

        migration = importlib.import_module(
            "management.migrations.0151_remove_duplicate_ig_payment_protocol"
        )
        prompt = (
            "CUSTOM PREFIX\n\n"
            "СЛУЖБОВІ ТЕГИ (клієнт їх НЕ бачить — система вирізає; додавай у САМОМУ КІНЦІ):\n"
            "• [MANAGER] — коли потрібен живий менеджер.\n"
            "CUSTOM SUFFIX"
        )

        cleaned = migration._remove_legacy_protocol_fragments(prompt)

        self.assertIn("CUSTOM PREFIX", cleaned)
        self.assertIn("CUSTOM SUFFIX", cleaned)
        self.assertNotIn("[MANAGER]", cleaned)
        self.assertEqual(cleaned, migration._remove_legacy_protocol_fragments(cleaned))
        self.assertEqual(
            migration._remove_legacy_protocol_fragments("operator-only prompt"),
            "operator-only prompt",
        )

    def test_prompt_cleanup_preserves_custom_bullet_after_known_legacy_line(self):
        import importlib

        migration = importlib.import_module(
            "management.migrations.0151_remove_duplicate_ig_payment_protocol"
        )
        custom_bullet = "• Завжди уточнюй, чи потрібне подарункове пакування."
        prompt = (
            "СЛУЖБОВІ ТЕГИ (клієнт їх НЕ бачить — система вирізає; додавай у САМОМУ КІНЦІ):\n"
            "• [MANAGER] — коли потрібен живий менеджер.\n"
            f"{custom_bullet}\n"
            "CUSTOM SUFFIX"
        )

        cleaned = migration._remove_legacy_protocol_fragments(prompt)

        self.assertNotIn("[MANAGER]", cleaned)
        self.assertIn(custom_bullet, cleaned)
        self.assertIn("CUSTOM SUFFIX", cleaned)

    def test_prompt_cleanup_removes_legacy_payment_promise_and_keeps_neighbors(self):
        import importlib

        migration = importlib.import_module(
            "management.migrations.0151_remove_duplicate_ig_payment_protocol"
        )
        previous_bullet = "• Не вигадуй ціни або залишки."
        legacy_payment = "• Оплата: на сайті або я сформую посилання на оплату сюди."
        next_bullet = "• Доставка Новою Поштою, зазвичай 1-3 дні."
        prompt = "\n".join((
            "CUSTOM PREFIX",
            previous_bullet,
            legacy_payment,
            next_bullet,
            "CUSTOM SUFFIX",
        ))

        cleaned = migration._remove_legacy_protocol_fragments(prompt)

        self.assertNotIn(legacy_payment, cleaned)
        self.assertIn(previous_bullet, cleaned)
        self.assertIn(next_bullet, cleaned)
        self.assertIn("CUSTOM PREFIX", cleaned)
        self.assertIn("CUSTOM SUFFIX", cleaned)
        self.assertEqual(cleaned, migration._remove_legacy_protocol_fragments(cleaned))

    def test_prompt_cleanup_removes_legacy_payment_paragraph_and_keeps_neighbors(self):
        import importlib

        migration = importlib.import_module(
            "management.migrations.0151_remove_duplicate_ig_payment_protocol"
        )
        legacy_payment = (
            "Способи оплати — на сайті або я сформую посилання на оплату сюди. "
            "Згадай передоплату коротко (див. нижче)."
        )
        prompt = "\n".join((
            "CUSTOM PREFIX",
            legacy_payment,
            "CUSTOM SUFFIX",
        ))

        cleaned = migration._remove_legacy_protocol_fragments(prompt)

        self.assertNotIn(legacy_payment, cleaned)
        self.assertIn("CUSTOM PREFIX", cleaned)
        self.assertIn("CUSTOM SUFFIX", cleaned)
        self.assertEqual(cleaned, migration._remove_legacy_protocol_fragments(cleaned))

    def test_prompt_cleanup_removes_all_known_historical_protocol_variants(self):
        import importlib

        migration = importlib.import_module(
            "management.migrations.0151_remove_duplicate_ig_payment_protocol"
        )
        historical_fragments = (
            "• [STAGE:x] — поточний етап клієнта. x із: new, qualifying, "
            "product_matched, checkout, payment_pending, paid, order_created, done, "
            "lead_manager, cold.",
            "• [PAYLINK:full] або [PAYLINK:prepay] — коли клієнт підтвердив товар і "
            "готовий платити (повна оплата / передоплата 200). Система сформує і "
            "надішле посилання.",
            "• Передоплата 200 грн (решта — накладеним при отриманні) можлива; "
            "згадуй коротко, деталі (навіщо передоплата) пояснюй лише якщо запитають.",
        )
        prompt = "\n".join(("CUSTOM PREFIX", *historical_fragments, "CUSTOM SUFFIX"))

        cleaned = migration._remove_legacy_protocol_fragments(prompt)

        for fragment in historical_fragments:
            self.assertNotIn(fragment, cleaned)
        self.assertIn("CUSTOM PREFIX", cleaned)
        self.assertIn("CUSTOM SUFFIX", cleaned)
        self.assertEqual(cleaned, migration._remove_legacy_protocol_fragments(cleaned))
