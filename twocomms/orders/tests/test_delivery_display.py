from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings

from orders.delivery_display import build_nova_poshta_point
from orders.models import Order
from orders.nova_poshta_lookup import NovaPoshtaDirectoryService
from orders.telegram_notifications import TelegramNotifier


class NovaPoshtaPointDisplayTests(SimpleTestCase):
    def test_branch_number_and_address_are_separated(self):
        point = build_nova_poshta_point(
            "Харків",
            "Відділення №4, вул. Полтавський шлях, 1",
        )

        self.assertEqual(point.kind, "branch")
        self.assertEqual(point.kind_label, "Відділення")
        self.assertEqual(point.number, "4")
        self.assertEqual(point.address, "вул. Полтавський шлях, 1")
        self.assertEqual(point.icon, "🏢")

    def test_postomat_number_and_address_are_separated(self):
        point = build_nova_poshta_point(
            "Київ",
            "Поштомат 21586, вул. Хрещатик, 1",
        )

        self.assertEqual(point.kind, "postomat")
        self.assertEqual(point.kind_label, "Поштомат")
        self.assertEqual(point.number, "21586")
        self.assertEqual(point.address, "вул. Хрещатик, 1")
        self.assertEqual(point.icon, "📮")

    def test_legacy_numeric_point_is_presented_as_branch_number(self):
        point = build_nova_poshta_point("Львів", "1")

        self.assertEqual(point.kind, "branch")
        self.assertEqual(point.number, "1")
        self.assertIn("№ 1", point.telegram_text)

    def test_legacy_long_numeric_point_is_presented_as_postomat(self):
        point = build_nova_poshta_point("Ізюм", "33383")

        self.assertEqual(point.kind, "postomat")
        self.assertEqual(point.number, "33383")

    def test_legacy_number_before_postomat_marker_is_recovered(self):
        point = build_nova_poshta_point("Одеса", "21597 поштомат Балківська 137г")

        self.assertEqual(point.kind, "postomat")
        self.assertEqual(point.number, "21597")

    def test_legacy_terse_postomat_note_recovers_number(self):
        point = build_nova_poshta_point("Бориспіль", "На 8507")

        self.assertEqual(point.kind, "postomat")
        self.assertEqual(point.number, "8507")

    def test_legacy_nova_poshta_number_is_presented_as_branch(self):
        point = build_nova_poshta_point("Івано-Франківськ", "Нова пошта 8")

        self.assertEqual(point.kind, "branch")
        self.assertEqual(point.number, "8")

    def test_missing_delivery_data_is_not_presented_as_address_delivery(self):
        point = build_nova_poshta_point("", "")

        self.assertEqual(point.kind, "missing")
        self.assertEqual(point.kind_label, "Дані доставки не вказані")
        self.assertEqual(point.number, "")
        self.assertEqual(point.address, "")
        self.assertIn("Дані доставки не вказані", point.telegram_text)

    def test_missing_point_keeps_known_city_visible(self):
        point = build_nova_poshta_point("Харків", "")

        self.assertEqual(point.kind, "missing")
        self.assertIn("Харків", point.telegram_text)

    def test_telegram_values_are_html_escaped(self):
        point = build_nova_poshta_point("Київ & область", "Поштомат №22, вул. <Тестова>")

        self.assertIn("Київ &amp; область", point.telegram_text)
        self.assertIn("&lt;Тестова&gt;", point.telegram_text)
        self.assertNotIn("<Тестова>", point.telegram_text)


class OrderTelegramDeliveryDisplayTests(TestCase):
    def test_new_order_message_highlights_postomat_and_number(self):
        order = Order.objects.create(
            full_name="Тестовий клієнт",
            phone="+380501112233",
            city="Київ",
            np_office="Поштомат №21586, вул. Хрещатик, 1",
            pay_type="online_full",
            payment_status="paid",
            total_sum="1000.00",
        )

        message = TelegramNotifier().format_order_message(order)

        self.assertIn("📮 Тип: Поштомат", message)
        self.assertIn("Номер: № 21586", message)
        self.assertIn("Адреса: Поштомат №21586, вул. Хрещатик, 1", message)


class NovaPoshtaWarehouseRefLookupTests(SimpleTestCase):
    @override_settings(NOVA_POSHTA_API_KEY="test-key")
    def test_ref_lookup_builds_canonical_postomat_label_with_number(self):
        cache.clear()
        service = NovaPoshtaDirectoryService()
        payload = [{
            "Ref": "postomat-ref",
            "Description": 'Поштомат "Нова Пошта" №46071',
            "ShortAddress": "Харків, вул. Дача 55, 9",
            "Number": "46071",
            "CategoryOfWarehouse": "Postomat",
        }]

        with patch.object(service, "_request", return_value=payload) as request:
            record = service.get_warehouse_by_ref("postomat-ref")

        self.assertEqual(record["kind"], "postomat")
        self.assertEqual(record["number"], "46071")
        self.assertEqual(record["label"], "Поштомат № 46071: Харків, вул. Дача 55, 9")
        request.assert_called_once_with("Address", "getWarehouses", {"Ref": "postomat-ref"})


class NovaPoshtaDeliveryBackfillTests(TestCase):
    def test_command_restores_canonical_label_for_existing_order(self):
        order = Order.objects.create(
            full_name="Старий клієнт",
            phone="+380501112244",
            city="Харків",
            np_office="Харків, вул. Дача 55, 9",
            np_warehouse_ref="postomat-ref",
        )
        canonical = {
            "label": "Поштомат № 46071: Харків, вул. Дача 55, 9",
            "kind": "postomat",
            "number": "46071",
        }
        output = StringIO()

        with patch(
            "orders.management.commands.backfill_nova_poshta_delivery_labels."
            "NovaPoshtaDirectoryService.get_warehouse_by_ref",
            return_value=canonical,
        ):
            call_command(
                "backfill_nova_poshta_delivery_labels",
                delay=0,
                stdout=output,
            )

        order.refresh_from_db()
        self.assertEqual(order.np_office, canonical["label"])
        self.assertIn("Updated 1 orders", output.getvalue())
