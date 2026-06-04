"""Tests for product video (YouTube) — model helpers, PDP gallery, schema, feed."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from storefront.models import Category, Product
from storefront.utils.video import (
    extract_youtube_id,
    youtube_embed_url,
    youtube_thumbnail_url,
    youtube_watch_url,
)


class YouTubeUtilTests(TestCase):
    def test_extract_from_supported_formats(self):
        vid = "dQw4w9WgXcQ"
        cases = [
            f"https://www.youtube.com/watch?v={vid}",
            f"https://youtu.be/{vid}",
            f"https://www.youtube.com/embed/{vid}",
            f"https://www.youtube.com/shorts/{vid}",
            f"https://m.youtube.com/watch?v={vid}&t=5s",
        ]
        for url in cases:
            self.assertEqual(extract_youtube_id(url), vid, msg=url)

    def test_extract_rejects_garbage(self):
        self.assertEqual(extract_youtube_id("not a url"), "")
        self.assertEqual(extract_youtube_id(""), "")
        self.assertEqual(extract_youtube_id("https://example.com/watch?v=x"), "")

    def test_derived_urls(self):
        vid = "dQw4w9WgXcQ"
        self.assertEqual(youtube_embed_url(vid), f"https://www.youtube-nocookie.com/embed/{vid}")
        self.assertEqual(youtube_watch_url(vid), f"https://www.youtube.com/watch?v={vid}")
        self.assertEqual(youtube_thumbnail_url(vid), f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg")


class ProductVideoModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Cat", slug="cat", is_active=True)

    def test_video_properties_when_set(self):
        product = Product.objects.create(
            title="P", slug="p", category=self.category, price=100,
            video_url="https://youtu.be/dQw4w9WgXcQ", status="published",
        )
        self.assertTrue(product.has_video)
        self.assertEqual(product.youtube_id, "dQw4w9WgXcQ")
        self.assertIn("youtube-nocookie.com/embed/dQw4w9WgXcQ", product.video_embed_url)
        self.assertIn("i.ytimg.com/vi/dQw4w9WgXcQ", product.video_thumbnail_url)

    def test_no_video_by_default(self):
        product = Product.objects.create(
            title="Q", slug="q", category=self.category, price=100, status="published",
        )
        self.assertFalse(product.has_video)
        self.assertEqual(product.youtube_id, "")


class ProductVideoPdpTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Cat", slug="cat", is_active=True)
        self.product = Product.objects.create(
            title="Video Product", slug="video-product", category=self.category,
            price=100, video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            status="published",
        )

    def test_pdp_exposes_video_context_and_json(self):
        response = self.client.get(reverse("product", args=[self.product.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["product_video"])
        self.assertEqual(response.context["product_video"]["id"], "dQw4w9WgXcQ")
        self.assertContains(response, 'id="product-video"', html=False)
        self.assertContains(response, "data-video-open", html=False)

    def test_pdp_without_video_has_no_video_markup(self):
        product = Product.objects.create(
            title="No Video", slug="no-video", category=self.category,
            price=100, status="published",
        )
        response = self.client.get(reverse("product", args=[product.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["product_video"])
        self.assertNotContains(response, 'id="product-video"', html=False)


class ProductVideoSchemaTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Cat", slug="cat", is_active=True)

    def test_schema_embeds_video_object(self):
        from storefront.seo_utils import StructuredDataGenerator

        product = Product.objects.create(
            title="P", slug="p", category=self.category, price=100,
            video_url="https://youtu.be/dQw4w9WgXcQ", status="published",
        )
        schema = StructuredDataGenerator.generate_product_schema(product)
        self.assertIn("video", schema)
        self.assertEqual(schema["video"]["@type"], "VideoObject")
        self.assertIn("dQw4w9WgXcQ", schema["video"]["embedUrl"])

    def test_schema_no_video_key_without_video(self):
        from storefront.seo_utils import StructuredDataGenerator

        product = Product.objects.create(
            title="Q", slug="q", category=self.category, price=100, status="published",
        )
        schema = StructuredDataGenerator.generate_product_schema(product)
        self.assertNotIn("video", schema)


class ProductVideoFeedTests(TestCase):
    def setUp(self):
        merchant_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        merchant_patcher.start()
        self.addCleanup(merchant_patcher.stop)
        self.category = Category.objects.create(name="Cat", slug="cat", is_active=True)

    def test_feed_video_link_prefers_video_url_field(self):
        from storefront.services.marketplace_feeds import _video_link

        product = Product.objects.create(
            title="P", slug="p", category=self.category, price=100,
            video_url="https://youtu.be/dQw4w9WgXcQ", status="published",
        )
        self.assertEqual(_video_link(product), "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_feed_video_link_falls_back_to_seo_schema(self):
        from storefront.services.marketplace_feeds import _video_link

        product = Product.objects.create(
            title="Q", slug="q", category=self.category, price=100,
            seo_schema={"video_link": "https://twocomms.shop/media/products/x.mp4"},
            status="published",
        )
        self.assertEqual(_video_link(product), "https://twocomms.shop/media/products/x.mp4")


class ProductFormVideoTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Cat", slug="cat", is_active=True)

    def _base_data(self, **overrides):
        data = {
            "title": "Form Product",
            "category": str(self.category.pk),
            "status": "published",
            "priority": "0",
            "price": "500",
            "points_reward": "0",
            "drop_price": "0",
            "wholesale_price": "0",
        }
        data.update(overrides)
        return data

    def test_form_normalizes_video_url_to_watch(self):
        from storefront.forms import ProductForm

        form = ProductForm(data=self._base_data(video_url="https://youtu.be/dQw4w9WgXcQ"))
        self.assertTrue(form.is_valid(), msg=form.errors)
        product = form.save()
        self.assertEqual(product.video_url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_form_rejects_non_youtube_url(self):
        from storefront.forms import ProductForm

        form = ProductForm(data=self._base_data(video_url="https://vimeo.com/12345"))
        self.assertFalse(form.is_valid())
        self.assertIn("video_url", form.errors)

    def test_form_allows_empty_video_url(self):
        from storefront.forms import ProductForm

        form = ProductForm(data=self._base_data(video_url=""))
        self.assertTrue(form.is_valid(), msg=form.errors)
        product = form.save()
        self.assertEqual(product.video_url, "")
        self.assertFalse(product.has_video)
