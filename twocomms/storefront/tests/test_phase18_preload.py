"""Phase 18 — LCP preload hint for product hero image."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.template import Context, Template
from django.test import TestCase, override_settings


class PreloadImageTagTests(TestCase):
    """The ``preload_image`` tag must:

    - emit a ``<link rel=preload as=image type=image/avif>`` tag with a
      valid ``imagesrcset`` and ``imagesizes`` when AVIF variants exist,
    - emit nothing (empty string) when the optimized/ folder is missing
      or the AVIF variants haven't been generated yet,
    - keep the URL inside the original ``/media/...`` namespace.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmpdir = Path(tempfile.mkdtemp(prefix="twc-phase18-"))
        # Mirror the on-disk layout used in production: ``products/c3.jpg``
        # plus ``products/optimized/c3_<width>w.avif``.
        products = cls._tmpdir / "products"
        (products / "optimized").mkdir(parents=True, exist_ok=True)
        (products / "c3.jpg").write_bytes(b"jpg")
        for w in (320, 640, 1080):
            (products / "optimized" / f"c3_{w}w.avif").write_bytes(b"avif")
            (products / "optimized" / f"c3_{w}w.webp").write_bytes(b"webp")
        # A second product without optimized variants — the tag must
        # return "" for it.
        (products / "no_avif.jpg").write_bytes(b"jpg")
        cls._media_root = str(cls._tmpdir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmpdir, ignore_errors=True)
        super().tearDownClass()

    def _render(self, image_path: str, sizes: str = "") -> str:
        with override_settings(MEDIA_ROOT=self._media_root):
            tpl = Template(
                "{% load responsive_images %}"
                "{% preload_image image_path sizes %}"
            )
            return tpl.render(Context({"image_path": image_path, "sizes": sizes}))

    def test_emits_avif_preload_when_variants_present(self):
        out = self._render("/media/products/c3.jpg")
        self.assertIn('rel="preload"', out)
        self.assertIn('as="image"', out)
        self.assertIn('type="image/avif"', out)
        self.assertIn('fetchpriority="high"', out)
        # Srcset entries must reference the /media/ namespace.
        self.assertIn("/media/products/optimized/c3_320w.avif 320w", out)
        self.assertIn("/media/products/optimized/c3_1080w.avif 1080w", out)
        # imagesizes attr must be present and non-empty.
        self.assertIn('imagesizes=', out)

    def test_returns_empty_when_no_avif_variants(self):
        out = self._render("/media/products/no_avif.jpg")
        self.assertEqual(out.strip(), "")

    def test_returns_empty_for_missing_path(self):
        out = self._render("")
        self.assertEqual(out.strip(), "")

    def test_uses_custom_sizes_attr_when_provided(self):
        out = self._render("/media/products/c3.jpg", sizes="100vw")
        self.assertIn('imagesizes="100vw"', out)

    def test_default_sizes_attr_when_none_passed(self):
        out = self._render("/media/products/c3.jpg")
        # Default mirrors the <img> sizes used on the PDP.
        self.assertIn("(max-width: 768px) 94vw", out)


class ProductDetailPreloadIntegrationTests(TestCase):
    """The PDP must render the preload hint inside <head>, not <body>."""

    def setUp(self):
        super().setUp()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            p = patch(target)
            self.addCleanup(p.stop)
            p.start()

    def test_pdp_html_carries_preload_block_marker(self):
        # We don't render the full PDP here (heavy fixtures); we only
        # verify the base template exposes the new block so any future
        # template inheritance change is caught.
        from django.template.loader import get_template
        tpl = get_template("base.html")
        # ``origin`` exposes the file path; we read the raw template
        # text to assert the block is present and lives in <head>.
        path = Path(tpl.origin.name)
        head_text = path.read_text().split("</head>")[0]
        self.assertIn("{% block preload_hints %}", head_text)
