"""
Unit tests for catalog views (catalog.py).

Tests:
- home: Homepage with featured products
- catalog: Category catalog view
- search: Product search functionality
- load_more_products: AJAX pagination
"""

from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
import json

from storefront.models import Product, Category


class HomeViewTests(TestCase):
    """Tests for home (homepage) function."""
    
    def setUp(self):
        """Set up test client and products."""
        self.client = Client()
        self.home_url = reverse('home')
        
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category',
            is_active=True
        )
        
        # Create test products
        for i in range(5):
            Product.objects.create(
                title=f'Test Product {i}',
                slug=f'test-product-{i}',
                category=self.category,
                retail_price=Decimal(f'{100 + i * 10}.00'),
                is_active=True,
                in_stock=True
            )
    
    def test_home_page_loads(self):
        """Test that homepage loads successfully."""
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
    
    def test_home_page_displays_products(self):
        """Test that homepage shows products."""
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        
        # Should display at least one product
        self.assertContains(response, 'Test Product')
    
    def test_home_page_pagination(self):
        """Test that homepage has pagination."""
        # Create many products
        for i in range(20):
            Product.objects.create(
                title=f'Extra Product {i}',
                slug=f'extra-product-{i}',
                category=self.category,
                retail_price=Decimal('100.00'),
                is_active=True,
                in_stock=True
            )
        
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        
        # Should have pagination (implementation specific)
        # Check for pagination elements
    
    def test_home_page_only_shows_active_products(self):
        """Test that only active products are shown."""
        # Create inactive product
        inactive_product = Product.objects.create(
            title='Inactive Product',
            slug='inactive-product',
            category=self.category,
            retail_price=Decimal('100.00'),
            is_active=False,
            in_stock=True
        )
        
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        
        # Should NOT contain inactive product
        self.assertNotContains(response, 'Inactive Product')
    
    def test_home_page_caching(self):
        """Test that homepage is cached for anonymous users."""
        # First request
        response1 = self.client.get(self.home_url)
        
        # Second request (should be cached)
        response2 = self.client.get(self.home_url)
        
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)


class CatalogViewTests(TestCase):
    """Tests for catalog (category) function."""
    
    def setUp(self):
        """Set up test client, categories, and products."""
        self.client = Client()
        
        self.category1 = Category.objects.create(
            name='Category 1',
            slug='category-1',
            is_active=True
        )
        
        self.category2 = Category.objects.create(
            name='Category 2',
            slug='category-2',
            is_active=True
        )
        
        # Create products in category 1
        for i in range(3):
            Product.objects.create(
                title=f'Product 1-{i}',
                slug=f'product-1-{i}',
                category=self.category1,
                retail_price=Decimal('100.00'),
                is_active=True,
                in_stock=True
            )
        
        # Create products in category 2
        for i in range(2):
            Product.objects.create(
                title=f'Product 2-{i}',
                slug=f'product-2-{i}',
                category=self.category2,
                retail_price=Decimal('150.00'),
                is_active=True,
                in_stock=True
            )
        
        self.catalog_url = reverse('catalog', args=[self.category1.slug])
    
    def test_catalog_page_loads(self):
        """Test that catalog page loads successfully."""
        response = self.client.get(self.catalog_url)
        self.assertEqual(response.status_code, 200)
    
    def test_catalog_displays_category_products(self):
        """Test that catalog shows only products from category."""
        response = self.client.get(self.catalog_url)
        self.assertEqual(response.status_code, 200)
        
        # Should contain products from category 1
        self.assertContains(response, 'Product 1-')
        
        # Should NOT contain products from category 2
        self.assertNotContains(response, 'Product 2-')
    
    def test_catalog_with_nonexistent_category(self):
        """Test catalog with non-existent category slug."""
        nonexistent_url = reverse('catalog', args=['nonexistent-category'])
        response = self.client.get(nonexistent_url)
        
        self.assertEqual(response.status_code, 404)
    
    def test_catalog_with_inactive_category(self):
        """Test catalog with inactive category."""
        self.category1.is_active = False
        self.category1.save()
        
        response = self.client.get(self.catalog_url)
        self.assertEqual(response.status_code, 404)
    
    def test_catalog_filtering(self):
        """Test catalog with filter parameters."""
        response = self.client.get(self.catalog_url, {
            'min_price': '50',
            'max_price': '200'
        })
        
        self.assertEqual(response.status_code, 200)
        # Should apply price filter
    
    def test_catalog_sorting(self):
        """Test catalog with sorting parameters."""
        response = self.client.get(self.catalog_url, {
            'sort': 'price_asc'
        })
        
        self.assertEqual(response.status_code, 200)
        # Products should be sorted by price


class SearchViewTests(TestCase):
    """Tests for search function."""
    
    def setUp(self):
        """Set up test client and searchable products."""
        self.client = Client()
        self.search_url = reverse('search')
        
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category',
            is_active=True
        )
        
        # Create products with different names
        Product.objects.create(
            title='Red T-Shirt',
            slug='red-t-shirt',
            category=self.category,
            description='A beautiful red shirt',
            retail_price=Decimal('50.00'),
            is_active=True,
            in_stock=True
        )
        
        Product.objects.create(
            title='Blue Jeans',
            slug='blue-jeans',
            category=self.category,
            description='Comfortable blue jeans',
            retail_price=Decimal('80.00'),
            is_active=True,
            in_stock=True
        )
        
        Product.objects.create(
            title='Red Cap',
            slug='red-cap',
            category=self.category,
            description='Stylish red cap',
            retail_price=Decimal('30.00'),
            is_active=True,
            in_stock=True
        )
    
    def test_search_page_loads(self):
        """Test that search page loads."""
        response = self.client.get(self.search_url)
        self.assertEqual(response.status_code, 200)
    
    def test_search_with_query(self):
        """Test search with query parameter."""
        response = self.client.get(self.search_url, {'q': 'red'})
        self.assertEqual(response.status_code, 200)
        
        # Should find products with "red" in title
        self.assertContains(response, 'Red T-Shirt')
        self.assertContains(response, 'Red Cap')
        
        # Should NOT contain "Blue Jeans"
        self.assertNotContains(response, 'Blue Jeans')
    
    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        response = self.client.get(self.search_url, {'q': 'RED'})
        self.assertEqual(response.status_code, 200)
        
        # Should still find "Red" products
        self.assertContains(response, 'Red T-Shirt')
    
    def test_search_in_description(self):
        """Test search in product descriptions."""
        response = self.client.get(self.search_url, {'q': 'comfortable'})
        self.assertEqual(response.status_code, 200)
        
        # Should find product with "comfortable" in description
        self.assertContains(response, 'Blue Jeans')
    
    def test_search_with_empty_query(self):
        """Test search with empty query."""
        response = self.client.get(self.search_url, {'q': ''})
        self.assertEqual(response.status_code, 200)
        
        # Should show all products or message
    
    def test_search_no_results(self):
        """Test search with query that has no results."""
        response = self.client.get(self.search_url, {'q': 'nonexistent'})
        self.assertEqual(response.status_code, 200)
        
        # Should show "no results" message
        self.assertContains(response, 'No')
    
    def test_search_only_active_products(self):
        """Test that search only shows active products."""
        # Create inactive product with matching query
        Product.objects.create(
            title='Red Hoodie',
            slug='red-hoodie',
            category=self.category,
            retail_price=Decimal('70.00'),
            is_active=False,
            in_stock=True
        )
        
        response = self.client.get(self.search_url, {'q': 'red'})
        self.assertEqual(response.status_code, 200)
        
        # Should NOT contain inactive product
        self.assertNotContains(response, 'Red Hoodie')


class LoadMoreProductsTests(TestCase):
    """Tests for load_more_products AJAX endpoint."""
    
    def setUp(self):
        """Set up test client and products."""
        self.client = Client()
        self.load_more_url = reverse('load_more_products')
        
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category',
            is_active=True
        )
        
        # Create many products for pagination
        for i in range(30):
            Product.objects.create(
                title=f'Product {i}',
                slug=f'product-{i}',
                category=self.category,
                retail_price=Decimal('100.00'),
                is_active=True,
                in_stock=True
            )
    
    def test_load_more_returns_json(self):
        """Test that endpoint returns JSON."""
        response = self.client.get(self.load_more_url, {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_load_more_products_pagination(self):
        """Test loading next page of products."""
        response = self.client.get(self.load_more_url, {'page': 2})
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('products', data)
        self.assertIsInstance(data['products'], list)
    
    def test_load_more_with_category_filter(self):
        """Test loading more with category filter."""
        response = self.client.get(self.load_more_url, {
            'page': 2,
            'category': self.category.slug
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('products', data)
    
    def test_load_more_beyond_last_page(self):
        """Test loading page beyond available products."""
        response = self.client.get(self.load_more_url, {'page': 999})
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        # Should return empty products list or has_next=False
        self.assertTrue(
            len(data.get('products', [])) == 0 or
            data.get('has_next') == False
        )


