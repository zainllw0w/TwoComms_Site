"""View / URL tests for warehouse subdomain."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from warehouse.models import (
    MovementReason,
    StockItem,
    StorageCategory,
    StorageSubcategory,
)
from warehouse.permissions import WAREHOUSE_GROUP_NAME

User = get_user_model()


@override_settings(ROOT_URLCONF="twocomms.urls_storage")
class WarehouseAccessTests(TestCase):
    def setUp(self):
        self.cat = StorageCategory.objects.create(name="Cat", slug="cat-test")
        self.sub = StorageSubcategory.objects.create(category=self.cat, name="Sub")

    def test_root_redirects_to_login_for_anonymous(self):
        r = self.client.get("/", HTTP_HOST="storage.twocomms.shop")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_staff_without_group_gets_403(self):
        user = User.objects.create_user("staffonly", "s@example.com", "pw")
        user.is_staff = True
        user.save()
        self.client.login(username="staffonly", password="pw")
        r = self.client.get("/", HTTP_HOST="storage.twocomms.shop")
        # 403 from custom template
        self.assertEqual(r.status_code, 403)

    def test_admin_in_group_gets_dashboard(self):
        user = User.objects.create_user("admin1", "a@example.com", "pw")
        user.is_staff = True
        user.save()
        group, _ = Group.objects.get_or_create(name=WAREHOUSE_GROUP_NAME)
        user.groups.add(group)
        self.client.login(username="admin1", password="pw")
        r = self.client.get("/", HTTP_HOST="storage.twocomms.shop")
        self.assertEqual(r.status_code, 200)

    def test_superuser_bypasses_group(self):
        user = User.objects.create_superuser("super1", "s@example.com", "pw")
        self.client.login(username="super1", password="pw")
        r = self.client.get("/", HTTP_HOST="storage.twocomms.shop")
        self.assertEqual(r.status_code, 200)


@override_settings(ROOT_URLCONF="twocomms.urls_storage")
class WarehouseStockAdjustTests(TestCase):
    def setUp(self):
        self.cat = StorageCategory.objects.create(name="C", slug="c")
        self.sub = StorageSubcategory.objects.create(category=self.cat, name="S")
        self.user = User.objects.create_user("op", "o@example.com", "pw")
        self.user.is_staff = True
        self.user.save()
        group, _ = Group.objects.get_or_create(name=WAREHOUSE_GROUP_NAME)
        self.user.groups.add(group)
        self.client.login(username="op", password="pw")

    def test_create_via_delta(self):
        r = self.client.post(
            "/api/stock-adjust/",
            data={
                "subcategory_id": self.sub.id,
                "size": "M",
                "color_id": "",
                "mode": "delta",
                "delta": 5,
            },
            HTTP_HOST="storage.twocomms.shop",
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["quantity"], 5)
        item = StockItem.objects.get(subcategory=self.sub, size="M", color__isnull=True)
        self.assertEqual(item.quantity, 5)

    def test_negative_blocked(self):
        StockItem.objects.create(subcategory=self.sub, size="M", quantity=2)
        r = self.client.post(
            "/api/stock-adjust/",
            data={
                "subcategory_id": self.sub.id,
                "size": "M",
                "color_id": "",
                "mode": "delta",
                "delta": -10,
            },
            HTTP_HOST="storage.twocomms.shop",
        )
        self.assertEqual(r.status_code, 400)

    def test_set_quantity(self):
        StockItem.objects.create(subcategory=self.sub, size="L", quantity=3)
        r = self.client.post(
            "/api/stock-adjust/",
            data={
                "subcategory_id": self.sub.id,
                "size": "L",
                "color_id": "",
                "mode": "set",
                "quantity": 8,
            },
            HTTP_HOST="storage.twocomms.shop",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        item = StockItem.objects.get(subcategory=self.sub, size="L")
        self.assertEqual(item.quantity, 8)
