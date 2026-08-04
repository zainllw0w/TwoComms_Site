from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase

from accounts.signals import notify_admins_on_registration


class RegistrationNotificationSignalTests(SimpleTestCase):
    def test_test_runs_do_not_start_detached_database_notifier(self):
        user = User(username="signal-test-user", email="signal@example.com")

        with patch("accounts.signals.threading.Thread") as thread:
            notify_admins_on_registration(User, user, created=True)

        thread.assert_not_called()
