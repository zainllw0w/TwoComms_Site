from django.test import TestCase

from storefront.models import Category, Product
from storefront.services.catalog_facets import (
    filter_products_by_facets,
    normalize_catalog_facet_state,
)

from fable5.models import AudienceTag, ProductAudience


class CatalogFacetContractTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="tshirts")
        self.unisex = AudienceTag.objects.create(
            code="unisex", label_uk="Унісекс", label_ru="Унисекс", label_en="Unisex", order=0
        )
        self.women = AudienceTag.objects.create(
            code="women", label_uk="Жіночі", label_ru="Женские", label_en="Women", order=1
        )
        self.both = Product.objects.create(
            title="Both audiences",
            slug="both-audiences",
            category=self.category,
            price=1090,
            status="published",
        )
        self.only_unisex = Product.objects.create(
            title="Unisex only",
            slug="unisex-only",
            category=self.category,
            price=1090,
            status="published",
        )
        ProductAudience.objects.create(product=self.both, tag=self.unisex)
        ProductAudience.objects.create(product=self.both, tag=self.women)
        ProductAudience.objects.create(product=self.only_unisex, tag=self.unisex)

    def test_repeated_query_keys_are_normalized_in_stable_order(self):
        state = normalize_catalog_facet_state(
            {
                "audience": ["women", "unisex", "women"],
                "fit": ["oversize", "classic"],
                "size": ["XL", "M", "XL"],
                "unknown": ["ignored"],
            }
        )

        self.assertEqual(state["audience"], ("unisex", "women"))
        self.assertEqual(state["fit"], ("classic", "oversize"))
        self.assertEqual(state["size"], ("M", "XL"))
        self.assertNotIn("unknown", state)

    def test_audience_multi_select_is_strict_and(self):
        state = normalize_catalog_facet_state({"audience": ["unisex", "women"]})

        result = filter_products_by_facets(
            Product.objects.filter(category=self.category), state
        )

        self.assertEqual(list(result), [self.both])

    def test_empty_audience_does_not_filter_products(self):
        state = normalize_catalog_facet_state({"audience": []})

        result = filter_products_by_facets(
            Product.objects.filter(category=self.category), state
        )

        self.assertCountEqual(result, [self.both, self.only_unisex])
