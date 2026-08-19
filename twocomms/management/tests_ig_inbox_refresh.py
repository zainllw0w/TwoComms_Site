import json
import re
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from management.bot_access import META_REVIEWER_GROUP_NAME
from management.models import (
    IgClient,
    IgConversationAnalysisSnapshot,
    IgConversationAnalysisJob,
    IgFollowUpTask,
    IgInboxRefreshItem,
    IgInboxRefreshRun,
    IgPostSaleCase,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import ig_inbox_refresh
from management.services import instagram_bot as bot


User = get_user_model()
MGMT = override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop"],
    SECURE_SSL_REDIRECT=False,
)


def _message(mid, sender, created_at, text="hello", recipient="17841467101471112"):
    return {
        "id": mid,
        "created_time": created_at.isoformat().replace("+00:00", "Z"),
        "from": {"id": sender},
        "to": {"data": [{"id": recipient}]},
        "message": text,
    }


class InboxRefreshRunTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("refresh-admin", is_staff=True)
        self.settings = InstagramBotSettings.load()
        self.settings.ig_user_id = "17841467101471112"
        self.settings.save(update_fields=["ig_user_id"])

    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_start_is_durable_idempotent_and_performs_no_meta_io(self, _transport):
        requested_at = timezone.now().replace(microsecond=654321)
        with patch("management.services.ig_inbox_refresh.bot._provider_http") as provider_http:
            first, first_created = ig_inbox_refresh.create_refresh_run(
                self.admin,
                now=requested_at,
            )
            second, second_created = ig_inbox_refresh.create_refresh_run(
                self.admin,
                now=requested_at + timedelta(seconds=1),
            )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.recovery_cutoff.microsecond, 0)
        self.assertEqual(first.open_slot, 1)
        provider_http.assert_not_called()

    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_latest_run_is_scoped_to_current_provider_owner(self, _transport):
        current = IgInboxRefreshRun.objects.create(
            provider_owner_id=f"{bot.INSTAGRAM_LOGIN_TRANSPORT}:{self.settings.ig_user_id}",
            transport=bot.INSTAGRAM_LOGIN_TRANSPORT,
            recovery_cutoff=timezone.now(),
            open_slot=None,
            status=IgInboxRefreshRun.Status.COMPLETED,
        )
        IgInboxRefreshRun.objects.create(
            provider_owner_id=f"{bot.INSTAGRAM_LOGIN_TRANSPORT}:different-owner",
            transport=bot.INSTAGRAM_LOGIN_TRANSPORT,
            recovery_cutoff=timezone.now(),
            open_slot=None,
            status=IgInboxRefreshRun.Status.COMPLETED,
        )

        self.assertEqual(ig_inbox_refresh.latest_refresh_run().pk, current.pk)


@MGMT
class InboxRefreshApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("refresh-api-admin", is_staff=True)
        self.reviewer = User.objects.create_user("refresh-api-reviewer")
        reviewer_group, _ = Group.objects.get_or_create(name=META_REVIEWER_GROUP_NAME)
        self.reviewer.groups.add(reviewer_group)
        settings = InstagramBotSettings.load()
        settings.ig_user_id = "17841467101471112"
        settings.save(update_fields=["ig_user_id"])

    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_only_admin_can_start_and_second_start_returns_existing_run(self, _transport):
        self.client.force_login(self.reviewer)
        denied = self.client.post(reverse("management_bot_inbox_refresh_start_api"))
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.admin)
        created = self.client.post(reverse("management_bot_inbox_refresh_start_api"))
        duplicate = self.client.post(reverse("management_bot_inbox_refresh_start_api"))

        self.assertEqual(created.status_code, 202)
        self.assertTrue(created.json()["success"])
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(created.json()["run"]["id"], duplicate.json()["run"]["id"])

    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_status_cancel_and_retry_contract_is_admin_only(self, _transport):
        self.client.force_login(self.reviewer)
        denied = self.client.get(reverse("management_bot_inbox_refresh_status_api"))
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.admin)
        empty = self.client.get(reverse("management_bot_inbox_refresh_status_api"))
        self.assertEqual(empty.status_code, 200)
        self.assertIsNone(empty.json()["run"])

        created = self.client.post(reverse("management_bot_inbox_refresh_start_api"))
        run_id = created.json()["run"]["id"]
        status = self.client.get(reverse("management_bot_inbox_refresh_status_api"))
        self.assertEqual(status.json()["run"]["id"], run_id)

        cancelled = self.client.post(
            reverse("management_bot_inbox_refresh_cancel_api", args=[run_id])
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["run"]["status"], IgInboxRefreshRun.Status.CANCELLING)

        retry_wrong_state = self.client.post(
            reverse("management_bot_inbox_refresh_retry_api", args=[run_id])
        )
        self.assertEqual(retry_wrong_state.status_code, 409)

    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_cancel_and_retry_cannot_mutate_a_different_provider_owner(self, _transport):
        self.client.force_login(self.admin)
        foreign_active = IgInboxRefreshRun.objects.create(
            provider_owner_id=f"{bot.INSTAGRAM_LOGIN_TRANSPORT}:different-owner",
            transport=bot.INSTAGRAM_LOGIN_TRANSPORT,
            recovery_cutoff=timezone.now(),
            status=IgInboxRefreshRun.Status.RUNNING,
        )
        foreign_failed = IgInboxRefreshRun.objects.create(
            provider_owner_id=f"{bot.INSTAGRAM_LOGIN_TRANSPORT}:another-owner",
            transport=bot.INSTAGRAM_LOGIN_TRANSPORT,
            recovery_cutoff=timezone.now(),
            status=IgInboxRefreshRun.Status.FAILED,
            open_slot=None,
        )

        cancel = self.client.post(
            reverse("management_bot_inbox_refresh_cancel_api", args=[foreign_active.pk])
        )
        retry = self.client.post(
            reverse("management_bot_inbox_refresh_retry_api", args=[foreign_failed.pk])
        )

        self.assertEqual(cancel.status_code, 404)
        self.assertEqual(retry.status_code, 404)
        foreign_active.refresh_from_db()
        foreign_failed.refresh_from_db()
        self.assertEqual(foreign_active.status, IgInboxRefreshRun.Status.RUNNING)
        self.assertEqual(foreign_failed.status, IgInboxRefreshRun.Status.FAILED)

    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_dashboard_contains_manual_refresh_progress_for_admin_only(self, _transport):
        self.client.force_login(self.admin)
        admin_page = self.client.get(reverse("management_bot"))
        self.assertContains(admin_page, 'id="bot-inbox-refresh-start"')
        self.assertContains(admin_page, 'id="bot-inbox-refresh-progress"')
        self.assertContains(admin_page, 'role="progressbar"')
        self.assertContains(admin_page, "response.redirected")
        self.assertContains(admin_page, "contentType.includes('application/json')")
        self.assertContains(admin_page, "bar.style.width=discovering?'':pct+'%'")
        self.assertContains(admin_page, "function recoverAfterAction")
        self.assertContains(admin_page, "if(result.authRequired)")
        page_css = admin_page.content.decode()
        for selector in (
            ".bot-inbox-refresh-progress.is-discovering .bot-inbox-refresh-bar",
            ".bot-inbox-refresh-start.is-running .bot-inbox-refresh-icon",
        ):
            self.assertRegex(
                page_css,
                rf"@media\(prefers-reduced-motion:reduce\)\{{[^}}]*{re.escape(selector)}[^}}]*\{{animation:none!important\}}",
            )

        self.client.force_login(self.reviewer)
        reviewer_page = self.client.get(reverse("management_bot"))
        self.assertNotContains(reviewer_page, 'id="bot-inbox-refresh-start"')


class InboxRefreshWorkerTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("refresh-worker-admin", is_staff=True)
        self.settings = InstagramBotSettings.load()
        self.settings.ig_user_id = "17841467101471112"
        self.settings.save(update_fields=["ig_user_id"])
        self.cutoff = timezone.now().replace(microsecond=0)
        self.run = IgInboxRefreshRun.objects.create(
            requested_by=self.admin,
            provider_owner_id=f"{bot.INSTAGRAM_LOGIN_TRANSPORT}:{self.settings.ig_user_id}",
            transport=bot.INSTAGRAM_LOGIN_TRANSPORT,
            recovery_cutoff=self.cutoff,
        )

    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    @patch("management.services.ig_inbox_refresh.bot._provider_http")
    def test_discovery_creates_pending_item_and_fails_closed_for_hidden_client(
        self, provider_http, _transport, _token
    ):
        hidden = IgClient.get_or_create_for_sender("hidden-participant")
        hidden.hidden_at = timezone.now()
        hidden.save(update_fields=["hidden_at", "updated_at"])
        provider_http.return_value = (200, json.dumps({
            "data": [
                {
                    "id": "conv-active",
                    "participants": {"data": [
                        {"id": self.settings.ig_user_id},
                        {"id": "active-participant"},
                    ]},
                    "updated_time": self.cutoff.isoformat(),
                },
                {
                    "id": "conv-hidden",
                    "participants": {"data": [
                        {"id": self.settings.ig_user_id},
                        {"id": hidden.igsid},
                    ]},
                    "updated_time": self.cutoff.isoformat(),
                },
            ]
        }))

        result = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertTrue(result["worked"])
        self.run.refresh_from_db()
        self.assertTrue(self.run.discovery_complete)
        self.assertEqual(self.run.status, IgInboxRefreshRun.Status.RUNNING)
        self.assertEqual(
            IgInboxRefreshItem.objects.get(run=self.run, conversation_id="conv-active").status,
            IgInboxRefreshItem.Status.PENDING,
        )
        hidden_item = IgInboxRefreshItem.objects.get(
            run=self.run,
            conversation_id="conv-hidden",
        )
        self.assertEqual(hidden_item.status, IgInboxRefreshItem.Status.SKIPPED)
        self.assertEqual(hidden_item.skip_reason, "client_hidden")

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot.enqueue_inbound")
    @patch("management.services.bot_sales_classifier.ensure_rule_classification")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_history_is_done_only_respects_cutoff_and_schedules_one_analysis(
        self, _transport, _token, fetch_history, ensure_rule_classification,
        enqueue_inbound, schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-history",
            participant_igsid="history-participant",
        )
        before = self.cutoff - timedelta(minutes=1)
        after = self.cutoff + timedelta(seconds=1)
        before_message = _message("mid-before", item.participant_igsid, before, "before")
        before_message["attachments"] = [{
            "type": "image",
            "payload": {"url": "https://lookaside.example/manual-history.jpg"},
        }]
        fetch_history.return_value = {
            "messages": [
                before_message,
                _message("mid-after", item.participant_igsid, after, "after"),
            ],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        result = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertTrue(result["worked"])
        row = InstagramBotMessage.objects.get(mid="mid-before")
        self.assertEqual(row.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(row.source, "manual_refresh")
        self.assertEqual(row.role, InstagramBotMessage.Role.USER)
        self.assertEqual(row.provider_created_at, before)
        self.assertEqual(row.attachment_media, [{
            "url": "https://lookaside.example/manual-history.jpg",
            "provenance": "historical_import",
            "status": "metadata_only",
        }])
        self.assertFalse(InstagramBotMessage.objects.filter(mid="mid-after").exists())
        enqueue_inbound.assert_not_called()
        schedule_analysis.assert_called_once()
        ensure_rule_classification.assert_called_once()
        self.assertFalse(
            ensure_rule_classification.call_args.kwargs["operational_effects"]
        )
        item.refresh_from_db()
        self.assertEqual(item.status, IgInboxRefreshItem.Status.DONE)
        self.assertEqual(item.messages_created, 1)
        self.assertEqual(item.messages_after_cutoff, 1)

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.bot_followups.cancel_pending")
    @patch("management.services.bot_sales_classifier.ensure_rule_classification")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_history_for_restricted_sender_is_visible_without_automation(
        self,
        _transport,
        _token,
        fetch_history,
        ensure_rule_classification,
        cancel_pending,
        schedule_analysis,
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-restricted-history",
            participant_igsid="restricted-history-participant",
        )
        self.settings.allowed_senders = "another-participant"
        self.settings.save(update_fields=["allowed_senders"])
        created = self.cutoff - timedelta(minutes=1)
        fetch_history.return_value = {
            "messages": [
                _message(
                    "mid-restricted-history",
                    item.participant_igsid,
                    created,
                    "Please send your number",
                )
            ],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        row = InstagramBotMessage.objects.get(mid="mid-restricted-history")
        self.assertEqual(row.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(row.source, "manual_refresh")
        self.assertFalse(row.media_capture_eligible)
        ensure_rule_classification.assert_not_called()
        cancel_pending.assert_not_called()
        schedule_analysis.assert_not_called()

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_provider_order_is_normalized_before_latest_twenty_and_cutoff_is_inclusive(
        self, _transport, _token, fetch_history, _schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-inverted-provider-order",
            participant_igsid="inverted-provider-order",
        )
        provider_times = [
            self.cutoff - timedelta(minutes=offset)
            for offset in range(20, -1, -1)
        ]
        fetch_history.return_value = {
            "messages": [
                _message(f"mid-inverted-{index}", item.participant_igsid, created)
                for index, created in enumerate(provider_times)
            ],
            "complete": True,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        item.refresh_from_db()
        self.assertEqual(item.messages_seen, 20)
        self.assertEqual(item.messages_created, 20)
        self.assertFalse(InstagramBotMessage.objects.filter(mid="mid-inverted-0").exists())
        self.assertTrue(InstagramBotMessage.objects.filter(provider_created_at=self.cutoff).exists())

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_missing_recipients_and_malformed_timestamp_fail_closed(
        self, _transport, _token, fetch_history, _schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        missing_to = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-missing-to",
            participant_igsid="missing-to-participant",
        )
        malformed_time = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-malformed-time",
            participant_igsid="malformed-time-participant",
        )
        missing_to_message = _message(
            "mid-missing-to",
            missing_to.participant_igsid,
            self.cutoff - timedelta(minutes=1),
        )
        missing_to_message.pop("to")
        malformed_time_message = _message(
            "mid-malformed-time",
            malformed_time.participant_igsid,
            self.cutoff - timedelta(minutes=1),
        )
        malformed_time_message["created_time"] = "not-a-provider-time"
        fetch_history.side_effect = [
            {"messages": [missing_to_message], "complete": True},
            {"messages": [malformed_time_message], "complete": True},
        ]

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)
        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        missing_to.refresh_from_db()
        malformed_time.refresh_from_db()
        self.assertEqual(missing_to.status, IgInboxRefreshItem.Status.FAILED)
        self.assertIn("ambiguous_message_participants", missing_to.last_error)
        self.assertEqual(malformed_time.status, IgInboxRefreshItem.Status.FAILED)
        self.assertIn("malformed_message_time", malformed_time.last_error)

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_existing_webhook_pending_row_is_never_consumed_as_history(
        self, _transport, _token, fetch_history, schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-existing",
            participant_igsid="existing-participant",
        )
        created = self.cutoff - timedelta(minutes=1)
        existing = InstagramBotMessage.objects.create(
            sender_id=item.participant_igsid,
            role=InstagramBotMessage.Role.USER,
            text="live webhook row",
            mid="mid-existing",
            status=InstagramBotMessage.Status.PENDING,
            source="webhook",
            provider_created_at=created,
        )
        fetch_history.return_value = {
            "messages": [_message("mid-existing", item.participant_igsid, created)],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        existing.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(existing.status, InstagramBotMessage.Status.PENDING)
        self.assertEqual(existing.source, "webhook")
        self.assertEqual(existing.client_id, item.client_id)
        self.assertEqual(item.status, IgInboxRefreshItem.Status.DONE)
        schedule_analysis.assert_not_called()

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_existing_mid_tolerates_provider_timestamp_precision_difference(
        self, _transport, _token, fetch_history, schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-timestamp-precision",
            participant_igsid="timestamp-precision-participant",
        )
        live_at = self.cutoff - timedelta(minutes=1)
        history_at = live_at + timedelta(milliseconds=500)
        existing = InstagramBotMessage.objects.create(
            sender_id=item.participant_igsid,
            role=InstagramBotMessage.Role.USER,
            text="same provider message",
            mid="mid-timestamp-precision",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
            provider_created_at=live_at,
        )
        fetch_history.return_value = {
            "messages": [_message(existing.mid, item.participant_igsid, history_at, existing.text)],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        item.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(item.status, IgInboxRefreshItem.Status.DONE)
        self.assertEqual(existing.client_id, item.client_id)
        self.assertEqual(existing.provider_created_at, live_at)
        schedule_analysis.assert_called_once()

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.bot_sales_classifier.ensure_rule_classification")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_existing_legacy_model_mid_matches_provider_owner_message(
        self, _transport, _token, fetch_history, ensure_rule_classification,
        schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        client = IgClient.get_or_create_for_sender("legacy-model-mid-participant")
        client.stage = IgClient.Stage.ORDER_CREATED
        client.intent = IgClient.Intent.PRODUCT
        client.buying_readiness = 90
        client.save(update_fields=["stage", "intent", "buying_readiness", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-legacy-model-mid",
            participant_igsid=client.igsid,
            client=client,
        )
        created = self.cutoff - timedelta(minutes=1)
        existing = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.MODEL,
            text="Стара відповідь бота",
            mid="mid-legacy-model-owner-message",
            status=InstagramBotMessage.Status.DONE,
            source="manual_test",
            provider_created_at=created,
        )
        fetch_history.return_value = {
            "messages": [
                _message(
                    existing.mid,
                    self.settings.ig_user_id,
                    created,
                    existing.text,
                    recipient=client.igsid,
                )
            ],
            "complete": True,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        item.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(item.status, IgInboxRefreshItem.Status.DONE)
        self.assertEqual(item.messages_existing, 1)
        self.assertEqual(existing.role, InstagramBotMessage.Role.MODEL)
        self.assertEqual(InstagramBotMessage.objects.filter(mid=existing.mid).count(), 1)
        client.refresh_from_db()
        self.assertEqual(client.stage, IgClient.Stage.ORDER_CREATED)
        self.assertEqual(client.intent, IgClient.Intent.PRODUCT)
        self.assertEqual(client.buying_readiness, 90)
        ensure_rule_classification.assert_not_called()
        schedule_analysis.assert_called_once()

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_cross_client_mid_collision_fails_item_without_mutating_existing_row(
        self, _transport, _token, fetch_history, schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        participant = IgClient.get_or_create_for_sender("refresh-collision-participant")
        other = IgClient.get_or_create_for_sender("refresh-collision-other")
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-cross-client-mid",
            participant_igsid=participant.igsid,
            client=participant,
        )
        created = self.cutoff - timedelta(minutes=1)
        existing = InstagramBotMessage.objects.create(
            sender_id=other.igsid,
            client=other,
            role=InstagramBotMessage.Role.USER,
            text="other conversation",
            mid="mid-refresh-cross-client",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
            provider_created_at=created,
        )
        fetch_history.return_value = {
            "messages": [_message(existing.mid, participant.igsid, created)],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        item.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(item.status, IgInboxRefreshItem.Status.FAILED)
        self.assertIn("mid_identity_conflict", item.last_error)
        self.assertEqual(existing.client_id, other.pk)
        self.assertEqual(existing.sender_id, other.igsid)
        schedule_analysis.assert_not_called()

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_owner_message_uses_raw_account_id_not_provider_owner_key(
        self, _transport, _token, fetch_history, schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-owner-message",
            participant_igsid="owner-message-participant",
        )
        created = self.cutoff - timedelta(minutes=2)
        fetch_history.return_value = {
            "messages": [
                _message(
                    "mid-owner-message",
                    self.settings.ig_user_id,
                    created,
                    text="manager reply",
                    recipient=item.participant_igsid,
                )
            ],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        row = InstagramBotMessage.objects.get(mid="mid-owner-message")
        self.assertEqual(row.role, InstagramBotMessage.Role.MANAGER)
        self.assertEqual(row.status, InstagramBotMessage.Status.DONE)
        schedule_analysis.assert_called_once()

    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_hidden_client_is_skipped_before_provider_history_request(
        self, _transport, _token, fetch_history
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        hidden = IgClient.get_or_create_for_sender("hidden-before-fetch")
        hidden.hidden_at = self.cutoff
        hidden.save(update_fields=["hidden_at", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-hidden-before-fetch",
            participant_igsid=hidden.igsid,
        )

        result = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertTrue(result["worked"])
        fetch_history.assert_not_called()
        item.refresh_from_db()
        self.assertEqual(item.status, IgInboxRefreshItem.Status.SKIPPED)
        self.assertEqual(item.skip_reason, "client_hidden")

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_future_retry_does_not_starve_a_due_conversation(
        self, _transport, _token, fetch_history, _schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        future = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-future",
            participant_igsid="future-participant",
            next_attempt_at=self.cutoff + timedelta(hours=1),
        )
        due = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-due",
            participant_igsid="due-participant",
            next_attempt_at=self.cutoff,
        )
        fetch_history.return_value = {
            "messages": [],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        result = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertEqual(result["item_id"], due.pk)
        due.refresh_from_db()
        future.refresh_from_db()
        self.assertEqual(due.status, IgInboxRefreshItem.Status.DONE)
        self.assertEqual(future.status, IgInboxRefreshItem.Status.PENDING)

    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_cancel_is_durable_and_finishes_all_open_items(self, _transport):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-cancel",
            participant_igsid="cancel-participant",
        )
        ig_inbox_refresh.request_refresh_cancel(self.run.pk, now=self.cutoff)

        result = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertEqual(result["phase"], "cancel")
        self.run.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(self.run.status, IgInboxRefreshRun.Status.CANCELLED)
        self.assertIsNone(self.run.open_slot)
        self.assertEqual(item.status, IgInboxRefreshItem.Status.CANCELLED)

    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    @patch("management.services.ig_inbox_refresh.bot._provider_http")
    def test_cancel_wins_discovery_failure_race(
        self, provider_http, _transport, _token
    ):
        def cancel_then_fail(*_args, **_kwargs):
            ig_inbox_refresh.request_refresh_cancel(self.run.pk, now=self.cutoff)
            return 503, "provider unavailable"

        provider_http.side_effect = cancel_then_fail

        first = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertEqual(first["phase"], "discovery")
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, IgInboxRefreshRun.Status.CANCELLING)
        self.assertIsNotNone(self.run.cancel_requested_at)

        second = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertEqual(second["phase"], "cancel")
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, IgInboxRefreshRun.Status.CANCELLED)
        self.assertIsNone(self.run.open_slot)

    def test_completed_run_releases_open_slot_and_serializes_progress(self):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-complete",
            participant_igsid="complete-participant",
            status=IgInboxRefreshItem.Status.DONE,
            messages_created=3,
            messages_existing=2,
            completed_at=self.cutoff,
        )

        result = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertEqual(result["phase"], "finalize")
        self.run.refresh_from_db()
        payload = ig_inbox_refresh.serialize_refresh_run(self.run)
        self.assertEqual(self.run.status, IgInboxRefreshRun.Status.COMPLETED)
        self.assertIsNone(self.run.open_slot)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["terminal"], 1)
        self.assertEqual(payload["messages_created"], 3)
        self.assertEqual(payload["messages_existing"], 2)
        self.assertEqual(payload["hidden_skipped"], 0)

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_provider_503_retries_item_with_backoff(
        self, _transport, _token, fetch_history, _schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-retry-503",
            participant_igsid="retry-participant",
            next_attempt_at=self.cutoff,
        )
        fetch_history.return_value = {
            "messages": [],
            "requests": 1,
            "complete": False,
            "budget_exhausted": False,
            "reason": "http_503",
            "http_code": 503,
        }

        result = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertTrue(result["worked"])
        item.refresh_from_db()
        self.assertEqual(item.status, IgInboxRefreshItem.Status.PENDING)
        self.assertEqual(item.attempts, 1)
        self.assertGreater(item.next_attempt_at, self.cutoff)
        self.assertIn("http_503", item.last_error)

    @patch("management.services.ig_inbox_refresh.bot.CONV_MAX_PAGES", 1)
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    @patch("management.services.ig_inbox_refresh.bot._provider_http")
    def test_discovery_walks_all_conversation_pages(
        self, provider_http, _transport, _token
    ):
        provider_http.side_effect = [
            (200, json.dumps({
                "data": [{
                    "id": "conv-page-one",
                    "participants": {"data": [
                        {"id": self.settings.ig_user_id},
                        {"id": "participant-page-one"},
                    ]},
                    "updated_time": self.cutoff.isoformat(),
                }],
                "paging": {"cursors": {"after": "cursor-two"}, "next": "https://graph.instagram.com/v25.0/next?after=cursor-two"},
            })),
            (200, json.dumps({
                "data": [{
                    "id": "conv-page-two",
                    "participants": {"data": [
                        {"id": self.settings.ig_user_id},
                        {"id": "participant-page-two"},
                    ]},
                    "updated_time": self.cutoff.isoformat(),
                }],
            })),
        ]

        first = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)
        second = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertEqual(first["phase"], "discovery")
        self.assertEqual(second["phase"], "discovery")
        self.run.refresh_from_db()
        self.assertTrue(self.run.discovery_complete)
        self.assertEqual(self.run.discovery_pages_seen, 2)
        self.assertEqual(
            set(self.run.items.values_list("conversation_id", flat=True)),
            {"conv-page-one", "conv-page-two"},
        )

    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    @patch("management.services.ig_inbox_refresh.bot._provider_http")
    def test_discovery_retry_preserves_cursor(self, provider_http, _transport, _token):
        self.run.discovery_cursor = "cursor-before-retry"
        self.run.save(update_fields=["discovery_cursor", "updated_at"])
        provider_http.side_effect = [
            (503, "provider unavailable"),
            (200, json.dumps({"data": []})),
        ]

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.run.refresh_from_db()
        retry_at = self.run.next_attempt_at
        self.assertEqual(self.run.discovery_cursor, "cursor-before-retry")
        self.assertEqual(self.run.status, IgInboxRefreshRun.Status.DISCOVERING)

        ig_inbox_refresh.process_refresh_slice(now=retry_at)

        self.run.refresh_from_db()
        self.assertTrue(self.run.discovery_complete)
        self.assertEqual(self.run.discovery_cursor, "")

    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    @patch("management.services.ig_inbox_refresh.bot._provider_http")
    def test_discovery_repeated_cursor_fails_closed(
        self, provider_http, _transport, _token
    ):
        self.run.discovery_cursor = "cursor-loop"
        self.run.save(update_fields=["discovery_cursor", "updated_at"])
        provider_http.return_value = (200, json.dumps({
            "data": [{
                "id": "conv-loop",
                "participants": {"data": [
                    {"id": self.settings.ig_user_id},
                    {"id": "participant-loop"},
                ]},
                "updated_time": self.cutoff.isoformat(),
            }],
            "paging": {
                "cursors": {"after": "cursor-loop"},
                "next": "https://graph.instagram.com/v25.0/next?after=cursor-loop",
            },
        }))

        result = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertEqual(result["phase"], "discovery")
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, IgInboxRefreshRun.Status.FAILED)
        self.assertIsNone(self.run.open_slot)
        self.assertIn("repeated discovery cursor", self.run.last_error)
        self.assertFalse(self.run.items.exists())

    @patch("management.services.ig_inbox_refresh.bot._provider_http")
    def test_discovery_page_limit_fails_before_provider_request(self, provider_http):
        self.run.discovery_pages_seen = ig_inbox_refresh.MAX_DISCOVERY_PAGES
        self.run.discovery_cursor = "cursor-after-limit"
        self.run.save(update_fields=[
            "discovery_pages_seen", "discovery_cursor", "updated_at",
        ])

        result = ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        self.assertEqual(result["phase"], "discovery")
        provider_http.assert_not_called()
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, IgInboxRefreshRun.Status.FAILED)
        self.assertIsNone(self.run.open_slot)
        self.assertIn("discovery page limit exceeded", self.run.last_error)

    def test_stale_item_lease_cannot_publish_failure(self):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-stale-lease",
            participant_igsid="stale-lease-participant",
            status=IgInboxRefreshItem.Status.PROCESSING,
            lease_token="replacement-owner",
            lease_until=self.cutoff + timedelta(minutes=1),
        )
        item._claimed_lease_token = "stale-owner"

        ig_inbox_refresh._finish_item_failure(item, "stale failure", now=self.cutoff)

        item.refresh_from_db()
        self.assertEqual(item.status, IgInboxRefreshItem.Status.PROCESSING)
        self.assertEqual(item.lease_token, "replacement-owner")
        self.assertEqual(item.attempts, 0)

    def test_expired_item_lease_eventually_becomes_terminal_failure(self):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-expired-item-lease",
            participant_igsid="expired-item-lease-participant",
            status=IgInboxRefreshItem.Status.PROCESSING,
            attempts=ig_inbox_refresh.MAX_ATTEMPTS - 1,
            lease_token="lost-item-worker",
            lease_until=self.cutoff - timedelta(seconds=1),
        )

        claimed, worked = ig_inbox_refresh._claim_item(self.cutoff)

        self.assertIsNone(claimed)
        self.assertFalse(worked)
        item.refresh_from_db()
        self.assertEqual(item.status, IgInboxRefreshItem.Status.FAILED)
        self.assertEqual(item.attempts, ig_inbox_refresh.MAX_ATTEMPTS)
        self.assertEqual(item.lease_token, "")
        self.assertIsNotNone(item.completed_at)
        self.assertIn("lease expired", item.last_error)

    def test_expired_discovery_lease_eventually_fails_and_releases_run(self):
        self.run.status = IgInboxRefreshRun.Status.DISCOVERING
        self.run.attempts = ig_inbox_refresh.MAX_ATTEMPTS - 1
        self.run.lease_token = "lost-discovery-worker"
        self.run.lease_until = self.cutoff - timedelta(seconds=1)
        self.run.save(update_fields=[
            "status", "attempts", "lease_token", "lease_until", "updated_at",
        ])

        claimed = ig_inbox_refresh._claim_discovery_run(self.cutoff)

        self.assertIsNone(claimed)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, IgInboxRefreshRun.Status.FAILED)
        self.assertEqual(self.run.attempts, ig_inbox_refresh.MAX_ATTEMPTS)
        self.assertIsNone(self.run.open_slot)
        self.assertEqual(self.run.lease_token, "")
        self.assertIsNotNone(self.run.completed_at)
        self.assertIn("lease expired", self.run.last_error)

    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_failed_discovery_run_can_retry_without_losing_cursor(self, _transport):
        self.run.status = IgInboxRefreshRun.Status.FAILED
        self.run.open_slot = None
        self.run.attempts = ig_inbox_refresh.MAX_ATTEMPTS
        self.run.discovery_cursor = "cursor-retry-failed-run"
        self.run.completed_at = self.cutoff
        self.run.save(update_fields=[
            "status", "open_slot", "attempts", "discovery_cursor",
            "completed_at", "updated_at",
        ])

        retried = ig_inbox_refresh.retry_refresh_failures(
            self.run.pk,
            now=self.cutoff + timedelta(seconds=1),
        )

        self.assertEqual(retried.status, IgInboxRefreshRun.Status.DISCOVERING)
        self.assertEqual(retried.open_slot, 1)
        self.assertEqual(retried.attempts, 0)
        self.assertEqual(retried.discovery_cursor, "cursor-retry-failed-run")

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_client_hidden_during_fetch_is_skipped_before_persistence(
        self, _transport, _token, fetch_history, schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        client = IgClient.get_or_create_for_sender("hidden-during-fetch")
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-hidden-during-fetch",
            participant_igsid=client.igsid,
            client=client,
        )
        created = self.cutoff - timedelta(minutes=1)

        def hide_then_return(*_args, **_kwargs):
            IgClient.objects.filter(pk=client.pk).update(hidden_at=self.cutoff)
            return {
                "messages": [_message("mid-hidden-race", client.igsid, created)],
                "requests": 1,
                "complete": True,
                "budget_exhausted": False,
                "reason": "instagram_latest_window",
            }

        fetch_history.side_effect = hide_then_return

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        item.refresh_from_db()
        self.assertEqual(item.status, IgInboxRefreshItem.Status.SKIPPED)
        self.assertEqual(item.skip_reason, "client_hidden")
        self.assertFalse(InstagramBotMessage.objects.filter(mid="mid-hidden-race").exists())
        schedule_analysis.assert_not_called()

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_new_client_hidden_during_creation_is_skipped_before_persistence(
        self, _transport, _token, fetch_history, schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-hidden-during-create",
            participant_igsid="hidden-during-create",
        )
        created = self.cutoff - timedelta(minutes=1)
        fetch_history.return_value = {
            "messages": [_message("mid-hidden-create", item.participant_igsid, created)],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        def create_hidden(sender_id):
            return IgClient.objects.create(igsid=sender_id, hidden_at=self.cutoff)

        with patch.object(IgClient, "get_or_create_for_sender", side_effect=create_hidden):
            ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        item.refresh_from_db()
        self.assertEqual(item.status, IgInboxRefreshItem.Status.SKIPPED)
        self.assertEqual(item.skip_reason, "client_hidden")
        self.assertFalse(InstagramBotMessage.objects.filter(mid="mid-hidden-create").exists())
        schedule_analysis.assert_not_called()

    @patch("management.services.bot_conversation_analysis.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_missed_opt_out_is_projected_and_cancels_followups(
        self, _transport, _token, fetch_history, schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        client = IgClient.get_or_create_for_sender("opt-out-participant")
        task = IgFollowUpTask.objects.create(
            client=client,
            due_at=self.cutoff + timedelta(hours=1),
        )
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-opt-out",
            participant_igsid=client.igsid,
            client=client,
        )
        created = self.cutoff - timedelta(minutes=2)
        fetch_history.return_value = {
            "messages": [_message("mid-opt-out", client.igsid, created, "Не пишіть мені більше")],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }
        schedule_analysis.side_effect = RuntimeError("scheduler unavailable")

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        client.refresh_from_db()
        task.refresh_from_db()
        self.assertIsNotNone(client.opted_out_at)
        self.assertTrue(client.bot_paused)
        self.assertEqual(client.paused_reason, "opt_out")
        self.assertEqual(task.status, IgFollowUpTask.Status.CANCELLED)
        self.assertEqual(InstagramBotMessage.objects.get(mid="mid-opt-out").status, InstagramBotMessage.Status.DONE)

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_old_opt_out_cannot_override_newer_manual_opt_in(
        self, _transport, _token, fetch_history, _schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        old_opt_out_at = self.cutoff - timedelta(minutes=20)
        opted_in_at = self.cutoff - timedelta(minutes=2)
        client = IgClient.objects.create(
            igsid="opted-in-participant",
            opted_out_at=old_opt_out_at,
            opted_in_at=opted_in_at,
            bot_paused=False,
            stage=IgClient.Stage.CHECKOUT,
            buying_readiness=80,
            intent=IgClient.Intent.PAYMENT,
            primary_objection=IgClient.Objection.PRICE,
            language="uk",
            sales_context={"stable": True},
        )
        IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-opted-in",
            participant_igsid=client.igsid,
            client=client,
        )
        historical_at = self.cutoff - timedelta(minutes=10)
        fetch_history.return_value = {
            "messages": [
                _message(
                    "mid-old-opt-out",
                    client.igsid,
                    historical_at,
                    "Не пишіть мені більше, купувати не буду",
                )
            ],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        client.refresh_from_db()
        self.assertEqual(client.opted_out_at, old_opt_out_at)
        self.assertEqual(client.opted_in_at, opted_in_at)
        self.assertFalse(client.bot_paused)
        self.assertEqual(client.stage, IgClient.Stage.CHECKOUT)
        self.assertEqual(client.buying_readiness, 80)
        self.assertEqual(client.intent, IgClient.Intent.PAYMENT)
        self.assertEqual(client.primary_objection, IgClient.Objection.PRICE)
        self.assertEqual(client.language, "uk")
        self.assertEqual(client.sales_context, {"stable": True})

    @patch("management.services.bot_conversation_analysis.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_old_intent_does_not_override_newer_live_projection_and_transcript_is_chronological(
        self,
        _transport,
        _token,
        fetch_history,
        _schedule_refresh_analysis,
        _schedule_rules_analysis,
    ):
        from management.services import bot_conversation_analysis

        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        client = IgClient.get_or_create_for_sender("intent-history-participant")
        item = IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-intent-history",
            participant_igsid=client.igsid,
            client=client,
        )
        live_at = self.cutoff - timedelta(minutes=1)
        live = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Хочу оплатити замовлення",
            mid="mid-newer-live-payment",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
            provider_created_at=live_at,
        )
        client.intent = IgClient.Intent.PAYMENT
        client.save(update_fields=["intent", "updated_at"])
        self.assertEqual(client.intent, IgClient.Intent.PAYMENT)

        historical_at = self.cutoff - timedelta(minutes=10)
        fetch_history.return_value = {
            "messages": [
                _message(
                    "mid-old-size-intent",
                    client.igsid,
                    historical_at,
                    "Який розмір L?",
                )
            ],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        client.refresh_from_db()
        historical = InstagramBotMessage.objects.get(mid="mid-old-size-intent")
        self.assertEqual(client.intent, IgClient.Intent.PAYMENT)
        transcript, _by_id, _media = bot_conversation_analysis._conversation(
            client.pk,
            historical.pk,
        )
        self.assertEqual(
            [row["message_id"] for row in transcript],
            [historical.pk, live.pk],
        )

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_historical_manager_timestamp_uses_provider_time(
        self, _transport, _token, fetch_history, _schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        client = IgClient.get_or_create_for_sender("manager-history-participant")
        IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-manager-history",
            participant_igsid=client.igsid,
            client=client,
        )
        manager_at = self.cutoff - timedelta(minutes=7)
        fetch_history.return_value = {
            "messages": [
                _message(
                    "mid-old-manager",
                    self.settings.ig_user_id,
                    manager_at,
                    "Відповідь менеджера",
                    recipient=client.igsid,
                )
            ],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        client.refresh_from_db()
        self.assertEqual(client.last_manager_message_at, manager_at)

    @patch("management.services.bot_conversation_analysis.schedule_analysis")
    def test_rule_projection_rejects_message_older_than_newer_snapshot(
        self, _schedule_analysis
    ):
        from management.services import bot_sales_classifier

        client = IgClient.objects.create(
            igsid="rules-watermark-participant",
            intent=IgClient.Intent.PAYMENT,
        )
        older = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Який розмір L?",
            mid="mid-rules-older",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=self.cutoff - timedelta(minutes=10),
        )
        newer = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Оплата",
            mid="mid-rules-newer",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
            provider_created_at=self.cutoff - timedelta(minutes=1),
        )
        IgConversationAnalysisSnapshot.objects.create(
            client=client,
            last_analyzed_message=newer,
            dedupe_key=f"rules:test:{client.pk}:{newer.pk}",
            score_band=IgConversationAnalysisSnapshot.Band.CHECKOUT,
            interaction_type=IgConversationAnalysisSnapshot.InteractionType.HIGH_INTENT,
            analysis_model="rules",
        )

        result = bot_sales_classifier.ensure_rule_classification(client, older)

        client.refresh_from_db()
        self.assertIsNone(result)
        self.assertEqual(client.intent, IgClient.Intent.PAYMENT)

    @patch("management.services.bot_conversation_analysis.schedule_analysis")
    def test_rule_projection_fails_closed_for_ambiguous_equal_provider_time(
        self, _schedule_analysis
    ):
        from management.services import bot_sales_classifier

        client = IgClient.objects.create(
            igsid="rules-equal-time-participant",
            stage=IgClient.Stage.CHECKOUT,
            intent=IgClient.Intent.PAYMENT,
            buying_readiness=80,
            primary_objection=IgClient.Objection.PRICE,
        )
        event_at = self.cutoff - timedelta(minutes=1)
        live = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Оплата",
            mid="mid-rules-equal-live",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
            provider_created_at=event_at,
        )
        historical = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Купувати не буду",
            mid="mid-rules-equal-history",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=event_at,
        )
        self.assertLess(live.pk, historical.pk)

        result = bot_sales_classifier.ensure_rule_classification(client, historical)

        client.refresh_from_db()
        self.assertIsNone(result)
        self.assertEqual(client.stage, IgClient.Stage.CHECKOUT)
        self.assertEqual(client.intent, IgClient.Intent.PAYMENT)
        self.assertEqual(client.buying_readiness, 80)
        self.assertEqual(client.primary_objection, IgClient.Objection.PRICE)

    @patch("management.services.ig_inbox_refresh.schedule_analysis")
    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_missed_exchange_message_opens_post_sale_case(
        self, _transport, _token, fetch_history, _schedule_analysis
    ):
        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        client = IgClient.get_or_create_for_sender("exchange-participant")
        IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-exchange",
            participant_igsid=client.igsid,
            client=client,
        )
        created = self.cutoff - timedelta(minutes=3)
        fetch_history.return_value = {
            "messages": [_message("mid-exchange", client.igsid, created, "Хочу обміняти розмір M на L")],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        ig_inbox_refresh.process_refresh_slice(now=self.cutoff)

        case = IgPostSaleCase.objects.get(client=client)
        self.assertEqual(case.case_type, IgPostSaleCase.CaseType.EXCHANGE)
        self.assertEqual(case.source_message.mid, "mid-exchange")

    def test_older_exchange_still_opens_case_without_rewinding_newer_projection(self):
        from management.services import bot_sales_classifier

        client = IgClient.get_or_create_for_sender("historical-exchange-projection")
        older = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Футболка вже у вас. Є розміри для заміни?",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=self.cutoff - timedelta(days=2),
        )
        newer = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Оплату вже підтверджено",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
            provider_created_at=self.cutoff - timedelta(minutes=2),
        )
        client.stage = IgClient.Stage.PAID
        client.intent = IgClient.Intent.PAYMENT
        client.buying_readiness = 100
        client.save(update_fields=["stage", "intent", "buying_readiness", "updated_at"])

        result = bot_sales_classifier.ensure_rule_classification(
            client,
            older,
            operational_effects=False,
        )

        client.refresh_from_db()
        self.assertIsNone(result)
        self.assertEqual(client.stage, IgClient.Stage.PAID)
        self.assertEqual(client.intent, IgClient.Intent.PAYMENT)
        self.assertEqual(client.buying_readiness, 100)
        case = IgPostSaleCase.objects.get(client=client)
        self.assertEqual(case.source_message_id, older.pk)
        self.assertGreater(newer.pk, older.pk)

    @patch("management.services.ig_inbox_refresh.bot._fetch_polled_conversation")
    @patch("management.services.ig_inbox_refresh.bot.get_page_token", return_value="PT")
    @patch("management.services.ig_inbox_refresh.bot.provider_transport", return_value=bot.INSTAGRAM_LOGIN_TRANSPORT)
    def test_reconciliation_does_not_requeue_historical_refresh_for_ai(
        self, _transport, _token, fetch_history
    ):
        from management.services.bot_conversation_analysis import reconcile_analysis_jobs

        self.run.status = IgInboxRefreshRun.Status.RUNNING
        self.run.discovery_complete = True
        self.run.save(update_fields=["status", "discovery_complete", "updated_at"])
        client = IgClient.get_or_create_for_sender("analysis-recovery-participant")
        IgInboxRefreshItem.objects.create(
            run=self.run,
            conversation_id="conv-analysis-recovery",
            participant_igsid=client.igsid,
            client=client,
        )
        created = self.cutoff - timedelta(minutes=4)
        fetch_history.return_value = {
            "messages": [_message("mid-analysis-recovery", client.igsid, created, "Потрібен розмір L")],
            "requests": 1,
            "complete": True,
            "budget_exhausted": False,
            "reason": "instagram_latest_window",
        }

        with patch(
            "management.services.ig_inbox_refresh.schedule_analysis",
            side_effect=RuntimeError("scheduler unavailable"),
        ), patch(
            "management.services.bot_conversation_analysis.schedule_analysis",
            side_effect=RuntimeError("scheduler unavailable"),
        ):
            ig_inbox_refresh.process_refresh_slice(now=self.cutoff)
        self.assertFalse(IgConversationAnalysisJob.objects.filter(client=client).exists())

        result = reconcile_analysis_jobs(
            limit=50,
            now=self.cutoff + timedelta(seconds=1),
        )

        self.assertFalse(IgConversationAnalysisJob.objects.filter(client=client).exists())
        self.assertEqual(result["queued"], 0)
        self.assertEqual(result["historical_blocked"], 1)


class InboxRefreshWebhookRaceTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.ig_user_id = "17841467101471112"
        self.settings.is_enabled = True
        self.settings.allowed_senders = ""
        self.settings.reply_after = timezone.now() - timedelta(days=1)
        self.settings.save(update_fields=[
            "ig_user_id", "is_enabled", "allowed_senders", "reply_after",
        ])

    def test_delayed_webhook_promotes_matching_manual_refresh_row(self):
        client = IgClient.get_or_create_for_sender("webhook-after-refresh")
        received_at = timezone.now() - timedelta(minutes=1)
        history = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Покажіть футболку",
            mid="mid-refresh-before-webhook",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=received_at,
            processed_at=timezone.now(),
        )

        with patch("management.services.bot_sales_classifier.classify_message", return_value={"interaction_type": "product_question"}), patch(
            "management.services.bot_followups.schedule_after_inbound"
        ):
            queued = bot.enqueue_inbound(
                self.settings,
                sender_id=client.igsid,
                text=history.text,
                mid=history.mid,
                source="webhook",
                received_at=received_at,
            )

        self.assertTrue(queued)
        history.refresh_from_db()
        self.assertEqual(history.status, InstagramBotMessage.Status.PENDING)
        self.assertEqual(history.source, "webhook")
        self.assertIsNone(history.processed_at)
        self.assertEqual(InstagramBotMessage.objects.filter(mid=history.mid).count(), 1)

    def test_webhook_promotion_changes_analysis_fingerprint(self):
        from management.services import bot_conversation_analysis as analysis

        client = IgClient.get_or_create_for_sender("webhook-fingerprint-refresh")
        received_at = timezone.now() - timedelta(minutes=1)
        history = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Покажіть футболку",
            mid="mid-refresh-fingerprint",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=received_at,
            processed_at=timezone.now(),
        )
        before = analysis._required_state_fingerprint(client, history.pk)

        with patch(
            "management.services.bot_sales_classifier.classify_message",
            return_value={"interaction_type": "product_question"},
        ), patch("management.services.bot_followups.schedule_after_inbound"):
            queued = bot.enqueue_inbound(
                self.settings,
                sender_id=client.igsid,
                text=history.text,
                mid=history.mid,
                source="webhook",
                attachments=["https://example.invalid/product.jpg"],
                received_at=received_at,
            )

        self.assertTrue(queued)
        after = analysis._required_state_fingerprint(client, history.pk)
        self.assertNotEqual(after, before)

    @patch("management.services.bot_conversation_analysis.schedule_analysis")
    def test_persistence_only_webhook_keeps_terminal_history_done(
        self, schedule_analysis
    ):
        terminal_cases = (
            (
                "reaction",
                "🔥",
                IgConversationAnalysisSnapshot.InteractionType.REACTION_ONLY,
            ),
            (
                "no-buy",
                "Купувати не буду",
                IgConversationAnalysisSnapshot.InteractionType.EXPLICIT_NO_BUY,
            ),
        )
        for offset, (label, text, interaction_type) in enumerate(terminal_cases, start=1):
            with self.subTest(label=label):
                client = IgClient.get_or_create_for_sender(f"terminal-{label}")
                received_at = timezone.now() - timedelta(minutes=offset)
                history = InstagramBotMessage.objects.create(
                    sender_id=client.igsid,
                    client=client,
                    role=InstagramBotMessage.Role.USER,
                    text=text,
                    mid=f"mid-terminal-{label}",
                    status=InstagramBotMessage.Status.DONE,
                    source="manual_refresh",
                    provider_created_at=received_at,
                    processed_at=timezone.now(),
                )
                IgConversationAnalysisSnapshot.objects.create(
                    client=client,
                    last_analyzed_message=history,
                    dedupe_key=f"rules:terminal:{client.pk}:{history.pk}",
                    score_band=IgConversationAnalysisSnapshot.Band.LOST,
                    interaction_type=interaction_type,
                    analysis_model="rules",
                )
                payload = {"entry": [{"messaging": [{
                    "sender": {"id": client.igsid},
                    "recipient": {"id": self.settings.ig_user_id},
                    "timestamp": int(received_at.timestamp() * 1000),
                    "message": {"mid": history.mid, "text": history.text},
                }]}]}

                handled = bot.handle_webhook_payload(
                    self.settings,
                    payload,
                    persistence_only=True,
                )

                self.assertEqual(handled, 1)
                history.refresh_from_db()
                self.assertEqual(history.status, InstagramBotMessage.Status.DONE)
                self.assertEqual(history.source, "webhook")
        self.assertFalse(InstagramBotMessage.objects.filter(
            status=InstagramBotMessage.Status.PENDING,
            mid__startswith="mid-terminal-",
        ).exists())
        self.assertEqual(schedule_analysis.call_count, len(terminal_cases))

    @patch("management.services.bot_conversation_analysis.schedule_analysis")
    def test_older_webhook_is_observed_not_promoted_after_newer_user_event(
        self, schedule_analysis
    ):
        client = IgClient.get_or_create_for_sender("webhook-older-than-live")
        older_at = timezone.now() - timedelta(minutes=10)
        newer_at = timezone.now() - timedelta(minutes=1)
        newer = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="newer live message",
            mid="mid-newer-live-before-history",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
            provider_created_at=newer_at,
            processed_at=timezone.now(),
        )
        history = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="older recovered message",
            mid="mid-older-history-after-live",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=older_at,
            processed_at=timezone.now(),
        )

        handled = bot.enqueue_inbound(
            self.settings,
            sender_id=client.igsid,
            text=history.text,
            mid=history.mid,
            source="webhook",
            received_at=older_at,
            persistence_only=True,
        )

        self.assertTrue(handled)
        history.refresh_from_db()
        self.assertEqual(history.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(history.source, "manual_refresh")
        self.assertFalse(InstagramBotMessage.objects.filter(
            client=client,
            status=InstagramBotMessage.Status.PENDING,
        ).exists())
        schedule_analysis.assert_called_once()
        self.assertEqual(schedule_analysis.call_args.args[1].pk, max(history.pk, newer.pk))

    @patch("management.services.bot_conversation_analysis.schedule_analysis")
    def test_older_webhook_is_observed_after_newer_manager_event(self, schedule_analysis):
        client = IgClient.get_or_create_for_sender("webhook-older-than-manager")
        older_at = timezone.now() - timedelta(minutes=10)
        history = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="старе відновлене повідомлення",
            mid="mid-older-history-after-manager",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=older_at,
            processed_at=timezone.now(),
        )
        InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.MANAGER,
            text="Менеджер вже відповів",
            status=InstagramBotMessage.Status.DONE,
            source="echo",
            created_at=timezone.now(),
        )

        handled = bot.enqueue_inbound(
            self.settings,
            sender_id=client.igsid,
            text=history.text,
            mid=history.mid,
            source="webhook",
            received_at=older_at,
        )

        self.assertTrue(handled)
        history.refresh_from_db()
        self.assertEqual(history.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(history.source, "manual_refresh")
        schedule_analysis.assert_called_once()

    @patch("management.services.bot_conversation_analysis.schedule_analysis")
    def test_equal_time_webhook_is_observed_when_live_event_has_lower_pk(
        self, schedule_analysis
    ):
        client = IgClient.get_or_create_for_sender("webhook-equal-time-ambiguous")
        event_at = timezone.now() - timedelta(minutes=1)
        live = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="live message stored first",
            mid="mid-equal-time-live-first",
            status=InstagramBotMessage.Status.DONE,
            source="webhook",
            provider_created_at=event_at,
            processed_at=timezone.now(),
        )
        history = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="history stored second",
            mid="mid-equal-time-history-second",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=event_at,
            processed_at=timezone.now(),
        )
        self.assertLess(live.pk, history.pk)

        handled = bot.enqueue_inbound(
            self.settings,
            sender_id=client.igsid,
            text=history.text,
            mid=history.mid,
            source="webhook",
            received_at=event_at,
            persistence_only=True,
        )

        self.assertTrue(handled)
        history.refresh_from_db()
        self.assertEqual(history.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(history.source, "manual_refresh")
        schedule_analysis.assert_called_once()

    @patch("management.services.bot_conversation_analysis.schedule_analysis")
    def test_delayed_opt_out_webhook_cannot_cancel_newer_manual_opt_in(
        self, schedule_analysis
    ):
        older_at = timezone.now() - timedelta(minutes=10)
        opted_in_at = timezone.now() - timedelta(minutes=1)
        client = IgClient.objects.create(
            igsid="delayed-opt-out-after-opt-in",
            opted_out_at=older_at - timedelta(minutes=1),
            opted_in_at=opted_in_at,
            bot_paused=False,
            stage=IgClient.Stage.CHECKOUT,
            buying_readiness=80,
            intent=IgClient.Intent.PAYMENT,
            primary_objection=IgClient.Objection.PRICE,
        )
        history = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Не пишіть мені більше, купувати не буду",
            mid="mid-delayed-opt-out-after-opt-in",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=older_at,
            processed_at=timezone.now(),
        )

        handled = bot.enqueue_inbound(
            self.settings,
            sender_id=client.igsid,
            text=history.text,
            mid=history.mid,
            source="webhook",
            received_at=older_at,
            persistence_only=True,
        )

        self.assertTrue(handled)
        client.refresh_from_db()
        history.refresh_from_db()
        self.assertEqual(client.opted_in_at, opted_in_at)
        self.assertEqual(client.opted_out_at, older_at - timedelta(minutes=1))
        self.assertFalse(client.bot_paused)
        self.assertEqual(client.stage, IgClient.Stage.CHECKOUT)
        self.assertEqual(client.buying_readiness, 80)
        self.assertEqual(client.intent, IgClient.Intent.PAYMENT)
        self.assertEqual(client.primary_objection, IgClient.Objection.PRICE)
        self.assertEqual(history.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(history.source, "manual_refresh")
        schedule_analysis.assert_called_once()

    def test_mid_collision_for_different_client_fails_closed(self):
        original = IgClient.get_or_create_for_sender("collision-original")
        other = IgClient.get_or_create_for_sender("collision-other")
        history = InstagramBotMessage.objects.create(
            sender_id=original.igsid,
            client=original,
            role=InstagramBotMessage.Role.USER,
            text="original",
            mid="mid-cross-client-collision",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
        )

        with patch("management.services.bot_sales_classifier.classify_message") as classifier:
            queued = bot.enqueue_inbound(
                self.settings,
                sender_id=other.igsid,
                text="conflicting",
                mid=history.mid,
                source="webhook",
                received_at=timezone.now(),
            )

        self.assertFalse(queued)
        history.refresh_from_db()
        self.assertEqual(history.client_id, original.pk)
        self.assertEqual(history.sender_id, original.igsid)
        self.assertEqual(history.source, "manual_refresh")
        classifier.assert_not_called()

    def test_manual_refresh_before_reply_cutoff_is_not_promoted(self):
        client = IgClient.get_or_create_for_sender("webhook-before-reply-cutoff")
        self.settings.reply_after = timezone.now()
        self.settings.save(update_fields=["reply_after"])
        received_at = self.settings.reply_after - timedelta(seconds=1)
        history = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="old message",
            mid="mid-before-reply-cutoff",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=received_at,
            processed_at=timezone.now(),
        )

        queued = bot.enqueue_inbound(
            self.settings,
            sender_id=client.igsid,
            text=history.text,
            mid=history.mid,
            source="webhook",
            received_at=received_at,
        )

        self.assertFalse(queued)
        history.refresh_from_db()
        self.assertEqual(history.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(history.source, "manual_refresh")

    def test_manual_refresh_timestamp_mismatch_is_not_promoted(self):
        client = IgClient.get_or_create_for_sender("webhook-time-mismatch")
        provider_time = timezone.now() - timedelta(minutes=1)
        history = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="same mid wrong time",
            mid="mid-time-mismatch",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=provider_time,
            processed_at=timezone.now(),
        )

        queued = bot.enqueue_inbound(
            self.settings,
            sender_id=client.igsid,
            text=history.text,
            mid=history.mid,
            source="webhook",
            received_at=provider_time + timedelta(seconds=5),
        )

        self.assertFalse(queued)
        history.refresh_from_db()
        self.assertEqual(history.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(history.source, "manual_refresh")

    def test_replayed_webhook_does_not_queue_promoted_row_twice(self):
        client = IgClient.get_or_create_for_sender("webhook-replayed")
        received_at = timezone.now() - timedelta(minutes=1)
        history = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="one delivery",
            mid="mid-webhook-replayed",
            status=InstagramBotMessage.Status.DONE,
            source="manual_refresh",
            provider_created_at=received_at,
            processed_at=timezone.now(),
        )

        with patch("management.services.bot_sales_classifier.classify_message", return_value={"interaction_type": "product_question"}), patch(
            "management.services.bot_followups.schedule_after_inbound"
        ):
            first = bot.enqueue_inbound(
                self.settings,
                sender_id=client.igsid,
                text=history.text,
                mid=history.mid,
                source="webhook",
                received_at=received_at,
            )
            second = bot.enqueue_inbound(
                self.settings,
                sender_id=client.igsid,
                text=history.text,
                mid=history.mid,
                source="webhook",
                received_at=received_at,
            )

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(InstagramBotMessage.objects.filter(mid=history.mid).count(), 1)


class InboxRefreshDaemonTests(TestCase):
    @patch("management.management.commands.run_instagram_bot.close_old_connections")
    @patch("management.services.ig_inbox_refresh.process_refresh_slice", return_value={"worked": False})
    def test_daemon_worker_invokes_manual_refresh_consumer(self, process_slice, _close):
        from management.management.commands import run_instagram_bot as runner

        stop_event = Mock()
        stop_event.is_set.side_effect = [False, True]
        stop_event.wait.return_value = True

        runner._inbox_refresh_worker(stop_event)

        process_slice.assert_called_once_with()
