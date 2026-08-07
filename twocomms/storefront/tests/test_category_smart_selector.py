"""Contract tests for the category-scoped Variant 3 Smart Selector."""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase
from django.urls import reverse

from productcolors.models import Color, ProductColorVariant
from fable5.models import (
    AudienceTag,
    MerchCollection,
    ProductAudience,
    ProductMerchCollection,
)
from storefront.models import Category, CategoryColorLanding, Product, ProductFitOption


class SmartSelectorCategoryTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        merchant_patcher = patch("storefront.signals.generate_google_merchant_feed_task.apply_async")
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()

        self.tshirts = Category.objects.create(
            name="Футболки",
            slug="tshirts",
            seo_h1="Футболки TwoComms",
            seo_description="Футболки з авторськими принтами TwoComms.",
            description="Футболки з щільної бавовни та авторським DTF-друком.",
        )
        self.hoodie = Category.objects.create(name="Худі", slug="hoodie")
        self.long_sleeve = Category.objects.create(name="Лонгсліви", slug="long-sleeve")
        self.other = Category.objects.create(name="Інше", slug="other")

    def create_product(self, *, category, title="Smart Product", slug="smart-product", price=1190, discount_percent=None):
        return Product.objects.create(
            title=title,
            slug=slug,
            category=category,
            price=price,
            discount_percent=discount_percent,
            status="published",
        )

    def add_fit_options(self, product, *codes):
        for order, code in enumerate(codes):
            ProductFitOption.objects.create(
                product=product,
                code=code,
                label=code.title(),
                order=order,
                is_default=order == 0,
                is_active=True,
            )

    def create_merch_taxonomy(self):
        military = MerchCollection.objects.create(
            slug="military",
            kind=MerchCollection.Kind.THEME,
            name_uk="Мілітарі",
            name_ru="Милитари",
            name_en="Military",
            order=10,
        )
        brigades = MerchCollection.objects.create(
            slug="brigades",
            kind=MerchCollection.Kind.THEME,
            name_uk="Бригади",
            name_ru="Бригады",
            name_en="Brigades",
            order=20,
        )
        brigade_225 = MerchCollection.objects.create(
            slug="225",
            kind=MerchCollection.Kind.BRIGADE,
            parent=brigades,
            name_uk="225 ОШП",
            name_ru="225 ОШП",
            name_en="225 Assault Regiment",
            order=21,
            indexable=True,
        )
        brigade_127 = MerchCollection.objects.create(
            slug="127",
            kind=MerchCollection.Kind.BRIGADE,
            parent=brigades,
            name_uk="127 бригада",
            name_ru="127 бригада",
            name_en="127 Brigade",
            order=22,
        )
        streetwear = MerchCollection.objects.create(
            slug="streetwear",
            kind=MerchCollection.Kind.THEME,
            name_uk="Стрітвір",
            name_ru="Стритвир",
            name_en="Streetwear",
            order=30,
        )
        kharkiv = MerchCollection.objects.create(
            slug="kharkiv",
            kind=MerchCollection.Kind.CITY,
            name_uk="Харків",
            name_ru="Харьков",
            name_en="Kharkiv",
            order=40,
        )
        return {
            "military": military,
            "brigades": brigades,
            "225": brigade_225,
            "127": brigade_127,
            "streetwear": streetwear,
            "kharkiv": kharkiv,
        }

    def create_audience_tags(self):
        return {
            code: AudienceTag.objects.create(
                code=code,
                label_uk=label,
                label_ru=label,
                label_en=code.title(),
                order=order,
            )
            for order, (code, label) in enumerate(
                (("unisex", "Унісекс"), ("women", "Жіночий"), ("men", "Чоловічий"))
            )
        }

    def test_supported_category_renders_smart_selector_and_preserves_seo_contract(self):
        product = self.create_product(category=self.tshirts)
        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["smart_selector_enabled"])
        self.assertContains(response, 'data-smart-selector="true"')
        self.assertContains(response, 'data-smart-product-item')
        self.assertContains(response, 'data-smart-filter-sheet')
        self.assertContains(response, 'data-smart-desktop-rail')
        self.assertContains(response, "Футболки TwoComms")
        self.assertContains(response, "Футболки з щільної бавовни")
        self.assertContains(response, reverse("product", kwargs={"slug": product.slug}))
        self.assertContains(response, 'class="catalog-pagination"')

    def test_supported_category_uses_variant_3_product_card_markup(self):
        product = self.create_product(category=self.tshirts, slug="variant-3-card")
        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="smart-product-card"')
        self.assertContains(response, 'data-smart-product-card')
        self.assertContains(response, 'class="smart-product-card__media"')
        self.assertContains(response, f'href="{reverse("product", kwargs={"slug": product.slug})}"')
        self.assertNotContains(response, 'class="home-product-card card product')

    def test_quick_facets_precede_catalog_command_and_product_grid(self):
        self.create_product(category=self.tshirts, slug="quick-facet-order")
        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        html = response.content.decode()
        quick_facets_position = html.index('class="smart-selector__quick-facets"')
        command_position = html.index('class="smart-selector__command"')
        grid_position = html.index('class="smart-selector__grid"')

        self.assertLess(quick_facets_position, command_position)
        self.assertLess(command_position, grid_position)

    def test_category_tabs_use_real_urls_and_selected_category(self):
        self.create_product(category=self.hoodie)
        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "hoodie"}))

        self.assertEqual(response.context["smart_selector_active_category"].slug, "hoodie")
        self.assertEqual(
            [tab.slug for tab in response.context["smart_selector_category_tabs"]],
            ["tshirts", "hoodie", "long-sleeve"],
        )
        self.assertContains(response, f'href="{reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"})}"')
        self.assertContains(response, f'href="{reverse("catalog_by_cat", kwargs={"cat_slug": "hoodie"})}"')
        self.assertContains(response, f'href="{reverse("catalog_by_cat", kwargs={"cat_slug": "long-sleeve"})}"')

    def test_fit_options_are_category_specific(self):
        tshirt = self.create_product(category=self.tshirts, slug="fit-tshirt")
        hoodie = self.create_product(category=self.hoodie, slug="fit-hoodie")
        longsleeve = self.create_product(category=self.long_sleeve, slug="fit-longsleeve")
        self.add_fit_options(tshirt, "classic", "oversize")
        self.add_fit_options(hoodie, "classic", "oversize")
        self.add_fit_options(longsleeve, "regular")

        tshirt_response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))
        hoodie_response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "hoodie"}))
        longsleeve_response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "long-sleeve"}))

        self.assertEqual(tshirt_response.context["smart_selector_fit_codes"], ["classic", "oversize"])
        self.assertEqual(hoodie_response.context["smart_selector_fit_codes"], ["classic", "oversize"])
        self.assertEqual(longsleeve_response.context["smart_selector_fit_codes"], ["standard"])

    def test_long_sleeves_keep_standard_fit_fallback_without_fit_rows(self):
        self.create_product(category=self.long_sleeve, slug="unannotated-long-sleeve")

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "long-sleeve"}))

        self.assertEqual(response.context["smart_selector_fit_codes"], ["standard"])
        self.assertContains(response, "Стандартний")
        self.assertContains(response, 'data-smart-fit="standard"')

    def test_fit_filter_matches_ukrainian_fit_labels(self):
        product = self.create_product(category=self.tshirts, slug="ukrainian-fit")
        self.add_fit_options(product, "класичний")

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"fit": "classic"},
        )

        self.assertEqual(response.context["paginator"].count, 1)
        self.assertEqual(response.context["smart_selector_selected_fit"], "classic")

    def test_smart_selector_validates_theme_and_fit_query_state(self):
        taxonomy = self.create_merch_taxonomy()
        product = self.create_product(
            category=self.tshirts,
            title="Military field tee",
            slug="military-field-tee",
        )
        self.add_fit_options(product, "oversize")
        ProductMerchCollection.objects.create(
            product=product,
            collection=taxonomy["military"],
        )

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"theme": "military", "fit": "oversize"},
        )
        invalid = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"theme": "not-a-theme", "fit": "not-a-fit"},
        )

        self.assertEqual(response.context["smart_selector_selected_theme"], "military")
        self.assertEqual(response.context["smart_selector_selected_fit"], "oversize")
        self.assertEqual(invalid.context["smart_selector_selected_theme"], "")
        self.assertEqual(invalid.context["smart_selector_selected_fit"], "")

    def test_smart_selector_ignores_fit_unavailable_in_current_category(self):
        product = self.create_product(category=self.tshirts, slug="classic-only")
        self.add_fit_options(product, "classic")

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"fit": "oversize"},
        )

        self.assertEqual(response.context["smart_selector_fit_codes"], ["classic"])
        self.assertEqual(response.context["smart_selector_selected_fit"], "")
        self.assertEqual(response.context["paginator"].count, 1)

    def test_theme_and_fit_filter_full_queryset_before_pagination(self):
        taxonomy = self.create_merch_taxonomy()
        first_match = self.create_product(
            category=self.tshirts,
            title="Military oversize one",
            slug="military-oversize-one",
        )
        second_match = self.create_product(
            category=self.tshirts,
            title="Military oversize two",
            slug="military-oversize-two",
        )
        wrong_theme = self.create_product(
            category=self.tshirts,
            title="Streetwear oversize",
            slug="streetwear-oversize",
        )
        wrong_fit = self.create_product(
            category=self.tshirts,
            title="Military classic",
            slug="military-classic",
        )
        self.add_fit_options(first_match, "oversize")
        self.add_fit_options(second_match, "oversize")
        self.add_fit_options(wrong_theme, "oversize")
        self.add_fit_options(wrong_fit, "classic")
        for product in (first_match, second_match, wrong_fit):
            ProductMerchCollection.objects.create(
                product=product,
                collection=taxonomy["military"],
            )
        ProductMerchCollection.objects.create(
            product=wrong_theme,
            collection=taxonomy["streetwear"],
        )

        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            response = self.client.get(
                reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
                {"theme": "military", "fit": "oversize"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paginator"].count, 2)
        self.assertEqual(response.context["paginator"].num_pages, 2)
        self.assertEqual([product.pk for product in response.context["products"]], [second_match.pk])
        self.assertContains(
            response,
            'data-next-page-url="?theme=military&amp;fit=oversize&amp;page=2"',
        )
        self.assertNotContains(response, wrong_theme.title)
        self.assertNotContains(response, wrong_fit.title)

    def test_theme_filter_uses_only_explicit_collection_assignments(self):
        taxonomy = self.create_merch_taxonomy()
        misleading = self.create_product(
            category=self.tshirts,
            title="Military 225 streetwear tee",
            slug="military-225-streetwear-tee",
        )
        assigned = self.create_product(
            category=self.tshirts,
            title="Нейтральна назва",
            slug="neutral-name",
        )
        ProductMerchCollection.objects.create(
            product=misleading,
            collection=taxonomy["streetwear"],
        )
        ProductMerchCollection.objects.create(
            product=assigned,
            collection=taxonomy["military"],
        )

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"theme": "military"},
        )

        self.assertEqual(response.context["paginator"].count, 1)
        self.assertContains(response, assigned.title)
        self.assertNotContains(response, misleading.title)

    def test_repeated_brigades_and_audiences_use_strict_and_before_pagination(self):
        taxonomy = self.create_merch_taxonomy()
        audiences = self.create_audience_tags()
        complete = self.create_product(category=self.tshirts, title="Повний збіг", slug="complete-match")
        one_brigade = self.create_product(category=self.tshirts, title="Лише 225", slug="only-225")
        one_audience = self.create_product(category=self.tshirts, title="Лише унісекс", slug="only-unisex")
        for product, collections, tags in (
            (complete, ("225", "127"), ("unisex", "women")),
            (one_brigade, ("225",), ("unisex", "women")),
            (one_audience, ("225", "127"), ("unisex",)),
        ):
            for slug in collections:
                ProductMerchCollection.objects.create(product=product, collection=taxonomy[slug])
            for code in tags:
                ProductAudience.objects.create(product=product, tag=audiences[code])

        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            response = self.client.get(
                reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
                [
                    ("collection", "225"),
                    ("collection", "127"),
                    ("audience", "unisex"),
                    ("audience", "women"),
                ],
            )

        self.assertEqual(response.context["paginator"].count, 1)
        self.assertEqual(response.context["smart_selector_facet_state"]["collection"], ("127", "225"))
        self.assertEqual(response.context["smart_selector_facet_state"]["audience"], ("unisex", "women"))
        self.assertContains(response, complete.title)
        self.assertNotContains(response, one_brigade.title)
        self.assertNotContains(response, one_audience.title)

    def test_brigades_theme_exposes_nested_children_in_public_context(self):
        self.create_merch_taxonomy()
        self.create_product(category=self.tshirts, slug="nested-brigade-context")

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        brigades = next(
            option
            for option in response.context["smart_selector_theme_options"]
            if option["code"] == "brigades"
        )
        self.assertEqual(
            [(child["code"], child["label"]) for child in brigades["children"]],
            [("225", "225 ОШП"), ("127", "127 бригада")],
        )

    def test_card_context_keeps_leaf_collection_and_structured_audiences(self):
        taxonomy = self.create_merch_taxonomy()
        audiences = self.create_audience_tags()
        product = self.create_product(category=self.tshirts, slug="leaf-card-context")
        ProductMerchCollection.objects.create(product=product, collection=taxonomy["brigades"])
        ProductMerchCollection.objects.create(product=product, collection=taxonomy["225"], order=1)
        ProductAudience.objects.create(product=product, tag=audiences["unisex"])
        ProductAudience.objects.create(product=product, tag=audiences["women"])

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))
        rendered_product = response.context["products"][0]

        self.assertEqual(
            [row["slug"] for row in rendered_product.smart_selector_collections],
            ["225"],
        )
        self.assertEqual(
            [row["code"] for row in rendered_product.smart_selector_audiences],
            ["unisex", "women"],
        )

    def test_root_and_search_keep_legacy_catalog_branch(self):
        self.create_product(category=self.tshirts, slug="root-product")
        root = self.client.get(reverse("catalog"))
        search = self.client.get(reverse("search"), {"q": "root"})

        self.assertFalse(root.context.get("smart_selector_enabled", False))
        self.assertNotContains(root, 'data-smart-selector="true"')
        self.assertFalse(search.context.get("smart_selector_enabled", False))
        self.assertNotContains(search, 'data-smart-selector="true"')

    def test_smart_selector_preserves_category_intro_and_color_seo_copy(self):
        self.tshirts.seo_intro_html = "<p>Короткий SEO вступ для футболок.</p>"
        self.tshirts.save(update_fields=["seo_intro_html"])
        product = self.create_product(category=self.tshirts, slug="color-seo-tshirt")
        black = Color.objects.create(name="black", primary_hex="#000000")
        ProductColorVariant.objects.create(product=product, color=black, is_default=True)

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"color": "black"},
        )

        self.assertContains(response, "Короткий SEO вступ для футболок.")
        self.assertContains(response, 'data-color-seo-color="black"')

    def test_smart_selector_color_chip_keeps_category_url_when_seo_landing_exists(self):
        product = self.create_product(category=self.tshirts, slug="landing-color-tshirt")
        black = Color.objects.create(name="black", primary_hex="#000000")
        ProductColorVariant.objects.create(product=product, color=black, is_default=True)
        CategoryColorLanding.objects.create(
            category=self.tshirts,
            color=black,
            color_slug="black",
            seo_title="Black T-shirts",
            seo_description="Black T-shirts TwoComms.",
            editorial_html="<p>Black T-shirts editorial copy.</p>",
            is_published=True,
        )

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        black_chip = next(
            chip for chip in response.context["available_colors"]
            if chip["slug"] == "black"
        )
        self.assertEqual(black_chip["url"], "/catalog/tshirts/?color=black")
        self.assertFalse(black_chip["is_landing"])

    def test_color_filtered_cards_do_not_reuse_another_color_fragment(self):
        product = self.create_product(category=self.tshirts, slug="two-color-tshirt")
        black = Color.objects.create(name="black", primary_hex="#000000")
        white = Color.objects.create(name="white", primary_hex="#ffffff")
        ProductColorVariant.objects.create(product=product, color=black, is_default=True)
        ProductColorVariant.objects.create(product=product, color=white, is_default=False)

        black_response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"color": "black"},
        )
        white_response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"color": "white"},
        )

        black_url = reverse("product", kwargs={"slug": product.slug, "v1": "black"})
        white_url = reverse("product", kwargs={"slug": product.slug, "v1": "white"})
        self.assertContains(black_response, f'data-product-url="{black_url}"')
        self.assertContains(white_response, f'data-product-url="{white_url}"')
        self.assertNotContains(white_response, f'data-product-url="{black_url}"')

    def test_price_sort_applies_to_full_queryset_before_pagination(self):
        expensive = self.create_product(category=self.tshirts, slug="expensive", price=1900)
        discounted = self.create_product(
            category=self.tshirts,
            slug="discounted",
            price=1800,
            discount_percent=50,
        )
        middle = self.create_product(category=self.tshirts, slug="middle", price=1200)

        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 2):
            ascending = self.client.get(
                reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
                {"sort": "price-asc"},
            )
            descending = self.client.get(
                reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
                {"sort": "price-desc"},
            )

        self.assertEqual(
            [product.pk for product in ascending.context["products"]],
            [discounted.pk, middle.pk],
        )
        self.assertEqual(
            [product.pk for product in descending.context["products"]],
            [expensive.pk, middle.pk],
        )
        self.assertContains(
            ascending,
            'data-next-page-url="?sort=price-asc&amp;page=2"',
        )

    def test_price_sort_uses_visible_variant_minimum_before_pagination(self):
        base_cheapest = self.create_product(
            category=self.tshirts,
            slug="base-cheapest-variant-expensive",
            price=700,
        )
        visible_cheapest = self.create_product(
            category=self.tshirts,
            slug="visible-cheapest",
            price=1200,
        )
        black = Color.objects.create(name="black", primary_hex="#000000")
        ProductColorVariant.objects.create(
            product=base_cheapest,
            color=black,
            is_default=True,
            price_override=1900,
        )

        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            response = self.client.get(
                reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
                {"sort": "price-asc"},
            )
            second_page = self.client.get(
                reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
                {"sort": "price-asc", "page": 2},
            )

        self.assertEqual(response.context["paginator"].count, 2)
        self.assertEqual(
            [product.pk for product in response.context["products"]],
            [visible_cheapest.pk],
        )
        self.assertEqual(response.context["products"][0].card_price_min, 1200)
        self.assertEqual(second_page.context["products"][0].card_price_min, 1900)
        self.assertContains(second_page, 'data-smart-price="1900"')

    def test_faceted_category_page_is_noindex_but_followable(self):
        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"theme": "military", "fit": "oversize"},
        )

        self.assertContains(response, 'content="noindex, follow"', html=False)
        self.assertContains(
            response,
            'href="https://twocomms.shop/catalog/tshirts/"',
            html=False,
        )
