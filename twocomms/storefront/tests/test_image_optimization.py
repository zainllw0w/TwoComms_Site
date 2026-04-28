"""
Regression tests for optimized media variants.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile

from django.test import SimpleTestCase
from PIL import Image

from image_optimizer import ImageOptimizer
from storefront.services.image_variants import build_optimized_image_payload


class ImageOptimizerResponsiveTests(SimpleTestCase):
    def test_responsive_variants_use_real_output_width_in_filename(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "vertical.png"
            Image.new("RGB", (1080, 1350), (12, 24, 36)).save(source)

            variants = ImageOptimizer().create_responsive_images(str(source), "vertical")

        self.assertIn("vertical_640w.webp", variants)
        self.assertIn("vertical_1080w.webp", variants)
        self.assertNotIn("vertical_1920w.webp", variants)

        with Image.open(BytesIO(variants["vertical_640w.webp"])) as image:
            self.assertEqual(image.width, 640)

    def test_image_payload_ignores_oversized_legacy_responsive_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            media_root = Path(tmp_dir)
            source = media_root / "product_colors" / "legacy.jpg"
            optimized_dir = source.parent / "optimized"
            optimized_dir.mkdir(parents=True)
            Image.new("RGB", (1080, 1350), (12, 24, 36)).save(source)
            for width in (1440, 1920):
                (optimized_dir / f"legacy_{width}w.webp").write_bytes(b"webp")
                (optimized_dir / f"legacy_{width}w.avif").write_bytes(b"avif")

            with self.settings(MEDIA_ROOT=media_root):
                payload = build_optimized_image_payload("/media/product_colors/legacy.jpg")

        self.assertIn("legacy_1440w.webp 1440w", payload["webp_srcset"])
        self.assertIn("legacy_1440w.avif 1440w", payload["avif_srcset"])
        self.assertNotIn("legacy_1920w.webp", payload["webp_srcset"])
        self.assertNotIn("legacy_1920w.avif", payload["avif_srcset"])
