import logging

from django.test import SimpleTestCase

from twocomms.log_handlers import PIIRedactionFilter


class PIIRedactionFilterTests(SimpleTestCase):
    def test_masks_email_phone_and_long_numbers(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="client john@example.com phone +380991112233 card 4111111111111111",
            args=(),
            exc_info=None,
        )

        PIIRedactionFilter().filter(record)

        self.assertEqual(
            record.getMessage(),
            "client [email] phone [phone] card [number]",
        )

    def test_masks_instagram_webhook_verify_token_in_access_path(self):
        record = logging.LogRecord(
            name="django.server",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='"GET /bot/webhook/?hub.mode=subscribe&hub.verify_token=secret-value&hub.challenge=123 HTTP/1.1" 403 9',
            args=(),
            exc_info=None,
        )

        PIIRedactionFilter().filter(record)

        self.assertNotIn("secret-value", record.getMessage())
        self.assertIn("hub.verify_token=[redacted]", record.getMessage())
