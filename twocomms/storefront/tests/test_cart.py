"""
Unit tests for shopping cart views (cart.py).

Tests:
- view_cart: Display cart contents
- add_to_cart: Add product to cart
- update_cart: Update product quantity
- remove_from_cart: Remove product from cart
- clear_cart: Empty the cart
- apply_promo_code: Apply promo code discount
- remove_promo_code: Remove promo code
- get_cart_count: Get total items count
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
import json

from storefront.models import Product, Category, PromoCode
from accounts.models import UserProfile


class ViewCartTests(TestCase):
    """Tests for view_cart function."""
    
    def setUp(self):
        """Set up test client and test products."""
        self.client = Client()
        self.cart_url = reverse('cart')
        
        # Create test category and products
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        self.product1 = Product.objects.create(
            title='Test Product 1',
            slug='test-product-1',
            category=self.category,
            retail_price=Decimal('100.00'),
            is_active=True,
            in_stock=True
        )
        
        self.product2 = Product.objects.create(
            title='Test Product 2',
            slug='test-product-2',
            category=self.category,
            retail_price=Decimal('200.00'),
            is_active=True,
            in_stock=True
        )
    
    def test_view_empty_cart(self):
        """Test viewing an empty cart."""
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cart')
        # Cart should be empty
        cart = response.context.get('cart', {})
        self.assertEqual(len(cart), 0)
    
    def test_view_cart_with_products(self):
        """Test viewing cart with products."""
        # Add products to session cart
        session = self.client.session
        session['cart'] = {
            str(self.product1.id): {
                'quantity': 2,
                'color': 'Black',
                'size': 'M'
            }
        }
        session.save()
        
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, 200)
        
        # Should display product
        self.assertContains(response, self.product1.title)


class AddToCartTests(TestCase):
    """Tests for add_to_cart function."""
    
    def setUp(self):
        """Set up test client and products."""
        self.client = Client()
        self.add_to_cart_url = reverse('add_to_cart')
        
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
    
    def test_add_product_to_cart(self):
        """Test adding a product to cart."""
        response = self.client.post(self.add_to_cart_url, {
            'product_id': self.product.id,
            'quantity': 1,
            'color': 'Black',
            'size': 'M'
        })
        
        # Should return success response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        
        # Product should be in session cart
        cart = self.client.session.get('cart', {})
        self.assertIn(str(self.product.id), cart)
        self.assertEqual(cart[str(self.product.id)]['quantity'], 1)
    
    def test_add_product_with_quantity(self):
        """Test adding product with specific quantity."""
        response = self.client.post(self.add_to_cart_url, {
            'product_id': self.product.id,
            'quantity': 5,
            'color': 'Black',
            'size': 'L'
        })
        
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        
        cart = self.client.session.get('cart', {})
        self.assertEqual(cart[str(self.product.id)]['quantity'], 5)
    
    def test_add_nonexistent_product(self):
        """Test adding non-existent product to cart."""
        response = self.client.post(self.add_to_cart_url, {
            'product_id': 99999,
            'quantity': 1
        })
        
        # Should return error
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))
    
    def test_add_inactive_product(self):
        """Test adding inactive product to cart."""
        self.product.is_active = False
        self.product.save()
        
        response = self.client.post(self.add_to_cart_url, {
            'product_id': self.product.id,
            'quantity': 1
        })
        
        # Should return error
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))
    
    def test_add_out_of_stock_product(self):
        """Test adding out of stock product."""
        self.product.in_stock = False
        self.product.save()
        
        response = self.client.post(self.add_to_cart_url, {
            'product_id': self.product.id,
            'quantity': 1
        })
        
        # Should return error
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))
        self.assertIn('stock', data.get('error', '').lower())


class UpdateCartTests(TestCase):
    """Tests for update_cart function."""
    
    def setUp(self):
        """Set up test client and cart."""
        self.client = Client()
        self.update_cart_url = reverse('update_cart')
        
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
    
    def test_update_product_quantity(self):
        """Test updating product quantity in cart."""
        response = self.client.post(self.update_cart_url, {
            'product_id': self.product.id,
            'quantity': 5
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        
        cart = self.client.session.get('cart', {})
        self.assertEqual(cart[str(self.product.id)]['quantity'], 5)
    
    def test_update_to_zero_quantity(self):
        """Test updating quantity to 0 removes product."""
        response = self.client.post(self.update_cart_url, {
            'product_id': self.product.id,
            'quantity': 0
        })
        
        self.assertEqual(response.status_code, 200)
        
        cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product.id), cart)
    
    def test_update_nonexistent_cart_item(self):
        """Test updating product not in cart."""
        response = self.client.post(self.update_cart_url, {
            'product_id': 99999,
            'quantity': 1
        })
        
        # Should return error
        self.assertEqual(response.status_code, 404)


class RemoveFromCartTests(TestCase):
    """Tests for remove_from_cart function."""
    
    def setUp(self):
        """Set up test client and cart."""
        self.client = Client()
        
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
        
        self.remove_url = reverse('cart_remove', args=[self.product.id])
    
    def test_remove_product_from_cart(self):
        """Test removing product from cart."""
        response = self.client.post(self.remove_url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        
        cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product.id), cart)
    
    def test_remove_nonexistent_product(self):
        """Test removing product that's not in cart."""
        remove_url = reverse('cart_remove', args=[99999])
        response = self.client.post(remove_url)
        
        # Should still return success (idempotent)
        self.assertEqual(response.status_code, 200)


class ClearCartTests(TestCase):
    """Tests for clear_cart function."""
    
    def setUp(self):
        """Set up test client and cart."""
        self.client = Client()
        self.clear_cart_url = reverse('clean_cart')
        
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        # Add multiple products to cart
        session = self.client.session
        session['cart'] = {
            '1': {'quantity': 2},
            '2': {'quantity': 3},
            '3': {'quantity': 1}
        }
        session.save()
    
    def test_clear_cart(self):
        """Test clearing all products from cart."""
        response = self.client.post(self.clear_cart_url)
        
        self.assertEqual(response.status_code, 302)  # Redirect
        
        cart = self.client.session.get('cart', {})
        self.assertEqual(len(cart), 0)
    
    def test_clear_empty_cart(self):
        """Test clearing an already empty cart."""
        # Clear cart first
        session = self.client.session
        session['cart'] = {}
        session.save()
        
        response = self.client.post(self.clear_cart_url)
        
        # Should still work
        self.assertEqual(response.status_code, 302)


class PromoCodeTests(TestCase):
    """Tests for promo code functionality."""
    
    def setUp(self):
        """Set up test client and promo code."""
        self.client = Client()
        self.apply_promo_url = reverse('apply_promo_code')
        self.remove_promo_url = reverse('remove_promo_code')
        
        # Create promo code
        self.promo = PromoCode.objects.create(
            code='TEST10',
            discount_type='percentage',
            discount_value=Decimal('10.00'),
            is_active=True,
            usage_limit=100,
            used_count=0
        )
    
    def test_apply_valid_promo_code(self):
        """Test applying a valid promo code."""
        response = self.client.post(self.apply_promo_url, {
            'promo_code': 'TEST10'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        
        # Promo code should be in session
        self.assertEqual(
            self.client.session.get('promo_code_id'),
            self.promo.id
        )
    
    def test_apply_invalid_promo_code(self):
        """Test applying non-existent promo code."""
        response = self.client.post(self.apply_promo_url, {
            'promo_code': 'INVALID'
        })
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))
    
    def test_apply_inactive_promo_code(self):
        """Test applying inactive promo code."""
        self.promo.is_active = False
        self.promo.save()
        
        response = self.client.post(self.apply_promo_url, {
            'promo_code': 'TEST10'
        })
        
        self.assertEqual(response.status_code, 400)
    
    def test_remove_promo_code(self):
        """Test removing applied promo code."""
        # Apply promo first
        session = self.client.session
        session['promo_code_id'] = self.promo.id
        session.save()
        
        response = self.client.post(self.remove_promo_url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        
        # Promo code should be removed from session
        self.assertIsNone(self.client.session.get('promo_code_id'))


class GetCartCountTests(TestCase):
    """Tests for get_cart_count function."""
    
    def setUp(self):
        """Set up test client and cart."""
        self.client = Client()
        self.cart_count_url = reverse('get_cart_count')
    
    def test_get_cart_count_empty(self):
        """Test getting count of empty cart."""
        response = self.client.get(self.cart_count_url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data.get('count'), 0)
    
    def test_get_cart_count_with_items(self):
        """Test getting count with items in cart."""
        session = self.client.session
        session['cart'] = {
            '1': {'quantity': 2},
            '2': {'quantity': 3},
            '3': {'quantity': 1}
        }
        session.save()
        
        response = self.client.get(self.cart_count_url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # Total: 2 + 3 + 1 = 6
        self.assertEqual(data.get('count'), 6)



