"""Manager decisions for discount follow-ups are event-driven and durable."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.utils import timezone

from management.models import (
    IgBotNotification,
    IgBotNotificationAudit,
    IgClient,
    IgFollowUpTask,
)
from management.views import management_bot_webhook


class IgDiscountTelegramCallbackTests(TestCase):
    def _task_and_notification(self, *, message_id="501"):
        client = IgClient.get_or_create_for_sender(f"discount-callback-{message_id}")
        client.stage = IgClient.Stage.CHECKOUT
        client.primary_objection = IgClient.Objection.PRICE
        client.last_message_at = timezone.now()
        client.save(update_fields=[
            "stage", "primary_objection", "last_message_at", "updated_at"
        ])
        task = IgFollowUpTask.objects.create(
            client=client,
            due_at=timezone.now() - timedelta(minutes=1),
            status=IgFollowUpTask.Status.PENDING,
            kind=IgFollowUpTask.Kind.RESCUE,
            reason="price_objection",
            discount_percent=5,
            manager_approval_status=IgFollowUpTask.ManagerApprovalStatus.PENDING,
            manager_approval_requested_at=timezone.now(),
        )
        client.next_followup_at = task.due_at
        client.save(update_fields=["next_followup_at", "updated_at"])
        notification = IgBotNotification.objects.create(
            client=client,
            dedupe_key=f"discount_approval:{task.pk}",
            event_type="discount_approval",
            payload={
                "text": "Approve discount",
                "chat_id": "777",
                "followup_task_id": task.pk,
                "requires_human_review": True,
            },
            status=IgBotNotification.Status.SENT,
            telegram_message_id=message_id,
        )
        return task, notification

    def _request(self, task, action, *, chat_id=777, message_id=501, callback_id="cb"):
        return RequestFactory().post(
            "/management/tg-manager/webhook/token/",
            data=json.dumps({
                "callback_query": {
                    "id": callback_id,
                    "data": f"igdisc:{action}:{task.pk}",
                    "from": {"id": chat_id, "username": "owner"},
                    "message": {
                        "chat": {"id": chat_id, "type": "private"},
                        "message_id": message_id,
                        "text": "Approve discount",
                    },
                }
            }),
            content_type="application/json",
        )

    @patch.dict(
        "os.environ",
        {"MANAGEMENT_TG_ADMIN_CHAT_ID": "777", "MANAGEMENT_TG_BOT_TOKEN": "token"},
        clear=False,
    )
    @patch("management.views._tg_edit_message")
    @patch("management.views._tg_answer_callback")
    def test_approve_button_unlocks_task_and_is_idempotent(self, answer, edit):
        task, notification = self._task_and_notification()

        first = management_bot_webhook(self._request(task, "approve"), "token")
        task.refresh_from_db()
        task.status = IgFollowUpTask.Status.SENT
        task.save(update_fields=["status", "updated_at"])
        second = management_bot_webhook(
            self._request(task, "approve", callback_id="cb-repeat"), "token"
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        task.refresh_from_db()
        notification.refresh_from_db()
        self.assertEqual(
            task.manager_approval_status,
            IgFollowUpTask.ManagerApprovalStatus.APPROVED,
        )
        self.assertIsNotNone(task.manager_approval_decided_at)
        self.assertEqual(task.status, IgFollowUpTask.Status.SENT)
        self.assertEqual(notification.status, IgBotNotification.Status.RESOLVED)
        self.assertEqual(
            IgBotNotificationAudit.objects.filter(
                notification=notification,
                action="discount_approved",
            ).count(),
            1,
        )
        self.assertEqual(edit.call_count, 2)
        self.assertEqual(answer.call_count, 2)

    @patch.dict(
        "os.environ",
        {"MANAGEMENT_TG_ADMIN_CHAT_ID": "777", "MANAGEMENT_TG_BOT_TOKEN": "token"},
        clear=False,
    )
    @patch("management.views._tg_edit_message")
    @patch("management.views._tg_answer_callback")
    def test_reject_button_cancels_task(self, answer, edit):
        task, notification = self._task_and_notification(message_id="502")

        response = management_bot_webhook(
            self._request(task, "reject", message_id=502), "token"
        )

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        notification.refresh_from_db()
        self.assertEqual(task.status, IgFollowUpTask.Status.CANCELLED)
        self.assertEqual(
            task.manager_approval_status,
            IgFollowUpTask.ManagerApprovalStatus.REJECTED,
        )
        self.assertEqual(notification.status, IgBotNotification.Status.RESOLVED)
        task.client.refresh_from_db()
        self.assertIsNone(task.client.next_followup_at)
        answer.assert_called_once()
        edit.assert_called_once()

    @patch.dict(
        "os.environ",
        {"MANAGEMENT_TG_ADMIN_CHAT_ID": "777", "MANAGEMENT_TG_BOT_TOKEN": "token"},
        clear=False,
    )
    @patch("management.views._tg_edit_message")
    @patch("management.views._tg_answer_callback")
    def test_callback_from_unconfigured_chat_is_denied(self, answer, edit):
        task, _notification = self._task_and_notification(message_id="503")

        response = management_bot_webhook(
            self._request(task, "approve", chat_id=999, message_id=503), "token"
        )

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(
            task.manager_approval_status,
            IgFollowUpTask.ManagerApprovalStatus.PENDING,
        )
        answer.assert_called_once_with("token", "cb", "Недостатньо прав")
        edit.assert_not_called()

    @patch.dict(
        "os.environ",
        {"MANAGEMENT_TG_ADMIN_CHAT_ID": "777", "MANAGEMENT_TG_BOT_TOKEN": "token"},
        clear=False,
    )
    @patch("management.views._tg_edit_message")
    @patch("management.views._tg_answer_callback")
    def test_expired_discount_cannot_be_approved_from_stale_button(self, answer, edit):
        task, notification = self._task_and_notification(message_id="504")
        task.meta_window_deadline = timezone.now() - timedelta(seconds=1)
        task.save(update_fields=["meta_window_deadline", "updated_at"])

        response = management_bot_webhook(
            self._request(task, "approve", message_id=504), "token"
        )

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        notification.refresh_from_db()
        self.assertEqual(task.status, IgFollowUpTask.Status.CANCELLED)
        self.assertNotEqual(
            task.manager_approval_status,
            IgFollowUpTask.ManagerApprovalStatus.APPROVED,
        )
        self.assertEqual(notification.status, IgBotNotification.Status.RESOLVED)
        answer.assert_called_once_with("token", "cb", "Follow-up більше не актуальний")
        edit.assert_not_called()
