import importlib

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from management.models import BotSecretEncryptionUnavailable, InstagramBotSettings
from management.services import instagram_bot as bot


TEST_FERNET_KEY = "Tj-k7EnSDEgaPpRWR9lEGgp2DmQ4LgU6L6-3P5qiv5U="


@override_settings(FIELD_ENCRYPTION_KEY=TEST_FERNET_KEY)
class InstagramBotSecretEncryptionTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()

    def test_custom_credentials_are_ciphertext_at_rest_and_plaintext_in_memory(self):
        self.settings.custom_direct_token = "direct-secret-value"
        self.settings.custom_gemini_key = "gemini-secret-value"
        self.settings.save()

        raw_direct = self.settings.custom_direct_token_encrypted
        raw_gemini = self.settings.custom_gemini_key_encrypted
        self.assertTrue(raw_direct.startswith("fernet:v1:"))
        self.assertTrue(raw_gemini.startswith("fernet:v1:"))
        self.assertNotIn("direct-secret-value", raw_direct)
        self.assertNotIn("gemini-secret-value", raw_gemini)

        self.settings.refresh_from_db()
        self.assertNotIn("direct-secret-value", self.settings.custom_direct_token_encrypted)
        self.assertNotIn("gemini-secret-value", self.settings.custom_gemini_key_encrypted)
        self.assertEqual(self.settings.custom_direct_token, "direct-secret-value")
        self.assertEqual(self.settings.custom_gemini_key, "gemini-secret-value")
        self.assertTrue(self.settings.has_custom_direct_token)
        self.assertTrue(self.settings.has_custom_gemini_key)

    def test_token_resolvers_decrypt_custom_credentials_only_for_runtime_use(self):
        self.settings.direct_source = InstagramBotSettings.CredSource.CUSTOM
        self.settings.gemini_source = InstagramBotSettings.CredSource.CUSTOM
        self.settings.custom_direct_token = "direct-runtime-token"
        self.settings.custom_gemini_key = "gemini-runtime-key"
        self.settings.save()

        self.settings.refresh_from_db()
        self.assertEqual(bot.resolve_direct_token(self.settings), "direct-runtime-token")
        self.assertEqual(bot.resolve_gemini_key(self.settings), "gemini-runtime-key")

    @override_settings(FIELD_ENCRYPTION_KEY="")
    def test_custom_credentials_fail_closed_when_key_is_missing(self):
        with self.assertRaises(BotSecretEncryptionUnavailable):
            self.settings.custom_direct_token = "must-not-be-stored-plaintext"

        self.assertEqual(self.settings.custom_direct_token_encrypted, "")

    @override_settings(FIELD_ENCRYPTION_KEY="not-a-valid-fernet-key")
    def test_custom_credentials_fail_closed_when_key_is_malformed(self):
        with self.assertRaises(BotSecretEncryptionUnavailable):
            self.settings.custom_direct_token = "must-not-be-stored-plaintext"

        self.assertEqual(self.settings.custom_direct_token_encrypted, "")

    @override_settings(FIELD_ENCRYPTION_KEY="")
    def test_settings_api_refuses_plaintext_when_key_is_missing(self):
        user = get_user_model().objects.create_user(
            username="secret-settings-admin", password="x", is_staff=True
        )
        self.client.force_login(user)

        response = self.client.post(
            "/bot/api/settings/",
            {"custom_direct_token": "must-not-be-stored-plaintext"},
            HTTP_HOST="management.twocomms.shop",
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 503)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.custom_direct_token_encrypted, "")

    def test_legacy_plaintext_remains_readable_until_data_migration(self):
        InstagramBotSettings.objects.filter(pk=self.settings.pk).update(
            custom_direct_token_encrypted="legacy-direct-token"
        )

        self.settings.refresh_from_db()
        self.assertEqual(self.settings.custom_direct_token, "legacy-direct-token")

    def test_data_migration_encrypts_legacy_credentials(self):
        migration = importlib.import_module(
            "management.migrations.0136_encrypt_instagram_bot_settings_secrets"
        )
        InstagramBotSettings.objects.filter(pk=self.settings.pk).update(
            custom_direct_token_encrypted="legacy-direct-token",
            custom_gemini_key_encrypted="legacy-gemini-key",
        )

        class HistoricalApps:
            @staticmethod
            def get_model(app_label, model_name):
                self.assertEqual((app_label, model_name), ("management", "InstagramBotSettings"))
                return InstagramBotSettings

        migration.encrypt_legacy_credentials(HistoricalApps(), None)

        self.settings.refresh_from_db()
        self.assertTrue(self.settings.custom_direct_token_encrypted.startswith("fernet:v1:"))
        self.assertTrue(self.settings.custom_gemini_key_encrypted.startswith("fernet:v1:"))
        self.assertEqual(self.settings.custom_direct_token, "legacy-direct-token")
        self.assertEqual(self.settings.custom_gemini_key, "legacy-gemini-key")
