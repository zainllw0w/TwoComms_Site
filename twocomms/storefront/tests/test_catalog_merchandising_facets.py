from unittest.mock import patch

from django.core.cache import cache, caches
from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from storefront.models import Category, Product
from storefront.services.catalog_facets import (
    filter_products_by_facets,
    normalize_catalog_facet_state,
    redundant_parent_theme_slugs,
)
from storefront.services.catalog_helpers import (
    get_public_category_version,
    get_public_product_order_version,
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
        cache.clear()
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

    def test_supported_fit_aliases_normalize_to_public_fit_codes(self):
        state = normalize_catalog_facet_state(
            {"fit": ["regular", "класичний"]}
        )

        self.assertEqual(state["fit"], ("classic", "standard"))

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

    def test_redundant_parent_theme_url_redirects_to_leaf_collection(self):
        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {
                "theme": "brigades",
                "collection": "225",
                "page": "2",
                "utm_source": "audit",
            },
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "/catalog/tshirts/?collection=225&page=2&utm_source=audit",
        )

    def test_collection_parent_contract_is_cached_after_first_lookup(self):
        query = {"theme": ["brigades"], "collection": ["225"]}

        cache.clear()
        with CaptureQueriesContext(connection) as cold_lookup:
            self.assertEqual(redundant_parent_theme_slugs(query), {"brigades"})
        with CaptureQueriesContext(connection) as repeated_lookup:
            self.assertEqual(
                redundant_parent_theme_slugs(query),
                {"brigades"},
            )

        self.assertEqual(len(cold_lookup), 1)
        self.assertEqual(len(repeated_lookup), 0)

    def test_single_taxonomy_axis_skips_cache_and_database(self):
        for query in ({"theme": ["brigades"]}, {"collection": ["225"]}):
            with self.subTest(query=query), patch.object(cache, "get") as cache_get:
                with CaptureQueriesContext(connection) as queries:
                    self.assertEqual(redundant_parent_theme_slugs(query), set())

            cache_get.assert_not_called()
            self.assertEqual(len(queries), 0)

    def test_redirect_removes_only_implied_parent_theme(self):
        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            [
                ("theme", "streetwear"),
                ("theme", "brigades"),
                ("collection", "225"),
                ("sort", "price-asc"),
            ],
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "/catalog/tshirts/?collection=225&sort=price-asc&theme=streetwear",
        )

    def test_unrelated_theme_and_collection_do_not_redirect(self):
        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"theme": "streetwear", "collection": "225"},
        )

        self.assertEqual(response.status_code, 200)

    def test_redundant_parent_redirect_does_not_write_page_cache(self):
        fragment_cache = caches["fragments"]
        with (
            patch("storefront.views.utils.cache.set") as cache_set,
            patch.object(fragment_cache, "set", wraps=fragment_cache.set) as fragment_set,
        ):
            response = self.client.get(
                reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
                {"theme": "brigades", "collection": "225"},
            )

        self.assertEqual(response.status_code, 301)
        page_cache_writes = [
            call
            for call in cache_set.call_args_list
            if call.args and str(call.args[0]).startswith("anon-page:")
        ]
        self.assertEqual(page_cache_writes, [])
        outer_fragment_writes = [
            call
            for call in fragment_set.call_args_list
            if call.args and "catalog_products_home_cards" in str(call.args[0])
        ]
        self.assertEqual(outer_fragment_writes, [])

    def test_collection_taxonomy_and_assignment_changes_bump_listing_versions(self):
        category_version = get_public_category_version()
        with self.captureOnCommitCallbacks(execute=True):
            self.brigade_225.name_uk = "225 ОШП updated"
            self.brigade_225.save(update_fields=["name_uk"])
        self.assertGreater(get_public_category_version(), category_version)

        product_version = get_public_product_order_version()
        with self.captureOnCommitCallbacks(execute=True):
            ProductMerchCollection.objects.create(
                product=self.unassigned,
                collection=self.brigade_225,
            )
        self.assertGreater(get_public_product_order_version(), product_version)

    def test_reparented_collection_uses_new_parent_after_commit(self):
        streetwear = MerchCollection.objects.create(
            slug="streetwear",
            kind=MerchCollection.Kind.THEME,
            name_uk="Стрітвір",
        )
        query = {"theme": ["brigades"], "collection": ["225"]}
        self.assertEqual(redundant_parent_theme_slugs(query), {"brigades"})

        with self.captureOnCommitCallbacks(execute=True):
            self.brigade_225.parent = streetwear
            self.brigade_225.save(update_fields=["parent"])

        self.assertEqual(redundant_parent_theme_slugs(query), set())
        self.assertEqual(
            redundant_parent_theme_slugs(
                {"theme": ["streetwear"], "collection": ["225"]}
            ),
            {"streetwear"},
        )

    def test_nested_collection_removes_selected_ancestor_theme(self):
        with self.captureOnCommitCallbacks(execute=True):
            MerchCollection.objects.create(
                slug="225-support",
                kind=MerchCollection.Kind.COLLAB,
                parent=self.brigade_225,
                name_uk="225 Support",
            )

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"theme": "brigades", "collection": "225-support"},
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "/catalog/tshirts/?collection=225-support",
        )

    def test_nested_non_root_theme_is_rejected_without_redirect(self):
        with self.captureOnCommitCallbacks(execute=True):
            MerchCollection.objects.create(
                slug="225-support",
                kind=MerchCollection.Kind.COLLAB,
                parent=self.brigade_225,
                name_uk="225 Support",
            )

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"theme": "225", "collection": "225-support"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("Location", response)

    def test_inactive_collection_is_not_redirected_before_validation(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.brigade_225.is_active = False
            self.brigade_225.save(update_fields=["is_active"])

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"theme": "brigades", "collection": "225"},
        )

        self.assertEqual(response.status_code, 404)

    def test_rolled_back_reparent_keeps_committed_taxonomy_snapshot(self):
        streetwear = MerchCollection.objects.create(
            slug="streetwear",
            kind=MerchCollection.Kind.THEME,
            name_uk="Стрітвір",
        )
        query = {"theme": ["brigades"], "collection": ["225"]}
        self.assertEqual(redundant_parent_theme_slugs(query), {"brigades"})
        initial_version = get_public_category_version()

        try:
            with transaction.atomic():
                self.brigade_225.parent = streetwear
                self.brigade_225.save(update_fields=["parent"])
                raise RuntimeError("rollback taxonomy change")
        except RuntimeError:
            pass

        self.assertEqual(redundant_parent_theme_slugs(query), {"brigades"})
        self.assertEqual(get_public_category_version(), initial_version)

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
        with self.captureOnCommitCallbacks(execute=True):
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
