"""Э1.2–Э1.4 + Э6.2 — карточки, postback как действие FSM, посылка в отделении."""
import json
from unittest.mock import patch

from django.test import TestCase

from management.models import (
    IgClient,
    IgFollowUpTask,
    IgLifecycleEvent,
    InstagramBotMessage,
)
from management.services import ig_message_templates as templates
from management.services import ig_postback_router as router


class TemplateLimitValidatorTests(TestCase):
    """Э1.3 — лимиты Meta соблюдаются деградацией полей, а не отказом."""

    def _template(self, **kwargs):
        defaults = {
            "cards": (
                templates.TemplateCard(
                    title="Худі Vortex",
                    subtitle="Чорне, оверсайз",
                    buttons=(
                        templates.TemplateButton(
                            templates.BUTTON_POSTBACK, "S",
                            payload=templates.build_payload("size", "s", "1"),
                        ),
                    ),
                ),
            ),
            "fallback_text": "Худі Vortex, чорне. Напишіть розмір: S, M або L.",
        }
        defaults.update(kwargs)
        return templates.GenericTemplate(**defaults)

    def test_payload_is_versioned_and_round_trips(self):
        payload = templates.build_payload("parcel", "got", "42")
        self.assertEqual(payload, "twc:1:parcel:got:42")
        parsed = templates.parse_payload(payload)
        self.assertEqual(parsed["action"], "parcel")
        self.assertEqual(parsed["version"], "1")
        self.assertEqual(parsed["args"], ("got", "42"))

    def test_foreign_payload_is_not_claimed(self):
        # Существующая конвенция commerce:<generation>:select:<n> не должна
        # перехватываться новым роутером.
        self.assertEqual(templates.parse_payload("commerce:7:select:2"), {})
        self.assertEqual(templates.parse_payload(""), {})

    def test_long_title_is_truncated_on_a_word_boundary(self):
        long_title = "Худі " * 40
        normalized = templates.normalize_template(self._template(
            cards=(templates.TemplateCard(title=long_title, subtitle="Опис"),),
        ))
        card = normalized.cards[0]
        self.assertLessEqual(len(card.title), templates.MAX_TITLE_CHARS)
        self.assertTrue(card.title.endswith("…"))
        self.assertIn("title_truncated", normalized.degraded_fields)

    def test_untrusted_image_is_dropped_not_rejected(self):
        normalized = templates.normalize_template(self._template(
            cards=(
                templates.TemplateCard(
                    title="Худі",
                    subtitle="Чорне",
                    image_url="https://evil.example.com/a.jpg",
                ),
            ),
        ))
        self.assertEqual(normalized.cards[0].image_url, "")
        self.assertIn("image_dropped_untrusted", normalized.degraded_fields)

    def test_extra_buttons_and_elements_are_truncated(self):
        buttons = tuple(
            templates.TemplateButton(
                templates.BUTTON_POSTBACK, f"B{index}",
                payload=templates.build_payload("size", str(index)),
            )
            for index in range(6)
        )
        cards = tuple(
            templates.TemplateCard(title=f"Товар {index}", subtitle="Опис", buttons=buttons)
            for index in range(14)
        )
        normalized = templates.normalize_template(self._template(cards=cards))
        self.assertEqual(len(normalized.cards), templates.MAX_ELEMENTS)
        self.assertEqual(
            len(normalized.cards[0].buttons), templates.MAX_BUTTONS_PER_ELEMENT
        )
        self.assertIn("buttons_truncated", normalized.degraded_fields)
        self.assertIn("elements_truncated", normalized.degraded_fields)

    def test_unsupported_button_kind_is_dropped(self):
        normalized = templates.normalize_template(self._template(
            cards=(
                templates.TemplateCard(
                    title="Худі",
                    subtitle="Чорне",
                    buttons=(templates.TemplateButton("phone_number", "Подзвонити"),),
                ),
            ),
        ))
        self.assertEqual(normalized.cards[0].buttons, ())
        self.assertIn("button_kind_unsupported", normalized.degraded_fields)

    def test_template_without_text_fallback_is_refused(self):
        with self.assertRaises(templates.TemplateValidationError):
            templates.normalize_template(self._template(fallback_text="  "))

    def test_element_without_secondary_field_is_invalid(self):
        with self.assertRaises(templates.TemplateValidationError):
            templates.normalize_template(self._template(
                cards=(templates.TemplateCard(title="Тільки заголовок"),),
            ))

    def test_projection_keeps_buttons_visible_to_the_model(self):
        normalized = templates.normalize_template(self._template())
        self.assertIn("надіслано карточку", normalized.projection_text)
        self.assertIn("Худі Vortex", normalized.projection_text)
        self.assertIn("кнопки: S", normalized.projection_text)

    def test_provider_payload_matches_the_documented_shape(self):
        normalized = templates.normalize_template(self._template())
        message = templates.template_message_payload(normalized)
        payload = message["attachment"]["payload"]
        self.assertEqual(message["attachment"]["type"], "template")
        self.assertEqual(payload["template_type"], "generic")
        element = payload["elements"][0]
        self.assertEqual(element["title"], "Худі Vortex")
        self.assertEqual(element["buttons"][0]["type"], "postback")

    def test_button_template_payload_matches_the_documented_shape(self):
        normalized = templates.normalize_button_template(
            templates.ButtonTemplate(
                text="Отримувати ТТН і статус замовлення тут у Direct?",
                buttons=(
                    templates.TemplateButton(
                        templates.BUTTON_POSTBACK,
                        "Так, отримувати",
                        payload=templates.build_payload("preview", "2", "yes", "7"),
                    ),
                    templates.TemplateButton(
                        templates.BUTTON_WEB_URL,
                        "Розмірна сітка",
                        url="https://twocomms.shop/uk/rozmirna-sitka/",
                    ),
                ),
            )
        )
        message = templates.button_template_message_payload(normalized)
        payload = message["attachment"]["payload"]
        self.assertEqual(payload["template_type"], "button")
        self.assertEqual(payload["text"], normalized.text)
        self.assertEqual(payload["buttons"][0]["type"], "postback")
        self.assertEqual(payload["buttons"][1]["type"], "web_url")

    def test_button_template_is_bounded_to_three_buttons_and_640_chars(self):
        normalized = templates.normalize_button_template(
            templates.ButtonTemplate(
                text="слово " * 200,
                fallback_text="Оберіть потрібну дію у відповіді.",
                buttons=tuple(
                    templates.TemplateButton(
                        templates.BUTTON_POSTBACK,
                        f"Варіант {index}",
                        payload=templates.build_payload("preview", str(index), "yes", "7"),
                    )
                    for index in range(5)
                ),
            )
        )
        self.assertLessEqual(
            len(normalized.text),
            templates.MAX_BUTTON_TEMPLATE_TEXT_CHARS,
        )
        self.assertEqual(len(normalized.buttons), 3)
        self.assertIn("button_template_text_truncated", normalized.degraded_fields)
        self.assertIn("buttons_truncated", normalized.degraded_fields)


class TemplateTransportTests(TestCase):
    """Э1.2 — отклонённая карточка даёт текстовый эквивалент, а не молчание."""

    def setUp(self):
        from management.models import InstagramBotSettings

        self.settings = InstagramBotSettings.load()
        self.template = templates.GenericTemplate(
            cards=(templates.TemplateCard(title="Худі Vortex", subtitle="Чорне"),),
            fallback_text="Худі Vortex, чорне. Напишіть розмір.",
        )

    def test_rejected_template_falls_back_to_the_prepared_text(self):
        from management.services.instagram_bot import ProviderDeliveryReceipt

        with patch(
            "management.services.instagram_bot._provider_account_id", return_value="1"
        ), patch(
            "management.services.instagram_bot.get_page_token", return_value="t"
        ), patch(
            "management.services.instagram_bot._provider_http",
            return_value=(400, '{"error":{"message":"Invalid parameter: elements"}}'),
        ), patch(
            "management.services.instagram_bot.send_text",
            return_value=ProviderDeliveryReceipt(True, "sent", "", "mid-fallback"),
        ) as send:
            delivery = templates.send_template(self.settings, "igsid-1", self.template)

        self.assertTrue(delivery.ok)
        self.assertTrue(delivery.used_text_fallback)
        self.assertEqual(delivery.provider_message_id, "mid-fallback")
        self.assertEqual(send.call_args.args[2], self.template.fallback_text)

    def test_missing_provider_receipt_is_terminally_unknown(self):
        with patch(
            "management.services.instagram_bot._provider_account_id", return_value="1"
        ), patch(
            "management.services.instagram_bot.get_page_token", return_value="t"
        ), patch(
            "management.services.instagram_bot._provider_http",
            return_value=(200, "{}"),
        ):
            delivery = templates.send_template(self.settings, "igsid-1", self.template)

        self.assertFalse(delivery.ok)
        self.assertEqual(delivery.kind, "unknown")
        self.assertEqual(delivery.hint, "provider_message_id_missing")

    def test_permission_change_cancels_before_provider_io(self):
        from contextlib import contextmanager

        @contextmanager
        def denied():
            yield False

        with patch(
            "management.services.instagram_bot._provider_account_id", return_value="1"
        ), patch(
            "management.services.instagram_bot.get_page_token", return_value="t"
        ), patch(
            "management.services.instagram_bot._provider_http"
        ) as http:
            delivery = templates.send_template(
                self.settings, "igsid-1", self.template,
                permission_boundary_factory=denied,
            )

        http.assert_not_called()
        self.assertEqual(delivery.kind, "cancelled")

    def test_send_text_embeds_a_native_quick_reply_in_the_meta_payload(self):
        from management.services.instagram_bot import send_text

        replies = router.inout_test_quick_replies(7)
        with patch(
            "management.services.instagram_bot._provider_account_id", return_value="1"
        ), patch(
            "management.services.instagram_bot.get_page_token", return_value="t"
        ), patch(
            "management.services.instagram_bot._provider_http",
            return_value=(200, '{"message_id":"mid-quick-reply"}'),
        ) as http:
            receipt = send_text(
                self.settings,
                "igsid-1",
                "Натисніть IN для перевірки.",
                quick_replies=replies,
                return_receipt=True,
            )

        self.assertTrue(receipt.ok)
        payload = json.loads(http.call_args.kwargs["data"].decode("utf-8"))
        self.assertEqual(
            payload["message"]["quick_replies"],
            [
                {
                    "content_type": "text",
                    "title": "IN ✅",
                    "payload": "twc:1:diagnostic:inout:7",
                }
            ],
        )

    def test_button_template_transport_is_receipt_first_and_registers_echo(self):
        button_template = templates.ButtonTemplate(
            text="Отримувати ТТН і статус замовлення тут у Direct?",
            buttons=(
                templates.TemplateButton(
                    templates.BUTTON_POSTBACK,
                    "Так, отримувати",
                    payload=router.build_preview_payload(7, "2", "order_updates"),
                ),
            ),
        )
        with patch(
            "management.services.instagram_bot._provider_account_id", return_value="1"
        ), patch(
            "management.services.instagram_bot.get_page_token", return_value="t"
        ), patch(
            "management.services.instagram_bot._provider_http",
            return_value=(200, '{"message_id":"mid-button-template"}'),
        ) as http, patch(
            "management.services.instagram_bot._register_outgoing_message"
        ) as register:
            delivery = templates.send_button_template(
                self.settings,
                "igsid-1",
                button_template,
            )

        self.assertTrue(delivery.ok)
        self.assertEqual(delivery.provider_message_id, "mid-button-template")
        payload = json.loads(http.call_args.kwargs["data"].decode("utf-8"))
        self.assertEqual(
            payload["message"]["attachment"]["payload"]["template_type"],
            "button",
        )
        register.assert_called_once_with(
            "mid-button-template", "igsid-1", kind="template"
        )


class PostbackIngestionTests(TestCase):
    """Э1.4 — нажатие кнопки доходит как ход клиента, а не теряется."""

    def test_postback_event_becomes_a_customer_turn(self):
        from management.services.instagram_bot import _postback_message_fields

        fields = _postback_message_fields(
            {"payload": "twc:1:parcel:got:42", "title": "Забрав ✅", "mid": "m1"}
        )
        self.assertEqual(fields["quick_reply"], {"payload": "twc:1:parcel:got:42"})
        self.assertEqual(fields["text"], "Забрав ✅")
        self.assertEqual(fields["mid"], "m1")

    def test_payload_without_title_still_produces_a_turn(self):
        from management.services.instagram_bot import _postback_message_fields

        fields = _postback_message_fields({"payload": "twc:1:parcel:later:42"})
        self.assertEqual(fields["text"], "(натиснуто кнопку)")

    def test_subscription_requests_the_postback_field(self):
        import inspect

        from management.services import instagram_bot

        source = inspect.getsource(instagram_bot.ensure_instagram_subscription)
        self.assertIn("messaging_postbacks", source)


class ParcelReminderTests(TestCase):
    """Э6.2 — посылка в отделении: одно напоминание, отмена при получении."""

    def setUp(self):
        self.ig_client = IgClient.get_or_create_for_sender("parcel-sender")

    def _tap(self, payload, text="Забрав"):
        return InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text=text,
            quick_reply_payload=payload,
            status=InstagramBotMessage.Status.PENDING,
        )

    def test_quick_replies_offer_both_deterministic_actions(self):
        replies = router.parcel_quick_replies(42)
        self.assertEqual(len(replies), 2)
        self.assertEqual(replies[0].payload, "twc:1:parcel:got:42")
        self.assertEqual(replies[1].payload, "twc:1:parcel:later:42")
        for reply in replies:
            self.assertLessEqual(
                len(reply.title), templates.MAX_QUICK_REPLY_TITLE_CHARS
            )

    def test_inout_diagnostic_button_is_client_bound_and_deterministic(self):
        replies = router.inout_test_quick_replies(self.ig_client.pk)
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].title, "IN ✅")
        self.assertEqual(
            replies[0].payload,
            f"twc:1:diagnostic:inout:{self.ig_client.pk}",
        )

        row = self._tap(replies[0].payload, text="IN ✅")
        outcome = router.dispatch_postback(row)

        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.action, "diagnostic:inout")
        self.assertIn("Router V2", outcome.reply_text)
        self.assertIn("без Gemini", outcome.reply_text)
        self.assertFalse(outcome.quick_replies)

    def test_inout_diagnostic_payload_for_another_client_is_not_claimed(self):
        other = IgClient.get_or_create_for_sender("other-diagnostic-sender")
        payload = router.inout_test_quick_replies(other.pk)[0].payload

        self.assertIsNone(router.dispatch_postback(self._tap(payload, text="IN ✅")))

    def test_inout_diagnostic_button_rejects_invalid_client_identity(self):
        for invalid in (None, "", "0", "-1", "not-an-id"):
            with self.assertRaises(ValueError):
                router.inout_test_quick_replies(invalid)

    def test_visual_preview_payload_is_client_bound_and_has_no_business_action(self):
        payload = router.build_preview_payload(
            self.ig_client.pk,
            "3",
            "bonuses",
        )
        self.assertEqual(
            payload,
            f"twc:1:preview:3:bonuses:{self.ig_client.pk}",
        )
        outcome = router.dispatch_postback(self._tap(payload, text="Бонуси й новинки"))
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.action, "preview:3:bonuses")
        self.assertIn("preview", outcome.reply_text)
        self.assertFalse(outcome.quick_replies)

        other = IgClient.get_or_create_for_sender("other-preview-client")
        foreign_payload = router.build_preview_payload(other.pk, "3", "bonuses")
        self.assertIsNone(
            router.dispatch_postback(self._tap(foreign_payload, text="Бонуси й новинки"))
        )

    def test_remind_later_schedules_inside_the_reopened_window(self):
        row = self._tap("twc:1:parcel:later:42", text="Нагадати пізніше")
        outcome = router.dispatch_postback(row)

        self.assertIsNotNone(outcome)
        self.assertIn("нагадаю", outcome.reply_text.lower())
        task = IgFollowUpTask.objects.get(reason="parcel_reminder:42")
        self.assertEqual(task.status, IgFollowUpTask.Status.PENDING)
        self.assertTrue(task.message_text)
        # Напоминание должно попасть в переоткрытое нажатием 24-часовое окно.
        self.assertLess(
            (task.due_at - row.created_at).total_seconds(), 24 * 3600
        )

    def test_pickup_confirmation_cancels_the_pending_reminder(self):
        row = self._tap("twc:1:parcel:later:42", text="Нагадати пізніше")
        router.dispatch_postback(row)

        confirmed = self._tap("twc:1:parcel:got:42")
        outcome = router.dispatch_postback(confirmed)

        self.assertIsNotNone(outcome)
        self.assertIn("отримане", outcome.reply_text)
        task = IgFollowUpTask.objects.get(reason="parcel_reminder:42")
        self.assertEqual(task.status, IgFollowUpTask.Status.CANCELLED)
        self.assertEqual(task.skip_reason, "customer_confirmed_pickup")

    def test_pickup_confirmation_also_cancels_an_undelivered_arrival_event(self):
        """Клиент, только что написавший «забрал», не должен получить напоминание."""
        undelivered_states = (
            IgLifecycleEvent.State.PENDING,
            IgLifecycleEvent.State.WAITING_WINDOW,
        )
        with patch.object(IgLifecycleEvent, "objects") as events:
            router._cancel_parcel_reminders(self.ig_client.pk, "42")
            events.filter.assert_called_once()
            kwargs = events.filter.call_args.kwargs
            self.assertEqual(kwargs["client_id"], self.ig_client.pk)
            self.assertEqual(kwargs["kind"], IgLifecycleEvent.Kind.PARCEL_ARRIVED)
            self.assertEqual(tuple(kwargs["state__in"]), undelivered_states)

    def test_unknown_payload_is_not_claimed_by_the_router(self):
        self.assertIsNone(router.dispatch_postback(self._tap("commerce:7:select:2")))
        self.assertIsNone(router.dispatch_postback(self._tap("twc:1:unknown:x")))
        self.assertIsNone(router.dispatch_postback(self._tap("")))

    def test_arrival_event_key_is_one_reminder_per_tracking_number(self):
        from management.services.ig_lifecycle import _event_key

        order = type("_Order", (), {"pk": 42})()
        first = _event_key(
            order, IgLifecycleEvent.Kind.PARCEL_ARRIVED, {"tracking_number": "204"}
        )
        again = _event_key(
            order, IgLifecycleEvent.Kind.PARCEL_ARRIVED, {"tracking_number": "204"}
        )
        other = _event_key(
            order, IgLifecycleEvent.Kind.PARCEL_ARRIVED, {"tracking_number": "205"}
        )
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)

    def test_arrival_copy_never_names_an_unverified_storage_deadline(self):
        from management.services.ig_lifecycle import _message_for

        order = type(
            "_Order", (), {
                "pk": 42, "order_number": "TWC-42",
                "np_office": "Відділення №5", "city": "Київ",
            },
        )()
        for locale in ("uk", "ru", "en"):
            text = _message_for(
                IgLifecycleEvent.Kind.PARCEL_ARRIVED, locale, order,
                {"tracking_number": "20400000000000"},
            )
            self.assertIn("20400000000000", text)
            for forbidden in ("днів", "дней", "days", "до "):
                self.assertNotIn(forbidden, text.casefold())

    def test_cash_on_delivery_arrival_is_not_blocked_by_unverified_payment(self):
        from management.services.ig_lifecycle import _business_truth_cancellation_reason

        order = type(
            "_Order", (), {"pk": 42, "tracking_number": "204", "status": "ship"},
        )()
        with patch(
            "management.services.ig_lifecycle.nova_poshta_order_fulfillment_confirmed",
            return_value=False,
        ):
            reason = _business_truth_cancellation_reason(
                kind=IgLifecycleEvent.Kind.PARCEL_ARRIVED,
                payload={"tracking_number": "204"},
                payment_truth=None,
                order=order,
                assignment_matches=True,
            )
        self.assertEqual(reason, "")

    def test_already_received_parcel_cancels_without_provider_call(self):
        from management.services.ig_lifecycle import _business_truth_cancellation_reason

        order = type("_Order", (), {"pk": 42, "tracking_number": "204"})()
        with patch(
            "management.services.ig_lifecycle.nova_poshta_order_fulfillment_confirmed",
            return_value=True,
        ):
            reason = _business_truth_cancellation_reason(
                kind=IgLifecycleEvent.Kind.PARCEL_ARRIVED,
                payload={"tracking_number": "204"},
                payment_truth=None,
                order=order,
                assignment_matches=True,
            )
        self.assertEqual(reason, "parcel_already_received")
"""Э1.3 — фіксований словарь підписів з перевіркою довжини."""
from django.test import TestCase

from management.services import ig_message_templates as templates




class ButtonLabelDictionaryTests(TestCase):
    """Э1.3 — багатомовний контекстний словник підписів."""

    def test_every_label_fits_the_meta_limit_in_all_languages(self):
        """Кожна підпис ≤20 символів у всіх мовах."""
        for key, langs in templates.BUTTON_LABELS.items():
            if isinstance(langs, dict):
                for lang, label in langs.items():
                    with self.subTest(key=key, lang=lang):
                        self.assertLessEqual(
                            len(label), 20,
                            f"{key}[{lang}] = {label!r} ({len(label)} > 20)"
                        )

    def test_all_labels_have_uk_fallback(self):
        """Кожна кнопка має українську версію (fallback)."""
        for key, langs in templates.BUTTON_LABELS.items():
            with self.subTest(key=key):
                self.assertIn("uk", langs, f"{key} має мати 'uk' версію")

    def test_button_label_returns_requested_language(self):
        """button_label повертає правильну мову."""
        self.assertEqual(templates.button_label("parcel_received", "uk"), "Отримав посилку")
        self.assertEqual(templates.button_label("parcel_received", "ru"), "Получил посылку")
        self.assertEqual(templates.button_label("parcel_received", "en"), "Package received")

    def test_button_label_falls_back_to_uk_for_missing_language(self):
        """Якщо мови немає, fallback на uk."""
        result = templates.button_label("yes", "fr")  # французької немає
        self.assertEqual(result, "Так")  # uk fallback

    def test_button_label_unknown_key_returns_empty(self):
        """Невідомий ключ повертає порожній рядок."""
        self.assertEqual(templates.button_label("nonexistent_key", "uk"), "")

    def test_eliminated_buttons_are_not_in_dictionary(self):
        """Видалені кнопки (manager_contact, repeat_order) відсутні."""
        eliminated = ["manager_contact", "manager_call", "repeat_order", "cancel"]
        for key in eliminated:
            with self.subTest(key=key):
                self.assertNotIn(key, templates.BUTTON_LABELS,
                    f"{key} має бути видалена — це шум без користі")

    def test_contextual_buttons_are_present(self):
        """Контекстні кнопки (посилка, каталог, замовлення) є."""
        required = [
            "parcel_received", "parcel_not_received",
            "catalog_view", "order_confirm", "track_parcel",
            "size_s", "color_black", "yes", "no"
        ]
        for key in required:
            with self.subTest(key=key):
                self.assertIn(key, templates.BUTTON_LABELS)


class DisplayShortTests(TestCase):
    """Э1.3 — коротке ім'я товару замість обрубка з еліпсисом."""

    def test_manual_short_name_takes_precedence(self):
        result = templates.display_short(
            "Худі Vortex Tactical Edition Оверсайз Чорне Бавовна",
            manual="Худі Vortex",
        )
        self.assertEqual(result, "Худі Vortex")

    def test_name_within_the_limit_stays_intact(self):
        short = "Футболка Minimal"
        self.assertEqual(templates.display_short(short), short)

    def test_exactly_at_the_limit_is_not_shortened(self):
        name = "V" * templates.MAX_DISPLAY_SHORT_CHARS
        self.assertEqual(templates.display_short(name), name)

    def test_comma_separates_attributes_from_the_name(self):
        """«Худі Premium, оверсайз, чорне» → «Худі Premium»: після коми атрибути."""
        result = templates.display_short(
            "Худі Premium, оверсайз, чорне, натуральна бавовна"
        )
        self.assertEqual(result, "Худі Premium")

    def test_dash_is_not_treated_as_a_boundary(self):
        """«Vortex - …» НЕ стає «Vortex»: заголовок втратив би тип товару.

        Це свідоме рішення про смак, а не спрощення: карточка з заголовком
        «Vortex» не каже, худі це чи футболка, і клієнту вона гірша за довшу
        назву.
        """
        result = templates.display_short(
            "Vortex - Tactical Edition Оверсайз Чорне Бавовна Преміум"
        )
        self.assertNotEqual(result, "Vortex")
        self.assertTrue(result.startswith("Vortex - "), result)
        self.assertLessEqual(len(result), templates.MAX_DISPLAY_SHORT_CHARS)

    def test_long_name_is_trimmed_on_a_word_boundary_without_an_ellipsis(self):
        """Обрубок з «…» читається як баг інтерфейсу, тому його тут немає."""
        result = templates.display_short(
            "Худі Vortex Tactical Edition Оверсайз Чорне Натуральна Бавовна"
        )
        self.assertLessEqual(len(result), templates.MAX_DISPLAY_SHORT_CHARS)
        self.assertNotIn("…", result)
        self.assertEqual(result, "Худі Vortex Tactical Edition Оверсайз")

    def test_ellipsis_is_the_last_resort_for_one_very_long_word(self):
        """Одне слово довше за ліміт — тут будь-який варіант поганий."""
        result = templates.display_short("Х" * 60)
        self.assertLessEqual(len(result), templates.MAX_DISPLAY_SHORT_CHARS)
        self.assertTrue(result.endswith("…"))

    def test_result_leaves_room_for_a_branch_address_in_the_subtitle(self):
        """Практична межа: коротке ім'я плюс відділення влазить у subtitle."""
        short = templates.display_short(
            "Худі Vortex Tactical Edition Оверсайз Чорне Натуральна Бавовна"
        )
        subtitle = f"{short}, Відділення №123"
        self.assertLessEqual(len(subtitle), templates.MAX_SUBTITLE_CHARS)

    def test_whitespace_is_normalised_before_measuring(self):
        self.assertEqual(
            templates.display_short("  Худі   Vortex  "), "Худі Vortex"
        )
