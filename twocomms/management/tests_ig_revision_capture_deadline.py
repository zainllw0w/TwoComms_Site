"""Revision media deadlines reach the real bounded fetch adapter."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from management.services import instagram_bot as bot
from management.services import ig_media_url_policy as media_policy


class RevisionCaptureDeadlineTests(SimpleTestCase):
    def test_fetch_receives_remaining_budget_and_expired_budget_never_dispatches(self):
        outcome = media_policy.FetchOutcome(success=False, reason=media_policy.REASON_DEADLINE)
        with patch.object(media_policy, "fetch_media", return_value=outcome) as fetch:
            self.assertIsNone(bot.download_image("https://lookaside.example/a", deadline_seconds=0.25))
            self.assertEqual(fetch.call_args.kwargs["deadline_seconds"], 0.25)
            fetch.reset_mock()
            self.assertIsNone(bot.download_image("https://lookaside.example/a", deadline_seconds=0))
            fetch.assert_not_called()

    def test_expired_revision_starts_no_source_capture_claim(self):
        part = {
            "url": "https://lookaside.example/a", "source_part_id": "owned-source",
            "provenance": bot.MEDIA_PROVENANCE_LIVE_WEBHOOK, "status": bot.MEDIA_STATUS_PENDING,
        }
        row = SimpleNamespace(pk=9, source="webhook", attachment_media=[part], attachments="", media_capture_eligible=True)
        with patch.object(bot, "_persist_media_metadata", return_value=[part]), patch.object(
            bot, "_private_media_storage"
        ), patch.object(bot, "_claim_media_capture") as claim:
            bot._capture_message_media(row, deadline_at=timezone.now() - timedelta(seconds=1))
        claim.assert_not_called()
