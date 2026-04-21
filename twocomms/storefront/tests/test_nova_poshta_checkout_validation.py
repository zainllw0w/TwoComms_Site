import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from orders.models import Order
from orders.nova_poshta_checkout import build_city_choice_token, build_warehouse_choice_token
from storefront.models import Category, Product


class NovaPoshtaCheckoutValidationTests(TestCase):
    def setUp(self):
        self.feed_task_patcher = patch('storefront.signals.generate_google_merchant_feed_task.apply_async')
        self.feed_task_patcher.start()
        self.addCleanup(self.feed_task_patcher.stop)

        self.cart_url = reverse('cart')
        self.order_create_url = reverse('order_create')
        self.monobank_create_invoice_url = reverse('monobank_create_invoice')

        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.product = Product.objects.create(
            title='Test Product',
            slug='test-product',
            category=self.category,
            price=100,
        )

        self.user = User.objects.create_user(
            username='np-user',
            email='np@example.com',
            password='testpass123',
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.phone = '+380991234567'
        self.profile.full_name = 'Stored User'
        self.profile.city = 'Старе місто'
        self.profile.np_office = 'Старе відділення'
        self.profile.pay_type = 'online_full'
        self.profile.save()

    def _set_cart(self):
        session = self.client.session
        session['cart'] = {
            'line-1': {
                'product_id': self.product.id,
                'qty': 2,
                'size': 'M',
            }
        }
        session.save()

    def _delivery_payload(self):
        city_label = 'м. Київ, Київ'
        city_ref = 'delivery-city-ref'
        settlement_ref = 'settlement-ref'
        warehouse_label = 'Відділення №22, Київ, вул. Тестова, 1'
        return {
            'city': 'довільний текст, який має бути проігнорований',
            'np_office': 'ще один довільний текст',
            'np_settlement_ref': 'spoofed-settlement-ref',
            'np_city_ref': 'spoofed-city-ref',
            'np_city_token': build_city_choice_token(
                {
                    'label': city_label,
                    'settlement_ref': settlement_ref,
                    'city_ref': city_ref,
                }
            ),
            'np_warehouse_ref': 'spoofed-warehouse-ref',
            'np_warehouse_token': build_warehouse_choice_token(
                {
                    'label': warehouse_label,
                    'ref': 'warehouse-ref',
                    'kind': 'branch',
                    'city_ref': city_ref,
                }
            ),
            'canonical_city': city_label,
            'canonical_np_office': warehouse_label,
        }

    def test_profile_update_requires_signed_nova_poshta_selection(self):
        self.client.login(username='np-user', password='testpass123')

        response = self.client.post(
            self.cart_url,
            {
                'form_type': 'update_profile',
                'full_name': 'Updated User',
                'phone': '+380661112233',
                'city': 'Київ',
                'np_office': 'Відділення №1',
                'pay_type': 'online_full',
            },
            secure=True,
            follow=True,
        )

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, 'Stored User')
        self.assertEqual(self.profile.city, 'Старе місто')
        self.assertEqual(self.profile.np_office, 'Старе відділення')
        messages = [message.message for message in response.context['messages']]
        self.assertIn('Оберіть місто зі списку Нової пошти.', messages)

    def test_profile_update_saves_canonical_nova_poshta_values(self):
        self.client.login(username='np-user', password='testpass123')
        delivery = self._delivery_payload()

        response = self.client.post(
            self.cart_url,
            {
                'form_type': 'update_profile',
                'full_name': 'Updated User',
                'phone': '+380661112233',
                'city': delivery['city'],
                'np_office': delivery['np_office'],
                'np_settlement_ref': delivery['np_settlement_ref'],
                'np_city_ref': delivery['np_city_ref'],
                'np_city_token': delivery['np_city_token'],
                'np_warehouse_ref': delivery['np_warehouse_ref'],
                'np_warehouse_token': delivery['np_warehouse_token'],
                'pay_type': 'online_full',
            },
            secure=True,
            follow=True,
        )

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, 'Updated User')
        self.assertEqual(self.profile.phone, '+380661112233')
        self.assertEqual(self.profile.city, delivery['canonical_city'])
        self.assertEqual(self.profile.np_office, delivery['canonical_np_office'])
        self.assertEqual(self.profile.np_settlement_ref, 'settlement-ref')
        self.assertEqual(self.profile.np_city_ref, 'delivery-city-ref')
        self.assertEqual(self.profile.np_warehouse_ref, 'warehouse-ref')
        messages = [message.message for message in response.context['messages']]
        self.assertIn('Дані доставки успішно оновлено!', messages)

    def test_order_create_requires_signed_nova_poshta_selection(self):
        self._set_cart()

        response = self.client.post(
            self.order_create_url,
            {
                'full_name': 'Guest User',
                'phone': '+380991234567',
                'city': 'Київ',
                'np_office': 'Відділення №1',
                'pay_type': 'cash',
            },
            secure=True,
            follow=True,
        )

        self.assertEqual(Order.objects.count(), 0)
        messages = [message.message for message in response.context['messages']]
        self.assertIn('Оберіть місто зі списку Нової пошти.', messages)

    def test_order_create_uses_signed_delivery_choice_instead_of_raw_text(self):
        self._set_cart()
        delivery = self._delivery_payload()

        response = self.client.post(
            self.order_create_url,
            {
                'full_name': 'Guest User',
                'phone': '+380991234567',
                'city': delivery['city'],
                'np_office': delivery['np_office'],
                'np_settlement_ref': delivery['np_settlement_ref'],
                'np_city_ref': delivery['np_city_ref'],
                'np_city_token': delivery['np_city_token'],
                'np_warehouse_ref': delivery['np_warehouse_ref'],
                'np_warehouse_token': delivery['np_warehouse_token'],
                'pay_type': 'cash',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.city, delivery['canonical_city'])
        self.assertEqual(order.np_office, delivery['canonical_np_office'])
        self.assertEqual(order.np_settlement_ref, 'settlement-ref')
        self.assertEqual(order.np_city_ref, 'delivery-city-ref')
        self.assertEqual(order.np_warehouse_ref, 'warehouse-ref')

    def test_monobank_create_invoice_rejects_unsigned_delivery_payload(self):
        self._set_cart()

        response = self.client.post(
            self.monobank_create_invoice_url,
            data=json.dumps(
                {
                    'full_name': 'Guest User',
                    'phone': '+380991234567',
                    'city': 'Київ',
                    'np_office': 'Відділення №1',
                    'pay_type': 'online_full',
                }
            ),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            secure=True,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                'success': False,
                'field': 'city',
                'error': 'Оберіть місто зі списку Нової пошти.',
            },
        )
