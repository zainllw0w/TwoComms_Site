"""Tests for the new product builder admin view."""

import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from storefront.models import (
    Product,
    Category,
    Catalog,
    SizeGrid,
    ProductFitOption,
    ProductStatus,
)

PNG_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ProductBuilderViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp(prefix="product_builder_tests_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.feed_task_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            return_value=None,
        )
        self.feed_task_mock = self.feed_task_patcher.start()
        self.addCleanup(self.feed_task_patcher.stop)
        self.image_task_patcher = patch(
            "storefront.signals.optimize_image_field_task.delay",
            return_value=None,
        )
        self.optimize_image_mock = self.image_task_patcher.start()
        self.addCleanup(self.image_task_patcher.stop)
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
            'fit_options-TOTAL_FORMS': '0',
            'fit_options-INITIAL_FORMS': '0',
            'fit_options-MIN_NUM_FORMS': '0',
            'fit_options-MAX_NUM_FORMS': '1000',
        }
        if overrides:
            data.update(overrides)
        return data

    def image_file(self, name):
        return SimpleUploadedFile(name, PNG_PIXEL, content_type="image/png")

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

    def test_post_saves_home_card_image(self):
        self.client.force_login(self.staff_user)
        data = self.base_post_data({
            'product-title': 'New Home Card Product',
            'product-home_card_image': self.image_file('home-card-builder.png'),
        })

        with self.settings(MEDIA_ROOT=self._media_root):
            response = self.client.post(self.builder_url, data)

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(title='New Home Card Product')
        self.assertTrue(product.home_card_image.name.endswith('home-card-builder.png'))

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

    def test_post_creates_product_fit_options(self):
        self.client.force_login(self.staff_user)
        data = self.base_post_data({
            'product-title': 'New T-Shirt',
            'fit_options-TOTAL_FORMS': '2',
            'fit_options-INITIAL_FORMS': '0',
            'fit_options-MIN_NUM_FORMS': '0',
            'fit_options-MAX_NUM_FORMS': '1000',
            'fit_options-0-id': '',
            'fit_options-0-code': 'classic',
            'fit_options-0-label': 'Класичний',
            'fit_options-0-description': 'Прямий крій, стандартна посадка',
            'fit_options-0-icon': 'tshirt-classic',
            'fit_options-0-order': '0',
            'fit_options-0-is_default': 'on',
            'fit_options-0-is_active': 'on',
            'fit_options-1-id': '',
            'fit_options-1-code': 'oversize',
            'fit_options-1-label': 'Оверсайз',
            'fit_options-1-description': 'Вільний крій, спущене плече',
            'fit_options-1-icon': 'tshirt-oversize',
            'fit_options-1-order': '1',
            'fit_options-1-is_active': 'on',
        })

        response = self.client.post(self.builder_url, data)

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(title='New T-Shirt')
        options = list(product.fit_options.order_by('order', 'id'))
        self.assertEqual(len(options), 2)
        self.assertEqual([option.code for option in options], ['classic', 'oversize'])
        self.assertEqual(ProductFitOption.objects.filter(product=product, is_default=True).count(), 1)
