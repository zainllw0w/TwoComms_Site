from datetime import timedelta
from unittest.mock import patch

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
