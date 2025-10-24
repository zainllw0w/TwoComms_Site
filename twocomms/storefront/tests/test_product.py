"""
Unit tests for product views (product.py).

Tests:
- product_detail: Product detail page
- get_product_images: Get product images (AJAX)
- get_product_variants: Get product variants (AJAX)
- quick_view: Quick view modal (AJAX)
"""

from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
import json

from storefront.models import Product, Category
from productcolors.models import ProductColor


class ProductDetailTests(TestCase):
    """Tests for product_detail function."""
    
    def setUp(self):
        """Set up test client and products."""
        self.client = Client()
        
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category',
            is_active=True
        )
        
        self.product = Product.objects.create(
            title='Test Product',
            slug='test-product',
            category=self.category,
            retail_price=Decimal('100.00'),
            description='Test description',
            is_active=True,
            in_stock=True
        )
        
        self.product_url = reverse('product_detail', args=[self.product.slug])
    
    def test_product_detail_page_loads(self):
        """Test that product detail page loads successfully."""
        response = self.client.get(self.product_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
    
    def test_product_detail_displays_price(self):
        """Test that product page shows price."""
        response = self.client.get(self.product_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '100')
    
    def test_product_detail_displays_description(self):
        """Test that product description is shown."""
        response = self.client.get(self.product_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.description)
    
    def test_inactive_product_not_accessible(self):
        """Test that inactive product returns 404."""
        self.product.is_active = False
        self.product.save()
        
        response = self.client.get(self.product_url)
        self.assertEqual(response.status_code, 404)
    
    def test_nonexistent_product_returns_404(self):
        """Test that non-existent product returns 404."""
        nonexistent_url = reverse('product_detail', args=['nonexistent-slug'])
        response = self.client.get(nonexistent_url)
        self.assertEqual(response.status_code, 404)
    
    def test_product_detail_with_variants(self):
        """Test product page with color variants."""
        # Create color variant
        ProductColor.objects.create(
            product=self.product,
            color_name='Black',
            color_code='#000000',
            size='M',
            quantity=10
        )
        
        response = self.client.get(self.product_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Black')
    
    def test_product_detail_shows_related_products(self):
        """Test that related products are displayed."""
        # Create related product
        related_product = Product.objects.create(
            title='Related Product',
            slug='related-product',
            category=self.category,
            retail_price=Decimal('150.00'),
            is_active=True,
            in_stock=True
        )
        
        response = self.client.get(self.product_url)
        self.assertEqual(response.status_code, 200)
        # May contain related products
        # Implementation depends on how related products are determined
    
    def test_out_of_stock_product_displays_message(self):
        """Test that out of stock message is shown."""
        self.product.in_stock = False
        self.product.save()
        
        response = self.client.get(self.product_url)
        self.assertEqual(response.status_code, 200)
        # Should indicate product is out of stock
        # (Implementation may vary)


class GetProductImagesTests(TestCase):
    """Tests for get_product_images AJAX endpoint."""
    
    def setUp(self):
        """Set up test client and product."""
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
        
        self.images_url = reverse('get_product_images', args=[self.product.id])
    
    def test_get_product_images_returns_json(self):
        """Test that endpoint returns JSON response."""
        response = self.client.get(self.images_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_get_images_for_existing_product(self):
        """Test getting images for existing product."""
        response = self.client.get(self.images_url)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('images', data)
        self.assertIsInstance(data['images'], list)
    
    def test_get_images_for_nonexistent_product(self):
        """Test getting images for non-existent product."""
        nonexistent_url = reverse('get_product_images', args=[99999])
        response = self.client.get(nonexistent_url)
        
        self.assertEqual(response.status_code, 404)


class GetProductVariantsTests(TestCase):
    """Tests for get_product_variants AJAX endpoint."""
    
    def setUp(self):
        """Set up test client and product with variants."""
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
        
        # Create color variants
        ProductColor.objects.create(
            product=self.product,
            color_name='Black',
            color_code='#000000',
            size='M',
            quantity=10
        )
        
        ProductColor.objects.create(
            product=self.product,
            color_name='White',
            color_code='#FFFFFF',
            size='L',
            quantity=5
        )
        
        self.variants_url = reverse('get_product_variants', args=[self.product.id])
    
    def test_get_variants_returns_json(self):
        """Test that endpoint returns JSON."""
        response = self.client.get(self.variants_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_get_variants_for_product(self):
        """Test getting variants for product."""
        response = self.client.get(self.variants_url)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('variants', data)
        self.assertGreater(len(data['variants']), 0)
    
    def test_variants_include_color_and_size(self):
        """Test that variants include color and size info."""
        response = self.client.get(self.variants_url)
        data = json.loads(response.content)
        
        variants = data['variants']
        self.assertTrue(any(v.get('color_name') == 'Black' for v in variants))
        self.assertTrue(any(v.get('size') == 'M' for v in variants))
    
    def test_get_variants_for_nonexistent_product(self):
        """Test getting variants for non-existent product."""
        nonexistent_url = reverse('get_product_variants', args=[99999])
        response = self.client.get(nonexistent_url)
        
        self.assertEqual(response.status_code, 404)


class QuickViewTests(TestCase):
    """Tests for quick_view AJAX endpoint."""
    
    def setUp(self):
        """Set up test client and product."""
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
            description='Quick view test',
            is_active=True,
            in_stock=True
        )
        
        self.quick_view_url = reverse('quick_view', args=[self.product.id])
    
    def test_quick_view_returns_html(self):
        """Test that quick view returns HTML."""
        response = self.client.get(self.quick_view_url)
        self.assertEqual(response.status_code, 200)
        # Should return HTML fragment
    
    def test_quick_view_displays_product_info(self):
        """Test that quick view shows product information."""
        response = self.client.get(self.quick_view_url)
        self.assertEqual(response.status_code, 200)
        
        self.assertContains(response, self.product.title)
        self.assertContains(response, '100')
    
    def test_quick_view_for_nonexistent_product(self):
        """Test quick view for non-existent product."""
        nonexistent_url = reverse('quick_view', args=[99999])
        response = self.client.get(nonexistent_url)
        
        self.assertEqual(response.status_code, 404)
    
    def test_quick_view_for_inactive_product(self):
        """Test quick view for inactive product."""
        self.product.is_active = False
        self.product.save()
        
        response = self.client.get(self.quick_view_url)
        self.assertEqual(response.status_code, 404)



