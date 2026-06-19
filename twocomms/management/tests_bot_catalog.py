"""Тести Phase 2 / Task 8 — каталог бота збагачений візуальними відбитками."""
from django.test import TestCase

from management.services.bot_catalog import get_catalog_context


class CatalogFingerprintTests(TestCase):
    def test_catalog_includes_fingerprint_summary(self):
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import Category, Product, ProductStatus

        cat = Category.objects.create(name="Худі", slug="hudi-cat")
        p = Product.objects.create(
            title="Худі Kharkiv", slug="hk-cat", category=cat, price=950,
            status=ProductStatus.PUBLISHED,
        )
        color = Color.objects.create(name="чорний", primary_hex="#000000")
        ProductColorVariant.objects.create(
            product=p, color=color, stock=5,
            metadata={"bot_vision": {"summary": "худі з єнотом і написом Харків"}},
        )
        text = get_catalog_context(force=True)
        self.assertIn("Харків", text)
        self.assertIn("єнот", text)  # приходить лише з відбитка (не з назви)
