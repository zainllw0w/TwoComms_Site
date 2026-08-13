from io import StringIO
from unittest.mock import patch

from django.core.cache import cache, caches
from django.core.management import call_command
from django.test import TestCase

from storefront.models import Category, Product, ProductFAQ


class RefreshProductFaqsCompatibilityTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            mocked = patch(target)
            self.addCleanup(mocked.stop)
            mocked.start()

        category = Category.objects.create(
            name="Футболки", slug="tshirts", is_active=True
        )
        self.product = Product.objects.create(
            title="Refresh Test",
            slug="refresh-test",
            category=category,
            price=1000,
            status="published",
        )

    def test_refresh_skips_retired_delivery_faq_without_shifting_later_topics(self):
        legacy = (
            ("Як обрати розмір футболки?", "legacy size"),
            ("Чи можна прати футболку в машинці?", "legacy care"),
            ("Скільки триває доставка?", "legacy delivery"),
            ("Як повернути або обміняти товар?", "legacy returns"),
            ("Чи можна замовити з власним принтом?", "legacy custom"),
        )
        for order, (question, answer) in enumerate(legacy):
            ProductFAQ.objects.create(
                product=self.product,
                question=question,
                answer=answer,
                order=order,
                is_active=True,
            )

        call_command(
            "refresh_product_faqs",
            "--slug",
            self.product.slug,
            stdout=StringIO(),
        )

        faqs = list(
            ProductFAQ.objects.filter(product=self.product).order_by("order", "id")
        )
        self.assertEqual(faqs[2].question, "Скільки триває доставка?")
        self.assertEqual(faqs[2].answer, "legacy delivery")
        self.assertIn("повернути або обміняти", faqs[3].question.lower())
        self.assertIn("власним принтом", faqs[4].question.lower())
