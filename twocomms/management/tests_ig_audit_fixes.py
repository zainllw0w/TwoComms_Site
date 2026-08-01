"""Аудит-фікси IG-бота (Task 2): echo-гонка, неправильний товар у paylink,
дубль замовлення, safety-net створення замовлення.
"""
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgClient,
    IgDeal,
    IgDealItem,
    IgFollowUpTask,
    InstagramBotSettings,
)
from management.services import bot_orders
from management.services import instagram_bot as bot
from storefront.models import UserAction


class EchoChunkAndScopeTests(TestCase):
    """Bug A: echo приходить по чанках і має бути привʼязаний до отримувача."""

    def setUp(self):
        cache.clear()

    def test_marked_chunk_not_treated_as_manager(self):
        IgClient.get_or_create_for_sender("rcpt1")
        bot._mark_bot_sent("rcpt1", "Перша частина відповіді")
        bot._handle_echo("rcpt1", "Перша частина відповіді")
        c = IgClient.objects.get(igsid="rcpt1")
        self.assertFalse(c.bot_paused)
        self.assertFalse(c.manager_takeover)

    def test_unmarked_text_triggers_takeover(self):
        bot._handle_echo("rcpt2", "Вітаю, це Олег, менеджер")
        c = IgClient.objects.get(igsid="rcpt2")
        self.assertTrue(c.bot_paused)
        self.assertTrue(c.manager_takeover)

    def test_recipient_scoped_no_cross_client_false_negative(self):
        # бот написав "Привіт" клієнту A; менеджер пише те саме "Привіт" клієнту B
        bot._mark_bot_sent("A", "Привіт")
        bot._handle_echo("B", "Привіт")  # для B це менеджер, не власне відлуння
        self.assertTrue(IgClient.objects.get(igsid="B").bot_paused)

    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._http", return_value=(200, "{}"))
    def test_send_text_marks_each_chunk(self, mock_http, mock_pt):
        IgClient.get_or_create_for_sender("rcptX")
        s = InstagramBotSettings.load()
        long_text = ("Абзац один. " * 60) + "\n" + ("Абзац два. " * 60)
        parts = bot._split_for_send(long_text)
        self.assertGreater(len(parts), 1)  # реально кілька чанків
        ok, kind, hint = bot.send_text(s, "rcptX", long_text)
        self.assertTrue(ok)
        # echo КОЖНОГО чанка не має спричинити перехоплення
        for part in parts:
            bot._handle_echo("rcptX", part)
        self.assertFalse(IgClient.objects.get(igsid="rcptX").bot_paused)


class SendApiErrorClassificationTests(TestCase):
    def test_advanced_access_subcode_is_explicit(self):
        body = json.dumps({
            "error": {
                "code": 200,
                "error_subcode": bot.ADVANCED_ACCESS_SUBCODE,
                "message": "App does not have advanced access for Instagram messages.",
            }
        })

        kind, hint = bot._classify_send_error(403, body)

        self.assertEqual(kind, "permanent")
        self.assertIn("нерольового", hint)
        self.assertIn("Advanced Access", hint)
        self.assertIn("instagram_manage_messages", hint)

    def test_messaging_window_subcode_is_explicit(self):
        body = json.dumps({
            "error": {
                "code": 10,
                "error_subcode": bot.MESSAGING_WINDOW_CLOSED_SUBCODE,
                "message": "Messaging window closed.",
            }
        })

        kind, hint = bot._classify_send_error(400, body)

        self.assertEqual(kind, "permanent")
        self.assertIn("24-годинне", hint)

    def test_2534122_is_link_restriction_not_advanced_access(self):
        body = json.dumps({
            "error": {
                "code": 508,
                "error_subcode": 2534122,
                "message": "The message could not be sent at this time.",
            }
        })

        kind, hint = bot._classify_send_error(400, body)

        self.assertEqual(kind, "link_restricted")
        self.assertIn("тимчас", hint.lower())
        self.assertNotIn("Advanced Access", hint)
        self.assertNotIn("нерольов", hint)

    def test_2534122_special_classification_requires_http_400(self):
        body = json.dumps({
            "error": {
                "code": 508,
                "error_subcode": 2534122,
                "message": "Invalid message id",
            }
        })

        kind, hint = bot._classify_send_error(403, body)

        self.assertEqual(kind, "permanent")
        self.assertNotIn("тимчасово обмежив надсилання посилань", hint)

    def test_only_advanced_access_failure_claims_non_role_permission_problem(self):
        generic = bot._permanent_send_alert_text(
            "відмова Graph API (code 100)",
            graph_subcode=0,
        )
        advanced = bot._permanent_send_alert_text(
            "Meta відхилила нерольового отримувача",
            graph_subcode=bot.ADVANCED_ACCESS_SUBCODE,
        )

        self.assertNotIn("нерольов", generic)
        self.assertNotIn("Advanced Access", generic)
        self.assertIn("Advanced Access", advanced)


class SendApiBoundedRetryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.ai_enabled = False
        self.settings.trigger_text = "hello"
        self.settings.reply_text = "Ось рожеве худі: https://twocomms.shop/product/pink-hoodie/"
        self.settings.save()
        self.client = IgClient.get_or_create_for_sender("retry-2534122")
        self.error_body = json.dumps({
            "error": {
                "code": 508,
                "error_subcode": 2534122,
                "message": "Invalid message id",
            }
        })

    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._provider_http")
    def test_successful_meta_json_exposes_provider_message_id(
        self, provider_http, _token, _account
    ):
        provider_http.return_value = (200, json.dumps({"message_id": "mid.real.1"}))
        provider_ids = []

        ok, kind, _hint = bot.send_text(
            self.settings,
            self.client.igsid,
            "Delivery update",
            provider_message_callback=provider_ids.append,
        )

        self.assertTrue(ok)
        self.assertEqual(kind, "")
        self.assertEqual(provider_ids, ["mid.real.1"])

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._provider_http")
    def test_definite_2534122_link_rejection_retries_once_without_url(
        self, provider_http, _token, _account, notify_manager
    ):
        provider_http.side_effect = [(400, self.error_body), (200, "{}")]

        ok, kind, delivered_text = bot.send_text(
            self.settings,
            self.client.igsid,
            self.settings.reply_text,
            allow_url_fallback=True,
        )

        self.assertTrue(ok)
        self.assertEqual(kind, "degraded_link_restriction")
        self.assertNotIn("https://", delivered_text)
        self.assertIn("рожеве худі", delivered_text)
        self.assertEqual(provider_http.call_count, 2)
        first_payload = json.loads(provider_http.call_args_list[0].kwargs["data"])
        fallback_payload = json.loads(provider_http.call_args_list[1].kwargs["data"])
        self.assertIn("https://", first_payload["message"]["text"])
        self.assertNotIn("https://", fallback_payload["message"]["text"])
        self.assertNotIn("Advanced Access", str(notify_manager.call_args))
        self.settings.refresh_from_db()
        self.assertGreater(self.settings.link_send_blocked_until, timezone.now())

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._provider_http")
    def test_2534122_plain_text_fallback_is_bounded_to_one_attempt(
        self, provider_http, _token, _account, notify_manager
    ):
        provider_http.return_value = (400, self.error_body)

        ok, kind, hint = bot.send_text(
            self.settings,
            self.client.igsid,
            self.settings.reply_text,
            allow_url_fallback=True,
        )

        self.assertFalse(ok)
        self.assertEqual(kind, "permanent")
        self.assertEqual(provider_http.call_count, 2)
        self.assertNotIn("Advanced Access", hint)
        self.assertNotIn("нерольов", hint)
        self.assertNotIn("Advanced Access", str(notify_manager.call_args))

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._provider_http", return_value=(200, "{}"))
    def test_active_link_circuit_breaker_sends_plain_text_without_link_probe(
        self, provider_http, _token, _account, _notify_manager
    ):
        self.settings.link_send_blocked_until = timezone.now() + timedelta(hours=12)
        self.settings.save(update_fields=["link_send_blocked_until"])

        ok, kind, delivered_text = bot.send_text(
            self.settings,
            self.client.igsid,
            self.settings.reply_text,
            allow_url_fallback=True,
        )

        self.assertTrue(ok)
        self.assertEqual(kind, "degraded_link_restriction")
        self.assertNotIn("https://", delivered_text)
        self.assertEqual(provider_http.call_count, 1)
        payload = json.loads(provider_http.call_args.kwargs["data"])
        self.assertNotIn("https://", payload["message"]["text"])

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._provider_http", return_value=(200, "{}"))
    def test_active_catalog_circuit_never_preempts_fail_closed_payment_probe(
        self, provider_http, _token, _account, _notify_manager
    ):
        self.settings.link_send_blocked_until = timezone.now() + timedelta(hours=12)
        self.settings.save(update_fields=["link_send_blocked_until"])
        payment_reply = "Оплата: https://pay.example/invoice/critical"

        ok, kind, _hint = bot.send_text(
            self.settings,
            self.client.igsid,
            payment_reply,
            allow_url_fallback=False,
        )

        self.assertTrue(ok)
        self.assertEqual(kind, "")
        self.assertEqual(provider_http.call_count, 1)
        payload = json.loads(provider_http.call_args.kwargs["data"])
        self.assertIn("https://pay.example/invoice/critical", payload["message"]["text"])

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._provider_http")
    def test_plain_text_2534122_does_not_open_link_circuit_or_retry(
        self, provider_http, _token, _account, _notify_manager
    ):
        provider_http.return_value = (400, self.error_body)

        ok, kind, hint = bot.send_text(
            self.settings,
            self.client.igsid,
            "Звичайна відповідь без посилання",
            allow_url_fallback=True,
        )

        self.assertFalse(ok)
        self.assertEqual(kind, "permanent")
        self.assertEqual(provider_http.call_count, 1)
        self.settings.refresh_from_db()
        self.assertIsNone(self.settings.link_send_blocked_until)
        self.assertNotIn("Advanced Access", hint)

    def test_real_payment_url_never_allows_linkless_fallback(self):
        reply = "Дякую! 💳 Посилання на оплату: https://pay.mbnk.biz/example"

        self.assertFalse(bot._allows_linkless_fallback(reply, {}))

    def test_persisted_generic_invoice_url_never_allows_linkless_fallback(self):
        deal = IgDeal.objects.create(
            client=self.client,
            invoice_id="generic-invoice",
            invoice_url="https://pay.example/invoice/generic",
        )
        reply = f"Дякую! Оплатити можна тут: {deal.invoice_url}"

        self.assertFalse(bot._allows_linkless_fallback(reply, {}, self.client))

    @patch("management.services.instagram_bot.notify_manager")
    def test_blocked_invoices_create_distinct_deal_bound_manager_tasks(
        self, notify_manager
    ):
        first = IgDeal.objects.create(
            client=self.client,
            invoice_id="invoice-one",
            invoice_url="https://pay.example/invoice/one",
        )
        second = IgDeal.objects.create(
            client=self.client,
            invoice_id="invoice-two",
            invoice_url="https://pay.example/invoice/two",
        )

        bot._queue_payment_link_delivery_review(
            self.client,
            f"Оплата: {first.invoice_url}",
            "Instagram тимчасово обмежив надсилання посилань (code 508, subcode 2534122)",
        )
        bot._queue_payment_link_delivery_review(
            self.client,
            f"Оплата: {second.invoice_url}",
            "Instagram тимчасово обмежив надсилання посилань (code 508, subcode 2534122)",
        )

        tasks = list(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason="payment_link_delivery_review",
            ).order_by("deal_id")
        )
        self.assertEqual(len(tasks), 2)
        self.assertEqual({task.deal_id for task in tasks}, {first.pk, second.pk})
        self.assertEqual(notify_manager.call_count, 2)

    @patch("management.services.instagram_bot.notify_manager")
    def test_replaced_invoice_on_same_deal_creates_distinct_manager_tasks(
        self, notify_manager
    ):
        deal = IgDeal.objects.create(
            client=self.client,
            invoice_id="invoice-one",
            invoice_url="https://pay.example/invoice/one",
        )
        first_reply = f"Оплата: {deal.invoice_url}"
        hint = (
            "Instagram тимчасово обмежив надсилання посилань "
            "(code 508, subcode 2534122)"
        )

        bot._queue_payment_link_delivery_review(self.client, first_reply, hint)

        deal.invoice_id = "invoice-two"
        deal.invoice_url = "https://pay.example/invoice/two"
        deal.save(update_fields=["invoice_id", "invoice_url", "updated_at"])
        second_reply = f"Оплата: {deal.invoice_url}"
        bot._queue_payment_link_delivery_review(self.client, second_reply, hint)

        tasks = list(
            IgFollowUpTask.objects.filter(
                client=self.client,
                deal=deal,
                reason="payment_link_delivery_review",
            ).order_by("id")
        )
        self.assertEqual(len(tasks), 2)
        self.assertEqual(
            {task.message_text for task in tasks},
            {first_reply, second_reply},
        )
        dedupe_keys = [call.kwargs["dedupe_key"] for call in notify_manager.call_args_list]
        self.assertEqual(len(dedupe_keys), 2)
        self.assertEqual(len(set(dedupe_keys)), 2)

    @patch("management.services.instagram_bot.notify_manager")
    def test_payment_review_preserves_non_link_failure_reason(self, notify_manager):
        deal = IgDeal.objects.create(
            client=self.client,
            invoice_id="advanced-access-invoice",
            invoice_url="https://pay.example/invoice/advanced",
        )
        hint = (
            "Meta відхилила нерольового отримувача: немає Advanced Access на "
            "instagram_business_manage_messages"
        )

        bot._queue_payment_link_delivery_review(
            self.client,
            f"Оплата: {deal.invoice_url}",
            hint,
        )

        task = IgFollowUpTask.objects.get(
            client=self.client,
            deal=deal,
            reason="payment_link_delivery_review",
        )
        self.assertEqual(task.skip_reason, "meta_advanced_access")
        self.assertNotIn("заблокувала доставку платіжного посилання", notify_manager.call_args.args[0])

    @patch("management.services.instagram_bot.notify_manager")
    def test_payment_delivery_alert_contains_preserved_invoice_message(
        self, notify_manager
    ):
        deal = IgDeal.objects.create(
            client=self.client,
            invoice_id="invoice-visible",
            invoice_url="https://pay.example/invoice/visible",
        )
        reply = f"Оплата: {deal.invoice_url}"

        bot._queue_payment_link_delivery_review(
            self.client,
            reply,
            "Instagram тимчасово обмежив надсилання посилань (code 508, subcode 2534122)",
        )

        self.assertIn(reply, notify_manager.call_args.args[0])

    @patch("management.services.instagram_bot.notify_manager")
    def test_payment_delivery_review_cancels_only_failed_deal_payment_reminder(
        self, _notify_manager
    ):
        failed_deal = IgDeal.objects.create(
            client=self.client,
            invoice_id="invoice-failed-delivery",
            invoice_url="https://pay.example/invoice/failed-delivery",
        )
        other_deal = IgDeal.objects.create(
            client=self.client,
            invoice_id="invoice-other",
            invoice_url="https://pay.example/invoice/other",
        )
        failed_reminder = IgFollowUpTask.objects.create(
            client=self.client,
            deal=failed_deal,
            due_at=timezone.now() + timedelta(minutes=45),
            status=IgFollowUpTask.Status.PENDING,
            kind=IgFollowUpTask.Kind.PAYMENT,
            reason="payment_link_unpaid",
        )
        other_reminder = IgFollowUpTask.objects.create(
            client=self.client,
            deal=other_deal,
            due_at=timezone.now() + timedelta(minutes=45),
            status=IgFollowUpTask.Status.PENDING,
            kind=IgFollowUpTask.Kind.PAYMENT,
            reason="payment_link_unpaid",
        )

        bot._queue_payment_link_delivery_review(
            self.client,
            f"Оплата: {failed_deal.invoice_url}",
            "Instagram тимчасово обмежив надсилання посилань (code 508, subcode 2534122)",
            deal=failed_deal,
        )

        failed_reminder.refresh_from_db()
        other_reminder.refresh_from_db()
        self.assertEqual(failed_reminder.status, IgFollowUpTask.Status.CANCELLED)
        self.assertEqual(failed_reminder.skip_reason, "payment_link_not_delivered")
        self.assertEqual(other_reminder.status, IgFollowUpTask.Status.PENDING)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text")
    @patch("management.services.instagram_bot.finalize_paylink")
    def test_blocked_payment_url_creates_client_scoped_manager_task(
        self, finalize_paylink, send_text, _sender_action, _notify_manager
    ):
        payment_reply = "Дякую! 💳 Посилання на оплату: https://pay.mbnk.biz/example"
        self.settings.reply_text = payment_reply
        self.settings.save(update_fields=["reply_text"])
        finalize_paylink.return_value = payment_reply
        send_text.return_value = (
            False,
            "permanent",
            "Instagram тимчасово блокує посилання",
        )
        row = bot.InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=bot.InstagramBotMessage.Role.USER,
            text="hello",
            status=bot.InstagramBotMessage.Status.PENDING,
            source="webhook",
        )

        self.assertEqual(bot.process_pending(self.settings, max_items=1), 0)

        row.refresh_from_db()
        self.assertEqual(row.status, bot.InstagramBotMessage.Status.FAILED)
        self.assertFalse(send_text.call_args.kwargs["allow_url_fallback"])
        task = IgFollowUpTask.objects.get(
            client=self.client,
            kind=IgFollowUpTask.Kind.MANAGER_TASK,
            reason="payment_link_delivery_review",
        )
        self.assertEqual(task.status, IgFollowUpTask.Status.SKIPPED)
        self.assertIn("https://pay.mbnk.biz/example", task.message_text)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text")
    def test_current_generic_failure_does_not_reuse_stale_advanced_access_subcode(
        self, send_text, _sender_action, notify_manager
    ):
        self.client.delivery_graph_subcode = bot.ADVANCED_ACCESS_SUBCODE
        self.client.save(update_fields=["delivery_graph_subcode", "updated_at"])
        send_text.return_value = (False, "permanent", "поточна відмова Graph API")
        bot.InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=bot.InstagramBotMessage.Role.USER,
            text="hello",
            status=bot.InstagramBotMessage.Status.PENDING,
            source="webhook",
        )

        self.assertEqual(bot.process_pending(self.settings, max_items=1), 0)

        alert_text = str(notify_manager.call_args.args[0])
        self.assertNotIn("Advanced Access", alert_text)
        self.assertNotIn("нерольов", alert_text)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text")
    def test_worker_persists_the_plain_text_that_meta_actually_received(
        self, send_text, _sender_action, _notify_manager
    ):
        delivered = "Ось рожеве худі. Можу допомогти з розміром."
        send_text.return_value = (True, "degraded_link_restriction", delivered)
        row = bot.InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=bot.InstagramBotMessage.Role.USER,
            text="hello",
            status=bot.InstagramBotMessage.Status.PENDING,
            source="webhook",
        )

        self.assertEqual(bot.process_pending(self.settings, max_items=1), 1)

        row.refresh_from_db()
        self.assertEqual(row.status, bot.InstagramBotMessage.Status.DONE)
        self.assertTrue(
            bot.InstagramBotMessage.objects.filter(
                client=self.client,
                role=bot.InstagramBotMessage.Role.MODEL,
                text=delivered,
            ).exists()
        )
        self.assertFalse(
            bot.InstagramBotMessage.objects.filter(
                client=self.client,
                role=bot.InstagramBotMessage.Role.MODEL,
                text=self.settings.reply_text,
            ).exists()
        )

    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._http")
    def test_send_text_persists_permanent_error_for_dashboard(self, mock_http, _mock_pt):
        mock_http.return_value = (
            403,
            json.dumps({
                "error": {
                    "code": 200,
                    "error_subcode": bot.ADVANCED_ACCESS_SUBCODE,
                    "message": "App does not have advanced access for Instagram messages.",
                }
            }),
        )
        s = InstagramBotSettings.load()
        s.last_error = ""
        s.save(update_fields=["last_error"])

        ok, kind, hint = bot.send_text(s, "nonrole1", "Привіт")

        self.assertFalse(ok)
        self.assertEqual(kind, "permanent")
        self.assertIn("Advanced Access", hint)
        s.refresh_from_db()
        self.assertIn("Meta Send API", s.last_error)
        self.assertIn("Advanced Access", s.last_error)

    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._http", return_value=(503, "provider overloaded"))
    def test_transient_provider_result_is_unknown_not_retryable(self, _mock_http, _mock_pt):
        ok, kind, hint = bot.send_text(InstagramBotSettings.load(), "uncertain-recipient", "Привіт")

        self.assertFalse(ok)
        self.assertEqual(kind, "unknown")
        self.assertIn("не підтверджено", hint)

    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._http")
    def test_explicit_graph_rate_limit_remains_retryable(self, mock_http, _mock_pt):
        mock_http.return_value = (
            429,
            json.dumps({
                "error": {
                    "code": 4,
                    "message": "Application request limit reached",
                }
            }),
        )

        ok, kind, hint = bot.send_text(
            InstagramBotSettings.load(),
            "rate-limited-recipient",
            "Привіт",
        )

        self.assertFalse(ok)
        self.assertEqual(kind, "retryable")
        self.assertIn("ліміт", hint)
        self.assertEqual(mock_http.call_count, 1)

    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._http")
    def test_rate_limit_after_partial_chunk_delivery_is_not_replayed(
        self, mock_http, _mock_pt
    ):
        reply = "Перша частина. " * 500
        self.assertGreater(len(bot._split_for_send(reply)), 1)
        mock_http.side_effect = [
            (200, "{}"),
            (
                429,
                json.dumps({
                    "error": {
                        "code": 4,
                        "message": "Application request limit reached",
                    }
                }),
            ),
        ]

        ok, kind, hint = bot.send_text(
            InstagramBotSettings.load(),
            "partially-delivered-recipient",
            reply,
        )

        self.assertFalse(ok)
        self.assertEqual(kind, "unknown")
        self.assertIn("часткова доставка", hint)
        self.assertEqual(mock_http.call_count, 2)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text")
    def test_retryable_send_stops_current_drain_cycle(
        self, send_text, _sender_action, _notify_manager
    ):
        self.addCleanup(
            cache.delete,
            bot._send_rate_limit_backoff_key(self.settings),
        )
        send_text.return_value = (False, "retryable", "ліміт частоти")
        row = bot.InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=bot.InstagramBotMessage.Role.USER,
            text="hello",
            status=bot.InstagramBotMessage.Status.PENDING,
            source="webhook",
        )

        self.assertEqual(bot.process_pending(self.settings, max_items=5), 0)
        self.assertEqual(bot.process_pending(self.settings, max_items=5), 0)

        row.refresh_from_db()
        self.assertEqual(send_text.call_count, 1)
        self.assertEqual(row.attempts, 1)
        self.assertEqual(row.status, bot.InstagramBotMessage.Status.PENDING)

    def test_non_send_rate_observation_does_not_disable_send_backoff(self):
        self.addCleanup(
            cache.delete,
            bot._send_rate_limit_backoff_key(self.settings),
        )

        bot._activate_send_rate_limit_backoff(self.settings)
        bot._record_meta_http_observation(
            "conversations",
            429,
            json.dumps({"error": {"code": 4, "message": "Request limit"}}),
        )

        self.assertTrue(bot._send_rate_limit_backoff_active(self.settings))

    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._http")
    def test_permanent_send_block_is_persisted_on_the_affected_client(self, mock_http, _mock_pt):
        client = IgClient.get_or_create_for_sender("delivery-blocked-client")
        mock_http.return_value = (
            403,
            json.dumps({
                "error": {
                    "code": 200,
                    "error_subcode": bot.ADVANCED_ACCESS_SUBCODE,
                    "message": "App does not have advanced access for Instagram messages.",
                }
            }),
        )

        bot.send_text(InstagramBotSettings.load(), client.igsid, "Привіт")

        client.refresh_from_db()
        self.assertEqual(getattr(client, "delivery_status", ""), "advanced_access")
        self.assertIn("Advanced Access", getattr(client, "delivery_error", ""))

    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._http", return_value=(200, "{}"))
    def test_successful_send_clears_client_delivery_block(self, _mock_http, _mock_pt):
        client = IgClient.get_or_create_for_sender("delivery-cleared-client")
        setattr(client, "delivery_status", "advanced_access")
        setattr(client, "delivery_error", "попередня причина")
        client.save()

        bot.send_text(InstagramBotSettings.load(), client.igsid, "Привіт")

        client.refresh_from_db()
        self.assertEqual(getattr(client, "delivery_status", "advanced_access"), "")
        self.assertEqual(getattr(client, "delivery_error", "попередня причина"), "")

    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._http")
    def test_graph_551_requires_message_requests_check_without_claiming_it_is_confirmed(self, mock_http, _mock_pt):
        client = IgClient.get_or_create_for_sender("delivery-request-check-client")
        mock_http.return_value = (
            400,
            json.dumps({"error": {"code": 551, "message": "Recipient unavailable."}}),
        )

        bot.send_text(InstagramBotSettings.load(), client.igsid, "Привіт")

        client.refresh_from_db()
        self.assertEqual(getattr(client, "delivery_status", ""), "message_request_check")

    @patch("management.services.instagram_bot.log")
    @patch("management.services.instagram_bot.get_page_token", return_value="PT")
    @patch("management.services.instagram_bot._http")
    def test_send_error_log_never_contains_raw_graph_response(self, mock_http, _mock_pt, mock_log):
        raw_marker = "raw-meta-response-marker"
        mock_http.return_value = (
            403,
            json.dumps({"error": {"code": 200, "message": raw_marker}}),
        )

        bot.send_text(InstagramBotSettings.load(), "untracked-recipient", "Привіт")

        logged = "\n".join(str(call.args) for call in mock_log.call_args_list)
        self.assertNotIn(raw_marker, logged)


class PaylinkProductTests(TestCase):
    """Bug B: paylink має бути на ПРАВИЛЬНИЙ товар, навіть якщо є стара чернетка."""

    def setUp(self):
        from storefront.models import Category, Product, ProductStatus

        cat = Category.objects.create(name="Одяг", slug="odiah-pl")
        self.p1 = Product.objects.create(title="Стара футболка", slug="old-tee", category=cat, price=600, status=ProductStatus.PUBLISHED)
        self.p2 = Product.objects.create(title="Худі Kharkiv", slug="hk-pl", category=cat, price=950, status=ProductStatus.PUBLISHED)
        self.c = IgClient.get_or_create_for_sender("pl1")
        old = IgDeal.objects.create(client=self.c, pay_type=IgDeal.PayType.ONLINE_FULL)
        IgDealItem.objects.create(deal=old, product=self.p1, title=self.p1.title, qty=1, unit_price=Decimal("600"))
        old.recalc_total()

    @patch("management.services.bot_orders.create_payment_link")
    def test_new_product_not_charged_as_old(self, mock_link):
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/x", "invoice_id": "x"}
        # The assisted checkout contract requires an explicit size before a
        # paylink can be generated; this fixture has no fit-specific guide.
        bot_orders.create_deal_and_link(
            self.c,
            pay_type="full",
            product_id=self.p2.id,
            size="M",
        )
        billed_deal = mock_link.call_args.args[0]
        titles = [it.title for it in billed_deal.items.all()]
        self.assertIn("Худі Kharkiv", titles)
        self.assertNotIn("Стара футболка", titles)
        self.assertEqual(billed_deal.amount, Decimal("950"))


class SafetyNetTests(TestCase):
    """Bug D: створення замовлення без тегу [ORDER]."""

    def _paid_deal(self, igsid, with_np):
        c = IgClient.get_or_create_for_sender(igsid)
        d = IgDeal.objects.create(
            client=c, pay_type=IgDeal.PayType.ONLINE_FULL,
            status=IgDeal.Status.PAID, payment_status="paid",
            paid_at=timezone.now(),
            np_full_name=("Іван" if with_np else ""), np_phone=("0931112233" if with_np else ""),
            np_city=("Київ" if with_np else ""), np_office=("Відд 1" if with_np else ""),
            np_settlement_ref=("settlement-ref" if with_np else ""),
            np_city_ref=("city-ref" if with_np else ""),
            np_warehouse_ref=("warehouse-ref" if with_np else ""),
            delivery_status=(IgDeal.DeliveryStatus.VALIDATED if with_np else IgDeal.DeliveryStatus.UNVERIFIED),
            delivery_source=("nova_poshta_directory" if with_np else ""),
            delivery_verified_at=(timezone.now() if with_np else None),
        )
        IgDealItem.objects.create(deal=d, title="Худі", qty=1, unit_price=Decimal("950"))
        d.recalc_total()
        return c, d

    @patch("management.services.bot_orders.notify_manager")
    def test_fulfill_ready_paid_deals_creates_order(self, _n):
        c, d = self._paid_deal("sn1", with_np=True)
        self.assertEqual(bot_orders.fulfill_ready_paid_deals(), 1)
        d.refresh_from_db()
        self.assertIsNotNone(d.order_id)

    @patch("management.services.bot_orders.notify_manager")
    def test_fulfill_skips_without_np(self, _n):
        c, d = self._paid_deal("sn2", with_np=False)
        self.assertEqual(bot_orders.fulfill_ready_paid_deals(), 0)

    @patch("management.services.bot_orders.notify_manager")
    def test_safety_net_heals_missing_purchase_for_existing_order(self, _n):
        c, deal = self._paid_deal("sn-heal", with_np=True)
        order = bot_orders.create_order_from_deal(deal)
        UserAction.objects.filter(
            action_type='purchase',
            order_id=order.pk,
        ).delete()

        self.assertEqual(bot_orders.fulfill_ready_paid_deals(), 0)

        self.assertTrue(
            UserAction.objects.filter(
                action_type='purchase',
                order_id=order.pk,
            ).exists()
        )

    def test_looks_like_contact_info(self):
        self.assertTrue(bot._looks_like_contact_info("0931112233"))
        self.assertTrue(bot._looks_like_contact_info("Київ, відділення 5, Іван"))
        self.assertFalse(bot._looks_like_contact_info("а скільки коштує?"))
