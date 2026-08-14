from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import SimpleTestCase, TestCase
from django.utils.translation import override

from productcolors.models import Color, ProductColorVariant
from storefront.models import (
    CatalogColorSeoOverride,
    Category,
    CategorySeoBlock,
    CategorySeoBlockItem,
    Product,
)
from storefront.services.category_seo_blocks import get_category_seo_blocks
from storefront.services.catalog_facets import FACET_ALLOWED
from storefront.services.color_seo_copy import build_catalog_color_seo
from storefront.services.general_catalog_seo import get_general_catalog_seo_layout
from storefront.services.seo_link_policy import (
    filter_editorial_link_items,
    is_internal_ui_state_url,
    prepare_editorial_html,
    strip_internal_ui_state_links,
)


class EditorialLinkPolicyUnitTests(SimpleTestCase):
    def test_filter_accepts_empty_editorial_item_source(self):
        self.assertEqual(filter_editorial_link_items(None), [])

    def test_policy_preserves_external_and_tracking_links(self):
        self.assertTrue(is_internal_ui_state_url("/catalog/?color=black"))
        self.assertFalse(is_internal_ui_state_url("/catalog/?utm_source=seo"))
        self.assertFalse(
            is_internal_ui_state_url("https://example.com/catalog/?color=black")
        )
        self.assertFalse(is_internal_ui_state_url("mailto:editor@example.com?color=black"))

        html = (
            '<p><a href="/catalog/?color=black">Black</a> '
            '<a href="/catalog/tshirts/?utm_source=seo">T-shirts</a> '
            '<a href="https://example.com/catalog/?color=black">External</a></p>'
        )
        cleaned = strip_internal_ui_state_links(html)

        self.assertNotIn('href="/catalog/?color=black"', cleaned)
        self.assertIn('href="/catalog/tshirts/?utm_source=seo"', cleaned)
        self.assertIn('href="https://example.com/catalog/?color=black"', cleaned)

    def test_every_catalog_facet_is_treated_as_ui_state(self):
        for key in FACET_ALLOWED:
            with self.subTest(key=key):
                self.assertTrue(
                    is_internal_ui_state_url(f"/catalog/tshirts/?{key}=value")
                )

    def test_prepare_editorial_html_unwraps_state_and_localizes_known_routes(self):
        html = (
            '<p><a class="state" href="/catalog/tshirts/?audience=women">'
            '<strong>Women</strong></a> '
            '<a data-kind="clean" href="/catalog/hoodie/?utm_source=seo#sizes">'
            'Hoodies</a> '
            '<a href="/en/catalog/long-sleeve/">Long sleeves</a> '
            '<a href="https://twocomms.shop/catalog/tshirts/">Absolute</a> '
            '<a href="https://example.com/catalog/hoodie/">External</a> '
            '<a href="mailto:editor@example.com">Mail</a> '
            '<a href="tel:+380000000000">Phone</a> '
            '<a href="#care">Care</a> '
            '<a href="/not-a-real-route/">Unknown</a></p>'
        )

        with override("ru"):
            prepared = prepare_editorial_html(html, language="ru")

        self.assertNotIn('<a class="state"', prepared)
        self.assertIn("<strong>Women</strong>", prepared)
        self.assertIn(
            'href="/ru/catalog/hoodie/?utm_source=seo#sizes"', prepared
        )
        self.assertIn('href="/ru/catalog/long-sleeve/"', prepared)
        self.assertIn(
            'href="https://twocomms.shop/ru/catalog/tshirts/"', prepared
        )
        self.assertIn('href="https://example.com/catalog/hoodie/"', prepared)
        self.assertIn('href="mailto:editor@example.com"', prepared)
        self.assertIn('href="tel:+380000000000"', prepared)
        self.assertIn('href="#care"', prepared)
        self.assertIn('href="/not-a-real-route/"', prepared)

    def test_general_catalog_seo_layout_does_not_link_to_query_facets(self):
        layout = get_general_catalog_seo_layout(
            categories=[],
            available_colors=[{"slug": "black", "label": "Black", "count": 8}],
        )

        urls = [
            item.url
            for entry in layout["tab_blocks"]
            for item in entry["items"]
        ]

        self.assertNotIn("/catalog/?color=black", urls)
        self.assertFalse(any("?" in url for url in urls))

    def test_general_catalog_without_editorial_owner_returns_none(self):
        copy = build_catalog_color_seo(
            category=None,
            selected_color_slugs=None,
            available_colors=[],
        )

        self.assertIsNone(copy)


class EditorialLinkPolicyDatabaseTests(TestCase):
    def setUp(self):
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            patcher = patch(target)
            self.addCleanup(patcher.stop)
            patcher.start()

        self.category = Category.objects.create(
            name="T-shirts",
            slug="seo-link-policy-tshirts",
            is_active=True,
        )

    def test_admin_seo_block_drops_query_facet_but_keeps_clean_link(self):
        block = CategorySeoBlock.objects.create(
            category=self.category,
            block_type="top_filters",
            title="Filters",
        )
        CategorySeoBlockItem.objects.create(
            block=block,
            label="Black query",
            url=f"/catalog/{self.category.slug}/?color=black",
            order=1,
        )
        CategorySeoBlockItem.objects.create(
            block=block,
            label="Black landing",
            url=f"/catalog/{self.category.slug}/black/",
            order=2,
        )

        entries = get_category_seo_blocks(self.category)

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            [item.url for item in entries[0]["items"]],
            [f"/catalog/{self.category.slug}/black/"],
        )

    def test_color_copy_admin_override_cannot_restore_query_links(self):
        CatalogColorSeoOverride.objects.create(
            scope="general",
            color_slug="",
            body_html=(
                '<p>Choose <a href="/catalog/?color=black">black</a> '
                'or <a href="/catalog/tshirts/">all T-shirts</a>.</p>'
            ),
            queries_json=[
                {
                    "label": "Black filter",
                    "url": "/catalog/?color=black",
                    "freq": "hf",
                },
                {
                    "label": "T-shirts",
                    "url": "/catalog/tshirts/",
                    "freq": "hf",
                },
            ],
            is_active=True,
        )

        copy = build_catalog_color_seo(
            category=None,
            selected_color_slugs=None,
            available_colors=[],
        )

        self.assertEqual(
            copy["queries"],
            [{"label": "T-shirts", "url": "/catalog/tshirts/", "freq": "hf"}],
        )
        paragraph = copy["paragraphs"][0]
        self.assertIn("Choose black", paragraph)
        self.assertNotIn('href="/catalog/?color=black"', paragraph)
        self.assertIn('href="/catalog/tshirts/"', paragraph)

    def test_catalog_keeps_ui_filter_without_unowned_color_editorial_section(self):
        black = Color.objects.create(name="Black", primary_hex="#000000")
        product = Product.objects.create(
            title="Policy tee",
            slug="policy-tee",
            category=self.category,
            price=800,
            status="published",
        )
        ProductColorVariant.objects.create(
            product=product,
            color=black,
            is_default=True,
        )

        response = self.client.get("/catalog/")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("?color=black", body)

        seo_tabs = body.split('<div class="category-seo-blocks"', 1)[1].split(
            "</div>\n\n<script>", 1
        )[0]
        self.assertNotIn("href=\"/catalog/?", seo_tabs)
        self.assertNotIn(f'href="/catalog/{self.category.slug}/?color=', seo_tabs)
        self.assertNotIn('<section class="catalog-color-seo"', body)


class CatalogEditorialHtmlIntegrationTests(TestCase):
    SMART_UK_MARKER = "UK smart fallback must not leak"
    LEGACY_UK_MARKER = "UK legacy fallback must not leak"

    @classmethod
    def setUpTestData(cls):
        cls.smart_category = Category.objects.create(
            name="Футболки",
            name_ru="Футболки",
            name_en="T-shirts",
            slug="tshirts",
            is_active=True,
            description_uk=(
                f'<p>{cls.SMART_UK_MARKER} '
                '<a href="/catalog/hoodie/?fit=oversize">UK state</a></p>'
            ),
            description_ru=(
                '<p>RU smart description '
                '<a href="/catalog/hoodie/?fit=oversize"><strong>Оверсайз</strong></a> '
                '<a href="/catalog/hoodie/?utm_source=seo#sizes">Худи</a></p>'
            ),
            description_en="",
            seo_intro_html_uk=f"<p>{cls.SMART_UK_MARKER} intro</p>",
            seo_intro_html_ru=(
                '<p>RU smart intro '
                '<a href="/en/catalog/long-sleeve/">Лонгсливы</a></p>'
            ),
            seo_intro_html_en="",
        )
        cls.legacy_category = Category.objects.create(
            name="Аксесуари",
            name_ru="Аксессуары",
            name_en="Accessories",
            slug="editorial-accessories",
            is_active=True,
            description_uk=f"<p>{cls.LEGACY_UK_MARKER}</p>",
            description_ru=(
                '<p>RU legacy description '
                '<a href="/catalog/tshirts/?thermo=thermo"><em>Термо</em></a> '
                '<a href="/catalog/tshirts/">Футболки</a></p>'
            ),
            description_en="",
            seo_intro_html_uk=f"<p>{cls.LEGACY_UK_MARKER} intro</p>",
            seo_intro_html_ru=(
                '<p>RU legacy intro '
                '<a href="/catalog/hoodie/">Худи</a></p>'
            ),
            seo_intro_html_en="",
        )
        Category.objects.create(
            name="Худі",
            name_ru="Худи",
            name_en="Hoodies",
            slug="hoodie",
            is_active=True,
        )
        Category.objects.create(
            name="Лонгсліви",
            name_ru="Лонгсливы",
            name_en="Long sleeves",
            slug="long-sleeve",
            is_active=True,
        )
        product = Product.objects.create(
            title="Editorial policy T-shirt",
            slug="editorial-policy-tshirt",
            category=cls.smart_category,
            price=900,
            status="published",
        )
        black = Color.objects.create(name="Black", primary_hex="#000000")
        ProductColorVariant.objects.create(
            product=product,
            color=black,
            is_default=True,
        )

    def setUp(self):
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            patcher = patch(target)
            self.addCleanup(patcher.stop)
            patcher.start()

    def test_smart_selector_uses_prepared_ru_editorial_html(self):
        response = self.client.get("/ru/catalog/tshirts/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-smart-selector="true"', response.content.decode())
        description = response.context["category_description_html"]
        intro = response.context["category_intro_html"]
        self.assertIn("<strong>Оверсайз</strong>", description)
        self.assertNotIn("?fit=oversize", description)
        self.assertIn(
            'href="/ru/catalog/hoodie/?utm_source=seo#sizes"', description
        )
        self.assertIn('href="/ru/catalog/long-sleeve/"', intro)
        self.assertContains(response, description, html=False)
        self.assertContains(response, intro, html=False)
        self.assertContains(
            response,
            'href="/ru/catalog/tshirts/?color=black"',
            html=False,
        )

    def test_legacy_catalog_uses_prepared_ru_editorial_html(self):
        response = self.client.get("/ru/catalog/editorial-accessories/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('data-smart-selector="true"', response.content.decode())
        description = response.context["category_description_html"]
        intro = response.context["category_intro_html"]
        self.assertIn("<em>Термо</em>", description)
        self.assertNotIn("?thermo=thermo", description)
        self.assertIn('href="/ru/catalog/tshirts/"', description)
        self.assertIn('href="/ru/catalog/hoodie/"', intro)
        self.assertContains(response, description, html=False)
        self.assertContains(response, intro, html=False)

    def test_blank_en_editorial_columns_do_not_fallback_to_uk(self):
        smart_response = self.client.get("/en/catalog/tshirts/")
        legacy_response = self.client.get("/en/catalog/editorial-accessories/")

        self.assertEqual(smart_response.status_code, 200)
        self.assertEqual(legacy_response.status_code, 200)
        self.assertEqual(smart_response.context["category_description_html"], "")
        self.assertEqual(smart_response.context["category_intro_html"], "")
        self.assertEqual(legacy_response.context["category_description_html"], "")
        self.assertEqual(legacy_response.context["category_intro_html"], "")
        self.assertNotContains(smart_response, self.SMART_UK_MARKER)
        self.assertNotContains(legacy_response, self.LEGACY_UK_MARKER)
