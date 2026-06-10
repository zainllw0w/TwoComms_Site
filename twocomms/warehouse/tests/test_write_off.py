"""Tests for write-off flow (Telegram button → page → submit)."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product
from orders.models import Order, OrderItem
from warehouse.models import (
    StockItem,
    StorageCategory,
    StorageSubcategory,
    WriteOffRequest,
)
from warehouse.permissions import WAREHOUSE_GROUP_NAME
from warehouse.services.order_links import build_storage_writeoff_url

User = get_user_model()


@override_settings(ROOT_URLCONF="twocomms.urls_storage", SECURE_SSL_REDIRECT=False)
class WriteOffFlowTests(TestCase):
    def setUp(self):
        self.sf_cat = Category.objects.create(name="C", slug="c-wo")
        self.product = Product.objects.create(
            title="P", slug="p-wo", category=self.sf_cat, price=100,
        )
        self.color = Color.objects.create(name="Black", primary_hex="#000")
        self.variant = ProductColorVariant.objects.create(
            product=self.product, color=self.color, is_default=True,
        )

        self.wh_cat = StorageCategory.objects.create(
            name="C", slug="c-wo-wh", linked_storefront_category=self.sf_cat,
        )
        self.sub = StorageSubcategory.objects.create(
            category=self.wh_cat, name="Classic", is_default=True,
        )
        self.stock = StockItem.objects.create(
            subcategory=self.sub, color=self.color, size="M", quantity=5,
        )

        self.user = User.objects.create_user("admin_wo", "a@example.com", "pw")
        self.user.is_staff = True
        self.user.save()
        group, _ = Group.objects.get_or_create(name=WAREHOUSE_GROUP_NAME)
        self.user.groups.add(group)

        self.order = Order.objects.create(
            user=self.user, full_name="X", phone="+380000", city="C", np_office="O",
        )
        self.item = OrderItem.objects.create(
            order=self.order, product=self.product, color_variant=self.variant,
            title="P", size="M", qty=2,
            unit_price=Decimal("100"), line_total=Decimal("200"),
        )

    def test_build_storage_writeoff_url_creates_pending(self):
        url = build_storage_writeoff_url(self.order)
        self.assertIn("/order/", url)
        self.assertIn("/write-off/", url)
        self.assertEqual(self.order.warehouse_write_off_requests.count(), 1)
        wo = self.order.warehouse_write_off_requests.first()
        self.assertEqual(wo.status, WriteOffRequest.STATUS_PENDING)
        self.assertIn(str(wo.token), url)

    def test_reuses_pending(self):
        url1 = build_storage_writeoff_url(self.order)
        url2 = build_storage_writeoff_url(self.order)
        self.assertEqual(url1, url2)
        self.assertEqual(self.order.warehouse_write_off_requests.count(), 1)

    def test_write_off_page_renders(self):
        self.client.login(username="admin_wo", password="pw")
        wo = WriteOffRequest.objects.create(order=self.order)
        r = self.client.get(
            f"/order/{wo.token}/write-off/",
            HTTP_HOST="storage.twocomms.shop",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Classic", r.content)
        # candidate option should appear
        self.assertIn(b"option", r.content)

    def test_write_off_page_lists_all_stock_even_unmatched(self):
        """Навіть позиція з іншої категорії/розміру має бути у списку вибору."""
        # Окрема категорія без прив'язки до товару + розмір, який не співпадає.
        other_cat = StorageCategory.objects.create(name="Худі", slug="hoodie-wh")
        other_sub = StorageSubcategory.objects.create(
            category=other_cat, name="Оверсайз UNIQUE-SUB",
        )
        StockItem.objects.create(
            subcategory=other_sub, color=self.color, size="XXL", quantity=7,
        )
        self.client.login(username="admin_wo", password="pw")
        wo = WriteOffRequest.objects.create(order=self.order)
        r = self.client.get(
            f"/order/{wo.token}/write-off/",
            HTTP_HOST="storage.twocomms.shop",
        )
        self.assertEqual(r.status_code, 200)
        # Незважаючи на відсутність збігу, крій з'являється у селекті (optgroup).
        self.assertIn("Оверсайз UNIQUE-SUB".encode(), r.content)
        self.assertIn(b"optgroup", r.content)

    def test_write_off_submit_decrements_stock(self):
        self.client.login(username="admin_wo", password="pw")
        wo = WriteOffRequest.objects.create(order=self.order)
        prefix = f"item_{self.item.pk}_"
        r = self.client.post(
            f"/order/{wo.token}/write-off/submit/",
            data={
                prefix + "stock_id": self.stock.pk,
                prefix + "qty": 2,
                prefix + "print_variant_id": "",
            },
            HTTP_HOST="storage.twocomms.shop",
        )
        self.assertEqual(r.status_code, 302)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 3)
        wo.refresh_from_db()
        self.assertEqual(wo.status, WriteOffRequest.STATUS_COMPLETED)

    def test_invalid_token_returns_error_page(self):
        self.client.login(username="admin_wo", password="pw")
        r = self.client.get(
            "/order/00000000-0000-0000-0000-000000000000/write-off/",
            HTTP_HOST="storage.twocomms.shop",
        )
        self.assertEqual(r.status_code, 404)

    def test_writeoff_button_hidden_and_no_new_request_after_completion(self):
        """Після завершення списання кнопка зникає і НЕ створює новий pending."""
        from orders.telegram_notifications import TelegramNotifier

        wo = WriteOffRequest.objects.create(order=self.order)
        wo.status = WriteOffRequest.STATUS_COMPLETED
        wo.save(update_fields=["status"])

        notifier = TelegramNotifier()
        button = notifier._build_storage_writeoff_button(self.order)
        self.assertIsNone(button)
        # Жодного нового pending-запиту не створено.
        self.assertEqual(
            self.order.warehouse_write_off_requests.filter(
                status=WriteOffRequest.STATUS_PENDING
            ).count(),
            0,
        )

    def test_format_order_message_shows_writeoff_status(self):
        from orders.telegram_notifications import TelegramNotifier

        wo = WriteOffRequest.objects.create(order=self.order)
        wo.status = WriteOffRequest.STATUS_COMPLETED
        wo.save(update_fields=["status"])

        notifier = TelegramNotifier()
        block = notifier._build_writeoff_status(self.order)
        self.assertIn("Списано зі складу", block)

    def test_submit_rolls_back_all_on_error(self):
        """Якщо одна позиція з помилкою залишку — нічого не списується (atomic)."""
        self.client.login(username="admin_wo", password="pw")
        wo = WriteOffRequest.objects.create(order=self.order)
        prefix = f"item_{self.item.pk}_"
        r = self.client.post(
            f"/order/{wo.token}/write-off/submit/",
            data={
                prefix + "stock_id": self.stock.pk,
                prefix + "qty": 999,  # більше, ніж є на складі → ValueError
            },
            HTTP_HOST="storage.twocomms.shop",
        )
        self.assertEqual(r.status_code, 302)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)  # без змін
        wo.refresh_from_db()
        self.assertEqual(wo.status, WriteOffRequest.STATUS_PENDING)
