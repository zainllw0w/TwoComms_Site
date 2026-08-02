import importlib

from django.apps import apps
from django.core.exceptions import ValidationError
from django.test import TestCase

from fable5.models import ProductInventoryPolicy, VariantBlankLink
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product
from warehouse.models import StorageCategory, StorageSubcategory


class ProductInventoryPolicyTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Inventory policy",
            slug="inventory-policy",
        )
        self.product = Product.objects.create(
            title="Inventory product",
            slug="inventory-product",
            category=self.category,
            price=900,
        )

    def test_supported_inventory_policy_sources_are_explicit(self):
        for source in ("warehouse", "catalog_variant", "untracked"):
            with self.subTest(source=source):
                policy = ProductInventoryPolicy(product=self.product, source=source)
                policy.full_clean()
                self.assertEqual(policy.source, source)

    def test_policy_source_is_required_for_checkout_truth(self):
        with self.assertRaises(ValidationError):
            ProductInventoryPolicy(product=self.product, source="").full_clean()

    def test_product_has_only_one_inventory_policy(self):
        ProductInventoryPolicy.objects.create(product=self.product, source="untracked")

        with self.assertRaises(ValidationError):
            ProductInventoryPolicy(product=self.product, source="warehouse").full_clean()


class ProductInventoryPolicyBackfillTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Inventory migration",
            slug="inventory-migration",
        )

    def create_product(self, slug, **overrides):
        values = {
            "title": slug.replace("-", " ").title(),
            "slug": slug,
            "category": self.category,
            "price": 1000,
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def test_backfill_uses_only_structured_blank_link_evidence(self):
        warehouse_product = self.create_product("warehouse-evidence")
        variant = ProductColorVariant.objects.create(
            product=warehouse_product,
            color=Color.objects.create(name="Warehouse black", primary_hex="#111111"),
            stock=0,
        )
        storage_category = StorageCategory.objects.create(name="Blank garments")
        blank = StorageSubcategory.objects.create(
            category=storage_category,
            name="Structured black blank",
        )
        VariantBlankLink.objects.create(
            variant=variant,
            option_key="fit=classic",
            storage_subcategory=blank,
        )
        positive_stock = self.create_product(
            "positive-stock-is-not-policy",
            description="Warehouse product inferred from generated description",
        )
        ProductColorVariant.objects.create(
            product=positive_stock,
            color=Color.objects.create(name="Catalog red", primary_hex="#aa0000"),
            stock=50,
        )
        ordinary_product = self.create_product("ordinary-untracked")

        migration = importlib.import_module(
            "fable5.migrations.0008_product_inventory_policy"
        )
        migration.backfill_product_inventory_policies(apps, None)

        policies = {
            policy.product_id: policy.source
            for policy in ProductInventoryPolicy.objects.all()
        }
        self.assertEqual(policies[warehouse_product.pk], "warehouse")
        self.assertEqual(policies[positive_stock.pk], "untracked")
        self.assertEqual(policies[ordinary_product.pk], "untracked")
        self.assertNotIn("catalog_variant", policies.values())
