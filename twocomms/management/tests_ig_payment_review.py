import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings


class IgPaymentReviewRulesTests(SimpleTestCase):
    def test_manager_payment_instructions_do_not_count_as_customer_payment(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence(
            [
                {
                    "id": 237,
                    "role": "manager",
                    "text": "Оплата на рахунок ФОП. Сума: 2100 грн",
                },
            ]
        )
        self.assertFalse(result["needs_review"])
        self.assertEqual(result["evidence"], [])

    def test_receipt_and_negotiated_order_draft_keep_roles_and_uncertainty(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence(
            [
                {
                    "id": 233,
                    "role": "user",
                    "text": "Мені потрібно 2 футболки: 1. Базова s 2. Оверсайз xs. Принт однаковий",
                },
                {
                    "id": 237,
                    "role": "manager",
                    "text": "Оплата на рахунок ФОП. Сума: 2100 грн",
                },
                {
                    "id": 238,
                    "role": "user",
                    "text": "(зображення)",
                    "attachments": "[https://lookaside.fbsbx.com/receipt.jpg]",
                },
            ]
        )
        self.assertTrue(result["needs_review"])
        self.assertEqual(result["message_ids"], [238])
        self.assertEqual(result["order_draft"]["quoted_total"], "2100")
        self.assertEqual(
            [(item["fit"], item["size"], item["qty"]) for item in result["order_draft"]["items"]],
            [("classic", "S", 1), ("oversize", "XS", 1)],
        )
        self.assertIn("catalog_product_not_identified", result["order_draft"]["uncertainty_reasons"])
        self.assertEqual(result["amount_evidence"][0]["role"], "manager")
        self.assertEqual(result["order_draft"]["delivery"], {
            "full_name": "",
            "phone": "",
            "city": "",
            "office": "",
        })

    def test_receipt_before_manager_payment_context_is_still_reviewed(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence(
            [
                {"id": 238, "role": "user", "text": "Я оплатила, ось чек", "attachments": "receipt.jpg"},
                {"id": 237, "role": "manager", "text": "Оплата на рахунок ФОП. Сума: 2100 грн"},
            ]
        )
        self.assertTrue(result["needs_review"])
        self.assertEqual(result["message_ids"], [238])

    def test_product_post_and_receipt_are_separate_media_roles(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {
                "id": 235,
                "role": "user",
                "text": "Принт ось цей",
                "media": [{"url": "https://cdn/product.jpg", "type": "ig_post", "title": "Біла футболка 1654"}],
            },
            {"id": 237, "role": "manager", "text": "Оплата на рахунок ФОП. Сума: 2100 грн"},
            {
                "id": 238,
                "role": "user",
                "text": "(зображення)",
                "media": [{"url": "https://cdn/receipt.jpg", "type": "image"}],
            },
        ])
        self.assertEqual(
            [(item["url"], item["role"]) for item in result["media"]],
            [("https://cdn/product.jpg", "product"), ("https://cdn/receipt.jpg", "payment_candidate")],
        )
        self.assertEqual(result["evidence"][0]["media"][0]["role"], "payment_candidate")

    @patch("management.services.ig_payment_review._raw_media_by_mid", return_value={
        "mid-product": [{"url": "https://cdn/product.jpg", "type": "ig_post", "raw_event_id": 437}],
    })
    def test_raw_event_media_is_recovered_when_normalized_attachment_is_empty(self, _raw):
        from management.services.ig_payment_review import _augment_messages_with_raw_media

        client = SimpleNamespace(igsid="1735898131060065")
        rows = _augment_messages_with_raw_media(client, [{"id": 235, "mid": "mid-product", "attachments": ""}])
        self.assertEqual(rows[0]["media"][0]["type"], "ig_post")
        self.assertIn("product.jpg", rows[0]["attachments"])

    def test_packaging_preference_requires_manager_package_context(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence(
            [
                {"id": 241, "role": "manager", "text": "Футболки в різні зіп пакети чи можна в один?"},
                {"id": 242, "role": "user", "text": "В різні"},
                {"id": 238, "role": "user", "text": "(зображення)", "attachments": "receipt.jpg"},
            ]
        )
        self.assertEqual(result["order_draft"]["packaging_preference"], "Окремі пакети")

    def test_delivery_lines_are_preserved_for_editable_order_draft(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence(
            [
                {
                    "id": 236,
                    "role": "user",
                    "text": "Харків, поштомат 21586\nНіколаєнко Яна\n0502034719\n\nПо повній передоплаті",
                },
                {"id": 238, "role": "user", "text": "(зображення)", "attachments": "receipt.jpg"},
            ]
        )
        self.assertTrue(result["needs_review"])
        self.assertEqual(result["order_draft"]["delivery"], {
            "full_name": "Ніколаєнко Яна",
            "phone": "0502034719",
            "city": "Харків",
            "office": "Поштомат 21586",
        })

    def test_customer_prepayment_context_is_bounded_to_the_next_unlabelled_image(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {"id": 1, "role": "user", "text": "По повній передоплаті"},
            {"id": 2, "role": "user", "text": "Добре"},
            {
                "id": 3,
                "role": "user",
                "text": "(зображення)",
                "attachments": '["https://cdn.example/later-product.jpg"]',
            },
        ])

        self.assertFalse(result["needs_review"])
        self.assertEqual(result["media"][0]["role"], "other")

    def test_delivery_parser_ignores_short_followup_and_reads_slash_separated_name(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence(
            [
                {
                    "id": 236,
                    "role": "user",
                    "text": "Харків, поштомат 21586 / Ніколаєнко Яна / 0502034719 / По повній передоплаті",
                },
                {"id": 238, "role": "user", "text": "(зображення)", "attachments": "receipt.jpg"},
                {"id": 242, "role": "user", "text": "В різні"},
            ]
        )
        self.assertEqual(result["order_draft"]["delivery"]["full_name"], "Ніколаєнко Яна")

    def test_manager_alert_preserves_conversation_total_and_uncertainty(self):
        from types import SimpleNamespace

        from management.services.ig_payment_review import _alert_text

        review = SimpleNamespace(
            pk=42,
            evidence={
                "order_draft": {
                    "quoted_total": "2100",
                    "currency": "UAH",
                    "items": [{"title": "Базова футболка", "size": "S", "qty": 1}],
                    "uncertainty_reasons": ["catalog_product_not_identified"],
                },
            },
        )
        client = SimpleNamespace(display_name="Яна", username="yana", igsid="1735898131060065")
        text = _alert_text(review, client)
        self.assertIn("2100 грн", text)
        self.assertIn("Базова футболка · S · 1 шт.", text)
        self.assertIn("товар не зіставлено з каталогом", text)
        self.assertIn("management.twocomms.shop/bot/", text)
        self.assertNotIn("ціна сайту", text)

    def test_single_line_conversation_total_prefills_negotiated_unit_price(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {"id": 1, "role": "user", "text": "Беру базову S за 790 грн"},
            {"id": 2, "role": "user", "text": "Я вже оплатила, ось чек", "attachments": "receipt.jpg"},
        ])
        self.assertEqual(result["order_draft"]["items"][0]["unit_price"], "790.00")

    def test_multi_line_total_requires_manual_price_allocation(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {"id": 1, "role": "user", "text": "Базова S та oversize XS, разом 2100 грн"},
            {"id": 2, "role": "user", "text": "Я вже оплатила, ось чек", "attachments": "receipt.jpg"},
        ])
        self.assertIn("conversation_price_allocation_required", result["order_draft"]["uncertainty_reasons"])

    def test_prepaid_receipt_amount_does_not_replace_agreed_order_total(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {"id": 1, "role": "user", "text": "Базова S та oversize XS"},
            {"id": 2, "role": "manager", "text": "Сума замовлення разом 2100 грн"},
            {"id": 3, "role": "user", "text": "Так, погоджуюсь"},
            {"id": 4, "role": "user", "text": "Оплатила передоплату 200 грн, ось чек", "attachments": "receipt.jpg"},
        ])
        self.assertEqual(result["order_draft"]["quoted_total"], "2100")
        self.assertEqual(
            [(item["amount"], item["kind"]) for item in result["amount_evidence"]],
            [("2100", "order_total"), ("200", "payment_evidence")],
        )

    def test_multiple_amounts_in_one_message_keep_independent_meanings(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {
                "id": 237,
                "role": "manager",
                "text": "Сума замовлення 2100 грн, передоплата 200 грн на рахунок ФОП",
            },
        ])

        self.assertEqual(result["order_draft"]["quoted_total"], "2100")
        self.assertEqual(
            [(item["amount"], item["kind"]) for item in result["amount_evidence"]],
            [("2100", "order_total"), ("200", "payment_evidence")],
        )

    def test_completed_transfer_amount_does_not_replace_agreed_order_total(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence([
            {"id": 1, "role": "manager", "text": "Ціна футболки 790 грн"},
            {"id": 2, "role": "user", "text": "Так, оформлюйте"},
            {"id": 3, "role": "user", "text": "Переказ зроблено, сума 200 грн"},
        ])

        self.assertTrue(result["needs_review"])
        self.assertEqual(result["order_draft"]["quoted_total"], "790")
        self.assertEqual(
            [(item["amount"], item["kind"]) for item in result["amount_evidence"]],
            [("790", "unit_price"), ("200", "payment_evidence")],
        )

    def test_manager_alert_has_review_button_and_media_summary(self):
        from management.services.ig_payment_review import _alert_text, _review_keyboard

        review = SimpleNamespace(
            pk=42,
            evidence={
                "order_draft": {"quoted_total": "2100", "items": [{"title": "Базова футболка", "size": "S", "qty": 1}]},
                "media": [{"role": "product"}, {"role": "receipt"}],
                "catalog_match": {"status": "matched", "title": "Футболка «Харків Вокзальна»", "confidence": 0.94, "url": "https://twocomms.shop/product/kharkiv/"},
            },
        )
        client = SimpleNamespace(display_name="Яна", username="yana", igsid="1735898131060065")
        text = _alert_text(review, client)
        self.assertIn("чеків 1", text)
        self.assertIn("Футболка «Харків Вокзальна»", text)
        keyboard = _review_keyboard(review)
        self.assertEqual(keyboard["inline_keyboard"][0][0]["text"], "Підтвердити оплату 2100.00 грн")
        self.assertEqual(keyboard["inline_keyboard"][0][0]["callback_data"], "igpay:confirm:42")
        self.assertEqual(keyboard["inline_keyboard"][0][1]["callback_data"], "igpay:cancel:42")
        self.assertEqual(keyboard["inline_keyboard"][1][0]["text"], "Відкрити перевірку")
        self.assertEqual(keyboard["inline_keyboard"][2][0]["text"], "Товар: Футболка «Харків Вокзальна»")

    def test_telegram_keyboard_requires_unambiguous_amount_for_direct_confirm(self):
        from management.services.ig_payment_review import _review_keyboard

        review = SimpleNamespace(pk=43, evidence={})
        keyboard = _review_keyboard(review)
        callback_buttons = [
            button
            for row in keyboard["inline_keyboard"]
            for button in row
            if button.get("callback_data", "").startswith("igpay:confirm:")
        ]

        self.assertEqual(callback_buttons, [])
        self.assertEqual(keyboard["inline_keyboard"][0][0]["text"], "Відкрити перевірку")

    def test_confirmation_candidate_has_stable_evidence_digest(self):
        from management.services.ig_payment_review import resolve_review_payment_amount

        review = SimpleNamespace(
            pk=44,
            watermark_message_id=91,
            evidence={
                "amount_evidence": [
                    {"kind": "payment_evidence", "amount": "500", "message_id": 91},
                ],
                "order_draft": {"quoted_total": "2100", "currency": "UAH"},
            },
        )

        first = resolve_review_payment_amount(review)
        second = resolve_review_payment_amount(review)

        self.assertEqual(first["amount"], Decimal("500.00"))
        self.assertEqual(first["scope"], "prepayment")
        self.assertEqual(first["source"], "review_payment_evidence")
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(len(first["digest"]), 64)

    def test_customer_payment_statement_is_review_evidence_not_provider_paid(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence(
            [
                {"id": 10, "role": "user", "text": "Я вже оплатила, чек у вкладенні"},
                {"id": 11, "role": "manager", "text": "Добре, перевірю"},
            ]
        )
        self.assertTrue(result["needs_review"])
        self.assertFalse(result["provider_confirmed"])
        self.assertEqual(result["message_ids"], [10])

    def test_reaction_and_payment_link_do_not_create_review(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence(
            [
                {"id": 10, "role": "user", "text": "🔥"},
                {"id": 11, "role": "model", "text": "Ось посилання на оплату"},
            ]
        )
        self.assertFalse(result["needs_review"])

    def test_waiting_verbs_do_not_count_as_receipt_evidence(self):
        from management.services.ig_payment_review import extract_payment_review_evidence

        result = extract_payment_review_evidence(
            [
                {"id": 227, "role": "user", "text": "Чекаю розмірну сітку"},
                {"id": 234, "role": "user", "text": "Почекаємо"},
            ]
        )
        self.assertFalse(result["needs_review"])

    def test_confirmation_transition_is_idempotent_and_cancel_is_terminal(self):
        from management.services.ig_payment_review import next_review_status

        self.assertEqual(next_review_status("pending", "confirm"), "confirmed")
        self.assertEqual(next_review_status("confirmed", "confirm"), "confirmed")
        self.assertEqual(next_review_status("confirmed", "cancel"), "cancelled")
        self.assertEqual(next_review_status("cancelled", "confirm"), "cancelled")


class PaymentReviewEpisodeScopeTests(TestCase):
    def test_repeat_episode_without_deal_never_reuses_old_same_product_deal(self):
        from management.ig_bot_models import IgClient, IgCommercialEpisode, IgDeal, IgDealItem
        from management.services.ig_commercial_episodes import (
            ensure_episode_for_deal,
            start_repeat_episode,
        )
        from management.services.ig_payment_review import _select_review_deal
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Футболки review", slug="review-episode")
        product = Product.objects.create(
            title="Футболка review",
            slug="review-episode-product",
            category=category,
            price=Decimal("790.00"),
            status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("review-repeat-episode-scope")
        old_deal = IgDeal.objects.create(
            client=client,
            amount=Decimal("790.00"),
            status=IgDeal.Status.AWAITING_PAYMENT,
        )
        IgDealItem.objects.create(
            deal=old_deal,
            product=product,
            title=product.title,
            qty=1,
            unit_price=Decimal("790.00"),
        )
        old_episode = ensure_episode_for_deal(old_deal)
        old_episode.state = IgCommercialEpisode.State.LOST
        old_episode.open_slot = None
        old_episode.save(update_fields=["state", "open_slot", "updated_at"])
        client.current_commercial_episode = None
        client.save(update_fields=["current_commercial_episode", "updated_at"])
        repeat = start_repeat_episode(
            client,
            repeat_kind=IgCommercialEpisode.RepeatKind.REORDER,
            evidence_message_ids=[9901],
            confidence=Decimal("0.97"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-scope-v1",
        )

        selected = _select_review_deal(
            client,
            [{"status": "matched", "product_id": product.pk}],
        )

        self.assertIsNone(repeat.deal_id)
        self.assertIsNone(selected)

    def test_new_episode_review_does_not_rematerialize_old_payment_claim(self):
        from management.ig_bot_models import IgClient, IgCommercialEpisode
        from management.models import InstagramBotMessage
        from management.services.ig_commercial_episodes import start_repeat_episode
        from management.services.ig_payment_review import create_payment_review

        client = IgClient.get_or_create_for_sender("review-message-episode-scope")
        InstagramBotMessage.objects.create(
            client=client,
            sender_id=client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Я оплатив 790 грн, ось чек",
        )
        repeat_message = InstagramBotMessage.objects.create(
            client=client,
            sender_id=client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Хочу замовити ще одну футболку",
        )
        start_repeat_episode(
            client,
            repeat_kind=IgCommercialEpisode.RepeatKind.REORDER,
            evidence_message_ids=[repeat_message.pk],
            confidence=Decimal("0.98"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-review-scope-v1",
        )
        current_message = InstagramBotMessage.objects.create(
            client=client,
            sender_id=client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Потрібен чорний колір",
        )

        review = create_payment_review(client, watermark=current_message.pk)

        self.assertIsNone(review)


class IgPaymentTelegramCallbackTests(TestCase):
    @override_settings(MANAGEMENT_BASE_URL="https://management.example")
    @patch.dict("os.environ", {"MANAGEMENT_TG_ADMIN_CHAT_ID": "777", "MANAGEMENT_TG_BOT_TOKEN": "token"}, clear=False)
    @patch("management.views._tg_edit_message")
    @patch("management.views._tg_answer_callback")
    def test_confirm_button_confirms_review_without_management_second_click(self, answer, edit):
        from management.ig_bot_models import IgPaymentConfirmationReview
        from management.models import IgBotNotification, IgClient
        from management.views import management_bot_webhook

        client = IgClient.get_or_create_for_sender("telegram-review-client")
        review = IgPaymentConfirmationReview.objects.create(
            client=client,
            dedupe_key="telegram-review-callback",
            evidence={"order_draft": {"quoted_total": "2100"}},
        )
        IgBotNotification.objects.create(
            dedupe_key=review.dedupe_key,
            event_type="payment_review",
            payload={
                "text": "Review",
                "chat_id": "777",
                "media": [],
                "payment_candidate": {
                    "amount": "2100.00",
                    "currency": "UAH",
                    "scope": "full_payment",
                    "source": "review_quoted_total",
                    "evidence_message_ids": [],
                    "digest": "placeholder",
                },
            },
            status=IgBotNotification.Status.SENT,
            telegram_message_id="88",
        )
        request = RequestFactory().post(
            "/management/telegram/webhook/token",
            data=json.dumps({
                "callback_query": {
                    "id": "cb-1",
                    "data": f"igpay:confirm:{review.pk}",
                    "from": {"id": 777, "username": "owner"},
                    "message": {"chat": {"id": 777, "type": "private"}, "message_id": 88, "text": "Review"},
                }
            }),
            content_type="application/json",
        )
        from management.services.ig_payment_review import resolve_review_payment_amount

        notification = IgBotNotification.objects.get(dedupe_key=review.dedupe_key)
        notification.payload["payment_candidate"] = {
            **notification.payload["payment_candidate"],
            "digest": resolve_review_payment_amount(review)["digest"],
        }
        notification.save(update_fields=["payload", "updated_at"])
        response = management_bot_webhook(request, "token")
        self.assertEqual(response.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.status, IgPaymentConfirmationReview.Status.CONFIRMED)
        decision = review.decisions.get()
        self.assertEqual(decision.confirmed_amount, Decimal("2100.00"))
        self.assertEqual(decision.amount_source, "review_quoted_total")
        answer.assert_called_once()
        edit.assert_called_once()
        self.assertIsNone(edit.call_args.kwargs["parse_mode"])
        self.assertIn("ig_payment_review=", edit.call_args.kwargs["reply_markup"]["inline_keyboard"][0][0]["url"])

    @override_settings(MANAGEMENT_BASE_URL="https://management.example")
    @patch.dict("os.environ", {"MANAGEMENT_TG_ADMIN_CHAT_ID": "777", "MANAGEMENT_TG_BOT_TOKEN": "token"}, clear=False)
    @patch("management.views._tg_edit_message")
    @patch("management.views._tg_answer_callback")
    def test_confirm_button_rejects_stale_amount_candidate(self, answer, edit):
        from management.ig_bot_models import IgPaymentConfirmationReview
        from management.models import IgBotNotification, IgClient
        from management.views import management_bot_webhook

        client = IgClient.get_or_create_for_sender("telegram-stale-candidate")
        review = IgPaymentConfirmationReview.objects.create(
            client=client,
            dedupe_key="telegram-stale-candidate",
            evidence={"order_draft": {"quoted_total": "2100"}},
        )
        IgBotNotification.objects.create(
            dedupe_key=review.dedupe_key,
            event_type="payment_review",
            payload={
                "text": "Review",
                "chat_id": "777",
                "media": [],
                "payment_candidate": {
                    "amount": "2000.00",
                    "currency": "UAH",
                    "scope": "full_payment",
                    "source": "review_quoted_total",
                    "evidence_message_ids": [],
                    "digest": "stale",
                },
            },
            status=IgBotNotification.Status.SENT,
            telegram_message_id="92",
        )
        request = RequestFactory().post(
            "/management/telegram/webhook/token",
            data=json.dumps({
                "callback_query": {
                    "id": "cb-stale",
                    "data": f"igpay:confirm:{review.pk}",
                    "from": {"id": 777, "username": "owner"},
                    "message": {"chat": {"id": 777, "type": "private"}, "message_id": 92, "text": "Review"},
                }
            }),
            content_type="application/json",
        )

        response = management_bot_webhook(request, "token")

        self.assertEqual(response.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.status, IgPaymentConfirmationReview.Status.PENDING)
        answer.assert_called_once_with("token", "cb-stale", "Сума змінилася — відкрийте перевірку")
        edit.assert_not_called()

    @patch.dict("os.environ", {"MANAGEMENT_TG_BOT_TOKEN": "token"}, clear=True)
    @patch("management.views._tg_edit_message")
    @patch("management.views._tg_answer_callback")
    def test_callback_denies_when_admin_chat_allowlist_is_missing(self, answer, edit):
        from management.views import management_bot_webhook

        request = RequestFactory().post(
            "/management/telegram/webhook/token",
            data=json.dumps({
                "callback_query": {
                    "id": "cb-deny",
                    "data": "igpay:confirm:1",
                    "message": {"chat": {"id": 777}, "message_id": 88, "text": "Review"},
                }
            }),
            content_type="application/json",
        )
        response = management_bot_webhook(request, "token")
        self.assertEqual(response.status_code, 200)
        answer.assert_called_once_with("token", "cb-deny", "Доступ не налаштовано")
        edit.assert_not_called()

    @override_settings(MANAGEMENT_BASE_URL="https://management.example")
    @patch.dict("os.environ", {"MANAGEMENT_TG_ADMIN_CHAT_ID": "777", "MANAGEMENT_TG_BOT_TOKEN": "token"}, clear=False)
    @patch("management.views._tg_edit_message")
    @patch("management.views._tg_answer_callback")
    def test_cancel_button_cancels_review_directly(self, answer, edit):
        from management.ig_bot_models import IgPaymentConfirmationReview, IgPaymentReviewDecision
        from management.models import IgBotNotification, IgClient
        from management.views import management_bot_webhook

        client = IgClient.get_or_create_for_sender("telegram-cancel-client")
        review = IgPaymentConfirmationReview.objects.create(
            client=client,
            dedupe_key="telegram-review-cancel",
            evidence={},
        )
        IgBotNotification.objects.create(
            dedupe_key=review.dedupe_key,
            event_type="payment_review",
            payload={"text": "Review", "chat_id": "777", "media": []},
            status=IgBotNotification.Status.SENT,
            telegram_message_id="89",
        )
        request = RequestFactory().post(
            "/management/telegram/webhook/token",
            data=json.dumps({
                "callback_query": {
                    "id": "cb-cancel",
                    "data": f"igpay:cancel:{review.pk}",
                    "from": {"id": 777, "username": "owner"},
                    "message": {"chat": {"id": 777, "type": "private"}, "message_id": 89, "text": "Review"},
                }
            }),
            content_type="application/json",
        )
        response = management_bot_webhook(request, "token")
        self.assertEqual(response.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.status, IgPaymentConfirmationReview.Status.CANCELLED)
        decision = IgPaymentReviewDecision.objects.get(review=review)
        self.assertEqual(decision.reason_code, "telegram_rejected")
        self.assertEqual(decision.verification_scope, "payment_claim")
        self.assertEqual(decision.actor_source, "telegram_user")
        self.assertEqual(decision.actor_external_id, "777")
        answer.assert_called_once()
        edit.assert_called_once()

    @override_settings(MANAGEMENT_BASE_URL="https://management.example")
    @patch.dict("os.environ", {"MANAGEMENT_TG_ADMIN_CHAT_ID": "777", "MANAGEMENT_TG_BOT_TOKEN": "token"}, clear=False)
    @patch("management.views._tg_edit_message", side_effect=[RuntimeError("telegram edit failed"), None])
    @patch("management.views._tg_answer_callback")
    def test_callback_retry_repairs_message_after_decision_committed(self, answer, edit):
        from management.ig_bot_models import IgPaymentConfirmationReview, IgPaymentReviewDecision
        from management.models import IgBotNotification, IgClient
        from management.views import management_bot_webhook

        client = IgClient.get_or_create_for_sender("telegram-retry-client")
        review = IgPaymentConfirmationReview.objects.create(
            client=client,
            dedupe_key="telegram-review-retry",
            evidence={"order_draft": {"quoted_total": "2100.00", "currency": "UAH"}},
        )
        from management.services.ig_payment_review import resolve_review_payment_amount

        candidate = resolve_review_payment_amount(review)
        notification = IgBotNotification.objects.create(
            dedupe_key=review.dedupe_key,
            event_type="payment_review",
            payload={
                "text": "Review",
                "chat_id": "777",
                "media": [],
                "payment_candidate": {
                    "amount": f"{candidate['amount']:.2f}",
                    "currency": candidate["currency"],
                    "scope": candidate["scope"],
                    "source": candidate["source"],
                    "evidence_message_ids": candidate["evidence_message_ids"],
                    "digest": candidate["digest"],
                },
            },
            status=IgBotNotification.Status.SENT,
            telegram_message_id="90",
        )

        def callback_request(callback_id):
            return RequestFactory().post(
                "/management/telegram/webhook/token",
                data=json.dumps({
                    "callback_query": {
                        "id": callback_id,
                        "data": f"igpay:confirm:{review.pk}",
                        "from": {"id": 777, "username": "owner"},
                        "message": {
                            "chat": {"id": 777, "type": "private"},
                            "message_id": 90,
                            "text": "Review",
                        },
                    }
                }),
                content_type="application/json",
            )

        with self.assertRaisesMessage(RuntimeError, "telegram edit failed"):
            management_bot_webhook(callback_request("cb-retry-1"), "token")

        review.refresh_from_db()
        self.assertEqual(review.status, IgPaymentConfirmationReview.Status.CONFIRMED)
        self.assertEqual(IgPaymentReviewDecision.objects.filter(review=review).count(), 1)

        response = management_bot_webhook(callback_request("cb-retry-2"), "token")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(edit.call_count, 2)
        self.assertEqual(IgPaymentReviewDecision.objects.filter(review=review).count(), 1)
        notification.refresh_from_db()
        self.assertEqual(notification.status, IgBotNotification.Status.RESOLVED)
        answer.assert_called_once_with("token", "cb-retry-2", "Дію вже виконано")
