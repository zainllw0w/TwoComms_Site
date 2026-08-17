import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import transaction
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings

from accounts.signals import notify_admins_on_registration
from management.models import IgBotNotification


class RegistrationNotificationSignalTests(TestCase):
    def test_test_runs_do_not_start_detached_database_notifier(self):
        user = User(username="signal-test-user", email="signal@example.com")

        with patch("accounts.signals._notify_admins") as notify:
            notify_admins_on_registration(User, user, created=True)

        notify.assert_not_called()

    @override_settings(TESTING=False)
    def test_registration_intent_is_written_inside_outer_transaction(self):
        with transaction.atomic():
            user = User.objects.create_user(
                username="signal-commit-user",
                email="commit@example.com",
            )
            self.assertTrue(
                IgBotNotification.objects.filter(
                    dedupe_key=f"registration:{user.pk}"
                ).exists()
            )
        self.assertIsNotNone(
            IgBotNotification.objects.get(
                dedupe_key=f"registration:{user.pk}"
            ).next_attempt_at
        )

    @override_settings(TESTING=False)
    def test_rolled_back_registration_never_queues_notification(self):
        username = "signal-rollback-user"
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email="rollback@example.com",
                )
                raise RuntimeError("force outer rollback")

        self.assertFalse(User.objects.filter(username=username).exists())
        self.assertFalse(
            IgBotNotification.objects.filter(
                dedupe_key=f"registration:{user.pk}"
            ).exists()
        )

    @override_settings(TESTING=False)
    @patch.dict(
        "os.environ",
        {
            "TELEGRAM_BOT_TOKEN": "site-token",
            "TELEGRAM_ADMIN_ID": "111;222",
            "TELEGRAM_CHAT_ID": "333",
            "MANAGEMENT_TG_BOT_TOKEN": "management-token",
            "MANAGEMENT_TG_ADMIN_CHAT_ID": "999",
        },
        clear=False,
    )
    @patch("management.services.instagram_bot._http")
    def test_outbox_defers_social_lookup_and_uses_site_telegram_transport(self, http):
        from social_django.models import UserSocialAuth
        from management.services import instagram_bot

        http.side_effect = [
            (200, json.dumps({"ok": True, "result": {"message_id": 71}})),
            (200, json.dumps({"ok": True, "result": {"message_id": 72}})),
        ]
        with self.captureOnCommitCallbacks(execute=True):
            user = User.objects.create_user(
                username="signal-social-user",
                email="social@example.com",
            )
        row = IgBotNotification.objects.get(dedupe_key=f"registration:{user.pk}")
        self.assertEqual(row.status, IgBotNotification.Status.PENDING)
        self.assertEqual(http.call_count, 0)

        # The association happens after User creation and before a worker
        # processes the durable intent.
        UserSocialAuth.objects.create(
            user=user,
            provider="google-oauth2",
            uid="signal-social-uid",
        )

        notify_admins_on_registration(User, user, created=True)
        self.assertEqual(
            IgBotNotification.objects.filter(
                dedupe_key=f"registration:{user.pk}"
            ).count(),
            1,
        )
        row.refresh_from_db()
        self.assertEqual(row.payload["transport"], "site_registration")
        self.assertEqual(row.payload["registration_user_id"], str(user.pk))
        self.assertNotIn(user.username, json.dumps(row.payload))
        self.assertNotIn(user.email, json.dumps(row.payload))
        self.assertEqual(http.call_count, 0)

        self.assertTrue(instagram_bot._deliver_manager_notification_unlocked(row.dedupe_key))
        self.assertEqual(http.call_count, 2)
        self.assertTrue(all("botsite-token/sendMessage" in call.args[0] for call in http.call_args_list))
        deliveries = [json.loads(call.kwargs["data"]) for call in http.call_args_list]
        self.assertEqual([item["chat_id"] for item in deliveries], ["111", "222"])
        self.assertTrue(all("Спосіб: Google" in item["text"] for item in deliveries))

        # A retry after confirmed delivery is idempotent and does not re-enter
        # the transport boundary.
        self.assertTrue(instagram_bot._deliver_manager_notification_unlocked(row.dedupe_key))
        self.assertEqual(http.call_count, 2)


class RegistrationNotificationAutocommitTests(TransactionTestCase):
    @override_settings(TESTING=False)
    @patch("management.services.instagram_bot._deliver_manager_notification")
    def test_autocommit_persists_intent_without_immediate_delivery(self, deliver):
        user = User.objects.create_user(
            username="signal-autocommit-user",
            email="autocommit@example.com",
        )

        row = IgBotNotification.objects.get(dedupe_key=f"registration:{user.pk}")
        self.assertEqual(row.status, IgBotNotification.Status.PENDING)
        self.assertIsNotNone(row.next_attempt_at)
        deliver.assert_not_called()
