"""W2 / IMP-008 — guard'ы в `notify_shipped_deals` (F-CORE-001).

Функция вызывается только из cron `poll_ig_deal_payments`, который сейчас
удалён из crontab. Поэтому дефект латентный: он выстрелит ровно в момент
восстановления cron (IMP-009). Порядок в плане строгий — guard'ы первыми.

Инвариант: любая исходящая коммуникация проходит те же запреты, что и
`ig_order_fulfillment.deliver_event` — `is_enabled`, `hidden_at`,
`is_blocked`, opt-out, `bot_paused`, `manager_takeover`. Клиент, который
попросил не писать, не получает сообщение; вместо отправки создаётся
задача менеджеру.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgClient,
    IgDeal,
    IgFollowUpTask,
    InstagramBotSettings,
)
from orders.models import Order


class ShipmentGuardTests(TestCase):
    def setUp(self):
        self.settings_row = InstagramBotSettings.load()
        self.settings_row.is_enabled = True
        self.settings_row.save(update_fields=["is_enabled"])

        self.client_card = IgClient.objects.create(
            igsid="7000000001",
            username="ship_client",
            last_message_at=timezone.now() - timedelta(hours=1),
        )
        self.order = Order.objects.create(
            status="ship",
            tracking_number="59000123456789",
            payment_status="paid",
        )
        # Оплата должна проходить `verified_payment_q`: legacy-ветка требует
        # статус + payment_status + paid_at + отсутствие проекции.
        self.deal = IgDeal.objects.create(
            client=self.client_card,
            amount="700.00",
            pay_type=IgDeal.PayType.ONLINE_FULL,
            order=self.order,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now() - timedelta(hours=2),
        )

    def _run(self):
        from management.services import bot_orders

        with patch.object(
            bot_orders, "send_text", return_value=(True, "ok", "")
        ) as send, patch.object(bot_orders, "notify_manager"):
            bot_orders.notify_shipped_deals()
        return send

    def _reviews(self):
        return IgFollowUpTask.objects.filter(
            client=self.client_card,
            kind=IgFollowUpTask.Kind.MANAGER_TASK,
        )

    # ------------------------------------------------ регресс: чистый путь
    def test_clean_client_still_receives_tracking_number(self):
        send = self._run()

        self.assertTrue(send.called, "чистый клиент должен получить ТТН")
        self.deal.refresh_from_db()
        self.assertIsNotNone(self.deal.shipped_notified_at)

    # ------------------------------------------------------------ guard'ы
    def test_paused_client_is_not_messaged(self):
        self.client_card.bot_paused = True
        self.client_card.save(update_fields=["bot_paused"])

        send = self._run()

        self.assertFalse(
            send.called, "клиенту на паузе бот не имеет права писать"
        )
        self.deal.refresh_from_db()
        self.assertIsNone(self.deal.shipped_notified_at)
        self.assertTrue(
            self._reviews().exists(),
            "вместо отправки должна появиться задача менеджеру",
        )

    def test_manager_takeover_client_is_not_messaged(self):
        self.client_card.manager_takeover = True
        self.client_card.save(update_fields=["manager_takeover"])

        send = self._run()

        self.assertFalse(send.called)
        self.assertTrue(self._reviews().exists())

    def test_blocked_client_is_not_messaged(self):
        self.client_card.is_blocked = True
        self.client_card.save(update_fields=["is_blocked"])

        send = self._run()

        self.assertFalse(send.called)

    def test_hidden_client_is_not_messaged(self):
        self.client_card.hidden_at = timezone.now()
        self.client_card.save(update_fields=["hidden_at"])

        send = self._run()

        self.assertFalse(send.called)

    def test_opted_out_client_is_not_messaged(self):
        self.client_card.opted_out_at = timezone.now()
        self.client_card.save(update_fields=["opted_out_at"])

        send = self._run()

        self.assertFalse(
            send.called,
            "клиент, попросивший не писать, не должен получать сообщение",
        )
        self.assertTrue(self._reviews().exists())

    def test_opt_in_after_opt_out_restores_delivery(self):
        """Повторное согласие снимает запрет — иначе guard был бы необратим."""
        self.client_card.opted_out_at = timezone.now() - timedelta(days=2)
        self.client_card.opted_in_at = timezone.now() - timedelta(hours=2)
        self.client_card.save(update_fields=["opted_out_at", "opted_in_at"])

        send = self._run()

        self.assertTrue(send.called)

    def test_globally_disabled_bot_does_not_message(self):
        """Кнопка «стоп бота» в админке должна останавливать и этот путь."""
        self.settings_row.is_enabled = False
        self.settings_row.save(update_fields=["is_enabled"])

        send = self._run()

        self.assertFalse(send.called)
        self.deal.refresh_from_db()
        self.assertIsNone(self.deal.shipped_notified_at)

    def test_block_reason_is_recorded_for_the_manager(self):
        """Менеджер должен видеть, почему автоотправка не сработала."""
        self.client_card.bot_paused = True
        self.client_card.save(update_fields=["bot_paused"])

        self._run()

        task = self._reviews().first()
        self.assertIsNotNone(task)
        self.assertIn("bot_paused", task.last_error)
        self.assertIn("59000123456789", task.message_text)

    def test_send_goes_through_the_reply_permission_boundary(self):
        """Отправка обязана идти внутри epoch-модели, а не мимо неё."""
        from management.services import bot_orders

        with patch.object(
            bot_orders, "send_text", return_value=(True, "ok", "")
        ) as send, patch.object(bot_orders, "notify_manager"):
            bot_orders.notify_shipped_deals()

        self.assertTrue(send.called)
        _, kwargs = send.call_args
        self.assertIn(
            "permission_boundary_factory",
            kwargs,
            "send_text должен вызываться с boundary, как в deliver_event",
        )
        self.assertIsNotNone(kwargs["permission_boundary_factory"])
