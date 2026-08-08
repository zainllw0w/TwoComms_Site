from django.test import SimpleTestCase, TestCase
from pathlib import Path

from management.models import InstagramBotSettings
from management.services import instagram_bot


class InstagramBotSecureDefaultsTests(SimpleTestCase):
    def test_fresh_settings_do_not_embed_account_allowlist_or_debug_reply(self):
        settings = InstagramBotSettings()

        self.assertEqual(settings.page_id, "")
        self.assertEqual(settings.ig_user_id, "")
        self.assertEqual(settings.allowed_senders, "")
        self.assertEqual(settings.trigger_text, "")
        self.assertEqual(settings.reply_text, "")

    def test_empty_allowlist_keeps_explicit_allow_all_semantics(self):
        settings = InstagramBotSettings(allowed_senders="")

        self.assertTrue(instagram_bot._is_allowed(settings, "new-sender"))

    def test_active_allowlist_is_visible_as_redacted_operator_warning(self):
        settings = InstagramBotSettings(
            page_id="configured-page",
            allowed_senders="955313600823130",
        )

        warnings = instagram_bot.configuration_warnings(settings)

        self.assertIn("sender_allowlist_active", warnings)
        self.assertNotIn("955313600823130", str(warnings))

    def test_empty_allowlist_is_visible_as_explicit_open_mode_warning(self):
        settings = InstagramBotSettings(page_id="configured-page")

        warnings = instagram_bot.configuration_warnings(settings)

        self.assertIn("sender_allowlist_open", warnings)


class InstagramBotWarningTemplateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = (
            Path(__file__).with_name("templates") / "management" / "bot.html"
        ).read_text(encoding="utf-8")

    def test_overview_renders_redacted_configuration_warning(self):
        for contract in (
            'id="bot-configuration-warning"',
            "configurationWarningLabels",
            "st.configuration_warnings",
            "sender_allowlist_open",
        ):
            self.assertIn(contract, self.template)


class InstagramBotStatusWarningTests(TestCase):
    def test_status_snapshot_exposes_warning_without_allowlist_values(self):
        settings = InstagramBotSettings.load()
        settings.page_id = "configured-page"
        settings.ig_user_id = "configured-ig-user"
        settings.allowed_senders = "955313600823130"
        settings.save(update_fields=["page_id", "ig_user_id", "allowed_senders", "updated_at"])

        snapshot = instagram_bot.status_snapshot()

        self.assertIn("sender_allowlist_active", snapshot["configuration_warnings"])
        self.assertNotIn("955313600823130", str(snapshot["configuration_warnings"]))
