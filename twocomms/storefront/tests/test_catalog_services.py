"""
Tests for catalog service helpers (colour dedup + media handling).
"""
from __future__ import annotations

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from productcolors.models import Color, ProductColorVariant
from storefront.models import Catalog, Category, Product
from storefront.services.catalog import (
    VariantImagePayload,
    append_product_gallery,
    ensure_color_identity,
    sync_variant_images,
)

PNG_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class CatalogServiceTestCase(TestCase):
    """
    Base fixture: simple catalog/category/product for service tests.
    """

    @classmethod
    def setUpTestData(cls):
        cls.catalog = Catalog.objects.create(name="Apparel", slug="apparel")
        cls.category = Category.objects.create(name="T-Shirts", slug="t-shirts")
        cls.product = Product.objects.create(
            title="Test Tee",
            slug="test-tee",
            category=cls.category,
            catalog=cls.catalog,
            price=999,
        )


class ColorServiceTests(CatalogServiceTestCase):
    def test_ensure_color_identity_merges_duplicates(self):
        canonical = Color.objects.create(
            name="Black",
            primary_hex="#000000",
            secondary_hex=None,
        )
        duplicate = Color.objects.create(
            name="Duplicate Black",
            primary_hex="#000000",
            secondary_hex="",
        )
        variant = ProductColorVariant.objects.create(
            product=self.product,
            color=duplicate,
            order=0,
        )

        result = ensure_color_identity(
            primary_hex="#000000",
            secondary_hex=None,
            name="Чорний",
        )

        self.assertTrue(result.any_changes())
        self.assertIn(duplicate.pk, result.merged_ids)
        self.assertEqual(Color.objects.count(), 1)
        variant.refresh_from_db()
        self.assertEqual(variant.color_id, result.color.pk)
        self.assertEqual(result.color.name, "Чорний")
        self.assertEqual(result.color.primary_hex, "#000000")

    def test_ensure_color_identity_normalises_hex(self):
        result = ensure_color_identity(
            primary_hex="ff00aa",
            secondary_hex=None,
            name="Accent",
        )
        self.assertTrue(result.created)
        self.assertEqual(result.color.primary_hex, "#FF00AA")
        self.assertEqual(result.color.name, "Accent")


class MediaServiceTests(CatalogServiceTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp(prefix="catalog_media_tests_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.color = Color.objects.create(name="White", primary_hex="#FFFFFF")
        self.variant = ProductColorVariant.objects.create(
            product=self.product,
            color=self.color,
            order=0,
        )

    def _image_file(self, name: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(name, PNG_PIXEL, content_type="image/png")

    def test_append_product_gallery_sets_main_image(self):
        with self.settings(MEDIA_ROOT=self._media_root):
            append_product_gallery(
                self.product,
                [self._image_file("gallery-1.png"), self._image_file("gallery-2.png")],
            )
            self.product.refresh_from_db()
            self.assertTrue(
                self.product.main_image.name.endswith("gallery-1.png"),
                msg="First gallery image should become main when absent.",
            )
            self.assertEqual(self.product.images.count(), 2)

    def test_sync_variant_images_creates_and_orders_images(self):
        with self.settings(MEDIA_ROOT=self._media_root):
            payloads = [
                VariantImagePayload(
                    instance=None,
                    uploaded_file=self._image_file("variant-front.png"),
                    alt_text="Front",
                    order=None,
                ),
                VariantImagePayload(
                    instance=None,
                    uploaded_file=self._image_file("variant-back.png"),
                    alt_text="Back",
                    order=5,
                ),
            ]
            sync_variant_images(self.variant, payloads, auto_assign_product_main=True)

            images = list(self.variant.images.order_by("order", "id"))
            self.assertEqual(len(images), 2)
            self.assertEqual(images[0].order, 0)
            self.assertEqual(images[0].alt_text, "Front")
            self.assertEqual(images[1].order, 1)
            self.assertEqual(images[1].alt_text, "Back")

            self.product.refresh_from_db()
            self.assertTrue(self.product.main_image, "Product main image should be auto-populated.")

    def test_sync_variant_images_supports_updates_and_deletions(self):
        with self.settings(MEDIA_ROOT=self._media_root):
            initial_payloads = [
                VariantImagePayload(
                    instance=None,
                    uploaded_file=self._image_file("initial-1.png"),
                    alt_text="Primary",
                    order=None,
                ),
                VariantImagePayload(
                    instance=None,
                    uploaded_file=self._image_file("initial-2.png"),
                    alt_text="Secondary",
                    order=None,
                ),
            ]
            sync_variant_images(self.variant, initial_payloads, auto_assign_product_main=False)
            existing = list(self.variant.images.order_by("order", "id"))

            update_payloads = [
                VariantImagePayload(
                    instance=existing[0],
                    uploaded_file=None,
                    alt_text="Primary(updated)",
                    order=3,
                ),
                VariantImagePayload(
                    instance=existing[1],
                    uploaded_file=None,
                    alt_text="Secondary",
                    order=0,
                    delete=True,
                ),
            ]
            sync_variant_images(self.variant, update_payloads, auto_assign_product_main=False)

            images = list(self.variant.images.order_by("order", "id"))
            self.assertEqual(len(images), 1)
            self.assertEqual(images[0].order, 0)
            self.assertEqual(images[0].alt_text, "Primary(updated)")

