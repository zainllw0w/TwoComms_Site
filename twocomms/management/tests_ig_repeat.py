"""Task 7 — повторні замовлення та статус замовлення в контексті бота.

- Бот має знати статус останнього замовлення клієнта (щоб відповісти «де моє
  замовлення?» по фактах, не вигадуючи).
- Постійний клієнт: тепле спілкування + підказка, що нове бажання = нова покупка.
"""
from unittest.mock import patch

from django.test import TestCase

from management.models import IgClient, IgDeal
from management.services import bot_memory


def _order(status="prep", ttn=""):
    from orders.models import Order

    return Order.objects.create(
        full_name="Тест", phone="0501112233", city="Київ", np_office="Відділення 1",
        status=status, tracking_number=ttn, total_sum=950,
    )


class OrderStatusNoteTests(TestCase):
    def test_includes_status_and_ttn(self):
        c = IgClient.get_or_create_for_sender("ro1")
        order = _order(status="ship", ttn="59000123")
        IgDeal.objects.create(client=c, status=IgDeal.Status.ORDER_CREATED, order=order)
        note = bot_memory.order_status_note(c)
        self.assertIsNotNone(note)
        self.assertIn("відправлено", note)
        self.assertIn("59000123", note)

    def test_none_without_order(self):
        c = IgClient.get_or_create_for_sender("ro2")
        self.assertIsNone(bot_memory.order_status_note(c))


class ClientContextIncludesOrderTests(TestCase):
    def test_context_note_mentions_order(self):
        c = IgClient.get_or_create_for_sender("ro3")
        order = _order(status="prep")
        IgDeal.objects.create(client=c, status=IgDeal.Status.ORDER_CREATED, order=order)
        note = bot_memory.client_context_note(c)
        self.assertIsNotNone(note)
        self.assertIn("замовлення", note)


class ReturningBuyerNoteTests(TestCase):
    def test_returning_buyer_guidance(self):
        c = IgClient.get_or_create_for_sender("ro4")
        c.purchases_count = 2
        c.save(update_fields=["purchases_count"])
        note = bot_memory.client_context_note(c)
        self.assertIsNotNone(note)
        self.assertIn("постійний клієнт", note)
        self.assertIn("нова покупка", note)
