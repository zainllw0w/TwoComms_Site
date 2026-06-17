"""Тести view редагування замовлення в кастомній адмінці.

Покривають: JSON-ендпоінт даних для drawer (``manual_order_edit_data``)
та відправку diff-сповіщення в Telegram при збереженні змін.
"""
from __future__ import annotations

import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from orders.models import Order, OrderItem
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductStatus

User = get_user_model()


class OrderEditViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin-edit', password='pass12345', is_staff=True)
        cls.category = Category.objects.create(name='Футболки', slug='tshirts-edit')
        cls.product = Product.objects.create(
            title='Футболка Reality Bends', slug='reality-bends-edit',
            category=cls.category, price=880, status=ProductStatus.PUBLISHED,
        )
        cls.mint = Color.objects.create(name='Ментол', primary_hex='#9FE2BF')
        cls.black = Color.objects.create(name='Чорний', primary_hex='#000000')
        cls.variant_mint = ProductColorVariant.objects.create(
            product=cls.product, color=cls.mint, is_default=True)
        cls.variant_black = ProductColorVariant.objects.create(
            product=cls.product, color=cls.black)

    def setUp(self):
        self.client.force_login(self.admin)
        self.order = Order.objects.create(
            full_name='Лагош Олег', phone='+380500234363',
            city='Харків', np_office='Відділення №4',
            pay_type='online_full', payment_status='paid',
            total_sum=Decimal('880.00'), source='web',
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, color_variant=self.variant_mint,
            title=self.product.title, size='XXL', qty=1,
            unit_price=Decimal('880.00'), line_total=Decimal('880.00'),
        )

    def test_edit_data_endpoint_returns_order_and_catalog(self):
        url = reverse('manual_order_edit_data', args=[self.order.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['order']['id'], self.order.id)
        self.assertEqual(len(data['order']['items']), 1)
        self.assertTrue(any(p['id'] == self.product.id for p in data['products']))

    def test_edit_data_endpoint_requires_staff(self):
        self.client.logout()
        plain = User.objects.create_user(username='plain-edit', password='pass12345')
        self.client.force_login(plain)
        url = reverse('manual_order_edit_data', args=[self.order.id])
        response = self.client.get(url)
        self.assertIn(response.status_code, (302, 403))

    def _edit(self, payload):
        url = reverse('manual_order_edit', args=[self.order.id])
        with mock.patch(
            'storefront.views.manual_orders.telegram_notifier.update_order_notification_message',
            return_value=True,
        ), mock.patch(
            'storefront.views.manual_orders.telegram_notifier.send_order_edit_notification',
            return_value=True,
        ) as edit_notify:
            response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        return response, edit_notify

    def test_edit_swap_color_sends_diff_notification(self):
        payload = {
            'full_name': 'Лагош Олег',
            'phone': '+380500234363',
            'delivery_method': 'keep',
            'payment_preset': 'paid_full',
            'items': [
                {
                    'kind': 'catalog',
                    'product_id': self.product.id,
                    'color_variant_id': self.variant_black.id,
                    'size': 'XXL',
                    'qty': 1,
                    'unit_price': 880,
                },
            ],
        }
        response, edit_notify = self._edit(payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['success'])

        # Позиція в БД оновлена на чорний варіант.
        item = self.order.items.get()
        self.assertEqual(item.color_variant_id, self.variant_black.id)

        # Сповіщення про редагування відправлено з diff, що містить зміни.
        edit_notify.assert_called_once()
        _, kwargs = edit_notify.call_args
        diff = edit_notify.call_args.args[1]
        self.assertTrue(diff['has_changes'])

    def test_edit_without_changes_skips_diff_notification_payload(self):
        # Зберігаємо без жодних змін — diff не повинен містити змін.
        payload = {
            'full_name': 'Лагош Олег',
            'phone': '+380500234363',
            'delivery_method': 'keep',
            'payment_preset': 'paid_full',
            'items': [
                {
                    'kind': 'catalog',
                    'product_id': self.product.id,
                    'color_variant_id': self.variant_mint.id,
                    'size': 'XXL',
                    'qty': 1,
                    'unit_price': 880,
                },
            ],
        }
        response, edit_notify = self._edit(payload)
        self.assertEqual(response.status_code, 200, response.content)
        diff = edit_notify.call_args.args[1]
        self.assertFalse(diff['has_changes'])


class OrderEditButtonRenderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin-render', password='pass12345', is_staff=True)
        cls.category = Category.objects.create(name='Футболки', slug='tshirts-render')
        cls.product = Product.objects.create(
            title='Футболка', slug='tee-render', category=cls.category,
            price=880, status=ProductStatus.PUBLISHED,
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.order = Order.objects.create(
            full_name='Клієнт Тест', phone='+380501112233',
            city='Київ', np_office='Відділення №1',
            pay_type='cod', payment_status='unpaid', total_sum=Decimal('880.00'),
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, title='Футболка',
            qty=1, unit_price=Decimal('880.00'), line_total=Decimal('880.00'),
        )

    def test_orders_section_renders_edit_button_and_drawer(self):
        response = self.client.get(reverse('admin_panel') + '?section=orders')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Редагувати замовлення')
        self.assertContains(response, 'oeditDrawer')
        self.assertContains(response, 'data-edit-order="%d"' % self.order.id)
