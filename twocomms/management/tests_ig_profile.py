"""Тести Phase 3 / Task 11 — підвантаження профілю IG-клієнта (Graph API).

При першому контакті бот тягне name/username/profile_pic через Graph і кладе в
картку, щоб у CRM було видно, хто саме пише (з аватаркою).
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, InstagramBotSettings
from management.services import instagram_bot as bot


class FetchProfileTests(TestCase):
    @patch("management.services.instagram_bot.get_page_token")
    @patch("management.services.instagram_bot._http")
    def test_fetch_parses_profile(self, mock_http, mock_pt):
        mock_pt.return_value = "PT"
        mock_http.return_value = (
            200, '{"name":"Іван","username":"ivan","profile_pic":"https://cdn/a.jpg"}'
        )
        prof = bot.fetch_ig_profile(InstagramBotSettings.load(), "u1")
        self.assertEqual(prof["name"], "Іван")
        self.assertEqual(prof["username"], "ivan")
        self.assertEqual(prof["profile_pic"], "https://cdn/a.jpg")

    @patch("management.services.instagram_bot.get_page_token")
    def test_fetch_empty_without_token(self, mock_pt):
        mock_pt.return_value = ""
        self.assertEqual(bot.fetch_ig_profile(InstagramBotSettings.load(), "u1"), {})


class EnsureProfileTests(TestCase):
    @patch("management.services.instagram_bot.fetch_ig_profile")
    def test_ensure_stores_profile(self, mock_fetch):
        mock_fetch.return_value = {"name": "Іван", "username": "ivan", "profile_pic": "https://cdn/a.jpg"}
        c = IgClient.get_or_create_for_sender("u2")
        self.assertTrue(bot.ensure_profile(InstagramBotSettings.load(), c))
        c.refresh_from_db()
        self.assertEqual(c.display_name, "Іван")
        self.assertEqual(c.username, "ivan")
        self.assertEqual(c.profile_pic_url, "https://cdn/a.jpg")
        self.assertIsNotNone(c.profile_fetched_at)

    @patch("management.services.instagram_bot.fetch_ig_profile")
    def test_ensure_skips_when_already_fetched(self, mock_fetch):
        c = IgClient.get_or_create_for_sender("u3")
        c.profile_fetched_at = timezone.now()
        c.save()
        self.assertFalse(bot.ensure_profile(InstagramBotSettings.load(), c))
        self.assertEqual(mock_fetch.call_count, 0)
