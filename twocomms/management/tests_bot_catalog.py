"""Тести Phase 2 / Task 8 — каталог бота збагачений візуальними відбитками."""
from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext

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


class CatalogProductIdTests(TestCase):
    def test_catalog_includes_product_id(self):
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import Category, Product, ProductStatus

        cat = Category.objects.create(name="Х", slug="hudi-id")
        p = Product.objects.create(
            title="Тест-товар", slug="t-id", category=cat, price=500, status=ProductStatus.PUBLISHED
        )
        color = Color.objects.create(name="ч", primary_hex="#111111")
        ProductColorVariant.objects.create(product=p, color=color, stock=1)
        text = get_catalog_context(force=True)
        self.assertIn(f"id={p.id}", text)


class CatalogVariantPriceTests(TestCase):
    def test_catalog_variant_pricing_uses_a_bounded_query_graph(self):
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Футболки", slug="priced-query-budget")
        color = Color.objects.create(name="Чорний", primary_hex="#101010")
        for index in range(3):
            product = Product.objects.create(
                title=f"Футболка {index}",
                slug=f"priced-query-product-{index}",
                category=category,
                price=800 + index,
                status=ProductStatus.PUBLISHED,
            )
            ProductColorVariant.objects.create(
                product=product,
                color=color,
                price_override=900 + index,
                is_default=True,
            )

        with CaptureQueriesContext(connection) as captured:
            text = get_catalog_context(force=True)

        self.assertIn("Футболка 0", text)
        self.assertLessEqual(
            len(captured),
            35,
            f"catalog pricing query budget exceeded: {len(captured)}",
        )

    def test_catalog_never_falls_back_to_base_price_for_unresolved_variant_matrix(self):
        from fable5.models import GarmentFlow, GarmentFlowCategory
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Складні", slug="priced-matrix")
        product = Product.objects.create(
            title="Конфігурований товар",
            slug="priced-matrix-product",
            category=category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        color = Color.objects.create(name="Тестовий", primary_hex="#123456")
        ProductColorVariant.objects.create(
            product=product,
            color=color,
            price_override=1450,
            is_default=True,
        )
        axes = [
            {
                "code": f"option{index}",
                "label": f"Опція {index}",
                "options": [
                    {"code": "a", "label": "A"},
                    {"code": "b", "label": "B"},
                ],
            }
            for index in range(8)
        ]
        flow = GarmentFlow.objects.create(
            code="priced-matrix-flow",
            name="Велика матриця",
            axes=axes,
        )
        GarmentFlowCategory.objects.create(flow=flow, category=category)

        with self.assertLogs(
            "management.services.ig_catalog_pricing", level="WARNING"
        ):
            text = get_catalog_context(force=True)

        self.assertIn(
            f"id={product.pk} | Конфігурований товар — ціна залежить від конфігурації",
            text,
        )
        self.assertNotIn("Конфігурований товар — 1090 грн", text)

    def test_catalog_exposes_authoritative_price_for_each_adjusted_variant(self):
        from fable5.models import ColorProfile, VariantDetails, VariantFitRule
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import Category, Product, ProductFitOption, ProductStatus

        category = Category.objects.create(name="Футболки", slug="priced-variants")
        product = Product.objects.create(
            title="Футболка Бойова квіточка",
            slug="priced-flower-shirt",
            category=category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        ProductFitOption.objects.create(
            product=product,
            code="oversize",
            label="Оверсайз",
            is_default=True,
        )
        white = Color.objects.create(name="Білий", primary_hex="#FFFFFF")
        ProductColorVariant.objects.create(
            product=product,
            color=white,
            price_override=1090,
        )
        color = Color.objects.create(name="Термо-зелена", primary_hex="#A2AB92")
        variant = ProductColorVariant.objects.create(
            product=product,
            color=color,
            price_override=1050,
            is_default=True,
        )
        ColorProfile.objects.create(color=color, is_thermo=True)
        VariantDetails.objects.create(
            variant=variant,
            price_delta=400,
            price_delta_reason="термохромна тканина",
        )
        VariantFitRule.objects.create(
            variant=variant,
            fit_code="oversize",
            is_enabled=True,
        )

        text = get_catalog_context(force=True)

        self.assertIn(
            f"id={product.pk} | Футболка Бойова квіточка — 1090-1450 грн",
            text,
        )
        self.assertIn("Білий (variant_id=", text)
        self.assertIn("ціна 1090 грн", text)
        self.assertIn(
            f"Термо-зелена (variant_id={variant.pk}, ціна 1450 грн",
            text,
        )
        self.assertIn("термохромна тканина", text)
        self.assertIn("фасони: oversize", text)

    def test_catalog_exposes_fit_specific_prices_for_the_same_variant(self):
        from fable5.models import ProductOptionProfile
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import Category, Product, ProductFitOption, ProductStatus

        category = Category.objects.create(name="Футболки", slug="priced-fits")
        product = Product.objects.create(
            title="Футболка 225ОШП",
            slug="priced-fit-shirt",
            category=category,
            price=660,
            status=ProductStatus.PUBLISHED,
        )
        ProductFitOption.objects.create(
            product=product,
            code="classic",
            label="Класичний",
            is_default=True,
        )
        ProductFitOption.objects.create(
            product=product,
            code="oversize",
            label="Оверсайз",
        )
        color = Color.objects.create(name="Чорний", primary_hex="#111111")
        variant = ProductColorVariant.objects.create(
            product=product,
            color=color,
            price_override=800,
            is_default=True,
        )
        ProductOptionProfile.objects.create(
            product=product,
            option_key="fit=oversize",
            option_values={"fit": "oversize"},
            price_delta=150,
            price_delta_reason="щільніша тканина",
        )

        text = get_catalog_context(force=True)

        self.assertIn(f"Чорний (variant_id={variant.pk}, ціни:", text)
        self.assertIn("fit=classic=800 грн", text)
        self.assertIn("fit=oversize=950 грн", text)
