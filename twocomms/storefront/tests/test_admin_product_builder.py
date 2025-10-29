"""Tests for the new product builder admin view."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from storefront.models import (
    Product,
    Category,
    Catalog,
    SizeGrid,
    ProductStatus,
)
from productcolors.models import ProductColorVariant


class ProductBuilderViewTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.staff_user = self.user_model.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='secret',
            is_staff=True,
        )
        self.catalog = Catalog.objects.create(
            name='Apparel',
            slug='apparel',
            description='Clothing catalog',
        )
        self.category = Category.objects.create(
            name='T-Shirts',
            slug='t-shirts',
        )
        self.builder_url = reverse('admin_product_builder')

    def base_post_data(self, overrides=None):
        data = {
            'product-title': 'New Hoodie',
            'product-slug': '',
            'product-category': str(self.category.pk),
            'product-catalog': str(self.catalog.pk),
            'product-size_grid': '',
            'product-price': '1099',
            'product-discount_percent': '',
            'product-short_description': 'Short summary',
            'product-full_description': 'Detailed description',
            'product-main_image_alt': '',
            'product-points_reward': '0',
            'product-status': ProductStatus.DRAFT,
            'product-priority': '0',
            'seo-seo_title': '',
            'seo-seo_description': '',
            'seo-seo_keywords': '',
            'seo-seo_schema': '{}',
            'color_variants-TOTAL_FORMS': '0',
            'color_variants-INITIAL_FORMS': '0',
            'color_variants-MIN_NUM_FORMS': '0',
            'color_variants-MAX_NUM_FORMS': '1000',
            'catalog-options-TOTAL_FORMS': '0',
            'catalog-options-INITIAL_FORMS': '0',
            'catalog-options-MIN_NUM_FORMS': '0',
            'catalog-options-MAX_NUM_FORMS': '1000',
        }
        if overrides:
            data.update(overrides)
        return data

    def test_requires_staff_login(self):
        response = self.client.get(self.builder_url)
        self.assertEqual(response.status_code, 302)

    def test_staff_can_open_builder(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.builder_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('product_form', response.context)
        self.assertIn('builder_progress', response.context)

    def test_post_creates_product(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(self.builder_url, self.base_post_data())
        self.assertEqual(response.status_code, 302)

        product = Product.objects.get(title='New Hoodie')
        self.assertEqual(product.catalog, self.catalog)
        self.assertEqual(product.category, self.category)
        self.assertEqual(product.status, ProductStatus.DRAFT)
        self.assertTrue(product.slug)

    def test_post_creates_size_grid(self):
        self.client.force_login(self.staff_user)
        data = self.base_post_data({
            'size_grid-name': 'Unisex sizing',
            'size_grid-description': 'XS-XXL',
            'size_grid-is_active': 'on',
        })
        response = self.client.post(self.builder_url, data)
        self.assertEqual(response.status_code, 302)

        product = Product.objects.get(title='New Hoodie')
        self.assertIsNotNone(product.size_grid)
        self.assertEqual(product.size_grid.name, 'Unisex sizing')
        self.assertEqual(product.size_grid.catalog, self.catalog)
        self.assertTrue(SizeGrid.objects.filter(name='Unisex sizing').exists())

    def test_post_creates_color_variant(self):
        self.client.force_login(self.staff_user)
        data = self.base_post_data({
            'color_variants-TOTAL_FORMS': '1',
            'color_variants-INITIAL_FORMS': '0',
            'color_variants-MIN_NUM_FORMS': '0',
            'color_variants-MAX_NUM_FORMS': '1000',
            'color_variants-0-id': '',
            'color_variants-0-color': '',
            'color_variants-0-name': 'Червоний',
            'color_variants-0-primary_hex': '#FF0000',
            'color_variants-0-secondary_hex': '',
            'color_variants-0-is_default': 'on',
            'color_variants-0-order': '0',
            'color_variants-0-sku': 'RED-SKU',
            'color_variants-0-barcode': '',
            'color_variants-0-stock': '7',
            'color_variants-0-price_override': '',
            'color_variants-0-metadata': '{}',
            'color_variants-0-images-TOTAL_FORMS': '0',
            'color_variants-0-images-INITIAL_FORMS': '0',
            'color_variants-0-images-MIN_NUM_FORMS': '0',
            'color_variants-0-images-MAX_NUM_FORMS': '1000',
        })
        response = self.client.post(self.builder_url, data)
        self.assertEqual(response.status_code, 302)

        product = Product.objects.get(title='New Hoodie')
        variants = product.color_variants.all()
        self.assertEqual(variants.count(), 1)
        variant = variants.first()
        self.assertTrue(variant.is_default)
        self.assertEqual(variant.sku, 'RED-SKU')
        self.assertEqual(variant.color.primary_hex, '#FF0000')
