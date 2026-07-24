"""Тести ручного створення замовлень адміністратором."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from orders.models import Order, OrderItem
from orders.nova_poshta_checkout import build_city_choice_token, build_warehouse_choice_token
from fable5.models import (
    ColorProfile,
    ProductOptionSizeGrid,
    VariantFitRule,
    VariantSizeRule,
)
from productcolors.models import Color, ProductColorVariant
from storefront.models import (
    Catalog,
    Category,
    Product,
    ProductFitOption,
    ProductStatus,
    SizeGrid,
    UserAction,
)

User = get_user_model()


def _delivery_payload():
    """Будує валідні підписані токени НП (місто + відділення)."""
    city_item = {
        'label': 'Київ',
        'settlement_ref': 'settle-ref-1',
        'city_ref': 'city-ref-1',
    }
    wh_item = {
        'label': 'Відділення №1',
        'ref': 'wh-ref-1',
        'kind': 'branch',
        'city_ref': 'city-ref-1',
    }
    return {
        'city': 'Київ',
        'np_office': 'Відділення №1',
        'np_settlement_ref': 'settle-ref-1',
        'np_city_ref': 'city-ref-1',
        'np_city_token': build_city_choice_token(city_item),
        'np_warehouse_ref': 'wh-ref-1',
        'np_warehouse_token': build_warehouse_choice_token(wh_item, fallback_city_ref='city-ref-1'),
    }


class ManualOrderCreateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='admin', password='pass12345', is_staff=True,
        )
        cls.category = Category.objects.create(name='Футболки', slug='tshirts-mo')
        cls.product = Product.objects.create(
            title='Базова футболка',
            slug='basic-tee-mo',
            category=cls.category,
            price=900,
            status=ProductStatus.PUBLISHED,
        )
        cls.color = Color.objects.create(name='Чорний', primary_hex='#000000')
        cls.variant = ProductColorVariant.objects.create(
            product=cls.product, color=cls.color, is_default=True,
        )
        cls.classic_fit = ProductFitOption.objects.create(
            product=cls.product,
            code='classic',
            label='Класична',
            is_default=True,
            order=10,
        )
        cls.oversize_fit = ProductFitOption.objects.create(
            product=cls.product,
            code='oversize',
            label='Оверсайз',
            order=20,
        )
        cls.thermo_color = Color.objects.create(name='Термо-зелена', primary_hex='#29A36A')
        cls.thermo_variant = ProductColorVariant.objects.create(
            product=cls.product,
            color=cls.thermo_color,
            price_override=1200,
        )
        ColorProfile.objects.create(color=cls.thermo_color, is_thermo=True)
        VariantFitRule.objects.create(
            variant=cls.thermo_variant,
            fit_code='classic',
            is_enabled=False,
            reason='Термотканина доступна лише в оверсайз посадці',
        )
        VariantFitRule.objects.create(
            variant=cls.thermo_variant,
            fit_code='oversize',
            is_enabled=True,
        )
        cls.url = reverse('manual_order_create')

    def setUp(self):
        self.client.force_login(self.admin)

    def _post(self, payload):
        with mock.patch(
            'storefront.views.manual_orders.telegram_notifier.send_new_order_notification',
            return_value=True,
        ) as notify:
            response = self.client.post(
                self.url,
                data=json.dumps(payload),
                content_type='application/json',
            )
        return response, notify

    def test_get_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Створення замовлення вручну')

    def test_create_form_contains_fit_and_thermo_controls(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-edit="fit_option_code"')
        self.assertContains(response, 'Термотканина')
        self.assertContains(response, 'fit_option_code: it.fit_option_code')
        self.assertContains(response, 'normalizeCatalogItem(item, product, false, true)')
        self.assertContains(response, 'variant.sizes_by_fit')

    def test_product_payload_exposes_fit_and_thermo_variant_choices(self):
        VariantSizeRule.objects.create(
            variant=self.thermo_variant,
            fit_code='oversize',
            size='M',
            is_enabled=False,
        )
        VariantSizeRule.objects.create(
            variant=self.thermo_variant,
            fit_code='oversize',
            size='L',
            is_enabled=True,
            stock=0,
        )
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        products = json.loads(response.context['products_json'])
        product = next(item for item in products if item['id'] == self.product.id)
        self.assertEqual(
            [(item['code'], item['label']) for item in product['fits']],
            [('classic', 'Класична'), ('oversize', 'Оверсайз')],
        )
        self.assertEqual(product['default_fit_code'], 'classic')
        self.assertTrue(product['sizes_by_fit']['classic'])
        self.assertTrue(product['sizes_by_fit']['oversize'])

        normal = next(item for item in product['variants'] if item['id'] == self.variant.id)
        self.assertFalse(normal['is_thermo'])
        self.assertEqual(normal['available_fit_codes'], ['classic', 'oversize'])

        thermo = next(item for item in product['variants'] if item['id'] == self.thermo_variant.id)
        self.assertTrue(thermo['is_thermo'])
        self.assertEqual(thermo['available_fit_codes'], ['oversize'])
        self.assertEqual(thermo['prices_by_fit']['oversize'], 1200)
        self.assertIn('M', normal['sizes_by_fit']['oversize'])
        self.assertNotIn('M', thermo['sizes_by_fit']['oversize'])
        self.assertNotIn('L', thermo['sizes_by_fit']['oversize'])

    def test_product_payload_skips_fit_grid_work_for_products_without_fits(self):
        Product.objects.create(
            title='Худі без посадки',
            slug='hoodie-without-fit',
            category=self.category,
            price=1500,
            status=ProductStatus.PUBLISHED,
        )

        with mock.patch(
            'fable5.size_grid_services.build_size_grid_comparison',
            wraps=__import__(
                'fable5.size_grid_services',
                fromlist=['build_size_grid_comparison'],
            ).build_size_grid_comparison,
        ) as build_comparison:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(build_comparison.call_count, 1)

    def test_product_payload_has_bounded_queries_for_production_tshirt_shape(self):
        catalog = Catalog.objects.create(name='Футболки SQL', slug='tshirts-query-budget')
        grid_payload = {
            'columns': [{'key': 'size', 'label': 'Розмір'}],
            'rows': [{'size': size} for size in ('S', 'M', 'L', 'XL', 'XXL')],
        }
        classic_grid = SizeGrid.objects.create(
            catalog=catalog,
            name='Classic query grid',
            guide_data=grid_payload,
        )
        oversize_grid = SizeGrid.objects.create(
            catalog=catalog,
            name='Oversize query grid',
            guide_data=grid_payload,
        )

        products = [self.product]
        self.product.catalog = catalog
        self.product.save(update_fields=['catalog'])
        for index in range(30):
            product = Product.objects.create(
                title=f'Футболка SQL {index}',
                slug=f'tshirt-query-budget-{index}',
                category=self.category,
                catalog=catalog,
                price=900,
                status=ProductStatus.PUBLISHED,
            )
            ProductFitOption.objects.bulk_create([
                ProductFitOption(
                    product=product,
                    code='classic',
                    label='Класична',
                    is_default=True,
                    order=10,
                ),
                ProductFitOption(
                    product=product,
                    code='oversize',
                    label='Оверсайз',
                    order=20,
                ),
            ])
            ProductColorVariant.objects.create(
                product=product,
                color=self.color,
                is_default=True,
            )
            if index < 4:
                ProductColorVariant.objects.create(
                    product=product,
                    color=self.thermo_color,
                )
            products.append(product)

        ProductOptionSizeGrid.objects.bulk_create([
            ProductOptionSizeGrid(
                product=product,
                option_key=f'fit={fit_code}',
                size_grid=grid,
            )
            for product in products
            for fit_code, grid in (
                ('classic', classic_grid),
                ('oversize', oversize_grid),
            )
        ])

        from storefront.views.manual_orders import _build_products_payload

        with CaptureQueriesContext(connection) as queries:
            payload = _build_products_payload()

        self.assertEqual(len(payload), 31)
        self.assertLessEqual(len(queries), 120, len(queries))

    def test_create_catalog_order(self):
        payload = {
            'full_name': 'Іваненко Іван Іванович',
            'phone': '0501234567',
            'payment_preset': 'cod',
            'sale_source': 'Instagram',
            'manager_comment': 'Терміново',
            'items': [
                {
                    'kind': 'catalog',
                    'product_id': self.product.id,
                    'color_variant_id': self.variant.id,
                    'size': 'M',
                    'qty': 2,
                    'unit_price': 850,
                },
            ],
        }
        payload.update(_delivery_payload())
        response, notify = self._post(payload)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['success'], data)

        order = Order.objects.get(order_number=data['order_number'])
        self.assertEqual(order.source, 'manual')
        self.assertEqual(order.created_by, self.admin)
        self.assertEqual(order.sale_source, 'Instagram')
        self.assertEqual(order.manager_comment, 'Терміново')
        self.assertEqual(order.pay_type, 'cod')
        self.assertEqual(order.payment_status, 'unpaid')
        self.assertEqual(order.city, 'Київ')
        self.assertEqual(order.np_office, 'Відділення №1')
        self.assertEqual(order.np_warehouse_ref, 'wh-ref-1')
        self.assertEqual(order.total_sum, Decimal('1700.00'))

        item = order.items.get()
        self.assertEqual(item.product_id, self.product.id)
        self.assertEqual(item.qty, 2)
        self.assertEqual(item.unit_price, Decimal('850.00'))
        self.assertFalse(item.is_custom)
        notify.assert_called_once()

    def test_create_keeps_same_size_classic_and_oversize_as_separate_lines(self):
        payload = {
            'full_name': 'Іваненко Іван Іванович',
            'phone': '0501234567',
            'payment_preset': 'cod',
            'items': [
                {
                    'kind': 'catalog',
                    'product_id': self.product.id,
                    'color_variant_id': self.variant.id,
                    'fit_option_code': 'classic',
                    'size': 'S',
                    'qty': 1,
                    'unit_price': 900,
                },
                {
                    'kind': 'catalog',
                    'product_id': self.product.id,
                    'color_variant_id': self.variant.id,
                    'fit_option_code': 'oversize',
                    'size': 'S',
                    'qty': 1,
                    'unit_price': 900,
                },
            ],
        }
        payload.update(_delivery_payload())

        response, _ = self._post(payload)

        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(pk=response.json()['order_id'])
        self.assertEqual(
            list(order.items.order_by('id').values_list('fit_option_code', 'fit_option_label', 'size')),
            [('classic', 'Класична', 'S'), ('oversize', 'Оверсайз', 'S')],
        )

    def test_create_rejects_fit_disabled_for_selected_thermo_variant(self):
        payload = {
            'full_name': 'Іваненко Іван Іванович',
            'phone': '0501234567',
            'payment_preset': 'cod',
            'items': [
                {
                    'kind': 'catalog',
                    'product_id': self.product.id,
                    'color_variant_id': self.thermo_variant.id,
                    'fit_option_code': 'classic',
                    'size': 'M',
                    'qty': 1,
                    'unit_price': 1200,
                },
            ],
        }
        payload.update(_delivery_payload())

        response, _ = self._post(payload)

        self.assertEqual(response.status_code, 422, response.content)
        self.assertIn('недоступна', response.json()['message'])

    def test_create_defaults_missing_thermo_fit_to_oversize(self):
        payload = {
            'full_name': 'Іваненко Іван Іванович',
            'phone': '0501234567',
            'payment_preset': 'cod',
            'items': [
                {
                    'kind': 'catalog',
                    'product_id': self.product.id,
                    'color_variant_id': self.thermo_variant.id,
                    'size': 'M',
                    'qty': 1,
                    'unit_price': 1200,
                },
            ],
        }
        payload.update(_delivery_payload())

        response, _ = self._post(payload)

        self.assertEqual(response.status_code, 200, response.content)
        item = Order.objects.get(pk=response.json()['order_id']).items.get()
        self.assertEqual(item.fit_option_code, 'oversize')
        self.assertEqual(item.fit_option_label, 'Оверсайз')

    def test_create_rejects_size_disabled_for_selected_color_and_fit(self):
        VariantSizeRule.objects.create(
            variant=self.thermo_variant,
            fit_code='oversize',
            size='M',
            is_enabled=False,
        )
        payload = {
            'full_name': 'Іваненко Іван Іванович',
            'phone': '0501234567',
            'payment_preset': 'cod',
            'items': [
                {
                    'kind': 'catalog',
                    'product_id': self.product.id,
                    'color_variant_id': self.thermo_variant.id,
                    'fit_option_code': 'oversize',
                    'size': 'M',
                    'qty': 1,
                    'unit_price': 1200,
                },
            ],
        }
        payload.update(_delivery_payload())

        response, _ = self._post(payload)

        self.assertEqual(response.status_code, 422, response.content)
        self.assertIn('Розмір', response.json()['message'])

    def test_create_rejects_zero_stock_size_for_selected_color_and_fit(self):
        VariantSizeRule.objects.create(
            variant=self.thermo_variant,
            fit_code='oversize',
            size='M',
            is_enabled=True,
            stock=0,
        )
        payload = {
            'full_name': 'Іваненко Іван Іванович',
            'phone': '0501234567',
            'payment_preset': 'cod',
            'items': [
                {
                    'kind': 'catalog',
                    'product_id': self.product.id,
                    'color_variant_id': self.thermo_variant.id,
                    'fit_option_code': 'oversize',
                    'size': 'M',
                    'qty': 1,
                    'unit_price': 1200,
                },
            ],
        }
        payload.update(_delivery_payload())

        response, _ = self._post(payload)

        self.assertEqual(response.status_code, 422, response.content)
        self.assertIn('Розмір', response.json()['message'])

    def test_create_custom_item_order(self):
        payload = {
            'full_name': 'Петренко Петро',
            'phone': '+380671112233',
            'payment_preset': 'paid_full',
            'items': [
                {
                    'kind': 'custom',
                    'title': 'Термо-футболка XL',
                    'unit_price': 1200,
                    'qty': 1,
                    'size': 'XL',
                    'color_name': 'Сірий',
                },
            ],
        }
        payload.update(_delivery_payload())
        response, _ = self._post(payload)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['success'], data)

        order = Order.objects.get(order_number=data['order_number'])
        self.assertEqual(order.pay_type, 'online_full')
        self.assertEqual(order.payment_status, 'paid')
        item = order.items.get()
        self.assertIsNone(item.product_id)
        self.assertTrue(item.is_custom)
        self.assertEqual(item.title, 'Термо-футболка XL')
        self.assertEqual(item.color_name_custom, 'Сірий')
        self.assertEqual(item.color_name, 'Сірий')
        self.assertEqual(order.total_sum, Decimal('1200.00'))
        self.assertEqual(
            UserAction.objects.filter(action_type='purchase', order_id=order.pk).count(),
            1,
        )

    def test_free_manual_order_does_not_record_purchase(self):
        payload = {
            'full_name': 'Подарунок Клієнту',
            'phone': '+380671112233',
            'payment_preset': 'free',
            'items': [
                {
                    'kind': 'custom',
                    'title': 'Подарункова футболка',
                    'unit_price': 1200,
                    'qty': 1,
                },
            ],
        }
        payload.update(_delivery_payload())

        response, _ = self._post(payload)

        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(pk=response.json()['order_id'])
        self.assertEqual(order.payment_status, 'paid')
        self.assertFalse(
            UserAction.objects.filter(action_type='purchase', order_id=order.pk).exists()
        )

    def test_invalid_phone_rejected(self):
        payload = {
            'full_name': 'Хтось',
            'phone': '123',
            'items': [{'kind': 'custom', 'title': 'X', 'unit_price': 10, 'qty': 1}],
        }
        payload.update(_delivery_payload())
        response, _ = self._post(payload)
        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.json()['success'])

    def test_missing_delivery_rejected(self):
        payload = {
            'full_name': 'Хтось',
            'phone': '0501234567',
            'items': [{'kind': 'custom', 'title': 'X', 'unit_price': 10, 'qty': 1}],
        }
        response, _ = self._post(payload)
        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.json()['success'])

    def test_manual_delivery_without_np(self):
        payload = {
            'full_name': 'Сидоренко Сидір',
            'phone': '0631112233',
            'delivery_method': 'manual',
            'city': 'Львів',
            'np_office': 'Укрпошта, вул. Сихівська 5',
            'payment_preset': 'cod',
            'items': [
                {'kind': 'custom', 'title': 'Худі ручне', 'unit_price': 1500, 'qty': 1},
            ],
        }
        response, notify = self._post(payload)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['success'], data)
        order = Order.objects.get(order_number=data['order_number'])
        self.assertEqual(order.city, 'Львів')
        self.assertEqual(order.np_office, 'Укрпошта, вул. Сихівська 5')
        self.assertEqual(order.np_warehouse_ref, '')
        self.assertEqual(order.np_city_ref, '')
        notify.assert_called_once()

    def test_manual_delivery_requires_city_and_office(self):
        payload = {
            'full_name': 'Без адреси',
            'phone': '0501234567',
            'delivery_method': 'manual',
            'city': '',
            'np_office': '',
            'items': [{'kind': 'custom', 'title': 'X', 'unit_price': 10, 'qty': 1}],
        }
        response, _ = self._post(payload)
        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.json()['success'])

    def test_empty_items_rejected(self):
        payload = {'full_name': 'Хтось', 'phone': '0501234567', 'items': []}
        payload.update(_delivery_payload())
        response, _ = self._post(payload)
        self.assertEqual(response.status_code, 422)

    def test_non_staff_redirected(self):
        self.client.logout()
        user = User.objects.create_user(username='plain', password='pass12345')
        self.client.force_login(user)
        response = self.client.get(self.url)
        # staff_member_required перенаправляє не-адмінів на сторінку логіну адмінки
        self.assertIn(response.status_code, (302, 403))
