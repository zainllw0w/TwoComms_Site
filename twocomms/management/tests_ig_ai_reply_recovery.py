from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, InstagramBotMessage, InstagramBotSettings
from management.services.instagram_bot import ProviderDeliveryReceipt


class IgAIReplyRecoveryTests(TestCase):
    def setUp(self):
        from management.services import ig_ai_reply_recovery as recovery

        self.recovery = recovery
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled"])
        self.client = IgClient.get_or_create_for_sender("recovery-sender")
        self.source = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Привіт",
            status=InstagramBotMessage.Status.DONE,
            send_state="sent",
        )

    def test_schedule_is_one_durable_intent(self):
        first = self.recovery.schedule_recovery(self.source)
        second = self.recovery.schedule_recovery(self.source)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.recovery.IgAiReplyRecoveryJob.objects.count(), 1)

    def test_prepared_recovery_is_inert_until_holding_delivery_is_confirmed(self):
        job = self.recovery.schedule_recovery(self.source, activate=False)
        holding = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Зараз відновлю деталі.",
            status=InstagramBotMessage.Status.DONE,
            source="ai_fallback",
            send_state="sent",
            provider_message_id="holding-confirmed-1",
        )

        with patch.object(self.recovery, "send_text") as send:
            self.recovery.process_recovery_job(job.pk)

        job.refresh_from_db()
        self.assertIsNone(job.activated_at)
        self.assertEqual(job.status, job.Status.PENDING)
        send.assert_not_called()

        self.recovery.activate_recovery(job, holding_message=holding)
        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
            return_value="Вибачте за затримку. Уже відповідаю.",
        ), patch.object(
            self.recovery,
            "send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "recovery-activated-1"),
        ) as send:
            result = self.recovery.process_recovery_job(job.pk)

        result.refresh_from_db()
        self.assertEqual(result.status, result.Status.SENT)
        self.assertIsNotNone(result.activated_at)
        send.assert_called_once()

    def test_unconfirmed_holding_terminalizes_prepared_recovery_without_sending(self):
        job = self.recovery.schedule_recovery(self.source, activate=False)

        self.recovery.terminalize_prepared_recovery(
            job,
            reason="holding_provider_message_id_missing",
            ambiguous=True,
        )

        job.refresh_from_db()
        self.assertEqual(job.status, job.Status.AMBIGUOUS)
        self.assertEqual(job.last_error, "holding_provider_message_id_missing")
        self.assertIsNotNone(job.completed_at)
        self.assertEqual(self.recovery.process_due_recoveries(limit=1), 0)

    def test_worker_reconciles_confirmed_holding_for_prepared_recovery(self):
        job = self.recovery.schedule_recovery(self.source, activate=False)
        holding = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Зараз уточню деталі.",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
            provider_message_id="holding-reconcile-1",
        )
        self.recovery.schedule_recovery(
            self.source,
            holding_message=holding,
            activate=False,
        )

        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
            return_value="Вибачте за затримку. Вже відповідаю.",
        ), patch.object(
            self.recovery,
            "send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "reconciled-recovery-1"),
        ):
            self.assertEqual(self.recovery.process_due_recoveries(limit=1), 1)

        job.refresh_from_db()
        self.assertIsNotNone(job.activated_at)
        self.assertEqual(job.status, job.Status.SENT)

    def test_generation_failure_is_deferred_before_the_next_recovery_attempt(self):
        job = self.recovery.schedule_recovery(self.source)

        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
            side_effect=RuntimeError("temporary Gemini failure"),
        ):
            result = self.recovery.process_recovery_job(job.pk)

        result.refresh_from_db()
        self.assertEqual(result.status, result.Status.PENDING)
        self.assertGreater(result.next_attempt_at, timezone.now())
        self.assertEqual(self.recovery.process_due_recoveries(limit=1), 0)

    @patch("management.services.ig_ai_reply_recovery.notify_manager")
    def test_generation_failure_terminalizes_after_bounded_recovery_attempts(self, notify_manager):
        job = self.recovery.schedule_recovery(self.source)
        job.attempts = self.recovery.MAX_RECOVERY_ATTEMPTS - 1
        job.save(update_fields=["attempts"])

        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
            side_effect=RuntimeError("persistent Gemini failure"),
        ):
            result = self.recovery.process_recovery_job(job.pk)

        result.refresh_from_db()
        self.assertEqual(result.status, result.Status.FAILED)
        self.assertIsNotNone(result.completed_at)
        self.assertIsNone(result.next_attempt_at)
        notify_manager.assert_called_once()

    def test_generated_recovery_always_includes_technical_delay_apology(self):
        job = self.recovery.schedule_recovery(self.source)

        with patch.object(
            self.recovery,
            "gemini_generate",
            return_value="Вітаю! Чим можу допомогти?",
        ):
            draft = self.recovery._generate_recovery_draft(job)

        self.assertTrue(draft.startswith("Вибачте за технічну затримку."))
        self.assertIn("Вітаю! Чим можу допомогти?", draft)

    def test_generated_recovery_consumes_typed_reply_text_without_dataclass_leak(self):
        from management.services.ig_response_control import ValidatedResponse

        job = self.recovery.schedule_recovery(self.source)
        generated = ValidatedResponse(reply_text="Підкажу по наявності.")

        with patch.object(self.recovery, "gemini_generate", return_value=generated):
            draft = self.recovery._generate_recovery_draft(job)

        self.assertIn("Підкажу по наявності.", draft)
        self.assertNotIn("ValidatedResponse", draft)

    def test_generated_recovery_rejects_invalid_typed_reply_without_delivery_text(self):
        from management.services.ig_response_control import ValidatedResponse

        job = self.recovery.schedule_recovery(self.source)
        generated = ValidatedResponse(
            reply_text="unsafe provider text",
            valid=False,
            error="invalid_reply_text",
        )

        with patch.object(self.recovery, "gemini_generate", return_value=generated):
            draft = self.recovery._generate_recovery_draft(job)

        self.assertEqual(draft, "")

    def test_generated_recovery_rejects_non_string_provider_payload(self):
        job = self.recovery.schedule_recovery(self.source)

        with patch.object(self.recovery, "gemini_generate", return_value={"reply_text": "leak"}):
            draft = self.recovery._generate_recovery_draft(job)

        self.assertEqual(draft, "")

    def test_invalid_typed_recovery_reply_is_not_deliverable(self):
        from management.services.ig_response_control import ValidatedResponse

        job = self.recovery.schedule_recovery(self.source)
        generated = ValidatedResponse(
            reply_text="x" * 4001,
            valid=False,
            error="invalid_reply_text",
        )

        with patch.object(self.recovery, "gemini_generate", return_value=generated):
            draft = self.recovery._generate_recovery_draft(job)

        self.assertEqual(draft, "")

    def test_generated_recovery_uses_russian_apology_for_russian_turn(self):
        self.source.text = "Привет, нужна футболка"
        self.source.save(update_fields=["text"])
        job = self.recovery.schedule_recovery(self.source)

        with patch.object(
            self.recovery,
            "gemini_generate",
            return_value="Подскажу по наличию.",
        ):
            draft = self.recovery._generate_recovery_draft(job)

        self.assertTrue(draft.startswith("Извините за техническую задержку."))

    def test_generated_recovery_prefixes_technical_delay_apology_despite_generic_apology(self):
        job = self.recovery.schedule_recovery(self.source)
        generated = "Вітаю! Sorry, що відповідь затрималась. Чим можу допомогти?"

        with patch.object(
            self.recovery,
            "gemini_generate",
            return_value=generated,
        ):
            draft = self.recovery._generate_recovery_draft(job)

        self.assertTrue(draft.startswith("Вибачте за технічну затримку."))
        self.assertIn(generated, draft)

    def test_generated_recovery_does_not_duplicate_exact_localized_apology(self):
        self.source.text = "Hello, what sizes do you have?"
        self.source.save(update_fields=["text"])
        job = self.recovery.schedule_recovery(self.source)
        generated = "Sorry for the technical delay. I can help you choose a size."

        with patch.object(
            self.recovery,
            "gemini_generate",
            return_value=generated,
        ):
            draft = self.recovery._generate_recovery_draft(job)

        self.assertEqual(draft, generated)

    def test_generated_recovery_does_not_duplicate_localized_apology_with_punctuation(self):
        job = self.recovery.schedule_recovery(self.source)
        generated = "Вибачте за технічну затримку! Підкажу по наявності."

        with patch.object(
            self.recovery,
            "gemini_generate",
            return_value=generated,
        ):
            draft = self.recovery._generate_recovery_draft(job)

        self.assertEqual(draft, generated)

    def test_generated_recovery_with_apology_stays_in_one_meta_chunk(self):
        job = self.recovery.schedule_recovery(self.source)
        generated = "Підкажу по наявності. " * 200

        with patch.object(
            self.recovery,
            "gemini_generate",
            return_value=generated,
        ):
            draft = self.recovery._generate_recovery_draft(job)

        self.assertTrue(draft.startswith("Вибачте за технічну затримку."))
        self.assertLessEqual(
            len(draft.encode("utf-8")),
            self.recovery.MAX_RECOVERY_REPLY_CHARS,
        )

    def test_newer_inbound_cancels_before_gemini(self):
        job = self.recovery.schedule_recovery(self.source)
        InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Нове питання",
            status=InstagramBotMessage.Status.DONE,
        )

        with patch.object(self.recovery, "_generate_recovery_draft") as generate:
            self.recovery.process_recovery_job(job.pk)

        job.refresh_from_db()
        self.assertEqual(job.status, job.Status.CANCELLED)
        generate.assert_not_called()

    def test_recovery_history_ends_at_the_failed_customer_turn(self):
        holding = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Коротка технічна затримка, будь ласка, зачекайте.",
            status=InstagramBotMessage.Status.DONE,
            source="ai_fallback",
            send_state="sent",
            provider_message_id="holding-1",
        )
        later = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Нове повідомлення, яке не належить старому turn.",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
        )
        job = self.recovery.schedule_recovery(self.source, holding_message=holding)

        history = self.recovery._build_recovery_history(job)
        texts = [item["text"] for item in history]

        self.assertIn(self.source.text, texts)
        self.assertNotIn(holding.text, texts)
        self.assertNotIn(later.text, texts)

    def test_confirmed_receipt_finalizes_and_is_idempotent(self):
        job = self.recovery.schedule_recovery(self.source)
        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
            return_value="Зараз підкажу, чим можу допомогти.",
        ), patch.object(
            self.recovery,
            "send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "meta-recovery-1"),
        ) as send:
            result = self.recovery.process_recovery_job(job.pk)
            again = self.recovery.process_recovery_job(job.pk)

        result.refresh_from_db()
        self.assertEqual(result.status, result.Status.SENT)
        self.assertEqual(result.provider_message_id, "meta-recovery-1")
        self.assertEqual(again.pk, result.pk)
        send.assert_called_once()
        self.client.refresh_from_db()
        self.assertIsNotNone(self.client.last_bot_reply_at)

    def test_recovery_persists_actual_fallback_model_on_reply_message(self):
        job = self.recovery.schedule_recovery(self.source)

        def generate_with_fallback(*_args, failure_context=None, **_kwargs):
            failure_context["model"] = "gemini-3.6-flash"
            return "Підкажу по наявності."

        with patch.object(
            self.recovery,
            "gemini_generate",
            side_effect=generate_with_fallback,
        ), patch.object(
            self.recovery,
            "send_text",
            return_value=ProviderDeliveryReceipt(
                True, "", "", "meta-recovery-fallback-model-1"
            ),
        ):
            result = self.recovery.process_recovery_job(job.pk)

        result.refresh_from_db()
        result.reply_message.refresh_from_db()
        self.assertEqual(result.status, result.Status.SENT)
        self.assertEqual(result.reply_message.gemini_model, "gemini-3.6-flash")

    def test_persisted_recovery_draft_is_normalized_before_its_first_meta_send(self):
        job = self.recovery.schedule_recovery(self.source)
        job.draft_text = "Вітаю! Чим можу допомогти?"
        reply_message = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text=job.draft_text,
            status=InstagramBotMessage.Status.PROCESSING,
            source="ai_recovery",
            send_state="",
        )
        job.reply_message = reply_message
        job.save(update_fields=["draft_text", "reply_message"])

        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
        ) as generate, patch.object(
            self.recovery,
            "send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "meta-recovery-persisted-1"),
        ) as send:
            result = self.recovery.process_recovery_job(job.pk)

        result.refresh_from_db()
        self.assertEqual(result.status, result.Status.SENT)
        self.assertTrue(
            result.draft_text.startswith("Вибачте за технічну затримку.")
        )
        self.assertIn("Вітаю! Чим можу допомогти?", result.draft_text)
        generate.assert_not_called()
        self.assertEqual(send.call_args.args[2], result.draft_text)
        result.reply_message.refresh_from_db()
        self.assertEqual(result.reply_message.text, result.draft_text)


    def test_missing_provider_receipt_is_ambiguous_and_not_retried(self):
        job = self.recovery.schedule_recovery(self.source)
        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
            return_value="Технічну затримку вже виправлено.",
        ), patch.object(
            self.recovery,
            "send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", ""),
        ) as send:
            result = self.recovery.process_recovery_job(job.pk)
            again = self.recovery.process_recovery_job(job.pk)

        result.refresh_from_db()
        self.assertEqual(result.status, result.Status.AMBIGUOUS)
        self.assertEqual(again.pk, result.pk)
        send.assert_called_once()

    def test_invalid_provider_receipt_ids_are_ambiguous_not_coerced_or_truncated(self):
        for suffix, provider_message_id in (
            ("numeric", 123),
            ("overlong", "m" * 256),
        ):
            with self.subTest(receipt=suffix):
                source = InstagramBotMessage.objects.create(
                    sender_id=self.client.igsid,
                    client=self.client,
                    role=InstagramBotMessage.Role.USER,
                    text=f"Receipt case: {suffix}",
                    status=InstagramBotMessage.Status.DONE,
                    send_state="sent",
                )
                job = self.recovery.schedule_recovery(source)
                with patch.object(
                    self.recovery,
                    "_generate_recovery_draft",
                    return_value="Технічну затримку вже виправлено.",
                ), patch.object(
                    self.recovery,
                    "send_text",
                    return_value=ProviderDeliveryReceipt(
                        True,
                        "",
                        "",
                        provider_message_id,
                    ),
                ) as send:
                    result = self.recovery.process_recovery_job(job.pk)
                    again = self.recovery.process_recovery_job(job.pk)

                result.refresh_from_db()
                self.assertEqual(result.status, result.Status.AMBIGUOUS)
                self.assertEqual(result.provider_message_id, "")
                self.assertEqual(again.pk, result.pk)
                result.reply_message.refresh_from_db()
                self.assertEqual(result.reply_message.send_state, "unknown")
                self.assertEqual(result.reply_message.provider_message_id, "")
                self.client.refresh_from_db()
                self.assertIsNone(self.client.last_bot_reply_at)
                send.assert_called_once()

    def test_recovery_draft_fits_one_meta_send_request(self):
        from management.services.instagram_bot import _split_for_send

        draft = self.recovery._trim_draft("слово " * 500)

        self.assertLessEqual(len(draft.encode("utf-8")), 950)
        self.assertEqual(len(_split_for_send(draft)), 1)

    def test_recovery_draft_uses_fail_closed_control_sanitizer(self):
        draft = self.recovery._trim_draft(
            "Підкажу по наявності. [manager] [MANAGER:false]"
        )

        self.assertEqual(draft, "Підкажу по наявності.")

    def test_draft_and_history_row_exist_before_meta_request(self):
        job = self.recovery.schedule_recovery(self.source)

        def inspect_durable_boundary(*_args, **_kwargs):
            job.refresh_from_db()
            self.assertEqual(job.status, job.Status.SENDING)
            self.assertEqual(job.draft_text, "Вибачте за затримку. Вже відповідаю.")
            self.assertIsNotNone(job.reply_message_id)
            job.reply_message.refresh_from_db()
            self.assertEqual(job.reply_message.send_state, "sending")
            return ProviderDeliveryReceipt(True, "", "", "meta-recovery-2")

        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
            return_value="Вибачте за затримку. Вже відповідаю.",
        ), patch.object(self.recovery, "send_text", side_effect=inspect_durable_boundary):
            result = self.recovery.process_recovery_job(job.pk)

        result.refresh_from_db()
        self.assertEqual(result.status, result.Status.SENT)

    def test_stale_sending_job_becomes_ambiguous_without_meta_replay(self):
        job = self.recovery.schedule_recovery(self.source)
        job.status = job.Status.SENDING
        job.lease_token = "old-worker"
        job.lease_until = timezone.now() - timedelta(seconds=1)
        job.save(update_fields=["status", "lease_token", "lease_until"])

        with patch.object(self.recovery, "send_text") as send:
            result = self.recovery.process_recovery_job(job.pk)

        result.refresh_from_db()
        self.assertEqual(result.status, result.Status.AMBIGUOUS)
        send.assert_not_called()

    def test_command_defaults_to_read_only_dry_run(self):
        output = StringIO()

        call_command(
            "recover_ig_ai_reply",
            source_message=str(self.source.pk),
            stdout=output,
        )

        self.assertIn("dry_run", output.getvalue())
        self.assertFalse(
            self.recovery.IgAiReplyRecoveryJob.objects.filter(
                source_message=self.source,
            ).exists()
        )

    def test_command_requires_explicit_acknowledgement_for_legacy_unreceipted_holding(self):
        holding = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Зараз передам менеджеру.",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
        )

        with self.assertRaisesMessage(CommandError, "unreceipted_holding_not_acknowledged"):
            call_command(
                "recover_ig_ai_reply",
                source_message=str(self.source.pk),
                holding_message=str(holding.pk),
                execute=True,
            )

        self.assertFalse(
            self.recovery.IgAiReplyRecoveryJob.objects.filter(
                source_message=self.source,
            ).exists()
        )

    def test_command_recovers_with_explicit_acknowledged_legacy_unreceipted_holding(self):
        holding = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Зараз передам менеджеру.",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
        )
        output = StringIO()

        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
            return_value="Вибачте за технічну затримку. Я вже на зв'язку.",
        ), patch.object(
            self.recovery,
            "send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "meta-recovery-legacy-1"),
        ) as send:
            call_command(
                "recover_ig_ai_reply",
                source_message=str(self.source.pk),
                holding_message=str(holding.pk),
                acknowledge_unreceipted_holding=True,
                execute=True,
                stdout=output,
            )

        job = self.recovery.IgAiReplyRecoveryJob.objects.get(source_message=self.source)
        self.assertEqual(job.holding_message_id, holding.pk)
        self.assertEqual(job.status, job.Status.SENT)
        self.assertEqual(job.provider_message_id, "meta-recovery-legacy-1")
        self.assertIn('"status": "sent"', output.getvalue())
        send.assert_called_once()

    def test_command_acknowledgement_links_an_existing_prepared_job(self):
        self.recovery.schedule_recovery(self.source, activate=False)
        holding = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Зараз передам менеджеру.",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
        )

        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
            return_value="Вибачте за затримку. Я вже на зв'язку.",
        ), patch.object(
            self.recovery,
            "send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "meta-recovery-prepared-1"),
        ):
            call_command(
                "recover_ig_ai_reply",
                source_message=str(self.source.pk),
                holding_message=str(holding.pk),
                acknowledge_unreceipted_holding=True,
                execute=True,
            )

        job = self.recovery.IgAiReplyRecoveryJob.objects.get(source_message=self.source)
        self.assertEqual(job.holding_message_id, holding.pk)
        self.assertEqual(job.status, job.Status.SENT)

    def test_acknowledgement_does_not_exempt_a_confirmed_bot_reply(self):
        reply = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Звичайна відповідь бота.",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
            send_state="sent",
            provider_message_id="ordinary-reply-1",
        )

        with self.assertRaisesMessage(CommandError, "holding_must_be_unreceipted"):
            call_command(
                "recover_ig_ai_reply",
                source_message=str(self.source.pk),
                holding_message=str(reply.pk),
                acknowledge_unreceipted_holding=True,
                execute=True,
            )

    def test_due_worker_drains_pending_recovery_once(self):
        job = self.recovery.schedule_recovery(self.source)
        with patch.object(
            self.recovery,
            "_generate_recovery_draft",
            return_value="Вибачте за затримку. Вже відповідаю.",
        ), patch.object(
            self.recovery,
            "send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "meta-recovery-due-1"),
        ) as send:
            processed = self.recovery.process_due_recoveries(limit=5)

        job.refresh_from_db()
        self.assertEqual(processed, 1)
        self.assertEqual(job.status, job.Status.SENT)
        send.assert_called_once()
