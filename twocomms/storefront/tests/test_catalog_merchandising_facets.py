from django.test import TestCase

from storefront.models import Category, Product
from storefront.services.catalog_facets import (
    filter_products_by_facets,
    normalize_catalog_facet_state,
)

from product_catalog.models import (
    AudienceTag,
    ColorProfile,
    MerchCollection,
    ProductAudience,
    ProductMerchCollection,
    VariantSizeRule,
)
from productcolors.models import Color, ProductColorVariant


class CatalogFacetContractTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="tshirts")
        self.unisex, _ = AudienceTag.objects.update_or_create(
            code="unisex",
            defaults={
                "label_uk": "Унісекс",
                "label_ru": "Унисекс",
                "label_en": "Unisex",
                "order": 0,
            },
        )
        self.women, _ = AudienceTag.objects.update_or_create(
            code="women",
            defaults={
                "label_uk": "Жіночі",
                "label_ru": "Женские",
                "label_en": "Women",
                "order": 1,
            },
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
        self.unassigned = Product.objects.create(
            title="No collection assignment",
            slug="no-collection-assignment",
            category=self.category,
            price=1090,
            status="published",
        )
        ProductAudience.objects.create(product=self.both, tag=self.unisex)
        ProductAudience.objects.create(product=self.both, tag=self.women)
        ProductAudience.objects.create(product=self.only_unisex, tag=self.unisex)

        self.brigades, _ = MerchCollection.objects.update_or_create(
            slug="brigades",
            defaults={
                "kind": MerchCollection.Kind.THEME,
                "name_uk": "Бригади",
                "name_ru": "Бригады",
                "name_en": "Brigades",
                "order": 20,
            },
        )
        self.brigade_225, _ = MerchCollection.objects.update_or_create(
            slug="225",
            defaults={
                "kind": MerchCollection.Kind.BRIGADE,
                "parent": self.brigades,
                "name_uk": "225 ОШП",
                "name_ru": "225 ОШП",
                "name_en": "225 Assault Regiment",
                "order": 30,
            },
        )
        self.brigade_127, _ = MerchCollection.objects.update_or_create(
            slug="127",
            defaults={
                "kind": MerchCollection.Kind.BRIGADE,
                "parent": self.brigades,
                "name_uk": "127 бригада",
                "name_ru": "127 бригада",
                "name_en": "127 Brigade",
                "order": 31,
            },
        )
        ProductMerchCollection.objects.create(
            product=self.both,
            collection=self.brigade_225,
        )
        ProductMerchCollection.objects.create(
            product=self.only_unisex,
            collection=self.brigade_127,
        )

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

        self.assertCountEqual(result, [self.both, self.only_unisex, self.unassigned])

    def test_parent_theme_matches_products_assigned_to_active_children(self):
        state = normalize_catalog_facet_state({"theme": ["brigades"]})

        result = filter_products_by_facets(
            Product.objects.filter(category=self.category), state
        )

        self.assertCountEqual(result, [self.both, self.only_unisex])

    def test_specific_brigade_filter_matches_only_exact_assignment(self):
        state = normalize_catalog_facet_state({"collection": ["225"]})

        result = filter_products_by_facets(
            Product.objects.filter(category=self.category), state
        )

        self.assertEqual(list(result), [self.both])

    def test_redundant_parent_theme_is_removed_when_child_is_selected(self):
        state = normalize_catalog_facet_state(
            {"theme": ["brigades"], "collection": ["225"]}
        )

        self.assertNotIn("theme", state)
        self.assertEqual(state["collection"], ("225",))

    def test_multiple_specific_brigades_use_strict_and(self):
        ProductMerchCollection.objects.create(
            product=self.both,
            collection=self.brigade_127,
            order=1,
        )
        state = normalize_catalog_facet_state({"collection": ["225", "127"]})

        result = filter_products_by_facets(
            Product.objects.filter(category=self.category), state
        )

        self.assertEqual(list(result), [self.both])

    def test_unknown_or_inactive_collection_values_are_ignored(self):
        self.brigade_127.is_active = False
        self.brigade_127.save(update_fields=["is_active"])

        state = normalize_catalog_facet_state(
            {"collection": ["225", "127", "missing"]}
        )

        self.assertEqual(state["collection"], ("225",))

    def test_inventory_facets_normalize_without_treating_informational_3xl_as_sellable(self):
        state = normalize_catalog_facet_state(
            {
                "availability": ["in_stock"],
                "size": ["M", "3XL"],
                "thermo": ["thermo"],
                "color": ["black", "red"],
            },
            allowed_colors={"black", "red"},
        )

        self.assertEqual(state["availability"], ("in_stock",))
        self.assertEqual(state["size"], ("M",))
        self.assertEqual(state["thermo"], ("thermo",))
        self.assertEqual(state["color"], ("black", "red"))

    def test_variant_facets_use_size_rules_and_color_profile_truth(self):
        thermo_color = Color.objects.create(
            name="Thermo black",
            primary_hex="#111111",
        )
        thermo_variant = ProductColorVariant.objects.create(
            product=self.both,
            color=thermo_color,
            is_default=True,
        )
        ColorProfile.objects.create(color=thermo_color, is_thermo=True)
        VariantSizeRule.objects.create(
            variant=thermo_variant,
            fit_code="",
            size="M",
            is_enabled=True,
            stock=2,
        )

        ordinary_color = Color.objects.create(
            name="Ordinary red",
            primary_hex="#aa2222",
        )
        ordinary_variant = ProductColorVariant.objects.create(
            product=self.only_unisex,
            color=ordinary_color,
            is_default=True,
        )
        VariantSizeRule.objects.create(
            variant=ordinary_variant,
            fit_code="",
            size="M",
            is_enabled=True,
            stock=0,
        )

        state = normalize_catalog_facet_state(
            {"availability": ["in_stock"], "size": ["M"], "thermo": ["thermo"]}
        )
        result = filter_products_by_facets(
            Product.objects.filter(category=self.category), state
        )

        self.assertEqual(list(result), [self.both])
