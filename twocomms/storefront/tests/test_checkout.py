"""
Checkout-adjacent tests for the current storefront contract.

Covers:
- order_create
- order_success
- confirm_payment
- cart/promo endpoints used by the checkout flow
"""

from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse

from orders.models import Order, OrderItem
from storefront.models import Category, Product, PromoCode


class CheckoutTestSupport(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category',
        )
        self.product = Product.objects.create(
            title='Test Product',
            slug='test-product',
            category=self.category,
            price=130,
            status='published',
        )

        self.order_create_url = reverse('order_create')
        self.order_success_url_name = 'order_success'
        self.confirm_payment_url = reverse('confirm_payment')
        self.cart_summary_url = reverse('cart_summary')
        self.apply_promo_url = reverse('apply_promo_code')
        self.remove_promo_url = reverse('remove_promo_code')

    def set_cart(self, *, product=None, qty=2, size='M'):
        product = product or self.product
        session = self.client.session
        session['cart'] = {
            f'{product.id}:{size}': {
                'product_id': product.id,
                'qty': qty,
                'size': size,
            }
        }
        session.save()

    def make_user(self, *, username='buyer', pay_type='full'):
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='testpass123',
        )
        profile = user.userprofile
        profile.full_name = 'Profile Buyer'
        profile.phone = '+380991234567'
        profile.city = 'Київ'
        profile.np_office = 'Відділення №1'
        profile.pay_type = pay_type
        profile.save()
        return user

    def make_fake_order_item_class(self):
        manager = Mock()

        class FakeOrderItem:
            objects = manager

            def __init__(self, **kwargs):
                self.order = kwargs['order']
                self.product = kwargs['product']
                self.color_variant = kwargs.get('color_variant')
                self.size = kwargs.get('size', '')
                self.qty = kwargs.get('qty', kwargs.get('quantity'))
                self.unit_price = kwargs.get('unit_price', kwargs.get('price'))
                self.line_total = kwargs.get('line_total', self.qty * self.unit_price)
                self.raw_kwargs = kwargs

        return FakeOrderItem, manager


class CreateOrderTests(CheckoutTestSupport):
    def test_create_order_guest_cod_creates_order_and_clears_cart(self):
        self.set_cart()
        fake_order_item_class, fake_manager = self.make_fake_order_item_class()

        with patch('storefront.views.checkout.OrderItem', fake_order_item_class):
            response = self.client.post(
                self.order_create_url,
                {
                    'full_name': 'Guest Buyer',
                    'phone': '+380501112233',
                    'city': 'Львів',
                    'np_office': 'Відділення №5',
                    'pay_type': 'cod',
                },
            )

        order = Order.objects.get()
        self.assertRedirects(
            response,
            reverse(self.order_success_url_name, kwargs={'order_id': order.id}),
            fetch_redirect_response=False,
        )
        self.assertIsNone(order.user)
        self.assertEqual(order.full_name, 'Guest Buyer')
        self.assertEqual(order.phone, '+380501112233')
        self.assertEqual(order.city, 'Львів')
        self.assertEqual(order.np_office, 'Відділення №5')
        self.assertEqual(order.pay_type, 'cod')
        self.assertEqual(order.total_sum, Decimal('260'))
        self.assertEqual(self.client.session.get('cart'), {})

        bulk_items = fake_manager.bulk_create.call_args.args[0]
        self.assertEqual(len(bulk_items), 1)
        self.assertEqual(bulk_items[0].product, self.product)
        self.assertEqual(bulk_items[0].qty, 2)
        self.assertEqual(bulk_items[0].unit_price, self.product.final_price)
        self.assertEqual(bulk_items[0].line_total, self.product.final_price * 2)

    def test_create_order_authenticated_uses_profile_data(self):
        self.set_cart()
        user = self.make_user(pay_type='full')
        self.client.force_login(user)
        fake_order_item_class, _ = self.make_fake_order_item_class()

        with patch('storefront.views.checkout.OrderItem', fake_order_item_class):
            response = self.client.post(
                self.order_create_url,
                {
                    'full_name': 'Posted Name',
                    'phone': '+380000000000',
                    'city': 'Одеса',
                    'np_office': 'Відділення №99',
                    'pay_type': 'cod',
                },
            )

        order = Order.objects.get(user=user)
        self.assertRedirects(
            response,
            reverse(self.order_success_url_name, kwargs={'order_id': order.id}),
            fetch_redirect_response=False,
        )
        self.assertEqual(order.full_name, 'Profile Buyer')
        self.assertEqual(order.phone, '+380991234567')
        self.assertEqual(order.city, 'Київ')
        self.assertEqual(order.np_office, 'Відділення №1')
        self.assertEqual(order.pay_type, 'full')

    def test_create_order_guest_online_full_calls_monobank(self):
        self.set_cart()
        fake_order_item_class, _ = self.make_fake_order_item_class()

        with patch('storefront.views.checkout.OrderItem', fake_order_item_class), patch(
            'storefront.views.checkout.monobank_create_invoice',
            return_value=HttpResponseRedirect('/mock-monobank-checkout/'),
        ) as monobank_create_invoice:
            response = self.client.post(
                self.order_create_url,
                {
                    'full_name': 'Card Buyer',
                    'phone': '+380671112233',
                    'city': 'Київ',
                    'np_office': 'Відділення №7',
                    'pay_type': 'online_full',
                },
            )

        order = Order.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/mock-monobank-checkout/')
        self.assertEqual(monobank_create_invoice.call_args.args[1], order.id)
        self.assertEqual(order.pay_type, 'online_full')

    def test_create_order_empty_cart_redirects_to_cart(self):
        response = self.client.post(
            self.order_create_url,
            {
                'full_name': 'Empty Cart Buyer',
                'phone': '+380501112233',
                'city': 'Київ',
                'np_office': 'Відділення №1',
                'pay_type': 'cod',
            },
        )

        self.assertRedirects(response, reverse('cart'), fetch_redirect_response=False)
        self.assertFalse(Order.objects.exists())

    def test_create_order_ignores_cart_promo_session_keys(self):
        self.set_cart()
        promo = PromoCode.objects.create(
            code='TEST10',
            discount_type='percentage',
            discount_value=Decimal('10.00'),
            is_active=True,
        )
        session = self.client.session
        session['promo_code_id'] = promo.id
        session['promo_code_data'] = {
            'code': promo.code,
            'discount': 26.0,
        }
        session.save()

        fake_order_item_class, _ = self.make_fake_order_item_class()
        with patch('storefront.views.checkout.OrderItem', fake_order_item_class):
            response = self.client.post(
                self.order_create_url,
                {
                    'full_name': 'Promo Buyer',
                    'phone': '+380501112233',
                    'city': 'Харків',
                    'np_office': 'Відділення №3',
                    'pay_type': 'cod',
                },
            )

        order = Order.objects.get()
        self.assertRedirects(
            response,
            reverse(self.order_success_url_name, kwargs={'order_id': order.id}),
            fetch_redirect_response=False,
        )
        self.assertIsNone(order.promo_code)
        self.assertEqual(order.discount_amount, Decimal('0'))
        self.assertNotIn('promo_code_id', self.client.session)
        self.assertNotIn('promo_code_data', self.client.session)


class OrderSuccessTests(CheckoutTestSupport):
    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            full_name='Success Buyer',
            phone='+380991112233',
            email='buyer@example.com',
            city='Київ',
            np_office='Відділення №4',
            pay_type='cod',
            payment_status='paid',
            total_sum=Decimal('260.00'),
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            title=self.product.title,
            size='M',
            qty=2,
            unit_price=Decimal('130.00'),
            line_total=Decimal('260.00'),
        )
        self.success_url = reverse(self.order_success_url_name, kwargs={'order_id': self.order.id})

    def test_order_success_renders_order_details(self):
        response = self.client.get(self.success_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['order'].pk, self.order.pk)
        self.assertContains(response, self.order.order_number)
        self.assertContains(response, self.order.full_name)
        self.assertContains(response, self.product.title)
        self.assertEqual(response.context['order'].total_sum, self.order.total_sum)

    def test_order_success_returns_404_for_unknown_order(self):
        response = self.client.get(
            reverse(self.order_success_url_name, kwargs={'order_id': self.order.id + 999})
        )

        self.assertEqual(response.status_code, 404)


class ConfirmPaymentTests(CheckoutTestSupport):
    def test_confirm_payment_redirects_to_my_orders(self):
        response = self.client.get(self.confirm_payment_url)

        self.assertRedirects(response, reverse('my_orders'), fetch_redirect_response=False)

    def test_confirm_payment_follow_redirect_for_authenticated_user(self):
        user = self.make_user(username='history-user')
        self.client.force_login(user)

        response = self.client.get(self.confirm_payment_url, follow=True)

        self.assertRedirects(response, reverse('my_orders'))
        self.assertContains(response, 'Мої замовлення')


class PromoAndCartTests(CheckoutTestSupport):
    def test_cart_summary_uses_current_cart_session_shape(self):
        discounted_product = Product.objects.create(
            title='Discounted Product',
            slug='discounted-product',
            category=self.category,
            price=130,
            discount_percent=10,
            status='published',
        )
        self.set_cart(product=discounted_product)

        response = self.client.get(self.cart_summary_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 2)
        self.assertEqual(response.json()['total'], 234.0)

    def test_apply_promo_code_requires_authenticated_user(self):
        self.set_cart()
        promo = PromoCode.objects.create(
            code='LOGIN10',
            discount_type='percentage',
            discount_value=Decimal('10.00'),
            is_active=True,
        )

        response = self.client.post(self.apply_promo_url, {'promo_code': promo.code})

        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()['auth_required'])
        self.assertNotIn('promo_code_id', self.client.session)

    def test_apply_promo_code_stores_session_data_for_authenticated_user(self):
        self.set_cart()
        user = self.make_user(username='promo-user')
        self.client.force_login(user)
        promo = PromoCode.objects.create(
            code='SAVE10',
            discount_type='percentage',
            discount_value=Decimal('10.00'),
            is_active=True,
        )

        response = self.client.post(self.apply_promo_url, {'promo_code': 'save10'})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['promo_code'], 'SAVE10')
        self.assertEqual(data['discount'], 26.0)
        self.assertEqual(data['total'], 234.0)
        self.assertEqual(self.client.session['promo_code_id'], promo.id)
        self.assertEqual(self.client.session['promo_code_data']['code'], promo.code)

    def test_remove_promo_code_clears_session_keys(self):
        self.set_cart()
        session = self.client.session
        session['promo_code_id'] = 123
        session['promo_code_data'] = {'code': 'SAVE10', 'discount': 26.0}
        session.save()

        response = self.client.post(self.remove_promo_url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['discount'], 0.0)
        self.assertEqual(data['total'], 260.0)
        self.assertNotIn('promo_code_id', self.client.session)
        self.assertNotIn('promo_code_data', self.client.session)
