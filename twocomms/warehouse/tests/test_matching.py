"""Tests for matching service (OrderItem → StockItem)."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product
from orders.models import Order, OrderItem
from warehouse.models import (
    StockItem,
    StorageCategory,
    StorageSubcategory,
)
from warehouse.services.matching import (
    find_stock_items_for_order_item,
    stock_matrix_for_category,
)

User = get_user_model()


class MatchingTests(TestCase):
    def setUp(self):
        # storefront
        self.sf_cat = Category.objects.create(name="Футболки", slug="tshirts-sf")
        self.product = Product.objects.create(
            title="Tshirt Test",
            slug="tshirt-test",
            category=self.sf_cat,
            price=500,
        )
        self.color = Color.objects.create(name="Чорний", primary_hex="#000000")
        self.variant = ProductColorVariant.objects.create(
            product=self.product, color=self.color, is_default=True
        )

        # warehouse
        self.wh_cat = StorageCategory.objects.create(
            name="Футболки", slug="tshirts-wh",
            linked_storefront_category=self.sf_cat,
        )
        self.sub_classic = StorageSubcategory.objects.create(
            category=self.wh_cat, name="Класична", is_default=True,
        )
        self.sub_oversize = StorageSubcategory.objects.create(
            category=self.wh_cat, name="Оверсайз ERC",
        )

        # stock items
        StockItem.objects.create(
            subcategory=self.sub_classic, color=self.color, size="M", quantity=3,
        )
        StockItem.objects.create(
            subcategory=self.sub_oversize, color=self.color, size="M", quantity=2,
        )
        # different size — should not match
        StockItem.objects.create(
            subcategory=self.sub_classic, color=self.color, size="L", quantity=4,
        )

        self.user = User.objects.create_user("buyer", "b@example.com", "pw")
        self.order = Order.objects.create(
            user=self.user, full_name="X", phone="+380000", city="C", np_office="O",
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            color_variant=self.variant,
            title=self.product.title,
            size="M",
            qty=1,
            unit_price=Decimal("500"),
            line_total=Decimal("500"),
        )

    def test_finds_both_subcategories(self):
        results = find_stock_items_for_order_item(self.item)
        # Two M black items: classic + oversize
        self.assertEqual(len(results), 2)
        ids = {r.subcategory.name for r in results}
        self.assertEqual(ids, {"Класична", "Оверсайз ERC"})

    def test_filters_size(self):
        # change size to L
        self.item.size = "L"
        self.item.save()
        results = find_stock_items_for_order_item(self.item)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].size, "L")

    def test_no_match_if_no_link(self):
        # remove link
        self.wh_cat.linked_storefront_category = None
        self.wh_cat.save()
        results = find_stock_items_for_order_item(self.item)
        self.assertEqual(results, [])

    def test_stock_matrix(self):
        matrix = stock_matrix_for_category(self.wh_cat)
        # sizes sorted: M, L (L > M in custom order)
        self.assertIn("M", matrix["sizes"])
        self.assertIn("L", matrix["sizes"])
        # two subcategories present
        names = {s["name"] for s in matrix["subcategories"]}
        self.assertEqual(names, {"Класична", "Оверсайз ERC"})
        # total = 3 + 2 + 4 = 9
        self.assertEqual(matrix["total"], 9)
