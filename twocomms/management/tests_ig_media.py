"""Тести Phase 1 / Task 6 — збір медіа з повідомлення у байти для vision.

_collect_images() завантажує вкладення (через download_image) у список
(mime, bytes), який далі йде в мультимодальний вхід Gemini. Винесено з
_process_one, щоб бути тестованим і переюзабельним матчингом (Task 8/9).
"""
import json
from unittest.mock import patch

from django.test import TestCase

from management.services import instagram_bot as bot


class CollectImagesTests(TestCase):
    @patch("management.services.instagram_bot.download_image")
    def test_collects_only_successful_downloads(self, mock_dl):
        mock_dl.side_effect = lambda u: ("image/jpeg", b"x") if u != "bad" else None
        attachments = json.dumps(["https://cdn/a.jpg", "bad", "https://cdn/b.jpg"])
        imgs = bot._collect_images(attachments)
        self.assertEqual(len(imgs), 2)
        self.assertEqual(imgs[0], ("image/jpeg", b"x"))

    @patch("management.services.instagram_bot.download_image")
    def test_caps_to_limit(self, mock_dl):
        mock_dl.return_value = ("image/jpeg", b"x")
        attachments = json.dumps([f"u{i}" for i in range(10)])
        imgs = bot._collect_images(attachments, limit=3)
        self.assertEqual(len(imgs), 3)
        self.assertEqual(mock_dl.call_count, 3)

    def test_empty_when_no_attachments(self):
        self.assertEqual(bot._collect_images(""), [])
        self.assertEqual(bot._collect_images(None), [])

    def test_bad_json_safe(self):
        self.assertEqual(bot._collect_images("not-json"), [])
