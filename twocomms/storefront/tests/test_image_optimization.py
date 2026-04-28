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
