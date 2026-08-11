from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from storefront.models import Category, IndexNowSubmission, Product
from storefront.services.indexnow import get_core_indexnow_urls, submit_indexnow_urls


@override_settings(
    SITE_BASE_URL="https://twocomms.shop",
    INDEXNOW_ENABLED=True,
    INDEXNOW_KEY="abc12345",
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
        post_mock.return_value.status_code = 202
        post_mock.return_value.text = ""

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
                "key": "abc12345",
                "keyLocation": "https://twocomms.shop/abc12345.txt",
                "urlList": ["https://twocomms.shop/product/test-product/"],
            },
        )
        submission = IndexNowSubmission.objects.get(
            url="https://twocomms.shop/product/test-product/"
        )
        self.assertEqual(submission.status, IndexNowSubmission.STATUS_SUCCESS)
        self.assertEqual(submission.http_status, 202)

    @patch("storefront.services.indexnow.requests.post")
    def test_submit_indexnow_urls_records_failed_api_acceptance(self, post_mock):
        post_mock.return_value.status_code = 400
        post_mock.return_value.text = "invalid key"

        submitted = submit_indexnow_urls(
            ["https://twocomms.shop/product/rejected-product/"]
        )

        self.assertFalse(submitted)
        submission = IndexNowSubmission.objects.get(
            url="https://twocomms.shop/product/rejected-product/"
        )
        self.assertEqual(submission.status, IndexNowSubmission.STATUS_FAILED)
        self.assertEqual(submission.http_status, 400)
        self.assertIn("invalid key", submission.error_message)

    @override_settings(INDEXNOW_KEY="")
    @patch("storefront.services.indexnow.requests.post")
    def test_submit_indexnow_urls_skips_when_key_missing(self, post_mock):
        submitted = submit_indexnow_urls(["https://twocomms.shop/product/test-product/"])

        self.assertFalse(submitted)
        post_mock.assert_not_called()

    def test_indexnow_key_file_returns_configured_key(self):
        response = self.client.get("/abc12345.txt", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "abc12345")

    @override_settings(INDEXNOW_KEY="abc-1234")
    def test_indexnow_key_file_accepts_official_hyphenated_key(self):
        response = self.client.get("/abc-1234.txt", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "abc-1234")

    def test_indexnow_key_file_returns_404_for_unknown_key(self):
        response = self.client.get("/wrong-key.txt", secure=True)

        self.assertEqual(response.status_code, 404)


@override_settings(
    SITE_BASE_URL="https://twocomms.shop",
    INDEXNOW_ENABLED=True,
    INDEXNOW_KEY="abc12345",
)
class IndexNowSignalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.category = Category.objects.create(name="Hoodies", slug="hoodie")

    @patch("storefront.signals.enqueue_google_indexing_urls")
    @patch("storefront.signals.enqueue_indexnow_urls")
    def test_published_product_save_enqueues_indexnow_after_commit(
        self,
        indexnow_enqueue_mock,
        google_enqueue_mock,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            Product.objects.create(
                title="Test Product",
                slug="test-product",
                category=self.category,
                price=1000,
                status="published",
            )

        expected_urls = ["https://twocomms.shop/product/test-product/"]
        indexnow_enqueue_mock.assert_called_once_with(expected_urls)
        google_enqueue_mock.assert_called_once_with(expected_urls)

    @patch("storefront.signals.enqueue_google_indexing_urls")
    @patch("storefront.signals.enqueue_indexnow_urls")
    @patch("storefront.signals.mark_feeds_dirty")
    def test_published_product_save_schedules_google_merchant_feed_when_lock_absent(
        self,
        mark_feeds_dirty_mock,
        indexnow_enqueue_mock,
        google_enqueue_mock,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            Product.objects.create(
                title="Merchant Feed Product",
                slug="merchant-feed-product",
                category=self.category,
                price=1000,
                status="published",
            )

        mark_feeds_dirty_mock.assert_called_once()
        expected_urls = ["https://twocomms.shop/product/merchant-feed-product/"]
        indexnow_enqueue_mock.assert_called_once_with(expected_urls)
        google_enqueue_mock.assert_called_once_with(expected_urls)
