from datetime import timedelta

from django.test import SimpleTestCase, override_settings

from management.services.ig_manager_media_projection import (
    expire_failed_capture_urls,
    project_manager_media,
    redact_notification_payload,
)
from django.utils import timezone


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class ManagerMediaProjectionTests(SimpleTestCase):
    def test_private_customer_media_has_only_authorized_preview_metadata(self):
        projected = project_manager_media([{
            "url": "https://lookaside.fbsbx.com/signed?token=secret",
            "storage_name": "ig_message_media/42/private.jpg",
            "private_storage": True,
            "message_id": 42,
            "source_part_id": "mp1_" + "a" * 32,
            "content_hash": "b" * 64,
            "role": "receipt",
        }])

        self.assertEqual(projected[0]["availability"], "private_preview")
        self.assertTrue(projected[0]["preview_url"].startswith("https://management.twocomms.shop/"))
        self.assertIn("/bot/private-media/42/", projected[0]["preview_url"])
        self.assertNotIn("url", projected[0])
        self.assertNotIn("storage_name", projected[0])
        self.assertNotIn("content_hash", projected[0])
        self.assertNotIn("secret", repr(projected))

    def test_legacy_provider_url_is_unavailable_not_a_telegram_candidate(self):
        projected = project_manager_media([{
            "url": "https://scontent.cdninstagram.com/expired?signature=secret",
            "role": "customer_media",
        }])

        self.assertEqual(projected, [{"role": "customer_media", "availability": "unavailable"}])

    def test_payload_redaction_keeps_unrelated_alert_content(self):
        payload = redact_notification_payload({
            "text": "Need manager review",
            "event_type": "escalation",
            "media": [{
                "url": "https://lookaside.fbsbx.com/signed?token=secret",
                "message_id": 9,
                "role": "customer_media",
            }],
        })

        self.assertEqual(payload["text"], "Need manager review")
        self.assertEqual(payload["event_type"], "escalation")
        self.assertNotIn("url", payload["media"][0])

    def test_expired_failed_url_becomes_a_coverage_tombstone(self):
        result = expire_failed_capture_urls([{
            "source_part_id": "mp1_" + "a" * 32,
            "original_index": 2,
            "status": "unavailable",
            "error_kind": "download_failed",
            "url": "https://lookaside.fbsbx.com/expired?token=secret",
            "url_metadata_delete_after": timezone.now() - timedelta(seconds=1),
        }], now=timezone.now())

        self.assertNotIn("url", result[0])
        self.assertTrue(result[0]["url_metadata_expired"])
        self.assertEqual(result[0]["source_part_id"], "mp1_" + "a" * 32)

    def test_text_and_markup_provider_urls_are_replaced_with_preview(self):
        payload = redact_notification_payload({
            "text": "Source https://lookaside.fbsbx.com/file?token=secret",
            "reply_markup": {"inline_keyboard": [[{
                "text": "source",
                "url": "https://scontent.cdninstagram.com/file?signature=secret",
            }]]},
            "media": [{
                "message_id": 5,
                "source_part_id": "mp1_" + "a" * 32,
                "private_storage": True,
                "role": "receipt",
            }],
        })

        self.assertNotIn("secret", repr(payload))
        self.assertIn("Приватний перегляд:", payload["text"])
        self.assertEqual(
            payload["reply_markup"]["inline_keyboard"][0][0]["url"],
            "https://management.twocomms.shop/bot/private-media/5/mp1_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/preview/",
        )

    def test_untrusted_preprojected_preview_is_downgraded(self):
        projected = project_manager_media([{
            "role": "receipt",
            "availability": "private_preview",
            "preview_url": "https://evil.example/bot/private-media/5/mp1_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/preview/?token=secret",
        }])

        self.assertEqual(projected, [{"role": "receipt", "availability": "unavailable"}])

    def test_payload_redaction_is_idempotent_for_preview_buttons(self):
        payload = {
            "text": "Review",
            "media": [{
                "message_id": 5,
                "source_part_id": "mp1_" + "a" * 32,
                "private_storage": True,
                "role": "receipt",
            }],
        }

        first = redact_notification_payload(payload)
        second = redact_notification_payload(first)

        self.assertEqual(second, first)
