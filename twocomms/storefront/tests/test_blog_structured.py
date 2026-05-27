from __future__ import annotations

import json
import io
import tempfile
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from storefront.models import (
    BlogCategory,
    BlogMediaAsset,
    BlogPost,
    BlogPostBlock,
    BlogPromoCampaign,
    BlogPromoClaim,
    PromoCode,
    UserPromoCode,
)
from storefront.services.blog_blocks import render_post_blocks
from storefront.services.index_targets import build_blog_urls
from storefront.sitemaps import BlogCategorySitemap


@override_settings(
    COMPRESS_ENABLED=False,
    COMPRESS_OFFLINE=False,
    SITE_BASE_URL="https://twocomms.shop",
)
class BlogStructuredPublicTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.reviews = BlogCategory.objects.create(name="Огляди", slug="reviews")
        self.product_reviews = BlogCategory.objects.create(
            name="Огляди продукції",
            slug="product-reviews",
            parent=self.reviews,
        )
        self.news = BlogCategory.objects.create(name="Новини", slug="news")
        self.veteran = BlogCategory.objects.create(
            name="Український ветеранський фонд",
            slug="veteran-fund",
            parent=self.news,
        )

    def test_product_review_without_blocks_does_not_render_veteran_fund_hardcode(self):
        post = BlogPost.objects.create(
            category=self.product_reviews,
            title="Огляд футболки TwoComms",
            slug="shirt-review",
            excerpt="Огляд посадки та тканини.",
            content_html="<p>Матеріал без фондових блоків.</p>",
            published_at=timezone.now(),
            is_published=True,
        )

        response = self.client.get(reverse("blog_post", kwargs={"slug": post.slug}), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Огляд футболки TwoComms")
        self.assertContains(response, "Матеріал без фондових блоків")
        self.assertNotContains(response, "Український ветеранський фонд")
        self.assertNotContains(response, "Внутрішній прогрес")
        self.assertNotContains(response, "2/4")
        self.assertNotContains(response, "article-custom-print-cta")

    def test_structured_blocks_render_only_when_attached_to_post(self):
        fund_post = BlogPost.objects.create(
            category=self.veteran,
            title="Звіт фонду",
            slug="twocomms-veteran-fund-progress",
            excerpt="Звіт по етапах.",
            content_html="<p>Legacy fallback.</p>",
            published_at=timezone.now(),
            is_published=True,
        )
        BlogPostBlock.objects.create(
            post=fund_post,
            block_type=BlogPostBlock.BlockType.METRIC_CARDS,
            sort_order=10,
            payload={
                "cards": [
                    {
                        "label": {"uk": "Внутрішній прогрес"},
                        "value": "2/4",
                        "caption": {"uk": "етапи закрито"},
                    }
                ]
            },
        )
        BlogPostBlock.objects.create(
            post=fund_post,
            block_type=BlogPostBlock.BlockType.CTA_GROUP,
            sort_order=20,
            payload={
                "layout": "full",
                "buttons": [
                    {
                        "provider": "telegram",
                        "label": {"uk": "Написати в Telegram"},
                        "url": "https://t.me/twocomms",
                    }
                ],
            },
        )

        response = self.client.get(reverse("blog_post", kwargs={"slug": fund_post.slug}), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Внутрішній прогрес")
        self.assertContains(response, "2/4")
        self.assertContains(response, "Написати в Telegram")
        self.assertContains(response, "article-structured-block")

    def test_nested_category_url_filters_child_and_flat_url_redirects(self):
        child_post = BlogPost.objects.create(
            category=self.veteran,
            title="Звіт УВФ",
            slug="fund-report",
            excerpt="Новина фонду.",
            content_html="<p>Звіт.</p>",
            published_at=timezone.now(),
            is_published=True,
        )
        other_post = BlogPost.objects.create(
            category=self.product_reviews,
            title="Огляд худі",
            slug="hoodie-review",
            excerpt="Огляд.",
            content_html="<p>Огляд.</p>",
            published_at=timezone.now(),
            is_published=True,
        )

        nested = self.client.get("/blog/category/news/veteran-fund/", secure=True)
        legacy = self.client.get("/blog/category/veteran-fund/", secure=True, follow=False)

        self.assertEqual(nested.status_code, 200)
        self.assertContains(nested, child_post.title)
        self.assertNotContains(nested, other_post.title)
        self.assertEqual(legacy.status_code, 301)
        self.assertEqual(legacy["Location"], "/blog/category/news/veteran-fund/")

    def test_child_category_related_posts_do_not_mix_other_parent_fallback(self):
        review_post = BlogPost.objects.create(
            category=self.product_reviews,
            title="Огляд худі TwoComms",
            slug="hoodie-review-related",
            excerpt="Огляд.",
            content_html="<p>Огляд.</p>",
            published_at=timezone.now(),
            is_published=True,
        )
        veteran_post = BlogPost.objects.create(
            category=self.veteran,
            title="Звіт ветеранського фонду",
            slug="fund-report-related",
            excerpt="Звіт.",
            content_html="<p>Звіт.</p>",
            published_at=timezone.now(),
            is_published=True,
        )

        response = self.client.get(reverse("blog_post", kwargs={"slug": review_post.slug}), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, review_post.title)
        self.assertNotContains(response, veteran_post.title)

    def test_sitemap_and_index_targets_include_nested_category_urls(self):
        sitemap = BlogCategorySitemap()

        self.assertIn(self.veteran, list(sitemap.items()))
        self.assertEqual(sitemap.location(self.veteran), "/blog/category/news/veteran-fund/")
        urls = build_blog_urls(["uk"])
        self.assertIn("https://twocomms.shop/blog/category/news/veteran-fund/", urls)

    def test_rich_text_is_sanitized_and_h1_is_removed(self):
        post = BlogPost.objects.create(
            category=self.product_reviews,
            title="Безпечний пост",
            slug="safe-post",
            excerpt="Тест.",
            content_html="",
            published_at=timezone.now(),
            is_published=True,
        )
        BlogPostBlock.objects.create(
            post=post,
            block_type=BlogPostBlock.BlockType.RICH_TEXT,
            sort_order=10,
            payload={
                "html": {
                    "uk": "<h1>Небажаний H1</h1><h2>Дозволений H2</h2><p onclick='x()'>Текст</p><script>alert(1)</script>"
                }
            },
        )

        html, schema = render_post_blocks(post, request=self.client.request().wsgi_request)

        self.assertIn("Дозволений H2", html)
        self.assertIn("<p>Текст</p>", html)
        self.assertNotIn("<h1", html)
        self.assertNotIn("onclick", html)
        self.assertNotIn("script", html)
        self.assertEqual(schema, {})

    def test_faq_block_contributes_schema(self):
        post = BlogPost.objects.create(
            category=self.product_reviews,
            title="FAQ пост",
            slug="faq-post",
            excerpt="FAQ.",
            content_html="",
            published_at=timezone.now(),
            is_published=True,
        )
        BlogPostBlock.objects.create(
            post=post,
            block_type=BlogPostBlock.BlockType.FAQ,
            sort_order=10,
            payload={
                "items": [
                    {
                        "question": {"uk": "Як прати футболку?"},
                        "answer": {"uk": "Прати навиворіт при 30 градусах."},
                    }
                ]
            },
        )

        html, schema = render_post_blocks(post, request=self.client.request().wsgi_request)

        self.assertIn("Як прати футболку?", html)
        self.assertEqual(schema["@type"], "FAQPage")
        self.assertEqual(schema["mainEntity"][0]["name"], "Як прати футболку?")


@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
class BlogStructuredAdminTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(username="blog-admin", password="pass12345", is_staff=True)
        self.category = BlogCategory.objects.create(name="Огляди", slug="reviews")
        self.post = BlogPost.objects.create(
            category=self.category,
            title="Огляд худі",
            slug="hoodie-review",
            excerpt="Огляд.",
            content_html="<p>Legacy.</p>",
            published_at=timezone.now(),
            is_published=True,
        )

    def test_admin_editor_exposes_visual_block_composer_and_server_preview(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin_blog_post_update", kwargs={"pk": self.post.pk}), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-blog-block-editor")
        self.assertContains(response, "data-block-palette")
        self.assertContains(response, "data-preview-endpoint")
        self.assertContains(response, "data-media-upload-endpoint")
        self.assertContains(response, "SEO")
        self.assertContains(response, "45-60")

    def test_category_editor_does_not_boot_post_block_composer(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin_blog_category_create"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-blog-block-editor")
        self.assertContains(response, "Нова категорія блогу")

    def test_admin_preview_endpoint_uses_server_renderer(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("admin_blog_post_preview", kwargs={"pk": self.post.pk}),
            data=json.dumps(
                {
                    "blocks": [
                        {
                            "type": "callout",
                            "payload": {
                                "tone": "info",
                                "title": {"uk": "Важливо"},
                                "body": {"uk": "Server-side preview."},
                            },
                        }
                    ]
                }
            ),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Server-side preview.")
        self.assertContains(response, "article-callout", html=False)

    def test_admin_preview_handles_unsaved_promo_block(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("admin_blog_post_preview", kwargs={"pk": self.post.pk}),
            data=json.dumps(
                {
                    "blocks": [
                        {
                            "type": "promo_claim",
                            "payload": {
                                "campaign_id": "",
                                "title": {"uk": "Отримати промокод"},
                                "button_label": {"uk": "Забрати"},
                            },
                        }
                    ]
                }
            ),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Отримати промокод")
        self.assertContains(response, "disabled")

    def test_admin_media_upload_creates_asset_for_image_blocks(self):
        self.client.force_login(self.staff)
        image = Image.new("RGB", (640, 400), "#f97316")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        upload = SimpleUploadedFile("article.jpg", buffer.getvalue(), content_type="image/jpeg")

        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("admin_blog_media_upload"),
                {
                    "file": upload,
                    "alt_text": "Фото худі",
                    "caption_text": "Підпис під фото",
                    "credit_text": "TwoComms",
                },
                secure=True,
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["asset"]["width"], 640)
            self.assertEqual(payload["asset"]["height"], 400)
            asset = BlogMediaAsset.objects.get(pk=payload["asset"]["id"])
            self.assertEqual(asset.alt["uk"], "Фото худі")
            self.assertEqual(asset.caption["uk"], "Підпис під фото")
            self.assertGreater(asset.file.size, 0)


@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
class BlogPromoAndLockedContentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = BlogCategory.objects.create(name="Акції", slug="promos")
        self.post = BlogPost.objects.create(
            category=self.category,
            title="Акція",
            slug="promo-post",
            excerpt="Промо.",
            content_html="",
            published_at=timezone.now(),
            is_published=True,
        )
        self.campaign = BlogPromoCampaign.objects.create(
            name="Blog launch",
            code_prefix="BLOG",
            discount_type="percentage",
            discount_value=Decimal("15.00"),
            max_claims=2,
            valid_days=14,
            is_active=True,
        )
        self.block = BlogPostBlock.objects.create(
            post=self.post,
            block_type=BlogPostBlock.BlockType.PROMO_CLAIM,
            sort_order=10,
            payload={
                "campaign_id": self.campaign.pk,
                "title": {"uk": "Отримати промокод"},
                "button_label": {"uk": "Забрати знижку"},
            },
        )

    def test_locked_content_is_not_sent_to_anonymous_users(self):
        BlogPostBlock.objects.create(
            post=self.post,
            block_type=BlogPostBlock.BlockType.LOCKED_CONTENT,
            sort_order=20,
            payload={
                "teaser": {"uk": "Увійдіть, щоб побачити бонус."},
                "html": {"uk": "<p>SECRET DISCOUNT DETAILS</p>"},
            },
        )

        response = self.client.get(reverse("blog_post", kwargs={"slug": self.post.slug}), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Увійдіть, щоб побачити бонус")
        self.assertNotContains(response, "SECRET DISCOUNT DETAILS")

    def test_anonymous_promo_claim_does_not_create_code(self):
        response = self.client.post(
            reverse("blog_promo_claim", kwargs={"slug": self.post.slug, "block_id": self.block.pk}),
            secure=True,
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])
        self.assertEqual(PromoCode.objects.count(), 0)
        self.assertEqual(BlogPromoClaim.objects.count(), 0)

    def test_authenticated_promo_claim_generates_unique_code_once(self):
        user = User.objects.create_user(username="reader", password="pass12345")
        self.client.force_login(user)

        first = self.client.post(
            reverse("blog_promo_claim", kwargs={"slug": self.post.slug, "block_id": self.block.pk}),
            secure=True,
            follow=True,
        )
        second = self.client.post(
            reverse("blog_promo_claim", kwargs={"slug": self.post.slug, "block_id": self.block.pk}),
            secure=True,
            follow=True,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(PromoCode.objects.count(), 1)
        self.assertEqual(BlogPromoClaim.objects.count(), 1)
        claim = BlogPromoClaim.objects.get()
        self.assertEqual(claim.user, user)
        self.assertEqual(claim.post, self.post)
        self.assertEqual(claim.block, self.block)
        self.assertTrue(claim.promo_code.code.startswith("BLOG"))
        self.assertTrue(UserPromoCode.objects.filter(user=user, promo_code=claim.promo_code).exists())
