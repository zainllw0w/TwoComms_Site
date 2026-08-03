"""IMP-057: evidence-bound objection lifecycle and reply handling."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone

from management.models import (
    BotInstruction,
    IgClient,
    IgCommercialEpisode,
    IgConversationSignal,
    IgFunnelResetAudit,
    IgObjection,
    IgObjectionAttempt,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import bot_sales_classifier
from management.services.ig_objections import (
    detect_objection_type,
    objection_prompt_note,
    observe_inbound_objection,
    observe_inbound_progress,
    record_reply_attempt,
)


class ObjectionDetectionTests(SimpleTestCase):
    def test_plain_questions_are_not_true_objections(self):
        for text in (
            "Скільки коштує футболка?",
            "Яка ціна термохромної футболки?",
            "Сколько ждать доставку?",
            "Можно оплатить с предоплатой?",
            "Какой размер мне выбрать?",
            "Яка якість принта?",
        ):
            with self.subTest(text=text):
                self.assertEqual(detect_objection_type(text), "")

    def test_all_twelve_true_objection_types_are_detected(self):
        cases = {
            "Це занадто дорого для мене": "price",
            "Я ще подумаю і напишу пізніше": "thinking",
            "Боюся, що цей розмір мені не підійде": "size_risk",
            "Не довіряю передоплаті": "prepayment_trust",
            "Боюся, що прийде товар із браком": "defect_risk",
            "Це надто довго, я не встигну отримати": "delivery_time",
            "В іншому магазині є дешевше": "cheaper_elsewhere",
            "Боюся, що принт потріскається після прання": "print_quality",
            "Немає мого розміру в наявності": "out_of_stock",
            "Зможу купити тільки після зарплати": "payday",
            "Порівнюю вас з іншим брендом": "compare_brand",
            "Спитаю у дружини і тоді вирішу": "ask_partner",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(detect_objection_type(text), expected)


class ObjectionClassifierTests(TestCase):
    def _message(self, client, text):
        return InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text=text,
        )

    def test_product_price_question_keeps_price_intent_without_objection(self):
        client = IgClient.get_or_create_for_sender("objection-price-question")
        message = self._message(client, "Скільки коштує біла футболка?")

        result = bot_sales_classifier.classify_message(client, message=message)

        client.refresh_from_db()
        self.assertEqual(client.intent, IgClient.Intent.PRICE)
        self.assertEqual(client.primary_objection, IgClient.Objection.NONE)
        self.assertNotIn(IgConversationSignal.Type.PRICE_OBJECTION, result["signals"])

    def test_hard_price_objection_still_creates_price_signal(self):
        client = IgClient.get_or_create_for_sender("objection-hard-price")
        message = self._message(client, "Дорого, мені не по кишені")

        result = bot_sales_classifier.classify_message(client, message=message)

        client.refresh_from_db()
        self.assertEqual(client.primary_objection, IgClient.Objection.PRICE)
        self.assertIn(IgConversationSignal.Type.PRICE_OBJECTION, result["signals"])

    def test_thinking_objection_is_written_as_a_signal(self):
        client = IgClient.get_or_create_for_sender("objection-thinking-signal")
        message = self._message(client, "Я ще подумаю і напишу пізніше")

        result = bot_sales_classifier.classify_message(client, message=message)

        self.assertIn(IgConversationSignal.Type.THINKING_OBJECTION, result["signals"])
        self.assertTrue(
            IgConversationSignal.objects.filter(
                client=client,
                message=message,
                signal_type=IgConversationSignal.Type.THINKING_OBJECTION,
            ).exists()
        )

    def test_classifier_materializes_one_lifecycle_per_type_and_episode(self):
        client = IgClient.get_or_create_for_sender("objection-classifier-lifecycle")
        message = self._message(client, "Це занадто дорого для мене")

        bot_sales_classifier.classify_message(client, message=message)
        bot_sales_classifier.classify_message(client, message=message)

        objection = IgObjection.objects.get(client=client)
        self.assertEqual(objection.objection_type, IgObjection.Type.PRICE)
        self.assertEqual(objection.first_message_id, message.pk)
        self.assertEqual(objection.last_message_id, message.pk)
        self.assertEqual(objection.repeat_count, 1)

    def test_compound_turn_materializes_each_distinct_objection(self):
        client = IgClient.get_or_create_for_sender("objection-compound-lifecycle")
        message = self._message(
            client,
            "Це дорого і я боюся, що розмір мені не підійде",
        )

        result = bot_sales_classifier.classify_message(client, message=message)

        self.assertEqual(
            set(IgObjection.objects.filter(client=client).values_list(
                "objection_type", flat=True,
            )),
            {IgObjection.Type.PRICE, IgObjection.Type.SIZE_RISK},
        )
        self.assertEqual(
            set(result["objection_lifecycle_types"]),
            {IgObjection.Type.PRICE, IgObjection.Type.SIZE_RISK},
        )

    def test_checkout_intent_accepts_handling_without_claiming_purchase(self):
        client = IgClient.get_or_create_for_sender("objection-checkout-not-purchased")
        objection_message = self._message(client, "Це занадто дорого для мене")
        bot_sales_classifier.classify_message(client, message=objection_message)
        reply = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.MODEL,
            text="Щільна тканина і DTF-друк пояснюють цінність речі.",
        )
        attempt = record_reply_attempt(
            client,
            reply,
            {"objhandle": "price:value_breakdown"},
            reply.text,
        )
        checkout_message = self._message(client, "Добре, беру білу у розмірі XL")

        result = bot_sales_classifier.classify_message(client, message=checkout_message)

        objection = IgObjection.objects.get(client=client)
        attempt.refresh_from_db()
        self.assertIn(IgConversationSignal.Type.CHECKOUT_STARTED, result["signals"])
        self.assertEqual(objection.state, IgObjection.State.RESOLVED)
        self.assertEqual(objection.outcome, IgObjection.Outcome.UNRESOLVED)
        self.assertEqual(attempt.result, IgObjectionAttempt.Result.ACCEPTED)

    def test_lifecycle_failure_is_logged_without_blocking_classification(self):
        client = IgClient.get_or_create_for_sender("objection-lifecycle-log")
        message = self._message(client, "Це занадто дорого для мене")

        with patch(
            "management.services.ig_objections.detect_objection_types",
            side_effect=RuntimeError("lifecycle unavailable"),
        ), self.assertLogs(
            "management.services.bot_sales_classifier", level="ERROR",
        ) as captured:
            result = bot_sales_classifier.classify_message(client, message=message)

        self.assertEqual(result["objection_lifecycle_type"], "")
        self.assertIn("lifecycle unavailable", "\n".join(captured.output))


class ObjectionLifecycleTests(TestCase):
    def setUp(self):
        self.client = IgClient.get_or_create_for_sender("objection-lifecycle")
        self.inbound = self._message("Це занадто дорого для мене")
        self.objection = observe_inbound_objection(
            self.client,
            self.inbound,
            IgObjection.Type.PRICE,
            readiness=20,
        )

    def _message(self, text, *, role=InstagramBotMessage.Role.USER):
        return InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=role,
            text=text,
        )

    def test_handled_requires_matching_type_method_and_text_fingerprint(self):
        weak_reply = self._message("Розумію вас.", role=InstagramBotMessage.Role.MODEL)
        weak = record_reply_attempt(
            self.client,
            weak_reply,
            {"objhandle": "price:value_breakdown"},
            weak_reply.text,
        )

        self.objection.refresh_from_db()
        self.assertFalse(weak.verified)
        self.assertEqual(weak.result, IgObjectionAttempt.Result.IGNORED)
        self.assertEqual(self.objection.state, IgObjection.State.OPEN)

        strong_reply = self._message(
            "Щільна тканина і DTF-друк пояснюють цінність речі.",
            role=InstagramBotMessage.Role.MODEL,
        )
        strong = record_reply_attempt(
            self.client,
            strong_reply,
            {"objhandle": "price:value_breakdown"},
            strong_reply.text,
        )

        self.objection.refresh_from_db()
        self.assertTrue(strong.verified)
        self.assertEqual(self.objection.state, IgObjection.State.HANDLED)
        self.assertEqual(self.objection.resolution_method, "value_breakdown")

    def test_method_for_another_objection_type_never_marks_handled(self):
        reply = self._message(
            "Щільна тканина і DTF-друк пояснюють цінність речі.",
            role=InstagramBotMessage.Role.MODEL,
        )

        attempt = record_reply_attempt(
            self.client,
            reply,
            {"objhandle": "size_risk:value_breakdown"},
            reply.text,
        )

        self.objection.refresh_from_db()
        self.assertFalse(attempt.verified)
        self.assertEqual(attempt.verification_reason, "objection_type_mismatch")
        self.assertEqual(self.objection.state, IgObjection.State.OPEN)

    def test_missing_tag_is_recorded_as_ignored_not_handled(self):
        reply = self._message("Розумію вас.", role=InstagramBotMessage.Role.MODEL)

        attempt = record_reply_attempt(self.client, reply, {}, reply.text)

        self.objection.refresh_from_db()
        self.assertEqual(attempt.method, "none")
        self.assertEqual(attempt.verification_reason, "missing_objhandle")
        self.assertEqual(self.objection.state, IgObjection.State.OPEN)

    def test_same_objection_after_verified_attempt_reopens_it(self):
        reply = self._message(
            "Щільна тканина і DTF-друк пояснюють цінність речі.",
            role=InstagramBotMessage.Role.MODEL,
        )
        attempt = record_reply_attempt(
            self.client,
            reply,
            {"objhandle": "price:value_breakdown"},
            reply.text,
        )
        repeated = self._message("Все одно дорого")

        observe_inbound_objection(
            self.client,
            repeated,
            IgObjection.Type.PRICE,
            readiness=10,
        )

        self.objection.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(self.objection.state, IgObjection.State.OPEN)
        self.assertEqual(self.objection.repeat_count, 2)
        self.assertEqual(attempt.result, IgObjectionAttempt.Result.RE_OBJECTED)
        self.assertEqual(attempt.client_response_message_id, repeated.pk)

    def test_next_positive_client_step_resolves_handled_objection(self):
        reply = self._message(
            "Щільна тканина і DTF-друк пояснюють цінність речі.",
            role=InstagramBotMessage.Role.MODEL,
        )
        attempt = record_reply_attempt(
            self.client,
            reply,
            {"objhandle": "price:value_breakdown"},
            reply.text,
        )
        progress = self._message("Добре, беру білу в розмірі XL")

        observe_inbound_progress(
            self.client,
            progress,
            objection_type="",
            readiness=70,
        )

        self.objection.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(self.objection.state, IgObjection.State.RESOLVED)
        self.assertEqual(attempt.result, IgObjectionAttempt.Result.ACCEPTED)
        self.assertEqual(attempt.client_response_message_id, progress.pk)

    def test_explicit_refusal_abandons_open_and_handled_objections(self):
        refusal = self._message("Не буду купувати")

        observe_inbound_progress(
            self.client,
            refusal,
            objection_type="",
            readiness=0,
            abandoned=True,
        )

        self.objection.refresh_from_db()
        self.assertEqual(self.objection.state, IgObjection.State.ABANDONED)
        self.assertEqual(self.objection.outcome, IgObjection.Outcome.LOST)

    def test_reset_boundary_hides_old_objection_and_allows_new_same_type(self):
        episode = IgCommercialEpisode.objects.create(
            client=self.client,
            sequence=1,
            materialization_key="objection-reset-boundary",
            opened_watermark_message_id=self.inbound.pk,
        )
        self.client.current_commercial_episode = episode
        self.client.save(update_fields=["current_commercial_episode", "updated_at"])
        self.objection.episode = episode
        self.objection.dedupe_key = (
            f"ig-objection:{self.client.pk}:episode:{episode.pk}:floor:{self.inbound.pk}:price"
        )
        self.objection.save(update_fields=["episode", "dedupe_key", "updated_at"])
        IgFunnelResetAudit.objects.create(
            client=self.client,
            reset_after_message_id=self.inbound.pk,
            reason="test_reset",
        )

        self.assertEqual(objection_prompt_note(self.client), "")

        new_message = self._message("Все одно дорого після скидання")
        new_objection = observe_inbound_objection(
            self.client,
            new_message,
            IgObjection.Type.PRICE,
            readiness=15,
        )

        self.assertNotEqual(new_objection.pk, self.objection.pk)
        self.assertEqual(IgObjection.objects.filter(client=self.client).count(), 2)


class ObjectionPromptTests(TestCase):
    def setUp(self):
        self.client = IgClient.get_or_create_for_sender("objection-prompt")
        self.inbound = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Це дорого",
        )
        self.objection = observe_inbound_objection(
            self.client,
            self.inbound,
            IgObjection.Type.PRICE,
            readiness=20,
        )

    def test_prompt_shows_failed_method_and_is_injected_into_system_instruction(self):
        reply = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Щільна тканина і DTF-друк пояснюють цінність речі.",
        )
        attempt = record_reply_attempt(
            self.client,
            reply,
            {"objhandle": "price:value_breakdown"},
            reply.text,
        )
        repeated = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Все одно дорого",
        )
        observe_inbound_objection(
            self.client,
            repeated,
            IgObjection.Type.PRICE,
            readiness=10,
        )
        attempt.refresh_from_db()

        from management.services.instagram_bot import assemble_system_instruction

        note = objection_prompt_note(self.client)
        prompt = assemble_system_instruction(
            InstagramBotSettings.load(),
            client=self.client,
            turn_text=repeated.text,
        )

        self.assertIn("price", note)
        self.assertIn("value_breakdown", note)
        self.assertIn(IgObjectionAttempt.Result.RE_OBJECTED, note)
        self.assertIn("[ЗАПЕРЕЧЕННЯ", prompt)
        self.assertIn("value_breakdown", prompt)

    def test_prompt_is_suppressed_during_manager_takeover(self):
        self.client.manager_takeover = True
        self.client.save(update_fields=["manager_takeover", "updated_at"])

        self.assertEqual(objection_prompt_note(self.client), "")


class ObjectionPlaybookTests(TestCase):
    def test_seed_creates_twelve_editable_objection_instructions(self):
        call_command("seed_ig_bot_sales_playbooks", stdout=StringIO())

        rows = BotInstruction.objects.filter(title__startswith="IG Objection · ")
        self.assertEqual(rows.count(), 12)
        self.assertEqual(
            set(rows.values_list("intent_tags", flat=True)),
            {f"objection_{value}" for value, _label in IgObjection.Type.choices},
        )

    def test_lifecycle_tag_failure_keeps_base_routing_and_is_logged(self):
        from management.services import bot_playbooks

        client = IgClient.get_or_create_for_sender("objection-playbook-log")
        with patch(
            "management.services.ig_objections.objection_tags_for_client",
            side_effect=RuntimeError("tag projection unavailable"),
        ), self.assertLogs(
            "management.services.bot_playbooks", level="WARNING",
        ) as captured:
            tags = bot_playbooks.tags_for_client(client)

        self.assertIn("sales", tags)
        self.assertIn("tag projection unavailable", "\n".join(captured.output))


class ObjectionConfirmedSendTests(TransactionTestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.ai_enabled = True
        self.settings.allowed_senders = ""
        self.settings.save(update_fields=[
            "is_enabled", "ai_enabled", "allowed_senders", "updated_at",
        ])
        self.client = IgClient.get_or_create_for_sender("objection-confirmed-send")
        self.client.profile_fetched_at = timezone.now()
        self.client.save(update_fields=["profile_fetched_at", "updated_at"])
        opened = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Це дорого",
            status=InstagramBotMessage.Status.DONE,
        )
        observe_inbound_objection(
            self.client,
            opened,
            IgObjection.Type.PRICE,
            readiness=20,
        )

    def _pending_row(self, suffix):
        return InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text=f"Поясніть ціну {suffix}",
            status=InstagramBotMessage.Status.PROCESSING,
            processing_started_at=timezone.now(),
        )

    def _run(self, row, send_result):
        from management.services import instagram_bot

        with patch(
            "management.services.bot_sales_classifier.ensure_rule_classification",
            return_value=None,
        ), patch(
            "management.services.instagram_bot._rate_exceeded", return_value=False,
        ), patch(
            "management.services.instagram_bot._repeated_question", return_value=0,
        ), patch(
            "management.services.instagram_bot.send_sender_action",
        ), patch(
            "management.services.instagram_bot.gemini_generate",
            return_value=(
                "Щільна тканина і DTF-друк пояснюють цінність речі. "
                "[OBJHANDLE:price:value_breakdown]"
            ),
        ), patch(
            "management.services.instagram_bot.send_text", return_value=send_result,
        ), patch(
            "management.services.instagram_bot.notify_manager",
        ):
            return instagram_bot._process_one(self.settings, row)

    def test_attempt_is_recorded_only_after_confirmed_provider_send(self):
        row = self._pending_row("success")

        self.assertTrue(self._run(row, (True, "", "")))

        attempt = IgObjectionAttempt.objects.get(objection__client=self.client)
        self.assertTrue(attempt.verified)
        self.assertEqual(attempt.reply_message.role, InstagramBotMessage.Role.MODEL)
        self.assertNotIn("OBJHANDLE", attempt.reply_message.text)

    def test_failed_provider_send_does_not_claim_objection_handling(self):
        row = self._pending_row("failure")

        self.assertFalse(self._run(row, (False, "permanent", "blocked")))

        self.assertFalse(IgObjectionAttempt.objects.filter(
            objection__client=self.client,
        ).exists())

    def test_lifecycle_db_failure_does_not_rollback_sent_message_ledger(self):
        row = self._pending_row("lifecycle-db-failure")
        duplicate_mid = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="provider duplicate fixture",
            mid="objection-ledger-duplicate-mid",
            status=InstagramBotMessage.Status.DONE,
        )

        def fail_lifecycle(*_args, **_kwargs):
            InstagramBotMessage.objects.create(
                sender_id=self.client.igsid,
                client=self.client,
                role=InstagramBotMessage.Role.MODEL,
                text="duplicate",
                mid=duplicate_mid.mid,
            )

        with patch(
            "management.services.ig_objections.record_reply_attempt",
            side_effect=fail_lifecycle,
        ):
            self.assertTrue(self._run(row, (True, "", "")))

        self.assertTrue(InstagramBotMessage.objects.filter(
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Щільна тканина і DTF-друк пояснюють цінність речі.",
        ).exists())
