"""Contract tests for the category-scoped Variant 3 Smart Selector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from productcolors.models import Color, ProductColorVariant
from fable5.models import (
    AudienceTag,
    ColorProfile,
    MerchCollection,
    ProductAudience,
    ProductMerchCollection,
    VariantSizeRule,
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
        self.assertNotContains(response, "Швидкий перегляд")
        self.assertNotContains(response, "data-quick-view")
        self.assertNotContains(response, 'class="home-product-card card product')

    @override_settings(STATIC_URL="/static/")
    def test_image_less_card_uses_static_placeholder_url(self):
        self.create_product(category=self.tshirts, slug="placeholder-card")

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        self.assertContains(response, 'src="/static/img/placeholder.jpg"')
        self.assertNotContains(response, 'src="img/placeholder.jpg"')

    def test_narrow_mobile_cards_keep_title_and_price_above_bottom_navigation(self):
        css_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme/static/css/catalog-smart-selector.css"
        )
        css = css_path.read_text(encoding="utf-8")

        self.assertIn("@media (max-width: 340px)", css)
        self.assertIn("aspect-ratio: 1 / 1", css)

    def test_catalog_command_and_variant_3_quick_facets_precede_grid(self):
        self.create_product(category=self.tshirts, slug="quick-facet-order")
        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        html = response.content.decode()
        command_position = html.index('class="smart-selector__command"')
        quick_facets_position = html.index('class="smart-selector__quick-facets"')
        grid_position = html.index('class="smart-selector__grid"')

        self.assertLess(command_position, quick_facets_position)
        self.assertLess(quick_facets_position, grid_position)
        for mode in ("theme", "fit", "color"):
            self.assertContains(response, f'data-smart-focus-filter="{mode}"')

    def test_mobile_sort_and_sheet_expose_focused_variant_3_modes(self):
        self.create_product(category=self.tshirts, slug="focused-sheet")

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        self.assertContains(response, 'data-smart-focus-filter="all"')
        self.assertContains(response, 'data-smart-focus-filter="sort"')
        template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "partials"
            / "catalog_smart_selector.html"
        ).read_text(encoding="utf-8")
        for section in ("theme", "fit", "color", "sort", "audience", "availability", "size", "thermo"):
            self.assertIn(f'data-smart-filter-section="{section}"', template)
        self.assertContains(response, 'data-smart-sort-value="recommended"')
        self.assertContains(response, 'data-smart-sort-value="price-asc"')
        self.assertContains(response, 'data-smart-sort-value="price-desc"')

    def test_base_category_uses_compact_category_name_as_visible_h1(self):
        self.create_product(category=self.tshirts, slug="compact-heading")

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        self.assertContains(response, '<h1 id="smart-selector-title">Футболки</h1>')

    def test_product_card_hides_decision_metadata_and_visible_color_label(self):
        product = self.create_product(category=self.tshirts, slug="quiet-card")
        self.add_fit_options(product, "classic")
        color = Color.objects.create(name="black", primary_hex="#111111")
        ProductColorVariant.objects.create(product=product, color=color, is_default=True)

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        self.assertNotContains(response, 'class="smart-product-card__decision-meta"')
        self.assertNotContains(response, 'class="smart-product-card__color-label"')
        self.assertContains(response, 'aria-label="Доступні кольори"')

    def test_thermo_flame_is_nested_inside_color_swatch_dot(self):
        template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "partials"
            / "catalog_smart_product_card.html"
        ).read_text(encoding="utf-8")
        swatch_dot_markup = template.split('class="smart-product-card__swatch-dot"', 1)[1]

        self.assertLess(
            swatch_dot_markup.index('class="smart-product-card__thermo"'),
            swatch_dot_markup.index("</span>"),
        )

    def test_thermo_flame_has_no_secondary_circular_badge(self):
        css = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "catalog-smart-selector.css"
        ).read_text(encoding="utf-8")
        thermo_block = css.split(".smart-product-card__thermo {", 1)[1].split("}", 1)[0]

        self.assertIn("fill: #ffb15f", thermo_block)
        self.assertIn("filter: drop-shadow", thermo_block)
        self.assertNotIn("background:", thermo_block)
        self.assertNotIn("border-radius:", thermo_block)
        self.assertNotIn("box-shadow:", thermo_block)

    def test_product_card_uses_open_variant_3_surface(self):
        css = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "catalog-smart-selector.css"
        ).read_text(encoding="utf-8")
        card_block = css.split(".smart-product-card {", 1)[1].split("}", 1)[0]

        self.assertIn("padding: 0", card_block)
        self.assertIn("border: 0", card_block)
        self.assertIn("background: transparent", card_block)
        self.assertIn("box-shadow: none", card_block)

    def test_product_card_renders_quiet_fit_marker_next_to_price(self):
        product = self.create_product(category=self.tshirts, slug="fit-marker")
        self.add_fit_options(product, "oversize")

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        html = response.content.decode()
        price_row = html.split('class="smart-product-card__price-row"', 1)[1].split("</div>", 1)[0]
        self.assertIn('class="smart-product-card__fit"', price_row)
        self.assertIn("Oversize", price_row)

    def test_css_keeps_sticky_rail_unframed_and_favorite_visually_transparent(self):
        css = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "catalog-smart-selector.css"
        ).read_text(encoding="utf-8")
        root_block = css.split("[data-smart-selector] {", 1)[1].split("}", 1)[0]
        favorite_block = css.split(".smart-product-card__favorite {", 1)[1].split("}", 1)[0]
        desktop = css.split("@media (min-width: 1024px)", 1)[1]
        rail_block = desktop.split(".smart-selector__rail {", 1)[1].split("}", 1)[0]

        self.assertNotIn("overflow-x:", root_block)
        self.assertIn("border-right: 1px solid", rail_block)
        self.assertIn("background: transparent", rail_block)
        self.assertIn("box-shadow: none", rail_block)
        self.assertIn("background: transparent", favorite_block)
        self.assertIn("border-radius: 0", favorite_block)

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

    def test_card_swatch_with_legacy_unicode_slug_falls_back_to_product_url(self):
        product = self.create_product(category=self.tshirts, slug="legacy-thermo-slug")
        thermo = Color.objects.create(
            name="Термохром чорний",
            primary_hex="#171717",
            secondary_hex="#b5482d",
        )
        variant = ProductColorVariant.objects.create(
            product=product,
            color=thermo,
            is_default=True,
        )
        ProductColorVariant.objects.filter(pk=variant.pk).update(slug="термохром-black")

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("product", kwargs={"slug": product.slug})}"',
        )

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

    def test_indexable_brigade_has_curated_merch_landing(self):
        taxonomy = self.create_merch_taxonomy()
        product = self.create_product(
            category=self.tshirts,
            title="Мерч 225",
            slug="merch-225-product",
        )
        ProductMerchCollection.objects.create(
            product=product,
            collection=taxonomy["225"],
        )

        response = self.client.get(
            reverse("merch_collection", kwargs={"collection_slug": "225"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["smart_selector_enabled"])
        self.assertEqual(response.context["paginator"].count, 1)
        self.assertEqual(response.context["merch_collection_page"]["slug"], "225")
        self.assertContains(response, "Мерч для 225 ОШП — TwoComms")
        self.assertContains(response, 'content="index, follow, max-image-preview:large', html=False)
        self.assertContains(response, 'href="https://twocomms.shop/merch/225/"', html=False)

    def test_non_indexable_brigade_has_no_public_merch_landing(self):
        self.create_merch_taxonomy()

        response = self.client.get(
            reverse("merch_collection", kwargs={"collection_slug": "127"})
        )

        self.assertEqual(response.status_code, 404)

    def test_curated_merch_facet_state_is_noindex_and_canonical_to_collection(self):
        taxonomy = self.create_merch_taxonomy()
        product = self.create_product(category=self.tshirts, slug="merch-225-filtered")
        ProductMerchCollection.objects.create(product=product, collection=taxonomy["225"])

        response = self.client.get(
            reverse("merch_collection", kwargs={"collection_slug": "225"}),
            {"audience": "unisex"},
        )

        self.assertContains(response, 'content="noindex, follow"', html=False)
        self.assertContains(response, 'href="https://twocomms.shop/merch/225/"', html=False)

    def test_inventory_filter_controls_render_in_desktop_rail_and_mobile_sheet(self):
        product = self.create_product(category=self.tshirts, slug="inventory-filter-ui")
        color = Color.objects.create(name="thermo-black", primary_hex="#151515")
        variant = ProductColorVariant.objects.create(
            product=product,
            color=color,
            is_default=True,
        )
        ColorProfile.objects.create(color=color, is_thermo=True)
        VariantSizeRule.objects.create(
            variant=variant,
            size="M",
            is_enabled=True,
            stock=3,
        )

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}))

        self.assertEqual(response.context["smart_selector_size_options"][2]["code"], "M")
        self.assertContains(response, 'data-smart-filter="availability"', count=2)
        self.assertContains(response, 'data-smart-filter="size"', count=12)
        self.assertContains(response, 'data-smart-filter="thermo"', count=2)

    def test_product_card_exposes_authoritative_availability_label(self):
        product = self.create_product(
            category=self.tshirts,
            slug="availability-card-label",
        )

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "availability-card-label")
        self.assertContains(response, "В наявності")

    def test_inventory_facets_filter_before_pagination(self):
        available = self.create_product(
            category=self.tshirts,
            title="Available Thermo Product",
            slug="available-thermo",
        )
        sold_out = self.create_product(
            category=self.tshirts,
            title="Sold Out Ordinary Product",
            slug="sold-out-ordinary",
        )
        thermo_color = Color.objects.create(name="thermo-black", primary_hex="#111111")
        thermo_variant = ProductColorVariant.objects.create(
            product=available,
            color=thermo_color,
            is_default=True,
        )
        ColorProfile.objects.create(color=thermo_color, is_thermo=True)
        VariantSizeRule.objects.create(
            variant=thermo_variant,
            size="M",
            is_enabled=True,
            stock=2,
        )
        ordinary_color = Color.objects.create(name="ordinary-red", primary_hex="#aa2222")
        ordinary_variant = ProductColorVariant.objects.create(
            product=sold_out,
            color=ordinary_color,
            is_default=True,
        )
        VariantSizeRule.objects.create(
            variant=ordinary_variant,
            size="M",
            is_enabled=True,
            stock=0,
        )

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": "tshirts"}),
            {"availability": "in_stock", "size": "M", "thermo": "thermo"},
        )

        self.assertEqual(response.context["paginator"].count, 1)
        self.assertEqual(response.context["smart_selector_facet_state"]["size"], ("M",))
        self.assertEqual(response.context["smart_selector_facet_state"]["thermo"], ("thermo",))
        self.assertContains(response, available.title)
        self.assertNotContains(response, sold_out.title)


class SmartSelectorAnalyticsContractTests(SimpleTestCase):
    def test_catalog_selector_uses_checkout_palette_without_purple(self):
        css = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "catalog-smart-selector.css"
        ).read_text(encoding="utf-8")

        self.assertNotIn("#a77bf7", css.lower())
        self.assertNotIn("#7c4bd8", css.lower())
        self.assertIn("--smart-accent: #f3a43d", css)
        self.assertIn("--smart-action: #ff6b2b", css)
        self.assertIn("border-radius: 22px 22px 0 0", css)
        self.assertIn(".smart-selector__sheet::before", css)

    def test_smart_selector_tracks_state_changes_and_smart_card_selection(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "js"
            / "catalog-smart-selector.js"
        ).read_text(encoding="utf-8")

        self.assertIn("CatalogFilterApply", source)
        self.assertIn("CatalogFilterClear", source)
        self.assertIn("CatalogFilterSheetOpen", source)
        self.assertIn("CatalogFilterSheetClose", source)
        self.assertIn("CatalogProgressiveLoad", source)
        self.assertIn("smart-product-card", source)
        self.assertIn("CatalogSelectItem", source)

    def test_smart_selector_bumps_assets_after_interaction_contract_change(self):
        template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "catalog.html"
        ).read_text(encoding="utf-8")

        self.assertIn("catalog-smart-selector.css' %}?v=20260808-v12", template)
        self.assertIn("catalog-smart-selector.js' %}?v=20260808-v12", template)
