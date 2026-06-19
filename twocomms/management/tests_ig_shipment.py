"""Task 6 — повідомлення клієнта про відправку (ТТН) у IG Direct.

Відправлення йде через 1-3 дні — поза 24-год вікном RESPONSE, тож шлемо з тегом
HUMAN_AGENT (вікно 7 днів). Ідемпотентно: один раз на угоду.
"""
import json
from unittest.mock import patch

from django.test import TestCase

from management.models import IgClient, IgDeal
from management.services import bot_orders
from management.services import instagram_bot as bot


def _order(status="ship", ttn="59000111222"):
    from orders.models import Order

    return Order.objects.create(
        full_name="Тест", phone="0501112233", city="Київ", np_office="Відділення 1",
        status=status, tracking_number=ttn, total_sum=950,
    )


class SendTextTaggedTests(TestCase):
    @patch("management.services.instagram_bot._http")
    @patch("management.services.instagram_bot.get_page_token")
    def test_uses_message_tag_human_agent(self, mock_pt, mock_http):
        from management.models import InstagramBotSettings

        mock_pt.return_value = "PT"
        mock_http.return_value = (200, '{"message_id":"m"}')
        ok, kind, hint = bot.send_text_tagged(InstagramBotSettings.load(), "u1", "Відправлено")
        self.assertTrue(ok)
        body = mock_http.call_args.kwargs.get("data")
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["messaging_type"], "MESSAGE_TAG")
        self.assertEqual(payload["tag"], "HUMAN_AGENT")
        self.assertEqual(payload["recipient"]["id"], "u1")

    @patch("management.services.instagram_bot.get_page_token")
    def test_no_token_permanent(self, mock_pt):
        from management.models import InstagramBotSettings

        mock_pt.return_value = ""
        ok, kind, hint = bot.send_text_tagged(InstagramBotSettings.load(), "u1", "Х")
        self.assertFalse(ok)
        self.assertEqual(kind, "permanent")


class NotifyShippedDealsTests(TestCase):
    @patch("management.services.bot_orders.send_text_tagged")
    def test_notifies_ig_linked_shipped_order_once(self, mock_send):
        mock_send.return_value = (True, "", "")
        c = IgClient.get_or_create_for_sender("sh1")
        order = _order(ttn="59000111222")
        IgDeal.objects.create(client=c, status=IgDeal.Status.ORDER_CREATED, order=order)
        n = bot_orders.notify_shipped_deals()
        self.assertEqual(n, 1)
        mock_send.assert_called_once()
        sent_text = mock_send.call_args.args[2]
        self.assertIn("59000111222", sent_text)
        # ідемпотентність — другий прогін не дублює
        n2 = bot_orders.notify_shipped_deals()
        self.assertEqual(n2, 0)

    @patch("management.services.bot_orders.send_text_tagged")
    def test_skips_when_not_shipped_or_no_ttn(self, mock_send):
        c = IgClient.get_or_create_for_sender("sh2")
        order = _order(status="new", ttn="")
        IgDeal.objects.create(client=c, status=IgDeal.Status.ORDER_CREATED, order=order)
        self.assertEqual(bot_orders.notify_shipped_deals(), 0)
        mock_send.assert_not_called()

    @patch("management.services.bot_orders.send_text_tagged")
    def test_transient_failure_retries_next_run(self, mock_send):
        mock_send.return_value = (False, "transient", "timeout")
        c = IgClient.get_or_create_for_sender("sh3")
        order = _order(ttn="59000999888")
        deal = IgDeal.objects.create(client=c, status=IgDeal.Status.ORDER_CREATED, order=order)
        bot_orders.notify_shipped_deals()
        deal.refresh_from_db()
        self.assertIsNone(deal.shipped_notified_at)  # не помічено → повторимо
