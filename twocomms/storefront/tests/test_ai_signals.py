from unittest.mock import patch

from django.test import TestCase, override_settings

from storefront.models import Category, Product


class AIAutoGenerationSignalTests(TestCase):
    def setUp(self):
        self.feed_task_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            return_value=None,
        )
        self.product_indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.category_indexnow_patcher = patch("storefront.cache_signals.enqueue_indexnow_urls")
        self.feed_task_patcher.start()
        self.product_indexnow_patcher.start()
        self.category_indexnow_patcher.start()
        self.addCleanup(self.feed_task_patcher.stop)
        self.addCleanup(self.product_indexnow_patcher.stop)
        self.addCleanup(self.category_indexnow_patcher.stop)
        self.category = Category.objects.create(
            name="AI Signal Category",
            slug="ai-signal-category",
            is_active=True,
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        USE_AI_KEYWORDS=True,
        USE_AI_DESCRIPTIONS=True,
        AUTO_GENERATE_AI_CONTENT_ON_CREATE=False,
    )
    def test_product_creation_does_not_enqueue_ai_task_when_auto_generation_disabled(self):
        with patch("storefront.ai_signals.generate_ai_content_for_product_task.delay") as delay:
            Product.objects.create(
                title="No AI Product",
                slug="no-ai-product",
                category=self.category,
                price=1000,
                status="published",
            )

        delay.assert_not_called()

    @override_settings(
        OPENAI_API_KEY="test-key",
        USE_AI_KEYWORDS=True,
        USE_AI_DESCRIPTIONS=True,
        AUTO_GENERATE_AI_CONTENT_ON_CREATE=False,
    )
    def test_category_creation_does_not_enqueue_ai_task_when_auto_generation_disabled(self):
        with patch("storefront.ai_signals.generate_ai_content_for_category_task.delay") as delay:
            Category.objects.create(
                name="No AI Category",
                slug="no-ai-category",
                is_active=True,
            )

        delay.assert_not_called()
