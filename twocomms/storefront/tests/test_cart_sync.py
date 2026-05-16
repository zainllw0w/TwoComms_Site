"""
Tests for cross-device cart synchronization (UserCart + CartSyncMiddleware).

Покрываем три ключевых сценария:
* анонимная сессионная корзина переносится в БД при логине;
* при следующем заходе пользователя (даже с другого устройства/новой сессии)
  корзина подтягивается из БД обратно в сессию;
* изменение корзины в одной сессии сохраняется в БД и видно из другой сессии.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.cart_models import UserCart
from accounts.cart_sync import (
    hydrate_session_from_db,
    merge_session_into_db,
    persist_session_to_db,
)
from storefront.custom_print_config import SESSION_CUSTOM_CART_KEY
from storefront.models import Category, Product


def _build_request(user, session_data=None):
    """Простейший fake request, хватает для unit-теста sync-функций."""

    class _Session(dict):
        def __init__(self, data=None):
            super().__init__(data or {})
            self.modified = False

    request = type('Req', (), {})()
    request.user = user
    request.session = _Session(session_data or {})
    return request


class CartSyncUnitTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='cart-sync-user', password='StrongPass!123', email='c@example.com'
        )
        category = Category.objects.create(name='Sync Cat', slug='sync-cat')
        self.product = Product.objects.create(
            title='Sync Tee',
            slug='sync-tee',
            category=category,
            price=100,
            status='published',
        )

    def _cart_key(self, size='M', fit=''):
        key = f'{self.product.id}:{size}:default'
        if fit:
            key = f'{key}:{fit}'
        return key

    def test_persist_writes_cart_into_db(self):
        request = _build_request(
            self.user,
            {
                'cart': {
                    self._cart_key(): {
                        'product_id': self.product.id,
                        'qty': 2,
                        'size': 'M',
                        'color_variant_id': None,
                        'fit_option_code': '',
                        'fit_option_label': '',
                    }
                }
            },
        )
        persist_session_to_db(request)
        cart = UserCart.objects.get(user=self.user)
        self.assertEqual(list(cart.cart_data.keys()), [self._cart_key()])
        self.assertEqual(cart.cart_data[self._cart_key()]['qty'], 2)

    def test_hydrate_loads_cart_from_db_into_empty_session(self):
        UserCart.objects.create(
            user=self.user,
            cart_data={
                self._cart_key(): {
                    'product_id': self.product.id,
                    'qty': 3,
                    'size': 'M',
                    'color_variant_id': None,
                }
            },
            promo_code_id=42,
        )
        request = _build_request(self.user)
        hydrate_session_from_db(request)
        self.assertIn('cart', request.session)
        self.assertEqual(request.session['cart'][self._cart_key()]['qty'], 3)
        self.assertEqual(request.session['promo_code_id'], 42)

    def test_merge_on_login_combines_session_and_db_quantities(self):
        UserCart.objects.create(
            user=self.user,
            cart_data={
                self._cart_key(): {
                    'product_id': self.product.id,
                    'qty': 1,
                    'size': 'M',
                    'color_variant_id': None,
                }
            },
        )
        request = _build_request(
            self.user,
            {
                'cart': {
                    self._cart_key(): {
                        'product_id': self.product.id,
                        'qty': 4,
                        'size': 'M',
                        'color_variant_id': None,
                    },
                    self._cart_key(size='L'): {
                        'product_id': self.product.id,
                        'qty': 2,
                        'size': 'L',
                        'color_variant_id': None,
                    },
                }
            },
        )
        merge_session_into_db(request, self.user)
        cart = UserCart.objects.get(user=self.user)
        # Стандартный ключ: 1 (DB) + 4 (session) = 5
        self.assertEqual(cart.cart_data[self._cart_key()]['qty'], 5)
        # Новая позиция должна оказаться в обеих структурах
        self.assertEqual(cart.cart_data[self._cart_key(size='L')]['qty'], 2)
        self.assertEqual(request.session['cart'][self._cart_key(size='L')]['qty'], 2)

    def test_merge_custom_cart_keeps_unique_entries(self):
        UserCart.objects.create(
            user=self.user,
            custom_cart_data={
                'custom:1': {'lead_id': 1, 'quantity': 1, 'final_total': '100'},
            },
        )
        request = _build_request(
            self.user,
            {
                SESSION_CUSTOM_CART_KEY: {
                    'custom:2': {'lead_id': 2, 'quantity': 3, 'final_total': '300'},
                }
            },
        )
        merge_session_into_db(request, self.user)
        cart = UserCart.objects.get(user=self.user)
        self.assertEqual(set(cart.custom_cart_data.keys()), {'custom:1', 'custom:2'})


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    LANGUAGE_CODE='uk',
    USE_I18N=False,
    SECURE_SSL_REDIRECT=False,
)
class CartSyncCrossSessionIntegrationTests(TestCase):
    """
    Имитируем кросс-девайсный сценарий: добавляем товар через middleware-цепочку
    одного клиента и проверяем, что данные доступны из независимой сессии другого
    клиента (другого устройства того же пользователя).
    """

    def setUp(self):
        super().setUp()
        self.password = 'StrongPass!123'
        self.user = User.objects.create_user(
            username='dual-device', email='d@example.com', password=self.password
        )
        category = Category.objects.create(name='Dual Cat', slug='dual-cat')
        self.product = Product.objects.create(
            title='Dual Tee',
            slug='dual-tee',
            category=category,
            price=150,
            status='published',
        )

    def _cart_key(self, size='M'):
        return f'{self.product.id}:{size}:default'

    def test_cart_added_on_one_device_is_visible_on_another(self):
        # Device 1: эмулируем добавление товара в сессию + persist в БД через signals/middleware.
        # Прямо через login() гарантируем, что user_logged_in сработал.
        from django.test import RequestFactory
        from django.contrib.auth import login

        factory = RequestFactory()

        # Шаг 1. Logged-in пользователь добавляет товар в сессионный cart.
        request1 = factory.post('/uk/cart/add/')
        request1.session = self.client.session
        request1.user = self.user
        request1.session['cart'] = {
            self._cart_key(): {
                'product_id': self.product.id,
                'qty': 2,
                'size': 'M',
                'color_variant_id': None,
            }
        }
        request1.session.modified = True
        # Эмулируем CartSyncMiddleware.process_response.
        from accounts.cart_middleware import CartSyncMiddleware

        middleware = CartSyncMiddleware(get_response=lambda r: None)
        request1.path = '/uk/cart/add/'
        from django.http import HttpResponse

        middleware.process_response(request1, HttpResponse(status=200))

        cart = UserCart.objects.get(user=self.user)
        self.assertEqual(cart.cart_data[self._cart_key()]['qty'], 2)

        # Шаг 2. Новое устройство = новая сессия. Эмулируем CartSyncMiddleware.process_request.
        request2 = factory.get('/uk/')
        from importlib import import_module
        engine = import_module('django.contrib.sessions.backends.db')
        request2.session = engine.SessionStore()
        request2.user = self.user
        request2.path = '/uk/'
        middleware.process_request(request2)

        # Корзина с device 1 должна быть видна device 2.
        self.assertIn('cart', request2.session)
        self.assertEqual(request2.session['cart'][self._cart_key()]['qty'], 2)
