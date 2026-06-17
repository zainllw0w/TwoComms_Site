"""Тести для побудови diff при редагуванні замовлення.

Перевіряють чисту логіку ``orders.order_edit_diff``: знімок замовлення
(``snapshot_order``) та порівняння двох знімків (``build_order_edit_diff``).
Diff використовується для Telegram-сповіщення «замовлення відредаговано».
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from orders.models import Order, OrderItem
from orders.order_edit_diff import build_order_edit_diff, snapshot_order
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductStatus

User = get_user_model()


class OrderEditDiffTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Футболки', slug='tshirts-diff')
        cls.product = Product.objects.create(
            title='Футболка Reality Bends',
            slug='reality-bends-diff',
            category=cls.category,
            price=880,
            status=ProductStatus.PUBLISHED,
        )
        cls.mint = Color.objects.create(name='Ментол', primary_hex='#9FE2BF')
        cls.black = Color.objects.create(name='Чорний', primary_hex='#000000')
        cls.variant_mint = ProductColorVariant.objects.create(
            product=cls.product, color=cls.mint, is_default=True,
        )
        cls.variant_black = ProductColorVariant.objects.create(
            product=cls.product, color=cls.black,
        )

    def _make_order(self):
        return Order.objects.create(
            full_name='Лагош Олег', phone='+380500234363',
            city='Харків', np_office='Відділення №4',
            pay_type='online_full', payment_status='paid',
            total_sum=Decimal('880.00'),
        )

    def _add_item(self, order, **kwargs):
        defaults = dict(
            title=self.product.title, qty=1,
            unit_price=Decimal('880.00'), line_total=Decimal('880.00'),
        )
        defaults.update(kwargs)
        return OrderItem.objects.create(order=order, **defaults)

    def test_snapshot_captures_items_and_total(self):
        order = self._make_order()
        self._add_item(order, product=self.product, color_variant=self.variant_mint, size='XXL')
        snap = snapshot_order(order)
        self.assertEqual(snap['total'], Decimal('880.00'))
        self.assertEqual(len(snap['items']), 1)
        self.assertEqual(snap['items'][0]['qty'], 1)
        self.assertIn('XXL', snap['items'][0]['label'])

    def test_diff_no_changes(self):
        order = self._make_order()
        self._add_item(order, product=self.product, color_variant=self.variant_mint, size='XXL')
        before = snapshot_order(order)
        after = snapshot_order(order)
        diff = build_order_edit_diff(before, after)
        self.assertFalse(diff['has_changes'])
        self.assertEqual(diff['items']['added'], [])
        self.assertEqual(diff['items']['removed'], [])
        self.assertEqual(diff['items']['changed'], [])

    def test_diff_color_swap_is_remove_and_add(self):
        order = self._make_order()
        item = self._add_item(order, product=self.product, color_variant=self.variant_mint, size='XXL')
        before = snapshot_order(order)
        # Замінюємо ментол на чорний (як на скріншоті користувача).
        item.color_variant = self.variant_black
        item.save(update_fields=['color_variant'])
        after = snapshot_order(order)
        diff = build_order_edit_diff(before, after)
        self.assertTrue(diff['has_changes'])
        self.assertEqual(len(diff['items']['removed']), 1)
        self.assertEqual(len(diff['items']['added']), 1)
        self.assertIn('Ментол', diff['items']['removed'][0]['label'])
        self.assertIn('Чорний', diff['items']['added'][0]['label'])

    def test_diff_qty_change(self):
        order = self._make_order()
        item = self._add_item(order, product=self.product, color_variant=self.variant_mint, size='M', qty=1)
        before = snapshot_order(order)
        item.qty = 3
        item.save(update_fields=['qty'])
        after = snapshot_order(order)
        diff = build_order_edit_diff(before, after)
        self.assertTrue(diff['has_changes'])
        self.assertEqual(len(diff['items']['changed']), 1)
        changed = diff['items']['changed'][0]
        self.assertEqual(changed['old_qty'], 1)
        self.assertEqual(changed['new_qty'], 3)

    def test_diff_price_change(self):
        order = self._make_order()
        item = self._add_item(order, product=self.product, color_variant=self.variant_mint, size='M')
        before = snapshot_order(order)
        item.unit_price = Decimal('990.00')
        item.save(update_fields=['unit_price'])
        after = snapshot_order(order)
        diff = build_order_edit_diff(before, after)
        self.assertTrue(diff['has_changes'])
        self.assertEqual(len(diff['items']['changed']), 1)
        changed = diff['items']['changed'][0]
        self.assertEqual(changed['old_price'], Decimal('880.00'))
        self.assertEqual(changed['new_price'], Decimal('990.00'))

    def test_diff_total_change(self):
        order = self._make_order()
        self._add_item(order, product=self.product, color_variant=self.variant_mint, size='M')
        before = snapshot_order(order)
        order.total_sum = Decimal('760.00')
        after = snapshot_order(order)
        diff = build_order_edit_diff(before, after)
        self.assertIsNotNone(diff['total'])
        self.assertEqual(diff['total']['old'], Decimal('880.00'))
        self.assertEqual(diff['total']['new'], Decimal('760.00'))
        self.assertEqual(diff['total']['delta'], Decimal('-120.00'))

    def test_diff_delivery_change(self):
        order = self._make_order()
        self._add_item(order, product=self.product, color_variant=self.variant_mint, size='M')
        before = snapshot_order(order)
        order.city = 'Київ'
        order.np_office = 'Відділення №1'
        after = snapshot_order(order)
        diff = build_order_edit_diff(before, after)
        self.assertIsNotNone(diff['delivery'])
        self.assertIn('Харків', diff['delivery']['old'])
        self.assertIn('Київ', diff['delivery']['new'])

    def test_diff_custom_item_added(self):
        order = self._make_order()
        self._add_item(order, product=self.product, color_variant=self.variant_mint, size='M')
        before = snapshot_order(order)
        self._add_item(
            order, product=None, color_variant=None, is_custom=True,
            title='Термо-футболка', color_name_custom='Хакі', size='L',
            unit_price=Decimal('500.00'), line_total=Decimal('500.00'),
        )
        after = snapshot_order(order)
        diff = build_order_edit_diff(before, after)
        self.assertEqual(len(diff['items']['added']), 1)
        self.assertIn('Термо-футболка', diff['items']['added'][0]['label'])
