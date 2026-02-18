from decimal import Decimal
from unittest.mock import patch
import os

from django.test import SimpleTestCase
from django.utils import timezone

from dtf.models import (
    ContactChannel,
    DtfFulfillmentKind,
    DtfLifecycleStatus,
    DtfOrder,
    DtfPaymentStatus,
    LeadStatus,
    LeadType,
    OrderType,
    OrderStatus,
    DtfLead,
)
from dtf.telegram import _build_dtf_notifier, notify_new_lead, notify_new_order


class DtfTelegramConfigTests(SimpleTestCase):
    def test_build_notifier_uses_dtf_token_and_legacy_chat_ids(self):
        with patch.dict(
            os.environ,
            {
                "DTF_TG_BOT_TOKEN": "dtf-token",
                "TELEGRAM_CHAT_ID": "111;222",
                "DTF_TG_CHAT_ID": "",
                "DTF_TG_ADMIN_ID": "",
                "TELEGRAM_ADMIN_ID": "",
            },
            clear=False,
        ):
            notifier = _build_dtf_notifier()

        self.assertEqual(notifier.bot_token, "dtf-token")
        self.assertEqual(notifier.chat_ids, ["111", "222"])
        self.assertEqual(notifier.admin_ids, [])
        self.assertFalse(notifier.async_enabled)


class DtfTelegramMessageTests(SimpleTestCase):
    @patch("dtf.telegram._send_admin_message", return_value=True)
    def test_notify_new_order_builds_structured_message(self, mocked_send):
        order = DtfOrder(
            order_number="DTF15022026N01",
            order_type=OrderType.HELP,
            status=OrderStatus.CHECK_MOCKUP,
            lifecycle_status=DtfLifecycleStatus.NEEDS_REVIEW,
            name="Test Client",
            phone="+380000000000",
            contact_channel=ContactChannel.TELEGRAM,
            contact_handle="@test_client",
            city="Kyiv",
            np_branch="Branch 1",
            copies=2,
            product_quantity=2,
            meters_total=Decimal("4.5"),
            price_total=Decimal("1200"),
            payment_status=DtfPaymentStatus.AWAITING_PAYMENT,
            payment_amount=Decimal("1200"),
            payment_reference="INV-100",
            payment_link="https://example.com/pay/INV-100",
            fulfillment_kind=DtfFulfillmentKind.CUSTOM_PRODUCT,
            tracking_number="NP000123",
            comment="Need urgent production",
            requires_review=True,
        )
        order.pk = 91
        order.created_at = timezone.now()
        order.updated_at = timezone.now()
        order.payment_updated_at = timezone.now()

        notify_new_order(order)

        mocked_send.assert_called_once()
        message = mocked_send.call_args.args[0]
        self.assertIn("<b>DTF: нове замовлення</b>", message)
        self.assertIn("<b>Замовлення</b>", message)
        self.assertIn("<b>Клієнт</b>", message)
        self.assertIn("<b>Доставка</b>", message)
        self.assertIn("<b>Оплата</b>", message)
        self.assertIn("Адмінка замовлення", message)
        self.assertIn("Сторінка статусу", message)
        self.assertIn("<code>NP000123</code>", message)

    @patch("dtf.telegram._send_admin_message", return_value=True)
    def test_notify_new_lead_builds_structured_message(self, mocked_send):
        lead = DtfLead(
            lead_number="DTF15022026L01",
            lead_type=LeadType.CONSULTATION,
            status=LeadStatus.NEW,
            name="Lead Client",
            phone="+380000000001",
            contact_channel=ContactChannel.TELEGRAM,
            contact_handle="@lead_client",
            city="Lviv",
            np_branch="Branch 2",
            task_description="Need sample batch details",
            deadline_note="2 days",
            folder_link="https://example.com/folder",
            source="landing_form",
        )
        lead.pk = 71
        lead.created_at = timezone.now()

        notify_new_lead(lead)

        mocked_send.assert_called_once()
        message = mocked_send.call_args.args[0]
        self.assertIn("<b>DTF: нова заявка</b>", message)
        self.assertIn("<b>Заявка</b>", message)
        self.assertIn("<b>Контактні дані</b>", message)
        self.assertIn("Адмінка заявки", message)
        self.assertIn("Папка з файлами", message)
