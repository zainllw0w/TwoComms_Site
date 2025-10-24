"""
Unit tests for checkout views (checkout.py).

Tests:
- checkout: Checkout page display
- create_order: Order creation
- confirm_payment: Payment confirmation
- order_success: Order success page
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
import json

from storefront.models import Product, Category, PromoCode
from orders.models import Order
from accounts.models import UserProfile


class CheckoutViewTests(TestCase):
    """Tests for checkout function."""
    
    def setUp(self):
        """Set up test client, user, and products."""
        self.client = Client()
        self.checkout_url = reverse('checkout')
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            phone='+380991234567',
            full_name='Test User',
            city='Київ',
            np_office='Відділення №1'
        )
        
        # Create test products
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        self.product = Product.objects.create(
            title='Test Product',
            slug='test-product',
            category=self.category,
            retail_price=Decimal('100.00'),
            is_active=True,
            in_stock=True
        )
        
        # Add product to cart
        session = self.client.session
        session['cart'] = {
            str(self.product.id): {
                'quantity': 2,
                'color': 'Black',
                'size': 'M'
            }
        }
        session.save()
    
    def test_checkout_page_loads(self):
        """Test that checkout page loads successfully."""
        response = self.client.get(self.checkout_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'checkout')
    
    def test_checkout_with_empty_cart(self):
        """Test checkout with empty cart."""
        # Clear cart
        session = self.client.session
        session['cart'] = {}
        session.save()
        
        response = self.client.get(self.checkout_url)
        
        # Should redirect to cart or show error
        self.assertIn(response.status_code, [200, 302])
    
    def test_checkout_with_authenticated_user(self):
        """Test checkout with logged in user."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(self.checkout_url)
        
        self.assertEqual(response.status_code, 200)
        # Should have user profile data
        self.assertContains(response, self.profile.phone)
    
    def test_checkout_with_guest(self):
        """Test checkout as guest user."""
        response = self.client.get(self.checkout_url)
        
        self.assertEqual(response.status_code, 200)
        # Should display form for guest info
        self.assertContains(response, 'phone')
    
    def test_checkout_displays_cart_summary(self):
        """Test that checkout displays cart items."""
        response = self.client.get(self.checkout_url)
        
        self.assertEqual(response.status_code, 200)
        # Should show product in cart
        self.assertContains(response, self.product.title)
    
    def test_checkout_with_promo_code(self):
        """Test checkout with applied promo code."""
        # Create and apply promo code
        promo = PromoCode.objects.create(
            code='TEST10',
            discount_type='percentage',
            discount_value=Decimal('10.00'),
            is_active=True
        )
        
        session = self.client.session
        session['promo_code_id'] = promo.id
        session.save()
        
        response = self.client.get(self.checkout_url)
        
        self.assertEqual(response.status_code, 200)
        # Should display discount
        self.assertContains(response, promo.code)


class CreateOrderTests(TestCase):
    """Tests for create_order function."""
    
    def setUp(self):
        """Set up test client and products."""
        self.client = Client()
        self.create_order_url = reverse('order_create')
        
        # Create test product
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        self.product = Product.objects.create(
            title='Test Product',
            slug='test-product',
            category=self.category,
            retail_price=Decimal('100.00'),
            is_active=True,
            in_stock=True
        )
        
        # Add to cart
        session = self.client.session
        session['cart'] = {
            str(self.product.id): {
                'quantity': 2,
                'color': 'Black',
                'size': 'M'
            }
        }
        session.save()
    
    def test_create_order_as_guest(self):
        """Test order creation as guest user."""
        response = self.client.post(self.create_order_url, {
            'full_name': 'Test Guest',
            'phone': '+380991234567',
            'email': 'guest@example.com',
            'city': 'Київ',
            'np_office': 'Відділення №1',
            'payment_method': 'cash',
            'delivery_method': 'nova_poshta'
        })
        
        # Should create order and redirect
        self.assertEqual(response.status_code, 302)
        
        # Order should exist
        self.assertTrue(Order.objects.filter(
            phone='+380991234567'
        ).exists())
        
        # Cart should be cleared
        cart = self.client.session.get('cart', {})
        self.assertEqual(len(cart), 0)
    
    def test_create_order_authenticated_user(self):
        """Test order creation as authenticated user."""
        # Create and login user
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=user,
            phone='+380991234567',
            full_name='Test User'
        )
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.create_order_url, {
            'full_name': 'Test User',
            'phone': '+380991234567',
            'city': 'Київ',
            'np_office': 'Відділення №1',
            'payment_method': 'card',
            'delivery_method': 'nova_poshta'
        })
        
        # Should create order
        self.assertEqual(response.status_code, 302)
        
        # Order should be linked to user
        order = Order.objects.filter(user=user).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.phone, '+380991234567')
    
    def test_create_order_with_empty_cart(self):
        """Test order creation with empty cart."""
        # Clear cart
        session = self.client.session
        session['cart'] = {}
        session.save()
        
        response = self.client.post(self.create_order_url, {
            'full_name': 'Test User',
            'phone': '+380991234567',
            'city': 'Київ',
            'np_office': 'Відділення №1',
            'payment_method': 'cash',
            'delivery_method': 'nova_poshta'
        })
        
        # Should return error or redirect
        self.assertIn(response.status_code, [200, 302, 400])
    
    def test_create_order_with_invalid_data(self):
        """Test order creation with invalid phone."""
        response = self.client.post(self.create_order_url, {
            'full_name': 'Test User',
            'phone': 'invalid',
            'city': 'Київ',
            'np_office': 'Відділення №1',
            'payment_method': 'cash',
            'delivery_method': 'nova_poshta'
        })
        
        # Should show error
        self.assertEqual(response.status_code, 400)
    
    def test_create_order_with_promo_code(self):
        """Test order creation with promo code discount."""
        # Create promo code
        promo = PromoCode.objects.create(
            code='TEST10',
            discount_type='percentage',
            discount_value=Decimal('10.00'),
            is_active=True
        )
        
        # Apply promo to session
        session = self.client.session
        session['promo_code_id'] = promo.id
        session.save()
        
        response = self.client.post(self.create_order_url, {
            'full_name': 'Test User',
            'phone': '+380991234567',
            'city': 'Київ',
            'np_office': 'Відділення №1',
            'payment_method': 'cash',
            'delivery_method': 'nova_poshta'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Order should have discount applied
        order = Order.objects.first()
        self.assertIsNotNone(order)
        self.assertIsNotNone(order.promo_code)
        self.assertEqual(order.promo_code.code, 'TEST10')
    
    def test_create_order_card_payment_redirect(self):
        """Test that card payment redirects to payment gateway."""
        response = self.client.post(self.create_order_url, {
            'full_name': 'Test User',
            'phone': '+380991234567',
            'city': 'Київ',
            'np_office': 'Відділення №1',
            'payment_method': 'card',
            'delivery_method': 'nova_poshta'
        })
        
        # Should redirect to payment page
        self.assertEqual(response.status_code, 302)
        
        order = Order.objects.first()
        # Should redirect to payment confirmation
        self.assertIn(order.order_number, response.url)


class ConfirmPaymentTests(TestCase):
    """Tests for confirm_payment function."""
    
    def setUp(self):
        """Set up test client and order."""
        self.client = Client()
        
        # Create test user and order
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.order = Order.objects.create(
            user=self.user,
            order_number='TEST001',
            full_name='Test User',
            phone='+380991234567',
            email='test@example.com',
            total=Decimal('200.00'),
            payment_method='card',
            payment_status='pending'
        )
        
        self.confirm_url = reverse('confirm_payment', args=[self.order.order_number])
    
    def test_confirm_payment_page_loads(self):
        """Test that payment confirmation page loads."""
        response = self.client.get(self.confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)
    
    def test_confirm_payment_authenticated_user(self):
        """Test payment confirmation for order owner."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(self.confirm_url)
        self.assertEqual(response.status_code, 200)
    
    def test_confirm_payment_displays_amount(self):
        """Test that payment page displays correct amount."""
        response = self.client.get(self.confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '200')


class OrderSuccessTests(TestCase):
    """Tests for order_success function."""
    
    def setUp(self):
        """Set up test client and order."""
        self.client = Client()
        
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.order = Order.objects.create(
            user=self.user,
            order_number='TEST001',
            full_name='Test User',
            phone='+380991234567',
            email='test@example.com',
            total=Decimal('200.00'),
            payment_method='cash',
            payment_status='paid'
        )
        
        self.success_url = reverse('order_success', args=[self.order.order_number])
    
    def test_order_success_page_loads(self):
        """Test that order success page loads."""
        response = self.client.get(self.success_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)
    
    def test_order_success_authenticated_user(self):
        """Test success page for authenticated user."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(self.success_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'success')
    
    def test_order_success_displays_order_details(self):
        """Test that success page shows order details."""
        response = self.client.get(self.success_url)
        
        self.assertEqual(response.status_code, 200)
        # Should display order number and total
        self.assertContains(response, self.order.order_number)
        self.assertContains(response, self.order.full_name)



