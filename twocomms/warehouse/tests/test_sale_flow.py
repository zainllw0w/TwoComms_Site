"""Тести семантики продаж/списання, відміни продажу та FIN-аналітики складу."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product
from orders.models import Order, OrderItem
from warehouse.models import (
    MovementReason,
    StockItem,
    StorageCategory,
    StorageSubcategory,
    WriteOffRequest,
)
from warehouse.services.inventory import adjust_stock_item, reverse_write_off

User = get_user_model()


class MovementReasonClassifyTests(TestCase):
    def test_sale_reasons_classified_as_sold(self):
        self.assertEqual(MovementReason.category_of(MovementReason.ORDER_WRITE_OFF, -2), "sold")
        self.assertEqual(MovementReason.category_of(MovementReason.SALE, -1), "sold")

    def test_addition_reasons(self):
        for r in (MovementReason.MANUAL_ADD, MovementReason.BULK_ADD, MovementReason.PRINT_ADD, MovementReason.RETURN):
            self.assertEqual(MovementReason.category_of(r, 5), "added")

    def test_writeoff_reasons(self):
        for r in (MovementReason.MANUAL_REMOVE, MovementReason.PRINT_REMOVE, MovementReason.DAMAGE):
            self.assertEqual(MovementReason.category_of(r, -3), "written_off")

    def test_adjustment_by_sign(self):
        self.assertEqual(MovementReason.category_of(MovementReason.RECOUNT, 4), "added")
        self.assertEqual(MovementReason.category_of(MovementReason.ADJUSTMENT, -4), "written_off")


class WarehouseDynamicsTests(TestCase):
    def setUp(self):
        self.cat = StorageCategory.objects.create(name="Футболки", slug="t-dyn")
        self.sub = StorageSubcategory.objects.create(category=self.cat, name="Базова")
        self.color = Color.objects.create(name="Чорний", primary_hex="#000")
        self.stock = StockItem.objects.create(
            subcategory=self.sub, color=self.color, size="M", quantity=10,
            cost_price=Decimal("100"),
        )
        self.user = User.objects.create_user("dynu", "d@e.com", "pw")

    def test_dynamics_does_not_crash_and_counts(self):
        from finance.services import warehouse_analytics as wa

        # Прихід (manual_add) + продаж (order_write_off) + брак (damage)
        adjust_stock_item(stock_item=self.stock, delta=5, user=self.user,
                          reason=MovementReason.MANUAL_ADD)
        adjust_stock_item(stock_item=self.stock, delta=-2, user=self.user,
                          reason=MovementReason.ORDER_WRITE_OFF)
        adjust_stock_item(stock_item=self.stock, delta=-1, user=self.user,
                          reason=MovementReason.DAMAGE)

        data = wa.warehouse_dynamics(days=7)  # раніше падало AttributeError
        self.assertEqual(sum(data["added_value"]), float(Decimal("500")))   # 5 * 100
        self.assertEqual(sum(data["sold_value"]), float(Decimal("200")))    # 2 * 100
        self.assertEqual(sum(data["written_off_value"]), float(Decimal("100")))  # 1 * 100


class ReverseWriteOffTests(TestCase):
    def setUp(self):
        self.sf_cat = Category.objects.create(name="C", slug="c-rev")
        self.product = Product.objects.create(title="P", slug="p-rev", category=self.sf_cat, price=100)
        self.color = Color.objects.create(name="Black", primary_hex="#000")
        self.cat = StorageCategory.objects.create(name="C", slug="c-rev-wh", linked_storefront_category=self.sf_cat)
        self.sub = StorageSubcategory.objects.create(category=self.cat, name="Classic", is_default=True)
        self.stock = StockItem.objects.create(subcategory=self.sub, color=self.color, size="M", quantity=5)
        self.user = User.objects.create_user("revu", "r@e.com", "pw")
        self.order = Order.objects.create(user=self.user, full_name="X", phone="+380", city="C", np_office="O")

    def test_reverse_returns_stock_and_sets_cancelled(self):
        wo = WriteOffRequest.objects.create(order=self.order, status=WriteOffRequest.STATUS_COMPLETED)
        # Списання-продаж на 3 шт
        adjust_stock_item(stock_item=self.stock, delta=-3, user=self.user,
                          reason=MovementReason.ORDER_WRITE_OFF, order=self.order,
                          write_off_request=wo)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 2)

        count = reverse_write_off(write_off_request=wo, user=self.user)
        self.assertEqual(count, 1)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)  # повернено
        wo.refresh_from_db()
        self.assertEqual(wo.status, WriteOffRequest.STATUS_CANCELLED)

    def test_reverse_is_idempotent(self):
        wo = WriteOffRequest.objects.create(order=self.order, status=WriteOffRequest.STATUS_COMPLETED)
        adjust_stock_item(stock_item=self.stock, delta=-2, user=self.user,
                          reason=MovementReason.ORDER_WRITE_OFF, order=self.order,
                          write_off_request=wo)
        reverse_write_off(write_off_request=wo, user=self.user)
        self.stock.refresh_from_db()
        qty_after_first = self.stock.quantity
        # Повторний виклик нічого не змінює
        count2 = reverse_write_off(write_off_request=wo, user=self.user)
        self.assertEqual(count2, 0)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, qty_after_first)


class StorageButtonTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("btnu", "b@e.com", "pw")
        self.order = Order.objects.create(user=self.user, full_name="X", phone="+380", city="C", np_office="O")

    def test_button_is_sell_when_no_completed_sale(self):
        from orders.telegram_notifications import TelegramNotifier
        btn = TelegramNotifier()._build_storage_action_button(self.order)
        self.assertIsNotNone(btn)
        self.assertIn("продати", btn["text"].lower())

    def test_button_is_cancel_when_completed_sale(self):
        from orders.telegram_notifications import TelegramNotifier
        WriteOffRequest.objects.create(order=self.order, status=WriteOffRequest.STATUS_COMPLETED)
        btn = TelegramNotifier()._build_storage_action_button(self.order)
        self.assertIsNotNone(btn)
        self.assertIn("відмінити", btn["text"].lower())

    def test_done_order_keeps_storage_button(self):
        from orders.telegram_notifications import TelegramNotifier
        self.order.status = "done"
        self.order.save(update_fields=["status"])
        markup = TelegramNotifier()._build_order_management_reply_markup(self.order)
        self.assertIsNotNone(markup)
        # рівно одна складська кнопка
        rows = markup["inline_keyboard"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]), 1)
