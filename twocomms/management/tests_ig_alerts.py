# -*- coding: utf-8 -*-
"""Політика Telegram-алертів.

Скарга заказника: «сразу спам из 10 штук». По коду це відтворювалось так:
`drain_manager_notifications(limit=10)` крутиться в демоні кожні 1.5 секунди і
всередині не має ні задержки, ні лічильника — до 20 повідомлень за прохід.
Одночасно 12 точок із 31 не передавали `dedupe_key`, тому повтор тієї самої
події не доходив ніколи, а різні клієнти давали пачку.
"""
from datetime import timedelta
from types import SimpleNamespace

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone


class ThrottlePolicyTests(TestCase):
    def test_flow_under_the_limit_is_allowed(self):
        from management.services.ig_alerts import should_send_now

        now = timezone.now()
        stamps = [now - timedelta(seconds=10), now - timedelta(seconds=20)]
        self.assertTrue(should_send_now(stamps, now=now, max_per_minute=6))

    def test_flow_at_the_limit_is_held(self):
        from management.services.ig_alerts import should_send_now

        now = timezone.now()
        stamps = [now - timedelta(seconds=index) for index in range(6)]
        self.assertFalse(should_send_now(stamps, now=now, max_per_minute=6))

    def test_old_marks_do_not_count(self):
        """Ліміт саме на хвилину: те, що було дві хвилини тому, не блокує."""
        from management.services.ig_alerts import should_send_now

        now = timezone.now()
        stamps = [now - timedelta(minutes=2, seconds=index) for index in range(20)]
        self.assertTrue(should_send_now(stamps, now=now, max_per_minute=6))

    def test_gate_holds_after_the_limit_and_reports_retry(self):
        from management.services.ig_alerts import throttle_gate

        cache.clear()
        for _ in range(6):
            allowed, _ = throttle_gate("test-flow", max_per_minute=6)
            self.assertTrue(allowed)
        allowed, retry_after = throttle_gate("test-flow", max_per_minute=6)
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)

    def test_broken_cache_does_not_block_alerts(self):
        """Втратити алерт про інцидент гірше, ніж надіслати один зайвий."""
        from unittest.mock import patch

        from management.services.ig_alerts import throttle_gate

        with patch("management.services.ig_alerts.cache.get", side_effect=RuntimeError("down")):
            allowed, retry_after = throttle_gate("test-flow-broken")
        self.assertTrue(allowed)
        self.assertEqual(retry_after, 0)


class DedupeKeyTests(TestCase):
    def test_key_includes_entity_so_two_clients_do_not_collide(self):
        from management.services.ig_alerts import alert_dedupe_key

        first = alert_dedupe_key("escalation", client_id=1)
        second = alert_dedupe_key("escalation", client_id=2)
        self.assertNotEqual(first, second)

    def test_same_event_same_window_is_one_key(self):
        from management.services.ig_alerts import alert_dedupe_key

        first = alert_dedupe_key("escalation", client_id=1, window_minutes=60)
        second = alert_dedupe_key("escalation", client_id=1, window_minutes=60)
        self.assertEqual(first, second)

    def test_next_window_produces_a_new_key(self):
        """Головне, чого не було: повтор події через годину має дійти."""
        from unittest.mock import patch

        from management.services.ig_alerts import alert_dedupe_key

        now = timezone.now()
        with patch("django.utils.timezone.now", return_value=now):
            first = alert_dedupe_key("escalation", client_id=1, window_minutes=60)
        with patch("django.utils.timezone.now", return_value=now + timedelta(hours=2)):
            later = alert_dedupe_key("escalation", client_id=1, window_minutes=60)
        self.assertNotEqual(first, later)

    def test_without_entity_falls_back_to_text_hash(self):
        from management.services.ig_alerts import alert_dedupe_key

        first = alert_dedupe_key("generic", text="щось зламалось")
        same = alert_dedupe_key("generic", text="щось зламалось")
        other = alert_dedupe_key("generic", text="інша поломка")
        self.assertEqual(first, same)
        self.assertNotEqual(first, other)

    def test_key_fits_the_column(self):
        from management.services.ig_alerts import alert_dedupe_key

        key = alert_dedupe_key("x" * 100, client_id=999999, entity_id=888888, text="y" * 500)
        self.assertLessEqual(len(key), 255)


class AlertFormatTests(TestCase):
    def test_link_is_the_last_line(self):
        from management.services.ig_alerts import format_alert

        text = format_alert(
            "🔔 Потрібен менеджер",
            lines=["Клієнт: lesiakolt", "Питання: дай посилання"],
            url="https://management.twocomms.shop/bot/?client=2",
            url_label="Картка:",
        )
        self.assertTrue(text.endswith("?client=2"))
        self.assertIn("Картка:", text)

    def test_link_survives_truncation(self):
        """Посилання — найкорисніший рядок, ріжуться факти, а не воно."""
        from management.services.ig_alerts import MAX_ALERT_CHARS, format_alert

        text = format_alert(
            "Заголовок",
            lines=["х" * 1000 for _ in range(10)],
            url="https://management.twocomms.shop/bot/?client=2",
        )
        self.assertLessEqual(len(text), MAX_ALERT_CHARS)
        self.assertIn("?client=2", text)

    def test_empty_lines_are_dropped(self):
        from management.services.ig_alerts import format_alert

        text = format_alert("Заголовок", lines=["", "   ", "Факт"])
        self.assertEqual(text, "Заголовок\nФакт")

    def test_technical_alert_accepts_only_typed_local_references(self):
        from management.services.ig_alerts import format_technical_alert

        raw_provider_body = "customer@example.com +380501112233 provider exploded"
        text = format_technical_alert(
            "⚠️ IG: технічна помилка",
            event_type="send_gave_up",
            client_id=42,
            message_id=91,
            failure_kind=raw_provider_body,
            attempts=3,
        )

        self.assertIn("Подія: send_gave_up", text)
        self.assertIn("Клієнт ID: 42", text)
        self.assertIn("Повідомлення ID: 91", text)
        self.assertIn("Тип збою: unknown", text)
        self.assertIn("Спроби: 3", text)
        self.assertIn("?client=42", text)
        self.assertNotIn("customer@example.com", text)
        self.assertNotIn("+380501112233", text)
        self.assertNotIn("provider exploded", text)

    def test_operator_alert_accepts_only_typed_local_references(self):
        from management.services.ig_alerts import format_operator_alert

        text = format_operator_alert(
            "⚠️ Потрібна перевірка оплати",
            event_type="payment_review",
            client_id=42,
            deal_id=17,
            review_id=91,
            amount="1550.00",
            status="raw provider body customer@example.com",
            instruction_code="payment_review",
        )

        self.assertIn("Подія: payment_review", text)
        self.assertIn("Клієнт ID: 42", text)
        self.assertIn("Угода ID: 17", text)
        self.assertIn("Review ID: 91", text)
        self.assertIn("Сума: 1550.00", text)
        self.assertIn("CRM: https://management.twocomms.shop/bot/?payment_review=91", text)
        self.assertNotIn("customer@example.com", text)
        self.assertNotIn("raw provider body", text)

    def test_alert_formatters_do_not_accept_freeform_instruction_or_url(self):
        import inspect

        from management.services.ig_alerts import (
            format_operator_alert,
            format_technical_alert,
        )

        technical_params = inspect.signature(format_technical_alert).parameters
        operator_params = inspect.signature(format_operator_alert).parameters
        self.assertNotIn("instruction", technical_params)
        self.assertNotIn("instruction", operator_params)
        self.assertNotIn("url", operator_params)
        self.assertIn("instruction_code", technical_params)
        self.assertIn("instruction_code", operator_params)

        marker = "private-question-marker customer@example.com"
        technical = format_technical_alert(
            marker,
            event_type="generation_failed",
            client_id=42,
            instruction_code=marker,
        )
        operator = format_operator_alert(
            marker,
            event_type="payment_review",
            client_id=42,
            review_id=91,
            instruction_code=marker,
        )
        self.assertNotIn(marker, technical)
        self.assertNotIn(marker, operator)
        self.assertIn("?payment_review=91", operator)


class PaymentReviewAlertTests(TestCase):
    def test_payment_review_alert_omits_customer_identity_delivery_and_raw_evidence(self):
        from management.services.ig_payment_review import _alert_text

        client = SimpleNamespace(
            pk=42,
            igsid="17841400000009999",
            username="private_customer_name",
            display_name="Private Customer",
        )
        review = SimpleNamespace(
            pk=91,
            evidence={
                "order_draft": {
                    "quoted_total": "1550.00",
                    "delivery": {
                        "full_name": "Іван Іванов",
                        "phone": "+380501112233",
                        "city": "Київ",
                        "office": "123",
                    },
                    "context_messages": [
                        {"text": "private-question-marker customer@example.com"},
                    ],
                },
                "media": [{"role": "receipt"}],
            },
        )

        text = _alert_text(review, client)

        for private_value in (
            client.igsid,
            client.username,
            client.display_name,
            "Іван Іванов",
            "+380501112233",
            "customer@example.com",
            "private-question-marker",
        ):
            self.assertNotIn(private_value, text)
        self.assertIn("Клієнт ID: 42", text)
        self.assertIn("Review ID: 91", text)
        self.assertIn("?payment_review=91", text)


class AdminUrlTests(TestCase):
    def test_client_url_points_at_the_crm_card(self):
        from management.services.ig_alerts import client_admin_url

        self.assertIn("/bot/?client=42", client_admin_url(42))

    def test_invalid_id_yields_no_url(self):
        from management.services.ig_alerts import client_admin_url, deal_admin_url

        self.assertEqual(client_admin_url(None), "")
        self.assertEqual(client_admin_url("abc"), "")
        self.assertEqual(deal_admin_url(0), "")


class BatchSummaryTests(TestCase):
    def test_batch_collapses_into_one_summary(self):
        from management.services.ig_alerts import summarize_batch

        text = summarize_batch("paid", [f"угода #{index}" for index in range(12)], limit=3)
        self.assertIn("угода #0", text)
        self.assertIn("і ще 9", text)
        self.assertEqual(text.count("•"), 4)

    def test_short_batch_has_no_tail(self):
        from management.services.ig_alerts import summarize_batch

        text = summarize_batch("paid", ["угода #1", "угода #2"], limit=5)
        self.assertNotIn("і ще", text)

    def test_empty_batch_produces_nothing(self):
        from management.services.ig_alerts import summarize_batch

        self.assertEqual(summarize_batch("paid", []), "")


class EscalationAlertTests(TestCase):
    """Telegram receives local references, while the CRM keeps conversation PII."""

    def test_escalation_alert_omits_customer_identity_and_question(self):
        from unittest.mock import patch

        from management.models import IgClient, InstagramBotMessage
        from management.services import instagram_bot as bot

        client = IgClient.get_or_create_for_sender("17841400000009999")
        client.username = "private_customer_name"
        client.phone = "+380501112233"
        client.save(update_fields=["username", "phone", "updated_at"])
        row = InstagramBotMessage.objects.create(
            sender_id=client.igsid, client=client,
            role=InstagramBotMessage.Role.USER,
            text="private-question-marker customer@example.com +380501112233",
        )

        with patch.object(bot, "notify_manager") as notify, \
                patch.object(bot, "_apply_stage", return_value=True):
            bot._escalate_manager_for_row(row)
            text = notify.call_args.args[0]

        for private_value in (
            client.igsid, client.username, "customer@example.com", client.phone,
            "private-question-marker",
        ):
            self.assertNotIn(private_value, text)
        self.assertIn(f"Клієнт ID: {client.pk}", text)
        self.assertIn(f"Повідомлення ID: {row.pk}", text)
        self.assertIn(f"?client={client.pk}", text)
        self.assertEqual(notify.call_args.kwargs["event_type"], "escalation")


class AiFallbackOperatorPayloadTests(TestCase):
    def test_handoff_task_and_alert_reference_crm_without_raw_customer_data(self):
        from unittest.mock import patch

        from management.models import IgClient, IgFollowUpTask, InstagramBotMessage
        from management.services.bot_reply_fallback import _queue_manager_handoff

        client = IgClient.get_or_create_for_sender("17841400000008888")
        client.username = "private_fallback_customer"
        client.save(update_fields=["username", "updated_at"])
        row = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="private-fallback-question customer@example.com +380501112233",
        )

        with patch("management.services.instagram_bot.notify_manager") as notify:
            _queue_manager_handoff(
                row,
                kind="support",
                reference="TWC-PRIVATE-REFERENCE",
            )

        task = IgFollowUpTask.objects.get(client=client)
        alert_text = notify.call_args.args[0]
        combined = f"{task.message_text}\n{alert_text}"
        for private_value in (
            client.igsid,
            client.username,
            row.text,
            "customer@example.com",
            "+380501112233",
            "TWC-PRIVATE-REFERENCE",
        ):
            self.assertNotIn(private_value, combined)
        self.assertIn(f"Повідомлення ID: {row.pk}", combined)
        self.assertIn(f"?client={client.pk}", alert_text)
