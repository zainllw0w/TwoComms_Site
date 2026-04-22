from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from storefront.models import Category, Product
from storefront.services.indexnow import get_core_indexnow_urls, submit_indexnow_urls


@override_settings(
    SITE_BASE_URL="https://twocomms.shop",
    INDEXNOW_ENABLED=True,
    INDEXNOW_KEY="abc123",
    INDEXNOW_ENDPOINT="https://api.indexnow.org/indexnow",
    INDEXNOW_TIMEOUT=2.5,
)
class IndexNowServiceTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_core_indexnow_urls_skip_pricelist_duplicate(self):
        urls = get_core_indexnow_urls()

        self.assertIn("https://twocomms.shop/wholesale/", urls)
        self.assertNotIn("https://twocomms.shop/pricelist/", urls)

    @patch("storefront.services.indexnow.requests.post")
    def test_submit_indexnow_urls_posts_expected_payload(self, post_mock):
        post_mock.return_value.raise_for_status.return_value = None

        submitted = submit_indexnow_urls(
            [
                "https://twocomms.shop/product/test-product/",
                "https://twocomms.shop/product/test-product/",
                "https://example.com/ignored/",
            ]
        )

        self.assertTrue(submitted)
        post_mock.assert_called_once()
        self.assertEqual(
            post_mock.call_args.kwargs["json"],
            {
                "host": "twocomms.shop",
                "key": "abc123",
                "keyLocation": "https://twocomms.shop/abc123.txt",
                "urlList": ["https://twocomms.shop/product/test-product/"],
            },
        )

    @override_settings(INDEXNOW_KEY="")
    @patch("storefront.services.indexnow.requests.post")
    def test_submit_indexnow_urls_skips_when_key_missing(self, post_mock):
        submitted = submit_indexnow_urls(["https://twocomms.shop/product/test-product/"])

        self.assertFalse(submitted)
        post_mock.assert_not_called()

    def test_indexnow_key_file_returns_configured_key(self):
        response = self.client.get("/abc123.txt", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "abc123")

    def test_indexnow_key_file_returns_404_for_unknown_key(self):
        response = self.client.get("/wrong-key.txt", secure=True)

        self.assertEqual(response.status_code, 404)


@override_settings(
    SITE_BASE_URL="https://twocomms.shop",
    INDEXNOW_ENABLED=True,
    INDEXNOW_KEY="abc123",
)
class IndexNowSignalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.category = Category.objects.create(name="Hoodies", slug="hoodie")

    @patch("storefront.tasks.submit_indexnow_urls_task.delay")
    def test_published_product_save_enqueues_indexnow_after_commit(self, indexnow_delay_mock):
        with self.captureOnCommitCallbacks(execute=True):
            Product.objects.create(
                title="Test Product",
                slug="test-product",
                category=self.category,
                price=1000,
                status="published",
            )

        indexnow_delay_mock.assert_called_once_with(["https://twocomms.shop/product/test-product/"])

    @patch("storefront.tasks.submit_indexnow_urls_task.delay")
    @patch("storefront.signals.generate_google_merchant_feed_task.apply_async")
    def test_published_product_save_schedules_google_merchant_feed_when_lock_absent(
        self,
        merchant_feed_mock,
        indexnow_delay_mock,
    ):
        Product.objects.create(
            title="Merchant Feed Product",
            slug="merchant-feed-product",
            category=self.category,
            price=1000,
            status="published",
        )

        merchant_feed_mock.assert_called_once_with(countdown=300)
        indexnow_delay_mock.assert_not_called()
