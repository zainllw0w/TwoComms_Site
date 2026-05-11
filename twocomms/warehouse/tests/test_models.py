"""Tests for warehouse models and inventory services."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from warehouse.models import (
    MovementReason,
    Print,
    PrintColorVariant,
    StockItem,
    StockMovement,
    StorageCategory,
    StorageSubcategory,
    WarehouseSettings,
)
from warehouse.services.inventory import (
    adjust_print_variant,
    adjust_stock_item,
    set_stock_quantity,
)

User = get_user_model()


class StorageCategoryTests(TestCase):
    def test_auto_slug(self):
        cat = StorageCategory.objects.create(name="Тестова категорія")
        # dtf.utils.build_slug transliterates cyrillic; exact slug may vary
        # between transliteration libraries — just ensure non-empty and slug-safe.
        self.assertTrue(cat.slug)
        self.assertNotEqual(cat.slug, "category")
        self.assertRegex(cat.slug, r"^[a-z0-9-]+$")

    def test_unique_slug(self):
        StorageCategory.objects.create(name="Test")
        cat2 = StorageCategory.objects.create(name="Test")
        self.assertNotEqual(cat2.slug, "test")
        self.assertTrue(cat2.slug.startswith("test"))


class StorageSubcategoryTests(TestCase):
    def setUp(self):
        # Use unique slug to avoid clash with initial_data migration fixtures.
        self.cat = StorageCategory.objects.create(name="Футболки тест", slug="tshirts-test-unique")

    def test_unique_default_per_category(self):
        sub1 = StorageSubcategory.objects.create(category=self.cat, name="A", is_default=True)
        sub2 = StorageSubcategory.objects.create(category=self.cat, name="B", is_default=True)
        sub1.refresh_from_db()
        self.assertFalse(sub1.is_default)
        self.assertTrue(sub2.is_default)


class StockItemTests(TestCase):
    def setUp(self):
        self.cat = StorageCategory.objects.create(name="Cat", slug="cat")
        self.sub = StorageSubcategory.objects.create(category=self.cat, name="Sub")
        self.user = User.objects.create_user("ws", "ws@example.com", "pw")

    def test_adjust_stock_item_positive(self):
        item = StockItem.objects.create(subcategory=self.sub, size="M", quantity=0)
        m = adjust_stock_item(stock_item=item, delta=5, user=self.user, reason=MovementReason.MANUAL_ADD)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 5)
        self.assertEqual(m.delta, 5)
        self.assertEqual(m.quantity_after, 5)
        self.assertEqual(m.created_by, self.user)

    def test_adjust_stock_item_cannot_go_negative(self):
        item = StockItem.objects.create(subcategory=self.sub, size="M", quantity=2)
        with self.assertRaises(ValueError):
            adjust_stock_item(stock_item=item, delta=-5, user=self.user)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)  # unchanged

    def test_set_stock_quantity(self):
        item = StockItem.objects.create(subcategory=self.sub, size="M", quantity=3)
        set_stock_quantity(stock_item=item, new_quantity=10, user=self.user)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 10)
        # delta should be 7
        movement = StockMovement.objects.filter(object_id=item.pk).order_by("-id").first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.delta, 7)

    def test_frozen_value(self):
        item = StockItem.objects.create(
            subcategory=self.sub, size="M", quantity=5, cost_price=Decimal("250.00")
        )
        self.assertEqual(item.frozen_value, Decimal("1250.00"))


class PrintVariantTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("pu", "pu@example.com", "pw")
        self.p = Print.objects.create(name="Sabli")

    def test_adjust_print_variant(self):
        v = PrintColorVariant.objects.create(print=self.p, color_name="Green", quantity=0)
        adjust_print_variant(variant=v, delta=3, user=self.user)
        v.refresh_from_db()
        self.assertEqual(v.quantity, 3)

    def test_only_one_default_variant(self):
        v1 = PrintColorVariant.objects.create(print=self.p, color_name="Green", is_default=True)
        v2 = PrintColorVariant.objects.create(print=self.p, color_name="White", is_default=True)
        v1.refresh_from_db()
        self.assertFalse(v1.is_default)
        self.assertTrue(v2.is_default)


class WarehouseSettingsTests(TestCase):
    def test_singleton(self):
        ws1 = WarehouseSettings.load()
        ws2 = WarehouseSettings.load()
        self.assertEqual(ws1.pk, ws2.pk)
        self.assertEqual(ws1.pk, 1)

    def test_reminder_chat_ids_parsing(self):
        ws = WarehouseSettings.load()
        ws.evening_reminder_chat_ids = "123, 456,,789"
        ws.save()
        ids = ws.reminder_chat_ids_list
        self.assertEqual(ids, ["123", "456", "789"])
