"""W3 / IMP-062 — новая ТТН привязывается к тому же заказу как обмен.

Прямой запрос заказчика: «мне нужна новая ТТН для подвяза, чтобы было понятно,
что это тот же заказ и по нему был обмен, а не возврат».

Состояние до правки, снятое с прода по клиенту #59:

- `Order#296` (TWC24072026N01), `tracking_number=20451495591085` — исходная
  отправка;
- в переписке два числа-ТТН, которых нет **ни в одном поле БД**: `20451496352240`
  из сообщения клиента (он отправил товар назад) и `59001727278637` из сообщения
  менеджера (замена XL уехала);
- `Order.tracking_number` — одно скалярное поле без истории во всём проекте,
  поэтому вписать ТТН замены означало бы затереть исходную и потерять факт,
  что отправок было две;
- `IgPostSaleCase` не имеет ни одного поля под ТТН;
- текст `ttn_assigned` говорит «Ваше замовлення відправлено» — для замены это
  ложь по смыслу: клиент прочитает как повторную отправку заказа.

Обмен — это одна покупка и несколько отправок. Поэтому появляется журнал
отправок на заказе, а не второй заказ: второй заказ удвоил бы выручку и
`purchases_count`.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from management.ig_bot_models import (
    IgClient,
    IgPostSaleCase,
)
from management.models import InstagramBotMessage
from orders.models import Order

INITIAL_TTN = "20451495591085"
RETURN_TTN = "20451496352240"
REPLACEMENT_TTN = "59001727278637"


class ExchangeShipmentMixin:
    def _order(self, number="TWC-EXCH-01", *, tracking=INITIAL_TTN, status="ship"):
        return Order.objects.create(
            order_number=number,
            full_name="Ніколаєнко Яна",
            phone="380502034719",
            total_sum=Decimal("2100.00"),
            payment_status="paid",
            status=status,
            tracking_number=tracking,
        )

    def _client(self, key="exchange-client"):
        return IgClient.get_or_create_for_sender(key)

    def _case(self, client, order, *, status=None, case_type=None, key="c"):
        return IgPostSaleCase.objects.create(
            client=client,
            order=order,
            source_message=InstagramBotMessage.objects.create(
                client=client,
                role=InstagramBotMessage.Role.USER,
                text=f"розмір не підійшов, хочу обмін {key}",
            ),
            case_type=case_type or IgPostSaleCase.CaseType.EXCHANGE,
            status=status or IgPostSaleCase.Status.APPROVED,
            requested_size="XL",
        )


class ShipmentJournalTests(ExchangeShipmentMixin, TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "exchange-journal-manager", password="x", is_staff=True
        )

    def test_initial_tracking_is_recorded_as_the_first_shipment(self):
        from management.ig_bot_models import IgOrderShipment

        order = self._order()

        shipment = IgOrderShipment.objects.get(order=order)

        self.assertEqual(shipment.tracking_number, INITIAL_TTN)
        self.assertEqual(shipment.direction, IgOrderShipment.Direction.OUTBOUND)
        self.assertEqual(shipment.purpose, IgOrderShipment.Purpose.INITIAL)

    def test_replacing_tracking_keeps_the_original_shipment(self):
        """Главное требование: исходная ТТН не должна исчезать."""
        from management.ig_bot_models import IgOrderShipment

        order = self._order()
        client = self._client()
        self._case(client, order)

        order.tracking_number = REPLACEMENT_TTN
        order.save(update_fields=["tracking_number", "updated"])

        numbers = set(
            IgOrderShipment.objects.filter(order=order).values_list(
                "tracking_number", flat=True
            )
        )
        self.assertEqual(numbers, {INITIAL_TTN, REPLACEMENT_TTN})

    def test_replacement_during_an_exchange_is_marked_as_such(self):
        from management.ig_bot_models import IgOrderShipment

        order = self._order()
        client = self._client()
        case = self._case(client, order)

        order.tracking_number = REPLACEMENT_TTN
        order.save(update_fields=["tracking_number", "updated"])

        replacement = IgOrderShipment.objects.get(
            order=order, tracking_number=REPLACEMENT_TTN
        )
        self.assertEqual(
            replacement.purpose, IgOrderShipment.Purpose.EXCHANGE_REPLACEMENT
        )
        self.assertEqual(replacement.post_sale_case_id, case.pk)

    def test_replacement_points_at_the_shipment_it_supersedes(self):
        from management.ig_bot_models import IgOrderShipment

        order = self._order()
        self._case(self._client(), order)

        order.tracking_number = REPLACEMENT_TTN
        order.save(update_fields=["tracking_number", "updated"])

        initial = IgOrderShipment.objects.get(order=order, tracking_number=INITIAL_TTN)
        replacement = IgOrderShipment.objects.get(
            order=order, tracking_number=REPLACEMENT_TTN
        )
        self.assertEqual(replacement.supersedes_id, initial.pk)

    def test_tracking_change_without_a_case_is_a_correction_not_an_exchange(self):
        """Менеджер переоформил ТТН по ошибке — это не обмен."""
        from management.ig_bot_models import IgOrderShipment

        order = self._order(number="TWC-EXCH-FIX")

        order.tracking_number = REPLACEMENT_TTN
        order.save(update_fields=["tracking_number", "updated"])

        replacement = IgOrderShipment.objects.get(
            order=order, tracking_number=REPLACEMENT_TTN
        )
        self.assertEqual(replacement.purpose, IgOrderShipment.Purpose.CORRECTION)

    def test_repeated_save_of_the_same_tracking_creates_no_duplicate(self):
        from management.ig_bot_models import IgOrderShipment

        order = self._order(number="TWC-EXCH-IDEMPOTENT")
        order.save(update_fields=["tracking_number", "updated"])
        order.save(update_fields=["tracking_number", "updated"])

        self.assertEqual(IgOrderShipment.objects.filter(order=order).count(), 1)

    def test_clearing_tracking_does_not_erase_history(self):
        from management.ig_bot_models import IgOrderShipment

        order = self._order(number="TWC-EXCH-CLEARED")

        order.tracking_number = None
        order.save(update_fields=["tracking_number", "updated"])

        self.assertEqual(IgOrderShipment.objects.filter(order=order).count(), 1)

    def test_shipment_journal_is_append_only(self):
        from management.ig_bot_models import IgOrderShipment

        order = self._order(number="TWC-EXCH-APPEND")
        shipment = IgOrderShipment.objects.get(order=order)

        with self.assertRaises(ValueError):
            shipment.delete()
        with self.assertRaises(ValueError):
            IgOrderShipment.objects.filter(pk=shipment.pk).delete()


class ReturnLegTests(ExchangeShipmentMixin, TestCase):
    """ТТН возврата приходит текстом от клиента, поэтому её нельзя вывести."""

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "exchange-return-manager", password="x", is_staff=True
        )

    def test_manager_can_record_the_return_tracking(self):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_post_sale import record_return_shipment

        order = self._order(number="TWC-EXCH-RETURN")
        case = self._case(self._client("return-leg-client"), order)

        shipment = record_return_shipment(
            case, RETURN_TTN, actor=self.manager, evidence_message_id=933
        )

        self.assertEqual(shipment.tracking_number, RETURN_TTN)
        self.assertEqual(shipment.direction, IgOrderShipment.Direction.INBOUND)
        self.assertEqual(shipment.purpose, IgOrderShipment.Purpose.RETURN_INBOUND)
        self.assertEqual(shipment.post_sale_case_id, case.pk)
        self.assertEqual(shipment.evidence_message_id, 933)

    def test_return_tracking_does_not_touch_the_order_field(self):
        """Обратная посылка — не отправка заказа, поле заказа не трогаем."""
        from management.services.ig_post_sale import record_return_shipment

        order = self._order(number="TWC-EXCH-RETURN-FIELD")
        case = self._case(self._client("return-field-client"), order)

        record_return_shipment(case, RETURN_TTN, actor=self.manager)

        order.refresh_from_db()
        self.assertEqual(order.tracking_number, INITIAL_TTN)

    def test_recording_the_same_return_tracking_twice_is_idempotent(self):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_post_sale import record_return_shipment

        order = self._order(number="TWC-EXCH-RETURN-TWICE")
        case = self._case(self._client("return-twice-client"), order)

        first = record_return_shipment(case, RETURN_TTN, actor=self.manager)
        second = record_return_shipment(case, RETURN_TTN, actor=self.manager)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            IgOrderShipment.objects.filter(
                order=order, tracking_number=RETURN_TTN
            ).count(),
            1,
        )

    def test_invalid_tracking_is_rejected(self):
        from management.services.ig_post_sale import record_return_shipment

        order = self._order(number="TWC-EXCH-RETURN-BAD")
        case = self._case(self._client("return-bad-client"), order)

        for value in ("", "   ", "12345", "abc-not-a-ttn"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    record_return_shipment(case, value, actor=self.manager)

    def test_case_without_an_order_cannot_record_a_return(self):
        from management.services.ig_post_sale import record_return_shipment

        client = self._client("return-no-order-client")
        case = IgPostSaleCase.objects.create(
            client=client,
            source_message=InstagramBotMessage.objects.create(
                client=client,
                role=InstagramBotMessage.Role.USER,
                text="хочу обмін",
            ),
            case_type=IgPostSaleCase.CaseType.EXCHANGE,
            status=IgPostSaleCase.Status.NEEDS_DETAILS,
        )

        with self.assertRaises(ValueError):
            record_return_shipment(case, RETURN_TTN, actor=self.manager)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class ExchangeTimelineTests(ExchangeShipmentMixin, TestCase):
    """Одним взглядом должно быть видно: один заказ, обмен, три отправки."""

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "exchange-timeline-manager", password="x", is_staff=True
        )

    def _full_exchange(self):
        from management.services.ig_post_sale import record_return_shipment

        order = self._order(number="TWC24072026N01")
        client = self._client("timeline-client")
        case = self._case(client, order, status=IgPostSaleCase.Status.IN_TRANSIT)
        record_return_shipment(case, RETURN_TTN, actor=self.manager)
        order.tracking_number = REPLACEMENT_TTN
        order.save(update_fields=["tracking_number", "updated"])
        return client, order, case

    def test_case_payload_lists_all_three_shipments_in_order(self):
        from management.bot_views import _post_sale_case_payload

        _client, _order, case = self._full_exchange()

        payload = _post_sale_case_payload(case)
        rows = payload["shipments"]

        self.assertEqual(
            [row["tracking_number"] for row in rows],
            [INITIAL_TTN, RETURN_TTN, REPLACEMENT_TTN],
        )

    def test_timeline_names_each_leg_in_human_words(self):
        from management.bot_views import _post_sale_case_payload

        _client, _order, case = self._full_exchange()

        labels = [row["purpose_label"] for row in _post_sale_case_payload(case)["shipments"]]

        self.assertEqual(
            labels,
            ["Перша відправка", "Повернення від клієнта", "Заміна відправлена"],
        )

    def test_timeline_says_it_is_one_order(self):
        from management.bot_views import _post_sale_case_payload

        _client, order, case = self._full_exchange()

        payload = _post_sale_case_payload(case)

        self.assertEqual(payload["order"]["number"], "TWC24072026N01")
        self.assertTrue(
            all(row["order_number"] == "TWC24072026N01" for row in payload["shipments"])
        )

    def test_timeline_distinguishes_exchange_from_refund(self):
        from management.bot_views import _post_sale_case_payload

        _client, _order, case = self._full_exchange()

        payload = _post_sale_case_payload(case)

        self.assertEqual(payload["case_type"], "exchange")
        self.assertEqual(payload["case_type_label"], "Обмін")
        self.assertTrue(payload["has_replacement_shipment"])
        self.assertTrue(payload["has_return_shipment"])


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class ReturnTrackingApiTests(ExchangeShipmentMixin, TestCase):
    def setUp(self):
        from django.test import Client as DjangoClient

        self.manager = get_user_model().objects.create_user(
            "exchange-api-manager", password="x", is_staff=True, is_superuser=True
        )
        self.http = DjangoClient()
        self.http.force_login(self.manager)

    def test_api_records_the_return_tracking(self):
        order = self._order(number="TWC-EXCH-API")
        client = self._client("api-return-client")
        case = self._case(client, order)

        response = self.http.post(
            reverse(
                "management_bot_post_sale_case_api", args=[client.pk, case.pk]
            ),
            {"return_tracking_number": RETURN_TTN},
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["success"])
        rows = response.json()["case"]["shipments"]
        self.assertIn(RETURN_TTN, [row["tracking_number"] for row in rows])

    def test_api_rejects_a_malformed_tracking(self):
        order = self._order(number="TWC-EXCH-API-BAD")
        client = self._client("api-bad-client")
        case = self._case(client, order)

        response = self.http.post(
            reverse(
                "management_bot_post_sale_case_api", args=[client.pk, case.pk]
            ),
            {"return_tracking_number": "123"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])


class ExchangeCustomerMessageTests(ExchangeShipmentMixin, TestCase):
    """Клиент должен прочитать «заміна відправлена», а не «замовлення відправлено»."""

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "exchange-message-manager", password="x", is_staff=True
        )

    def test_exchange_replacement_has_its_own_message_kind(self):
        from management.ig_bot_models import IgOrderCustomerEvent

        self.assertIn(
            "exchange_shipped",
            {value for value, _label in IgOrderCustomerEvent.Kind.choices},
        )

    def test_exchange_message_names_the_exchange_and_the_size(self):
        from management.services.ig_order_fulfillment import _message

        order = self._order(number="TWC-EXCH-MSG")
        text = _message(
            "exchange_shipped",
            "uk",
            order,
            REPLACEMENT_TTN,
            exchange_size="XL",
        )

        self.assertIn("XL", text)
        self.assertIn(REPLACEMENT_TTN, text)
        self.assertIn("амін", text)
        self.assertNotIn("Ваше замовлення №", text)

    def test_exchange_message_says_no_extra_payment_is_needed(self):
        from management.services.ig_order_fulfillment import _message

        order = self._order(number="TWC-EXCH-MSG-PAY")
        text = _message(
            "exchange_shipped", "uk", order, REPLACEMENT_TTN, exchange_size="XL"
        )

        self.assertIn("оплач", text.lower())

    def test_exchange_message_is_localized(self):
        from management.services.ig_order_fulfillment import _message

        order = self._order(number="TWC-EXCH-MSG-LOCALE")
        for locale, marker in (("en", "exchange"), ("ru", "замен")):
            with self.subTest(locale=locale):
                text = _message(
                    "exchange_shipped", locale, order, REPLACEMENT_TTN,
                    exchange_size="XL",
                )
                self.assertIn(marker, text.lower())

    def test_replacement_tracking_produces_an_exchange_event_not_a_plain_ttn(self):
        from management.ig_bot_models import IgOrderCustomerEvent
        from management.services.ig_order_assignments import link_order_to_client
        from management.services.ig_order_fulfillment import ensure_assignment_events

        order = self._order(number="TWC-EXCH-EVENT")
        client = self._client("exchange-event-client")
        client.last_message_at = None
        client.save(update_fields=["last_message_at", "updated_at"])
        link_order_to_client(order, client=client, actor=self.manager)
        self._case(client, order, status=IgPostSaleCase.Status.APPROVED)

        order.tracking_number = REPLACEMENT_TTN
        order.save(update_fields=["tracking_number", "updated"])
        # Так же, как в проде: воркер читает свежую привязку из БД, а не
        # закешированный в памяти объект.
        from management.ig_bot_models import IgOrderAssignment

        ensure_assignment_events(
            IgOrderAssignment.objects.select_related("order", "client").get(
                order_id=order.pk
            )
        )

        kinds = set(
            IgOrderCustomerEvent.objects.filter(order=order).values_list(
                "kind", flat=True
            )
        )
        self.assertIn(IgOrderCustomerEvent.Kind.EXCHANGE_SHIPPED, kinds)


class ExchangeTimelineTemplateTests(TestCase):
    """Журнал отправок бесполезен, если менеджер его не видит."""

    def _template(self):
        from pathlib import Path

        from django.conf import settings

        return (
            Path(settings.BASE_DIR)
            / "management"
            / "templates"
            / "management"
            / "bot.html"
        ).read_text(encoding="utf-8")

    def test_template_renders_the_shipment_timeline(self):
        self.assertTrue(
            "renderShipmentTimeline" in self._template(),
            "у карточці немає таймлайну відправок",
        )

    def test_template_has_a_field_for_the_return_tracking(self):
        template = self._template()

        self.assertTrue(
            "return_tracking_number" in template,
            "менеджеру нема куди вставити ТТН повернення",
        )

    def test_timeline_has_its_own_style(self):
        self.assertTrue(
            ".bot-shipment-timeline{" in self._template(),
            "таймлайн без стилю зіллється з рештою карточки",
        )

    def test_post_sale_strip_reports_shipment_progress(self):
        template = self._template()

        for marker in ("has_return_shipment", "has_replacement_shipment"):
            with self.subTest(marker=marker):
                self.assertIn(marker, template)


class ShipmentBackfillCommandTests(ExchangeShipmentMixin, TestCase):
    """Без бэкфилла у существующего заказа замена стала бы «первой отправкой»."""

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "shipment-backfill-manager", password="x", is_staff=True
        )

    def _linked_order_without_journal(self, number="TWC-BACKFILL-SHIP"):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_order_assignments import link_order_to_client

        order = self._order(number=number)
        link_order_to_client(order, client=self._client("backfill-ship-client"), actor=self.manager)
        # Симулируем заказ, созданный до появления журнала. Журнал append-only,
        # поэтому обходим ORM сырым SQL — только внутри теста.
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM management_igordershipment WHERE order_id = %s",
                [order.pk],
            )
        return order

    def test_dry_run_reports_without_writing(self):
        from io import StringIO

        from django.core.management import call_command

        from management.ig_bot_models import IgOrderShipment

        order = self._linked_order_without_journal()
        stdout = StringIO()

        call_command("backfill_ig_order_shipments", "--dry-run", stdout=stdout)

        self.assertIn("dry-run", stdout.getvalue())
        self.assertIn(str(order.pk), stdout.getvalue())
        self.assertEqual(IgOrderShipment.objects.filter(order=order).count(), 0)

    def test_apply_creates_the_initial_shipment(self):
        from io import StringIO

        from django.core.management import call_command

        from management.ig_bot_models import IgOrderShipment

        order = self._linked_order_without_journal(number="TWC-BACKFILL-APPLY")

        call_command("backfill_ig_order_shipments", "--apply", stdout=StringIO())

        shipment = IgOrderShipment.objects.get(order=order)
        self.assertEqual(shipment.tracking_number, INITIAL_TTN)
        self.assertEqual(shipment.purpose, IgOrderShipment.Purpose.INITIAL)

    def test_apply_is_idempotent(self):
        from io import StringIO

        from django.core.management import call_command

        from management.ig_bot_models import IgOrderShipment

        order = self._linked_order_without_journal(number="TWC-BACKFILL-TWICE")
        call_command("backfill_ig_order_shipments", "--apply", stdout=StringIO())
        second = StringIO()
        call_command("backfill_ig_order_shipments", "--apply", stdout=second)

        self.assertEqual(IgOrderShipment.objects.filter(order=order).count(), 1)
        self.assertIn("created=0", second.getvalue())


class ManualReplacementShipmentTests(ExchangeShipmentMixin, TestCase):
    """Фиксация ТТН замены задним числом, когда обмен уже закрыт.

    Автоматический вывод ноги обмена работает только пока кейс открыт: смена
    `Order.tracking_number` при закрытом кейсе — это `correction`. Но реальный
    обмен клиента #59 был закрыт менеджером вручную ещё до появления журнала, и
    ТТН замены существует только текстом в переписке. Без прямого поля эту ТТН
    некуда вставить, а именно это заказчик и просил.
    """

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "manual-replacement-manager", password="x", is_staff=True
        )

    def test_manager_can_record_a_replacement_after_the_case_is_closed(self):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_post_sale import record_replacement_shipment

        order = self._order(number="TWC-MANUAL-REPL")
        case = self._case(
            self._client("manual-repl-client"),
            order,
            status=IgPostSaleCase.Status.COMPLETED,
        )

        shipment = record_replacement_shipment(
            case, REPLACEMENT_TTN, actor=self.manager
        )

        self.assertEqual(shipment.tracking_number, REPLACEMENT_TTN)
        self.assertEqual(shipment.direction, IgOrderShipment.Direction.OUTBOUND)
        self.assertEqual(
            shipment.purpose, IgOrderShipment.Purpose.EXCHANGE_REPLACEMENT
        )
        self.assertEqual(shipment.post_sale_case_id, case.pk)
        self.assertEqual(shipment.source, IgOrderShipment.Source.MANAGER_MANUAL)

    def test_manual_replacement_supersedes_the_previous_outbound(self):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_post_sale import record_replacement_shipment

        order = self._order(number="TWC-MANUAL-REPL-CHAIN")
        case = self._case(self._client("manual-chain-client"), order)

        shipment = record_replacement_shipment(
            case, REPLACEMENT_TTN, actor=self.manager
        )

        initial = IgOrderShipment.objects.get(
            order=order, tracking_number=INITIAL_TTN
        )
        self.assertEqual(shipment.supersedes_id, initial.pk)

    def test_manual_replacement_does_not_touch_the_order_field(self):
        """Иначе воркер отправил бы клиенту сообщение про уже отправленную замену."""
        from management.services.ig_post_sale import record_replacement_shipment

        order = self._order(number="TWC-MANUAL-REPL-FIELD")
        case = self._case(self._client("manual-field-client"), order)

        record_replacement_shipment(case, REPLACEMENT_TTN, actor=self.manager)

        order.refresh_from_db()
        self.assertEqual(order.tracking_number, INITIAL_TTN)

    def test_manual_replacement_is_idempotent(self):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_post_sale import record_replacement_shipment

        order = self._order(number="TWC-MANUAL-REPL-TWICE")
        case = self._case(self._client("manual-twice-client"), order)

        first = record_replacement_shipment(case, REPLACEMENT_TTN, actor=self.manager)
        second = record_replacement_shipment(case, REPLACEMENT_TTN, actor=self.manager)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            IgOrderShipment.objects.filter(
                order=order,
                tracking_number=REPLACEMENT_TTN,
                direction=IgOrderShipment.Direction.OUTBOUND,
            ).count(),
            1,
        )

    def test_manual_replacement_rejects_a_malformed_tracking(self):
        from management.services.ig_post_sale import record_replacement_shipment

        order = self._order(number="TWC-MANUAL-REPL-BAD")
        case = self._case(self._client("manual-bad-client"), order)

        with self.assertRaises(ValueError):
            record_replacement_shipment(case, "12", actor=self.manager)

    def test_manual_replacement_refuses_the_current_order_tracking(self):
        """Текущая ТТН заказа — не замена, это та же самая отправка."""
        from management.services.ig_post_sale import record_replacement_shipment

        order = self._order(number="TWC-MANUAL-REPL-SAME")
        case = self._case(self._client("manual-same-client"), order)

        with self.assertRaises(ValueError):
            record_replacement_shipment(case, INITIAL_TTN, actor=self.manager)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class ReplacementTrackingApiTests(ExchangeShipmentMixin, TestCase):
    def setUp(self):
        from django.test import Client as DjangoClient

        self.manager = get_user_model().objects.create_user(
            "replacement-api-manager", password="x", is_staff=True, is_superuser=True
        )
        self.http = DjangoClient()
        self.http.force_login(self.manager)

    def test_api_records_the_replacement_tracking(self):
        order = self._order(number="TWC-REPL-API")
        client = self._client("api-replacement-client")
        case = self._case(
            client, order, status=IgPostSaleCase.Status.COMPLETED
        )

        response = self.http.post(
            reverse("management_bot_post_sale_case_api", args=[client.pk, case.pk]),
            {
                "status": IgPostSaleCase.Status.COMPLETED,
                "replacement_tracking_number": REPLACEMENT_TTN,
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()["case"]["shipments"]
        replacement = next(
            row for row in rows if row["tracking_number"] == REPLACEMENT_TTN
        )
        self.assertEqual(replacement["purpose"], "exchange_replacement")
        self.assertTrue(response.json()["case"]["has_replacement_shipment"])

    def test_api_can_record_both_legs_at_once(self):
        order = self._order(number="TWC-REPL-API-BOTH")
        client = self._client("api-both-client")
        case = self._case(client, order)

        response = self.http.post(
            reverse("management_bot_post_sale_case_api", args=[client.pk, case.pk]),
            {
                "return_tracking_number": RETURN_TTN,
                "replacement_tracking_number": REPLACEMENT_TTN,
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["case"]
        self.assertTrue(payload["has_return_shipment"])
        self.assertTrue(payload["has_replacement_shipment"])
        self.assertEqual(
            [row["purpose_label"] for row in payload["shipments"]],
            ["Перша відправка", "Повернення від клієнта", "Заміна відправлена"],
        )

    def test_api_rejects_a_malformed_replacement(self):
        order = self._order(number="TWC-REPL-API-BAD")
        client = self._client("api-replacement-bad")
        case = self._case(client, order)

        response = self.http.post(
            reverse("management_bot_post_sale_case_api", args=[client.pk, case.pk]),
            {"replacement_tracking_number": "abc"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_template_has_a_field_for_the_replacement_tracking(self):
        from pathlib import Path

        from django.conf import settings

        template = (
            Path(settings.BASE_DIR)
            / "management"
            / "templates"
            / "management"
            / "bot.html"
        ).read_text(encoding="utf-8")

        self.assertTrue(
            "replacement_tracking_number" in template,
            "менеджеру нема куди вставити ТТН заміни",
        )


class FastReturnSameTrackingTests(ExchangeShipmentMixin, TestCase):
    """Быстрый возврат Новой Почты идёт по ТОЙ ЖЕ ТТН, что и отправка.

    Уточнение от заказчика по живому кейсу: обратная посылка может ехать по той
    же накладной, и клиент за неё не платит — это «швидке повернення» НП.
    Замену мы отправили новой ТТН и оплатили сами.

    Для журнала это значит две вещи: один и тот же номер в обе стороны — норма,
    а не ошибка ввода; и плательщик у ног обмена разный, поэтому его надо
    хранить, а не угадывать при чтении.
    """

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "fast-return-manager", password="x", is_staff=True
        )

    def test_return_may_reuse_the_outbound_tracking(self):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_post_sale import record_return_shipment

        order = self._order(number="TWC-FAST-RETURN")
        case = self._case(self._client("fast-return-client"), order)

        shipment = record_return_shipment(case, INITIAL_TTN, actor=self.manager)

        self.assertEqual(shipment.tracking_number, INITIAL_TTN)
        self.assertEqual(shipment.direction, IgOrderShipment.Direction.INBOUND)
        self.assertEqual(
            IgOrderShipment.objects.filter(
                order=order, tracking_number=INITIAL_TTN
            ).count(),
            2,
            "той самий номер у два напрямки — це дві різні посилки",
        )

    def test_fast_return_is_marked_as_reused_and_paid_by_shop(self):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_post_sale import record_return_shipment

        order = self._order(number="TWC-FAST-RETURN-FLAGS")
        case = self._case(self._client("fast-return-flags"), order)

        shipment = record_return_shipment(case, INITIAL_TTN, actor=self.manager)

        self.assertTrue(shipment.reuses_outbound_tracking)
        self.assertEqual(shipment.payer, IgOrderShipment.Payer.SHOP)

    def test_return_on_a_new_tracking_defaults_to_the_customer_paying(self):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_post_sale import record_return_shipment

        order = self._order(number="TWC-RETURN-NEW-TTN")
        case = self._case(self._client("return-new-ttn"), order)

        shipment = record_return_shipment(case, RETURN_TTN, actor=self.manager)

        self.assertFalse(shipment.reuses_outbound_tracking)
        self.assertEqual(shipment.payer, IgOrderShipment.Payer.CUSTOMER)

    def test_explicit_payer_overrides_the_default(self):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_post_sale import record_return_shipment

        order = self._order(number="TWC-RETURN-PAYER-OVERRIDE")
        case = self._case(self._client("return-payer-override"), order)

        shipment = record_return_shipment(
            case,
            RETURN_TTN,
            actor=self.manager,
            payer=IgOrderShipment.Payer.SHOP,
        )

        self.assertEqual(shipment.payer, IgOrderShipment.Payer.SHOP)

    def test_replacement_is_paid_by_the_shop(self):
        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_post_sale import record_replacement_shipment

        order = self._order(number="TWC-REPL-PAYER")
        case = self._case(self._client("repl-payer"), order)

        shipment = record_replacement_shipment(
            case, REPLACEMENT_TTN, actor=self.manager
        )

        self.assertEqual(shipment.payer, IgOrderShipment.Payer.SHOP)

    def test_timeline_explains_the_fast_return_in_human_words(self):
        from management.services.ig_post_sale import record_return_shipment
        from management.services.ig_shipments import order_shipment_rows

        order = self._order(number="TWC-FAST-RETURN-TIMELINE")
        case = self._case(self._client("fast-return-timeline"), order)
        record_return_shipment(case, INITIAL_TTN, actor=self.manager)

        rows = order_shipment_rows(order)
        inbound = next(row for row in rows if row["direction"] == "inbound")

        self.assertIn("тією ж ТТН", inbound["purpose_label"])
        self.assertEqual(inbound["payer_label"], "За наш рахунок")

    def test_timeline_keeps_plain_label_for_a_separate_return_parcel(self):
        from management.services.ig_post_sale import record_return_shipment
        from management.services.ig_shipments import order_shipment_rows

        order = self._order(number="TWC-RETURN-PLAIN-LABEL")
        case = self._case(self._client("return-plain-label"), order)
        record_return_shipment(case, RETURN_TTN, actor=self.manager)

        rows = order_shipment_rows(order)
        inbound = next(row for row in rows if row["direction"] == "inbound")

        self.assertEqual(inbound["purpose_label"], "Повернення від клієнта")
        self.assertEqual(inbound["payer_label"], "За рахунок клієнта")

    def test_replacement_still_refuses_the_current_order_tracking(self):
        """Регрес: для ИСХОДЯЩЕЙ ноги та же ТТН по-прежнему не замена."""
        from management.services.ig_post_sale import record_replacement_shipment

        order = self._order(number="TWC-REPL-SAME-GUARD")
        case = self._case(self._client("repl-same-guard"), order)

        with self.assertRaises(ValueError):
            record_replacement_shipment(case, INITIAL_TTN, actor=self.manager)
