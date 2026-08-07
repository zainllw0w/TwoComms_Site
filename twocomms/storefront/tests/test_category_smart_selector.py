"""Contract tests for the category-scoped Variant 3 Smart Selector."""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase
from django.urls import reverse

from storefront.models import Category, Product, ProductFitOption


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

    def test_category_tabs_use_real_urls_and_selected_category(self):
        self.create_product(category=self.hoodie)
        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": "hoodie"}))

        self.assertEqual(response.context["smart_selector_active_category"].slug, "hoodie")
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

    def test_smart_selector_validates_theme_and_fit_query_state(self):
        self.create_product(category=self.tshirts, title="Military field tee", slug="military-field-tee")

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

    def test_theme_and_fit_filter_full_queryset_before_pagination(self):
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

    def test_root_and_search_keep_legacy_catalog_branch(self):
        self.create_product(category=self.tshirts, slug="root-product")
        root = self.client.get(reverse("catalog"))
        search = self.client.get(reverse("search"), {"q": "root"})

        self.assertFalse(root.context.get("smart_selector_enabled", False))
        self.assertNotContains(root, 'data-smart-selector="true"')
        self.assertFalse(search.context.get("smart_selector_enabled", False))
        self.assertNotContains(search, 'data-smart-selector="true"')

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
