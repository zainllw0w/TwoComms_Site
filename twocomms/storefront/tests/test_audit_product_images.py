"""Phase 21 (PR-6, T16.2) — regression for the audit_product_images
management command.
"""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from storefront.models import Category, Product


class AuditProductImagesCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Audit", slug="audit-cat", is_active=True,
        )
        # No images at all — should appear in the report.
        cls.empty_product = Product.objects.create(
            title="Empty Tee", slug="empty-tee",
            category=cls.category, price=300, status="published",
        )
        # Draft — must be ignored even though it has no images.
        cls.draft_product = Product.objects.create(
            title="Draft Tee", slug="draft-tee",
            category=cls.category, price=300, status="draft",
        )

    def _run(self, *flags):
        out = StringIO()
        call_command("audit_product_images", *flags, stdout=out)
        return out.getvalue()

    def test_lists_published_products_with_zero_images(self):
        output = self._run()
        self.assertIn("empty-tee", output)
        self.assertIn("Empty Tee", output)

    def test_does_not_include_draft_products(self):
        output = self._run()
        self.assertNotIn("draft-tee", output)

    def test_csv_output_has_header_and_row(self):
        output = self._run("--csv")
        lines = [line for line in output.splitlines() if line.strip()]
        self.assertEqual(lines[0], "product_id,category_slug,slug,title,image_count")
        self.assertTrue(any("empty-tee" in line for line in lines[1:]))

    def test_limit_caps_rows(self):
        for i in range(3):
            Product.objects.create(
                title=f"Empty Tee {i}", slug=f"empty-tee-{i}",
                category=self.category, price=300, status="published",
            )
        output = self._run("--limit", "2", "--csv")
        body_rows = [l for l in output.splitlines() if l and not l.startswith("product_id")]
        self.assertEqual(len(body_rows), 2)
