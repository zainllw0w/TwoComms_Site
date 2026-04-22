import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from orders.models import DropshipperOrder
from orders.nova_poshta_checkout import build_city_choice_token, build_warehouse_choice_token
from storefront.models import Category, Product


class DropshipperNovaPoshtaTests(TestCase):
    def setUp(self):
        self.feed_task_patcher = patch('storefront.signals.generate_google_merchant_feed_task.apply_async')
        self.feed_task_patcher.start()
        self.addCleanup(self.feed_task_patcher.stop)

        self.telegram_notify_patcher = patch(
            'orders.telegram_notifications.telegram_notifier.send_dropshipper_order_notification'
        )
        self.telegram_notify_patcher.start()
        self.addCleanup(self.telegram_notify_patcher.stop)

        self.telegram_created_patcher = patch(
            'orders.telegram_notifications.telegram_notifier.send_dropshipper_order_created_notification'
        )
        self.telegram_created_patcher.start()
        self.addCleanup(self.telegram_created_patcher.stop)

        self.user = User.objects.create_user(
            username='dropship-np-user',
            email='dropship@example.com',
            password='testpass123',
        )
        self.client.login(username='dropship-np-user', password='testpass123')

        self.category = Category.objects.create(name='T-Shirts', slug='t-shirts')
        self.product = Product.objects.create(
            title='Test T-Shirt',
            slug='dropship-test-product',
            category=self.category,
            price=1000,
            recommended_price=1500,
        )

        self.add_to_cart_url = reverse('orders:add_to_cart')
        self.create_order_url = reverse('orders:create_dropshipper_order')

    def _delivery_payload(self):
        city_label = 'м. Київ, Київ'
        city_ref = 'delivery-city-ref'
        settlement_ref = 'settlement-ref'
        warehouse_label = 'Поштомат №22, Київ, вул. Тестова, 1'
        return {
            'client_city': 'довільний текст, який має бути проігнорований',
            'client_np_office': 'ще один довільний текст',
            'client_np_settlement_ref': 'spoofed-settlement-ref',
            'client_np_city_ref': 'spoofed-city-ref',
            'client_np_city_token': build_city_choice_token(
                {
                    'label': city_label,
                    'settlement_ref': settlement_ref,
                    'city_ref': city_ref,
                }
            ),
            'client_np_warehouse_ref': 'spoofed-warehouse-ref',
            'client_np_warehouse_token': build_warehouse_choice_token(
                {
                    'label': warehouse_label,
                    'ref': 'warehouse-ref',
                    'kind': 'postomat',
                    'city_ref': city_ref,
                }
            ),
            'canonical_city': city_label,
            'canonical_np_office': warehouse_label,
            'canonical_address': f'{city_label}, {warehouse_label}',
        }

    def _set_dropshipper_cart(self):
        session = self.client.session
        session['dropshipper_cart'] = [
            {
                'product_id': self.product.id,
                'quantity': 2,
                'size': 'M',
                'drop_price': 570,
                'selling_price': 900,
            }
        ]
        session.save()

    def test_add_to_cart_requires_signed_nova_poshta_selection(self):
        response = self.client.post(
            self.add_to_cart_url,
            data=json.dumps(
                {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'client_name': 'Test Client',
                    'client_phone': '0939693920',
                    'client_city': 'Київ',
                    'client_np_office': 'Відділення №1',
                    'payment_method': 'cod',
                }
            ),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            secure=True,
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['message'], 'Оберіть місто зі списку Нової пошти.')
        self.assertEqual(DropshipperOrder.objects.count(), 0)

    def test_add_to_cart_saves_canonical_client_address_and_refs(self):
        delivery = self._delivery_payload()

        response = self.client.post(
            self.add_to_cart_url,
            data=json.dumps(
                {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'size': 'M',
                    'selling_price': 900,
                    'client_name': 'Test Client',
                    'client_phone': '0939693920',
                    'payment_method': 'cod',
                    **delivery,
                }
            ),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        order = DropshipperOrder.objects.get()
        self.assertEqual(order.client_phone, '+380939693920')
        self.assertEqual(order.client_np_address, delivery['canonical_address'])
        self.assertEqual(order.client_np_settlement_ref, 'settlement-ref')
        self.assertEqual(order.client_np_city_ref, 'delivery-city-ref')
        self.assertEqual(order.client_np_warehouse_ref, 'warehouse-ref')

    def test_create_dropshipper_order_requires_signed_nova_poshta_selection(self):
        self._set_dropshipper_cart()

        response = self.client.post(
            self.create_order_url,
            data=json.dumps(
                {
                    'client_name': 'Test Client',
                    'client_phone': '0939693920',
                    'client_city': 'Київ',
                    'client_np_office': 'Відділення №1',
                    'payment_method': 'cod',
                }
            ),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            secure=True,
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['message'], 'Оберіть місто зі списку Нової пошти.')
        self.assertEqual(DropshipperOrder.objects.count(), 0)

    def test_create_dropshipper_order_saves_canonical_client_address_and_refs(self):
        self._set_dropshipper_cart()
        delivery = self._delivery_payload()

        response = self.client.post(
            self.create_order_url,
            data=json.dumps(
                {
                    'client_name': 'Test Client',
                    'client_phone': '80939693920',
                    'payment_method': 'cod',
                    **delivery,
                }
            ),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        order = DropshipperOrder.objects.get()
        self.assertEqual(order.client_phone, '+380939693920')
        self.assertEqual(order.client_np_address, delivery['canonical_address'])
        self.assertEqual(order.client_np_settlement_ref, 'settlement-ref')
        self.assertEqual(order.client_np_city_ref, 'delivery-city-ref')
        self.assertEqual(order.client_np_warehouse_ref, 'warehouse-ref')
