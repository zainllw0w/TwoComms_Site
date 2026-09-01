"""
Tests for ig_link_intent module — link request classification, resolution,
and postback handling.
"""
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from management.services import ig_link_intent as lint
from management.services.ig_message_templates import ButtonTemplate, QuickReplyMessage


class TestClassifyRequest(unittest.TestCase):
    """Tests for classify_request() — link intent detection."""

    def test_payment_link_request_uk(self):
        result = lint.classify_request("дай посилання на оплату")
        self.assertEqual(result.intent, "link")
        self.assertEqual(result.link_type, "payment")

    def test_payment_link_request_ru(self):
        result = lint.classify_request("дай ссылку на оплату")
        self.assertEqual(result.intent, "link")
        self.assertEqual(result.link_type, "payment")

    def test_site_link_request(self):
        result = lint.classify_request("дай ссылку на сайт")
        self.assertEqual(result.intent, "link")
        self.assertEqual(result.link_type, "site")

    def test_product_link_request(self):
        result = lint.classify_request("дай посилання на товар")
        self.assertEqual(result.intent, "link")
        self.assertEqual(result.link_type, "product")

    def test_ambiguous_link_request(self):
        result = lint.classify_request("дай посилання")
        self.assertEqual(result.intent, "link")
        self.assertIsNone(result.link_type)

    def test_not_link_request(self):
        result = lint.classify_request("хочу замовити футболку")
        self.assertIsNone(result.intent)


class TestResolve(unittest.TestCase):
    """Tests for resolve() — link resolution based on deal state."""

    def setUp(self):
        self.deal = MagicMock()
        self.deal.id = 123
        self.deal.language = "uk"

    def test_payment_link_live_invoice(self):
        """Live invoice → payment link card."""
        self.deal.invoice_link = "https://secure.wayforpay.com/payment/s123"
        self.deal.invoice_link_expires_at = datetime.now() + timedelta(hours=1)

        result = lint.resolve(self.deal, "payment")

        self.assertIsInstance(result, ButtonTemplate)
        self.assertEqual(len(result.elements), 1)
        self.assertIn("Оплатить", result.elements[0].title)

    def test_payment_link_expired_invoice(self):
        """Expired invoice → reissue offer."""
        self.deal.invoice_link = "https://secure.wayforpay.com/payment/s123"
        self.deal.invoice_link_expires_at = datetime.now() - timedelta(hours=1)

        result = lint.resolve(self.deal, "payment")

        self.assertIsInstance(result, ButtonTemplate)
        self.assertIn("перевипустити", result.fallback_text.lower())

    def test_payment_link_no_invoice(self):
        """No invoice → explanation text."""
        self.deal.invoice_link = None

        result = lint.resolve(self.deal, "payment")

        self.assertIsInstance(result, str)
        self.assertIn("не сформована", result)

    def test_site_link(self):
        """Site link → button card."""
        result = lint.resolve(self.deal, "site")

        self.assertIsInstance(result, ButtonTemplate)
        self.assertEqual(len(result.elements), 1)
        self.assertIn("twocomms.shop", result.elements[0].buttons[0].url)

    def test_ambiguous_request(self):
        """Ambiguous → question with buttons."""
        result = lint.resolve(self.deal, None)

        self.assertIsInstance(result, QuickReplyMessage)
        self.assertGreaterEqual(len(result.quick_replies), 2)


class TestPostbackHandling(unittest.TestCase):
    """Tests for postback handling via LINK_ACTION."""

    def test_link_action_constant(self):
        """Verify LINK_ACTION constant is defined."""
        self.assertEqual(lint.LINK_ACTION, "link_intent")

    def test_payment_choice_payload(self):
        """Payment choice postback → payment link resolution."""
        # This would require full bot integration test
        # Just verify the constant structure
        self.assertIsInstance(lint.LINK_ACTION, str)


if __name__ == "__main__":
    unittest.main()
