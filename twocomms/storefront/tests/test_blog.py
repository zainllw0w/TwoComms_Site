import io
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from storefront.models import BlogCategory, BlogPost, BlogPostBlock
from storefront.services.index_targets import build_blog_urls
from storefront.sitemaps import BlogCategorySitemap, BlogPostSitemap


TEST_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
    "fragments": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
}


@override_settings(
    COMPRESS_ENABLED=False,
    COMPRESS_OFFLINE=False,
    SITE_BASE_URL="https://twocomms.shop",
    CACHES=TEST_CACHES,
)
class BlogPublicTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = BlogCategory.objects.create(
            name="Новини бренда TwoComms Test",
            slug="brand-news-test",
            description="Офіційні оновлення TwoComms.",
            seo_title="Новини бренда TwoComms",
            seo_h1="Новини бренда TwoComms",
            seo_description="Офіційні новини бренда TwoComms.",
            bottom_title="Що ще читати про TwoComms",
            bottom_text="Добірка матеріалів про бренд, речі та догляд.",
        )
        self.other_category = BlogCategory.objects.create(
            name="Корисні знання Test",
            slug="guides-test",
            description="Поради та пояснення.",
        )
        self.post = BlogPost.objects.create(
            category=self.category,
            title="TwoComms і Український ветеранський фонд",
            slug="twocomms-veteran-fund-progress-test",
            excerpt="TwoComms фіксує два закриті етапи з чотирьох у внутрішньому плані розвитку.",
            content_html=(
                "<p>TwoComms продовжує розвиток після грантової підтримки "
                "Українського ветеранського фонду.</p>"
            ),
            seo_title="TwoComms і Український ветеранський фонд",
            seo_description="Новина TwoComms про прогрес після підтримки Українського ветеранського фонду.",
            seo_keywords="TwoComms, Український ветеранський фонд",
            source_url="https://veteranfund.com.ua/stories-of-winner/artem-sinilo-istoriia-veterana/",
            published_at=timezone.now(),
            is_published=True,
        )
        self.other_post = BlogPost.objects.create(
            category=self.other_category,
            title="Як доглядати за принтом",
            slug="print-care-guide-test",
            excerpt="Короткий гайд з догляду.",
            content_html="<p>Прати навиворіт.</p>",
            published_at=timezone.now(),
            is_published=True,
        )

    def test_blog_index_lists_posts_newest_first_without_staff_controls_for_guests(self):
        response = self.client.get(reverse("blog"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Новини та блог")
        self.assertContains(response, "blog-hero-lab")
        self.assertContains(response, "blog-featured-strip")
        self.assertContains(response, "blog-topic-dock")
        self.assertContains(response, self.post.title)
        self.assertContains(response, self.other_post.title)
        self.assertContains(response, reverse("blog_category", kwargs={"slug": self.category.slug}))
        self.assertNotContains(response, "Додати пост")
        self.assertNotContains(response, "Перегляди")

    def test_blog_index_shows_staff_add_button_and_post_counters(self):
        staff = User.objects.create_user(username="blog-admin", password="pass12345", is_staff=True)
        self.client.force_login(staff)

        response = self.client.get(reverse("blog"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Додати пост")
        self.assertContains(response, "Перегляди")
        self.assertContains(response, "Унікальні")
        self.assertContains(response, "Редагувати")
        self.assertContains(response, reverse("admin_panel") + "?section=blog")

    def test_legacy_news_urls_redirect_permanently_to_canonical_blog(self):
        checks = {
            "/novyny/": "/blog/",
            "/news/": "/blog/",
            "/blog": "/blog/",
            "/ru/novyny/": "/ru/blog/",
            "/en/news/": "/en/blog/",
        }

        for path, target in checks.items():
            with self.subTest(path=path):
                response = self.client.get(path, secure=True, follow=False)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response["Location"], target)

    def test_category_landing_filters_posts_and_uses_category_seo_copy(self):
        response = self.client.get(reverse("blog_category", kwargs={"slug": self.category.slug}), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Новини бренда TwoComms")
        self.assertContains(response, "Що ще читати про TwoComms")
        self.assertContains(response, self.post.title)
        self.assertNotContains(response, self.other_post.title)
        self.assertContains(response, '"@type": "CollectionPage"', html=False)

    def test_article_records_total_and_unique_non_bot_views(self):
        url = reverse("blog_post", kwargs={"slug": self.post.slug})

        first = self.client.get(url, secure=True, HTTP_USER_AGENT="Mozilla/5.0")
        second = self.client.get(url, secure=True, HTTP_USER_AGENT="Mozilla/5.0")
        bot = self.client.get(url, secure=True, HTTP_USER_AGENT="Googlebot/2.1")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(bot.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 2)
        self.assertEqual(self.post.unique_view_count, 1)
        self.assertContains(first, '"@type": "BlogPosting"', html=False)
        self.assertContains(first, '"mainEntityOfPage": {"@type": "WebPage"', html=False)
        self.assertContains(first, self.post.source_url)

    def test_article_page_renders_editorial_source_and_custom_print_cta_blocks_when_attached(self):
        BlogPostBlock.objects.create(
            post=self.post,
            block_type=BlogPostBlock.BlockType.SOURCE_LIST,
            sort_order=10,
            payload={
                "sources": [
                    {
                        "label": {"uk": "Читати першоджерело"},
                        "url": self.post.source_url,
                    }
                ]
            },
        )
        BlogPostBlock.objects.create(
            post=self.post,
            block_type=BlogPostBlock.BlockType.CTA_GROUP,
            sort_order=20,
            payload={
                "layout": "full",
                "buttons": [
                    {
                        "provider": "custom_print",
                        "label": {"uk": "Створити кастомний принт"},
                        "url": reverse("custom_print"),
                    }
                ],
            },
        )

        response = self.client.get(reverse("blog_post", kwargs={"slug": self.post.slug}), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "article-source-card")
        self.assertContains(response, "article-cta-row")
        self.assertContains(response, reverse("custom_print"))
        self.assertContains(response, "Створити кастомний принт")
        self.assertNotContains(response, "blog-article-media-badges")

    def test_article_page_renders_custom_cover_caption_when_set(self):
        self.post.cover_caption = "TWOCOMMS / Custom cover caption"
        self.post.save(update_fields=["cover_caption"])

        response = self.client.get(reverse("blog_post", kwargs={"slug": self.post.slug}), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "blog-article-media-caption")
        self.assertContains(response, "TWOCOMMS / Custom cover caption")

    def test_uploaded_cover_image_is_converted_to_webp_with_stable_ratio(self):
        image = Image.new("RGB", (2400, 1600), "#f97316")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        upload = SimpleUploadedFile("raw-cover.jpg", buffer.getvalue(), content_type="image/jpeg")

        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            post = BlogPost.objects.create(
                category=self.category,
                title="Пост із фото",
                slug="cover-conversion",
                excerpt="Перевірка конвертації.",
                content_html="<p>Контент.</p>",
                cover_image=upload,
                cover_alt="Тестова обкладинка",
                published_at=timezone.now(),
                is_published=True,
            )

            self.assertTrue(post.cover_image.name.endswith(".webp"))
            with Image.open(post.cover_image.path) as optimized:
                self.assertEqual(optimized.format, "WEBP")
                self.assertLessEqual(max(optimized.size), 1600)

    def test_sitemaps_and_index_targets_include_blog_urls(self):
        post_sitemap = BlogPostSitemap()
        category_sitemap = BlogCategorySitemap()

        self.assertEqual(post_sitemap.location(self.post), reverse("blog_post", kwargs={"slug": self.post.slug}))
        self.assertEqual(
            category_sitemap.location(self.category),
            reverse("blog_category", kwargs={"slug": self.category.slug}),
        )

        urls = build_blog_urls(["uk", "ru"])
        self.assertIn("https://twocomms.shop/blog/", urls)
        self.assertIn(f"https://twocomms.shop/blog/{self.post.slug}/", urls)
        self.assertIn(f"https://twocomms.shop/blog/category/{self.category.slug}/", urls)
        self.assertIn("https://twocomms.shop/ru/blog/", urls)


@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False, CACHES=TEST_CACHES)
class BlogAdminTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(username="staff-blog", password="pass12345", is_staff=True)
        self.category = BlogCategory.objects.create(name="Огляди продукції Test Admin", slug="product-reviews-admin-test")
        self.post = BlogPost.objects.create(
            category=self.category,
            title="Огляд худі TwoComms",
            slug="hoodie-review-admin-test",
            excerpt="Огляд посадки та матеріалів.",
            content_html="<p>Огляд.</p>",
            published_at=timezone.now(),
            view_count=24,
            unique_view_count=9,
        )
        self.post.cover_image = "blog/covers/admin-preview.webp"
        self.post.save(update_fields=["cover_image"])

    def test_custom_admin_blog_section_lists_posts_and_categories(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin_panel"), {"section": "blog"}, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Блог")
        self.assertContains(response, self.category.name)
        self.assertContains(response, self.post.title)
        self.assertContains(response, "Категорії блогу")
        self.assertContains(response, "Пости блогу")
        self.assertContains(response, "admin-blog-overview")
        self.assertContains(response, "admin-blog-preview")
        self.assertContains(response, "admin-preview.webp")
        self.assertContains(response, "24")
        self.assertContains(response, "9")
        self.assertContains(response, "Опубліковано")
        self.assertContains(response, reverse("admin_blog_post_update", kwargs={"pk": self.post.pk}))
        self.assertContains(response, reverse("admin_blog_post_delete", kwargs={"pk": self.post.pk}))
        self.assertContains(response, reverse("admin_blog_category_update", kwargs={"pk": self.category.pk}))
        self.assertContains(response, reverse("admin_blog_category_delete", kwargs={"pk": self.category.pk}))

    def test_custom_admin_can_create_category_and_post(self):
        self.client.force_login(self.staff)

        category_response = self.client.post(
            reverse("admin_blog_category_create"),
            {
                "name": "Новини тест",
                "slug": "test-news",
                "description": "Тестова категорія",
                "is_active": "on",
            },
            secure=True,
        )
        self.assertEqual(category_response.status_code, 302)
        category = BlogCategory.objects.get(slug="test-news")

        post_response = self.client.post(
            reverse("admin_blog_post_create"),
            {
                "category": category.pk,
                "title": "Новий пост",
                "slug": "new-post",
                "excerpt": "Короткий опис",
                "content_html": "<p>Контент</p>",
                "published_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "is_published": "on",
                "seo_title": "SEO title",
                "seo_description": "SEO description",
            },
            secure=True,
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertTrue(BlogPost.objects.filter(slug="new-post", category=category).exists())

    def test_custom_admin_can_delete_post_and_empty_category(self):
        self.client.force_login(self.staff)
        empty_category = BlogCategory.objects.create(name="Порожня категорія", slug="empty-category")

        post_response = self.client.post(
            reverse("admin_blog_post_delete", kwargs={"pk": self.post.pk}),
            secure=True,
        )
        self.assertEqual(post_response.status_code, 302)
        self.assertFalse(BlogPost.objects.filter(pk=self.post.pk).exists())

        category_response = self.client.post(
            reverse("admin_blog_category_delete", kwargs={"pk": empty_category.pk}),
            secure=True,
        )
        self.assertEqual(category_response.status_code, 302)
        self.assertFalse(BlogCategory.objects.filter(pk=empty_category.pk).exists())

    def test_custom_admin_does_not_delete_category_with_posts(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("admin_blog_category_delete", kwargs={"pk": self.category.pk}),
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(BlogCategory.objects.filter(pk=self.category.pk).exists())
