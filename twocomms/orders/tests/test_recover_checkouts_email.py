import io
from datetime import timedelta
from unittest.mock import ANY, patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from orders.models import CheckoutCapture


@override_settings(EMAIL_DELIVERY_CONFIGURED=True)
class RecoverCheckoutsEmailPolicyTests(TestCase):
    @patch("django.core.mail.send_mail")
    def test_smtp_failure_is_reported_and_capture_remains_retryable(self, send_mail):
        send_mail.side_effect = OSError("SMTP unavailable")
        capture = CheckoutCapture.objects.create(
            session_key="email-recovery-contract",
            full_name="Buyer",
            email="buyer@example.com",
            cart_snapshot={},
            cart_total=950,
            admin_notified_at=timezone.now(),
        )
        CheckoutCapture.objects.filter(pk=capture.pk).update(
            updated_at=timezone.now() - timedelta(hours=1)
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        call_command("recover_checkouts", stdout=stdout, stderr=stderr)

        capture.refresh_from_db()
        self.assertIsNone(capture.recovery_sent_at)
        self.assertIn(f"Email fail for {capture.pk}: SMTP unavailable", stderr.getvalue())
        self.assertIn("email=0", stdout.getvalue())
        send_mail.assert_called_once_with(
            "Твоє замовлення на TwoComms майже готове 🖤",
            ANY,
            ANY,
            ["buyer@example.com"],
            using="transactional",
        )
