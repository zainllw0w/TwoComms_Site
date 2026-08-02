"""Блок A — находки, подтверждённые данными прода, а не чтением кода.

Все шесть дефектов ниже измерены на живой базе; для каждого есть число.

F-PAT-003 — размеры кириллицей не распознаются. Клиенты пишут «М», «л», «с»
чаще, чем латиницей (46 токенов против 43). 41 сообщение содержит только
кириллический размер, это 31 клиент, и у 24 из них `current_size` пуст.

F-AI-008 — язык не липкий. У 99 из 168 клиентов с двумя и более определениями
язык меняется хотя бы раз, всего 229 переключений, у 93 клиентов в диалоге есть
и ru, и uk. Бот отвечает то на одном, то на другом.

F-CAT-001 — каталог обрезается по символам молча. Фактический размер 16 118 при
лимите 16 000, поэтому 22 published товара из 71 бот не видит, а обрыв
приходится на середину строки товара.

IMP-054 — две несогласованные конфигурации тишины: `bot_followups` 10:00–19:00,
`services/config_versions` 21:00–08:00.

F-OPS-005 — событие с ТТН клиента #303 висело в `waiting_window` с 53 попытками
без дедлайна и эскалации; клиент оплатил 3428 грн и номер не получил.

F-STATE-009 — у клиента #303 оплаченный отправленный заказ, а `stage='new'`:
стадия пересчитывается только от входящего сообщения.
"""
from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from management.ig_bot_models import IgClient, IgFollowUpTask
from management.models import InstagramBotMessage
from orders.models import Order


class CyrillicSizeTests(TestCase):
    """F-PAT-003: тот же класс ошибки, что F-PAT-002, в другой раскладке."""

    def _classify(self, text, key):
        from management.services.bot_sales_classifier import classify_message

        client = IgClient.get_or_create_for_sender(key)
        message = InstagramBotMessage.objects.create(
            client=client, role=InstagramBotMessage.Role.USER, text=text
        )
        classify_message(client, message=message)
        client.refresh_from_db()
        return client

    def test_bare_cyrillic_size_answer_is_understood(self):
        """Дословные сообщения с прода: «М», «Лучше л», «Давайте краще л»."""
        for index, (text, expected) in enumerate((
            ("М", "M"),
            ("л", "L"),
            ("с", "S"),
            ("хл", "XL"),
        )):
            with self.subTest(text=text):
                client = self._classify(text, f"cyr-size-bare-{index}")
                self.assertEqual(client.current_size, expected)

    def test_cyrillic_size_with_context_is_understood(self):
        client = self._classify("Давайте краще л", "cyr-size-context")

        self.assertEqual(client.current_size, "L")

    def test_cyrillic_size_after_the_word_is_understood(self):
        client = self._classify("розмір м підійде?", "cyr-size-word")

        self.assertEqual(client.current_size, "M")

    def test_latin_size_still_works(self):
        client = self._classify("Давайте XL", "cyr-size-latin-regress")

        self.assertEqual(client.current_size, "XL")

    def test_cyrillic_letter_inside_a_sentence_is_not_a_size(self):
        """Иначе вернётся ошибка «it's ok», только в кириллице."""
        client = self._classify(
            "а с чого починається виготовлення принта?", "cyr-size-false-positive"
        )

        self.assertEqual(client.current_size, "")

    def test_cyrillic_size_is_normalized_to_latin(self):
        """Все значения на проде латинские; смешивать раскладки нельзя."""
        from management.services.bot_sales_classifier import normalize_size_token

        self.assertEqual(normalize_size_token("м"), "M")
        self.assertEqual(normalize_size_token("ХЛ"), "XL")
        self.assertEqual(normalize_size_token("xl"), "XL")
        self.assertEqual(normalize_size_token("ххл"), "XXL")


class LanguageStickinessTests(TestCase):
    """F-AI-008: 229 переключений языка у 99 клиентов."""

    def _classify(self, client, text):
        from management.services.bot_sales_classifier import classify_message

        message = InstagramBotMessage.objects.create(
            client=client, role=InstagramBotMessage.Role.USER, text=text
        )
        classify_message(client, message=message)
        client.refresh_from_db()
        return client.language

    def test_single_ambiguous_message_does_not_flip_the_language(self):
        client = IgClient.get_or_create_for_sender("lang-no-flip")
        self._classify(client, "Вітаю, підкажіть будь ласка щодо розміру")
        self.assertEqual(client.language, "uk")

        self._classify(client, "ок, спасибо")

        self.assertEqual(
            client.language, "uk", "одно неоднозначное сообщение — не смена языка"
        )

    def test_two_consistent_messages_do_flip_the_language(self):
        client = IgClient.get_or_create_for_sender("lang-flip-confirmed")
        self._classify(client, "Вітаю, підкажіть щодо розміру")

        self._classify(client, "здравствуйте, скажите пожалуйста")
        self._classify(client, "мне нужен размер побольше")

        self.assertEqual(client.language, "ru")

    def test_first_detection_sets_the_language_immediately(self):
        client = IgClient.get_or_create_for_sender("lang-first")

        self._classify(client, "hello, do you ship to Poland?")

        self.assertEqual(client.language, "en")

    def test_unrecognized_message_keeps_the_previous_language(self):
        client = IgClient.get_or_create_for_sender("lang-keep")
        self._classify(client, "hello, is it available?")

        self._classify(client, "👍")

        self.assertEqual(client.language, "en")


class QuietHoursTests(TestCase):
    """IMP-054: одна конфигурация тишины и аварийное окно ради окна Meta."""

    def test_initiation_window_starts_at_ten(self):
        from management.services import bot_followups

        self.assertEqual(bot_followups.QUIET_START, time(10, 0))

    def test_initiation_window_now_ends_at_half_past_nine_pm(self):
        """19:00 отрезало вечер — самое живое время в Instagram."""
        from management.services import bot_followups

        self.assertEqual(bot_followups.QUIET_END, time(21, 30))

    def test_emergency_window_is_wider_than_the_initiation_window(self):
        from management.services import bot_followups

        self.assertLess(bot_followups.EMERGENCY_START, bot_followups.QUIET_START)
        self.assertGreater(bot_followups.EMERGENCY_END, bot_followups.QUIET_END)

    def test_late_evening_candidate_is_postponed_to_the_morning(self):
        from django.utils import timezone as tz

        from management.services.bot_followups import next_allowed_send_at

        candidate = tz.localtime(tz.now()).replace(
            hour=23, minute=0, second=0, microsecond=0
        )

        allowed = tz.localtime(next_allowed_send_at(candidate))

        self.assertEqual(allowed.hour, 10)

    def test_deadline_before_the_morning_uses_the_emergency_window(self):
        """Иначе задача умрёт от окна Meta, не дождавшись тишины."""
        from django.utils import timezone as tz

        from management.services.bot_followups import next_allowed_send_at

        candidate = tz.localtime(tz.now()).replace(
            hour=22, minute=0, second=0, microsecond=0
        )
        deadline = candidate + timedelta(minutes=20)

        allowed = tz.localtime(next_allowed_send_at(candidate, deadline=deadline))

        self.assertEqual(allowed.hour, 22)

    def test_deadline_outside_even_the_emergency_window_does_not_send_at_night(self):
        from django.utils import timezone as tz

        from management.services.bot_followups import next_allowed_send_at

        candidate = tz.localtime(tz.now()).replace(
            hour=3, minute=0, second=0, microsecond=0
        )
        deadline = candidate + timedelta(minutes=20)

        allowed = tz.localtime(next_allowed_send_at(candidate, deadline=deadline))

        self.assertGreaterEqual(allowed.hour, 9)


class CatalogTruncationTests(TestCase):
    """F-CAT-001: 22 published товара из 71 не попадали в промпт, молча."""

    def test_truncation_keeps_whole_product_lines(self):
        from management.services.bot_catalog import truncate_catalog_lines

        lines = [f"• id={index} | " + "x" * 100 for index in range(50)]

        text, dropped = truncate_catalog_lines(lines, limit=1000)

        self.assertGreater(dropped, 0)
        for line in text.split("\n"):
            if line.startswith("•"):
                self.assertTrue(line.endswith("x"), "строка товара обрезана посередине")

    def test_truncation_reports_how_many_were_dropped(self):
        from management.services.bot_catalog import truncate_catalog_lines

        lines = [f"• id={index} | " + "x" * 100 for index in range(50)]

        text, dropped = truncate_catalog_lines(lines, limit=1000)

        self.assertIn(str(dropped), text)

    def test_nothing_is_dropped_when_it_fits(self):
        from management.services.bot_catalog import truncate_catalog_lines

        lines = ["• id=1 | short", "• id=2 | short"]

        text, dropped = truncate_catalog_lines(lines, limit=10000)

        self.assertEqual(dropped, 0)
        self.assertNotIn("скорочено", text)

    def test_truncation_is_logged_so_it_stops_being_silent(self):
        from management.services import bot_catalog

        lines = [f"• id={index} | " + "x" * 100 for index in range(50)]

        with patch.object(bot_catalog, "_log_catalog_truncation") as logger:
            bot_catalog.truncate_catalog_lines(lines, limit=1000)

        self.assertEqual(logger.call_count, 1)


class StuckEventEscalationTests(TestCase):
    """F-OPS-005: 53 попытки в `waiting_window` без дедлайна и эскалации."""

    def setUp(self):
        from management.models import InstagramBotSettings

        self.manager = get_user_model().objects.create_user(
            "stuck-event-manager", password="x", is_staff=True
        )
        InstagramBotSettings.objects.update_or_create(
            pk=1, defaults={"is_enabled": True}
        )

    def _waiting_event(self, *, attempts, hours_old):
        from management.ig_bot_models import IgOrderCustomerEvent
        from management.services.ig_order_assignments import link_order_to_client

        client = IgClient.get_or_create_for_sender(f"stuck-{attempts}-{hours_old}")
        client.manager_takeover = True
        client.last_message_at = timezone.now()
        client.save(update_fields=[
            "manager_takeover", "last_message_at", "updated_at",
        ])
        order = Order.objects.create(
            order_number=f"TWC-STUCK-{attempts}-{hours_old}",
            full_name="Buyer",
            phone="380500000000",
            total_sum=Decimal("3428.00"),
            payment_status="paid",
            status="ship",
            tracking_number=f"5900172758{attempts:04d}",
        )
        from management.services.ig_order_fulfillment import ensure_assignment_events

        assignment = link_order_to_client(order, client=client, actor=self.manager)
        # `on_commit` внутри тестовой транзакции не исполняется, поэтому
        # материализуем события так же, как это делает воркер.
        ensure_assignment_events(assignment)
        event = IgOrderCustomerEvent.objects.filter(
            order=order, kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED
        ).first()
        IgOrderCustomerEvent.objects.filter(pk=event.pk).update(
            state=IgOrderCustomerEvent.State.WAITING_WINDOW,
            attempts=attempts,
            due_at=timezone.now() - timedelta(minutes=1),
            created_at=timezone.now() - timedelta(hours=hours_old),
        )
        event.refresh_from_db()
        return event

    def test_long_stuck_event_is_escalated_to_a_manager(self):
        from management.ig_bot_models import IgOrderCustomerEvent
        from management.services.ig_order_fulfillment import deliver_event

        event = self._waiting_event(attempts=53, hours_old=14)

        deliver_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(event.state, IgOrderCustomerEvent.State.MANAGER_REVIEW)
        self.assertIn("менеджер", event.last_error.lower())

    def test_recently_stuck_event_keeps_retrying(self):
        from management.ig_bot_models import IgOrderCustomerEvent
        from management.services.ig_order_fulfillment import deliver_event

        event = self._waiting_event(attempts=3, hours_old=1)

        deliver_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(event.state, IgOrderCustomerEvent.State.WAITING_WINDOW)


class OrderDrivenStageTests(TestCase):
    """F-STATE-009: оплаченный отправленный заказ не двигал стадию клиента."""

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "order-stage-manager", password="x", is_staff=True
        )

    def _order(self, number, *, payment_status="paid", status="ship"):
        return Order.objects.create(
            order_number=number,
            full_name="Buyer",
            phone="380500000000",
            total_sum=Decimal("1500.00"),
            payment_status=payment_status,
            status=status,
        )

    def test_linking_a_paid_order_advances_the_stage(self):
        from management.services.ig_order_assignments import link_order_to_client

        client = IgClient.get_or_create_for_sender("order-stage-paid")
        self.assertEqual(client.stage, IgClient.Stage.NEW)

        link_order_to_client(
            self._order("TWC-STAGE-PAID"), client=client, actor=self.manager
        )

        client.refresh_from_db()
        self.assertEqual(client.stage, IgClient.Stage.ORDER_CREATED)

    def test_linking_an_unpaid_order_does_not_claim_a_purchase(self):
        from management.services.ig_order_assignments import link_order_to_client

        client = IgClient.get_or_create_for_sender("order-stage-unpaid")

        link_order_to_client(
            self._order("TWC-STAGE-UNPAID", payment_status="unpaid", status="new"),
            client=client,
            actor=self.manager,
        )

        client.refresh_from_db()
        self.assertEqual(client.stage, IgClient.Stage.NEW)

    def test_a_more_advanced_stage_is_not_regressed(self):
        from management.services.ig_order_assignments import link_order_to_client

        client = IgClient.get_or_create_for_sender("order-stage-done")
        client.stage = IgClient.Stage.DONE
        client.save(update_fields=["stage", "updated_at"])

        link_order_to_client(
            self._order("TWC-STAGE-DONE"), client=client, actor=self.manager
        )

        client.refresh_from_db()
        self.assertEqual(client.stage, IgClient.Stage.DONE)

    def test_delivered_order_moves_the_stage_to_done(self):
        from management.services.ig_order_assignments import link_order_to_client

        client = IgClient.get_or_create_for_sender("order-stage-delivered")

        link_order_to_client(
            self._order("TWC-STAGE-DELIVERED", status="done"),
            client=client,
            actor=self.manager,
        )

        client.refresh_from_db()
        self.assertEqual(client.stage, IgClient.Stage.DONE)
