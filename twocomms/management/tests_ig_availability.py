from django.test import TestCase

from fable5.models import ProductInventoryPolicy, VariantBlankLink, VariantSizeRule
from management.services.ig_availability import (
    AllocationSpec,
    AvailabilityStatus,
    resolve_allocation,
    resolve_basket_allocations,
)
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption, ProductStatus
from warehouse.models import StockItem, StorageCategory, StorageSubcategory


class CommerceAvailabilityTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Availability", slug="availability")
        self.product = Product.objects.create(
            title="Availability shirt",
            slug="availability-shirt",
            category=category,
            price=800,
            status=ProductStatus.PUBLISHED,
        )
        ProductFitOption.objects.create(
            product=self.product, code="classic", label="Classic", is_active=True
        )
        self.color = Color.objects.create(name="Black", primary_hex="#111111")
        self.variant = ProductColorVariant.objects.create(
            product=self.product, color=self.color, stock=0, slug="black"
        )
        ProductInventoryPolicy.objects.create(
            product=self.product, source=ProductInventoryPolicy.Source.WAREHOUSE
        )
        storage_category = StorageCategory.objects.create(name="T-shirts")
        self.subcategory = StorageSubcategory.objects.create(
            category=storage_category, name="Classic blank"
        )

    def spec(self, *, size="M", fit_code="classic", quantity=1):
        return AllocationSpec(
            product_id=self.product.pk,
            color_variant_id=self.variant.pk,
            size=size,
            fit_code=fit_code,
            quantity=quantity,
        )

    def link_blank(self, *, quantity=2, size="M", option_key="fit=classic"):
        VariantBlankLink.objects.create(
            variant=self.variant,
            option_key=option_key,
            storage_subcategory=self.subcategory,
        )
        StockItem.objects.create(
            subcategory=self.subcategory,
            color=self.color,
            size=size,
            quantity=quantity,
        )

    def test_warehouse_policy_ignores_legacy_zero_variant_and_size_stock(self):
        self.link_blank(quantity=2)
        VariantSizeRule.objects.create(
            variant=self.variant,
            fit_code="classic",
            size="M",
            stock=0,
            is_enabled=True,
        )

        result = resolve_allocation(self.spec())

        self.assertEqual(result.status, AvailabilityStatus.ALLOCATABLE)

    def test_missing_blank_link_is_unknown_not_catalog_fallback(self):
        self.assertEqual(
            resolve_allocation(self.spec()).status,
            AvailabilityStatus.UNKNOWN,
        )

    def test_exact_checkout_match_never_uses_graceful_category_fallback(self):
        self.link_blank(size="L")

        result = resolve_allocation(self.spec(size="M"))

        self.assertEqual(result.status, AvailabilityStatus.UNAVAILABLE)

    def test_lines_sharing_one_allocation_are_checked_as_aggregate_quantity(self):
        self.link_blank(quantity=1)

        result = resolve_basket_allocations((self.spec(), self.spec()))

        self.assertEqual(result.status, AvailabilityStatus.UNAVAILABLE)

    def test_missing_fit_does_not_guess_between_warehouse_mappings(self):
        self.link_blank(option_key="fit=classic")
        VariantBlankLink.objects.create(
            variant=self.variant,
            option_key="fit=oversize",
            storage_subcategory=self.subcategory,
        )

        result = resolve_allocation(self.spec(fit_code=""))

        self.assertEqual(result.status, AvailabilityStatus.UNKNOWN)
        self.assertEqual(result.reason, "inventory_mapping_ambiguous")
