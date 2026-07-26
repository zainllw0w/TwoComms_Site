"""Pure contracts for image-aware Instagram workflow and payment safety."""
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings


class MediaSemanticsTests(SimpleTestCase):
    def test_product_question_image_is_interest_not_receipt(self):
        from management.services.ig_payment_review import classify_media_items

        items = classify_media_items(
            "Який тут розмір і колір?",
            [{"url": "https://cdn.example/post.jpg", "type": "image"}],
        )
        self.assertEqual(items[0]["role"], "product")
        self.assertEqual(items[0]["intent"], "question")
        self.assertFalse(items[0]["payment_evidence"])

    def test_purchase_image_is_actionable_product_candidate(self):
        from management.services.ig_payment_review import classify_media_items

        items = classify_media_items(
            "Хочу саме таку, оформлюйте",
            [{"url": "https://cdn.example/photo.jpg", "type": "image"}],
        )
        self.assertEqual(items[0]["role"], "product")
        self.assertEqual(items[0]["intent"], "purchase_candidate")
        self.assertTrue(items[0]["actionable"])

    def test_product_reference_after_order_is_actionable(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {
                "id": 233,
                "role": "user",
                "text": "Мені потрібно 2 футболки: 1. Базова S 2. Оверсайз XS. Принт однаковий",
            },
            {"id": 234, "role": "user", "text": "Почекаємо)"},
            {
                "id": 235,
                "role": "user",
                "text": "Принт ось цей",
                "attachments": '["https://cdn.example/product.jpg"]',
            },
            {"id": 236, "role": "manager", "text": "Оплата на IBAN, надішліть чек"},
            {
                "id": 237,
                "role": "user",
                "text": "Оплатила, ось чек",
                "attachments": '["https://cdn.example/receipt.jpg"]',
            },
        ])

        product_media = [item for item in result["media"] if item.get("url") == "https://cdn.example/product.jpg"]
        self.assertEqual(len(product_media), 1)
        self.assertEqual(product_media[0]["intent"], "purchase_candidate")
        self.assertTrue(product_media[0]["actionable"])
        self.assertTrue(product_media[0]["catalog_match_allowed"])

    def test_product_media_attached_to_order_lines_is_actionable(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {
                "id": 233,
                "role": "user",
                "text": "Мені потрібно 2 футболки: 1. Базова S 2. Оверсайз XS",
                "media": [{"url": "https://cdn.example/order-product.jpg", "type": "ig_post"}],
            },
        ])

        product_media = result["media"]
        self.assertEqual(len(product_media), 1)
        self.assertEqual(product_media[0]["intent"], "purchase_candidate")
        self.assertTrue(product_media[0]["actionable"])

    def test_custom_reference_is_not_catalog_product(self):
        from management.services.ig_payment_review import classify_media_items

        items = classify_media_items(
            "Можете зробити такий принт на футболці?",
            [{"url": "https://cdn.example/reference.jpg", "type": "image"}],
        )
        self.assertEqual(items[0]["role"], "custom_reference")
        self.assertEqual(items[0]["intent"], "custom_print_request")
        self.assertFalse(items[0]["catalog_match_allowed"])

    def test_receipt_wins_over_product_language_in_payment_context(self):
        from management.services.ig_payment_review import classify_media_items

        items = classify_media_items(
            "Оплатила, ось чек",
            [{"url": "https://cdn.example/receipt.jpg", "type": "image"}],
            payment_context=True,
        )
        self.assertEqual(items[0]["role"], "receipt")
        self.assertEqual(items[0]["intent"], "payment_evidence")
        self.assertTrue(items[0]["payment_evidence"])
        self.assertFalse(items[0]["catalog_match_allowed"])

    def test_product_question_stays_product_after_earlier_payment_context(self):
        from management.services.ig_payment_review import classify_media_items

        items = classify_media_items(
            "Підкажіть, який тут розмір?",
            [{"url": "https://cdn.example/product.jpg", "type": "image"}],
            payment_context=True,
        )
        self.assertEqual(items[0]["role"], "product")
        self.assertEqual(items[0]["intent"], "question")

    def test_unrelated_image_stays_unresolved(self):
        from management.services.ig_payment_review import classify_media_items

        items = classify_media_items(
            "",
            [{"url": "https://cdn.example/random.jpg", "type": "image"}],
        )
        self.assertEqual(items[0]["role"], "other")
        self.assertEqual(items[0]["intent"], "unknown")
        self.assertTrue(items[0]["uncertain"])

    def test_manager_payment_instruction_does_not_turn_product_question_into_receipt(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {"id": 1, "role": "manager", "text": "Оплата на IBAN, після цього надішліть чек.", "attachments": ""},
            {"id": 2, "role": "user", "text": "Який тут розмір?", "attachments": '["https://cdn.example/product.jpg"]'},
        ])
        self.assertFalse(result["needs_review"])
        self.assertEqual([item["role"] for item in result["media"]], ["product"])
        self.assertFalse(any(item["role"] == "receipt" for item in result["media"]))

    def test_old_payment_context_does_not_turn_later_generic_image_into_receipt(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {"id": 1, "role": "user", "text": "Беру оверсайз XS"},
            {"id": 2, "role": "manager", "text": "Оплата на IBAN, сума 790 грн. Надішліть чек."},
            {"id": 3, "role": "user", "text": "Дякую, ще подумаю"},
            {"id": 4, "role": "user", "text": "", "attachments": '["https://cdn.example/unrelated.jpg"]'},
        ])

        self.assertFalse(result["needs_review"])
        self.assertEqual(result["media"][-1]["role"], "other")

    def test_image_immediately_after_receipt_request_is_payment_evidence(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {"id": 1, "role": "user", "text": "Беру оверсайз XS"},
            {"id": 2, "role": "manager", "text": "Оплата на IBAN, сума 790 грн. Надішліть чек."},
            {"id": 3, "role": "user", "text": "", "attachments": '["https://cdn.example/receipt.jpg"]'},
        ])

        self.assertTrue(result["needs_review"])
        self.assertEqual(result["media"][-1]["role"], "payment_candidate")

    @patch("management.services.instagram_bot.download_image", return_value=("image/jpeg", b"image"))
    @patch("management.services.bot_vision.classify_media_roles", return_value=[{
        "source_image_index": 0,
        "role": "product",
        "confidence": 0.96,
        "reason": "скриншот картки товару",
    }])
    def test_vision_can_reclassify_payment_candidate_as_product(self, classify, _download):
        from management.services.ig_payment_review import _resolve_payment_media_candidates

        media = [{
            "url": "https://cdn.example/unknown.jpg",
            "role": "payment_candidate",
            "intent": "payment_evidence_candidate",
            "payment_evidence": True,
            "catalog_match_allowed": False,
        }]
        resolved = _resolve_payment_media_candidates(media)

        self.assertEqual(resolved[0]["role"], "product")
        self.assertEqual(resolved[0]["intent"], "interest")
        self.assertFalse(resolved[0]["payment_evidence"])
        self.assertFalse(resolved[0]["catalog_match_allowed"])
        classify.assert_called_once_with([("image/jpeg", b"image")])

    def test_vision_product_result_removes_image_only_payment_evidence(self):
        from management.services.ig_payment_review import (
            _reconcile_payment_evidence_after_media_resolution,
            extract_payment_review_evidence,
        )

        extracted = extract_payment_review_evidence([
            {"id": 1, "role": "user", "text": "Беру базову S"},
            {"id": 2, "role": "manager", "text": "Оплата на IBAN, надішліть чек"},
            {"id": 3, "role": "user", "text": "", "attachments": '["https://cdn.example/product.jpg"]'},
        ])
        self.assertTrue(extracted["needs_review"])

        reconciled = _reconcile_payment_evidence_after_media_resolution(
            extracted,
            [{"url": "https://cdn.example/product.jpg", "message_id": 3, "role": "product"}],
        )

        self.assertFalse(reconciled["needs_review"])
        self.assertEqual(reconciled["message_ids"], [])
        self.assertEqual(reconciled["evidence"], [])

    def test_explicit_payment_statement_survives_product_image_reclassification(self):
        from management.services.ig_payment_review import (
            _reconcile_payment_evidence_after_media_resolution,
            extract_payment_review_evidence,
        )

        extracted = extract_payment_review_evidence([
            {
                "id": 3,
                "role": "user",
                "text": "Я вже оплатила, перевірте, будь ласка",
                "attachments": '["https://cdn.example/product.jpg"]',
            },
        ])
        reconciled = _reconcile_payment_evidence_after_media_resolution(
            extracted,
            [{"url": "https://cdn.example/product.jpg", "message_id": 3, "role": "product"}],
        )

        self.assertTrue(reconciled["needs_review"])
        self.assertEqual(reconciled["message_ids"], [3])

    @patch("management.services.instagram_bot.download_image", return_value=("image/jpeg", b"image"))
    @patch("management.services.bot_vision.classify_media_roles", return_value=[{
        "source_image_index": 0,
        "role": "receipt",
        "confidence": 0.4,
        "reason": "нечітко",
    }])
    def test_low_confidence_vision_keeps_payment_candidate_unresolved(self, _classify, _download):
        from management.services.ig_payment_review import _resolve_payment_media_candidates

        media = [{"url": "https://cdn.example/unknown.jpg", "role": "payment_candidate"}]
        resolved = _resolve_payment_media_candidates(media)

        self.assertEqual(resolved[0]["role"], "payment_candidate")
        self.assertTrue(resolved[0]["uncertain"])


class ReplyMediaRecoveryTests(SimpleTestCase):
    @override_settings(SITE_BASE_URL="https://twocomms.shop")
    def test_relative_persisted_media_url_is_absolutized_with_original_fallback(self):
        from management.services.instagram_bot import _telegram_media_url_candidates

        urls = _telegram_media_url_candidates({
            "local_url": "/media/ig_payment_reviews/evidence.jpg",
            "url": "https://lookaside.example/original.jpg",
        })
        self.assertEqual(urls, [
            "https://twocomms.shop/media/ig_payment_reviews/evidence.jpg",
            "https://lookaside.example/original.jpg",
        ])

    @patch("management.services.ig_payment_review._augment_messages_with_raw_media")
    def test_customer_worker_can_recover_raw_product_media(self, augment):
        from management.services import instagram_bot

        augment.return_value = [{
            "id": 10,
            "mid": "normalized-mid",
            "text": "Хочу таку",
            "attachments": '["https://cdn.example/post.jpg"]',
            "media": [{"url": "https://cdn.example/post.jpg", "type": "ig_post"}],
        }]
        row = SimpleNamespace(
            pk=10,
            mid="normalized-mid",
            text="Хочу таку",
            attachments="",
            role="user",
            client=SimpleNamespace(igsid="ig-1"),
        )
        recovered = instagram_bot._recover_current_message_media(row)
        self.assertEqual(recovered[0]["type"], "ig_post")
        self.assertIn("post.jpg", recovered[0]["url"])
        augment.assert_called_once()

    def test_receipt_media_never_reaches_catalog_matcher(self):
        from management.services.instagram_bot import _catalog_match_media

        media = [{"url": "https://cdn.example/receipt.jpg", "role": "receipt", "catalog_match_allowed": False}]
        self.assertEqual(_catalog_match_media(media), [])

    def test_only_explicit_product_media_reaches_catalog_matcher(self):
        from management.services.instagram_bot import _catalog_match_media

        product = {"url": "https://cdn.example/product.jpg", "role": "product", "catalog_match_allowed": True}
        receipt = {"url": "https://cdn.example/receipt.jpg", "role": "receipt", "catalog_match_allowed": False}
        self.assertEqual(_catalog_match_media([receipt, product]), [product])

    def test_echo_media_metadata_is_bounded_and_preserves_type(self):
        from management.services.instagram_bot import _echo_media_items

        items = _echo_media_items({
            "attachments": [
                {"type": "ig_post", "payload": {"url": "https://cdn.example/post.jpg"}},
                {"type": "image", "payload": {"url": "https://cdn.example/extra.jpg"}},
            ],
        })
        self.assertEqual(items[0]["type"], "ig_post")
        self.assertEqual(len(items), 2)


class PaymentLinkGateTests(SimpleTestCase):
    def test_product_question_cannot_open_payment_link(self):
        from management.services.instagram_bot import payment_link_allowed

        client = SimpleNamespace(
            current_product_id=111,
            intent="product",
            stage="product_matched",
            buying_readiness=20,
        )
        self.assertFalse(payment_link_allowed(client, {"paylink": "full", "product": 111}, "Який розмір?"))

    def test_explicit_purchase_candidate_can_open_payment_link(self):
        from management.services.instagram_bot import payment_link_allowed

        client = SimpleNamespace(
            current_product_id=111,
            intent="product",
            stage="product_matched",
            buying_readiness=20,
        )
        self.assertTrue(payment_link_allowed(client, {"paylink": "full", "product": 111}, "Так, хочу, оформлюйте"))

    def test_paid_client_cannot_receive_a_second_invoice(self):
        from management.services.instagram_bot import payment_link_allowed

        client = SimpleNamespace(
            current_product_id=111,
            intent="payment",
            stage="paid",
            buying_readiness=100,
        )
        self.assertFalse(payment_link_allowed(client, {"paylink": "full", "product": 111}, "Так, хочу"))

    @patch("management.services.bot_payment_truth.client_has_verified_payment", return_value=True)
    def test_verified_payment_blocks_invoice_even_when_stage_is_stale(self, _verified):
        from management.services.instagram_bot import payment_link_allowed

        client = SimpleNamespace(
            pk=1,
            current_product_id=111,
            intent="payment",
            stage="checkout",
            buying_readiness=80,
        )
        self.assertFalse(payment_link_allowed(client, {"paylink": "full", "product": 111}, "Так, хочу"))

    def test_boolean_product_tag_is_not_a_product_id(self):
        from management.services.instagram_bot import payment_link_allowed

        client = SimpleNamespace(
            current_product_id=None,
            intent="payment",
            stage="checkout",
            buying_readiness=80,
        )
        self.assertFalse(payment_link_allowed(client, {"paylink": "full", "product": True}, "Так, хочу"))

    def test_only_purchase_candidate_media_can_pin_a_product(self):
        from management.services.instagram_bot import _should_pin_product_media

        self.assertFalse(_should_pin_product_media([
            {"role": "product", "intent": "question", "catalog_match_allowed": True},
        ]))
        self.assertTrue(_should_pin_product_media([
            {"role": "product", "intent": "purchase_candidate", "catalog_match_allowed": True},
        ]))

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.bot_orders.create_deal_and_link")
    @patch("management.services.instagram_bot._conversation_negotiated_price", return_value=None)
    def test_unverified_price_tag_fails_closed_before_provider_invoice(self, _price, create_link, notify):
        from management.services.instagram_bot import finalize_paylink

        client = SimpleNamespace(
            current_product_id=111,
            intent="payment",
            stage="checkout",
            buying_readiness=80,
            username="client",
            display_name="",
            set_stage=lambda *args, **kwargs: None,
        )
        reply = "Так, хочу. Ось посилання на оплату"
        result = finalize_paylink(
            reply,
            {"paylink": "full", "product": 111, "price": "500"},
            client,
            "ig-1",
        )
        create_link.assert_not_called()
        notify.assert_called_once()
        self.assertNotIn("посилання на оплат", result.casefold())

    @patch("management.services.bot_orders._validated_negotiated_price", return_value=Decimal("790.00"))
    def test_omitted_price_tag_still_uses_validated_conversation_offer(self, validate):
        from management.services.instagram_bot import _conversation_negotiated_price

        client = SimpleNamespace(pk=1)
        self.assertEqual(_conversation_negotiated_price(client, {}), Decimal("790.00"))
        validate.assert_called_once_with(client, None)


class NegotiatedPriceEvidenceTests(SimpleTestCase):
    def test_customer_cannot_self_authorize_an_arbitrary_price(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [SimpleNamespace(role="user", text="Так, оформлюйте за 20 грн")]
        self.assertIsNone(_accepted_conversation_price(rows))

    def test_unrelated_later_yes_does_not_accept_old_offer(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [
            SimpleNamespace(role="manager", text="Ціна 790 грн"),
            SimpleNamespace(role="user", text="Який склад?"),
            SimpleNamespace(role="manager", text="Бавовна. Підходить?"),
            SimpleNamespace(role="user", text="Так"),
        ]
        self.assertIsNone(_accepted_conversation_price(rows))

    def test_product_switch_invalidates_an_earlier_accepted_price(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [
            SimpleNamespace(role="manager", text="Ціна худі 790 грн"),
            SimpleNamespace(role="user", text="Так, оформлюйте"),
            SimpleNamespace(role="user", text="Ні, хочу іншу футболку"),
        ]
        self.assertIsNone(_accepted_conversation_price(rows))

    def test_prepayment_receipt_amount_cannot_replace_accepted_order_price(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [
            SimpleNamespace(role="manager", text="Ціна футболки зі знижкою 790 грн"),
            SimpleNamespace(role="user", text="Так, оформлюйте"),
            SimpleNamespace(role="user", text="Оплатила передоплату 200 грн, ось чек"),
        ]
        self.assertEqual(_accepted_conversation_price(rows), Decimal("790.00"))
        self.assertIsNone(_accepted_conversation_price(rows, requested=Decimal("200")))

    def test_later_offer_supersedes_earlier_accepted_amount(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [
            SimpleNamespace(role="manager", text="Домовились, ціна 700 грн"),
            SimpleNamespace(role="user", text="Так"),
            SimpleNamespace(role="manager", text="Актуальна сума разом 900 грн"),
            SimpleNamespace(role="user", text="Добре, оформлюйте"),
        ]
        self.assertEqual(_accepted_conversation_price(rows), Decimal("900.00"))
        self.assertIsNone(_accepted_conversation_price(rows, requested=Decimal("700")))

    def test_model_cannot_accept_customer_counteroffer(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [
            SimpleNamespace(role="user", text="Можна за 20 грн?"),
            SimpleNamespace(role="model", text="Так, оформлюємо"),
        ]
        self.assertIsNone(_accepted_conversation_price(rows))

    def test_model_cannot_originate_price_override(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [
            SimpleNamespace(role="assistant", text="Можу зробити за 20 грн"),
            SimpleNamespace(role="user", text="Так, оформлюйте"),
        ]
        self.assertIsNone(_accepted_conversation_price(rows))

    def test_manager_price_for_same_product_remains_authoritative(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [
            SimpleNamespace(role="manager", text="Можу оформити цю футболку за 790 грн"),
            SimpleNamespace(role="user", text="Так, оформлюйте"),
        ]
        product = SimpleNamespace(pk=111, title="Футболка Харків", slug="kharkiv")
        self.assertEqual(_accepted_conversation_price(rows, product=product), Decimal("790.00"))

    def test_manager_can_accept_customer_counteroffer(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [
            SimpleNamespace(role="user", text="Можна за 790 грн?"),
            SimpleNamespace(role="manager", text="Так, домовились"),
        ]
        self.assertEqual(_accepted_conversation_price(rows), Decimal("790.00"))

    def test_named_product_selection_starts_a_new_price_epoch(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [
            SimpleNamespace(role="manager", text="Ціна худі 790 грн"),
            SimpleNamespace(role="user", text="Так, оформлюйте"),
            SimpleNamespace(role="user", text="Тоді беру оверсайз Харків"),
        ]
        product = SimpleNamespace(pk=111, title="Футболка Харків Вокзальна Oversize")
        self.assertIsNone(_accepted_conversation_price(rows, product=product))

    def test_product_image_selection_starts_a_new_price_epoch(self):
        from management.services.bot_orders import _accepted_conversation_price

        rows = [
            {"role": "manager", "text": "Ціна футболки 790 грн"},
            {"role": "user", "text": "Так, оформлюйте"},
            {
                "role": "user",
                "text": "Хочу цю",
                "media": [{"url": "https://cdn.example/new.jpg", "role": "product"}],
            },
        ]
        product = SimpleNamespace(pk=111, title="Футболка Харків", slug="kharkiv")
        self.assertIsNone(_accepted_conversation_price(rows, product=product))

    def test_manual_draft_does_not_prefill_customer_counteroffer(self):
        from management.services.ig_payment_review import (
            _apply_catalog_matches_to_draft,
            _apply_validated_conversation_price_to_draft,
            extract_payment_review_evidence,
        )

        messages = [
            {"id": 1, "role": "user", "text": "Беру базову S за 20 грн"},
            {"id": 2, "role": "user", "text": "Я оплатила, ось чек", "attachments": "receipt.jpg"},
        ]
        extracted = extract_payment_review_evidence(messages)
        matches = [{"status": "matched", "product_id": 111, "title": "Базова футболка"}]
        _apply_validated_conversation_price_to_draft(extracted["order_draft"], messages, matches)

        self.assertEqual(extracted["order_draft"]["quoted_total"], "")
        self.assertIsNone(extracted["order_draft"]["items"][0]["unit_price"])
        self.assertIn(
            "conversation_price_not_authorized",
            extracted["order_draft"]["uncertainty_reasons"],
        )

    def test_manual_draft_uses_only_manager_accepted_price(self):
        from management.services.ig_payment_review import (
            _apply_catalog_matches_to_draft,
            _apply_validated_conversation_price_to_draft,
            extract_payment_review_evidence,
        )

        messages = [
            {"id": 1, "role": "manager", "text": "Можу оформити цю футболку за 790 грн"},
            {"id": 2, "role": "user", "text": "Так, оформлюйте"},
            {"id": 3, "role": "user", "text": "Я оплатила, ось чек", "attachments": "receipt.jpg"},
        ]
        extracted = extract_payment_review_evidence(messages)
        matches = [{"status": "matched", "product_id": 111, "title": "Базова футболка"}]
        _apply_catalog_matches_to_draft(extracted["order_draft"], matches)
        _apply_validated_conversation_price_to_draft(
            extracted["order_draft"],
            messages,
            matches,
        )

        self.assertEqual(extracted["order_draft"]["quoted_total"], "790")
        self.assertEqual(extracted["order_draft"]["items"][0]["unit_price"], "790.00")

    def test_multi_line_manager_total_remains_visible_without_unsafe_allocation(self):
        from management.services.ig_payment_review import (
            _apply_catalog_matches_to_draft,
            _apply_validated_conversation_price_to_draft,
            extract_payment_review_evidence,
        )

        messages = [
            {"id": 1, "role": "user", "text": "Мені потрібно 2 футболки: 1. Базова S 2. Оверсайз XS"},
            {"id": 2, "role": "manager", "text": "Сума: 2100 грн"},
            {"id": 3, "role": "user", "text": "По повній передоплаті"},
        ]
        extracted = extract_payment_review_evidence(messages)
        matches = [{"status": "matched", "product_id": 111, "title": "Футболка Харків"}]
        _apply_catalog_matches_to_draft(extracted["order_draft"], matches)
        _apply_validated_conversation_price_to_draft(extracted["order_draft"], messages, matches)

        self.assertEqual(extracted["order_draft"]["quoted_total"], "2100")
        self.assertTrue(all(item["unit_price"] is None for item in extracted["order_draft"]["items"]))
        self.assertIn("conversation_price_allocation_required", extracted["order_draft"]["uncertainty_reasons"])


class PaymentReviewDealBindingTests(SimpleTestCase):
    def _deal(self, **overrides):
        values = {
            "status": "awaiting_payment",
            "order_id": None,
            "payment_truth": "unverified",
            "payment_status": "unpaid",
            "product_ids": {111},
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_terminal_or_product_conflicting_deal_is_not_compatible(self):
        from management.services.ig_payment_review import _is_review_deal_compatible

        self.assertFalse(_is_review_deal_compatible(self._deal(status="order_created"), {111}))
        self.assertFalse(_is_review_deal_compatible(self._deal(product_ids={222}), {111}))
        self.assertFalse(_is_review_deal_compatible(self._deal(payment_truth="confirmed"), {111}))

    def test_current_unpaid_same_product_deal_is_compatible(self):
        from management.services.ig_payment_review import _is_review_deal_compatible

        self.assertTrue(_is_review_deal_compatible(self._deal(), {111}))


class TelegramPaymentReviewGateTests(SimpleTestCase):
    def _notification(self, **overrides):
        values = {
            "event_type": "payment_review",
            "status": "sent",
            "telegram_message_id": "88",
            "payload": {"chat_id": "-100", "media": [{"delivery_status": "sent"}]},
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_exact_sent_review_notification_is_actionable(self):
        from management.views import _payment_review_notification_gate

        self.assertEqual(_payment_review_notification_gate(self._notification(), "-100", 88), "")

    def test_wrong_message_and_failed_media_block_decision(self):
        from management.views import _payment_review_notification_gate

        self.assertEqual(
            _payment_review_notification_gate(self._notification(), "-100", 89),
            "Ця кнопка не належить цьому review",
        )
        self.assertEqual(
            _payment_review_notification_gate(
                self._notification(status="failed", payload={
                    "chat_id": "-100",
                    "main_delivery_message_id": "88",
                    "media": [{"delivery_status": "failed"}],
                }),
                "-100",
                88,
            ),
            "Докази ще не доставлені — відкрийте перевірку",
        )

    def test_main_alert_waits_until_receipt_media_is_delivered(self):
        from management.views import _payment_review_notification_gate

        notification = self._notification(
            status="sending",
            telegram_message_id="",
            payload={
                "chat_id": "-100",
                "main_delivery_message_id": "88",
                "media": [{"delivery_status": "sending"}],
            },
        )
        self.assertEqual(
            _payment_review_notification_gate(notification, "-100", 88),
            "Докази ще не доставлені — відкрийте перевірку",
        )

    @patch("management.services.ig_payment_review.transaction.atomic", return_value=nullcontext())
    def test_losing_opposite_transition_cannot_overwrite_winner_audit(self, _atomic):
        from management.ig_bot_models import IgPaymentConfirmationReview
        from management.services.ig_payment_review import cancel_review, confirm_review

        locked = SimpleNamespace(
            pk=42,
            status=IgPaymentConfirmationReview.Status.PENDING,
            evidence={},
            save=Mock(),
        )
        query = Mock()
        query.get.return_value = locked
        with patch.object(IgPaymentConfirmationReview.objects, "select_for_update", return_value=query):
            winner = confirm_review(
                SimpleNamespace(pk=42),
                actor=None,
                telegram_decision={"action": "confirm", "telegram_user_id": "7"},
            )
            winner_applied = winner._transitioned
            loser = cancel_review(
                SimpleNamespace(pk=42),
                actor=None,
                telegram_decision={"action": "cancel", "telegram_user_id": "8"},
            )

        self.assertTrue(winner_applied)
        self.assertFalse(loser._transitioned)
        self.assertEqual(locked.status, IgPaymentConfirmationReview.Status.CONFIRMED)
        self.assertEqual(locked.evidence["telegram_decision"]["action"], "confirm")


class CatalogAssignmentTests(SimpleTestCase):
    def test_pending_review_refreshes_when_material_draft_changes(self):
        from management.services.ig_payment_review import _review_evidence_needs_refresh

        current = {
            "media_audit_v3": True,
            "order_draft": {"items": [{"product_id": 111}, {"product_id": None}], "quoted_total": ""},
            "media": [{"role": "product"}],
            "catalog_matches": [{"product_id": 111}],
        }
        extracted = {
            "media_audit_v3": True,
            "order_draft": {"items": [{"product_id": 111}, {"product_id": 111}], "quoted_total": "2100"},
            "media": [{"role": "product"}],
            "catalog_matches": [{"product_id": 111}],
        }

        self.assertTrue(_review_evidence_needs_refresh("pending", current, extracted))
        self.assertFalse(_review_evidence_needs_refresh("confirmed", current, extracted))
        self.assertFalse(_review_evidence_needs_refresh("pending", extracted, extracted))

    @patch("django.core.files.storage.default_storage")
    @patch(
        "management.services.instagram_bot.download_image",
        return_value=("image/jpeg", b"same-product"),
    )
    def test_persist_review_media_reuses_duplicate_provider_media(self, download, storage):
        from management.services.ig_payment_review import _persist_review_media

        storage.exists.return_value = False
        storage.url.return_value = "/media/ig_payment_reviews/reused.jpg"
        media = [
            {
                "url": "https://lookaside.example/signed-a.jpg",
                "ig_post_media_id": "post-123",
                "role": "product",
            },
            {
                "url": "https://lookaside.example/signed-b.jpg",
                "ig_post_media_id": "post-123",
                "role": "product",
            },
        ]

        persisted = _persist_review_media(media)

        self.assertEqual(download.call_count, 1)
        self.assertEqual(storage.save.call_count, 1)
        self.assertEqual(persisted[0]["local_url"], persisted[1]["local_url"])
        self.assertEqual(persisted[0]["content_hash"], persisted[1]["content_hash"])

    @patch("management.services.bot_vision.match_many", return_value=[{
        "product_id": 11,
        "confidence": 0.93,
        "source_image_indexes": [0],
        "reason": "локальне зображення збігається",
    }])
    @patch(
        "management.services.instagram_bot.download_image",
        side_effect=lambda url: ("image/jpeg", b"local") if "/media/" in url else None,
    )
    def test_catalog_matching_prefers_persisted_local_media(self, _download, _match_many):
        from management.services.ig_payment_review import _catalog_matches_for_media

        with patch(
            "management.services.ig_payment_review._hydrate_catalog_match",
            return_value={"status": "matched", "product_id": 11, "confidence": 0.93},
        ):
            matches = _catalog_matches_for_media([{
                "url": "https://lookaside.example/expired-signed-url.jpg",
                "local_url": "/media/ig_payment_reviews/product.jpg",
                "role": "product",
                "intent": "purchase_candidate",
                "actionable": True,
                "catalog_match_allowed": True,
            }])

        self.assertEqual(matches[0]["product_id"], 11)
        self.assertIn("/media/", _download.call_args.args[0])

    def test_order_binding_ignores_old_product_question_media(self):
        from management.services.ig_payment_review import _catalog_order_media

        question = {
            "url": "https://cdn.example/question.jpg",
            "role": "product",
            "intent": "question",
            "actionable": False,
            "catalog_match_allowed": True,
        }
        purchase = {
            "url": "https://cdn.example/purchase.jpg",
            "role": "product",
            "intent": "purchase_candidate",
            "actionable": True,
            "catalog_match_allowed": True,
        }
        self.assertEqual(_catalog_order_media([question, purchase]), [purchase])

    @patch("management.services.ig_payment_review._hydrate_catalog_match")
    @patch("management.services.bot_vision.match_many", return_value=[{
        "product_id": 11,
        "confidence": 0.93,
        "source_image_indexes": [0],
        "reason": "дубль одного зображення",
    }])
    @patch(
        "management.services.instagram_bot.download_image",
        side_effect=lambda url: ("image/jpeg", b"same-product") if "/media/" in url else None,
    )
    def test_catalog_matching_deduplicates_identical_media_but_keeps_source_indexes(
        self, _download, _match_many, hydrate
    ):
        from management.services.ig_payment_review import _catalog_matches_for_media

        hydrate.return_value = {"status": "matched", "product_id": 11, "confidence": 0.93}
        media = [
            {
                "url": "https://lookaside.example/expired-a.jpg",
                "local_url": "/media/ig_payment_reviews/a.jpg",
                "role": "product",
                "intent": "purchase_candidate",
                "actionable": True,
                "catalog_match_allowed": True,
            },
            {
                "url": "https://lookaside.example/expired-b.jpg",
                "local_url": "/media/ig_payment_reviews/b.jpg",
                "role": "product",
                "intent": "purchase_candidate",
                "actionable": True,
                "catalog_match_allowed": True,
            },
        ]

        matches = _catalog_matches_for_media(media)

        self.assertEqual(matches[0]["product_id"], 11)
        self.assertEqual(len(_match_many.call_args.args[0]), 1)
        self.assertEqual(hydrate.call_args.args[2], [0, 1])

    @patch("management.services.ig_payment_review._hydrate_catalog_match")
    @patch("management.services.bot_vision.match_many", return_value=[{
        "product_id": 11,
        "confidence": 0.93,
        "source_image_indexes": [0, 1],
        "reason": "два різні джерела одного замовлення",
    }])
    @patch(
        "management.services.instagram_bot.download_image",
        side_effect=lambda url: (
            "image/jpeg", b"product-a" if url.endswith("/a.jpg") else b"product-b"
        ),
    )
    def test_catalog_matching_keeps_distinct_media_independent(self, _download, _match_many, hydrate):
        from management.services.ig_payment_review import _catalog_matches_for_media

        hydrate.return_value = {"status": "matched", "product_id": 11, "confidence": 0.93}
        media = [
            {
                "url": "https://lookaside.example/a.jpg",
                "local_url": "/media/ig_payment_reviews/a.jpg",
                "role": "product",
                "intent": "purchase_candidate",
                "actionable": True,
                "catalog_match_allowed": True,
            },
            {
                "url": "https://lookaside.example/b.jpg",
                "local_url": "/media/ig_payment_reviews/b.jpg",
                "role": "product",
                "intent": "purchase_candidate",
                "actionable": True,
                "catalog_match_allowed": True,
            },
        ]

        _catalog_matches_for_media(media)

        self.assertEqual(len(_match_many.call_args.args[0]), 2)
        self.assertEqual(hydrate.call_args.args[2], [0, 1])

    @patch("management.services.ig_payment_review._hydrate_catalog_match")
    @patch("management.services.bot_vision.match_many", return_value=[{
        "product_id": 11,
        "confidence": 0.93,
        "source_image_indexes": [0],
        "reason": "durable hash reused",
    }])
    @patch(
        "management.services.instagram_bot.download_image",
        return_value=("image/jpeg", b"same-product"),
    )
    def test_catalog_matching_skips_second_local_download_for_known_hash(
        self, download, _match_many, hydrate
    ):
        from management.services.ig_payment_review import _catalog_matches_for_media

        hydrate.return_value = {"status": "matched", "product_id": 11, "confidence": 0.93}
        media = [
            {
                "url": "https://lookaside.example/a.jpg",
                "local_url": "/media/ig_payment_reviews/a.jpg",
                "content_hash": "6966aafb2ab4821d23624e6f910a007c27ccd55ee9b18bcea14d078c1fdeace4",
                "role": "product",
                "intent": "purchase_candidate",
                "actionable": True,
                "catalog_match_allowed": True,
            },
            {
                "url": "https://lookaside.example/b.jpg",
                "local_url": "/media/ig_payment_reviews/b.jpg",
                "content_hash": "6966aafb2ab4821d23624e6f910a007c27ccd55ee9b18bcea14d078c1fdeace4",
                "role": "product",
                "intent": "purchase_candidate",
                "actionable": True,
                "catalog_match_allowed": True,
            },
        ]

        matches = _catalog_matches_for_media(media)

        self.assertEqual(matches[0]["product_id"], 11)
        self.assertEqual(download.call_count, 1)
        self.assertEqual(hydrate.call_args.args[2], [0, 1])

    def test_two_catalog_matches_are_bound_to_two_draft_lines(self):
        from management.services.ig_payment_review import _apply_catalog_matches_to_draft

        draft = {
            "items": [
                {"title": "Футболка 1", "fit": "classic", "source_message_id": 101},
                {"title": "Футболка 2", "fit": "oversize", "source_message_id": 102},
            ],
            "uncertainty_reasons": ["catalog_product_not_identified"],
        }
        matches = [
            {"status": "matched", "product_id": 11, "title": "Харків", "url": "https://twocomms.shop/p/kharkiv/", "source_message_ids": [101]},
            {"status": "matched", "product_id": 22, "title": "Київ", "url": "https://twocomms.shop/p/kyiv/", "source_message_ids": [102]},
        ]
        _apply_catalog_matches_to_draft(draft, matches)
        self.assertEqual([item["product_id"] for item in draft["items"]], [11, 22])
        self.assertEqual(draft["items"][0]["catalog"]["url"], "https://twocomms.shop/p/kharkiv/")
        self.assertNotIn("catalog_product_not_identified", draft["uncertainty_reasons"])

    def test_one_catalog_product_can_bind_classic_and_oversize_lines_from_same_message(self):
        from management.services.ig_payment_review import _apply_catalog_matches_to_draft

        draft = {
            "items": [
                {"title": "Базова футболка", "fit": "classic", "size": "S", "source_message_id": 233},
                {"title": "Оверсайз", "fit": "oversize", "size": "XS", "source_message_id": 233},
            ],
            "uncertainty_reasons": ["catalog_product_not_identified"],
        }
        matches = [{
            "status": "matched",
            "product_id": 111,
            "title": "Футболка «Харків Вокзальна»",
            "url": "https://twocomms.shop/product/futbolka-kharkiv-vokzalna/",
            "source_message_ids": [233],
        }]

        _apply_catalog_matches_to_draft(draft, matches)

        self.assertEqual([item["product_id"] for item in draft["items"]], [111, 111])
        self.assertNotIn("catalog_product_not_identified", draft["uncertainty_reasons"])

    def test_two_matches_from_one_purchase_screenshot_create_two_draft_lines(self):
        from management.services.ig_payment_review import _apply_catalog_matches_to_draft

        draft = {"items": [], "uncertainty_reasons": ["catalog_product_not_identified"]}
        matches = [
            {"status": "matched", "product_id": 11, "title": "Харків", "url": "https://twocomms.shop/p/kharkiv/"},
            {"status": "matched", "product_id": 22, "title": "Київ", "url": "https://twocomms.shop/p/kyiv/"},
        ]
        _apply_catalog_matches_to_draft(draft, matches)
        self.assertEqual(len(draft["items"]), 2)
        self.assertEqual([item["product_id"] for item in draft["items"]], [11, 22])
        self.assertEqual([item["qty"] for item in draft["items"]], [1, 1])
        self.assertNotIn("catalog_product_not_identified", draft["uncertainty_reasons"])
