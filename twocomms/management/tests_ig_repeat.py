"""Task 7 — повторні замовлення та статус замовлення в контексті бота.

- Бот має знати статус останнього замовлення клієнта (щоб відповісти «де моє
  замовлення?» по фактах, не вигадуючи).
- Постійний клієнт: тепле спілкування + підказка, що нове бажання = нова покупка.
"""
from unittest.mock import patch

from django.test import TestCase

from management.models import IgBotNotification, IgClient, IgDeal
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

    def test_attribution_only_exact_order_and_multi_order_ambiguity(self):
        from management.services.ig_order_links import create_order_attribution

        c = IgClient.get_or_create_for_sender("ro-attribution-only")
        first = _order(status="prep", ttn="59000124")
        second = _order(status="ship", ttn="59000125")
        create_order_attribution(
            first,
            client=c,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        create_order_attribution(
            second,
            client=c,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )

        ambiguous = bot_memory.order_status_note(c)
        exact = bot_memory.order_status_note(c, second.order_number)

        self.assertIn("кілька замовлень", ambiguous)
        self.assertIn("попроси точний номер", ambiguous)
        self.assertIn("відправлено", exact)
        self.assertIn("59000125", exact)

    @patch("management.services.instagram_bot._deliver_manager_notification")
    def test_ambiguity_creates_one_safe_manager_task_and_exact_reference_resolves_it(
        self, mock_deliver
    ):
        mock_deliver.return_value = False
        from management.models import IgFollowUpTask
        from management.services.ig_order_links import create_order_attribution

        c = IgClient.get_or_create_for_sender("ro-ambiguity-task")
        first = _order(status="prep", ttn="59000131")
        second = _order(status="ship", ttn="59000132")
        for order in (first, second):
            create_order_attribution(
                order,
                client=c,
                creation_mode="linked_existing",
                payment_source="manager_verified",
            )

        bot_memory.order_status_note(c)
        bot_memory.order_status_note(c)

        tasks = IgFollowUpTask.objects.filter(
            client=c,
            kind=IgFollowUpTask.Kind.MANAGER_TASK,
            reason__startswith="ambiguous_order_status",
        )
        self.assertEqual(tasks.count(), 1)
        self.assertEqual(tasks.get().status, IgFollowUpTask.Status.SKIPPED)
        self.assertEqual(tasks.get().skip_reason, "human_agent_required")
        notifications = IgBotNotification.objects.filter(
            client=c,
            event_type="ambiguous_order_status",
        )
        self.assertEqual(notifications.count(), 1)
        self.assertIn("кілька замовлень", notifications.get().payload["text"])

        exact = bot_memory.order_status_note(c, second.order_number)
        self.assertIn("відправлено", exact)
        self.assertEqual(
            tasks.get().status,
            IgFollowUpTask.Status.CANCELLED,
        )


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
