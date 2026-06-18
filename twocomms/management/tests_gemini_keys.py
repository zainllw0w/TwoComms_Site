import datetime
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from management.models import GeminiKeyState, LeadCheckerSettings


class GeminiKeyStateModelTests(TestCase):
    def test_get_creates_row(self):
        st = GeminiKeyState.get("GEMINI_API")
        self.assertEqual(st.key_name, "GEMINI_API")
        self.assertIsNone(st.cooldown_until)
        self.assertEqual(st.requests_today, 0)

    def test_get_is_idempotent(self):
        a = GeminiKeyState.get("GEMINI_API2")
        a.requests_today = 5
        a.save()
        b = GeminiKeyState.get("GEMINI_API2")
        self.assertEqual(b.requests_today, 5)
        self.assertEqual(GeminiKeyState.objects.filter(key_name="GEMINI_API2").count(), 1)


class LeadCheckerSettingsAutoRecheckTests(TestCase):
    def test_auto_recheck_defaults(self):
        s = LeadCheckerSettings.load()
        self.assertFalse(s.auto_recheck)
        self.assertEqual(s.auto_recheck_batch, 25)
