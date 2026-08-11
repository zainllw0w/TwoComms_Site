"""
Regression tests for optimized media variants.
"""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase
from PIL import Image

from image_optimizer import ImageOptimizer
from storefront.services.image_variants import (
    build_optimized_image_payload,
    optimized_variants_are_current,
)


class ImageOptimizerResponsiveTests(SimpleTestCase):
    def test_product_optimizer_reports_derivative_stages(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "photo.png"
            Image.new("RGB", (4, 4), (12, 24, 36)).save(source)
            progress = []

            variants = ImageOptimizer().optimize_product_image(
                str(source),
                progress_callback=lambda stage, value: progress.append((stage, value)),
            )

        self.assertTrue(variants)
        stages = [stage for stage, _value in progress]
        self.assertEqual(stages[:2], ["webp", "avif"])
        self.assertTrue(all(stage == "responsive" for stage in stages[2:]))
        self.assertEqual(
            [value for _stage, value in progress],
            sorted(value for _stage, value in progress),
        )
        responsive_values = [value for stage, value in progress if stage == "responsive"]
        self.assertGreater(len(responsive_values), 1)
        self.assertGreater(responsive_values[-1], responsive_values[0])

    def test_optimized_files_are_published_with_atomic_replace(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "optimized"
            with patch("image_optimizer.os.replace", wraps=os.replace) as replace:
                saved = ImageOptimizer().save_optimized_images(
                    {"photo.webp": b"complete-image"}, output
                )

            self.assertEqual([Path(saved[0]).name], ["photo.webp"])
            self.assertEqual((output / "photo.webp").read_bytes(), b"complete-image")
            replace.assert_called_once()
            self.assertEqual(list(output.glob("*.tmp")), [])

    def test_partial_derivative_publication_raises_instead_of_reporting_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "optimized"
            real_replace = os.replace

            def fail_second_replace(source, destination):
                if Path(destination).name == "photo.avif":
                    raise OSError("disk full")
                return real_replace(source, destination)

            with patch("image_optimizer.os.replace", side_effect=fail_second_replace):
                with self.assertRaisesRegex(RuntimeError, "photo.avif"):
                    ImageOptimizer().save_optimized_images(
                        {
                            "photo.webp": b"complete-webp",
                            "photo.avif": b"complete-avif",
                        },
                        output,
                    )

            self.assertEqual((output / "photo.webp").read_bytes(), b"complete-webp")
            self.assertFalse((output / "photo.avif").exists())
            self.assertEqual(list(output.glob("*.tmp")), [])

    def test_truncated_derivatives_are_not_considered_current(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "photo.png"
            Image.new("RGB", (2, 2), (12, 24, 36)).save(source)
            output = source.parent / "optimized"
            output.mkdir()
            for extension in ("webp", "avif"):
                candidate = output / f"{source.stem}.{extension}"
                candidate.write_bytes(b"truncated")
                candidate.touch()

            self.assertFalse(optimized_variants_are_current(source))

    def test_missing_responsive_derivatives_are_not_considered_current(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "photo.png"
            Image.new("RGB", (640, 800), (12, 24, 36)).save(source)
            output = source.parent / "optimized"
            output.mkdir()
            for extension in ("webp", "avif"):
                Image.new("RGB", (640, 800), (12, 24, 36)).save(
                    output / f"photo.{extension}",
                    format=extension.upper(),
                )

            self.assertFalse(optimized_variants_are_current(source))

    def test_webp_only_derivatives_are_current_when_avif_encoder_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "photo.png"
            Image.new("RGB", (640, 800), (12, 24, 36)).save(source)
            output = source.parent / "optimized"
            output.mkdir()
            for name in (
                "photo.webp",
                "photo_320w.webp",
                "photo_480w.webp",
                "photo_640w.webp",
            ):
                Image.new("RGB", (2, 2), (12, 24, 36)).save(
                    output / name,
                    format="WEBP",
                )

            Image.init()
            save_registry = dict(Image.SAVE)
            save_registry.pop("AVIF", None)
            with patch.object(Image, "SAVE", save_registry):
                self.assertTrue(optimized_variants_are_current(source))

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
