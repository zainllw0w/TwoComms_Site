import json
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import IgBotNotification, IgClient, InstagramBotMessage
from management.services import instagram_bot as bot


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class NotificationMediaPrivacyTests(TestCase):
    @patch.dict(
        "os.environ",
        {"MANAGEMENT_TG_BOT_TOKEN": "test-token", "MANAGEMENT_TG_ADMIN_CHAT_ID": "123"},
        clear=False,
    )
    @patch(
        "management.services.instagram_bot._http",
        return_value=(200, json.dumps({"ok": True, "result": {"message_id": 71}})),
    )
    def test_new_private_media_notification_sends_only_main_preview_link(self, http):
        sent = bot.notify_manager(
            "Review attachment",
            dedupe_key="private-media-new",
            media=[{
                "role": "receipt",
                "url": "https://lookaside.fbsbx.com/file?token=secret",
                "private_storage": True,
                "storage_name": "ig_message_media/secret.jpg",
                "message_id": 12,
                "source_part_id": "mp1_" + "a" * 32,
            }],
        )

        row = IgBotNotification.objects.get(dedupe_key="private-media-new")
        self.assertTrue(sent)
        self.assertEqual(row.status, IgBotNotification.Status.SENT)
        self.assertNotIn("secret", repr(row.payload))
        self.assertEqual(row.payload["media"][0]["delivery_status"], "not_forwarded_private")
        self.assertEqual(sum(call.args[0].endswith("/sendMessage") for call in http.call_args_list), 1)
        self.assertEqual(sum(call.args[0].endswith("/sendPhoto") for call in http.call_args_list), 0)

    @patch.dict(
        "os.environ",
        {"MANAGEMENT_TG_BOT_TOKEN": "test-token", "MANAGEMENT_TG_ADMIN_CHAT_ID": "123"},
        clear=False,
    )
    @patch(
        "management.services.instagram_bot._http",
        return_value=(200, json.dumps({"ok": True, "result": {"message_id": 72}})),
    )
    def test_queued_provider_url_is_sanitized_before_delivery(self, http):
        row = IgBotNotification.objects.create(
            dedupe_key="private-media-queued",
            payload={
                "text": "https://lookaside.fbsbx.com/file?token=secret",
                "chat_id": "123",
                "media": [{"role": "receipt", "url": "https://lookaside.fbsbx.com/file?token=secret"}],
            },
        )

        self.assertTrue(bot._deliver_manager_notification(row.dedupe_key))
        row.refresh_from_db()
        self.assertEqual(row.status, IgBotNotification.Status.SENT)
        self.assertNotIn("secret", repr(row.payload))
        self.assertEqual(row.payload["media"][0]["delivery_status"], "not_forwarded_private")
        self.assertEqual(sum(call.args[0].endswith("/sendPhoto") for call in http.call_args_list), 0)

    def test_legacy_failed_url_is_removed_from_metadata_and_attachments(self):
        client = IgClient.objects.create(igsid="failed-url-cleanup")
        url = "https://lookaside.fbsbx.com/file?token=secret"
        row = InstagramBotMessage.objects.create(
            client=client,
            sender_id=client.igsid,
            role=InstagramBotMessage.Role.USER,
            attachments=json.dumps([url]),
            attachment_media=[{
                "source_part_id": "mp1_" + "a" * 32,
                "original_index": 0,
                "provenance": "live_webhook",
                "status": "unavailable",
                "error_kind": "download_failed",
                "url": url,
            }],
        )
        old = timezone.now() - timedelta(days=2)
        InstagramBotMessage.objects.filter(pk=row.pk).update(created_at=old)
        cache.delete("ig_failed_media_url_cleanup_cursor")

        self.assertEqual(bot.purge_expired_failed_media_url_metadata(now=timezone.now(), limit=10), 1)

        row.refresh_from_db()
        self.assertEqual(row.attachments, "[]")
        self.assertNotIn("url", row.attachment_media[0])
        self.assertTrue(row.attachment_media[0]["url_metadata_expired"])

    def test_new_failure_sets_once_only_bounded_url_metadata_ttl(self):
        from management.services.ig_media_url_policy import FetchOutcome, REASON_TRANSPORT

        first = bot._capture_failure_updates(
            FetchOutcome(success=False, reason=REASON_TRANSPORT),
            {"capture_attempts": 1},
        )
        second = bot._capture_failure_updates(
            FetchOutcome(success=False, reason=REASON_TRANSPORT),
            {"capture_attempts": 2, "url_metadata_delete_after": first["url_metadata_delete_after"]},
        )

        self.assertIn("url_metadata_delete_after", first)
        self.assertNotIn("url_metadata_delete_after", second)

    def test_failure_finalization_persists_url_ttl_on_the_actual_part(self):
        client = IgClient.objects.create(igsid="failure-ttl")
        source_part_id = "mp1_" + "b" * 32
        row = InstagramBotMessage.objects.create(
            client=client,
            sender_id=client.igsid,
            role=InstagramBotMessage.Role.USER,
            source="webhook",
            attachment_media=[{
                "source_part_id": source_part_id,
                "url": "https://lookaside.fbsbx.com/file?token=secret",
                "status": "acquiring",
                "capture_token": "failure-token",
            }],
        )

        bot._finish_media_capture(
            row.pk, source_part_id, "failure-token",
            {"status": "unavailable", "error_kind": "download_failed"},
        )

        row.refresh_from_db()
        self.assertTrue(row.attachment_media[0]["url_metadata_delete_after"])

    def test_two_private_preview_parts_remain_distinct_across_sent_replay(self):
        previews = [
            f"https://management.twocomms.shop/bot/private-media/5/mp1_{char * 32}/preview/"
            for char in ("a", "b")
        ]
        row = IgBotNotification.objects.create(
            dedupe_key="preview-identity-replay",
            status=IgBotNotification.Status.SENT,
            telegram_message_id="88",
            payload={
                "text": "Review",
                "media": [
                    {"role": "ugc_evidence", "availability": "private_preview", "preview_url": url}
                    for url in previews
                ],
            },
        )

        self.assertTrue(bot.notify_manager(
            "Review",
            dedupe_key=row.dedupe_key,
            deliver_immediately=False,
            media=[
                {
                    "role": "ugc_evidence",
                    "private_storage": True,
                    "message_id": 5,
                    "source_part_id": "mp1_" + char * 32,
                }
                for char in ("a", "b")
            ],
        ))

        row.refresh_from_db()
        self.assertEqual(len(row.payload["media"]), 2)
        self.assertEqual(
            {item.get("preview_url") for item in row.payload["media"]}, set(previews),
        )
