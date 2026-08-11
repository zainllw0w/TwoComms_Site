from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import SimpleTestCase, TestCase

from productcolors.models import Color, ProductColorVariant
from storefront.models import (
    CatalogColorSeoOverride,
    Category,
    CategorySeoBlock,
    CategorySeoBlockItem,
    Product,
)
from storefront.services.category_seo_blocks import get_category_seo_blocks
from storefront.services.color_seo_copy import build_catalog_color_seo
from storefront.services.general_catalog_seo import get_general_catalog_seo_layout
from storefront.services.seo_link_policy import (
    filter_editorial_link_items,
    is_internal_ui_state_url,
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

    def test_generated_color_editorial_keeps_only_clean_owner_links(self):
        copy = build_catalog_color_seo(
            category=None,
            selected_color_slugs=None,
            available_colors=[],
        )

        self.assertIsNotNone(copy)
        self.assertTrue(copy["queries"])
        self.assertFalse(any("?" in item["url"] for item in copy["queries"]))
        self.assertNotIn("href=\"/catalog/?", " ".join(map(str, copy["paragraphs"])))
        self.assertIn('href="/catalog/tshirts/"', " ".join(map(str, copy["paragraphs"])))


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

    def test_catalog_keeps_ui_filter_but_editorial_sections_have_no_query_links(self):
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
        color_copy = body.split('<section class="catalog-color-seo"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertNotIn("href=\"/catalog/?", seo_tabs)
        self.assertNotIn("href=\"/catalog/?", color_copy)
        self.assertNotIn(f'href="/catalog/{self.category.slug}/?color=', seo_tabs)
