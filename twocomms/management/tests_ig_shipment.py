"""Task 6 — policy-safe shipment notifications in Instagram Direct."""
import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgClient,
    IgDeal,
    IgFollowUpTask,
    IgOrderAttribution,
    IgPaymentProjection,
)
from management.services import bot_orders
from management.services import instagram_bot as bot


def _order(status="ship", ttn="59000111222"):
    from orders.models import Order

    return Order.objects.create(
        full_name="Тест", phone="0501112233", city="Київ", np_office="Відділення 1",
        status=status, tracking_number=ttn, total_sum=950,
    )


def _verified_deal(client, order):
    deal = IgDeal.objects.create(
        client=client,
        status=IgDeal.Status.ORDER_CREATED,
        order=order,
        payment_truth=IgDeal.PaymentTruth.CONFIRMED,
        payment_status="paid",
        paid_at=timezone.now(),
    )
    IgPaymentProjection.objects.create(
        deal=deal,
        client=client,
        truth=IgDeal.PaymentTruth.CONFIRMED,
        gross_amount=order.total_sum,
        paid_at=deal.paid_at,
    )
    return deal


def _legacy_attribution_episode(client, order):
    from management.services.ig_commercial_episodes import (
        ensure_episode_for_attribution,
    )

    attribution = IgOrderAttribution.objects.create(
        order=order,
        client=client,
        creation_mode="linked_existing",
        payment_source="manager_verified",
    )
    ensure_episode_for_attribution(attribution)
    return attribution


class SendTextTaggedTests(TestCase):
    @patch("management.services.instagram_bot._http")
    @patch("management.services.instagram_bot.get_page_token")
    def test_uses_message_tag_human_agent(self, mock_pt, mock_http):
        from management.models import InstagramBotSettings

        mock_pt.return_value = "PT"
        mock_http.return_value = (200, '{"message_id":"m"}')
        ok, kind, hint = bot.send_text_tagged(
            InstagramBotSettings.load(),
            "u1",
            "Відправлено",
            human_authored=True,
        )
        self.assertTrue(ok)
        body = mock_http.call_args.kwargs.get("data")
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["messaging_type"], "MESSAGE_TAG")
        self.assertEqual(payload["tag"], "HUMAN_AGENT")
        self.assertEqual(payload["recipient"]["id"], "u1")

    @patch("management.services.instagram_bot._http")
    @patch("management.services.instagram_bot.get_page_token")
    def test_rejects_automated_human_agent_tag_before_provider_call(self, mock_pt, mock_http):
        from management.models import InstagramBotSettings

        ok, kind, hint = bot.send_text_tagged(
            InstagramBotSettings.load(),
            "u1",
            "Автоматичне нагадування",
        )

        self.assertFalse(ok)
        self.assertEqual(kind, "policy")
        self.assertIn("human", hint.lower())
        mock_pt.assert_not_called()
        mock_http.assert_not_called()

    @patch("management.services.instagram_bot.get_page_token")
    def test_no_token_permanent(self, mock_pt):
        from management.models import InstagramBotSettings

        mock_pt.return_value = ""
        ok, kind, hint = bot.send_text_tagged(
            InstagramBotSettings.load(),
            "u1",
            "Х",
            human_authored=True,
        )
        self.assertFalse(ok)
        self.assertEqual(kind, "permanent")

    @patch("management.services.instagram_bot._http")
    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    def test_explicit_rate_limit_before_tagged_delivery_is_retryable(
        self, _mock_pt, mock_http
    ):
        from management.models import InstagramBotSettings

        mock_http.return_value = (
            429,
            json.dumps({"error": {"code": 4, "message": "Request limit"}}),
        )

        ok, kind, _hint = bot.send_text_tagged(
            InstagramBotSettings.load(),
            "u1",
            "Підтримка",
            human_authored=True,
        )

        self.assertFalse(ok)
        self.assertEqual(kind, "retryable")

    @patch("management.services.instagram_bot._http")
    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    def test_rate_limit_after_partial_tagged_delivery_is_not_replayed(
        self, _mock_pt, mock_http
    ):
        from management.models import InstagramBotSettings

        reply = "Повідомлення підтримки. " * 500
        self.assertGreater(len(bot._split_for_send(reply)), 1)
        mock_http.side_effect = [
            (200, '{"message_id":"m1"}'),
            (
                429,
                json.dumps({"error": {"code": 4, "message": "Request limit"}}),
            ),
        ]

        ok, kind, hint = bot.send_text_tagged(
            InstagramBotSettings.load(),
            "u1",
            reply,
            human_authored=True,
        )

        self.assertFalse(ok)
        self.assertEqual(kind, "unknown")
        self.assertIn("часткова доставка", hint)
        self.assertEqual(mock_http.call_count, 2)


class NotifyShippedDealsTests(TestCase):
    def setUp(self):
        """Бот включён — это предусловие любой автоотправки.

        До F-CORE-001 `notify_shipped_deals` не читала `is_enabled`, поэтому
        тесты и не выставляли его (по умолчанию `False`). Теперь путь
        соблюдает глобальный стоп, как `ig_order_fulfillment.deliver_event`,
        и предусловие надо выражать явно. Тестам «не отправлять» это тоже
        на пользу: они теперь доказывают, что блокировка пришла именно от
        проверяемого условия, а не от выключенного бота.
        """
        from management.models import InstagramBotSettings

        settings_row = InstagramBotSettings.load()
        settings_row.is_enabled = True
        settings_row.save(update_fields=["is_enabled"])

    @patch("management.services.bot_orders.notify_manager")
    @patch("management.services.bot_orders.send_text", create=True)
    def test_active_assignment_is_exclusively_owned_by_fulfillment_queue(
        self, mock_send, mock_notify
    ):
        from management.services.ig_order_assignments import link_order_to_client

        c = IgClient.get_or_create_for_sender("sh-assignment-owner")
        c.last_message_at = timezone.now()
        c.save(update_fields=["last_message_at", "updated_at"])
        order = _order(ttn="59000111999")
        deal = _verified_deal(c, order)
        link_order_to_client(order, client=c)

        self.assertEqual(bot_orders.notify_shipped_deals(), 0)

        deal.refresh_from_db()
        self.assertIsNone(deal.shipped_notified_at)
        mock_send.assert_not_called()
        mock_notify.assert_not_called()

    @patch("management.services.bot_orders.notify_manager")
    @patch("management.services.bot_orders.send_text", create=True)
    def test_active_assignment_excludes_attribution_episode_from_legacy_worker(
        self, mock_send, mock_notify
    ):
        from management.services.ig_order_links import create_order_attribution

        c = IgClient.get_or_create_for_sender("sh-assignment-episode-owner")
        c.last_message_at = timezone.now()
        c.save(update_fields=["last_message_at", "updated_at"])
        order = _order(ttn="59000111888")
        attribution = create_order_attribution(
            order,
            client=c,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )

        self.assertEqual(bot_orders.notify_shipped_deals(), 0)

        attribution.commercial_episode.refresh_from_db()
        self.assertIsNone(attribution.commercial_episode.shipment_notified_at)
        mock_send.assert_not_called()
        mock_notify.assert_not_called()

    @patch("management.services.bot_orders.notify_manager")
    @patch("management.services.instagram_bot.send_text_tagged")
    @patch("management.services.bot_orders.send_text", create=True)
    def test_uses_standard_response_inside_window_once(
        self, mock_send, mock_tagged, mock_notify
    ):
        mock_send.return_value = (True, "", "")
        c = IgClient.get_or_create_for_sender("sh1")
        c.last_message_at = timezone.now()
        c.save(update_fields=["last_message_at", "updated_at"])
        order = _order(ttn="59000111222")
        _verified_deal(c, order)
        n = bot_orders.notify_shipped_deals()
        self.assertEqual(n, 1)
        mock_send.assert_called_once()
        sent_text = mock_send.call_args.args[2]
        self.assertIn("59000111222", sent_text)
        mock_tagged.assert_not_called()
        mock_notify.assert_not_called()
        # ідемпотентність — другий прогін не дублює
        n2 = bot_orders.notify_shipped_deals()
        self.assertEqual(n2, 0)

    @patch("management.services.bot_orders.send_text", create=True)
    def test_skips_when_not_shipped_or_no_ttn(self, mock_send):
        c = IgClient.get_or_create_for_sender("sh2")
        order = _order(status="new", ttn="")
        _verified_deal(c, order)
        self.assertEqual(bot_orders.notify_shipped_deals(), 0)
        mock_send.assert_not_called()

    @patch("management.services.bot_orders.notify_manager")
    @patch("management.services.instagram_bot.send_text_tagged")
    @patch("management.services.bot_orders.send_text", create=True)
    def test_outside_window_creates_one_human_task_without_tagged_send(
        self, mock_send, mock_tagged, mock_notify
    ):
        c = IgClient.get_or_create_for_sender("sh3")
        order = _order(ttn="59000999888")
        deal = _verified_deal(c, order)

        self.assertEqual(bot_orders.notify_shipped_deals(), 0)
        self.assertEqual(bot_orders.notify_shipped_deals(), 0)

        deal.refresh_from_db()
        self.assertIsNone(deal.shipped_notified_at)
        mock_send.assert_not_called()
        mock_tagged.assert_not_called()
        task = IgFollowUpTask.objects.get(
            deal=deal,
            kind=IgFollowUpTask.Kind.MANAGER_TASK,
            reason="shipment_human_review",
        )
        self.assertEqual(task.status, IgFollowUpTask.Status.SKIPPED)
        self.assertEqual(task.skip_reason, "human_agent_required")
        self.assertIn("59000999888", task.message_text)
        self.assertEqual(
            IgFollowUpTask.objects.filter(
                deal=deal,
                reason="shipment_human_review",
            ).count(),
            1,
        )
        self.assertEqual(mock_notify.call_count, 2)

    @patch("management.services.bot_orders.notify_manager")
    @patch("management.services.bot_orders.send_text", create=True)
    def test_ambiguous_standard_send_creates_task_and_is_not_retried(
        self, mock_send, mock_notify
    ):
        mock_send.return_value = (False, "unknown", "delivery unknown")
        c = IgClient.get_or_create_for_sender("sh4")
        c.last_message_at = timezone.now()
        c.save(update_fields=["last_message_at", "updated_at"])
        order = _order(ttn="59000444444")
        deal = _verified_deal(c, order)

        self.assertEqual(bot_orders.notify_shipped_deals(), 0)
        self.assertEqual(bot_orders.notify_shipped_deals(), 0)

        self.assertEqual(mock_send.call_count, 1)
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                deal=deal,
                reason="shipment_delivery_review",
            ).exists()
        )
        self.assertEqual(mock_notify.call_count, 2)

    @patch("management.services.bot_orders.notify_manager")
    @patch("management.services.bot_orders.send_text", create=True)
    def test_legacy_attribution_episode_sends_once_and_marks_exact_episode(
        self, mock_send, mock_notify
    ):
        mock_send.return_value = (True, "", "")
        c = IgClient.get_or_create_for_sender("sh-attribution-only")
        c.last_message_at = timezone.now()
        c.save(update_fields=["last_message_at", "updated_at"])
        order = _order(ttn="59000777777")
        attribution = _legacy_attribution_episode(c, order)
        episode = attribution.commercial_episode

        self.assertEqual(bot_orders.notify_shipped_deals(), 1)
        self.assertEqual(bot_orders.notify_shipped_deals(), 0)

        episode.refresh_from_db()
        self.assertIsNotNone(episode.shipment_notified_at)
        self.assertEqual(mock_send.call_count, 1)
        self.assertIn("59000777777", mock_send.call_args.args[2])
        mock_notify.assert_not_called()

    @patch("management.services.bot_orders.notify_manager")
    @patch("management.services.bot_orders.send_text", create=True)
    def test_legacy_attribution_episode_outside_window_creates_manager_task(
        self, mock_send, mock_notify
    ):
        c = IgClient.get_or_create_for_sender("sh-attribution-review")
        order = _order(ttn="59000777778")
        attribution = _legacy_attribution_episode(c, order)

        self.assertEqual(bot_orders.notify_shipped_deals(), 0)
        mock_send.assert_not_called()
        task = IgFollowUpTask.objects.get(
            client=c,
            reason=f"shipment_human_review:episode:{attribution.commercial_episode.pk}",
        )
        self.assertEqual(task.status, IgFollowUpTask.Status.SKIPPED)
        self.assertEqual(task.skip_reason, "human_agent_required")
        mock_notify.assert_called_once()

    @patch("management.services.bot_orders.notify_manager")
    @patch("management.services.bot_orders.send_text", create=True)
    def test_blocked_deal_does_not_starve_eligible_attribution_episode_at_limit(
        self, mock_send, mock_notify
    ):
        blocked_client = IgClient.get_or_create_for_sender("sh-blocked-deal")
        blocked_order = _order(ttn="59000888881")
        _verified_deal(blocked_client, blocked_order)

        eligible_client = IgClient.get_or_create_for_sender("sh-eligible-attribution")
        eligible_client.last_message_at = timezone.now()
        eligible_client.save(update_fields=["last_message_at", "updated_at"])
        eligible_order = _order(ttn="59000888882")
        attribution = _legacy_attribution_episode(eligible_client, eligible_order)
        episode = attribution.commercial_episode
        mock_send.return_value = (True, "", "")

        self.assertEqual(bot_orders.notify_shipped_deals(limit=1), 1)

        episode.refresh_from_db()
        self.assertIsNotNone(episode.shipment_notified_at)
        self.assertEqual(mock_send.call_count, 1)
        self.assertIn("59000888882", mock_send.call_args.args[2])
        self.assertTrue(mock_notify.called)
