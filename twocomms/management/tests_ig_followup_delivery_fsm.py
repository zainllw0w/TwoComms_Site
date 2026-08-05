"""IMP-102: durable, operator-resolvable follow-up delivery boundary."""

from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from management.ig_bot_models import IgClient, IgFollowUpTask
from management.models import AdminAuditLog, InstagramBotSettings
from management.services.instagram_bot import ProviderDeliveryReceipt


KYIV = ZoneInfo("Europe/Kyiv")
MGMT = override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    SECURE_SSL_REDIRECT=False,
)


class FollowupDeliveryFsmTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 5, 11, 0, tzinfo=KYIV)
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled", "updated_at"])
        self.client_record = self._client("imp102")

    def _client(self, suffix):
        client = IgClient.get_or_create_for_sender(f"imp102-{suffix}")
        client.stage = IgClient.Stage.QUALIFYING
        client.last_message_at = self.now
        client.save(update_fields=["stage", "last_message_at", "updated_at"])
        return client

    def _task(self, *, client=None, **overrides):
        values = {
            "client": client or self.client_record,
            "due_at": self.now,
            "status": IgFollowUpTask.Status.PENDING,
            "kind": IgFollowUpTask.Kind.QUALIFICATION,
            "reason": "imp102_delivery_boundary",
            "message_text": "Чи актуальне ще замовлення?",
            "meta_window_deadline": self.now + timedelta(hours=20),
        }
        values.update(overrides)
        return IgFollowUpTask.objects.create(**values)

    def test_task_is_processing_with_lease_at_exact_provider_boundary(self):
        from management.services.bot_followups import process_due_followups

        task = self._task()
        observed = {}

        def send_text(*_args, **kwargs):
            task.refresh_from_db()
            observed.update(
                status=task.status,
                claim_token=task.claim_token,
                claim_until=task.claim_until,
                attempt_count=task.attempt_count,
                return_receipt=kwargs.get("return_receipt"),
            )
            return ProviderDeliveryReceipt(True, "", "", "mid-imp102-success")

        with patch(
            "management.services.instagram_bot.send_text", side_effect=send_text
        ):
            self.assertEqual(
                process_due_followups(self.settings, now=self.now, limit=1), 1
            )

        self.assertEqual(observed["status"], IgFollowUpTask.Status.PROCESSING)
        self.assertTrue(observed["claim_token"])
        self.assertGreater(observed["claim_until"], self.now)
        self.assertEqual(observed["attempt_count"], 1)
        self.assertTrue(observed["return_receipt"])
        task.refresh_from_db()
        self.assertEqual(task.status, IgFollowUpTask.Status.SENT)
        self.assertEqual(task.provider_message_id, "mid-imp102-success")
        self.assertEqual(task.sent_message.provider_message_id, "mid-imp102-success")
        self.assertEqual(task.claim_token, "")
        self.assertIsNone(task.claim_until)

    def test_uncertain_provider_outcomes_are_ambiguous_and_never_retried(self):
        from management.services.bot_followups import process_due_followups

        outcomes = {
            "timeout": TimeoutError("provider timeout"),
            "http_503": ProviderDeliveryReceipt(False, "transient", "http_503", ""),
            "unknown": ProviderDeliveryReceipt(False, "unknown", "unknown", ""),
            "missing_receipt": ProviderDeliveryReceipt(True, "", "", ""),
        }
        for suffix, outcome in outcomes.items():
            with self.subTest(outcome=suffix):
                client = self._client(suffix)
                task = self._task(client=client)
                first = {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
                with patch("management.services.instagram_bot.send_text", **first) as send:
                    self.assertEqual(
                        process_due_followups(self.settings, now=self.now, limit=1),
                        0,
                    )
                    task.refresh_from_db()
                    self.assertEqual(task.status, IgFollowUpTask.Status.AMBIGUOUS)
                    self.assertEqual(task.attempt_count, 1)
                    self.assertEqual(task.claim_token, "")
                    self.assertIsNone(task.claim_until)
                    review = IgFollowUpTask.objects.get(
                        delivery_review_for=task,
                        kind=IgFollowUpTask.Kind.MANAGER_TASK,
                    )
                    self.assertEqual(review.status, IgFollowUpTask.Status.PENDING)

                    self.assertEqual(
                        process_due_followups(self.settings, now=self.now, limit=1),
                        0,
                    )
                    self.assertEqual(send.call_count, 1)

    def test_stale_processing_lease_becomes_ambiguous_without_provider_call(self):
        from management.services.bot_followups import process_due_followups

        task = self._task(
            status=IgFollowUpTask.Status.PROCESSING,
            claim_token="dead-worker",
            claim_until=self.now - timedelta(seconds=1),
            attempt_count=1,
        )

        with patch("management.services.instagram_bot.send_text") as send:
            self.assertEqual(
                process_due_followups(self.settings, now=self.now, limit=1), 0
            )

        send.assert_not_called()
        task.refresh_from_db()
        self.assertEqual(task.status, IgFollowUpTask.Status.AMBIGUOUS)
        self.assertTrue(
            IgFollowUpTask.objects.filter(delivery_review_for=task).exists()
        )

    def test_receipt_committed_before_worker_crash_is_recovered_without_resend(self):
        from management.services.bot_followups import process_due_followups

        task = self._task(
            status=IgFollowUpTask.Status.SENT,
            provider_message_id="mid-recovery",
            message_text="Збережений текст доставки",
        )

        with patch("management.services.instagram_bot.send_text") as send:
            self.assertEqual(
                process_due_followups(self.settings, now=self.now, limit=1), 0
            )

        send.assert_not_called()
        task.refresh_from_db()
        self.assertEqual(task.status, IgFollowUpTask.Status.SENT)
        self.assertIsNotNone(task.sent_message_id)
        self.assertEqual(task.sent_message.text, "Збережений текст доставки")

    def test_stale_pending_claim_is_safely_reclaimed_before_provider_io(self):
        from management.services.bot_followups import process_due_followups

        task = self._task(
            claim_token="safe-dead-worker",
            claim_until=self.now - timedelta(seconds=1),
        )

        with patch(
            "management.services.instagram_bot.send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "mid-reclaimed"),
        ) as send:
            self.assertEqual(
                process_due_followups(self.settings, now=self.now, limit=1), 1
            )

        send.assert_called_once()
        task.refresh_from_db()
        self.assertEqual(task.status, IgFollowUpTask.Status.SENT)
        self.assertEqual(task.provider_message_id, "mid-reclaimed")
        self.assertEqual(task.attempt_count, 1)

    def test_finalize_failure_preserves_receipt_and_queues_review(self):
        from management.services.bot_followups import process_due_followups

        task = self._task()
        with (
            patch(
                "management.services.instagram_bot.send_text",
                return_value=ProviderDeliveryReceipt(
                    True, "", "", "mid-finalize-failed"
                ),
            ),
            patch(
                "management.services.bot_followups._finalize_confirmed_followup",
                side_effect=RuntimeError("local transaction failed"),
            ),
        ):
            self.assertEqual(
                process_due_followups(self.settings, now=self.now, limit=1), 0
            )

        task.refresh_from_db()
        self.assertEqual(task.status, IgFollowUpTask.Status.AMBIGUOUS)
        self.assertEqual(task.provider_message_id, "mid-finalize-failed")
        self.assertIn("local transaction failed", task.last_error)
        self.assertTrue(
            IgFollowUpTask.objects.filter(delivery_review_for=task).exists()
        )


@MGMT
class FollowupDeliveryResolutionTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 5, 12, 0, tzinfo=KYIV)
        self.admin = get_user_model().objects.create_user(
            "imp102-admin", password="x", is_staff=True
        )
        self.client.force_login(self.admin)
        self.client_record = IgClient.get_or_create_for_sender("imp102-resolution")
        self.client_record.stage = IgClient.Stage.QUALIFYING
        self.client_record.last_message_at = self.now
        self.client_record.save(
            update_fields=["stage", "last_message_at", "updated_at"]
        )

    def _ambiguous_pair(self, suffix):
        source = IgFollowUpTask.objects.create(
            client=self.client_record,
            due_at=self.now,
            status=IgFollowUpTask.Status.AMBIGUOUS,
            kind=IgFollowUpTask.Kind.QUALIFICATION,
            reason=f"imp102_{suffix}",
            message_text="Точний текст можливої доставки",
            attempt_count=1,
        )
        review = IgFollowUpTask.objects.create(
            client=self.client_record,
            due_at=self.now,
            kind=IgFollowUpTask.Kind.MANAGER_TASK,
            reason="followup_delivery_review",
            event_key=f"followup_delivery_review:{source.pk}",
            delivery_review_for=source,
            message_text="Перевірте Direct, не надсилайте повторно.",
        )
        return source, review

    def _resolve_url(self, source):
        return reverse(
            "management_bot_client_followup_delivery_resolve_api",
            args=[self.client_record.pk, source.pk],
        )

    def test_delivered_resolution_is_idempotent_audited_and_never_resends(self):
        source, review = self._ambiguous_pair("delivered")
        url = self._resolve_url(source)

        with patch("management.services.instagram_bot.send_text") as send:
            first = self.client.post(
                url,
                {"outcome": "delivered", "note": "Є у Meta Inbox"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            second = self.client.post(
                url,
                {"outcome": "delivered", "note": "Є у Meta Inbox"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(first.status_code, 200, first.content)
        self.assertFalse(first.json()["idempotent"])
        self.assertEqual(second.status_code, 200, second.content)
        self.assertTrue(second.json()["idempotent"])
        send.assert_not_called()
        source.refresh_from_db()
        review.refresh_from_db()
        self.assertEqual(source.status, IgFollowUpTask.Status.SENT)
        self.assertEqual(review.status, IgFollowUpTask.Status.COMPLETED)
        self.assertEqual(
            AdminAuditLog.objects.filter(
                action="ig_followup_delivery_resolved",
                entity_id=str(source.pk),
            ).count(),
            1,
        )

    def test_not_delivered_resolution_is_terminal_and_never_resends(self):
        source, review = self._ambiguous_pair("not-delivered")

        with patch("management.services.instagram_bot.send_text") as send:
            response = self.client.post(
                self._resolve_url(source),
                {"outcome": "not_delivered", "note": "У Direct немає"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200, response.content)
        send.assert_not_called()
        source.refresh_from_db()
        review.refresh_from_db()
        self.assertEqual(source.status, IgFollowUpTask.Status.SKIPPED)
        self.assertEqual(source.skip_reason, "manager_confirmed_not_delivered")
        self.assertEqual(review.status, IgFollowUpTask.Status.COMPLETED)

    def test_delivered_resolution_keeps_nonempty_transcript_when_source_text_missing(self):
        source, review = self._ambiguous_pair("missing-text")
        source.message_text = ""
        source.save(update_fields=["message_text", "updated_at"])
        review.message_text = "Текст, збережений для ручної перевірки"
        review.save(update_fields=["message_text", "updated_at"])

        response = self.client.post(
            self._resolve_url(source),
            {"outcome": "delivered", "note": "Підтверджено вручну"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200, response.content)
        source.refresh_from_db()
        self.assertTrue(source.sent_message_id)
        self.assertEqual(
            source.sent_message.text,
            "Текст, збережений для ручної перевірки",
        )

    def test_resolution_surface_requires_login_staff_and_post(self):
        source, _review = self._ambiguous_pair("access")
        url = self._resolve_url(source)
        self.assertEqual(self.client.get(url).status_code, 405)

        ordinary = get_user_model().objects.create_user("imp102-user", password="x")
        self.client.force_login(ordinary)
        self.assertEqual(
            self.client.post(url, {"outcome": "delivered"}).status_code, 403
        )
        self.client.logout()
        self.assertEqual(
            self.client.post(url, {"outcome": "delivered"}).status_code, 302
        )

    def test_client_detail_exposes_review_without_resend_action(self):
        source, _review = self._ambiguous_pair("detail")

        response = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.client_record.pk])
        )

        self.assertEqual(response.status_code, 200, response.content)
        row = next(
            item
            for item in response.json()["followups"]
            if item["id"] == source.pk
        )
        self.assertEqual(row["status"], IgFollowUpTask.Status.AMBIGUOUS)
        self.assertEqual(row["allowed_outcomes"], ["delivered", "not_delivered"])
        self.assertTrue(row["resolution_url"])
        self.assertNotIn("resend", row["allowed_outcomes"])
